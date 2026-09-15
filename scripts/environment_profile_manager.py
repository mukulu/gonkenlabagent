#!/usr/bin/env python3
"""Create, transition, or verify governed static room-environment profiles.

The helper never starts services, requests GPIO/I2C devices, or actuates
hardware.  It may create a missing site configuration or atomically transition
between exact profiles previously managed by this helper.  Unknown or mixed
administrator configuration always fails closed.
"""
from __future__ import annotations

import argparse
import grp
import os
import sys
import tempfile
import tomllib
from pathlib import Path

PROFILE_SPECS: dict[str, dict[str, object]] = {
    "full-simulation": {
        "enabled": True,
        "sensor_backend": "simulated",
        "relay_backend": "simulated",
        "relay_bcm": 23,
        "relay_active_high": True,
        "safe_state": "off",
        "simulation_runtime_control_enabled": True,
    },
    "sensor-deferred-relay": {
        "enabled": True,
        "sensor_backend": "simulated",
        "relay_backend": "libgpiod",
        "relay_bcm": 23,
        "relay_active_high": True,
        "safe_state": "off",
        "simulation_runtime_control_enabled": True,
    },
    "real-sensor-simulated-actuator": {
        "enabled": True,
        "sensor_backend": "sht31",
        "i2c_bus": 1,
        "i2c_address": 0x44,
        "sensor_repeatability": "high",
        "relay_backend": "simulated",
        "relay_bcm": 23,
        "relay_active_high": True,
        "safe_state": "off",
        "simulation_runtime_control_enabled": True,
    },
    "full-real": {
        "enabled": True,
        "sensor_backend": "sht31",
        "i2c_bus": 1,
        "i2c_address": 0x44,
        "sensor_repeatability": "high",
        "relay_backend": "libgpiod",
        "relay_bcm": 23,
        "relay_active_high": True,
        "safe_state": "off",
        "simulation_runtime_control_enabled": False,
    },
}

REAL_SENSOR_PROFILES = {"real-sensor-simulated-actuator", "full-real"}
SHT31_ADDRESSES = (0x44, 0x45)

PROFILE_CODES = {
    "full-simulation": "FULL_SIMULATION",
    "sensor-deferred-relay": "SENSOR_DEFERRED_RELAY",
    "real-sensor-simulated-actuator": "REAL_SENSOR_SIMULATED_ACTUATOR",
    "full-real": "FULL_REAL",
}

# Backward-compatible constants retained for checkpoint-24 tests/importers.
EXPECTED = PROFILE_SPECS["sensor-deferred-relay"]


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, int):
        if value == 0x44:
            return "0x44"
        return str(value)
    raise TypeError(value)


def profile_spec(name: str, *, sensor_address: int = 0x44) -> dict[str, object]:
    if name not in PROFILE_SPECS:
        fail("ENV_PROFILE_NAME", f"unsupported profile: {name}", "choose a governed environment profile", 64)
    if sensor_address not in SHT31_ADDRESSES:
        fail("ENV_PROFILE_SENSOR_ADDRESS", "SHT31 address must be 0x44 or 0x45", "use the address proven by the targeted SHT31 diagnostic", 64)
    spec = dict(PROFILE_SPECS[name])
    if name in REAL_SENSOR_PROFILES:
        spec["i2c_address"] = sensor_address
    elif sensor_address != 0x44:
        fail("ENV_PROFILE_SENSOR_ADDRESS", "sensor address applies only to real-sensor profiles", "omit --sensor-address for simulated-sensor profiles", 64)
    return spec


def profile_text(name: str, *, sensor_address: int = 0x44) -> str:
    spec = profile_spec(name, sensor_address=sensor_address)
    lines = ["[extensions.environment]"]
    lines.extend(f"{key} = {_toml_value(value)}" for key, value in spec.items())
    return "\n".join(lines) + "\n"


PROFILE_TEXT = profile_text("sensor-deferred-relay")


class ProfileError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, exit_code: int = 74):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.exit_code = exit_code


def fail(code: str, message: str, remediation: str, exit_code: int = 74) -> None:
    raise ProfileError(code, message, remediation, exit_code)


def emit(error: ProfileError) -> None:
    print(f"[ERROR] code={error.code} message={error} remediation={error.remediation}", file=sys.stderr)


