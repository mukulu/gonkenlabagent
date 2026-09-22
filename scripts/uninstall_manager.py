#!/usr/bin/env python3
"""Uninstall GonKenLab Agent-owned service and release files."""

from __future__ import annotations

import argparse
import os
import shutil
import re
import subprocess
import sys
from pathlib import Path


SERVICE_NAME = "gonken-agent.service"
ENVIRONMENT_SERVICE_NAME = "gonken-environment.service"
PURGE_CONFIRMATION = "purge-gonken-agent-data"
OWNED_DATA_PATHS = (
    "/var/lib/gonken-agent",
    "/var/cache/gonken-agent",
    "/srv/gonken-agent",
    "/var/lib/gonken-environment",
    "/var/cache/gonken-environment",
)


class UninstallError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, exit_code: int = 74):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.exit_code = exit_code


def fail(code: str, message: str, remediation: str, exit_code: int = 74) -> None:
    raise UninstallError(code, message, remediation, exit_code)


def emit_error(error: UninstallError) -> None:
    print(f"[ERROR] code={error.code} message={error} remediation={error.remediation}", file=sys.stderr)


def require_absolute(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or "\n" in value or "\r" in value or ".." in path.parts:
        fail("UNINSTALL_PATH", f"{label} must be an absolute normalized path", "supply a safe absolute path", 64)
    return path


def mapped(root: Path, absolute: str) -> Path:
    return Path(absolute) if root == Path("/") else root / absolute.lstrip("/")


def test_mode(root: Path) -> None:
    if root != Path("/") and os.environ.get("GONKEN_ENABLE_TEST_FAILURES") != "1":
        fail("UNINSTALL_TEST_GATE", "redirected system roots require the explicit test gate", "set GONKEN_ENABLE_TEST_FAILURES=1 only in isolated tests", 77)


def run_tool(tool: Path, *arguments: str) -> None:
    if not tool.is_absolute():
        fail("UNINSTALL_TOOL", "systemctl path must be absolute", "use /usr/bin/systemctl", 64)
    result = subprocess.run([str(tool), *arguments], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")[:400]
        fail("UNINSTALL_COMMAND", f"command failed ({result.returncode}): {detail or tool.name}", "inspect system service state and rerun", result.returncode if 1 <= result.returncode <= 125 else 74)


def load_service_payloads(unit_template: Path, tmpfiles_template: Path) -> tuple[bytes, bytes]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import service_manager  # type: ignore

    return service_manager.service_files(unit_template, tmpfiles_template)


def load_environment_service_payloads(unit_template: Path | None, tmpfiles_template: Path | None) -> tuple[bytes, bytes] | None:
    if unit_template is None or tmpfiles_template is None:
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import environment_service_manager  # type: ignore

    return environment_service_manager.service_files(unit_template, tmpfiles_template)


def service_paths(root: Path) -> tuple[Path, Path, Path]:
    return (
        mapped(root, "/etc/systemd/system/gonken-agent.service"),
        mapped(root, "/etc/tmpfiles.d/gonken-agent.conf"),
        mapped(root, "/etc/gonken-agent/runtime-environment"),
    )


def validate_runtime_environment_or_absent(path: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 4096:
        fail("UNINSTALL_CONFLICT", f"managed runtime environment differs: {path}", "review administrator changes before uninstalling", 75)
    text = path.read_text(encoding="utf-8", errors="strict")
    match = re.fullmatch(
        r"XDG_RUNTIME_DIR=/run/user/([1-9][0-9]*)\n"
        r"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/\1/bus\n",
        text,
    )
    if match is None:
        fail("UNINSTALL_CONFLICT", f"managed runtime environment differs: {path}", "review administrator changes before uninstalling", 75)
    return True


def environment_service_paths(root: Path) -> tuple[Path, Path]:
    return (
        mapped(root, "/etc/systemd/system/gonken-environment.service"),
        mapped(root, "/etc/tmpfiles.d/gonken-environment.conf"),
    )


def validate_managed_or_absent(path: Path, payload: bytes) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
        fail("UNINSTALL_CONFLICT", f"managed file differs: {path}", "review administrator changes before uninstalling", 75)
    return True


def remove_if_managed(path: Path, payload: bytes) -> bool:
    if validate_managed_or_absent(path, payload):
        path.unlink()
        return True
    return False


def remove_entrypoint(root: Path) -> bool:
    path = mapped(root, "/usr/local/bin/gonken-agent")
    if not path.exists() and not path.is_symlink():
        return False
    expected = "../lib/gonken-agent/current/.venv/bin/gonken-agent"
    if not path.is_symlink() or os.readlink(path) != expected:
        fail("UNINSTALL_CONFLICT", f"entrypoint differs: {path}", "review the binary path before uninstalling", 75)
    path.unlink()
    return True


def remove_tree(path: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    if path.is_symlink() or not path.is_dir():
        fail("UNINSTALL_CONFLICT", f"owned path is not a real directory: {path}", "inspect the path before uninstalling", 75)
    for directory in [path, *[item for item in path.rglob("*") if item.is_dir() and not item.is_symlink()]]:
        directory.chmod(0o700)
    shutil.rmtree(path)
    return True


def uninstall(
    root: Path,
    unit_template: Path,
    tmpfiles_template: Path,
    systemctl: Path,
    purge_data: bool,
    confirm_purge: str | None,
    environment_unit_template: Path | None = None,
    environment_tmpfiles_template: Path | None = None,
) -> None:
    if purge_data and confirm_purge != PURGE_CONFIRMATION:
        fail("UNINSTALL_PURGE_CONFIRMATION", "purge requires the exact confirmation phrase", f"use --confirm-purge {PURGE_CONFIRMATION}", 64)
    unit_payload, tmpfiles_payload = load_service_payloads(unit_template, tmpfiles_template)
    environment_payloads = load_environment_service_payloads(environment_unit_template, environment_tmpfiles_template)
    unit_path, tmpfiles_path, runtime_env_path = service_paths(root)
    service_installed = validate_managed_or_absent(unit_path, unit_payload)
    validate_managed_or_absent(tmpfiles_path, tmpfiles_payload)
    runtime_env_installed = validate_runtime_environment_or_absent(runtime_env_path)
    environment_service_installed = False
    environment_unit_path = environment_tmpfiles_path = None
    if environment_payloads is not None:
        environment_unit_payload, environment_tmpfiles_payload = environment_payloads
        environment_unit_path, environment_tmpfiles_path = environment_service_paths(root)
        environment_service_installed = validate_managed_or_absent(environment_unit_path, environment_unit_payload)
        validate_managed_or_absent(environment_tmpfiles_path, environment_tmpfiles_payload)

    # The fixed policy is a standalone sidecar in sealed releases, and a pure
    # data module in a source checkout. Never require the installed venv merely
    # to remove its own privilege grant.
    sidecar = Path(__file__).resolve().parent / "gonken_power_policy.py"
    if sidecar.is_file():
        import importlib.util
        spec = importlib.util.spec_from_file_location("gonken_power_policy", sidecar)
        assert spec and spec.loader
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)
        rule_name, rule = policy.RULE_NAME, policy.RULE
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from gonken_agent.power_policy import RULE_NAME, RULE
        rule_name, rule = RULE_NAME, RULE
    rule_path = mapped(root, "/etc/polkit-1/rules.d/" + rule_name)
    rule_installed = validate_managed_or_absent(rule_path, rule.encode("utf-8"))

    removed: list[str] = []
    if service_installed:
        run_tool(systemctl, "stop", SERVICE_NAME)
        run_tool(systemctl, "disable", SERVICE_NAME)
    if environment_service_installed:
        run_tool(systemctl, "stop", ENVIRONMENT_SERVICE_NAME)
        run_tool(systemctl, "disable", ENVIRONMENT_SERVICE_NAME)
    if remove_if_managed(unit_path, unit_payload):
        removed.append("/etc/systemd/system/gonken-agent.service")
    if remove_if_managed(tmpfiles_path, tmpfiles_payload):
        removed.append("/etc/tmpfiles.d/gonken-agent.conf")
    if runtime_env_installed:
        runtime_env_path.unlink()
        removed.append("/etc/gonken-agent/runtime-environment")
    if environment_payloads is not None and environment_unit_path is not None and environment_tmpfiles_path is not None:
        if remove_if_managed(environment_unit_path, environment_payloads[0]):
            removed.append("/etc/systemd/system/gonken-environment.service")
        if remove_if_managed(environment_tmpfiles_path, environment_payloads[1]):
            removed.append("/etc/tmpfiles.d/gonken-environment.conf")
    if service_installed or environment_service_installed:
        run_tool(systemctl, "daemon-reload")
    if rule_installed:
        remove_if_managed(rule_path, rule.encode("utf-8"))
        removed.append("/etc/polkit-1/rules.d/" + rule_name)
    if remove_entrypoint(root):
        removed.append("/usr/local/bin/gonken-agent")
    if remove_tree(mapped(root, "/usr/local/lib/gonken-agent")):
        removed.append("/usr/local/lib/gonken-agent")

    retained = [path for path in OWNED_DATA_PATHS if mapped(root, path).exists() or mapped(root, path).is_symlink()]
    purged: list[str] = []
    if purge_data:
        for path in OWNED_DATA_PATHS:
            if remove_tree(mapped(root, path)):
                purged.append(path)
        retained = []

    print(
        "[OK] code=UNINSTALL_COMPLETE "
        f"removed={','.join(removed) or 'none'} "
        f"retained={','.join(retained) or 'none'} "
        f"purged={','.join(purged) or 'none'}"
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--system-root", default="/")
    result.add_argument("--unit-template", required=True)
    result.add_argument("--tmpfiles-template", required=True)
    result.add_argument("--environment-unit-template")
    result.add_argument("--environment-tmpfiles-template")
    result.add_argument("--systemctl", default="/usr/bin/systemctl")
    result.add_argument("--purge-data", action="store_true")
    result.add_argument("--confirm-purge")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = require_absolute(args.system_root, "system root")
        test_mode(root)
        if root == Path("/") and os.geteuid() != 0:
            fail("UNINSTALL_PRIVILEGE", "production uninstall requires root", "run through an explicit administrator transition", 77)
        uninstall(
            root,
            require_absolute(args.unit_template, "unit template"),
            require_absolute(args.tmpfiles_template, "tmpfiles template"),
            require_absolute(args.systemctl, "systemctl"),
            args.purge_data,
            args.confirm_purge,
            require_absolute(args.environment_unit_template, "environment unit template") if args.environment_unit_template else None,
            require_absolute(args.environment_tmpfiles_template, "environment tmpfiles template") if args.environment_tmpfiles_template else None,
        )
    except UninstallError as error:
        emit_error(error)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
