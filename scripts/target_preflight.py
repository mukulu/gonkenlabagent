#!/usr/bin/env python3
"""Non-actuating Raspberry Pi target preflight for governed GonKen installation.

The preflight is deliberately independent of the active GonKen release.  It
checks prerequisite truth using the host OS, records machine-readable evidence,
and never opens GPIO/I2C devices or starts services.  Optional environment
capabilities are reported without blocking a generic installation.
"""
from __future__ import annotations

import argparse
import grp
import importlib
import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

FORMAT = "gonken-target-preflight-v1"
REQUIRED_PACKAGES = (
    "alsa-utils", "build-essential", "cmake", "i2c-tools", "ca-certificates",
    "git", "python3-libgpiod", "python3-pip", "python3-setuptools",
    "python3-venv", "tar", "util-linux", "zstd",
)
# python3-smbus remains an installation prerequisite until the SHT31 transport
# tranche decides whether the runtime can eliminate it.  Its presence is
# therefore observed here, but only gpiod is a core voice/runtime requirement.
TRANSITIONAL_SENSOR_PACKAGE = "python3-smbus"
REQUIRED_COMMANDS = (
    "aplay", "arecord", "cmake", "c++", "dpkg-query", "getent", "git",
    "groupadd", "i2cdetect", "python3", "runuser", "systemd-tmpfiles", "tar",
    "useradd", "usermod", "zstd",
)


@dataclass(frozen=True)
class Check:
    id: str
    required: bool
    ok: bool
    detail: str
    remediation: str = ""


def _safe_detail(value: str, limit: int = 240) -> str:
    value = " ".join(value.replace("\x00", "").split())
    return value[:limit]


def _package_version(name: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}|${Version}", name],
            text=True, capture_output=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, type(exc).__name__
    text = result.stdout.strip()
    if result.returncode == 0 and text.startswith("install ok installed|"):
        return True, text.split("|", 1)[1]
    return False, _safe_detail(result.stderr or text or f"exit={result.returncode}")


def _module_api(name: str, required_attributes: Iterable[str]) -> tuple[bool, str]:
    try:
        module = importlib.import_module(name)
    except Exception as exc:  # import failures are the evidence being captured
        return False, f"{type(exc).__name__}:{_safe_detail(str(exc))}"
    missing = [attr for attr in required_attributes if not hasattr(module, attr)]
    if missing:
        return False, "missing_api=" + ",".join(missing)
    location = getattr(module, "__file__", "built-in") or "built-in"
    return True, _safe_detail(str(location))


def _group_membership(user: str, required_groups: Iterable[str]) -> tuple[bool, str]:
    try:
        record = pwd.getpwnam(user)
    except KeyError:
        return False, "user_missing"
    memberships = {grp.getgrgid(record.pw_gid).gr_name}
    for entry in grp.getgrall():
        if user in entry.gr_mem:
            memberships.add(entry.gr_name)
    missing = [name for name in required_groups if name not in memberships]
    return not missing, "groups=" + ",".join(sorted(memberships)) + (";missing=" + ",".join(missing) if missing else "")


def _group_contains(group_name: str, users: Iterable[str]) -> tuple[bool, str]:
    try:
        record = grp.getgrnam(group_name)
    except KeyError:
        return False, "group_missing"
    members = set(record.gr_mem)
    missing = [user for user in users if user not in members]
    return not missing, "members=" + ",".join(sorted(members)) + (";missing=" + ",".join(missing) if missing else "")


def prerequisite_checks() -> list[Check]:
    checks: list[Check] = []
    for command in REQUIRED_COMMANDS:
        path = shutil.which(command)
        checks.append(Check(
            f"command:{command}", True, bool(path), path or "missing",
            f"install the package providing {command}",
        ))
    for package in REQUIRED_PACKAGES:
        ok, detail = _package_version(package)
        checks.append(Check(
            f"package:{package}", True, ok, detail,
            f"install or repair Debian package {package}",
        ))
    ok, detail = _package_version(TRANSITIONAL_SENSOR_PACKAGE)
    checks.append(Check(
        f"package:{TRANSITIONAL_SENSOR_PACKAGE}", False, ok, detail,
        "real-SHT31 readiness may install/replace this binding in M10.21",
    ))
    ok, detail = _module_api("gpiod", ("Chip", "request_lines", "LineSettings"))
    checks.append(Check(
        "system-python:gpiod-api", True, ok, detail,
        "repair python3-libgpiod before building the immutable release",
    ))
    ok, detail = _module_api("smbus", ("SMBus",))
    checks.append(Check(
        "system-python:smbus-api", False, ok, detail,
        "real-SHT31 readiness will validate the final transport contract separately",
    ))
    gpiochips = sorted(Path("/dev").glob("gpiochip*"))
    checks.append(Check(
        "device:gpiochip", True, bool(gpiochips),
        ",".join(str(p) for p in gpiochips) if gpiochips else "none",
        "boot a supported Raspberry Pi target with the RP1 GPIO device available",
    ))
    i2c = Path("/dev/i2c-1")
    checks.append(Check(
        "device:i2c-1", False, i2c.exists(), str(i2c) if i2c.exists() else "absent",
        "enable I2C before selecting a real-SHT31 profile; generic install may continue",
    ))
    return checks


def identity_checks(operator: str) -> list[Check]:
    checks: list[Check] = []
    for user, groups, required in (
        ("gonken-agent", ("audio", "gpio"), True),
        ("gonken-env", ("gpio", "i2c"), True),
    ):
        ok, detail = _group_membership(user, groups)
        checks.append(Check(
            f"identity:{user}", required, ok, detail,
            f"rerun the installer identity step to converge {user} memberships",
        ))
    clients = ["gonken-agent", "gonken-env"] + ([] if operator == "root" else [operator])
    ok, detail = _group_contains("gonken-envctl", clients)
    checks.append(Check(
        "identity:gonken-envctl", True, ok, detail,
        "rerun environment_account and start a fresh login session for the operator",
    ))
    return checks


def build_report(phase: str, operator: str) -> dict[str, object]:
    if phase == "prerequisites":
        checks = prerequisite_checks()
    elif phase == "identities":
        checks = identity_checks(operator)
    else:
        raise ValueError(phase)
    required_failures = [check.id for check in checks if check.required and not check.ok]
    warnings = [check.id for check in checks if not check.required and not check.ok]
    return {
        "format": FORMAT,
        "phase": phase,
        "status": "FAIL" if required_failures else ("WARN" if warnings else "PASS"),
        "required_failures": required_failures,
        "warnings": warnings,
        "checks": [asdict(check) for check in checks],
    }


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    if not path.is_absolute() or ".." in path.parts or path.is_symlink():
        raise ValueError("output path must be an absolute non-symlink path")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--phase", choices=("prerequisites", "identities"), required=True)
    result.add_argument("--operator", default="root")
    result.add_argument("--output")
    result.add_argument("--json", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    payload = build_report(args.phase, args.operator)
    if args.output:
        atomic_json(Path(args.output), payload)
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(
            f"[{'OK' if payload['status'] != 'FAIL' else 'ERROR'}] "
            f"code=TARGET_PREFLIGHT phase={args.phase} status={payload['status']} "
            f"required_failures={len(payload['required_failures'])} warnings={len(payload['warnings'])}"
        )
    return 0 if payload["status"] != "FAIL" else 74


if __name__ == "__main__":
    raise SystemExit(main())
