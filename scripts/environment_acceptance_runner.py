#!/usr/bin/env python3
"""Collect private M10.7 room-environment acceptance evidence on a target Pi.

The runner is an evidence collector, not an acceptance oracle.  It records
bounded command results and manual gates into a private output directory.  It
never claims physical acceptance by itself, and it does not actuate the room fan
unless ``--allow-actuation`` is explicitly supplied.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "gonken-m10.7-environment-evidence-v1"
MAX_TEXT = 8192
STATUS_ORDER = {"FAIL": 0, "BLOCKED": 1, "NEEDS_MANUAL_REVIEW": 2, "NOT_RUN": 3, "PASS": 4}


class AcceptanceRunnerError(RuntimeError):
    def __init__(self, code: str, message: str, exit_code: int = 74) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    missing_tool: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "duration_seconds": round(self.duration_seconds, 6),
            "timed_out": self.timed_out,
            "missing_tool": self.missing_tool,
            "stdout_excerpt": truncate_text(self.stdout),
            "stderr_excerpt": truncate_text(self.stderr),
        }


def truncate_text(value: str, limit: int = MAX_TEXT) -> str:
    clean = value.replace("\r", "")
    if len(clean) <= limit:
        return clean
    digest = hashlib.sha256(clean.encode("utf-8", errors="replace")).hexdigest()
    return clean[:limit] + f"\n[truncated sha256={digest}]"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_output_dir(path: Path) -> Path:
    candidate = path.expanduser().resolve(strict=False)
    if str(candidate) == "/" or "\n" in str(candidate) or "\r" in str(candidate):
        raise AcceptanceRunnerError("M10_7_OUTPUT_DIR", "unsafe output directory", 64)
    if candidate.exists() and candidate.is_symlink():
        raise AcceptanceRunnerError("M10_7_OUTPUT_DIR", "output directory is a symlink", 73)
    candidate.mkdir(parents=True, exist_ok=True)
    if not candidate.is_dir() or candidate.is_symlink():
        raise AcceptanceRunnerError("M10_7_OUTPUT_DIR", "output path is not a real directory", 73)
    return candidate


def repo_git_state() -> dict[str, object]:
    def run_git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, check=False, capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return "unknown"
        return result.stdout.strip() or "unknown"

    return {
        "branch": run_git("branch", "--show-current"),
        "commit": run_git("rev-parse", "HEAD"),
        "dirty": bool(run_git("status", "--porcelain")),
    }


def platform_identity() -> dict[str, object]:
    model = "unknown"
    model_path = Path("/proc/device-tree/model")
    try:
        if model_path.is_file():
            model = model_path.read_text(encoding="utf-8", errors="replace").strip("\x00\n ")
    except OSError:
        model = "unreadable"
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "raspberry_pi_model": model,
    }


class CommandRunner:
    def __init__(self, *, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, command: Sequence[str]) -> CommandResult:
        started = time.monotonic()
        try:
            result = subprocess.run(
                list(command), check=False, capture_output=True, text=True, timeout=self.timeout_seconds
            )
            return CommandResult(
                command=list(command),
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=time.monotonic() - started,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=list(command),
                returncode=None,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                duration_seconds=time.monotonic() - started,
                timed_out=True,
            )
        except FileNotFoundError:
            return CommandResult(
                command=list(command),
                returncode=None,
                stdout="",
                stderr="tool not found",
                duration_seconds=time.monotonic() - started,
                missing_tool=True,
            )


@dataclass(frozen=True, slots=True)
class StepSpec:
    step_id: str
    title: str
    evidence_tier: str
    command: tuple[str, ...] | None = None
    target_required: bool = True
    actuation: str = "none"
    manual_gate: bool = False
    notes: str = ""


def non_destructive_steps(gonken_agent: str, systemctl: str, journalctl: str) -> list[StepSpec]:
    return [
        StepSpec(
            "m10_7_platform_identity",
            "Target platform identity recorded",
            "E3",
            None,
            notes="Records OS/Python/host metadata from the runner process.",
        ),
        StepSpec(
            "m10_7_voice_service_active",
            "Voice service active state",
            "E3",
            (systemctl, "is-active", "gonken-agent.service"),
        ),
        StepSpec(
            "m10_7_environment_service_active",
            "Environment service active state",
            "E3",
            (systemctl, "is-active", "gonken-environment.service"),
        ),
        StepSpec(
            "m10_7_environment_service_enabled",
            "Environment service enabled state",
            "E3",
            (systemctl, "is-enabled", "gonken-environment.service"),
        ),
        StepSpec(
            "m10_7_agent_status_json",
            "Agent status JSON",
            "E3",
            (gonken_agent, "status", "--json"),
        ),
        StepSpec(
            "m10_7_env_status_json",
            "Environment status JSON",
            "E3",
            (gonken_agent, "env", "status", "--json"),
        ),
        StepSpec(
            "m10_7_env_health_json",
            "Environment health JSON",
            "E3",
            (gonken_agent, "env", "health", "--json"),
        ),
        StepSpec(
            "m10_7_env_read_json",
            "Environment sensor read JSON",
            "E4",
            (gonken_agent, "env", "read", "--json"),
            notes="Can support SHT31 evidence only when run on the accepted Pi wiring; host output is not physical acceptance.",
        ),
        StepSpec(
            "m10_7_env_probe_json",
            "Non-destructive environment probe JSON",
            "E4",
            (gonken_agent, "env", "probe", "--json"),
            notes="Probe must remain non-destructive and must not toggle the relay.",
        ),
        StepSpec(
            "m10_7_voice_service_recent_journal",
            "Voice service recent journal excerpt",
            "E3",
            (journalctl, "-u", "gonken-agent.service", "-b", "--no-pager", "-n", "80"),
        ),
        StepSpec(
            "m10_7_environment_service_recent_journal",
            "Environment service recent journal excerpt",
            "E3",
            (journalctl, "-u", "gonken-environment.service", "-b", "--no-pager", "-n", "80"),
        ),
    ]


def manual_steps() -> list[StepSpec]:
    return [
        StepSpec(
            "m10_7_physical_wiring_inspection",
            "Power-off wiring, polarity, COM/NO and placement inspection",
            "E4",
            None,
            manual_gate=True,
            notes="A supervised person must inspect SHT31 placement, relay input/output wiring and PENGLIN USB polarity before actuation.",
        ),
        StepSpec(
            "m10_7_reboot_no_login_manual",
            "Reboot/no-login convergence",
            "E5",
            None,
            manual_gate=True,
            notes="Requires real reboot and observation that services converge without interactive login.",
        ),
        StepSpec(
            "m10_7_wake_phrase_manual",
            "Wake phrase and spoken environment actions",
            "E4",
            None,
            manual_gate=True,
            notes="Requires supervised voice/audio evidence. This runner does not persist transcripts.",
        ),
    ]


def actuation_steps(gonken_agent: str) -> list[StepSpec]:
    return [
        StepSpec(
            "m10_7_fan_safe_off_before_cycle",
            "Fan relay power safe-off before cycle",
            "E4",
            (gonken_agent, "env", "fan", "off", "--json"),
            actuation="fan_power_off",
        ),
        StepSpec(
            "m10_7_fan_manual_on_cycle",
            "Fan relay power manual ON cycle",
            "E4",
            (gonken_agent, "env", "fan", "on", "--json"),
            actuation="fan_power_on",
            notes="A person must observe relay/fan behavior; JSON alone cannot prove blade motion.",
        ),
        StepSpec(
            "m10_7_fan_safe_off_after_cycle",
            "Fan relay power safe-off after cycle",
            "E4",
            (gonken_agent, "env", "fan", "off", "--json"),
            actuation="fan_power_off",
        ),
    ]


def make_step_payload(
    spec: StepSpec,
    *,
    status: str,
    execution_state: str,
    run_id: str,
    command_result: CommandResult | None = None,
    parsed_json: object | None = None,
    notes: Iterable[str] = (),
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "run_id": run_id,
        "step_id": spec.step_id,
        "title": spec.title,
        "evidence_tier": spec.evidence_tier,
        "status": status,
        "execution_state": execution_state,
        "target_required": spec.target_required,
        "physical_evidence_claimed": False,
        "actuation": spec.actuation,
        "manual_gate": spec.manual_gate,
        "observed_utc": utc_now(),
        "notes": [item for item in (spec.notes, *notes) if item],
    }
    if command_result is not None:
        payload["command_result"] = command_result.as_dict()
    if parsed_json is not None:
        payload["parsed_json"] = parsed_json
    return payload


def classify_command(result: CommandResult) -> tuple[str, str, object | None, list[str]]:
    notes: list[str] = []
    parsed: object | None = None
    if result.missing_tool:
        return "BLOCKED", "BLOCKED", None, ["Required tool was not found on this host."]
    if result.timed_out:
        return "FAIL", "TIMEOUT", None, ["Command exceeded the bounded timeout."]
    if result.stdout.strip().startswith("{") or result.stdout.strip().startswith("["):
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError:
            notes.append("Command looked like JSON but could not be parsed.")
            if result.returncode == 0:
                return "NEEDS_MANUAL_REVIEW", "COMPLETED", None, notes
    if result.returncode == 0:
        return "PASS", "COMPLETED", parsed, notes
    return "FAIL", "COMPLETED", parsed, notes


def write_json(path: Path, payload: object, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(mode)
    os.replace(temporary, path)


def write_ledger(path: Path, rows: list[dict[str, object]]) -> None:
    fields = [
        "step_id",
        "title",
        "evidence_tier",
        "status",
        "execution_state",
        "target_required",
        "actuation",
        "physical_evidence_claimed",
        "file",
        "notes",
    ]
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})
    temporary.chmod(0o600)
    os.replace(temporary, path)


def aggregate_status(statuses: Iterable[str]) -> str:
    ordered = list(statuses)
    if not ordered:
        return "NOT_RUN"
    if any(status == "FAIL" for status in ordered):
        return "FAIL"
    if any(status == "BLOCKED" for status in ordered):
        return "BLOCKED"
    if any(status == "NEEDS_MANUAL_REVIEW" for status in ordered):
        return "NEEDS_MANUAL_REVIEW"
    if all(status == "PASS" for status in ordered):
        return "PASS"
    return min(ordered, key=lambda item: STATUS_ORDER.get(item, 99))


def command_specs(args: argparse.Namespace) -> tuple[list[StepSpec], list[StepSpec]]:
    required = non_destructive_steps(str(args.gonken_agent), str(args.systemctl), str(args.journalctl))
    manual = manual_steps()
    actuation = actuation_steps(str(args.gonken_agent))
    if args.allow_actuation:
        required.extend(actuation)
    else:
        manual.append(
            StepSpec(
                "m10_7_fan_manual_cycle_blocked",
                "Fan manual ON/OFF cycle requires explicit actuation opt-in",
                "E4",
                None,
                actuation="blocked_without_allow_actuation",
                manual_gate=True,
                notes="Rerun with --allow-actuation only after power-off wiring inspection and physical supervision.",
            )
        )
    return required, manual


def run_collection(args: argparse.Namespace) -> dict[str, object]:
    out = safe_output_dir(args.output_dir)
    private = out / "private_evidence"
    private.mkdir(exist_ok=True)
    run_id = args.run_id or datetime.now(timezone.utc).strftime("m10_7_%Y%m%dT%H%M%SZ")
    runner = CommandRunner(timeout_seconds=args.timeout_seconds)
    command_steps, gates = command_specs(args)
    rows: list[dict[str, object]] = []
    statuses: list[str] = []

    manifest: dict[str, object] = {
        "schema": SCHEMA,
        "run_id": run_id,
        "created_utc": utc_now(),
        "purpose": "M10.7 private Raspberry Pi room-environment acceptance evidence collection",
        "output_directory": str(out),
        "physical_acceptance_claimed": False,
        "host_output_may_not_substitute_for_physical_acceptance": True,
        "allow_actuation": bool(args.allow_actuation),
        "plan_only": bool(args.plan_only),
        "git": repo_git_state(),
        "platform": platform_identity(),
        "tools": {
            "gonken_agent": str(args.gonken_agent),
            "systemctl": str(args.systemctl),
            "journalctl": str(args.journalctl),
        },
    }

    for spec in command_steps:
        if args.plan_only:
            payload = make_step_payload(
                spec,
                status="NOT_RUN",
                execution_state="NOT_STARTED",
                run_id=run_id,
                notes=["Plan-only mode: command was not executed."],
            )
        elif spec.step_id == "m10_7_platform_identity":
            payload = make_step_payload(
                spec,
                status="PASS",
                execution_state="COMPLETED",
                run_id=run_id,
                parsed_json=manifest["platform"],
            )
        else:
            assert spec.command is not None
            result = runner.run(spec.command)
            status, state, parsed, notes = classify_command(result)
            payload = make_step_payload(
                spec,
                status=status,
                execution_state=state,
                run_id=run_id,
                command_result=result,
                parsed_json=parsed,
                notes=notes,
            )
        file_name = f"{spec.step_id}.json"
        write_json(private / file_name, payload)
        rows.append(row_for_step(payload, file_name))
        statuses.append(str(payload["status"]))

    for spec in gates:
        status = "NEEDS_MANUAL_REVIEW" if spec.step_id != "m10_7_fan_manual_cycle_blocked" else "BLOCKED"
        state = "BLOCKED" if status == "BLOCKED" else "NOT_STARTED"
        payload = make_step_payload(spec, status=status, execution_state=state, run_id=run_id)
        file_name = f"{spec.step_id}.json"
        write_json(private / file_name, payload)
        rows.append(row_for_step(payload, file_name))
        statuses.append(str(payload["status"]))

    manifest["summary_status"] = aggregate_status(statuses)
    manifest["step_count"] = len(rows)
    manifest["status_counts"] = {status: statuses.count(status) for status in sorted(set(statuses))}
    manifest["private_evidence_directory"] = str(private)
    manifest["ledger_csv"] = str(out / "m10_7_private_evidence_ledger.csv")
    write_json(out / "m10_7_evidence_manifest.json", manifest)
    write_ledger(out / "m10_7_private_evidence_ledger.csv", rows)
    return manifest


def row_for_step(payload: dict[str, object], file_name: str) -> dict[str, object]:
    notes = payload.get("notes", [])
    if isinstance(notes, list):
        note_text = " | ".join(str(item) for item in notes if item)
    else:
        note_text = str(notes)
    return {
        "step_id": payload["step_id"],
        "title": payload["title"],
        "evidence_tier": payload["evidence_tier"],
        "status": payload["status"],
        "execution_state": payload["execution_state"],
        "target_required": payload["target_required"],
        "actuation": payload["actuation"],
        "physical_evidence_claimed": payload["physical_evidence_claimed"],
        "file": f"private_evidence/{file_name}",
        "notes": note_text,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="private evidence output directory")
    parser.add_argument("--run-id", help="stable run identifier; default UTC timestamp")
    parser.add_argument("--timeout-seconds", type=float, default=15.0, help="per-command timeout")
    parser.add_argument("--gonken-agent", default="gonken-agent", help="gonken-agent executable path")
    parser.add_argument("--systemctl", default="/usr/bin/systemctl", help="systemctl path")
    parser.add_argument("--journalctl", default="/usr/bin/journalctl", help="journalctl path")
    parser.add_argument("--plan-only", action="store_true", help="write planned evidence files without executing commands")
    parser.add_argument("--allow-actuation", action="store_true", help="run explicit fan ON/OFF commands under physical supervision")
    parser.add_argument("--json", action="store_true", dest="as_json", help="print machine-readable manifest summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    try:
        manifest = run_collection(args)
    except AcceptanceRunnerError as exc:
        payload = {"status": "FAILED", "code": exc.code, "message": str(exc)}
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        return exc.exit_code
    if args.as_json:
        print(json.dumps(manifest, sort_keys=True))
    else:
        print(f"[OK] code=M10_7_EVIDENCE_COLLECTED status={manifest['summary_status']} output={manifest['output_directory']}")
        print("[INFO] physical_acceptance_claimed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
