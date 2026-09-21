#!/usr/bin/env python3
"""Start and verify the installed voice appliance through its systemd service."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Source checkout and sealed standalone maintenance both consume the same module.
_source = Path(__file__).resolve().parents[1] / "src"
if _source.is_dir():
    sys.path.insert(0, str(_source))
try:
    from gonken_agent import runtime_readiness as rr
except ModuleNotFoundError as exc:
    if exc.name not in {"gonken_agent", "gonken_agent.runtime_readiness"}:
        raise
    import runtime_readiness as rr

SERVICE = "gonken-agent.service"
READY_FILE = Path("/run/gonken-agent/ready.json")
READINESS_FILE = Path("/run/gonken-agent/readiness.json")
BOOT_ID_FILE = Path("/proc/sys/kernel/random/boot_id")
CURRENT_LINK = Path("/usr/local/lib/gonken-agent/current")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class ApplianceError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, status: int = 74):
        super().__init__(message)
        self.code, self.remediation, self.status = code, remediation, status


def fail(code: str, message: str, remediation: str, status: int = 74) -> None:
    raise ApplianceError(code, message, remediation, status)


def emit(error: ApplianceError) -> None:
    print(f"[ERROR] code={error.code} message={error} remediation={error.remediation}", file=sys.stderr)


def systemctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(["/usr/bin/systemctl", *args], check=False, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        if check:
            fail("APPLIANCE_SYSTEMD", type(exc).__name__, "inspect systemd and rerun bootstrap", 69)
        return subprocess.CompletedProcess(args, 127, "", str(exc))
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")[:800]
        fail("APPLIANCE_SYSTEMD", detail or "systemctl failed", "inspect gonken-agent.service and rerun", result.returncode)
    return result


def current_release_directory() -> Path | None:
    commit, _profile = rr.current_release_identity(CURRENT_LINK)
    return CURRENT_LINK.parent / "releases" / commit if commit else None


def current_release_commit() -> str | None:
    return rr.current_release_identity(CURRENT_LINK)[0]


def current_release_profile() -> str | None:
    return rr.current_release_identity(CURRENT_LINK)[1]


def process_start_ticks(pid: int) -> int | None:
    return rr.process_start_ticks(pid)


def current_boot_id() -> str | None:
    return rr.current_boot_id(BOOT_ID_FILE)


def _binding() -> rr.Binding:
    return rr.Binding(current_release_commit(), current_release_profile(), current_boot_id())


def _read_state(path: Path, *, expected_status: str | None = None) -> dict[str, object] | None:
    value = rr.validate_record(rr.bounded_json(path), _binding(), start_ticks=process_start_ticks)
    return value if value and (expected_status is None or value['status'] == expected_status) else None


def read_ready() -> dict[str, object] | None:
    return rr.read_ready(READY_FILE, binding=_binding(), pending_path=READINESS_FILE)


def read_readiness() -> dict[str, object] | None:
    return rr.read_pending(READINESS_FILE, binding=_binding())


def bounded_failure() -> str:
    """Return content-free service state and reason-code counts only."""
    chunks: list[str] = []
    try:
        result = subprocess.run(
            [
                "/usr/bin/systemctl", "show", SERVICE,
                "--property=ActiveState,SubState,MainPID,ExecMainStatus,Result",
            ],
            check=False, capture_output=True, text=True, timeout=8,
        )
        fields = []
        for line in result.stdout.splitlines():
            key, sep, value = line.partition("=")
            if sep and key in {"ActiveState", "SubState", "MainPID", "ExecMainStatus", "Result"}:
                safe = re.sub(r"[^A-Za-z0-9_.:-]", "", value)[:80]
                fields.append(f"{key}={safe}")
        if fields:
            chunks.append("systemd:" + ",".join(fields))
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        result = subprocess.run(
            ["/usr/bin/journalctl", "-u", SERVICE, "-b", "--no-pager", "-n", "120", "-o", "cat"],
            check=False, capture_output=True, text=True, timeout=8,
        )
        counts: dict[str, int] = {}
        for match in re.finditer(r"(?:^|\s)code=([A-Z0-9_]{1,64})(?:\s|$)", result.stdout):
            code = match.group(1)
            counts[code] = counts.get(code, 0) + 1
        if counts:
            chunks.append("codes:" + ",".join(f"{key}={counts[key]}" for key in sorted(counts)))
    except (OSError, subprocess.TimeoutExpired):
        pass
    return " | ".join(chunks)[:1200]


def status() -> dict[str, object]:
    enabled = systemctl("is-enabled", "--quiet", SERVICE, check=False).returncode == 0
    active = systemctl("is-active", "--quiet", SERVICE, check=False).returncode == 0
    ready = read_ready()
    readiness = read_readiness()
    return {
        "enabled": enabled,
        "active": active,
        "ready": bool(ready),
        "semantic_status": "READY" if ready else (readiness.get("status") if readiness else "UNKNOWN"),
        "pending_component": None if ready else (readiness.get("component") if readiness else None),
        "pending_code": None if ready else (readiness.get("code") if readiness else None),
        "pending_recoverable": None if ready else (readiness.get("recoverable") if readiness else None),
        "wake_phrase": ready.get("wake_phrase") if ready else None,
        "model": ready.get("model") if ready else None,
        "audio_backend": ready.get("audio_backend") if ready else None,
    }


def activate(timeout: int) -> None:
    if os.geteuid() != 0:
        fail("APPLIANCE_PRIVILEGE", "activation requires root", "run through bootstrap or sudo", 77)
    READY_FILE.unlink(missing_ok=True)
    READINESS_FILE.unlink(missing_ok=True)
    systemctl("enable", SERVICE)
    systemctl("reset-failed", SERVICE)
    print("[RUNNING] code=APPLIANCE_START service=gonken-agent.service", flush=True)
    systemctl("restart", SERVICE)
    deadline = time.monotonic() + timeout
    last_pending = ""
    nonrecoverable_seen_at: float | None = None
    while time.monotonic() < deadline:
        if systemctl("is-active", "--quiet", SERVICE, check=False).returncode != 0:
            time.sleep(1)
            continue
        ready = read_ready()
        if ready:
            print(
                f"[READY] code=APPLIANCE_READY service={SERVICE} "
                f"wake_phrase={str(ready['wake_phrase']).replace(' ', '_')} reboot_required=false",
                flush=True,
            )
            return
        pending = read_readiness()
        if pending and pending.get("status") == "WAITING":
            fingerprint = f"{pending.get('component')}:{pending.get('code')}:{pending.get('recoverable')}"
            if fingerprint != last_pending:
                print(
                    "[WAITING] code=APPLIANCE_DEPENDENCY_WAIT "
                    f"component={pending['component']} dependency_code={pending['code']} "
                    f"recoverable={str(pending['recoverable']).lower()}",
                    flush=True,
                )
                last_pending = fingerprint
            if pending.get("recoverable") is False:
                if nonrecoverable_seen_at is None:
                    nonrecoverable_seen_at = time.monotonic()
                elif time.monotonic() - nonrecoverable_seen_at >= 3.0:
                    detail = bounded_failure()
                    fail(
                        "APPLIANCE_DEPENDENCY_FAILED",
                        f"component={pending['component']} code={pending['code']}; {detail}",
                        "correct the named non-recoverable dependency and rerun the same installer",
                        75,
                    )
            else:
                nonrecoverable_seen_at = None
        time.sleep(1)
    pending = read_readiness()
    causal = ""
    if pending and pending.get("status") == "WAITING":
        causal = (
            f"component={pending.get('component')} code={pending.get('code')} "
            f"recoverable={str(pending.get('recoverable')).lower()}; "
        )
    detail = bounded_failure()
    fail(
        "APPLIANCE_NOT_READY",
        f"voice service did not reach semantic readiness within {timeout}s; {causal}{detail}",
        "keep required local dependencies powered, inspect the named component, and upload the generated evidence ZIP",
        75,
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("activate")
    a.add_argument("--timeout", type=int, default=180)
    sub.add_parser("status")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if getattr(args, "timeout", 180) < 30 or getattr(args, "timeout", 180) > 600:
            fail("APPLIANCE_USAGE", "timeout must be 30..600 seconds", "use a bounded readiness timeout", 64)
        if args.command == "activate":
            activate(args.timeout)
        elif args.command == "status":
            data = status()
            if not data["enabled"] or not data["active"] or not data["ready"]:
                fail("APPLIANCE_NOT_READY", json.dumps(data, sort_keys=True), "start/restart the service and inspect logs", 1)
            print(json.dumps(data, sort_keys=True))
    except ApplianceError as error:
        emit(error)
        return error.status
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
