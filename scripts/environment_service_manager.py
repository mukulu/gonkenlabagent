#!/usr/bin/env python3
"""Install, validate, and remove the governed room-environment systemd service.

This manager installs only the structural service and tmpfiles contract.  It
intentionally does not enable or start ``gonken-environment.service`` during a
generic upgrade, because V09 environment hardware remains disabled until an
operator explicitly enables the static hardware profile and completes target
acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import grp
import subprocess
import sys
import tempfile
from pathlib import Path


SERVICE_NAME = "gonken-environment.service"
TMPFILES_NAME = "gonken-environment.conf"
SERVICE_USER = "gonken-env"
SERVICE_GROUP = "gonken-env"
CONTROL_GROUP = "gonken-envctl"
NON_ACTUATING_COMMISSIONED_PROFILES = {"full-simulation", "real-sensor-simulated-actuator"}
REAL_ACTUATOR_PROFILES = {"sensor-deferred-relay", "full-real"}
KNOWN_TEST_DROPIN = (
    "[Service]\n"
    "Environment=GONKEN_EXTENSIONS_ENVIRONMENT_ENABLED=true\n"
    "Environment=GONKEN_EXTENSIONS_ENVIRONMENT_RELAY_BACKEND=simulated\n"
)
KNOWN_PREVIOUS_UNIT_SHA256 = {
    # Checkpoint-32 unit before explicit Python bytecode suppression.
    "67123397d52a5895a9f60ce98205d8830d7a566b20e4ab183003f6dbabcd225b",
}
FORBIDDEN_TEXT = (
    "sudo",
    "sudoers",
    "polkit",
    "poweroff",
    "reboot",
    "shutdown",
    "halt",
    "PrivateDevices=true",
    "AF_INET",
    "AF_INET6",
)
REQUIRED_LINES = (
    "Type=exec",
    "User=gonken-env",
    "Group=gonken-env",
    "EnvironmentFile=-/etc/gonken-agent/environment",
    "Environment=PYTHONDONTWRITEBYTECODE=1",
    "Environment=PYTHONNOUSERSITE=1",
    "ExecStart=/usr/local/lib/gonken-agent/current/.venv/bin/gonken-agent env serve",
    "Restart=on-failure",
    "RestartSec=3",
    "NoNewPrivileges=true",
    "PrivateTmp=true",
    "ProtectHome=read-only",
    "ProtectSystem=strict",
    "ReadWritePaths=/var/lib/gonken-environment /var/cache/gonken-environment /run/gonken-environment",
    "RestrictAddressFamilies=AF_UNIX",
    "CapabilityBoundingSet=",
    "PrivateDevices=false",
)


class EnvironmentServiceError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, exit_code: int = 74):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.exit_code = exit_code


def fail(code: str, message: str, remediation: str, exit_code: int = 74) -> None:
    raise EnvironmentServiceError(code, message, remediation, exit_code)


def emit_error(error: EnvironmentServiceError) -> None:
    print(f"[ERROR] code={error.code} message={error} remediation={error.remediation}", file=sys.stderr)


def require_absolute(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or "\n" in value or "\r" in value or ".." in path.parts:
        fail("ENV_SERVICE_PATH", f"{label} must be an absolute normalized path", "supply a safe absolute path", 64)
    return path


def mapped(root: Path, absolute: str) -> Path:
    return Path(absolute) if root == Path("/") else root / absolute.lstrip("/")


def test_mode(root: Path) -> None:
    if root != Path("/") and os.environ.get("GONKEN_ENABLE_TEST_FAILURES") != "1":
        fail("ENV_SERVICE_TEST_GATE", "redirected system roots require the explicit test gate", "set GONKEN_ENABLE_TEST_FAILURES=1 only in isolated tests", 77)


def durable_bytes(path: Path, payload: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        fail("ENV_SERVICE_LAYOUT", f"destination is a symlink: {path}", "remove the unsafe path after inspection", 73)
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
        "state_dir": mapped(root, "/var/lib/gonken-environment"),
        "cache_dir": mapped(root, "/var/cache/gonken-environment"),
        "run_dir": mapped(root, "/run/gonken-environment"),
        "policy": mapped(root, "/var/lib/gonken-environment/policy.json"),
        "dropin_dir": mapped(root, f"/etc/systemd/system/{SERVICE_NAME}.d"),
    }


def _ownership(root: Path) -> tuple[int, int, int]:
    if root != Path("/"):
        uid = os.getuid()
        gid = os.getgid()
        return uid, gid, gid
    try:
        uid = pwd.getpwnam(SERVICE_USER).pw_uid
        service_gid = grp.getgrnam(SERVICE_GROUP).gr_gid
        control_gid = grp.getgrnam(CONTROL_GROUP).gr_gid
    except KeyError as exc:
        fail("ENV_SERVICE_IDENTITY", f"required environment identity is missing: {exc}", "rerun the environment-account installer step", 73)
    return uid, service_gid, control_gid


def _safe_directory(path: Path, *, mode: int, uid: int, gid: int, production: bool) -> None:
    if path.exists() or path.is_symlink():
        if not path.is_dir() or path.is_symlink():
            fail("ENV_STATE_UNSAFE", f"expected real directory: {path}", "remove or repair the unsafe path after inspection", 75)
    else:
        path.mkdir(parents=True, mode=mode)
    if production:
        os.chown(path, uid, gid)
    # Apply the final mode after ownership so setgid semantics on the runtime
    # directory cannot be lost as a side effect of chown on stricter kernels.
    os.chmod(path, mode)


def reconcile_runtime_state(root: Path) -> None:
    paths = layout(root)
    uid, service_gid, control_gid = _ownership(root)
    production = root == Path("/")
    _safe_directory(paths["state_dir"], mode=0o750, uid=uid, gid=service_gid, production=production)
    _safe_directory(paths["cache_dir"], mode=0o750, uid=uid, gid=service_gid, production=production)
    _safe_directory(paths["run_dir"], mode=0o2770, uid=uid, gid=control_gid, production=production)
    policy = paths["policy"]
    if policy.exists() or policy.is_symlink():
        if not policy.is_file() or policy.is_symlink() or policy.stat().st_size > 65536:
            fail("ENV_POLICY_UNSAFE", f"policy path is unsafe: {policy}", "inspect the policy path before continuing", 75)
        try:
            payload = json.loads(policy.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            fail("ENV_POLICY_JSON_INVALID", f"existing policy cannot be safely reconciled: {type(exc).__name__}", "repair or remove the invalid policy after review", 75)
        if not isinstance(payload, dict):
            fail("ENV_POLICY_JSON_INVALID", "existing policy root is not an object", "repair the policy after review", 75)
        os.chmod(policy, 0o640)
        if production:
            os.chown(policy, uid, service_gid)


def reconcile_known_dropins(root: Path) -> bool:
    directory = layout(root)["dropin_dir"]
    if not directory.exists():
        return False
    if not directory.is_dir() or directory.is_symlink():
        fail("ENV_SERVICE_DROPIN_CONFLICT", "environment drop-in path is unsafe", "inspect systemd drop-ins manually", 75)
    changed = False
    for child in sorted(directory.iterdir()):
        if not child.is_file() or child.is_symlink():
            fail("ENV_SERVICE_DROPIN_CONFLICT", f"unsupported environment drop-in entry: {child.name}", "inspect and remove only after administrator review", 75)
        try:
            text = child.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            fail("ENV_SERVICE_DROPIN_CONFLICT", f"cannot inspect environment drop-in: {child.name}", "inspect it manually", 75)
        if child.name == "10-environment-test.conf" and text == KNOWN_TEST_DROPIN:
            child.unlink()
            changed = True
            continue
        fail("ENV_SERVICE_DROPIN_CONFLICT", f"administrator/unknown environment drop-in is active: {child.name}", "preserve and review the drop-in before managed commissioning", 75)
    if changed and not any(directory.iterdir()):
        directory.rmdir()
    return changed


def converge_commissioned(root: Path, systemctl: Path, profile: str) -> None:
    if profile in REAL_ACTUATOR_PROFILES:
        fail(
            "ENVIRONMENT_PHYSICAL_COMMISSION_REQUIRED",
            f"profile {profile} contains a real relay actuator and cannot be auto-started by generic installation",
            "commission real GPIO23/fan actuation under the supervised Raspberry Pi acceptance ladder",
            78,
        )
    if profile not in NON_ACTUATING_COMMISSIONED_PROFILES:
        fail("ENV_PROFILE_NAME", f"unsupported commissioned profile: {profile}", "choose a canonical safe commissioning profile", 64)
    reconcile_runtime_state(root)
    changed = reconcile_known_dropins(root)
    if changed:
        run_tool(systemctl, "daemon-reload")
    run_tool(systemctl, "enable", SERVICE_NAME)
    run_tool(systemctl, "reset-failed", SERVICE_NAME)
    run_tool(systemctl, "restart", SERVICE_NAME)
    enabled = run_tool(systemctl, "is-enabled", "--quiet", SERVICE_NAME, allow_failure=True).returncode == 0
    active = run_tool(systemctl, "is-active", "--quiet", SERVICE_NAME, allow_failure=True).returncode == 0
    if not enabled or not active:
        fail("ENV_CONFIG_SERVICE_STATE_DRIFT", "commissioned environment service is not enabled and active", "inspect the current service invocation and causal dependency", 75)
    print(f"[READY] code=ENV_SERVICE_COMMISSIONED profile={profile} enabled=true active=true reboot_required=false")


def commissioned_status(root: Path, systemctl: Path, profile: str) -> None:
    validate_runtime_state(root)
    if profile in REAL_ACTUATOR_PROFILES:
        fail("ENVIRONMENT_PHYSICAL_COMMISSION_REQUIRED", f"profile {profile} still requires supervised actuator commissioning", "complete the physical fan acceptance ladder", 78)
    enabled = run_tool(systemctl, "is-enabled", "--quiet", SERVICE_NAME, allow_failure=True).returncode == 0
    active = run_tool(systemctl, "is-active", "--quiet", SERVICE_NAME, allow_failure=True).returncode == 0
    if not enabled or not active:
        fail("ENV_CONFIG_SERVICE_STATE_DRIFT", "commissioned environment service state differs from profile", "reconcile the selected environment profile", 75)
    print(f"[OK] code=ENV_SERVICE_COMMISSIONED_STATUS profile={profile} enabled=true active=true")


def validate_runtime_state(root: Path) -> None:
    paths = layout(root)
    uid, service_gid, control_gid = _ownership(root)
    expectations = (
        ("state_dir", 0o750, uid, service_gid),
        ("cache_dir", 0o750, uid, service_gid),
        ("run_dir", 0o2770, uid, control_gid),
    )
    for key, mode, expected_uid, expected_gid in expectations:
        path = paths[key]
        if not path.is_dir() or path.is_symlink():
            fail("ENV_STATE_METADATA_DRIFT", f"runtime path is missing or unsafe: {path}", "rerun managed environment reconciliation", 75)
        metadata = path.stat()
        if (metadata.st_mode & 0o7777) != mode or metadata.st_uid != expected_uid or metadata.st_gid != expected_gid:
            fail(
                "ENV_STATE_METADATA_DRIFT",
                f"runtime path owner/group/mode differs: {path}",
                "rerun managed environment reconciliation",
                75,
            )
    policy = paths["policy"]
    if policy.exists() or policy.is_symlink():
        if not policy.is_file() or policy.is_symlink():
            fail("ENV_POLICY_MODE_MISMATCH", "policy path is missing or unsafe", "rerun managed environment reconciliation", 75)
        metadata = policy.stat()
        if (metadata.st_mode & 0o777) != 0o640 or metadata.st_uid != uid or metadata.st_gid != service_gid:
            fail(
                "ENV_POLICY_MODE_MISMATCH",
                "policy owner/group/mode differs from governed contract",
                "rerun managed environment reconciliation",
                75,
            )


def read_template(path: Path, label: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        fail("ENV_SERVICE_TEMPLATE", f"{label} template is missing or unsafe", "restore it from the active immutable release", 65)
    payload = path.read_bytes()
    text = payload.decode("utf-8")
    if "\r" in text:
        fail("ENV_SERVICE_TEMPLATE", f"{label} template contains carriage returns", "restore the repository template", 65)
    return payload


def validate_unit_payload(payload: bytes) -> None:
    text = payload.decode("utf-8")
    for forbidden in FORBIDDEN_TEXT:
        if forbidden.lower() in text.lower():
            fail("ENV_SERVICE_PRIVILEGE", f"forbidden environment service text: {forbidden}", "remove network, power or privilege-granting behavior", 65)
    for required in REQUIRED_LINES:
        if required not in text:
            fail("ENV_SERVICE_TEMPLATE", f"environment unit lacks required line: {required}", "restore the governed unit template", 65)
    if "Requires=gonken-agent.service" in text or "Requires=ollama.service" in text:
        fail("ENV_SERVICE_DEPENDENCY", "environment service must not require voice, audio, Ollama, or network", "keep environment control independently supervised", 65)


def validate_tmpfiles_payload(payload: bytes) -> None:
    text = payload.decode("utf-8")
    expected = {
        "d /var/lib/gonken-environment 0750 gonken-env gonken-env -",
        "d /var/cache/gonken-environment 0750 gonken-env gonken-env -",
        "d /run/gonken-environment 2770 gonken-env gonken-envctl -",
    }
    if set(text.splitlines()) != expected:
        fail("ENV_SERVICE_TMPFILES", "tmpfiles template differs from the governed environment runtime/state contract", "restore the repository template", 65)


def service_files(unit_template: Path, tmpfiles_template: Path) -> tuple[bytes, bytes]:
    unit = read_template(unit_template, "environment service unit")
    tmpfiles = read_template(tmpfiles_template, "environment tmpfiles")
    validate_unit_payload(unit)
    validate_tmpfiles_payload(tmpfiles)
    return unit, tmpfiles


def run_tool(
    tool: Path, *arguments: str, optional: bool = False, allow_failure: bool = False
) -> subprocess.CompletedProcess[str]:
    if not tool.is_absolute():
        fail("ENV_SERVICE_TOOL", "manager helper path must be absolute", "use absolute systemctl/systemd-tmpfiles paths", 64)
    if optional and not tool.exists():
        return subprocess.CompletedProcess([str(tool), *arguments], 0, "", "")
    result = subprocess.run([str(tool), *arguments], check=False, capture_output=True, text=True)
    if result.returncode != 0 and not allow_failure:
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")[:400]
        fail("ENV_SERVICE_COMMAND", f"command failed ({result.returncode}): {detail or tool.name}", "inspect system service state and rerun", result.returncode if 1 <= result.returncode <= 125 else 74)
    return result


def write_if_exact_or_absent(
    path: Path, payload: bytes, *, known_previous_sha256: set[str] | None = None
) -> None:
    if path.exists():
        if not path.is_file() or path.is_symlink():
            fail("ENV_SERVICE_CONFLICT", f"existing managed path is unsafe: {path}", "review and remove it explicitly", 75)
        current = path.read_bytes()
        if current == payload:
            return
        digest = hashlib.sha256(current).hexdigest()
        if digest not in (known_previous_sha256 or set()):
            fail("ENV_SERVICE_CONFLICT", f"existing managed file differs: {path}", "review and remove or migrate it explicitly", 75)
        durable_bytes(path, payload)
        print(f"[OK] code=ENV_SERVICE_MANAGED_UPGRADE path={path}")
        return
    durable_bytes(path, payload)


def validate_installed(root: Path, unit_template: Path, tmpfiles_template: Path) -> dict[str, str]:
    paths = layout(root)
    unit, tmpfiles = service_files(unit_template, tmpfiles_template)
    for destination, payload in ((paths["unit"], unit), (paths["tmpfiles"], tmpfiles)):
        if not destination.is_file() or destination.is_symlink() or destination.read_bytes() != payload:
            fail("ENV_SERVICE_INSTALLED", f"installed file differs: {destination}", "rerun environment service installation or inspect conflicts", 74)
    return {
        "unit_sha256": hashlib.sha256(unit).hexdigest(),
        "tmpfiles_sha256": hashlib.sha256(tmpfiles).hexdigest(),
    }


def install(root: Path, unit_template: Path, tmpfiles_template: Path, systemctl: Path, tmpfiles_tool: Path) -> None:
    paths = layout(root)
    unit, tmpfiles = service_files(unit_template, tmpfiles_template)
    write_if_exact_or_absent(
        paths["unit"], unit, known_previous_sha256=KNOWN_PREVIOUS_UNIT_SHA256
    )
    write_if_exact_or_absent(paths["tmpfiles"], tmpfiles)
    run_tool(tmpfiles_tool, "--create", str(paths["tmpfiles"]), optional=root != Path("/"))
    reconcile_runtime_state(root)
    run_tool(systemctl, "daemon-reload")
    # Deliberately no enable/start here.  Hardware remains disabled by default,
    # and absence of target evidence must not be hidden behind a boot service.
    print(f"[OK] code=ENV_SERVICE_INSTALLED unit={SERVICE_NAME} autostart=disabled started=false")


def installed_status(root: Path, unit_template: Path, tmpfiles_template: Path) -> None:
    digests = validate_installed(root, unit_template, tmpfiles_template)
    print(
        f"[OK] code=ENV_SERVICE_INSTALLED_STATUS unit={SERVICE_NAME} "
        f"autostart=disabled started=false unit_sha256={digests['unit_sha256']}"
    )


def remove(root: Path, unit_template: Path, tmpfiles_template: Path, systemctl: Path) -> None:
    paths = layout(root)
    validate_installed(root, unit_template, tmpfiles_template)
    run_tool(systemctl, "stop", SERVICE_NAME)
    run_tool(systemctl, "disable", SERVICE_NAME)
    for path in (paths["unit"], paths["tmpfiles"]):
        path.unlink()
    run_tool(systemctl, "daemon-reload")
    print(f"[OK] code=ENV_SERVICE_REMOVED unit={SERVICE_NAME}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--system-root", default="/")
    common.add_argument("--unit-template", required=True)
    common.add_argument("--tmpfiles-template", required=True)
    common.add_argument("--systemctl", default="/usr/bin/systemctl")
    common.add_argument("--systemd-tmpfiles", default="/usr/bin/systemd-tmpfiles")
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("install", "installed-status", "remove"):
        commands.add_parser(name, parents=[common])
    for name in ("converge", "commissioned-status"):
        command = commands.add_parser(name, parents=[common])
        command.add_argument("--profile", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = require_absolute(args.system_root, "system root")
        test_mode(root)
        if root == Path("/") and args.command in {"install", "remove", "converge"} and os.geteuid() != 0:
            fail("ENV_SERVICE_PRIVILEGE", "production environment service mutation requires root", "run through the validated bootstrap privilege transition", 77)
        unit = require_absolute(args.unit_template, "unit template")
        tmpfiles = require_absolute(args.tmpfiles_template, "tmpfiles template")
        systemctl = require_absolute(args.systemctl, "systemctl")
        tmpfiles_tool = require_absolute(args.systemd_tmpfiles, "systemd-tmpfiles")
        if args.command == "install":
            install(root, unit, tmpfiles, systemctl, tmpfiles_tool)
        elif args.command == "installed-status":
            installed_status(root, unit, tmpfiles)
        elif args.command == "remove":
            remove(root, unit, tmpfiles, systemctl)
        elif args.command == "converge":
            validate_installed(root, unit, tmpfiles)
            converge_commissioned(root, systemctl, args.profile)
        elif args.command == "commissioned-status":
            validate_installed(root, unit, tmpfiles)
            commissioned_status(root, systemctl, args.profile)
        else:  # pragma: no cover
            fail("ENV_SERVICE_COMMAND", "unsupported command", "choose a supported environment service operation", 64)
    except EnvironmentServiceError as error:
        emit_error(error)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
