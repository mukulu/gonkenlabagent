#!/usr/bin/env python3
"""Private, offline Git recovery transport. This is not an application QA gate."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.parse import urlsplit

SCHEMA = 'gonken-standalone-recovery-v1'
META = 'gonken-recovery/RECOVERY_STATE.json'
BUNDLE = 'gonken-recovery/repository.bundle'
MAX_ARCHIVE = 128 * 1024 * 1024
MAX_BUNDLE = 128 * 1024 * 1024
MAX_META = 1024 * 1024
HEX = re.compile(r'^(?:[0-9a-f]{40}|[0-9a-f]{64})$')
SHA = re.compile(r'^[0-9a-f]{64}$')


class RecoveryError(Exception):
    """A refusal that must not be converted into a recovery PASS."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RecoveryError(reason)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


class Runner:
    def __init__(self, seconds: float = 120):
        require(0 < seconds <= 600, 'INVALID_TIME_BUDGET')
        self.deadline = time.monotonic() + seconds

    def run(self, argv: list[str], ok: tuple[int, ...] = (0,)) -> tuple[int, bytes]:
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, 'TOTAL_TIME_BUDGET_EXHAUSTED')
        # Ignore caller-injected Git configuration, alternate worktrees, tracing,
        # credential helpers and template hooks. Commands never use a shell.
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1', LC_ALL='C')
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, start_new_session=True)
        try:
            stdout, stderr = proc.communicate(timeout=min(remaining, 60))
        except subprocess.TimeoutExpired:
            # Kill the whole command group, including Git helpers, on POSIX.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()
            raise RecoveryError('COMMAND_TIMEOUT') from None
        require(proc.returncode in ok, 'COMMAND_FAILED:' + argv[0] + ':' + str(proc.returncode))
        require(len(stdout) <= 4 * 1024 * 1024, 'COMMAND_OUTPUT_TOO_LARGE')
        return proc.returncode, stdout

    def git(self, repo: Path, *args: str, ok: tuple[int, ...] = (0,)) -> str:
        _, out = self.run(['git', '-c', 'core.hooksPath=' + os.devnull,
                          '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0',
                          '-c', 'maintenance.auto=false', '-c', 'protocol.allow=never',
                          '-c', 'protocol.file.allow=always', '-C', str(repo), *args], ok)
        return out.decode('utf-8', errors='strict').strip()


def simple_text(value: object, maximum: int = 512) -> bool:
    return isinstance(value, str) and 0 < len(value) <= maximum and all(ord(c) >= 32 for c in value)


def safe_origin(value: object) -> bool:
    if value is None:
        return True
    if not simple_text(value):
        return False
    if re.fullmatch(r'git@[A-Za-z0-9.-]+:[A-Za-z0-9._/-]+', value):
        return True
    p = urlsplit(value)
    return (p.scheme == 'https' and bool(p.hostname) and not p.username
            and not p.password and not p.query and not p.fragment)


def refs_of(repo: Path, runner: Runner) -> dict:
    text = runner.git(repo, 'for-each-ref', '--format=%(refname) %(objectname) %(symref)')
    refs = {}
    for line in text.splitlines():
        fields = line.split(' ', 2)
        name, oid = fields[:2]
        target = fields[2] if len(fields) == 3 and fields[2] else None
        require(not name.startswith('refs/replace/'), 'REPLACE_REFS_UNSUPPORTED')
        require(name not in refs, 'DUPLICATE_REF')
        refs[name] = {'oid': oid, 'symbolic_target': target}
    require(0 < len(refs) <= 1024, 'REF_COUNT_UNSUPPORTED')
    return refs


