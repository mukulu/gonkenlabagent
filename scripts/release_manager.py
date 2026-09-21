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
TARGET_DISTRO_BINDING_PROFILES = {"core-pi-trixie-py313"}
DIST_PACKAGES_ROOT = Path("/usr/lib/python3/dist-packages")
TARGET_BINDING_PACKAGES = {
    "core-pi-trixie-py313": ("python3-libgpiod",),
}
BINDING_MANIFEST_RELATIVE = Path("share/gonken-agent/hardware-bindings.json")
PAYLOAD_MANIFEST_RELATIVE = Path("share/gonken-agent/release-payload-manifest.json")
HARDWARE_BINDING_CHECK = """
import gpiod
from gpiod.line import Bias, Direction, Value
required = {
    "gpiod.Chip": getattr(gpiod, "Chip", None),
    "gpiod.LineSettings": getattr(gpiod, "LineSettings", None),
    "gpiod.request_lines": getattr(gpiod, "request_lines", None),
}
missing = [name for name, value in required.items() if not callable(value)]
for name in ("get_info", "get_line_info"):
    if not callable(getattr(gpiod.Chip, name, None)):
        missing.append("gpiod.Chip." + name)
if missing:
    raise SystemExit("missing hardware API: " + ",".join(missing))
# Importing these enum types proves the libgpiod v2 line API used by the runtime.
assert Bias is not None and Direction is not None and Value is not None
print("hardware_bindings=ready")
"""


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
    # The interruption hook is test-only.  Do not kill the parent shell by
    # default: doing so can orphan this Python process with inherited pipes in
    # subprocess-based integration tests, which makes broad CI appear hung after
    # the intended interruption.  The default exits abruptly with the same
    # shell-visible signal-style code while preserving deterministic cleanup of
    # the subprocess boundary.  Parent termination remains opt-in for narrow
    # manual experiments that need to simulate wrapper loss.
    if os.environ.get("GONKEN_RELEASE_TEST_INTERRUPT_PARENT") == "1":
        os.kill(os.getppid(), chosen)
        os.kill(os.getpid(), chosen)
    os._exit(128 + chosen.value)



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
    ensure_real_directory(state_root.parent, 0o755)
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


def _payload_items(path: Path) -> list[Path]:
    return sorted(path.rglob("*"), key=lambda entry: entry.relative_to(path).as_posix())


def _is_runtime_cache_artifact(path: Path, release: Path) -> bool:
    """Return whether ``path`` is a standard derived Python cache artifact.

    The immutable authority boundary covers source/config/manifests/native
    bindings and all other release payload.  A *real directory* named
    ``__pycache__`` plus only ``.pyc/.pyo`` files immediately below/within it
    are interpreter-derived runtime cache and are not authoritative.

    A symlink named ``__pycache__`` is never trusted as cache.  Top-level
    sourceless bytecode and non-bytecode files hidden inside a cache directory
    remain authoritative/unexpected and therefore fail validation.
    """
    try:
        relative = path.relative_to(release)
    except ValueError:
        return False
    parts = relative.parts
    try:
        index = parts.index("__pycache__")
    except ValueError:
        return False
    cache_root = release.joinpath(*parts[: index + 1])
    try:
        if cache_root.is_symlink() or not cache_root.is_dir():
            return False
    except OSError:
        return False
    if path == cache_root:
        return True
    if path.is_symlink() or not path.is_file():
        return False
    return path.suffix in {".pyc", ".pyo"}


def _authoritative_payload_items(path: Path) -> list[Path]:
    return [item for item in _payload_items(path) if not _is_runtime_cache_artifact(item, path)]


def _payload_entry(path: Path, item: Path) -> tuple[str, str, str]:
    relative = item.relative_to(path).as_posix()
    if item.is_symlink():
        return relative, "link", hashlib.sha256(os.readlink(item).encode()).hexdigest()
    if item.is_dir():
        return relative, "directory", hashlib.sha256(b"").hexdigest()
    if item.is_file():
        return relative, "file", sha256_file(item)
    fail("RELEASE_PAYLOAD", f"unsupported release filesystem object: {relative}", "rebuild the candidate", 74)
    raise AssertionError("unreachable")


def payload_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for item in _authoritative_payload_items(path):
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


def purge_release_transients(path: Path) -> None:
    """Remove interpreter/build caches before the immutable payload is sealed."""
    for item in sorted(path.rglob("*"), key=lambda entry: len(entry.parts), reverse=True):
        if item.is_symlink():
            continue
        if item.is_file() and item.suffix in {".pyc", ".pyo"}:
            item.unlink()
        elif item.is_dir() and item.name in {"__pycache__", ".pytest_cache"}:
            shutil.rmtree(item)


def make_candidate_service_readable(workspace: Path, release: Path) -> None:
    """Allow the target service account to smoke-test the candidate before sealing."""
    workspace.chmod(0o711)
    for item in [release, *_payload_items(release)]:
        if item.is_symlink():
            continue
        mode = stat.S_IMODE(item.stat().st_mode)
        if item.is_dir():
            item.chmod(0o755)
        elif item.is_file():
            item.chmod(0o755 if mode & 0o111 else 0o644)


