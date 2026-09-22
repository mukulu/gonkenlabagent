#!/usr/bin/env python3
"""Select a thermostat mode through the sole environment daemon, preserving policy.

No GPIO, direct sensor access or policy-file writes. The explicit generation
precondition prevents overwriting a concurrent operator update.
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

# Both files live beside each other in source and in sealed maintenance.
from environment_readiness import ReadinessError, read_agent, require_agent

MODES = ("preserve", "manual", "semi_automatic", "automatic", "disabled")
PRESERVED = ("start_c", "stop_c", "minimum_on_seconds", "minimum_off_seconds", "schema_version")


def _policy(payload: dict) -> dict:
    policy = payload.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("policy_missing")
    for field in ("generation", "schema_version", "minimum_on_seconds", "minimum_off_seconds"):
        if type(policy.get(field)) is not int or policy[field] < 0:
            raise ValueError("policy_integer_invalid")
    for field in ("start_c", "stop_c"):
        if type(policy.get(field)) not in (float, int) or not math.isfinite(policy[field]):
            raise ValueError("policy_temperature_invalid")
    if policy.get("mode") not in MODES[1:]:
        raise ValueError("policy_mode_invalid")
    return policy


def converge(agent: Path, mode: str, *, check: bool = False, start_c: float | None = None, stop_c: float | None = None) -> dict:
    if mode not in MODES:
        raise ValueError("mode_invalid")
    before = _policy(read_agent(agent, ["env", "policy", "show", "--json"], 4.0))
    if (start_c is None) != (stop_c is None):
        raise ValueError("threshold_pair_required")
    if start_c is not None and (not all(type(v) in (float, int) and math.isfinite(v) for v in (start_c, stop_c))
                               or not -10 <= stop_c < start_c <= 60 or not 0.5 <= start_c-stop_c <= 15):
        raise ValueError("threshold_invalid")
    desired_mode = before["mode"] if mode == "preserve" else mode
    desired_start = before["start_c"] if start_c is None else start_c
    desired_stop = before["stop_c"] if stop_c is None else stop_c
    if before["mode"] == desired_mode and before["start_c"] == desired_start and before["stop_c"] == desired_stop:
        return before
    if check:
        raise ValueError("policy_mismatch")
    arguments = ["env", "policy", "set", "--expected-generation", str(before["generation"]),
                 "--mode", desired_mode, "--json"]
    if start_c is not None:
        arguments += ["--start-c", str(start_c), "--stop-c", str(stop_c)]
    read_agent(agent, arguments, 4.0)
    after = _policy(read_agent(agent, ["env", "policy", "show", "--json"], 4.0))
    if (after["mode"] != desired_mode or after["start_c"] != desired_start or after["stop_c"] != desired_stop
            or after["generation"] != before["generation"] + 1
            or any(after.get(key) != before.get(key) for key in PRESERVED if key not in {"start_c", "stop_c"})):
        raise ValueError("policy_postcondition_mismatch")
    return after


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--agent", required=True)
    p.add_argument("--mode", choices=MODES, required=True)
    p.add_argument("--start-c", type=float)
    p.add_argument("--stop-c", type=float)
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)
    try:
        policy = converge(require_agent(args.agent), args.mode, check=args.check, start_c=args.start_c, stop_c=args.stop_c)
        print(f"[OK] code=ENVIRONMENT_POLICY_SELECTED mode={policy['mode']} generation={policy['generation']} "
              f"start_c={policy['start_c']} stop_c={policy['stop_c']} minimum_on_seconds={policy['minimum_on_seconds']} "
              f"minimum_off_seconds={policy['minimum_off_seconds']} physical_acceptance=false")
        return 0
    except (ReadinessError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        # Never print private/untrusted subprocess output.
        print(f"[ERROR] code=ENVIRONMENT_POLICY_NOT_CONVERGED reason={type(exc).__name__} "
              "remediation=inspect_daemon_policy_and_retry_no_direct_policy_overwrite", file=sys.stderr)
        return 75


if __name__ == "__main__":
    raise SystemExit(main())
