#!/usr/bin/env python3
"""Validate semantic environment readiness through the daemon-owned IPC surface.

This helper is deliberately passive. It calls ``gonken-agent env health --json``
and never invokes sensor transport, GPIO, fan mutation, or policy mutation directly.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


SAFE_PROFILE_BACKENDS = {
    "full-simulation": ("simulated", "simulated"),
    "real-sensor-simulated-actuator": ("sht31", "simulated"),
}
REAL_ACTUATOR_PROFILES = {"sensor-deferred-relay", "full-real"}


class ReadinessError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, status: int = 75):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.status = status


def fail(code: str, message: str, remediation: str, status: int = 75) -> None:
    raise ReadinessError(code, message, remediation, status)


def require_agent(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or "\n" in value or "\r" in value:
        fail("ENV_READINESS_AGENT_PATH", "agent path must be absolute and normalized", "use the active release gonken-agent executable", 64)
    if not path.is_file() or path.is_symlink() or not path.stat().st_mode & 0o111:
        fail("ENV_READINESS_AGENT_PATH", f"agent executable is unavailable: {path}", "repair the active immutable release", 66)
    return path


def validate_payload(payload: object, profile: str) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "payload_not_object"
    expected = SAFE_PROFILE_BACKENDS.get(profile)
    if expected is None:
        return False, "profile_not_safe_for_passive_commissioning"
    sensor_backend, actuator_backend = expected
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        return False, "provenance_missing"
    problems: list[str] = []
    if str(payload.get("overall", "")).upper() != "READY":
        problems.append(f"overall={payload.get('overall', 'missing')}")
    if str(payload.get("sensor", "")).casefold() != "ready":
        problems.append(f"sensor={payload.get('sensor', 'missing')}")
    if str(payload.get("actuator", "")).upper() != "READY":
        problems.append(f"actuator={payload.get('actuator', 'missing')}")
    if provenance.get("sensor_backend") != sensor_backend:
        problems.append(f"sensor_backend={provenance.get('sensor_backend', 'missing')}")
    if provenance.get("actuator_backend") != actuator_backend:
        problems.append(f"actuator_backend={provenance.get('actuator_backend', 'missing')}")
    if payload.get("physical_evidence") is not False or provenance.get("physical_evidence") is not False:
        problems.append("physical_evidence_must_be_false")
    return not problems, ",".join(problems)


def probe(agent: Path, profile: str, *, timeout: float, interval: float) -> dict[str, object]:
    if profile in REAL_ACTUATOR_PROFILES:
        fail(
            "ENVIRONMENT_PHYSICAL_COMMISSION_REQUIRED",
            f"profile {profile} includes the real relay actuator",
            "complete supervised GPIO23/fan commissioning before semantic full-real readiness",
            78,
        )
    if profile not in SAFE_PROFILE_BACKENDS:
        fail("ENV_PROFILE_NAME", f"unsupported environment readiness profile: {profile}", "choose a canonical commissioned profile", 64)
    deadline = time.monotonic() + timeout
    last = "no_attempt"
    attempts = 0
    while True:
        attempts += 1
        try:
            result = subprocess.run(
                [str(agent), "env", "health", "--json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=min(4.0, max(1.0, timeout)),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            last = type(exc).__name__
        else:
            if result.returncode == 0:
                try:
                    payload = json.loads(result.stdout)
                except json.JSONDecodeError:
                    last = "invalid_json"
                else:
                    ready, detail = validate_payload(payload, profile)
                    if ready:
                        return {"status": "READY", "profile": profile, "attempts": attempts, "health": payload}
                    last = detail or "semantic_not_ready"
            else:
                last = f"agent_exit={result.returncode}"
        if time.monotonic() >= deadline:
            break
        time.sleep(interval)
    fail(
        "ENVIRONMENT_SEMANTIC_NOT_READY",
        f"environment profile {profile} did not reach semantic readiness: {last}",
        "inspect gonken-environment.service, policy/config provenance, I2C access, and upload the canonical evidence ZIP",
        75,
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--agent", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--interval", type=float, default=1.0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.timeout <= 0 or args.timeout > 120 or args.interval < 0 or args.interval > 10:
            fail("ENV_READINESS_USAGE", "timeout/interval are outside governed bounds", "use timeout 0..120 and interval 0..10 seconds", 64)
        agent = require_agent(args.agent)
        result = probe(agent, args.profile, timeout=args.timeout, interval=args.interval)
        health = result["health"] if isinstance(result.get("health"), dict) else {}
        provenance = health.get("provenance") if isinstance(health, dict) and isinstance(health.get("provenance"), dict) else {}
        print(
            "[READY] code=ENVIRONMENT_SEMANTIC_READY "
            f"profile={args.profile} sensor={health.get('sensor', 'unknown')} actuator={health.get('actuator', 'unknown')} "
            f"sensor_backend={provenance.get('sensor_backend', 'unknown')} actuator_backend={provenance.get('actuator_backend', 'unknown')} "
            "physical_evidence=false"
        )
        return 0
    except ReadinessError as exc:
        print(f"[ERROR] code={exc.code} message={exc} remediation={exc.remediation}", file=sys.stderr)
        return exc.status


if __name__ == "__main__":
    raise SystemExit(main())