def write_payload_manifest(path: Path) -> None:
    entries: list[dict[str, str]] = []
    excluded = {"release.record", PAYLOAD_MANIFEST_RELATIVE.as_posix()}
    for item in _authoritative_payload_items(path):
        relative = item.relative_to(path).as_posix()
        if relative in excluded:
            continue
        rel, kind, digest = _payload_entry(path, item)
        entries.append({"path": rel, "kind": kind, "sha256": digest})
    destination = path / PAYLOAD_MANIFEST_RELATIVE
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    destination.write_text(
        json.dumps({"format": "gonken-release-payload-v1", "entries": entries}, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def payload_manifest_differences(path: Path, limit: int | None = 8) -> list[str]:
    manifest = path / PAYLOAD_MANIFEST_RELATIVE
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        expected_rows = payload.get("entries")
        if payload.get("format") != "gonken-release-payload-v1" or not isinstance(expected_rows, list):
            return ["manifest:invalid"]
        expected: dict[str, tuple[str, str]] = {}
        for row in expected_rows:
            if not isinstance(row, dict) or not all(isinstance(row.get(key), str) for key in ("path", "kind", "sha256")):
                return ["manifest:invalid"]
            expected[row["path"]] = (row["kind"], row["sha256"])
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ["manifest:unreadable"]
    actual: dict[str, tuple[str, str]] = {}
    excluded = {"release.record", PAYLOAD_MANIFEST_RELATIVE.as_posix()}
    for item in _authoritative_payload_items(path):
        relative = item.relative_to(path).as_posix()
        if relative in excluded:
            continue
        rel, kind, digest = _payload_entry(path, item)
        actual[rel] = (kind, digest)
    differences: list[str] = []
    for name in sorted(set(expected) | set(actual)):
        if name not in expected:
            differences.append(f"unexpected:{name}")
        elif name not in actual:
            differences.append(f"missing:{name}")
        elif expected[name] != actual[name]:
            differences.append(f"changed:{name}")
        if limit is not None and len(differences) >= limit:
            break
    return differences


def freeze_tree(path: Path, *, keep_root_writable: bool = False) -> None:
    """Freeze a code release while keeping it readable/traversable by service users.

    The final modes are explicit rather than inherited from the caller's umask.
    This prevents root-built virtual environments from becoming inaccessible to
    the unprivileged runtime account.
    """
    for item in sorted(path.rglob("*"), key=lambda entry: len(entry.parts), reverse=True):
        if item.is_symlink():
            continue
        mode = stat.S_IMODE(item.stat().st_mode)
        if item.is_dir():
            item.chmod(0o555)
        elif item.is_file():
            item.chmod(0o555 if mode & 0o111 else 0o444)
        else:
            fail("RELEASE_PAYLOAD", f"unsupported release filesystem object: {item}", "rebuild the candidate", 74)
    path.chmod(0o755 if keep_root_writable else 0o555)


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


def profile_uses_distro_bindings(profile: str) -> bool:
    """Return whether a release profile consumes an allow-listed distro binding bridge."""
    return profile in TARGET_DISTRO_BINDING_PROFILES


def _venv_system_site_packages_enabled(release: Path) -> bool:
    configuration = release / ".venv" / "pyvenv.cfg"
    if not configuration.is_file() or configuration.is_symlink():
        return False
    try:
        lines = configuration.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return False
    values = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip().casefold()] = value.strip().casefold()
    return values.get("include-system-site-packages") == "true"


def _binding_relative_allowed(package: str, relative: Path) -> bool:
    """Allow only import payloads, never unrelated distro metadata/site packages."""
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        return False
    if package == "python3-libgpiod":
        return relative.parts[0] == "gpiod"
    return False


def _venv_site_packages(release: Path) -> Path:
    return release / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"


def _distro_package_version(package: str) -> str:
    result = run(["dpkg-query", "-W", "-f=${db:Status-Abbrev}\t${Version}", package])
    fields = result.stdout.strip().split("\t", 1)
    if len(fields) != 2 or not fields[0].startswith("ii") or not re.fullmatch(r"[A-Za-z0-9.+:~_-]{1,128}", fields[1]):
        fail("RELEASE_BINDING_PACKAGE", f"required distro binding package is not installed: {package}", "repair target prerequisites and rebuild the release", 74)
    return fields[1]


def _distro_binding_files(package: str, *, source_root: Path = DIST_PACKAGES_ROOT) -> list[Path]:
    result = run(["dpkg-query", "-L", package])
    files: list[Path] = []
    for line in result.stdout.splitlines():
        candidate = Path(line.strip())
        if not candidate.is_absolute():
            continue
        try:
            relative = candidate.relative_to(source_root)
        except ValueError:
            continue
        if not _binding_relative_allowed(package, relative):
            continue
        if candidate.is_symlink():
            fail("RELEASE_BINDING_SOURCE", f"distro binding source must not be a symlink: {candidate}", "repair the distro package installation", 74)
        if candidate.is_file():
            files.append(candidate)
    if not files:
        fail("RELEASE_BINDING_SOURCE", f"no allow-listed import files found for {package}", "reinstall the required distro binding package", 74)
    return sorted(set(files))


def install_target_distro_bindings(
    release: Path,
    profile: str,
    *,
    source_root: Path = DIST_PACKAGES_ROOT,
) -> dict[str, object] | None:
    """Copy only approved distro binding import payloads into an isolated venv."""
    if not profile_uses_distro_bindings(profile):
        return None
    if _venv_system_site_packages_enabled(release):
        fail(
            "RELEASE_VENV_POLICY",
            "target release venv unexpectedly exposes all system site-packages",
            "rebuild the release with an isolated venv and the allow-listed binding bridge",
            74,
        )
    site_packages = _venv_site_packages(release)
    if not site_packages.is_dir() or site_packages.is_symlink():
        fail("RELEASE_BINDING_DESTINATION", "release venv site-packages directory is missing or unsafe", "rebuild the immutable release", 74)
    records: list[dict[str, object]] = []
    for package in TARGET_BINDING_PACKAGES.get(profile, ()):
        version = _distro_package_version(package)
        copied = []
        for source in _distro_binding_files(package, source_root=source_root):
            relative = source.relative_to(source_root)
            destination = site_packages / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)
            copied.append({"path": relative.as_posix(), "sha256": sha256_file(destination)})
        records.append({"package": package, "version": version, "files": copied})
    manifest = {
        "format": "gonken-hardware-binding-bridge-v1",
        "profile": profile,
        "source_root": str(source_root),
        "system_site_packages": False,
        "packages": records,
    }
    path = release / BINDING_MANIFEST_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o444)
    return manifest


