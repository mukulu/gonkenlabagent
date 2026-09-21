#!/usr/bin/env python3
"""Bounded passive environment readiness, bound to actual configuration/release.

Reads daemon IPC and optionally a non-actuating config construction check. Never
opens I2C/GPIO, writes policy, or treats software readiness as physical acceptance.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

SAFE_PROFILE_BACKENDS = {
    "full-simulation": ("simulated", "simulated"),
    "real-sensor-simulated-actuator": ("sht31", "simulated"),
    "full-real": ("sht31", "libgpiod"),
}
REAL_ACTUATOR_PROFILES = {"sensor-deferred-relay"}


class ReadinessError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, status: int = 75):
        super().__init__(message)
        self.code, self.remediation, self.status = code, remediation, status


def fail(code: str, message: str, remediation: str, status: int = 75) -> None:
    raise ReadinessError(code, message, remediation, status)


def require_agent(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or "\n" in value or "\r" in value:
        fail("ENV_READINESS_AGENT_PATH", "agent path must be absolute and normalized", "use the active release executable", 64)
    if not path.is_file() or path.is_symlink() or not path.stat().st_mode & 0o111:
        fail("ENV_READINESS_AGENT_PATH", "agent executable is unavailable", "repair the immutable release", 66)
    return path


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def read_agent(agent: Path, arguments: list[str], budget: float) -> dict:
    result = subprocess.run([str(agent), *arguments], check=False, capture_output=True,
                            text=True, timeout=max(0.001, budget))
    if result.returncode != 0:
        raise ValueError(f"agent_exit={result.returncode}")
    if len(result.stdout.encode("utf-8")) > 65536:
        raise ValueError("agent_response_too_large")
    def invalid_constant(value):
        raise ValueError("nonfinite_json")
    payload = json.loads(result.stdout, object_pairs_hook=_pairs, parse_constant=invalid_constant)
    if not isinstance(payload, dict):
        raise ValueError("payload_not_object")
    return payload


def validate_payload(payload: object, profile: str, *, expected_commit: str | None = None,
                     expected_config: str | None = None, binding_only: bool = False) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "payload_not_object"
    expected = SAFE_PROFILE_BACKENDS.get(profile)
    if expected is None:
        return False, "profile_not_supported"
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        return False, "provenance_missing"
    problems: list[str] = []
    if not binding_only:
        for field, wanted in (("overall", "ready"), ("sensor", "ready"), ("actuator", "ready")):
            if str(payload.get(field, "")).casefold() != wanted:
                problems.append(f"{field}_not_ready")
        # Present-day production replies carry polling state. Reject stale sensor
        # readings even if an earlier READY enum has not yet been refreshed.
        state = payload.get("state", {})
        reading = state.get("last_reading", {}) if isinstance(state, dict) else {}
        if isinstance(reading, dict) and reading.get("quality") in {"stale", "failed", "unavailable"}:
            problems.append("reading_stale_or_invalid")
    for field, wanted in zip(("sensor_backend", "actuator_backend"), expected):
        if provenance.get(field) != wanted:
            problems.append(field + "_mismatch")
    if profile == "full-real":
        # Backend identity is mandatory; explicit contradictory simulation flags
        # are rejected too, rather than masked by a backend name.
        if provenance.get("sensor_is_simulated") is not False or provenance.get("actuator_is_simulated") is not False:
            problems.append("real_profile_simulation_flags_invalid")
    if expected_commit is not None and provenance.get("release_commit") != expected_commit:
        problems.append("daemon_release_mismatch")
    if expected_config is not None and provenance.get("configuration_sha256") != expected_config:
        problems.append("daemon_configuration_mismatch")
    if payload.get("physical_evidence") is not False or provenance.get("physical_evidence") is not False:
        problems.append("physical_evidence_must_be_false")
    return not problems, ",".join(problems)


def probe(agent: Path, profile: str, *, timeout: float, interval: float,
          expected_commit: str | None = None, check_config: bool = False,
          binding_only: bool = False) -> dict[str, object]:
    if not math.isfinite(timeout) or not 0 < timeout <= 120 or not math.isfinite(interval) or not 0 <= interval <= 10:
        fail("ENV_READINESS_USAGE", "timeout/interval are outside governed bounds", "use finite bounded seconds", 64)
    if expected_commit is not None and not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        fail("ENV_READINESS_USAGE", "expected commit is invalid", "use the exact source commit", 64)
    if profile in REAL_ACTUATOR_PROFILES:
        fail("ENVIRONMENT_PHYSICAL_COMMISSION_REQUIRED", "simulated sensor with real relay is a supervised HIL profile",
             "use full-real for the room thermostat", 78)
    if profile not in SAFE_PROFILE_BACKENDS:
        fail("ENV_PROFILE_NAME", "unsupported environment profile", "choose a canonical profile", 64)
    if binding_only and not (expected_commit and check_config):
        fail("ENV_READINESS_USAGE", "binding-only requires release and config checks", "supply --expect-commit and --check-config", 64)
    deadline = time.monotonic() + timeout
    expected_config = None
    if check_config:
        try:
            config = read_agent(agent, ["env", "serve", "--check", "--json"], min(4.0, timeout))
            daemon = config.get("daemon", {})
            expected_config = daemon.get("configuration_sha256")
            if (config.get("hardware_toggled") is not False or config.get("enabled") is not True
                    or not isinstance(expected_config, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_config)):
                raise ValueError("config_check_invalid")
            if expected_commit and daemon.get("release_commit") != expected_commit:
                raise ValueError("agent_release_mismatch")
        except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired) as exc:
            fail("ENVIRONMENT_CONFIG_NOT_READY", f"read-only config check failed: {type(exc).__name__}",
                 "validate the selected static profile and existing policy; no hardware was probed")
    last, attempts = "no_attempt", 0
    while time.monotonic() < deadline:
        attempts += 1
        try:
            payload = read_agent(agent, ["env", "health", "--json"], min(4.0, deadline - time.monotonic()))
            ready, last = validate_payload(payload, profile, expected_commit=expected_commit,
                                           expected_config=expected_config, binding_only=binding_only)
            if ready:
                return {"status": "BOUND" if binding_only else "READY", "profile": profile,
                        "attempts": attempts, "health": payload}
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            last = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        remaining = deadline - time.monotonic()
        if remaining > 0 and interval:
            time.sleep(min(interval, remaining))
    fail("ENVIRONMENT_SEMANTIC_NOT_READY", f"environment {profile} not ready: {last}",
         "inspect daemon/config/policy/I2C/GPIO reason codes in the single evidence .tar.bz2")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--agent", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--expect-commit")
    p.add_argument("--check-config", action="store_true")
    p.add_argument("--binding-only", action="store_true", help="check daemon release/config identity without claiming sensor readiness")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = probe(require_agent(args.agent), args.profile, timeout=args.timeout, interval=args.interval,
                       expected_commit=args.expect_commit, check_config=args.check_config, binding_only=args.binding_only)
        health = result["health"]
        provenance = health["provenance"]
        code = "ENVIRONMENT_RUNTIME_BOUND" if args.binding_only else "ENVIRONMENT_SEMANTIC_READY"
        print(f"[OK] code={code} profile={args.profile} sensor={health.get('sensor', 'unknown')} "
              f"actuator={health.get('actuator', 'unknown')} sensor_backend={provenance['sensor_backend']} "
              f"actuator_backend={provenance['actuator_backend']} physical_evidence=false")
        return 0
    except ReadinessError as exc:
        print(f"[ERROR] code={exc.code} message={exc} remediation={exc.remediation}", file=sys.stderr)
        return exc.status


if __name__ == "__main__":
    raise SystemExit(main())
