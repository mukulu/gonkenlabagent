#!/usr/bin/env python3
"""Inspect or enable Raspberry Pi I2C without probing sensor addresses."""
from __future__ import annotations

import argparse
import grp
import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path

I2C_DEVICE = Path("/dev/i2c-1")


class I2CError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, exit_code: int = 74):
        super().__init__(message); self.code=code; self.remediation=remediation; self.exit_code=exit_code


def fail(code: str, message: str, remediation: str, exit_code: int = 74) -> None:
    raise I2CError(code, message, remediation, exit_code)


def groups_for(user: str) -> set[str]:
    try:
        account = pwd.getpwnam(user)
    except KeyError:
        fail("I2C_USER_MISSING", f"user does not exist: {user}", "run the installer identity convergence step", 73)
    names = {grp.getgrgid(account.pw_gid).gr_name}
    names.update(item.gr_name for item in grp.getgrall() if user in item.gr_mem)
    return names



def can_open_as_user(user: str, device: Path) -> bool:
    """Prove the service identity can open the I2C character device without selecting an address."""
    runuser = shutil.which("runuser")
    python = shutil.which("python3")
    if not runuser or not python or not user or not device.exists() or device.is_symlink():
        return False
    code = "import os,sys; fd=os.open(sys.argv[1], os.O_RDWR|getattr(os,'O_CLOEXEC',0)); os.close(fd)"
    try:
        result = subprocess.run([runuser, "-u", user, "--", python, "-c", code, str(device)], check=False, capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def status(user: str) -> dict[str, object]:
    tool = shutil.which("raspi-config")
    device = I2C_DEVICE.exists() and not I2C_DEVICE.is_symlink()
    memberships = groups_for(user) if user else set()
    openable = can_open_as_user(user, I2C_DEVICE) if user and device and "i2c" in memberships else False
    return {
        "raspi_config_available": bool(tool),
        "device": str(I2C_DEVICE),
        "device_exists": device,
        "user": user or None,
        "user_i2c_group": ("i2c" in memberships) if user else None,
        "service_user_can_open": openable if user else None,
        "ready_for_sensor_probe": bool(device and (not user or ("i2c" in memberships and openable))),
    }


def enable() -> dict[str, object]:
    if os.geteuid() != 0:
        fail("I2C_PRIVILEGE", "enabling I2C requires root", "run with sudo", 77)
    tool = shutil.which("raspi-config")
    if not tool:
        fail("I2C_TOOL_MISSING", "raspi-config is not available", "install/restore Raspberry Pi OS raspi-config", 69)
    result = subprocess.run([tool, "nonint", "do_i2c", "0"], check=False, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        fail("I2C_ENABLE_FAILED", f"raspi-config returned {result.returncode}", "inspect Raspberry Pi boot configuration and rerun", 74)
    # The boot configuration is now requested.  Device-node appearance is the
    # authoritative current-boot signal; if absent, a reboot/resume is required.
    return {"configured": True, "device_exists": I2C_DEVICE.exists(), "reboot_required": not I2C_DEVICE.exists()}


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command", required=True)
    s=sub.add_parser("status"); s.add_argument("--user", default="gonken-env"); s.add_argument("--require-ready", action="store_true")
    sub.add_parser("enable")
    return p


def main(argv: list[str] | None=None) -> int:
    args=parser().parse_args(argv)
    try:
        if args.command=="status":
            payload=status(args.user)
            state="READY" if payload["ready_for_sensor_probe"] else "NOT_READY"
            print(f"[OK] code=I2C_STATUS status={state} device_exists={str(payload['device_exists']).lower()} user_i2c_group={str(payload['user_i2c_group']).lower()} service_user_can_open={str(payload['service_user_can_open']).lower()}")
            if args.require_ready and not payload["ready_for_sensor_probe"]:
                fail("I2C_NOT_READY", "I2C device/service-user prerequisites are not ready", "run sudo i2c_manager.py enable, reboot if requested, then rerun status", 75)
        else:
            payload=enable()
            print(f"[OK] code=I2C_ENABLE configured=true device_exists={str(payload['device_exists']).lower()} reboot_required={str(payload['reboot_required']).lower()}")
            if payload["reboot_required"]:
                return 75
        return 0
    except I2CError as exc:
        print(f"[ERROR] code={exc.code} message={exc} remediation={exc.remediation}", file=sys.stderr)
        return exc.exit_code


if __name__=="__main__": raise SystemExit(main())
