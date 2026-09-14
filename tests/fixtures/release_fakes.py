"""Deterministic immutable release fixtures for M3.3 tests."""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import stat
from pathlib import Path


def current_user() -> str:
    return pwd.getpwuid(os.geteuid()).pw_name


def freeze(path: Path) -> None:
    for item in sorted(path.rglob("*"), key=lambda entry: len(entry.parts), reverse=True):
        if not item.is_symlink():
            item.chmod(stat.S_IMODE(item.stat().st_mode) & ~0o222)
    path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)


def payload_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*"), key=lambda entry: entry.relative_to(path).as_posix()):
        relative = item.relative_to(path).as_posix()
        if relative == "release.record":
            continue
        if item.is_symlink():
            kind, payload = b"link", os.readlink(item).encode()
        elif item.is_dir():
            kind, payload = b"directory", b""
        else:
            kind, payload = b"file", item.read_bytes()
        digest.update(kind + b"\0" + relative.encode() + b"\0" + payload + b"\0")
    return digest.hexdigest()


def create_fake_release(
    release_root: Path,
    commit: str,
    *,
    fail_after_calls: int | None = None,
) -> Path:
    release = release_root / "releases" / commit
    binary = release / ".venv" / "bin"
    maintenance = release / "maintenance"
    binary.mkdir(parents=True)
    maintenance.mkdir()
    counter_logic = ""
    if fail_after_calls is not None:
        counter_logic = f"""
counter=${{GONKEN_FAKE_COUNTER:?}}
count=0
if [ -f "$counter" ]; then count=$(sed -n '1p' "$counter"); fi
count=$((count + 1))
printf '%s\\n' "$count" >"$counter"
if [ "$count" -ge {fail_after_calls} ]; then exit 41; fi
"""
    cli = binary / "gonken-agent"
    cli.write_text(
        "#!/bin/sh\nset -eu\n"
        + counter_logic
        + "case ${1:-} in\n"
        + "  version) printf '%s\\n' '0.2.0.dev0' ;;\n"
        + "  status) printf '%s\\n' '"
        + json.dumps({"product": "GonKenLab Agent"}, separators=(",", ":"))
        + "' ;;\n"
        + "  *) exit 2 ;;\n"
        + "esac\n",
        encoding="utf-8",
    )
    cli.chmod(0o755)
    python = binary / "python"
    python.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = -m ] && [ \"${2:-}\" = pip ] && [ \"${3:-}\" = check ]; then exit 0; fi\n"
        "exit 2\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    manager = maintenance / "release_manager.py"
    manager.write_text("# fixture maintenance helper\n", encoding="utf-8")
    manager.chmod(0o755)
    reconcile = maintenance / "reconcile-release.sh"
    reconcile.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    reconcile.chmod(0o755)
    manager_hash = hashlib.sha256(manager.read_bytes()).hexdigest()
    fields = {
        "format": "gonken-release-v1",
        "commit": commit,
        "profile": "dev-py312",
        "python_version": "3.12.14",
        "package_version": "0.2.0.dev0",
        "lock_sha256": "0" * 64,
        "wheel_sha256": "1" * 64,
        "build_backend": "fixture",
        "maintenance_sha256": manager_hash,
        "payload_sha256": payload_sha256(release),
        "owner_uid": str(os.geteuid()),
        "payload_size_kib": "1",
        "built_epoch": "1788912000",
        "validation": "passed",
    }
    (release / "release.record").write_text(
        "".join(f"{key}={value}\n" for key, value in fields.items()),
        encoding="utf-8",
    )
    freeze(release)
    return release


def point_current(release_root: Path, commit: str) -> None:
    current = release_root / "current"
    if current.is_symlink():
        current.unlink()
    current.symlink_to(f"releases/{commit}")