def check_tree(repo: Path, runner: Runner) -> None:
    # A plain Git bundle cannot carry submodule repositories or LFS objects.
    # Refuse rather than present a partial worktree as a complete backup.
    data = runner.git(repo, 'ls-tree', '-r', '-z', 'HEAD')
    for item in data.split('\0'):
        if not item:
            continue
        header, path = item.split('\t', 1)
        mode = header.split()[0]
        require(mode != '160000', 'SUBMODULE_BACKUP_UNSUPPORTED')
        require(mode != '120000', 'SYMLINK_CHECKOUT_UNSUPPORTED')
        pp = PurePosixPath(path)
        require(not pp.is_absolute() and '..' not in pp.parts and '.git' not in pp.parts,
                'UNSAFE_TRACKED_PATH')
    _, candidates = runner.run(['git', '-c', 'core.hooksPath=' + os.devnull, '-C', str(repo),
                                'grep', '-z', '-l', '-I',
                                r'^version https://git-lfs\.github\.com/spec/v1$',
                                'HEAD', '--'], ok=(0, 1))
    paths = [p for p in candidates.decode('utf-8').split('\0') if p]
    require(len(paths) <= 64, 'LFS_CANDIDATE_LIMIT')
    for path in paths:
        content = runner.git(repo, 'cat-file', 'blob', path)
        lines = content.splitlines()
        is_pointer = (lines and lines[0] == 'version https://git-lfs.github.com/spec/v1'
                      and any(re.fullmatch(r'oid sha256:[0-9a-f]{64}', x) for x in lines)
                      and any(re.fullmatch(r'size [0-9]+', x) for x in lines))
        require(not is_pointer, 'LFS_OBJECT_BACKUP_UNSUPPORTED')


def inspect_repo(repo: Path, runner: Runner) -> dict:
    require((repo / '.git').is_dir(), 'FULL_NONBARE_CHECKOUT_REQUIRED')
    require(runner.git(repo, 'rev-parse', '--show-toplevel') == str(repo.resolve()),
            'REPOSITORY_ROOT_REQUIRED')
    require(runner.git(repo, 'rev-parse', '--is-shallow-repository') == 'false',
            'SHALLOW_REPOSITORY_UNSUPPORTED')
    require(not runner.git(repo, 'config', '--get', 'extensions.partialClone', ok=(0, 1)),
            'PARTIAL_CLONE_UNSUPPORTED')
    require(runner.git(repo, 'config', '--get', 'core.sparseCheckout', ok=(0, 1)) != 'true',
            'SPARSE_CHECKOUT_UNSUPPORTED')
    require(not runner.git(repo, 'status', '--porcelain=v1', '--untracked-files=all'),
            'UNCOMMITTED_OR_UNTRACKED_FILES')
    flags = runner.git(repo, 'ls-files', '-v', '-z')
    require(not any(x and (x[0].islower() or x[0] == 'S') for x in flags.split('\0')),
            'HIDDEN_INDEX_STATE_UNSUPPORTED')
    origin = runner.git(repo, 'config', '--get', 'remote.origin.url', ok=(0, 1)) or None
    require(safe_origin(origin), 'CREDENTIAL_BEARING_OR_UNSUPPORTED_ORIGIN')
    branch = runner.git(repo, 'symbolic-ref', '-q', 'HEAD', ok=(0, 1)) or None
    identity = {}
    for key in ('user.name', 'user.email'):
        value = runner.git(repo, 'config', '--get', key, ok=(0, 1))
        if value:
            require(simple_text(value), 'INVALID_GIT_IDENTITY')
            identity[key] = value
    tracking = None
    if branch:
        short = branch.removeprefix('refs/heads/')
        remote = runner.git(repo, 'config', '--get', 'branch.' + short + '.remote', ok=(0, 1))
        merge = runner.git(repo, 'config', '--get', 'branch.' + short + '.merge', ok=(0, 1))
        if remote == 'origin' and merge.startswith('refs/heads/'):
            tracking = {'remote': remote, 'merge': merge}
    return {'head': runner.git(repo, 'rev-parse', 'HEAD'),
            'tree': runner.git(repo, 'rev-parse', 'HEAD^{tree}'),
            'object_format': runner.git(repo, 'rev-parse', '--show-object-format'),
            'branch': branch, 'refs': refs_of(repo, runner), 'origin': origin,
            'git_identity': identity, 'tracking': tracking}


