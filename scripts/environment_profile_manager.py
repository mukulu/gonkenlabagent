#!/usr/bin/env python3
"""Create or verify safe static room-environment target profiles.

This helper never starts services, requests GPIO/I2C devices, or actuates
hardware.  It is intentionally conservative: it creates the supervised
sensor-deferred relay profile only when the site configuration is absent, and
refuses to overwrite a differing administrator-owned configuration.
"""

from __future__ import annotations

import argparse
import os
import pwd
import grp
import stat
import sys
import tempfile
import tomllib
from pathlib import Path


PROFILE_TEXT = """[extensions.environment]\nenabled = true\nsensor_backend = \"simulated\"\nrelay_backend = \"libgpiod\"\nrelay_bcm = 23\nrelay_active_high = true\nsafe_state = \"off\"\nsimulation_runtime_control_enabled = true\n"""
EXPECTED = {
    "enabled": True,
    "sensor_backend": "simulated",
    "relay_backend": "libgpiod",
    "relay_bcm": 23,
    "relay_active_high": True,
    "safe_state": "off",
    "simulation_runtime_control_enabled": True,
}


class ProfileError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, exit_code: int = 74):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.exit_code = exit_code


def fail(code: str, message: str, remediation: str, exit_code: int = 74) -> None:
    raise ProfileError(code, message, remediation, exit_code)


def emit(error: ProfileError) -> None:
    print(
        f"[ERROR] code={error.code} message={error} remediation={error.remediation}",
        file=sys.stderr,
    )


def require_absolute(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or "\n" in value or "\r" in value:
        fail("ENV_PROFILE_PATH", "site configuration path must be absolute and normalized", "use /etc/gonken-agent/config.toml", 64)
    return path


def read_environment(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        fail("ENV_PROFILE_UNSAFE", "existing site configuration is not a regular file", "inspect the site configuration manually before continuing", 75)
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        fail("ENV_PROFILE_INVALID", f"cannot parse existing site configuration: {exc}", "repair the existing configuration before continuing", 65)
    extensions = payload.get("extensions")
    environment = extensions.get("environment") if isinstance(extensions, dict) else None
    if not isinstance(environment, dict):
        fail("ENV_PROFILE_CONFLICT", "existing site configuration does not contain the expected environment section", "merge the sensor-deferred profile manually after review", 75)
    return environment


def exact_profile(path: Path) -> bool:
    environment = read_environment(path)
    return all(environment.get(key) == value for key, value in EXPECTED.items())


def _group_gid(group: str) -> int:
    try:
        return grp.getgrnam(group).gr_gid
    except KeyError:
        fail("ENV_PROFILE_GROUP", f"required control group does not exist: {group}", "run the checkpoint installer successfully before creating the hardware profile", 73)


def durable_create(path: Path, *, group: str) -> None:
    if path.exists() or path.is_symlink():
        fail("ENV_PROFILE_CONFLICT", "site configuration already exists and differs from the managed profile", "review the existing file; this helper will not overwrite administrator configuration", 75)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        fail("ENV_PROFILE_UNSAFE", "site configuration parent is a symlink", "restore /etc/gonken-agent as a real root-owned directory", 75)
    gid = _group_gid(group) if path == Path("/etc/gonken-agent/config.toml") else os.getgid()
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o640)
        if os.geteuid() == 0:
            os.fchown(descriptor, 0, gid)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(PROFILE_TEXT)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def ensure_sensor_deferred(path: Path, *, group: str) -> str:
    if path.exists() or path.is_symlink():
        if exact_profile(path):
            return "ALREADY_CONFIGURED"
        fail("ENV_PROFILE_CONFLICT", "existing site configuration differs from the exact sensor-deferred relay profile", "review and merge the existing administrator configuration manually; no file was changed", 75)
    durable_create(path, group=group)
    if not exact_profile(path):
        fail("ENV_PROFILE_VERIFY", "written site configuration did not verify", "remove the managed file after inspection and rerun", 74)
    return "CREATED"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=["sensor-deferred-relay", "status"])
    result.add_argument("--site", default="/etc/gonken-agent/config.toml")
    result.add_argument("--group", default="gonken-envctl")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        path = require_absolute(args.site)
        production = path == Path("/etc/gonken-agent/config.toml")
        if production and args.command == "sensor-deferred-relay" and os.geteuid() != 0:
            fail("ENV_PROFILE_PRIVILEGE", "production site configuration requires root", "run this maintenance helper with sudo", 77)
        if args.command == "status":
            if not path.exists() and not path.is_symlink():
                print(f"[OK] code=ENV_PROFILE_STATUS status=ABSENT path={path}")
            elif exact_profile(path):
                print(f"[OK] code=ENV_PROFILE_STATUS status=SENSOR_DEFERRED_RELAY path={path}")
            else:
                print(f"[OK] code=ENV_PROFILE_STATUS status=OTHER_ADMIN_CONFIG path={path}")
            return 0
        status = ensure_sensor_deferred(path, group=args.group)
        print(
            f"[OK] code=ENV_PROFILE_SENSOR_DEFERRED status={status} path={path} "
            "sensor_backend=simulated relay_backend=libgpiod relay_bcm=23 "
            "hardware_toggled=false service_started=false physical_evidence=false"
        )
        return 0
    except ProfileError as error:
        emit(error)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