def _binding_manifest_valid(release: Path, profile: str) -> bool:
    path = release / BINDING_MANIFEST_RELATIVE
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            return False
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if payload.get("format") != "gonken-hardware-binding-bridge-v1" or payload.get("profile") != profile:
        return False
    if payload.get("system_site_packages") is not False:
        return False
    packages = payload.get("packages")
    if not isinstance(packages, list) or {item.get("package") for item in packages if isinstance(item, dict)} != set(TARGET_BINDING_PACKAGES.get(profile, ())):
        return False
    site_packages = _venv_site_packages(release)
    for item in packages:
        if not isinstance(item, dict) or not isinstance(item.get("version"), str):
            return False
        files = item.get("files")
        if not isinstance(files, list) or not files:
            return False
        for entry in files:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not isinstance(entry.get("sha256"), str):
                return False
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts or not _binding_relative_allowed(item["package"], relative):
                return False
            destination = site_packages / relative
            if not destination.is_file() or destination.is_symlink() or sha256_file(destination) != entry["sha256"]:
                return False
    return True


def _release_embedded_manager_uses_binding_bridge(release: Path) -> bool:
    """Return whether this immutable release was built under the bridge-era contract.

    The release manager itself is part of the immutable payload and its digest is
    validated from ``release.record`` before this helper is consulted.  Older
    post-verified releases predate the hardware-binding manifest entirely; a new
    manager must be able to transition away from those releases without applying
    today's candidate-only contract retroactively.  Conversely, a bridge-era
    release that loses or corrupts its manifest must never be reclassified as
    legacy merely because the manifest is absent.
    """
    manager = release / "maintenance" / "release_manager.py"
    try:
        if manager.is_symlink() or not manager.is_file() or manager.stat().st_size > 2 * 1024 * 1024:
            return True
        text = manager.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return True
    return (
        "gonken-hardware-binding-bridge-v1" in text
        and "hardware-bindings.json" in text
        and "install_target_distro_bindings" in text
    )


def _legacy_transition_runtime_allowed(release: Path, profile: str) -> bool:
    """Identify a genuine pre-bridge target release for state-bound transition use.

    This is intentionally narrower than general validation.  It is only useful
    when the caller has already established that the release is referenced by a
    trusted activation journal/current-pointer relationship.  A bridge-era
    release with a missing/corrupt manifest remains invalid and cannot use this
    path.
    """
    if not profile_uses_distro_bindings(profile):
        return False
    manifest = release / BINDING_MANIFEST_RELATIVE
    if manifest.exists() or manifest.is_symlink():
        return False
    return not _release_embedded_manager_uses_binding_bridge(release)


