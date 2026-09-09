#!/usr/bin/env python3
"""Install, validate, and remove the governed application systemd service."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


SERVICE_NAME = "gonken-agent.service"
TMPFILES_NAME = "gonken-agent.conf"
FORBIDDEN_TEXT = (
    "sudo",
    "sudoers",
    "polkit",
    "poweroff",
    "reboot",
    "shutdown",
    "halt",
    "PrivateDevices=true",
)
REQUIRED_LINES = (
    "Type=exec",
    "User=gonken-agent",
    "Group=gonken-agent",
    "ExecStartPre=/usr/local/lib/gonken-agent/current/maintenance/reconcile-release.sh",
    "ExecStart=/usr/local/lib/gonken-agent/current/.venv/bin/gonken-agent service",
    "Restart=on-failure",
    "NoNewPrivileges=true",
    "PrivateTmp=true",
    "ProtectHome=true",
    "ProtectSystem=full",
    "CapabilityBoundingSet=",
    "PrivateDevices=false",
)


class ServiceError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, exit_code: int = 74):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.exit_code = exit_code


def fail(code: str, message: str, remediation: str, exit_code: int = 74) -> None:
    raise ServiceError(code, message, remediation, exit_code)


def emit_error(error: ServiceError) -> None:
    print(f"[ERROR] code={error.code} message={error} remediation={error.remediation}", file=sys.stderr)


def require_absolute(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or "\n" in value or "\r" in value or ".." in path.parts:
        fail("SERVICE_PATH", f"{label} must be an absolute normalized path", "supply a safe absolute path", 64)
    return path


def mapped(root: Path, absolute: str) -> Path:
    return Path(absolute) if root == Path("/") else root / absolute.lstrip("/")


def test_mode(root: Path) -> None:
    if root != Path("/") and os.environ.get("GONKEN_ENABLE_TEST_FAILURES") != "1":
        fail("SERVICE_TEST_GATE", "redirected system roots require the explicit test gate", "set GONKEN_ENABLE_TEST_FAILURES=1 only in isolated tests", 77)


def durable_bytes(path: Path, payload: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        fail("SERVICE_LAYOUT", f"destination is a symlink: {path}", "remove the unsafe path after inspection", 73)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
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


def layout(root: Path) -> dict[str, Path]:
    return {
        "unit": mapped(root, f"/etc/systemd/system/{SERVICE_NAME}"),
        "tmpfiles": mapped(root, f"/etc/tmpfiles.d/{TMPFILES_NAME}"),
    }


def read_template(path: Path, label: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        fail("SERVICE_TEMPLATE", f"{label} template is missing or unsafe", "restore it from the active immutable release", 65)
    payload = path.read_bytes()
    text = payload.decode("utf-8")
    if "\r" in text:
        fail("SERVICE_TEMPLATE", f"{label} template contains carriage returns", "restore the repository template", 65)
    return payload


def validate_unit_payload(payload: bytes) -> None:
    text = payload.decode("utf-8")
    for forbidden in FORBIDDEN_TEXT:
        if forbidden.lower() in text.lower():
            fail("SERVICE_PRIVILEGE", f"forbidden service privilege text: {forbidden}", "remove power or privilege-granting behavior", 65)
    for required in REQUIRED_LINES:
        if required not in text:
            fail("SERVICE_TEMPLATE", f"service unit lacks required line: {required}", "restore the governed unit template", 65)
    if not re.search(r"(?m)^ReadWritePaths=/var/lib/gonken-agent/runtime /var/cache/gonken-agent /run/gonken-agent$", text):
        fail("SERVICE_HARDENING", "service writable paths are not restricted to runtime/cache/run", "restore the governed hardening block", 65)


def validate_tmpfiles_payload(payload: bytes) -> None:
    text = payload.decode("utf-8")
    expected = {
        "d /var/lib/gonken-agent/runtime 0750 gonken-agent gonken-agent -",
        "d /var/cache/gonken-agent 0750 gonken-agent gonken-agent -",
        "d /run/gonken-agent 0750 gonken-agent gonken-agent -",
    }
    if set(text.splitlines()) != expected:
        fail("SERVICE_TMPFILES", "tmpfiles template differs from the governed runtime/cache/run contract", "restore the repository template", 65)


def service_files(unit_template: Path, tmpfiles_template: Path) -> tuple[bytes, bytes]:
    unit = read_template(unit_template, "service unit")
    tmpfiles = read_template(tmpfiles_template, "tmpfiles")
    validate_unit_payload(unit)
    validate_tmpfiles_payload(tmpfiles)
    return unit, tmpfiles


def run_tool(tool: Path, *arguments: str, optional: bool = False) -> subprocess.CompletedProcess[str]:
    if not tool.is_absolute():
        fail("SERVICE_TOOL", "manager helper path must be absolute", "use absolute systemctl/systemd-tmpfiles paths", 64)
    if optional and not tool.exists():
        return subprocess.CompletedProcess([str(tool), *arguments], 0, "", "")
    result = subprocess.run([str(tool), *arguments], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")[:400]
        fail("SERVICE_COMMAND", f"command failed ({result.returncode}): {detail or tool.name}", "inspect system service state and rerun", result.returncode if 1 <= result.returncode <= 125 else 74)
    return result


def write_if_exact_or_absent(path: Path, payload: bytes) -> None:
    if path.exists() and (not path.is_file() or path.is_symlink() or path.read_bytes() != payload):
        fail("SERVICE_CONFLICT", f"existing managed file differs: {path}", "review and remove or migrate it explicitly", 75)
    if not path.exists():
        durable_bytes(path, payload)


def validate_installed(root: Path, unit_template: Path, tmpfiles_template: Path) -> dict[str, str]:
    paths = layout(root)
    unit, tmpfiles = service_files(unit_template, tmpfiles_template)
    for destination, payload in ((paths["unit"], unit), (paths["tmpfiles"], tmpfiles)):
        if not destination.is_file() or destination.is_symlink() or destination.read_bytes() != payload:
            fail("SERVICE_INSTALLED", f"installed file differs: {destination}", "rerun service installation or inspect conflicts", 74)
    return {
        "unit_sha256": hashlib.sha256(unit).hexdigest(),
        "tmpfiles_sha256": hashlib.sha256(tmpfiles).hexdigest(),
    }


def install(root: Path, unit_template: Path, tmpfiles_template: Path, systemctl: Path, tmpfiles_tool: Path) -> None:
    paths = layout(root)
    unit, tmpfiles = service_files(unit_template, tmpfiles_template)
    write_if_exact_or_absent(paths["unit"], unit)
    write_if_exact_or_absent(paths["tmpfiles"], tmpfiles)
    run_tool(tmpfiles_tool, "--create", str(paths["tmpfiles"]), optional=root != Path("/"))
    run_tool(systemctl, "daemon-reload")
    run_tool(systemctl, "enable", "--now", SERVICE_NAME)
    print(f"[OK] code=SERVICE_INSTALLED unit={SERVICE_NAME}")


def status(root: Path, unit_template: Path, tmpfiles_template: Path, systemctl: Path) -> None:
    validate_installed(root, unit_template, tmpfiles_template)
    run_tool(systemctl, "is-enabled", "--quiet", SERVICE_NAME)
    run_tool(systemctl, "is-active", "--quiet", SERVICE_NAME)
    print(f"[OK] code=SERVICE_HEALTHY unit={SERVICE_NAME}")


def remove(root: Path, unit_template: Path, tmpfiles_template: Path, systemctl: Path) -> None:
    paths = layout(root)
    validate_installed(root, unit_template, tmpfiles_template)
    run_tool(systemctl, "stop", SERVICE_NAME)
    run_tool(systemctl, "disable", SERVICE_NAME)
    for path in (paths["unit"], paths["tmpfiles"]):
        path.unlink()
    run_tool(systemctl, "daemon-reload")
    print(f"[OK] code=SERVICE_REMOVED unit={SERVICE_NAME}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--system-root", default="/")
    common.add_argument("--unit-template", required=True)
    common.add_argument("--tmpfiles-template", required=True)
    common.add_argument("--systemctl", default="/usr/bin/systemctl")
    common.add_argument("--systemd-tmpfiles", default="/usr/bin/systemd-tmpfiles")
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("install", "status", "remove"):
        commands.add_parser(name, parents=[common])
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = require_absolute(args.system_root, "system root")
        test_mode(root)
        if root == Path("/") and args.command in {"install", "remove"} and os.geteuid() != 0:
            fail("SERVICE_PRIVILEGE", "production service mutation requires root", "run through the validated bootstrap privilege transition", 77)
        unit = require_absolute(args.unit_template, "unit template")
        tmpfiles = require_absolute(args.tmpfiles_template, "tmpfiles template")
        systemctl = require_absolute(args.systemctl, "systemctl")
        tmpfiles_tool = require_absolute(args.systemd_tmpfiles, "systemd-tmpfiles")
        if args.command == "install":
            install(root, unit, tmpfiles, systemctl, tmpfiles_tool)
        elif args.command == "status":
            status(root, unit, tmpfiles, systemctl)
        else:
            remove(root, unit, tmpfiles, systemctl)
    except ServiceError as error:
        emit_error(error)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