def require_absolute(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or "\n" in value or "\r" in value:
        fail("ENV_PROFILE_PATH", "site configuration path must be absolute and normalized", "use /etc/gonken-agent/config.toml", 64)
    return path


def _load(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        fail("ENV_PROFILE_UNSAFE", "existing site configuration is not a regular file", "inspect the site configuration manually before continuing", 75)
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        fail("ENV_PROFILE_INVALID", f"cannot parse existing site configuration: {exc}", "repair the existing configuration before continuing", 65)
    return payload


def read_environment(path: Path) -> dict[str, object]:
    payload = _load(path)
    extensions = payload.get("extensions")
    environment = extensions.get("environment") if isinstance(extensions, dict) else None
    if not isinstance(environment, dict):
        fail("ENV_PROFILE_CONFLICT", "existing site configuration does not contain the expected environment section", "merge the environment profile manually after review", 75)
    return environment


def detect_managed_profile_details(path: Path) -> tuple[str, int | None] | None:
    payload = _load(path)
    # Managed profile files contain only the exact extensions.environment table.
    if set(payload) != {"extensions"} or not isinstance(payload.get("extensions"), dict):
        return None
    extensions = payload["extensions"]
    if set(extensions) != {"environment"} or not isinstance(extensions.get("environment"), dict):
        return None
    environment = extensions["environment"]
    for name in PROFILE_SPECS:
        addresses = SHT31_ADDRESSES if name in REAL_SENSOR_PROFILES else (0x44,)
        for address in addresses:
            if environment == profile_spec(name, sensor_address=address):
                return name, (address if name in REAL_SENSOR_PROFILES else None)
    return None


def detect_managed_profile(path: Path) -> str | None:
    details = detect_managed_profile_details(path)
    return details[0] if details else None


def exact_profile(path: Path, name: str = "sensor-deferred-relay", *, sensor_address: int | None = None) -> bool:
    details = detect_managed_profile_details(path)
    if not details or details[0] != name:
        return False
    return sensor_address is None or details[1] == sensor_address


def _group_gid(group: str) -> int:
    try:
        return grp.getgrnam(group).gr_gid
    except KeyError:
        fail("ENV_PROFILE_GROUP", f"required control group does not exist: {group}", "run the checkpoint installer successfully before creating an environment profile", 73)


def _atomic_write(path: Path, text: str, *, group: str) -> None:
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
            handle.write(text)
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


def ensure_profile(path: Path, *, name: str, group: str, sensor_address: int = 0x44) -> str:
    target_spec = profile_spec(name, sensor_address=sensor_address)
    target_text = profile_text(name, sensor_address=sensor_address)
    if path.exists() or path.is_symlink():
        current = detect_managed_profile_details(path)
        if current is not None and read_environment(path) == target_spec:
            return "ALREADY_CONFIGURED"
        if current is None:
            fail("ENV_PROFILE_CONFLICT", "existing site configuration is not an exact managed environment profile", "review and merge administrator configuration manually; no file was changed", 75)
        _atomic_write(path, target_text, group=group)
        if read_environment(path) != target_spec:
            fail("ENV_PROFILE_VERIFY", "transitioned site configuration did not verify", "inspect the managed file and restore the prior profile", 74)
        return f"TRANSITIONED_FROM_{PROFILE_CODES[current[0]]}"
    _atomic_write(path, target_text, group=group)
    if read_environment(path) != target_spec:
        fail("ENV_PROFILE_VERIFY", "written site configuration did not verify", "remove the managed file after inspection and rerun", 74)
    return "CREATED"


def durable_create(path: Path, *, group: str) -> None:
    if path.exists() or path.is_symlink():
        fail("ENV_PROFILE_CONFLICT", "site configuration already exists and differs from the managed profile", "review the existing file; this helper will not overwrite administrator configuration", 75)
    _atomic_write(path, PROFILE_TEXT, group=group)


def ensure_sensor_deferred(path: Path, *, group: str) -> str:
    return ensure_profile(path, name="sensor-deferred-relay", group=group)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=[*PROFILE_SPECS, "status"])
    result.add_argument("--site", default="/etc/gonken-agent/config.toml")
    result.add_argument("--group", default="gonken-envctl")
    result.add_argument("--sensor-address", default="0x44", choices=("0x44", "0x45"), help="real SHT31 address; ignored only when left at default for simulated-sensor profiles")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        path = require_absolute(args.site)
        production = path == Path("/etc/gonken-agent/config.toml")
        if production and args.command != "status" and os.geteuid() != 0:
            fail("ENV_PROFILE_PRIVILEGE", "production site configuration requires root", "run this maintenance helper with sudo", 77)
        if args.command == "status":
            if not path.exists() and not path.is_symlink():
                status = "ABSENT"
            else:
                selected = detect_managed_profile(path)
                status = PROFILE_CODES[selected] if selected else "OTHER_ADMIN_CONFIG"
            print(f"[OK] code=ENV_PROFILE_STATUS status={status} path={path}")
            return 0
        sensor_address = int(args.sensor_address, 0)
        status = ensure_profile(path, name=args.command, group=args.group, sensor_address=sensor_address)
        spec = profile_spec(args.command, sensor_address=sensor_address)
        address_text = f"i2c_address=0x{int(spec['i2c_address']):02x} " if args.command in REAL_SENSOR_PROFILES else ""
        print(
            f"[OK] code=ENV_PROFILE_APPLIED profile={args.command} status={status} path={path} "
            f"sensor_backend={spec['sensor_backend']} relay_backend={spec['relay_backend']} "
            f"{address_text}hardware_toggled=false service_started=false physical_evidence=false"
        )
        return 0
    except ProfileError as error:
        emit(error)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
