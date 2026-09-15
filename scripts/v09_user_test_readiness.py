#!/usr/bin/env python3
"""Gate the V09 checkpoint-22 user simulation/sensor-deferred HIL handoff.

The READY label produced by this script means the package is ready for supervised
user simulation and sensor-deferred HIL testing.  It is intentionally not a
physical Raspberry Pi, SHT31, relay, fan, wake, or audio acceptance verdict.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "development"
READY = "READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL"
NOT_READY = "NOT_READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL"
DEVELOPMENT_READY = "DEVELOPMENT_READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL"
SIM_SCHEMA = "gonken-v09-m10.14-simulation-evidence-v1"
REQUIRED_HOST_MILESTONES = {
    "M8.1",
    "M8.2",
    "M8.3",
    "M9.3",
    "M9.5",
    "M10.6",
    "M10.8",
    "M10.9",
    "M10.10",
    "M10.11",
    "M10.12",
    "M10.13",
}
REQUIRED_SIM_STEPS = {
    "full_simulation_provenance",
    "manual_fan_control",
    "automatic_hysteresis_cycle",
    "semi_automatic_no_autostart",
    "sensor_stale_safe_off_recovery",
    "passive_watch_no_observer_effect",
    "sensor_deferred_real_actuator_profile_check",
}
REQUIRED_HANDOFF_FILES = {
    "README.md",
    "docs/HARDWARE_SETUP.md",
    "docs/ENVIRONMENT_CONTROL.md",
    "docs/SIMULATION.md",
    "docs/OPERATIONS.md",
    "docs/TROUBLESHOOTING.md",
    "docs/ENVIRONMENT_ACCEPTANCE_RUN.md",
    "docs/USER_SIMULATION_HIL_HANDOFF.md",
    "scripts/environment_acceptance_runner.py",
    "scripts/collect-support.sh",
}


def run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True, timeout=20)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip()[:500])
    return json.loads(result.stdout)


def git_state() -> dict[str, Any]:
    def run(*args: str) -> str:
        result = subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else "unknown"

    return {
        "branch": run("branch", "--show-current"),
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(run("status", "--porcelain")),
    }


def validate_simulation_manifest(path: Path, *, current_commit: str) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"simulation manifest unreadable: {type(exc).__name__}"], {}
    if payload.get("schema") != SIM_SCHEMA:
        errors.append("simulation manifest schema mismatch")
    if payload.get("summary_status") != "PASS":
        errors.append("simulation manifest is not PASS")
    if payload.get("physical_acceptance_claimed") is not False:
        errors.append("simulation manifest must not claim physical acceptance")
    if payload.get("evidence_mode") != "HOST_SIMULATION":
        errors.append("simulation manifest evidence_mode must be HOST_SIMULATION")
    if payload.get("sht31_physical_acceptance") != "NOT_RUN":
        errors.append("SHT31 physical acceptance must remain NOT_RUN")
    if payload.get("relay_fan_physical_acceptance") != "NOT_RUN":
        errors.append("relay/fan physical acceptance must remain NOT_RUN")
    if payload.get("sensor_deferred_hil_physical_actuation_tested") is not False:
        errors.append("host release gate may not claim sensor-deferred physical actuation")
    manifest_git = payload.get("git", {})
    manifest_commit = str(manifest_git.get("commit", "")) if isinstance(manifest_git, dict) else ""
    if current_commit == "unknown":
        errors.append("current repository commit is unavailable")
    elif manifest_commit != current_commit:
        errors.append("simulation manifest commit does not match current repository HEAD")
    passed_steps = {
        str(step.get("step_id"))
        for step in payload.get("steps", [])
        if isinstance(step, dict) and step.get("status") == "PASS" and step.get("physical_evidence_claimed") is False
    }
    missing_steps = sorted(REQUIRED_SIM_STEPS - passed_steps)
    if missing_steps:
        errors.append("simulation manifest missing required PASS steps: " + ", ".join(missing_steps))
    return errors, payload


def build_report(*, simulation_manifest: Path | None, allow_dirty: bool) -> dict[str, Any]:
    errors: list[str] = []
    git = git_state()
    milestones = json.loads((DOCS / "MILESTONES.json").read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in milestones["milestones"]}

    missing_milestones = sorted(REQUIRED_HOST_MILESTONES - set(by_id))
    not_verified = sorted(
        item for item in REQUIRED_HOST_MILESTONES
        if item in by_id and by_id[item].get("software") != "host-verified"
    )
    if missing_milestones:
        errors.append("missing required host milestones: " + ", ".join(missing_milestones))
    if not_verified:
        errors.append("required host milestones not host-verified: " + ", ".join(not_verified))

    m10_7 = by_id.get("M10.7")
    if not m10_7 or m10_7.get("target") != "not-run":
        errors.append("M10.7 physical target acceptance must remain not-run at this gate")
    m10_14 = by_id.get("M10.14")
    if not m10_14 or m10_14.get("software") != "host-verified":
        errors.append("M10.14 software state must be host-verified before the user-test label")
    if not m10_14 or m10_14.get("target") != "not-run":
        errors.append("M10.14 target state must remain not-run")

    missing_files = sorted(path for path in REQUIRED_HANDOFF_FILES if not (ROOT / path).is_file())
    if missing_files:
        errors.append("missing handoff files: " + ", ".join(missing_files))

    release_report: dict[str, Any] = {}
    docs_report: dict[str, Any] = {}
    try:
        release_report = run_json([sys.executable, "scripts/release_readiness.py", "--json", "--allow-dirty"])
        if release_report.get("status") != "READY_FOR_TARGET_ACCEPTANCE":
            errors.append("base release_readiness.py is not READY_FOR_TARGET_ACCEPTANCE")
    except Exception as exc:
        errors.append(f"base release readiness failed: {type(exc).__name__}")
    try:
        docs_report = run_json([sys.executable, "scripts/validate_v09_docs.py", "--json"])
        if docs_report.get("status") != "PASS":
            errors.append("V09 documentation validator is not PASS")
    except Exception as exc:
        errors.append(f"documentation validation failed: {type(exc).__name__}")

    manifest_payload: dict[str, Any] = {}
    if simulation_manifest is None:
        errors.append("fresh M10.14 simulation manifest is required")
    else:
        manifest_errors, manifest_payload = validate_simulation_manifest(simulation_manifest, current_commit=str(git["commit"]))
        errors.extend(manifest_errors)
        manifest_git = manifest_payload.get("git", {}) if isinstance(manifest_payload, dict) else {}
        if isinstance(manifest_git, dict) and manifest_git.get("dirty") is True and not allow_dirty:
            errors.append("simulation manifest was collected from a dirty worktree")

    # Passing --allow-dirty is itself a development override.  It can never
    # produce the final READY label, even if the tree happens to be clean.
    dirty_development_override = bool(allow_dirty)
    if git["dirty"] and not allow_dirty:
        errors.append("repository worktree is dirty")

    if errors:
        status = NOT_READY
    elif dirty_development_override:
        status = DEVELOPMENT_READY
    else:
        status = READY
    return {
        "schema": 1,
        "status": status,
        "physical_acceptance_claimed": False,
        "development_dirty_override": dirty_development_override,
        "user_test_scope": "simulation and supervised sensor-deferred HIL readiness",
        "git": git,
        "required_host_milestones": sorted(REQUIRED_HOST_MILESTONES),
        "missing_host_milestones": missing_milestones,
        "not_host_verified": not_verified,
        "missing_handoff_files": missing_files,
        "simulation_manifest": str(simulation_manifest) if simulation_manifest else None,
        "simulation_summary_status": manifest_payload.get("summary_status"),
        "base_release_status": release_report.get("status"),
        "documentation_status": docs_report.get("status"),
        "m10_7_physical_acceptance": "NOT_RUN",
        "sht31_physical_acceptance": "NOT_RUN",
        "relay_penglin_fan_physical_acceptance": "NOT_RUN",
        "real_wake_audio_acceptance": "NOT_RUN",
        "errors": errors,
        "next_action": (
            "Install this checkpoint on the Raspberry Pi and follow docs/USER_SIMULATION_HIL_HANDOFF.md. "
            "Run full simulation first, then only supervised sensor-deferred relay/fan HIL after GPIO/wiring preflight. "
            "Export the support ZIP and M10.7 private evidence; do not mark M10.7 PASS locally."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulation-manifest", type=Path, help="fresh m10_14_simulation_manifest.json")
    parser.add_argument("--allow-dirty", action="store_true", help="permit an uncommitted tree for development inspection; never emits the final READY label")
    parser.add_argument("--check", action="store_true", help="return nonzero unless the user-test readiness label can be emitted")
    parser.add_argument("--json", action="store_true", dest="as_json", help="print machine-readable report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_report(simulation_manifest=args.simulation_manifest, allow_dirty=args.allow_dirty)
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Status: {report['status']}")
        print("Physical acceptance claimed: false")
        print("M10.7 physical acceptance: NOT_RUN")
        print("SHT31 physical acceptance: NOT_RUN")
        if report["errors"]:
            for error in report["errors"]:
                print(f"- {error}")
        else:
            print("Next action: " + str(report["next_action"]))
    if args.check and report["status"] != READY:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