def validate_meta(meta: object, runner: Runner, repo: Path) -> dict:
    require(isinstance(meta, dict), 'METADATA_NOT_OBJECT')
    require(meta.get('schema') == SCHEMA, 'SCHEMA_UNSUPPORTED')
    require(meta.get('validation_scope') == 'GIT_TRANSPORT_ONLY', 'FALSE_QA_SCOPE')
    require(meta.get('physical_acceptance_claimed') is False, 'FALSE_PHYSICAL_CLAIM')
    require(simple_text(meta.get('checkpoint')) and simple_text(meta.get('next_action'), 4096),
            'MISSING_HANDOFF_CONTEXT')
    require(isinstance(meta.get('bundle_sha256'), str) and SHA.fullmatch(meta['bundle_sha256']),
            'BUNDLE_DIGEST_INVALID')
    state = meta.get('repository')
    require(isinstance(state, dict), 'REPOSITORY_METADATA_INVALID')
    require(state.get('object_format') in ('sha1', 'sha256'), 'OBJECT_FORMAT_UNSUPPORTED')
    for key in ('head', 'tree'):
        require(isinstance(state.get(key), str) and HEX.fullmatch(state[key]), 'OBJECT_ID_INVALID')
    require(safe_origin(state.get('origin')), 'UNSAFE_ORIGIN')
    refs = state.get('refs')
    require(isinstance(refs, dict) and 0 < len(refs) <= 1024, 'REFS_INVALID')
    for name, ref in refs.items():
        require(simple_text(name) and name.startswith('refs/') and not name.startswith('refs/replace/'),
                'REF_NAME_INVALID')
        runner.git(repo, 'check-ref-format', name)
        require(isinstance(ref, dict) and isinstance(ref.get('oid'), str)
                and HEX.fullmatch(ref['oid']), 'REF_OBJECT_INVALID')
        target = ref.get('symbolic_target')
        require(target is None or (isinstance(target, str) and target in refs and target != name and
                                   refs[target].get('symbolic_target') is None and
                                   refs[target].get('oid') == ref['oid']), 'SYMBOLIC_REF_INVALID')
    branch = state.get('branch')
    require(branch is None or (isinstance(branch, str) and branch in refs and branch.startswith('refs/heads/') and
                               refs[branch]['oid'] == state['head'] and
                               refs[branch].get('symbolic_target') is None), 'HEAD_BRANCH_MISMATCH')
    identity = state.get('git_identity')
    require(isinstance(identity, dict) and set(identity) <= {'user.name', 'user.email'} and
            all(simple_text(v) for v in identity.values()), 'IDENTITY_INVALID')
    tracking = state.get('tracking')
    if tracking is not None:
        require(isinstance(tracking, dict) and tracking.get('remote') == 'origin' and
                isinstance(tracking.get('merge'), str) and
                tracking['merge'].startswith('refs/heads/') and bool(branch) and
                bool(state.get('origin')), 'TRACKING_INVALID')
        runner.git(repo, 'check-ref-format', tracking['merge'])
    return meta


def read_archive(archive: Path, expected_sha: str, scratch: Path) -> tuple[dict, Path]:
    require(isinstance(expected_sha, str) and SHA.fullmatch(expected_sha), 'EXPECTED_SHA256_REQUIRED')
    require(archive.is_file() and not archive.is_symlink(), 'ARCHIVE_NOT_REGULAR_FILE')
    require(0 < archive.stat().st_size <= MAX_ARCHIVE, 'ARCHIVE_SIZE_UNSUPPORTED')
    require(digest(archive) == expected_sha, 'ARCHIVE_SHA256_MISMATCH')
    seen = set()
    payload = None
    bundle = scratch / 'repository.bundle'
    try:
        with tarfile.open(archive, 'r:bz2') as tf:
            for member in tf:
                require(member.name in (META, BUNDLE) and member.name not in seen,
                        'UNEXPECTED_OR_DUPLICATE_MEMBER')
                require(member.isfile() and not member.issparse(), 'UNSAFE_MEMBER_TYPE')
                limit = MAX_META if member.name == META else MAX_BUNDLE
                require(0 < member.size <= limit, 'MEMBER_SIZE_UNSUPPORTED')
                seen.add(member.name)
                f = tf.extractfile(member)
                require(f is not None, 'MEMBER_UNREADABLE')
                if member.name == META:
                    payload = f.read(limit + 1)
                    require(len(payload) == member.size, 'MEMBER_TRUNCATED')
                else:
                    with bundle.open('xb') as dst:
                        shutil.copyfileobj(f, dst, 1024 * 1024)
                    require(bundle.stat().st_size == member.size, 'BUNDLE_TRUNCATED')
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise RecoveryError('ARCHIVE_READ_FAILED:' + type(exc).__name__) from None
    require(seen == {META, BUNDLE} and payload is not None, 'INCOMPLETE_ARCHIVE')
    try:
        # Duplicate JSON keys are not allowed to hide conflicting metadata.
        def unique(pairs):
            d = {}
            for k, v in pairs:
                require(k not in d, 'DUPLICATE_JSON_KEY')
                d[k] = v
            return d
        meta = json.loads(payload, object_pairs_hook=unique)
    except (ValueError, UnicodeError):
        raise RecoveryError('METADATA_JSON_INVALID') from None
    require(isinstance(meta, dict) and digest(bundle) == meta.get('bundle_sha256'),
            'BUNDLE_SHA256_MISMATCH')
    return meta, bundle


