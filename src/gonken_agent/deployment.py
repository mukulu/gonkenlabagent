"""Administrator-only, explicit room preset; never called from model output.

Only selected fields change. Unknown/malformed configuration is rejected before
writing; a private content-addressed backup protects the previous site file.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import tomllib

from .config import ConfigError, _dump_toml, load_config
from .llm.models import DEFAULT_MODEL

LLM_PRESET = {"model": DEFAULT_MODEL, "context_tokens": 2048,
              "max_output_tokens": 96, "keep_alive": "10m"}


def apply_preset(path: Path, *, phase: str = "llm", check: bool = False) -> bool:
    """Apply the named preset, preserving other fields and existing file modes.

    Return whether a change was needed. An exact check never creates files.
    The normal installer calls this under the candidate interpreter as root.
    Test paths are explicit; no source is discovered by traversing user files.
    """
    if phase not in {"llm", "power"}:
        raise ValueError("PRESET_PHASE_INVALID")
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path.is_symlink():
        raise ValueError("PRESET_PATH_UNSAFE")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("PRESET_PARENT_UNSAFE")
    production = path == Path("/etc/gonken-agent/config.toml")
    if production and os.geteuid() != 0:
        raise PermissionError("PRESET_REQUIRES_ADMIN")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
        raise ValueError("PRESET_FILE_UNSAFE")
    if production and (info.st_uid != 0 or info.st_mode & 0o022):
        raise ValueError("PRESET_OWNERSHIP_UNSAFE")
    original = path.read_bytes()
    data = tomllib.loads(original.decode("utf-8"))
    # Validate original and proposed data through the same runtime parser.
    load_config(site_path=path, environ={})
    desired = copy.deepcopy(data)
    if phase == "llm":
        desired.setdefault("llm", {}).update(LLM_PRESET)
    else:
        desired.setdefault("extensions", {}).setdefault("voice_power", {})["enabled"] = True
    if desired == data:
        return False
    if check:
        raise ValueError("PRESET_NOT_APPLIED")
    lock_path = path.with_name(".room-preset.lock")
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        handle, name = tempfile.mkstemp(prefix=".room-preset-", suffix=".toml", dir=path.parent)
        temp = Path(name)
        try:
            os.fchmod(handle, stat.S_IMODE(info.st_mode))
            if os.geteuid() == 0:
                os.fchown(handle, info.st_uid, info.st_gid)
            with os.fdopen(handle, "wb") as out:
                out.write(_dump_toml(desired).encode("utf-8"))
                out.flush(); os.fsync(out.fileno())
            load_config(site_path=temp, environ={})
            if path.is_symlink() or path.read_bytes() != original:
                raise ValueError("PRESET_CONCURRENT_CHANGE")
            backup = path.with_name("config.pre-room-preset." + hashlib.sha256(original).hexdigest() + ".bak")
            try:
                backup_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            except FileExistsError:
                if backup.is_symlink() or backup.read_bytes() != original:
                    raise ValueError("PRESET_BACKUP_CONFLICT")
            else:
                with os.fdopen(backup_fd, "wb") as out:
                    out.write(original); out.flush(); os.fsync(out.fileno())
            os.replace(temp, path)
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(directory_fd)
            finally: os.close(directory_fd)
        finally:
            temp.unlink(missing_ok=True)
    finally:
        os.close(fd)
    return True


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("llm", "power"))
    p.add_argument("--config", type=Path, default=Path("/etc/gonken-agent/config.toml"))
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)
    try:
        changed = apply_preset(args.config, phase=args.phase, check=args.check)
        print(f"[OK] code=ROOM_PRESET_APPLIED phase={args.phase} changed={str(changed).lower()}")
        return 0
    except ValueError as exc:
        # `--check` is an installer postcondition probe. A preset that has not
        # been applied yet is the normal "action required" state and must map
        # to the install engine's ordinary unsatisfied status (1), not a probe
        # failure. Unsafe/malformed input still fails closed with 65.
        if args.check and str(exc) == "PRESET_NOT_APPLIED":
            print(f"[INFO] code=ROOM_PRESET_PENDING phase={args.phase}")
            return 1
        print(f"[ERROR] code=ROOM_PRESET_REJECTED reason={type(exc).__name__}")
        return 65
    except (OSError, ConfigError) as exc:
        # No site content or raw exception body goes to diagnostics.
        print(f"[ERROR] code=ROOM_PRESET_REJECTED reason={type(exc).__name__}")
        return 65


if __name__ == "__main__":
    raise SystemExit(main())
