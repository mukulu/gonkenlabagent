#!/usr/bin/env python3
"""Build, validate, activate, and reconcile immutable GonKenLab releases.

The module intentionally uses only the Python standard library at runtime.
Candidate construction may invoke Git, venv/pip, and the source tree's declared
build backend. Every installed release is bound to a full Git commit and stays
inactive until its real smoke checks pass.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import venv
from pathlib import Path, PurePosixPath
from typing import Iterable


COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RELEASE_FIELDS = (
    "format",
    "commit",
    "profile",
    "python_version",
    "package_version",
    "lock_sha256",
    "wheel_sha256",
    "build_backend",
    "maintenance_sha256",
    "payload_sha256",
    "owner_uid",
    "payload_size_kib",
    "built_epoch",
    "validation",
)
JOURNAL_FIELDS = (
    "format",
    "candidate_commit",
    "previous_commit",
    "phase",
    "observed_epoch",
    "message",
)
JOURNAL_PHASES = {"prepared", "switched", "post_verified", "rolled_back"}


class ReleaseError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, exit_code: int = 74):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.exit_code = exit_code


def fail(code: str, message: str, remediation: str, exit_code: int = 74) -> None:
    raise ReleaseError(code, message, remediation, exit_code)


def emit_error(error: ReleaseError) -> None:
    print(
        f"[ERROR] code={error.code} message={error} remediation={error.remediation}",
        file=sys.stderr,
    )


def require_absolute(path: str, label: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute() or "\n" in path or "\r" in path or ".." in candidate.parts:
        fail("RELEASE_PATH", f"{label} must be an absolute normalized path", "supply a safe absolute path", 64)
    return candidate


def require_commit(value: str) -> str:
    if not COMMIT_RE.fullmatch(value):
        fail("RELEASE_COMMIT", "release commit must be a full lowercase Git SHA", "use the commit recorded by bootstrap", 64)
    return value


def require_profile(value: str) -> str:
    if not PROFILE_RE.fullmatch(value):
        fail("RELEASE_PROFILE", "invalid dependency profile identifier", "use an accepted requirements profile", 64)
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(
    arguments: list[str],
    *,
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
    service_user: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = arguments
    if service_user and os.geteuid() == 0 and service_user != "root":
        command = ["runuser", "-u", service_user, "--", *arguments]
    merged = os.environ.copy()
    merged.pop("PYTHONPATH", None)
    merged.pop("PYTHONHOME", None)
    merged["PYTHONDONTWRITEBYTECODE"] = "1"
    merged["PYTHONNOUSERSITE"] = "1"
    merged["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    merged["PIP_NO_INPUT"] = "1"
    if environment:
        merged.update(environment)
    result = subprocess.run(
        command,
        cwd=cwd,
        env=merged,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")[:400]
        fail(
            "RELEASE_COMMAND",
            f"command failed with exit {result.returncode}: {detail or arguments[0]}",
            "inspect installer events and the candidate before rerunning",
            result.returncode if 1 <= result.returncode <= 125 else 74,
        )
    return result


def read_record(path: Path, fields: Iterable[str], expected_format: str) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        fail("RELEASE_RECORD", f"missing or unsafe record: {path}", "restore a validated root-owned record", 75)
    allowed = set(fields)
    output: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        fail("RELEASE_RECORD", f"cannot read record: {exc}", "inspect the installed state manually", 75)
    for line in lines:
        if "=" not in line or "\r" in line:
            fail("RELEASE_RECORD", "record contains a malformed line", "restore a validated record", 75)
        key, value = line.split("=", 1)
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key) or key not in allowed or key in output:
            fail("RELEASE_RECORD", "record has an unknown or duplicate field", "restore a validated record", 75)
        output[key] = value
    if set(output) != allowed or output.get("format") != expected_format:
        fail("RELEASE_RECORD", "record schema is incomplete or unsupported", "restore the matching schema", 75)
    return output


def _safe_record_lines(fields: dict[str, str]) -> bytes:
    for key, value in fields.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key) or "\n" in value or "\r" in value:
            fail("RELEASE_RECORD", "unsafe record field", "use single-line machine values", 73)
    return "".join(f"{key}={value}\n" for key, value in fields.items()).encode()


def maybe_interrupt(operation: str, point: str) -> None:
    if os.environ.get("GONKEN_ENABLE_TEST_FAILURES") != "1":
        return
    if os.environ.get("GONKEN_RELEASE_TEST_INTERRUPT") != f"{operation}:{point}":
        return
    mode = os.environ.get("GONKEN_RELEASE_TEST_INTERRUPT_MODE", "term")
    chosen = signal.SIGTERM if mode == "term" else signal.SIGKILL if mode == "kill" else None
    if chosen is None:
        fail("RELEASE_TEST_CONTROL", "unknown release interruption mode", "use term or kill", 64)
    os.kill(os.getppid(), chosen)
    os.kill(os.getpid(), chosen)


def durable_record(path: Path, fields: dict[str, str], operation: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        fail("RELEASE_RECORD", "record destination is a symlink", "remove the unsafe path after inspection", 73)
    for stale in path.parent.glob(".journal.*"):
        if stale.is_file() and not stale.is_symlink():
            stale.unlink()
    payload = _safe_record_lines(fields)
    maybe_interrupt(operation, "before")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".journal.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        maybe_interrupt(operation, "during")
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        maybe_interrupt(operation, "after")
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def ensure_real_directory(path: Path, mode: int) -> None:
    if path.is_symlink():
        fail("RELEASE_LAYOUT", f"unsafe symbolic-link directory: {path}", "replace it with a root-owned real directory", 73)
    path.mkdir(parents=True, exist_ok=True, mode=mode)
    if not path.is_dir() or path.is_symlink():
        fail("RELEASE_LAYOUT", f"not a real directory: {path}", "repair the installation layout", 73)
    path.chmod(mode)


@contextlib.contextmanager
def maintenance_lock(state_root: Path):
    ensure_real_directory(state_root, 0o700)
    path = state_root / "maintenance.lock"
    if path.is_symlink():
        fail("ACTIVATION_LOCK", "maintenance lock is a symlink", "inspect the root-owned state manually", 75)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail("ACTIVATION_BUSY", "another activation or reconciliation owns the maintenance lock", "wait for it to finish and rerun", 75)
        yield
    finally:
        os.close(descriptor)


def init_layout(release_root: Path, state_root: Path, bin_root: Path) -> None:
    ensure_real_directory(release_root, 0o755)
    ensure_real_directory(release_root / "releases", 0o755)
    ensure_real_directory(state_root, 0o700)
    ensure_real_directory(bin_root, 0o755)
    entrypoint = bin_root / "gonken-agent"
    expected_target = os.path.relpath(
        release_root / "current" / ".venv" / "bin" / "gonken-agent",
        bin_root,
    )
    if entrypoint.exists() and not entrypoint.is_symlink():
        fail("RELEASE_LAYOUT", f"stable entrypoint is not a symlink: {entrypoint}", "move the conflicting administrator file", 73)
    if entrypoint.is_symlink() and os.readlink(entrypoint) == expected_target:
        return
    temporary = bin_root / f".gonken-agent.{os.getpid()}"
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    temporary.symlink_to(expected_target)
    os.replace(temporary, entrypoint)
    directory_fd = os.open(bin_root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _safe_extract(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:") as bundle:
        members = bundle.getmembers()
        for member in members:
            pure = PurePosixPath(member.name)
            if pure.is_absolute() or ".." in pure.parts or member.issym() or member.islnk() or member.isdev():
                fail("RELEASE_SOURCE", f"unsafe Git archive member: {member.name}", "remove links/devices from release source", 65)
        bundle.extractall(destination, members=members, filter="data")


def _remove_tree(path: Path, parent: Path) -> None:
    if path.parent != parent or path.is_symlink():
        fail("RELEASE_CLEANUP", f"refusing unsafe cleanup target: {path}", "inspect the release root manually", 75)
    if path.exists():
        shutil.rmtree(path)


def _remove_validated_release(path: Path, releases: Path) -> None:
    """Make validated owned directories removable, then delete exactly one release."""
    if path.parent != releases or not COMMIT_RE.fullmatch(path.name):
        fail("RELEASE_CLEANUP", f"refusing unsafe release cleanup target: {path}", "inspect the release root manually", 75)
    directories = [item for item in path.rglob("*") if item.is_dir() and not item.is_symlink()]
    try:
        path.chmod(0o700)
        for directory in directories:
            directory.chmod(0o700)
        shutil.rmtree(path)
    except OSError:
        if path.exists() and not path.is_symlink():
            freeze_tree(path)
        raise


def cleanup_stale_candidates(releases: Path, commit: str) -> None:
    for path in releases.iterdir():
        if path.name.startswith(f".candidate.{commit}."):
            _remove_tree(path, releases)


def relocate_venv(release: Path, final: Path) -> None:
    """Rewrite text launchers whose venv creation path precedes atomic rename."""
    old = str(release).encode()
    new = str(final).encode()
    for path in (release / ".venv" / "bin").iterdir():
        if not path.is_file() or path.is_symlink():
            continue
        payload = path.read_bytes()
        if old in payload:
            path.write_bytes(payload.replace(old, new))
    configuration = release / ".venv" / "pyvenv.cfg"
    payload = configuration.read_bytes()
    if old in payload:
        configuration.write_bytes(payload.replace(old, new))


def tree_size_kib(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file() and not item.is_symlink():
            total += item.stat().st_size
    return (total + 1023) // 1024


def payload_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*"), key=lambda entry: entry.relative_to(path).as_posix()):
        relative = item.relative_to(path).as_posix()
        if relative == "release.record":
            continue
        if item.is_symlink():
            kind = b"link"
            payload = os.readlink(item).encode()
        elif item.is_dir():
            kind = b"directory"
            payload = b""
        elif item.is_file():
            kind = b"file"
            payload = item.read_bytes()
        else:
            fail("RELEASE_PAYLOAD", f"unsupported release filesystem object: {relative}", "rebuild the candidate", 74)
        digest.update(kind + b"\0" + relative.encode() + b"\0" + payload + b"\0")
    return digest.hexdigest()


def freeze_tree(path: Path, *, keep_root_writable: bool = False) -> None:
    for item in sorted(path.rglob("*"), key=lambda entry: len(entry.parts), reverse=True):
        if item.is_symlink():
            continue
        mode = stat.S_IMODE(item.stat().st_mode)
        item.chmod(mode & ~0o222)
    path.chmod(0o755 if keep_root_writable else stat.S_IMODE(path.stat().st_mode) & ~0o222)


def finalize_candidate(release: Path, final: Path) -> None:
    if release.parent.parent != final.parent or final.exists() or final.is_symlink():
        fail("RELEASE_FINALIZE", "candidate and final paths do not form a new same-filesystem release", "inspect candidate containment and destination", 75)
    maybe_interrupt("candidate_finalize", "before")
    freeze_tree(release, keep_root_writable=True)
    maybe_interrupt("candidate_finalize", "during")
    os.replace(release, final)
    final.chmod(0o555)
    directory_fd = os.open(final.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    maybe_interrupt("candidate_finalize", "after")


def _profile_lock(source: Path, profile: str) -> Path:
    names = {
        "dev-py312": "requirements/dev-py312.lock",
        "core-pi-trixie-py313": "requirements/pi-trixie-py313.lock",
    }
    relative = names.get(profile)
    if relative is None:
        fail("RELEASE_PROFILE", f"profile is not a maintained headless release profile: {profile}", "use the platform-selected core profile", 65)
    lock = source / relative
    if not lock.is_file() or lock.is_symlink():
        fail("RELEASE_PROFILE", "recorded source lacks its exact lock", "repair the source commit", 65)
    return lock


def recover_final_permissions(final: Path, commit: str, profile: str) -> None:
    """Close only the rename-to-top-chmod power-loss interval."""
    record = read_record(final / "release.record", RELEASE_FIELDS, "gonken-release-v1")
    if record["commit"] != commit or record["profile"] != profile or final.name != commit:
        fail("RELEASE_INVALID", "partly finalized release identity differs", "inspect and quarantine the release", 75)
    if payload_sha256(final) != record["payload_sha256"]:
        fail("RELEASE_INVALID", "partly finalized release payload differs", "inspect and quarantine the release", 75)
    expected_uid = int(record["owner_uid"])
    for item in final.rglob("*"):
        if item.is_symlink():
            continue
        if item.stat().st_uid != expected_uid or stat.S_IMODE(item.stat().st_mode) & 0o222:
            fail("RELEASE_INVALID", "partly finalized release has mutable or foreign-owned content", "inspect and quarantine the release", 75)
    if final.stat().st_uid != expected_uid:
        fail("RELEASE_INVALID", "partly finalized release owner differs", "inspect and quarantine the release", 75)
    final.chmod(0o555)
    directory_fd = os.open(final.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _build_wheel(source: Path, output: Path) -> tuple[Path, str]:
    try:
        import setuptools
        from setuptools import build_meta
    except ImportError:
        fail("RELEASE_BUILD_BACKEND", "setuptools build backend is unavailable", "install the distribution python3-setuptools bootstrap prerequisite", 69)
    output.mkdir(mode=0o700)
    previous = Path.cwd()
    try:
        os.chdir(source)
        filename = build_meta.build_wheel(str(output))
    except Exception as exc:  # the selected source backend is an execution boundary
        fail("RELEASE_BUILD", f"application wheel build failed: {exc}", "inspect the exact source commit and build prerequisites", 74)
    finally:
        os.chdir(previous)
    wheel = output / filename
    if not wheel.is_file() or wheel.suffix != ".whl" or len(list(output.glob("*.whl"))) != 1:
        fail("RELEASE_BUILD", "build backend did not produce exactly one wheel", "inspect build output before rerunning", 74)
    return wheel, f"setuptools-{setuptools.__version__}"


def smoke_release(release: Path, service_user: str, *, operation: str | None = None) -> tuple[str, str]:
    executable = release / ".venv" / "bin" / "gonken-agent"
    python = release / ".venv" / "bin" / "python"
    if not executable.is_file() or not os.access(executable, os.X_OK):
        fail("RELEASE_SMOKE", f"release virtual environment lacks an executable CLI at {executable}", "rebuild the candidate", 74)
    if not python.exists():
        fail("RELEASE_SMOKE", f"release virtual environment lacks an interpreter at {python}", "rebuild the candidate", 74)
    if operation:
        maybe_interrupt(operation, "before")
    version = run([str(executable), "version"], service_user=service_user).stdout.strip()
    if operation:
        maybe_interrupt(operation, "during")
    status_result = run([str(executable), "status", "--json"], service_user=service_user)
    run([str(python), "-m", "pip", "check"], service_user=service_user)
    try:
        status_payload = json.loads(status_result.stdout)
    except json.JSONDecodeError:
        fail("RELEASE_SMOKE", "installed CLI status is not JSON", "rebuild the candidate", 74)
    if status_payload.get("product") != "GonKenLab Agent" or not version:
        fail("RELEASE_SMOKE", "installed CLI identity/version check failed", "rebuild the candidate", 74)
    if operation:
        maybe_interrupt(operation, "after")
    return version, status_result.stdout


def build_release(
    source_url: str,
    source_ref: str,
    commit: str,
    release_root: Path,
    profile: str,
    service_user: str,
) -> Path:
    require_commit(commit)
    require_profile(profile)
    releases = release_root / "releases"
    ensure_real_directory(releases, 0o755)
    final = releases / commit
    cleanup_stale_candidates(releases, commit)
    if final.exists() or final.is_symlink():
        try:
            validate_release(final, commit=commit, profile=profile, service_user=service_user)
        except ReleaseError as error:
            if error.code != "RELEASE_MUTABLE" or final.is_symlink() or not final.is_dir():
                raise
            recover_final_permissions(final, commit, profile)
            validate_release(final, commit=commit, profile=profile, service_user=service_user)
        print(f"[OK] code=RELEASE_ALREADY_VALID commit={commit}")
        return final
    free_kib = shutil.disk_usage(releases).free // 1024
    if os.environ.get("GONKEN_ENABLE_TEST_FAILURES") == "1" and os.environ.get("GONKEN_RELEASE_TEST_FREE_KIB"):
        free_kib = int(os.environ["GONKEN_RELEASE_TEST_FREE_KIB"])
    previous_sizes = [tree_size_kib(path) for path in releases.iterdir() if COMMIT_RE.fullmatch(path.name) and path.is_dir()]
    required_kib = max(524288, (max(previous_sizes, default=0) * 2) + 262144)
    if free_kib < required_kib:
        fail("RELEASE_SPACE", f"candidate requires {required_kib} KiB headroom; found {free_kib} KiB", "free release storage and rerun", 78)

    workspace = Path(tempfile.mkdtemp(prefix=f".candidate.{commit}.", dir=releases))
    source = workspace / "source"
    release = workspace / "release"
    source.mkdir(mode=0o700)
    release.mkdir(mode=0o700)
    bare = workspace / "source.git"
    archive = workspace / "source.tar"
    try:
        run(["git", "init", "--bare", "--quiet", str(bare)])
        run(["git", f"--git-dir={bare}", "fetch", "--quiet", "--depth=1", "--", source_url, source_ref])
        fetched = run(["git", f"--git-dir={bare}", "rev-parse", "FETCH_HEAD^{commit}"]).stdout.strip().lower()
        if fetched != commit:
            fail("RELEASE_SOURCE_CHANGED", "fetched source no longer matches the recorded commit", "rerun bootstrap and review the new commit", 69)
        submodules = run(["git", f"--git-dir={bare}", "ls-tree", "-r", commit]).stdout
        if any(line.startswith("160000 ") for line in submodules.splitlines()):
            fail("RELEASE_SOURCE", "submodule content is not admitted by the release contract", "vendor or separately verify required content", 65)
        run(["git", f"--git-dir={bare}", "archive", "--format=tar", f"--output={archive}", commit])
        _safe_extract(archive, source)
        lock = _profile_lock(source, profile)
        lock_digest = sha256_file(lock)
        wheel_dir = workspace / "wheels"
        wheel, backend = _build_wheel(source, wheel_dir)
        wheel_digest = sha256_file(wheel)
        venv.EnvBuilder(with_pip=True, symlinks=True).create(release / ".venv")
        venv_python = release / ".venv" / "bin" / "python"
        run([str(venv_python), "-m", "pip", "install", "--no-index", "-r", str(lock)])
        run([str(venv_python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)])
        maintenance = release / "maintenance"
        maintenance.mkdir(mode=0o755)
        maintenance_sources = {
            source / "scripts" / "release_manager.py": maintenance / "release_manager.py",
            source / "scripts" / "reconcile-release.sh": maintenance / "reconcile-release.sh",
            source / "scripts" / "rollback.sh": maintenance / "rollback.sh",
            source / "scripts" / "ollama_manager.py": maintenance / "ollama_manager.py",
            source / "scripts" / "speech_manager.py": maintenance / "speech_manager.py",
            source / "scripts" / "install_summary.py": maintenance / "install_summary.py",
            source / "scripts" / "service_manager.py": maintenance / "service_manager.py",
            source / "packaging" / "ollama-artifacts.toml": maintenance / "packaging" / "ollama-artifacts.toml",
            source / "packaging" / "speech-artifacts.toml": maintenance / "packaging" / "speech-artifacts.toml",
            source / "requirements" / "piper-pi-trixie-py313.lock": maintenance / "requirements" / "piper-pi-trixie-py313.lock",
            source / "packaging" / "systemd" / "ollama.service": maintenance / "packaging" / "systemd" / "ollama.service",
            source / "packaging" / "systemd" / "ollama.service.d" / "gonken-agent.conf": maintenance / "packaging" / "systemd" / "ollama.service.d" / "gonken-agent.conf",
            source / "packaging" / "systemd" / "gonken-agent.service": maintenance / "packaging" / "systemd" / "gonken-agent.service",
            source / "packaging" / "tmpfiles" / "gonken-agent.conf": maintenance / "packaging" / "tmpfiles" / "gonken-agent.conf",
        }
        if any(not item.is_file() for item in maintenance_sources):
            fail("RELEASE_MAINTENANCE", "source commit lacks release, Ollama, speech, or service maintenance inputs", "install a commit implementing M6.2", 65)
        for source_path, destination in maintenance_sources.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
        for executable in (
            maintenance / "release_manager.py",
            maintenance / "reconcile-release.sh",
            maintenance / "rollback.sh",
            maintenance / "ollama_manager.py",
            maintenance / "speech_manager.py",
            maintenance / "install_summary.py",
            maintenance / "service_manager.py",
        ):
            executable.chmod(0o755)
        package_version, _ = smoke_release(
            release,
            "root" if os.geteuid() == 0 else service_user,
        )
        relocate_venv(release, final)
        manager_digest = sha256_file(maintenance / "release_manager.py")
        payload_size = tree_size_kib(release)
        payload_digest = payload_sha256(release)
        record = {
            "format": "gonken-release-v1",
            "commit": commit,
            "profile": profile,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "package_version": package_version,
            "lock_sha256": lock_digest,
            "wheel_sha256": wheel_digest,
            "build_backend": backend,
            "maintenance_sha256": manager_digest,
            "payload_sha256": payload_digest,
            "owner_uid": str(os.geteuid()),
            "payload_size_kib": str(payload_size),
            "built_epoch": str(int(time.time())),
            "validation": "passed",
        }
        (release / "release.record").write_bytes(_safe_record_lines(record))
        (release / "release.record").chmod(0o444)
        finalize_candidate(release, final)
        _remove_tree(workspace, releases)
    except BaseException:
        # Ordinary failures are cleaned. SIGKILL/power loss deliberately leaves
        # the identity-scoped workspace for deterministic cleanup on rerun.
        if workspace.exists() and not workspace.is_symlink():
            _remove_tree(workspace, releases)
        raise
    validate_release(final, commit=commit, profile=profile, service_user=service_user)
    print(f"[OK] code=RELEASE_BUILT commit={commit} size_kib={tree_size_kib(final)} required_headroom_kib={required_kib}")
    return final


def validate_release(
    release: Path,
    *,
    commit: str | None = None,
    profile: str | None = None,
    service_user: str,
    postcheck_operation: str | None = None,
) -> dict[str, str]:
    if not release.is_dir() or release.is_symlink():
        fail("RELEASE_INVALID", f"release is missing or unsafe: {release}", "build a new immutable candidate", 74)
    record = read_record(release / "release.record", RELEASE_FIELDS, "gonken-release-v1")
    if not COMMIT_RE.fullmatch(record["commit"]) or release.name != record["commit"]:
        fail("RELEASE_INVALID", "release path and recorded commit differ", "quarantine the invalid release", 74)
    if commit and record["commit"] != commit:
        fail("RELEASE_INVALID", "release does not match requested commit", "select the intended candidate", 74)
    if profile and record["profile"] != profile:
        fail("RELEASE_INVALID", "release dependency profile differs", "rebuild for the current platform", 74)
    digest_fields = (
        "lock_sha256",
        "wheel_sha256",
        "maintenance_sha256",
        "payload_sha256",
    )
    numeric_fields = ("owner_uid", "payload_size_kib", "built_epoch")
    if (
        record["validation"] != "passed"
        or not PROFILE_RE.fullmatch(record["profile"])
        or any(not SHA256_RE.fullmatch(record[field]) for field in digest_fields)
        or any(not record[field].isdigit() for field in numeric_fields)
        or not record["python_version"]
        or not record["package_version"]
        or not record["build_backend"]
    ):
        fail("RELEASE_INVALID", "release manifest is not validated", "rebuild the candidate", 74)
    manager = release / "maintenance" / "release_manager.py"
    if not manager.is_file() or sha256_file(manager) != record["maintenance_sha256"]:
        fail("RELEASE_INVALID", "release maintenance helper hash differs", "rebuild the candidate", 74)
    if payload_sha256(release) != record["payload_sha256"]:
        fail("RELEASE_INVALID", "release payload digest differs", "quarantine the release and rebuild", 74)
    for item in [release, *release.rglob("*")]:
        if item.is_symlink():
            continue
        if stat.S_IMODE(item.stat().st_mode) & 0o222:
            fail("RELEASE_MUTABLE", f"release contains a writable path: {item}", "restore immutable permissions or rebuild", 74)
        if item.stat().st_uid != int(record["owner_uid"]):
            fail("RELEASE_OWNER", "release ownership differs from its manifest", "restore root ownership or rebuild", 74)
    version, _ = smoke_release(release, service_user, operation=postcheck_operation)
    if version != record["package_version"]:
        fail("RELEASE_INVALID", "CLI version differs from release manifest", "rebuild the candidate", 74)
    return record


def journal_path(state_root: Path) -> Path:
    return state_root / "activation.record"


def read_journal(state_root: Path) -> dict[str, str] | None:
    path = journal_path(state_root)
    if not path.exists() and not path.is_symlink():
        return None
    record = read_record(path, JOURNAL_FIELDS, "gonken-activation-v1")
    if not COMMIT_RE.fullmatch(record["candidate_commit"]):
        fail("ACTIVATION_JOURNAL", "journal candidate commit is invalid", "inspect installed state manually", 75)
    if record["previous_commit"] != "none" and not COMMIT_RE.fullmatch(record["previous_commit"]):
        fail("ACTIVATION_JOURNAL", "journal previous commit is invalid", "inspect installed state manually", 75)
    if record["phase"] not in JOURNAL_PHASES or not record["observed_epoch"].isdigit():
        fail("ACTIVATION_JOURNAL", "journal phase or timestamp is invalid", "inspect installed state manually", 75)
    return record


def write_journal(state_root: Path, candidate: str, previous: str, phase: str, message: str) -> None:
    if phase not in JOURNAL_PHASES:
        fail("ACTIVATION_JOURNAL", "unsupported activation phase", "use the defined phase protocol", 64)
    durable_record(
        journal_path(state_root),
        {
            "format": "gonken-activation-v1",
            "candidate_commit": candidate,
            "previous_commit": previous,
            "phase": phase,
            "observed_epoch": str(int(time.time())),
            "message": message,
        },
        "journal_replace",
    )


def current_commit(release_root: Path) -> str | None:
    current = release_root / "current"
    if not current.exists() and not current.is_symlink():
        return None
    if not current.is_symlink():
        fail("ACTIVATION_POINTER", "current is not a symbolic link", "inspect the root-owned release pointer", 75)
    target = os.readlink(current)
    match = re.fullmatch(r"releases/([0-9a-f]{40})", target)
    if not match:
        fail("ACTIVATION_POINTER", "current target is outside the release namespace", "inspect the root-owned pointer manually", 75)
    return match.group(1)


def switch_current(release_root: Path, commit: str) -> None:
    require_commit(commit)
    current = release_root / "current"
    if current.exists() and not current.is_symlink():
        fail("ACTIVATION_POINTER", "current is not a symbolic link", "move the conflicting file after inspection", 75)
    maybe_interrupt("current_switch", "before")
    for stale in release_root.glob(".current.*"):
        if stale.is_symlink():
            stale.unlink()
        elif stale.exists():
            fail("ACTIVATION_POINTER", "stale current-pointer temporary is not a symlink", "inspect the release root manually", 75)
    temporary = release_root / f".current.{os.getpid()}"
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    temporary.symlink_to(f"releases/{commit}")
    maybe_interrupt("current_switch", "during")
    os.replace(temporary, current)
    directory_fd = os.open(release_root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    maybe_interrupt("current_switch", "after")


def remove_current(release_root: Path) -> None:
    current = release_root / "current"
    if current.is_symlink():
        current.unlink()
        directory_fd = os.open(release_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)


def rollback(release_root: Path, state_root: Path, candidate: str, previous: str, service_user: str, message: str) -> None:
    if previous == "none":
        remove_current(release_root)
    else:
        validate_release(release_root / "releases" / previous, commit=previous, service_user=service_user)
        switch_current(release_root, previous)
    write_journal(state_root, candidate, previous, "rolled_back", message)


def reconcile(release_root: Path, state_root: Path, service_user: str) -> str:
    journal = read_journal(state_root)
    pointer = current_commit(release_root)
    if journal is None:
        if pointer is None:
            print("[OK] code=ACTIVATION_EMPTY")
            return "empty"
        fail("ACTIVATION_AMBIGUOUS", "current exists without an activation journal", "inspect the root-owned release state manually", 75)
    candidate = journal["candidate_commit"]
    previous = journal["previous_commit"]
    phase = journal["phase"]
    candidate_path = release_root / "releases" / candidate
    expected_previous = None if previous == "none" else previous

    if phase == "post_verified":
        if pointer != candidate:
            fail("ACTIVATION_AMBIGUOUS", "post-verified journal and current pointer disagree", "inspect installed state manually", 75)
        validate_release(candidate_path, commit=candidate, service_user=service_user)
        print(f"[OK] code=ACTIVATION_RECONCILED phase=post_verified commit={candidate}")
        return "post_verified"
    if phase == "rolled_back":
        if pointer != expected_previous:
            fail("ACTIVATION_AMBIGUOUS", "rolled-back journal and current pointer disagree", "inspect installed state manually", 75)
        if previous != "none":
            validate_release(release_root / "releases" / previous, commit=previous, service_user=service_user)
        print(f"[OK] code=ACTIVATION_RECONCILED phase=rolled_back commit={previous}")
        return "rolled_back"

    if phase == "prepared":
        if pointer not in {expected_previous, candidate}:
            fail("ACTIVATION_AMBIGUOUS", "prepared journal and current pointer disagree", "inspect installed state manually", 75)
        try:
            validate_release(candidate_path, commit=candidate, service_user=service_user)
        except ReleaseError:
            rollback(release_root, state_root, candidate, previous, service_user, "candidate_invalid_during_reconcile")
            print(f"[OK] code=ACTIVATION_ROLLED_BACK commit={previous}")
            return "rolled_back"
        if pointer != candidate:
            switch_current(release_root, candidate)
        write_journal(state_root, candidate, previous, "switched", "reconciled_switch")
        pointer = candidate

    if pointer != candidate:
        fail("ACTIVATION_AMBIGUOUS", "switched journal and current pointer disagree", "inspect installed state manually", 75)
    try:
        validate_release(candidate_path, commit=candidate, service_user=service_user, postcheck_operation="post_switch_validation")
    except ReleaseError:
        rollback(release_root, state_root, candidate, previous, service_user, "post_switch_validation_failed")
        print(f"[OK] code=ACTIVATION_ROLLED_BACK commit={previous}")
        return "rolled_back"
    write_journal(state_root, candidate, previous, "post_verified", "candidate_validated_after_switch")
    print(f"[OK] code=ACTIVATION_RECONCILED phase=post_verified commit={candidate}")
    return "post_verified"


def activate(release_root: Path, state_root: Path, commit: str, service_user: str) -> None:
    reconcile(release_root, state_root, service_user)
    validate_release(release_root / "releases" / commit, commit=commit, service_user=service_user)
    previous = current_commit(release_root) or "none"
    if previous == commit:
        journal = read_journal(state_root)
        if journal and journal["phase"] == "post_verified" and journal["candidate_commit"] == commit:
            print(f"[OK] code=ACTIVATION_ALREADY_VALID commit={commit}")
            return
    write_journal(state_root, commit, previous, "prepared", "candidate_validated_before_switch")
    switch_current(release_root, commit)
    write_journal(state_root, commit, previous, "switched", "current_pointer_replaced")
    try:
        validate_release(
            release_root / "releases" / commit,
            commit=commit,
            service_user=service_user,
            postcheck_operation="post_switch_validation",
        )
    except ReleaseError:
        rollback(release_root, state_root, commit, previous, service_user, "post_switch_validation_failed")
        raise
    write_journal(state_root, commit, previous, "post_verified", "candidate_validated_after_switch")
    print(f"[OK] code=ACTIVATION_COMPLETE commit={commit} previous={previous}")


def prune_releases(release_root: Path, state_root: Path, service_user: str) -> None:
    journal = read_journal(state_root)
    if not journal or journal["phase"] != "post_verified":
        return
    keep = {journal["candidate_commit"]}
    if journal["previous_commit"] != "none":
        keep.add(journal["previous_commit"])
    releases = release_root / "releases"
    for path in releases.iterdir():
        if COMMIT_RE.fullmatch(path.name) and path.name not in keep:
            validate_release(path, commit=path.name, service_user=service_user)
            _remove_validated_release(path, releases)


def status(release_root: Path, state_root: Path, expected: str | None, service_user: str) -> None:
    journal = read_journal(state_root)
    pointer = current_commit(release_root)
    if not journal or journal["phase"] != "post_verified" or pointer != journal["candidate_commit"]:
        fail("ACTIVATION_INCOMPLETE", "release activation is not post-verified", "run reconciliation and inspect failures", 1)
    if expected and pointer != expected:
        fail("ACTIVATION_WRONG_RELEASE", "active release differs from the requested commit", "activate the verified candidate", 1)
    validate_release(release_root / "releases" / pointer, commit=pointer, service_user=service_user)
    print(f"[OK] code=ACTIVATION_HEALTHY commit={pointer}")


def rollback_previous(release_root: Path, state_root: Path, service_user: str) -> None:
    reconcile(release_root, state_root, service_user)
    journal = read_journal(state_root)
    pointer = current_commit(release_root)
    if not journal or journal["phase"] != "post_verified" or pointer != journal["candidate_commit"]:
        fail("ROLLBACK_STATE", "active release is not a post-verified rollback source", "repair activation state before rollback", 75)
    previous = journal["previous_commit"]
    if previous == "none":
        fail("ROLLBACK_UNAVAILABLE", "no previous validated release is recorded", "install at least two validated releases before rollback", 1)
    activate(release_root, state_root, previous, service_user)
    print(f"[OK] code=ROLLBACK_COMPLETE commit={previous}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)

    layout = commands.add_parser("init-layout")
    layout.add_argument("--release-root", required=True)
    layout.add_argument("--state-root", required=True)
    layout.add_argument("--bin-root", required=True)

    build = commands.add_parser("build")
    build.add_argument("--source-url", required=True)
    build.add_argument("--source-ref", required=True)
    build.add_argument("--commit", required=True)
    build.add_argument("--release-root", required=True)
    build.add_argument("--profile", required=True)
    build.add_argument("--service-user", required=True)

    for name in ("activate", "reconcile", "status", "rollback-previous"):
        command = commands.add_parser(name)
        command.add_argument("--release-root", required=True)
        command.add_argument("--state-root", required=True)
        command.add_argument("--service-user", required=True)
        if name == "activate":
            command.add_argument("--commit", required=True)
        elif name == "status":
            command.add_argument("--expect-commit")

    validate = commands.add_parser("validate")
    validate.add_argument("--release", required=True)
    validate.add_argument("--commit")
    validate.add_argument("--profile")
    validate.add_argument("--service-user", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init-layout":
            init_layout(
                require_absolute(args.release_root, "release root"),
                require_absolute(args.state_root, "install-state root"),
                require_absolute(args.bin_root, "binary root"),
            )
        elif args.command == "build":
            build_release(
                args.source_url,
                args.source_ref,
                require_commit(args.commit),
                require_absolute(args.release_root, "release root"),
                require_profile(args.profile),
                args.service_user,
            )
        elif args.command == "validate":
            validate_release(
                require_absolute(args.release, "release"),
                commit=require_commit(args.commit) if args.commit else None,
                profile=require_profile(args.profile) if args.profile else None,
                service_user=args.service_user,
            )
            print("[OK] code=RELEASE_VALID")
        elif args.command == "activate":
            release_root = require_absolute(args.release_root, "release root")
            state_root = require_absolute(args.state_root, "install-state root")
            with maintenance_lock(state_root):
                activate(release_root, state_root, require_commit(args.commit), args.service_user)
                prune_releases(release_root, state_root, args.service_user)
        elif args.command == "reconcile":
            state_root = require_absolute(args.state_root, "install-state root")
            with maintenance_lock(state_root):
                reconcile(
                    require_absolute(args.release_root, "release root"),
                    state_root,
                    args.service_user,
                )
        elif args.command == "rollback-previous":
            state_root = require_absolute(args.state_root, "install-state root")
            with maintenance_lock(state_root):
                rollback_previous(
                    require_absolute(args.release_root, "release root"),
                    state_root,
                    args.service_user,
                )
        else:
            state_root = require_absolute(args.state_root, "install-state root")
            with maintenance_lock(state_root):
                status(
                    require_absolute(args.release_root, "release root"),
                    state_root,
                    require_commit(args.expect_commit) if args.expect_commit else None,
                    args.service_user,
                )
    except ReleaseError as error:
        emit_error(error)
        return error.exit_code
    except (OSError, ValueError) as error:
        emit_error(ReleaseError("RELEASE_IO", str(error), "inspect filesystem ownership, space, and installed state", 73))
        return 73
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
