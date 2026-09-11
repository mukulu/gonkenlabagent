#!/usr/bin/env python3
"""Start and verify the installed voice appliance through its systemd service."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SERVICE = "gonken-agent.service"
READY_FILE = Path("/run/gonken-agent/ready.json")


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


def read_ready() -> dict[str, object] | None:
    if not READY_FILE.is_file() or READY_FILE.is_symlink() or READY_FILE.stat().st_size > 8192:
        return None
    try:
        value = json.loads(READY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("status") != "READY" or value.get("code") != "VOICE_RUNTIME_READY":
        return None
    if not isinstance(value.get("wake_phrase"), str) or not value["wake_phrase"].strip():
        return None
    return value


def bounded_failure() -> str:
    chunks: list[str] = []
    for command in (
        ["/usr/bin/systemctl", "status", SERVICE, "--no-pager", "-l"],
        ["/usr/bin/journalctl", "-u", SERVICE, "-b", "--no-pager", "-n", "60"],
    ):
        try:
            result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=12)
        except (OSError, subprocess.TimeoutExpired):
            continue
        text = (result.stdout or result.stderr).strip()
        if text:
            chunks.append(" ".join(text.split()))
    return " | ".join(chunks)[:2200]


def status() -> dict[str, object]:
    enabled = systemctl("is-enabled", "--quiet", SERVICE, check=False).returncode == 0
    active = systemctl("is-active", "--quiet", SERVICE, check=False).returncode == 0
    ready = read_ready()
    return {
        "enabled": enabled,
        "active": active,
        "ready": bool(ready),
        "wake_phrase": ready.get("wake_phrase") if ready else None,
        "model": ready.get("model") if ready else None,
        "audio_backend": ready.get("audio_backend") if ready else None,
    }


def activate(timeout: int) -> None:
    if os.geteuid() != 0:
        fail("APPLIANCE_PRIVILEGE", "activation requires root", "run through bootstrap or sudo", 77)
    READY_FILE.unlink(missing_ok=True)
    systemctl("enable", SERVICE)
    systemctl("reset-failed", SERVICE)
    print("[RUNNING] code=APPLIANCE_START service=gonken-agent.service", flush=True)
    systemctl("restart", SERVICE)
    deadline = time.monotonic() + timeout
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
        time.sleep(1)
    detail = bounded_failure()
    fail(
        "APPLIANCE_NOT_READY",
        f"voice service did not reach physical readiness within {timeout}s; {detail}",
        "keep the configured microphone/speaker powered and inspect the captured service journal",
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