def restore(archive: Path, destination: Path, expected_sha: str, expected_head: str,
            seconds: float = 120) -> dict:
    runner = Runner(seconds)
    require(HEX.fullmatch(expected_head) is not None, 'EXPECTED_COMMIT_REQUIRED')
    require(not destination.exists() and not destination.is_symlink(), 'DESTINATION_EXISTS')
    require(destination.parent.is_dir(), 'DESTINATION_PARENT_MISSING')
    with tempfile.TemporaryDirectory(prefix='.recovery-read-', dir=destination.parent) as temp:
        meta, bundle = read_archive(archive, expected_sha, Path(temp))
        validate_meta(meta, runner, Path(temp))
        state = meta['repository']
        require(state['head'] == expected_head, 'EXPECTED_COMMIT_MISMATCH')
        # Exclusive mkdir is the no-overwrite boundary. Nothing in the archive is
        # executed; only fixed Git built-ins populate this newly allocated checkout.
        destination.mkdir(mode=0o700)
        try:
            runner.git(destination, 'init', '--quiet', '--template=',
                       '--object-format=' + state['object_format'])
            runner.git(destination, 'bundle', 'verify', str(bundle))
            runner.git(destination, 'bundle', 'unbundle', str(bundle))
            for name, ref in state['refs'].items():
                if ref['symbolic_target'] is None:
                    runner.git(destination, 'update-ref', name, ref['oid'])
            for name, ref in state['refs'].items():
                if ref['symbolic_target'] is not None:
                    runner.git(destination, 'symbolic-ref', name, ref['symbolic_target'])
            if state['branch']:
                runner.git(destination, 'symbolic-ref', 'HEAD', state['branch'])
            else:
                runner.git(destination, 'update-ref', '--no-deref', 'HEAD', state['head'])
            runner.git(destination, 'fsck', '--full', '--strict')
            check_tree(destination, runner)
            runner.git(destination, 'reset', '--hard', '--quiet', state['head'])
            if state['origin']:
                runner.git(destination, 'remote', 'add', 'origin', state['origin'])
            for k, v in state['git_identity'].items():
                runner.git(destination, 'config', k, v)
            if state['tracking']:
                short = state['branch'].removeprefix('refs/heads/')
                runner.git(destination, 'config', 'branch.' + short + '.remote', 'origin')
                runner.git(destination, 'config', 'branch.' + short + '.merge', state['tracking']['merge'])
            require(inspect_repo(destination.resolve(), runner) == state, 'RESTORED_IDENTITY_MISMATCH')
        except BaseException:
            shutil.rmtree(destination)
            raise
    return {'status': 'COLD_RESTORE_VERIFIED', 'scope': 'GIT_TRANSPORT_ONLY',
            'archive_sha256': expected_sha, 'head': expected_head, 'tree': state['tree'],
            'checkpoint': meta['checkpoint'], 'next_action': meta['next_action'],
            'destination': str(destination.resolve()), 'delivery_verified': False,
            'physical_acceptance_claimed': False}


def verify(archive: Path, expected_sha: str, expected_head: str, seconds: float = 120) -> dict:
    with tempfile.TemporaryDirectory(prefix='gonken-cold-verify-') as temp:
        report = restore(archive, Path(temp) / 'checkout', expected_sha, expected_head, seconds)
        del report['destination']
        return report


