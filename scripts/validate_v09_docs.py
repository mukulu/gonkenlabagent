#!/usr/bin/env python3
"""Validate V09 user-facing documentation and evidence-boundary references.

The validator is intentionally deterministic and host-only. It checks that the
M10.13 documentation set exists, documented commands still parse, static
environment config keys are documented, local markdown links resolve, the
GonKen default is documented consistently, and simulation output cannot be
mistaken for physical acceptance.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shlex
import sys
import tomllib
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
# Direct execution sets sys.path[0] to scripts/, not the repository root.
# Add both canonical source roots explicitly so documented-command validation
# never depends on CI-provided PYTHONPATH or ignored/generated build residue.
for import_root in (ROOT, SRC):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

REQUIRED_DOCS = (
    "README.md",
    "docs/HARDWARE_SETUP.md",
    "docs/ENVIRONMENT_CONTROL.md",
    "docs/SIMULATION.md",
    "docs/TROUBLESHOOTING.md",
    "docs/ENVIRONMENT_ACCEPTANCE_RUN.md",
    "docs/RASPBERRY_PI_ACCEPTANCE_RUN.md",
    "docs/OPERATIONS.md",
    "docs/INSTALLATION.md",
    "docs/USER_SIMULATION_HIL_HANDOFF.md",
)

REQUIRED_BOUNDARY_TERMS = {
    "docs/HARDWARE_SETUP.md": (
        "not the Raspberry Pi Active Cooler",
        "software_speed_control=false",
        "fan_motion_observed=false",
        "PENGLIN",
        "ELUTENG",
        "SHT31",
        "KKHMF",
        "physical_evidence=false",
    ),
    "docs/ENVIRONMENT_CONTROL.md": (
        "The CLI and voice layers are clients of the daemon",
        "physical_evidence=false",
        "software_speed_control=false",
        "fan_motion_observed=false",
        "env watch` is passive",
    ),
    "docs/SIMULATION.md": (
        "HOST_SIMULATION",
        "TARGET_HYBRID_SENSOR_SIMULATED",
        "TARGET_HYBRID_ACTUATOR_SIMULATED",
        "SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED",
        "not physical Raspberry Pi acceptance",
    ),
    "docs/TROUBLESHOOTING.md": (
        "SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED",
        "Do not interpret `fan_power=on` as measured blade motion",
        "GonKen",
    ),
    "docs/ENVIRONMENT_ACCEPTANCE_RUN.md": (
        "physical_acceptance_claimed=false",
        "SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED",
        "Exit code 0 means",
    ),
    "docs/USER_SIMULATION_HIL_HANDOFF.md": (
        "READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL",
        "not Raspberry Pi physical acceptance",
        "TARGET_HYBRID_SENSOR_SIMULATED",
        "SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED",
        "Do not actuate",
    ),
    "docs/RASPBERRY_PI_ACCEPTANCE_RUN.md": (
        "--local-checkpoint",
        "READY_FOR_TARGET_ACCEPTANCE",
        "M10.7",
        "not physically accepted",
        "BLOCKED_NO_PREVIOUS_VALIDATED_RELEASE",
    ),
}

DISALLOWED_STALE_DEFAULTS = (
    "wake_phrase=Hey_Gonken",
    "say_Hey_Gonken",
)

LOCAL_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    checks: list[dict[str, object]] = []
    checks.extend(check_required_docs())
    checks.extend(check_local_links())
    checks.extend(check_boundary_terms())
    checks.extend(check_wake_consistency())
    checks.extend(check_environment_config_documented())
    checks.extend(check_documented_commands())
    checks.extend(check_control_plane_consistency())
    ok = all(item["status"] == "PASS" for item in checks)
    report = {
        "schema": "gonken-v09-docs-validation-v1",
        "status": "PASS" if ok else "FAIL",
        "checks": checks,
    }
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for item in checks:
            print(f"[{item['status']}] {item['id']}: {item['message']}")
    return 0 if ok else 1


def check_required_docs() -> list[dict[str, object]]:
    rows = []
    for relative in REQUIRED_DOCS:
        path = ROOT / relative
        rows.append(result(
            f"doc-exists:{relative}",
            path.is_file(),
            f"{relative} exists",
            f"{relative} is missing",
        ))
    return rows


def check_local_links() -> list[dict[str, object]]:
    rows = []
    for relative in REQUIRED_DOCS:
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for target in LOCAL_LINK_RE.findall(text):
            if is_external_link(target):
                continue
            file_part = target.split("#", 1)[0]
            if not file_part:
                continue
            resolved = (path.parent / file_part).resolve(strict=False)
            ok = resolved.exists()
            rows.append(result(
                f"local-link:{relative}:{target}",
                ok,
                f"local link resolves: {relative} -> {target}",
                f"broken local link: {relative} -> {target}",
            ))
    return rows


def check_boundary_terms() -> list[dict[str, object]]:
    rows = []
    for relative, terms in REQUIRED_BOUNDARY_TERMS.items():
        text = (ROOT / relative).read_text(encoding="utf-8") if (ROOT / relative).exists() else ""
        for term in terms:
            rows.append(result(
                f"boundary-term:{relative}:{term}",
                term in text,
                f"required boundary term present in {relative}: {term}",
                f"required boundary term missing from {relative}: {term}",
            ))
    return rows


def check_wake_consistency() -> list[dict[str, object]]:
    rows = []
    defaults = read_toml(ROOT / "config/defaults.toml")
    phrase = defaults.get("extensions", {}).get("wake_word", {}).get("phrase")
    rows.append(result("wake-default-config", phrase == "GonKen", "packaged wake phrase is GonKen", f"packaged wake phrase is {phrase!r}"))
    for relative in ("README.md", "docs/INSTALLATION.md", "docs/RASPBERRY_PI_ACCEPTANCE_RUN.md", "scripts/install.sh"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for stale in DISALLOWED_STALE_DEFAULTS:
            rows.append(result(
                f"wake-stale-default:{relative}:{stale}",
                stale not in text,
                f"{relative} has no stale wake default token {stale}",
                f"{relative} still contains stale wake default token {stale}",
            ))
    return rows


def check_environment_config_documented() -> list[dict[str, object]]:
    rows = []
    defaults = read_toml(ROOT / "config/defaults.toml")
    env = defaults.get("extensions", {}).get("environment", {})
    text = (ROOT / "docs/ENVIRONMENT_CONTROL.md").read_text(encoding="utf-8")
    for key in sorted(env):
        rows.append(result(
            f"env-config-documented:{key}",
            f"`{key}`" in text,
            f"environment config key documented: {key}",
            f"environment config key missing from docs/ENVIRONMENT_CONTROL.md: {key}",
        ))
    return rows


def check_documented_commands() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    command_rows = list(csv.DictReader((ROOT / "docs/development/V09_DOCUMENTED_COMMANDS.csv").open(encoding="utf-8")))
    for row in command_rows:
        doc = row["doc"]
        command = row["command"]
        parser_name = row["parser"]
        text = (ROOT / doc).read_text(encoding="utf-8") if (ROOT / doc).exists() else ""
        rows.append(result(
            f"documented-command-present:{row['id']}",
            command in text,
            f"documented command appears in {doc}: {command}",
            f"documented command missing from {doc}: {command}",
        ))
        try:
            parse_documented_command(command, parser_name)
            rows.append(result(f"documented-command-parses:{row['id']}", True, f"command parses: {command}", ""))
        except Exception as exc:  # pragma: no cover - reported as validation failure
            rows.append(result(f"documented-command-parses:{row['id']}", False, "", f"command does not parse: {command}: {type(exc).__name__}: {exc}"))
    return rows


def check_control_plane_consistency() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    milestones = json.loads((ROOT / "docs/development/MILESTONES.json").read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in milestones.get("milestones", [])}
    matrix = (ROOT / "docs/development/TEST_MATRIX.md").read_text(encoding="utf-8")
    executed = ("M10.9", "M10.10", "M10.11", "M10.12", "M10.13", "M10.14")
    for milestone_id in executed:
        row = by_id.get(milestone_id, {})
        rows.append(result(
            f"control-host-verified:{milestone_id}",
            row.get("software") == "host-verified",
            f"{milestone_id} is host-verified in the milestone ledger",
            f"{milestone_id} is not host-verified in the milestone ledger",
        ))
        stale = re.search(rf"^\| {re.escape(milestone_id)}-P\d+ .*?\| PLANNED / NOT_RUN \|", matrix, re.M)
        rows.append(result(
            f"control-no-stale-plan:{milestone_id}",
            stale is None,
            f"{milestone_id} has no stale PLANNED / NOT_RUN plan rows",
            f"{milestone_id} still has a PLANNED / NOT_RUN row after executed evidence",
        ))
    return rows


def parse_documented_command(command: str, parser_name: str) -> None:
    tokens = shlex.split(command)
    if parser_name == "gonken-cli":
        if not tokens or tokens[0] != "gonken-agent":
            raise ValueError("gonken-cli command must start with gonken-agent")
        from gonken_agent import cli

        cli._build_parser().parse_args(tokens[1:])  # pylint: disable=protected-access
        return
    if parser_name == "environment-runner":
        from scripts import environment_acceptance_runner

        if not tokens or tokens[0] != "environment_acceptance_runner.py":
            raise ValueError("environment-runner command must start with environment_acceptance_runner.py")
        environment_acceptance_runner.build_parser().parse_args(tokens[1:])
        return
    if parser_name == "ci":
        if tokens[:1] != ["./scripts/ci.sh"]:
            raise ValueError("ci command must start with ./scripts/ci.sh")
        allowed = {"t0", "unit", "integration", "release-lifecycle", "all"}
        iterator = iter(tokens[1:])
        for token in iterator:
            if token == "--phase":
                phase = next(iterator)
                if phase not in allowed:
                    raise ValueError(f"unknown phase {phase}")
            elif token in {"--list-phases", "--help", "-h"}:
                pass
            else:
                raise ValueError(f"unknown ci argument {token}")
        return
    if parser_name == "bootstrap":
        if tokens[:1] != ["./bootstrap.sh"]:
            raise ValueError("bootstrap command must start with ./bootstrap.sh")
        allowed_flags = {"--local-checkpoint", "--preflight-only", "--development-host", "--bluetooth-audio", "--help", "-h"}
        value_flags = {"--bluetooth-device", "--source-url", "--ref", "--existing-checkout", "--staging-parent"}
        iterator = iter(tokens[1:])
        for token in iterator:
            if token in allowed_flags:
                continue
            if token in value_flags:
                next(iterator)
                continue
            raise ValueError(f"unknown bootstrap argument {token}")
        return
    raise ValueError(f"unknown parser {parser_name}")


def is_external_link(target: str) -> bool:
    lowered = target.lower()
    return lowered.startswith(("http://", "https://", "mailto:", "tel:"))


def read_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def result(identifier: str, ok: bool, ok_message: str, fail_message: str) -> dict[str, object]:
    return {"id": identifier, "status": "PASS" if ok else "FAIL", "message": ok_message if ok else fail_message}


if __name__ == "__main__":
    raise SystemExit(main())