def validate_runtime_hardware_bindings(
    release: Path,
    profile: str,
    service_user: str,
) -> None:
    """Fail closed when the target release interpreter cannot use bridged hardware APIs."""
    if not profile_uses_distro_bindings(profile):
        return
    if _venv_system_site_packages_enabled(release):
        fail(
            "RELEASE_VENV_POLICY",
            f"target release venv exposes broad system site-packages: {release.name}",
            "rebuild with the allow-listed distro binding bridge",
            74,
        )
    if not _binding_manifest_valid(release, profile):
        fail(
            "RELEASE_BINDING_MANIFEST",
            f"target release hardware-binding bridge is missing or invalid: {release.name}",
            "rebuild the target release from validated distro binding packages",
            74,
        )
    python = release / ".venv" / "bin" / "python"
    try:
        run([str(python), "-c", HARDWARE_BINDING_CHECK], service_user=service_user)
    except ReleaseError as error:
        fail(
            "RELEASE_HARDWARE_BINDINGS",
            f"target release interpreter cannot use required gpiod APIs: {error}",
            "repair the validated distro binding packages and rebuild the immutable release",
            error.exit_code,
        )


def smoke_release(
    release: Path,
    service_user: str,
    *,
    profile: str,
    operation: str | None = None,
) -> tuple[str, str]:
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
    validate_runtime_hardware_bindings(release, profile, service_user)
    try:
        status_payload = json.loads(status_result.stdout)
    except json.JSONDecodeError:
        fail("RELEASE_SMOKE", "installed CLI status is not JSON", "rebuild the candidate", 74)
    if status_payload.get("product") != "GonKenLab Agent" or not version:
        fail("RELEASE_SMOKE", "installed CLI identity/version check failed", "rebuild the candidate", 74)
    if operation:
        maybe_interrupt(operation, "after")
    return version, status_result.stdout


def smoke_legacy_transition_source(
    release: Path,
    service_user: str,
    *,
    profile: str,
) -> tuple[str, str]:
    """Perform the bounded smoke allowed for a previously post-verified legacy release.

    Legacy target releases may have been created before the allow-listed binding
    manifest existed, or under the short-lived system-site-packages contract.
    Re-evaluating those releases with the *new* pip/binding policy can prevent a
    safe upgrade away from them.  For a state-bound transition source we instead
    preserve the immutable payload/ownership checks in ``validate_release`` and
    require the installed CLI to execute as the service user and return a valid
    identity/status payload.  This path is never used for a newly built candidate.
    """
    if not _legacy_transition_runtime_allowed(release, profile):
        fail(
            "RELEASE_BINDING_MANIFEST",
            f"target release hardware-binding bridge is missing or invalid: {release.name}",
            "rebuild the target release from validated distro binding packages",
            74,
        )
    executable = release / ".venv" / "bin" / "gonken-agent"
    if not executable.is_file() or not os.access(executable, os.X_OK):
        fail(
            "RELEASE_SMOKE",
            f"legacy transition source lacks an executable CLI at {executable}",
            "inspect the previously active immutable release before retrying the upgrade",
            74,
        )
    version = run([str(executable), "version"], service_user=service_user).stdout.strip()
    status_result = run([str(executable), "status", "--json"], service_user=service_user)
    try:
        status_payload = json.loads(status_result.stdout)
    except json.JSONDecodeError:
        fail(
            "RELEASE_SMOKE",
            "legacy transition source status is not JSON",
            "inspect the previously active immutable release before retrying the upgrade",
            74,
        )
    if status_payload.get("product") != "GonKenLab Agent" or not version:
        fail(
            "RELEASE_SMOKE",
            "legacy transition source identity/version check failed",
            "inspect the previously active immutable release before retrying the upgrade",
            74,
        )
    print(
        f"[OK] code=RELEASE_LEGACY_TRANSITION_SOURCE commit={release.name} "
        f"profile={profile} runtime_policy=bounded_cli_smoke"
    )
    return version, status_result.stdout


