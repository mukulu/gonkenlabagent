#!/usr/bin/env python3
"""Collect deterministic M10.14 full-simulation and sensor-deferred readiness evidence.

This runner is deliberately non-physical.  It starts an isolated full-simulation
AF_UNIX environment daemon, drives it through the public CLI, checks the real
controller state machine, and validates a sensor-simulated/real-actuator profile
through the non-actuating ``env serve --check`` path.  It never requests GPIO,
never claims fan motion, and never closes M10.7 physical acceptance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
# The evidence runner is a user/package entry point and must execute from a
# clean extracted repository without relying on CI-provided PYTHONPATH.
for import_root in (ROOT, SRC):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

SCHEMA = "gonken-v09-m10.14-simulation-evidence-v1"
REQUIRED_STEP_IDS = {
    "full_simulation_provenance",
    "manual_fan_control",
    "automatic_hysteresis_cycle",
    "semi_automatic_no_autostart",
    "sensor_stale_safe_off_recovery",
    "passive_watch_no_observer_effect",
    "sensor_deferred_real_actuator_profile_check",
}


class SimulationRunnerError(RuntimeError):
    def __init__(self, code: str, message: str, exit_code: int = 74) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


@dataclass(slots=True)
class Step:
    step_id: str
    title: str
    status: str
    detail: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "status": self.status,
            "physical_evidence_claimed": False,
            "detail": self.detail,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_state() -> dict[str, Any]:
    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, check=False, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"

    return {
        "branch": run("branch", "--show-current"),
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(run("status", "--porcelain")),
    }


def safe_output_dir(path: Path) -> Path:
    candidate = path.expanduser().resolve(strict=False)
    if str(candidate) == "/" or "\n" in str(candidate) or "\r" in str(candidate):
        raise SimulationRunnerError("M10_14_OUTPUT_DIR", "unsafe output directory", 64)
    if candidate.exists() and candidate.is_symlink():
        raise SimulationRunnerError("M10_14_OUTPUT_DIR", "output directory is a symlink", 73)
    candidate.mkdir(parents=True, exist_ok=True)
    if not candidate.is_dir() or candidate.is_symlink():
        raise SimulationRunnerError("M10_14_OUTPUT_DIR", "output path is not a real directory", 73)
    return candidate


def write_json(path: Path, payload: Any, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(mode)
    os.replace(temporary, path)


def write_ledger(path: Path, steps: list[Step]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("step_id", "title", "status", "physical_evidence_claimed", "detail_sha256"),
            lineterminator="\n",
        )
        writer.writeheader()
        for step in steps:
            detail = json.dumps(step.detail, sort_keys=True, separators=(",", ":"))
            writer.writerow(
                {
                    "step_id": step.step_id,
                    "title": step.title,
                    "status": step.status,
                    "physical_evidence_claimed": "false",
                    "detail_sha256": hashlib.sha256(detail.encode("utf-8")).hexdigest(),
                }
            )
    temporary.chmod(0o600)
    os.replace(temporary, path)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise SimulationRunnerError(code, message, 1)


def cli_json(socket_path: Path, *arguments: str, expect_success: bool = True) -> dict[str, Any]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    src = str(ROOT / "src")
    env["PYTHONPATH"] = src if not existing else src + os.pathsep + existing
    command = [
        sys.executable,
        "-m",
        "gonken_agent",
        "env",
        "--socket",
        str(socket_path),
        *arguments,
        "--json",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if expect_success and result.returncode != 0:
        raise SimulationRunnerError(
            "M10_14_CLI_FAILED",
            f"CLI failed ({result.returncode}) for {' '.join(arguments)}: {(result.stderr or result.stdout).strip()[:400]}",
            1,
        )
    stream = result.stdout if result.returncode == 0 else result.stderr
    try:
        payload = json.loads(stream)
    except json.JSONDecodeError as exc:
        raise SimulationRunnerError(
            "M10_14_CLI_JSON",
            f"CLI did not return JSON for {' '.join(arguments)}",
            1,
        ) from exc
    payload["_returncode"] = result.returncode
    return payload


def cli_watch_json(socket_path: Path, *, count: int = 2) -> list[dict[str, Any]]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    src = str(ROOT / "src")
    env["PYTHONPATH"] = src if not existing else src + os.pathsep + existing
    command = [
        sys.executable,
        "-m",
        "gonken_agent",
        "env",
        "--socket",
        str(socket_path),
        "watch",
        "--interval",
        "0",
        "--count",
        str(count),
        "--json",
    ]
    result = subprocess.run(command, cwd=ROOT, env=env, check=False, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise SimulationRunnerError("M10_14_WATCH_FAILED", result.stderr.strip()[:400], 1)
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if line.strip():
            rows.append(json.loads(line))
    require(len(rows) == count, "M10_14_WATCH_COUNT", f"expected {count} watch rows, got {len(rows)}")
    return rows


def run_hybrid_profile_check(work: Path) -> dict[str, Any]:
    site = work / "sensor-deferred-site.toml"
    policy = work / "sensor-deferred-policy.json"
    socket_path = work / "sensor-deferred.sock"
    site.write_text(
        "[extensions.environment]\n"
        "enabled = true\n"
        "sensor_backend = \"simulated\"\n"
        "relay_backend = \"libgpiod\"\n"
        "simulation_runtime_control_enabled = true\n"
        f"socket_path = {json.dumps(str(socket_path))}\n"
        f"policy_path = {json.dumps(str(policy))}\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    src = str(ROOT / "src")
    env["PYTHONPATH"] = src if not existing else src + os.pathsep + existing
    result = subprocess.run(
        [sys.executable, "-m", "gonken_agent", "env", "serve", "--site", str(site), "--check", "--json"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    require(result.returncode == 0, "M10_14_HYBRID_CHECK", result.stderr.strip() or "hybrid profile check failed")
    payload = json.loads(result.stdout)
    daemon = payload.get("daemon", {})
    require(payload.get("hardware_toggled") is False, "M10_14_HYBRID_ACTUATION", "hybrid profile check reported hardware_toggled=true")
    require(payload.get("physical_evidence") is False, "M10_14_HYBRID_PHYSICAL", "hybrid profile check claimed physical evidence")
    require(daemon.get("sensor_backend") == "simulated", "M10_14_HYBRID_SENSOR", "hybrid profile did not select simulated sensor")
    require(daemon.get("actuator_backend") == "libgpiod", "M10_14_HYBRID_ACTUATOR", "hybrid profile did not retain libgpiod actuator")
    require(daemon.get("evidence_mode") == "TARGET_HYBRID_SENSOR_SIMULATED", "M10_14_HYBRID_MODE", "wrong hybrid evidence mode")
    return {
        "code": payload.get("code"),
        "hardware_toggled": payload.get("hardware_toggled"),
        "physical_evidence": payload.get("physical_evidence"),
        "sensor_backend": daemon.get("sensor_backend"),
        "actuator_backend": daemon.get("actuator_backend"),
        "evidence_mode": daemon.get("evidence_mode"),
        "physical_actuation_tested": False,
        "note": "Construction/configuration readiness only; real relay/fan actuation remains target NOT_RUN.",
    }


def run_campaign(output_dir: Path) -> dict[str, Any]:
    # Imports happen only after argument/output validation so --help remains light.
    from gonken_agent.config import load_config
    from gonken_agent.environment import EnvironmentDaemon

    out = safe_output_dir(output_dir)
    steps: list[Step] = []
    with tempfile.TemporaryDirectory(prefix="gonken-m10-14-") as temporary:
        work = Path(temporary)
        socket_path = work / "control.sock"
        policy_path = work / "policy.json"
        effective = load_config(
            site_path=None,
            environ={},
            cli_overrides={
                "extensions.environment.enabled": True,
                "extensions.environment.sensor_backend": "simulated",
                "extensions.environment.relay_backend": "simulated",
                "extensions.environment.simulation_runtime_control_enabled": True,
                "extensions.environment.socket_path": str(socket_path),
                "extensions.environment.policy_path": str(policy_path),
                "extensions.environment.valid_samples_to_recover": 1,
                "extensions.environment.minimum_dwell_seconds": 0,
            },
        )
        daemon = EnvironmentDaemon.from_config(effective.config.extensions.environment)
        thread = threading.Thread(target=daemon.server.serve_forever, daemon=True, name="m10-14-sim-server")
        thread.start()
        deadline = time.monotonic() + 3.0
        while not socket_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        require(socket_path.exists(), "M10_14_SOCKET", "full-simulation AF_UNIX socket did not appear")
        try:
            simulation = cli_json(socket_path, "simulate", "status")
            require(simulation.get("physical_evidence") is False, "M10_14_FALSE_PHYSICAL", "simulation claimed physical evidence")
            provenance = simulation.get("provenance", {})
            require(provenance.get("evidence_mode") == "HOST_SIMULATION", "M10_14_EVIDENCE_MODE", "full simulation evidence mode is not HOST_SIMULATION")
            require(provenance.get("sensor_is_simulated") is True, "M10_14_SENSOR_PROVENANCE", "sensor is not marked simulated")
            require(provenance.get("actuator_is_simulated") is True, "M10_14_ACTUATOR_PROVENANCE", "actuator is not marked simulated")
            steps.append(Step("full_simulation_provenance", "Full-simulation provenance and no-physical-claim boundary", "PASS", {
                "evidence_mode": provenance.get("evidence_mode"),
                "sensor_backend": provenance.get("sensor_backend"),
                "actuator_backend": provenance.get("actuator_backend"),
                "physical_evidence": simulation.get("physical_evidence"),
            }))

            cli_json(socket_path, "mode", "set", "manual")
            on = cli_json(socket_path, "fan", "on")
            off = cli_json(socket_path, "fan", "off")
            require(on.get("state", {}).get("fan_power") == "on", "M10_14_MANUAL_ON", "manual fan ON did not produce simulated power on")
            require(off.get("state", {}).get("fan_power") == "off", "M10_14_MANUAL_OFF", "manual fan OFF did not produce simulated power off")
            steps.append(Step("manual_fan_control", "Manual typed fan ON/OFF through AF_UNIX CLI", "PASS", {
                "on_state": on.get("state", {}).get("fan_power"),
                "off_state": off.get("state", {}).get("fan_power"),
                "physical_evidence": False,
            }))

            cli_json(
                socket_path,
                "policy",
                "set",
                "--mode",
                "automatic",
                "--start-c",
                "28",
                "--stop-c",
                "26.5",
                "--minimum-on-seconds",
                "0",
                "--minimum-off-seconds",
                "0",
            )
            auto_states: list[dict[str, Any]] = []
            for temperature in (27.0, 29.0, 27.0, 26.0, 26.0):
                cli_json(socket_path, "simulate", "sensor", "set", "--temperature-c", str(temperature), "--humidity-pct", "50")
                poll = daemon.poll_once()
                auto_states.append({
                    "temperature_c": temperature,
                    "fan_power": poll.get("state", {}).get("fan_power"),
                    "reason": poll.get("state", {}).get("last_transition_reason"),
                })
            require([row["fan_power"] for row in auto_states] == ["off", "on", "on", "on", "off"], "M10_14_AUTO_SEQUENCE", f"unexpected AUTO power sequence: {auto_states}")
            require(auto_states[1]["reason"] == "AUTO_START_THRESHOLD", "M10_14_AUTO_START_REASON", "AUTO start reason mismatch")
            require(auto_states[4]["reason"] == "AUTO_STOP_THRESHOLD", "M10_14_AUTO_STOP_REASON", "AUTO stop reason mismatch")
            steps.append(Step("automatic_hysteresis_cycle", "Automatic threshold/hysteresis cycle", "PASS", {"sequence": auto_states}))

            cli_json(socket_path, "mode", "set", "semi-automatic")
            cli_json(socket_path, "simulate", "sensor", "set", "--temperature-c", "30", "--humidity-pct", "50")
            before_start = daemon.poll_once()
            require(before_start.get("state", {}).get("fan_power") == "off", "M10_14_SEMI_AUTOSTART", "SEMI auto-started without explicit start")
            started = cli_json(socket_path, "fan", "on")
            require(started.get("state", {}).get("fan_power") == "on", "M10_14_SEMI_MANUAL_START", "SEMI explicit start did not turn simulated power on")
            cli_json(socket_path, "simulate", "sensor", "set", "--temperature-c", "26", "--humidity-pct", "50")
            stopped = daemon.poll_once()
            for _ in range(2):
                if stopped.get("state", {}).get("fan_power") == "off":
                    break
                stopped = daemon.poll_once()
            require(stopped.get("state", {}).get("fan_power") == "off", "M10_14_SEMI_STOP", "SEMI did not auto-stop after the median window reached the stop condition")
            require(stopped.get("state", {}).get("last_transition_reason") == "SEMI_AUTO_STOP", "M10_14_SEMI_REASON", "SEMI auto-stop reason mismatch")
            cli_json(socket_path, "simulate", "sensor", "set", "--temperature-c", "30", "--humidity-pct", "50")
            after_rise = daemon.poll_once()
            require(after_rise.get("state", {}).get("fan_power") == "off", "M10_14_SEMI_RESTART", "SEMI restarted without new explicit start")
            steps.append(Step("semi_automatic_no_autostart", "Semi-automatic explicit-start/auto-stop/no-restart semantics", "PASS", {
                "before_start": before_start.get("state", {}).get("fan_power"),
                "explicit_start": started.get("state", {}).get("fan_power"),
                "stop_reason": stopped.get("state", {}).get("last_transition_reason"),
                "after_temperature_rise": after_rise.get("state", {}).get("fan_power"),
            }))

            cli_json(socket_path, "policy", "set", "--mode", "automatic")
            cli_json(socket_path, "simulate", "sensor", "set", "--temperature-c", "29", "--humidity-pct", "50")
            daemon.poll_once()
            cli_json(socket_path, "simulate", "sensor", "stale", "--age-seconds", "30")
            stale = daemon.poll_once()
            require(stale.get("state", {}).get("fan_power") == "off", "M10_14_STALE_OFF", "stale sensor did not force safe off")
            require(stale.get("state", {}).get("last_transition_reason") == "SENSOR_STALE_SAFE_OFF", "M10_14_STALE_REASON", "stale safe-off reason mismatch")
            cli_json(socket_path, "simulate", "sensor", "recover", "--temperature-c", "27", "--humidity-pct", "50")
            recovered = daemon.poll_once()
            require(recovered.get("state", {}).get("sensor_quality") == "ready", "M10_14_RECOVERY", "simulated sensor did not recover through governed sample path")
            steps.append(Step("sensor_stale_safe_off_recovery", "Sensor staleness safe-off and governed recovery", "PASS", {
                "stale_reason": stale.get("state", {}).get("last_transition_reason"),
                "recovered_quality": recovered.get("state", {}).get("sensor_quality"),
            }))

            before_watch = daemon.server.core.daemon_metadata().get("poll_count")
            watch_rows = cli_watch_json(socket_path, count=2)
            after_watch = daemon.server.core.daemon_metadata().get("poll_count")
            require(before_watch == after_watch, "M10_14_WATCH_OBSERVER", "passive watch changed daemon poll count")
            require(all(row.get("physical_evidence") is False for row in watch_rows), "M10_14_WATCH_PHYSICAL", "watch claimed physical evidence")
            steps.append(Step("passive_watch_no_observer_effect", "Passive watch uses authoritative snapshots without sampling", "PASS", {
                "poll_count_before": before_watch,
                "poll_count_after": after_watch,
                "rows": len(watch_rows),
            }))

            hybrid = run_hybrid_profile_check(work)
            steps.append(Step("sensor_deferred_real_actuator_profile_check", "Sensor-simulated/libgpiod profile validates without actuation", "PASS", hybrid))
        finally:
            daemon.server.shutdown()
            daemon.server.server_close()
            thread.join(timeout=2.0)

    step_ids = {step.step_id for step in steps if step.status == "PASS"}
    missing = sorted(REQUIRED_STEP_IDS - step_ids)
    summary = "PASS" if not missing and all(step.status == "PASS" for step in steps) else "FAIL"
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "created_utc": utc_now(),
        "purpose": "M10.14 deterministic full-simulation and sensor-deferred HIL software-readiness evidence",
        "summary_status": summary,
        "git": git_state(),
        "evidence_mode": "HOST_SIMULATION",
        "test_configuration": {
            "valid_samples_to_recover": 1,
            "minimum_dwell_seconds": 0,
            "note": "Deliberately shortened deterministic host-campaign settings; target/user runs use configured production values.",
        },
        "physical_acceptance_claimed": False,
        "sht31_physical_acceptance": "NOT_RUN",
        "relay_fan_physical_acceptance": "NOT_RUN",
        "sensor_deferred_hil_physical_actuation_tested": False,
        "required_step_ids": sorted(REQUIRED_STEP_IDS),
        "missing_required_steps": missing,
        "steps": [step.as_dict() for step in steps],
        "false_green_boundaries": {
            "host_simulation_is_not_physical_acceptance": True,
            "hybrid_profile_check_is_non_actuating": True,
            "relay_command_does_not_prove_blade_motion": True,
            "software_speed_control": False,
            "fan_motion_observed": False,
        },
        "next_action": "Use docs/RASPBERRY_PI_ACCEPTANCE_RUN.md from the final checkpoint-23 package: verify/install the exact local checkpoint, run full simulation first, then only dependency-ready supervised hybrid/physical gates; keep M10.7 open until real target evidence is uploaded.",
    }
    write_json(out / "m10_14_simulation_manifest.json", manifest)
    write_ledger(out / "m10_14_simulation_ledger.csv", steps)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="new or existing directory for private simulation evidence")
    parser.add_argument("--json", action="store_true", dest="as_json", help="print the manifest to stdout")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = run_campaign(args.output_dir)
    except SimulationRunnerError as exc:
        print(json.dumps({"status": "FAIL", "code": exc.code, "message": str(exc)}, sort_keys=True), file=sys.stderr)
        return exc.exit_code
    if args.as_json:
        print(json.dumps(manifest, sort_keys=True))
    else:
        print(f"[OK] code=M10_14_SIMULATION_EVIDENCE status={manifest['summary_status']} output={args.output_dir}")
        print("[INFO] physical_acceptance_claimed=false")
    return 0 if manifest["summary_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