def create(repo: Path, output: Path, checkpoint: str, next_action: str,
           expected_head: str, seconds: float = 120) -> dict:
    runner = Runner(seconds)
    repo, output = repo.resolve(), output.absolute()
    require(output.suffixes[-2:] == ['.tar', '.bz2'], 'TAR_BZ2_REQUIRED')
    require(not output.exists() and not output.is_symlink(), 'OUTPUT_EXISTS')
    require(output.parent.is_dir(), 'OUTPUT_PARENT_MISSING')
    require(not output.resolve().is_relative_to(repo), 'OUTPUT_INSIDE_SOURCE')
    require(simple_text(checkpoint) and simple_text(next_action, 4096), 'HANDOFF_CONTEXT_REQUIRED')
    before = inspect_repo(repo, runner)
    require(before['head'] == expected_head, 'EXPECTED_COMMIT_MISMATCH')
    runner.git(repo, 'fsck', '--full', '--strict')
    check_tree(repo, runner)
    with tempfile.TemporaryDirectory(prefix='.recovery-build-', dir=output.parent) as temp:
        scratch = Path(temp)
        bundle = scratch / 'repository.bundle'
        runner.git(repo, 'bundle', 'create', str(bundle), '--all', 'HEAD')
        require(bundle.stat().st_size <= MAX_BUNDLE, 'BUNDLE_TOO_LARGE')
        require(inspect_repo(repo, runner) == before, 'SOURCE_CHANGED_DURING_EXPORT')
        meta = {'schema': SCHEMA, 'checkpoint': checkpoint, 'next_action': next_action,
                'validation_scope': 'GIT_TRANSPORT_ONLY', 'physical_acceptance_claimed': False,
                'repository': before, 'bundle_sha256': digest(bundle),
                'exclusions': ['untracked_files', 'ignored_files', 'hooks', 'local_credentials',
                               'reflogs_and_unreachable_objects'],
                'privacy': 'PRIVATE_GIT_HISTORY; no claim that historical tracked content is secret-free'}
        blob = (json.dumps(meta, sort_keys=True, indent=2) + '\n').encode()
        require(len(blob) <= MAX_META, 'METADATA_TOO_LARGE')
        pending = scratch / 'checkpoint.tar.bz2'
        with tarfile.open(pending, 'w:bz2', compresslevel=1, format=tarfile.USTAR_FORMAT) as tf:
            info = tarfile.TarInfo(META)
            info.size, info.mode, info.mtime = len(blob), 0o600, 0
            tf.addfile(info, io.BytesIO(blob))
            info = tarfile.TarInfo(BUNDLE)
            info.size, info.mode, info.mtime = bundle.stat().st_size, 0o600, 0
            with bundle.open('rb') as f:
                tf.addfile(info, f)
        os.chmod(pending, 0o600)
        checksum = digest(pending)
        remaining = runner.deadline - time.monotonic()
        report = verify(pending, checksum, expected_head, remaining)
        require(inspect_repo(repo, runner) == before, 'SOURCE_CHANGED_BEFORE_PUBLICATION')
        with pending.open('rb') as f:
            os.fsync(f.fileno())
        # Link the completely verified file without replacing any prior artifact.
        try:
            os.link(pending, output)
        except FileExistsError:
            raise RecoveryError('OUTPUT_EXISTS') from None
        directory_fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    report.update(archive=str(output), size_bytes=output.stat().st_size,
                  status='LOCAL_ARTIFACT_VERIFIED_NOT_DELIVERED')
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('create')
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--checkpoint', required=True)
    p.add_argument('--next-action', required=True)
    for cmd in ('verify', 'restore'):
        p = subs.add_parser(cmd)
        p.add_argument('--archive', type=Path, required=True)
        p.add_argument('--sha256', required=True)
        if cmd == 'restore':
            p.add_argument('--destination', type=Path, required=True)
    for p in subs.choices.values():
        p.add_argument('--expected-commit', required=True)
        p.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args(argv)
    try:
        if args.command == 'create':
            result = create(args.repo, args.output, args.checkpoint, args.next_action,
                            args.expected_commit, args.timeout)
        elif args.command == 'restore':
            result = restore(args.archive.resolve(), args.destination.absolute(), args.sha256,
                             args.expected_commit, args.timeout)
        else:
            result = verify(args.archive.resolve(), args.sha256, args.expected_commit, args.timeout)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (RecoveryError, OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({'status': 'REFUSED', 'reason': str(exc),
                          'scope': 'GIT_TRANSPORT_ONLY', 'delivery_verified': False}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