def smoke_installed_maintenance(release: Path) -> None:
    """Catch checkout-only imports before activation using actual installed paths.

    --help parses nothing and performs no device/service/network operation.
    A clean cwd/environment prevents source PYTHONPATH from hiding a missing
    sealed dependency (the B9 target failure). Each process is time bounded.
    """
    tools = ("ollama_manager.py", "model_roster_manager.py",
             "ollama_qualification_matrix.py", "appliance_manager.py",
             "install_summary.py", "environment_service_manager.py",
             "environment_profile_manager.py", "environment_readiness.py")
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
                   "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}
    for name in tools:
        try:
            result = subprocess.run(
                [sys.executable, "-s", str(release / "maintenance" / name), "--help"],
                cwd=release, env=environment, capture_output=True, text=True, timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            fail("RELEASE_MAINTENANCE_IMPORT", f"{name}: {type(exc).__name__}",
                 "repair the candidate maintenance dependency closure before activation", 74)
        if result.returncode != 0 or "usage:" not in result.stdout:
            fail("RELEASE_MAINTENANCE_IMPORT", f"{name}: exit={result.returncode}",
                 "repair the candidate maintenance dependency closure before activation", 74)


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
            validate_release_static(final, commit=commit, profile=profile)
        except ReleaseError as error:
            if error.code == "RELEASE_MUTABLE" and not final.is_symlink() and final.is_dir():
                recover_final_permissions(final, commit, profile)
                validate_release_static(final, commit=commit, profile=profile)
                print(f"[OK] code=RELEASE_ALREADY_VALID commit={commit}")
                return final
            current = current_commit(release_root)
            if current == commit:
                fail(
                    "RELEASE_ACTIVE_INVALID",
                    f"active release for the requested commit is invalid: {error.code}",
                    "install a newer checkpoint; authoritative active-release changes are never repaired in place",
                    74,
                )
            if final.is_symlink() or not final.is_dir():
                raise
            print(
                f"[WARN] code=RELEASE_INVALID_REBUILD commit={commit} reason={error.code} "
                "remediation=rebuild_noncurrent_release_from_current_source",
                file=sys.stderr,
            )
            _remove_tree(final, releases)
        else:
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
        venv.EnvBuilder(
            with_pip=True,
            symlinks=True,
            system_site_packages=False,
        ).create(release / ".venv")
        venv_python = release / ".venv" / "bin" / "python"
        run([str(venv_python), "-m", "pip", "install", "--no-index", "-r", str(lock)])
        run([str(venv_python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)])
        install_target_distro_bindings(release, profile)
        share = release / "share" / "gonken-agent"
        share.mkdir(parents=True, exist_ok=True, mode=0o755)
        local_prompt = source / "config" / "local_soul.md"
        if not local_prompt.is_file() or local_prompt.is_symlink():
            fail("RELEASE_PROMPT", "source commit lacks the local voice prompt", "restore config/local_soul.md", 65)
        shutil.copy2(local_prompt, share / "local_soul.md")
        (share / "local_soul.md").chmod(0o444)
        maintenance = release / "maintenance"
        maintenance.mkdir(mode=0o755)
        maintenance_sources = {
            source / "scripts" / "release_manager.py": maintenance / "release_manager.py",
            source / "scripts" / "reconcile-release.sh": maintenance / "reconcile-release.sh",
            source / "scripts" / "update.sh": maintenance / "update.sh",
            source / "scripts" / "collect-support.sh": maintenance / "collect-support.sh",
            source / "scripts" / "rollback.sh": maintenance / "rollback.sh",
            source / "scripts" / "uninstall.sh": maintenance / "uninstall.sh",
            source / "scripts" / "ollama_manager.py": maintenance / "ollama_manager.py",
            source / "scripts" / "model_roster_manager.py": maintenance / "model_roster_manager.py",
            source / "scripts" / "ollama_qualification_matrix.py": maintenance / "ollama_qualification_matrix.py",
            source / "scripts" / "speech_manager.py": maintenance / "speech_manager.py",
            source / "scripts" / "install_summary.py": maintenance / "install_summary.py",
            source / "scripts" / "service_manager.py": maintenance / "service_manager.py",
            source / "scripts" / "environment_service_manager.py": maintenance / "environment_service_manager.py",
            source / "scripts" / "environment_acceptance_runner.py": maintenance / "environment_acceptance_runner.py",
            source / "scripts" / "environment_profile_manager.py": maintenance / "environment_profile_manager.py",
            source / "scripts" / "environment_readiness.py": maintenance / "environment_readiness.py",
            source / "scripts" / "archive_qualifier.py": maintenance / "archive_qualifier.py",
            source / "scripts" / "target_probe.py": maintenance / "target_probe.py",
            source / "scripts" / "target_preflight.py": maintenance / "target_preflight.py",
            source / "scripts" / "i2c_manager.py": maintenance / "i2c_manager.py",
            source / "scripts" / "gpio_identity_preflight.py": maintenance / "gpio_identity_preflight.py",
            source / "scripts" / "sht31_diagnostic.py": maintenance / "sht31_diagnostic.py",
            source / "scripts" / "runtime_context_preflight.py": maintenance / "runtime_context_preflight.py",
            source / "scripts" / "installer_failure_bundle.py": maintenance / "installer_failure_bundle.py",
            source / "src" / "gonken_agent" / "evidence.py": maintenance / "evidence.py",
            source / "src" / "gonken_agent" / "runtime_readiness.py": maintenance / "runtime_readiness.py",
            source / "src" / "gonken_agent" / "llm" / "qualification.py": maintenance / "model_qualification.py",
            source / "src" / "gonken_agent" / "llm" / "errors.py": maintenance / "ollama_errors.py",
            source / "src" / "gonken_agent" / "llm" / "models.py": maintenance / "model_catalog.py",
            source / "scripts" / "bluetooth_manager.py": maintenance / "bluetooth_manager.py",
            source / "scripts" / "appliance_manager.py": maintenance / "appliance_manager.py",
            source / "scripts" / "update_manager.py": maintenance / "update_manager.py",
            source / "scripts" / "uninstall_manager.py": maintenance / "uninstall_manager.py",
            source / "packaging" / "ollama-artifacts.toml": maintenance / "packaging" / "ollama-artifacts.toml",
            source / "packaging" / "ollama-model-roster.toml": maintenance / "packaging" / "ollama-model-roster.toml",
            source / "packaging" / "speech-artifacts.toml": maintenance / "packaging" / "speech-artifacts.toml",
            source / "requirements" / "piper-pi-trixie-py313.lock": maintenance / "requirements" / "piper-pi-trixie-py313.lock",
            source / "packaging" / "systemd" / "ollama.service": maintenance / "packaging" / "systemd" / "ollama.service",
            source / "packaging" / "systemd" / "ollama.service.d" / "gonken-agent.conf": maintenance / "packaging" / "systemd" / "ollama.service.d" / "gonken-agent.conf",
            source / "packaging" / "systemd" / "gonken-agent.service": maintenance / "packaging" / "systemd" / "gonken-agent.service",
            source / "packaging" / "systemd" / "gonken-environment.service": maintenance / "packaging" / "systemd" / "gonken-environment.service",
            source / "packaging" / "systemd" / "gonken-bluetooth-autoconnect.service": maintenance / "packaging" / "systemd" / "gonken-bluetooth-autoconnect.service",
            source / "packaging" / "tmpfiles" / "gonken-agent.conf": maintenance / "packaging" / "tmpfiles" / "gonken-agent.conf",
            source / "packaging" / "tmpfiles" / "gonken-environment.conf": maintenance / "packaging" / "tmpfiles" / "gonken-environment.conf",
        }
        if any(not item.is_file() for item in maintenance_sources):
            fail("RELEASE_MAINTENANCE", "source commit lacks release, Ollama, speech, service, or environment-service maintenance inputs", "install a commit implementing M6.2", 65)
        for source_path, destination in maintenance_sources.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
        smoke_installed_maintenance(release)
        for executable in (
            maintenance / "release_manager.py",
            maintenance / "reconcile-release.sh",
            maintenance / "update.sh",
            maintenance / "collect-support.sh",
            maintenance / "rollback.sh",
            maintenance / "uninstall.sh",
            maintenance / "ollama_manager.py",
            maintenance / "model_roster_manager.py",
            maintenance / "ollama_qualification_matrix.py",
            maintenance / "speech_manager.py",
            maintenance / "install_summary.py",
            maintenance / "service_manager.py",
            maintenance / "environment_service_manager.py",
            maintenance / "environment_acceptance_runner.py",
            maintenance / "environment_profile_manager.py",
            maintenance / "environment_readiness.py",
            maintenance / "archive_qualifier.py",
            maintenance / "target_probe.py",
            maintenance / "target_preflight.py",
            maintenance / "i2c_manager.py",
            maintenance / "gpio_identity_preflight.py",
            maintenance / "sht31_diagnostic.py",
            maintenance / "runtime_context_preflight.py",
            maintenance / "installer_failure_bundle.py",
            maintenance / "bluetooth_manager.py",
            maintenance / "appliance_manager.py",
            maintenance / "update_manager.py",
            maintenance / "uninstall_manager.py",
        ):
            executable.chmod(0o755)
        # Complete every executable/package check before the immutable seal.
        # The service account, not root, must be able to traverse and execute the
        # candidate.  No runtime smoke is permitted after the seal is created.
        make_candidate_service_readable(workspace, release)
        package_version, _ = smoke_release(
            release,
            service_user,
            profile=profile,
        )
        relocate_venv(release, final)
        purge_release_transients(release)
        write_payload_manifest(release)
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
    validate_release_static(final, commit=commit, profile=profile)
    print(f"[OK] code=RELEASE_BUILT commit={commit} size_kib={tree_size_kib(final)} required_headroom_kib={required_kib}")
    return final


def validate_release_static(
    release: Path,
    *,
    commit: str | None = None,
    profile: str | None = None,
    allow_legacy_transition: bool = False,
) -> dict[str, str]:
    """Validate immutable release identity/integrity without executing its runtime.

    This is the authority for non-activation maintenance such as stale-release
    garbage collection.  Runtime/API policy belongs to candidate activation and
    state-bound transition validation, not to deletion of an unrelated historical
    release.
    """
    if not release.is_dir() or release.is_symlink():
        fail("RELEASE_INVALID", f"release is missing or unsafe: {release}", "build a new immutable candidate", 74)
    record = read_record(release / "release.record", RELEASE_FIELDS, "gonken-release-v1")
    if not COMMIT_RE.fullmatch(record["commit"]) or release.name != record["commit"]:
        fail("RELEASE_INVALID", "release path and recorded commit differ", "quarantine the invalid release", 74)
    if commit and record["commit"] != commit:
        fail("RELEASE_INVALID", "release does not match requested commit", "select the intended candidate", 74)
    if profile and record["profile"] != profile:
        fail("RELEASE_INVALID", "release dependency profile differs", "rebuild for the current platform", 74)
    if profile_uses_distro_bindings(record["profile"]):
        legacy_contract = allow_legacy_transition and _legacy_transition_runtime_allowed(
            release, record["profile"]
        )
        if not legacy_contract:
            if _venv_system_site_packages_enabled(release):
                fail(
                    "RELEASE_VENV_POLICY",
                    f"target release venv exposes broad system site-packages: {release.name}",
                    "rebuild with the isolated allow-listed binding bridge",
                    74,
                )
            if not _binding_manifest_valid(release, record["profile"]):
                fail(
                    "RELEASE_BINDING_MANIFEST",
                    f"target release hardware-binding bridge is missing or invalid: {release.name}",
                    "rebuild the target release from validated distro binding packages",
                    74,
                )
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
        differences = payload_manifest_differences(release)
        detail = ",".join(differences) if differences else "aggregate_only"
        fail(
            "RELEASE_INVALID",
            f"release payload digest differs: {release.name} changed={detail}",
            "quarantine the release and rebuild from the exact current checkpoint",
            74,
        )
    for item in [release, *_authoritative_payload_items(release)]:
        if item.is_symlink():
            continue
        if stat.S_IMODE(item.stat().st_mode) & 0o222:
            fail("RELEASE_MUTABLE", f"release contains a writable path: {item}", "restore immutable permissions or rebuild", 74)
        if item.stat().st_uid != int(record["owner_uid"]):
            fail("RELEASE_OWNER", "release ownership differs from its manifest", "restore root ownership or rebuild", 74)
    return record


def validate_release(
    release: Path,
    *,
    commit: str | None = None,
    profile: str | None = None,
    service_user: str,
    postcheck_operation: str | None = None,
    allow_legacy_transition: bool = False,
) -> dict[str, str]:
    record = validate_release_static(
        release,
        commit=commit,
        profile=profile,
        allow_legacy_transition=allow_legacy_transition,
    )
    if allow_legacy_transition and _legacy_transition_runtime_allowed(
        release, record["profile"]
    ):
        if postcheck_operation is not None:
            fail(
                "RELEASE_LEGACY_TRANSITION_SCOPE",
                "legacy transition validation cannot be used for candidate post-switch validation",
                "validate new candidates with the current strict release contract",
                74,
            )
        version, _ = smoke_legacy_transition_source(
            release,
            service_user,
            profile=record["profile"],
        )
    else:
        version, _ = smoke_release(
            release,
            service_user,
            profile=record["profile"],
            operation=postcheck_operation,
        )
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
        previous_path = release_root / "releases" / previous
        if not previous_path.is_dir() or previous_path.is_symlink():
            fail("ROLLBACK_SOURCE_MISSING", "previous release directory is missing or unsafe", "repair the release namespace before retrying", 75)
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
        if not candidate_path.is_dir() or candidate_path.is_symlink():
            fail("ACTIVATION_SOURCE_MISSING", "current journal release directory is missing or unsafe", "install the current checkpoint to replace the broken release", 75)
        # A completed previous release is not re-evaluated with today's runtime
        # contract during a new install.  New candidate validity is independent.
        print(f"[OK] code=ACTIVATION_RECONCILED phase=post_verified commit={candidate} policy=structural_current_only")
        return "post_verified"
    if phase == "rolled_back":
        if pointer != expected_previous:
            fail("ACTIVATION_AMBIGUOUS", "rolled-back journal and current pointer disagree", "inspect installed state manually", 75)
        if previous != "none":
            previous_path = release_root / "releases" / previous
            if not previous_path.is_dir() or previous_path.is_symlink():
                fail("ACTIVATION_SOURCE_MISSING", "rolled-back release directory is missing or unsafe", "install the current checkpoint to restore a valid current release", 75)
        print(f"[OK] code=ACTIVATION_RECONCILED phase=rolled_back commit={previous} policy=structural_current_only")
        return "rolled_back"

    if phase == "prepared":
        if pointer not in {expected_previous, candidate}:
            fail("ACTIVATION_AMBIGUOUS", "prepared journal and current pointer disagree", "inspect installed state manually", 75)
        try:
            validate_release_static(candidate_path, commit=candidate)
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
        validate_release_static(candidate_path, commit=candidate)
    except ReleaseError:
        rollback(release_root, state_root, candidate, previous, service_user, "post_switch_static_validation_failed")
        print(f"[OK] code=ACTIVATION_ROLLED_BACK commit={previous}")
        return "rolled_back"
    write_journal(state_root, candidate, previous, "post_verified", "candidate_validated_after_switch")
    print(f"[OK] code=ACTIVATION_RECONCILED phase=post_verified commit={candidate}")
    return "post_verified"


def activate(release_root: Path, state_root: Path, commit: str, service_user: str) -> None:
    reconcile(release_root, state_root, service_user)
    # Normal activation validates only the requested candidate's immutable seal.
    # Previously active releases are transition state, not dependencies of the
    # new candidate.  Runtime capability checks occur in later current-release
    # installer gates and service readiness, never by executing historical code.
    validate_release_static(
        release_root / "releases" / commit,
        commit=commit,
    )
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
        validate_release_static(
            release_root / "releases" / commit,
            commit=commit,
        )
    except ReleaseError:
        rollback(release_root, state_root, commit, previous, service_user, "post_switch_static_validation_failed")
        raise
    write_journal(state_root, commit, previous, "post_verified", "candidate_validated_after_switch")
    print(f"[OK] code=ACTIVATION_COMPLETE commit={commit} previous={previous}")


def prune_releases(release_root: Path, state_root: Path, service_user: str) -> None:
    """Best-effort garbage collection that can never invalidate a completed activation.

    The active and rollback releases remain protected by the activation journal.
    Historical releases are deleted only after static immutable-integrity checks;
    their obsolete runtime dependency contract is deliberately irrelevant.  A
    malformed stale release is retained for administrator review and reported as
    a warning instead of turning an already successful activation into failure.
    """
    del service_user  # runtime execution is intentionally forbidden while pruning
    journal = read_journal(state_root)
    if not journal or journal["phase"] != "post_verified":
        return
    keep = {journal["candidate_commit"]}
    if journal["previous_commit"] != "none":
        keep.add(journal["previous_commit"])
    releases = release_root / "releases"
    for path in releases.iterdir():
        if not COMMIT_RE.fullmatch(path.name) or path.name in keep:
            continue
        if path.is_symlink() or not path.is_dir():
            print(
                f"[WARN] code=RELEASE_PRUNE_SKIPPED commit={path.name} "
                "reason=UNSAFE_RELEASE_PATH remediation=inspect_stale_release_manually",
                file=sys.stderr,
            )
            continue
        try:
            _remove_validated_release(path, releases)
        except (ReleaseError, OSError) as error:
            reason = error.code if isinstance(error, ReleaseError) else "FILESYSTEM_ERROR"
            print(
                f"[WARN] code=RELEASE_PRUNE_SKIPPED commit={path.name} "
                f"reason={reason} remediation=inspect_stale_release_manually",
                file=sys.stderr,
            )
            continue
        print(f"[OK] code=RELEASE_PRUNED commit={path.name}")


def status(release_root: Path, state_root: Path, expected: str | None, service_user: str) -> None:
    journal = read_journal(state_root)
    pointer = current_commit(release_root)
    if not journal or journal["phase"] != "post_verified" or pointer != journal["candidate_commit"]:
        fail("ACTIVATION_INCOMPLETE", "release activation is not post-verified", "run reconciliation and inspect failures", 1)
    if expected and pointer != expected:
        fail("ACTIVATION_WRONG_RELEASE", "active release differs from the requested commit", "activate the verified candidate", 1)
    validate_release_static(
        release_root / "releases" / pointer,
        commit=pointer,
        allow_legacy_transition=True,
    )
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
    # The previous release is state-bound evidence: it was the active,
    # post-verified release immediately before the current candidate.  Permit a
    # bounded compatibility rollback when that release predates the bridge
    # manifest, while keeping normal candidate activation strict.
    current = current_commit(release_root)
    if current != pointer:
        fail("ROLLBACK_STATE", "active release changed while preparing rollback", "retry after inspecting activation state", 75)
    validate_release(
        release_root / "releases" / previous,
        commit=previous,
        service_user=service_user,
        allow_legacy_transition=True,
    )
    write_journal(state_root, previous, pointer, "prepared", "operator_rollback_candidate_validated")
    switch_current(release_root, previous)
    write_journal(state_root, previous, pointer, "switched", "operator_rollback_pointer_replaced")
    validate_release(
        release_root / "releases" / previous,
        commit=previous,
        service_user=service_user,
        allow_legacy_transition=True,
    )
    write_journal(state_root, previous, pointer, "post_verified", "operator_rollback_candidate_validated_after_switch")
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

    validate_static = commands.add_parser("validate-static")
    validate_static.add_argument("--release", required=True)
    validate_static.add_argument("--commit")
    validate_static.add_argument("--profile")

    bindings = commands.add_parser("bindings-check")
    bindings.add_argument("--release", required=True)
    bindings.add_argument("--commit")
    bindings.add_argument("--profile", required=True)
    bindings.add_argument("--service-user", required=True)
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
        elif args.command == "validate-static":
            validate_release_static(
                require_absolute(args.release, "release"),
                commit=require_commit(args.commit) if args.commit else None,
                profile=require_profile(args.profile) if args.profile else None,
            )
            print("[OK] code=RELEASE_STATIC_VALID")
        elif args.command == "bindings-check":
            release = require_absolute(args.release, "release")
            record = validate_release_static(
                release,
                commit=require_commit(args.commit) if args.commit else None,
                profile=require_profile(args.profile),
            )
            validate_runtime_hardware_bindings(release, record["profile"], args.service_user)
            print("[OK] code=RELEASE_BINDINGS_VALID")
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
