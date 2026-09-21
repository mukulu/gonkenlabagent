"""Report whether the repository can move through internal reliability gates."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import current_state


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "development"
_TARGET_PROBE_SPEC = importlib.util.spec_from_file_location("gonken_release_target_probe", ROOT / "scripts" / "target_probe.py")
if _TARGET_PROBE_SPEC is None or _TARGET_PROBE_SPEC.loader is None:
    raise RuntimeError("cannot load target_probe.py")
TARGET_PROBE = importlib.util.module_from_spec(_TARGET_PROBE_SPEC)
sys.modules[_TARGET_PROBE_SPEC.name] = TARGET_PROBE
_TARGET_PROBE_SPEC.loader.exec_module(TARGET_PROBE)
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
}
TEXT_EXTENSIONS = {
    ".py", ".sh", ".toml", ".md", ".json", ".cfg", ".ini", ".service", ".conf", ".txt"
}
SCAN_ROOTS = ("src", "scripts", "packaging", "requirements", "tests", "config", "README.md", "pyproject.toml", "AGENTS.md")
REQUIRED_TARGET_SHADOW_FIXTURES = (
    {
        "id": "checkpoint34_duplicate_rp1_alias",
        "path": "tests/fixtures/target_probe/checkpoint34_duplicate_rp1_alias_manifest.json",
        "expected_status": "PASS",
        "expected_code": "GPIO_HEADER_RESOLVED",
    },
    {
        "id": "distinct_duplicate_header_fail_closed",
        "path": "tests/fixtures/target_probe/distinct_duplicate_header_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "GPIO_HEADER_UNRESOLVED",
    },
    {
        "id": "capability_ready_audio_identity_release",
        "path": "tests/fixtures/target_probe/capability_ready_audio_identity_release_manifest.json",
        "expected_status": "PASS",
        "expected_code": "TARGET_SHADOW_READY",
    },
    {
        "id": "ambiguous_audio_route_fail_closed",
        "path": "tests/fixtures/target_probe/ambiguous_audio_route_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "AUDIO_ROUTE_UNRESOLVED",
    },
    {
        "id": "ckpt42_20260917_audio_capture_runtime_fail_closed",
        "path": "tests/fixtures/target_probe/ckpt42_20260917_audio_capture_runtime_failure_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "AUDIO_CAPTURE_RUNTIME_UNREADY",
    },
    {
        "id": "ckpt43_20260917_readiness_identity_mismatch_fail_closed",
        "path": "tests/fixtures/target_probe/ckpt43_20260917_readiness_identity_mismatch_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "READINESS_IDENTITY_MISMATCH",
    },
    {
        "id": "missing_service_identity_fail_closed",
        "path": "tests/fixtures/target_probe/missing_service_identity_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "SERVICE_IDENTITY_UNRESOLVED",
    },
    {
        "id": "dirty_release_state_fail_closed",
        "path": "tests/fixtures/target_probe/dirty_release_state_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "RELEASE_STATE_UNSAFE",
    },
    {
        "id": "i2c_sht31_ready_full_real",
        "path": "tests/fixtures/target_probe/i2c_sht31_ready_full_real_manifest.json",
        "expected_status": "PASS",
        "expected_code": "TARGET_SHADOW_READY",
    },
    {
        "id": "i2c_reboot_required_fail_closed",
        "path": "tests/fixtures/target_probe/i2c_reboot_required_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "I2C_REBOOT_REQUIRED",
    },
    {
        "id": "sht31_absent_real_sensor_fail_closed",
        "path": "tests/fixtures/target_probe/sht31_absent_real_sensor_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "I2C_SHT31_UNRESOLVED",
    },
    {
        "id": "environment_full_real_missing_relay_fail_closed",
        "path": "tests/fixtures/target_probe/environment_full_real_missing_relay_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "ENVIRONMENT_PROFILE_UNREADY",
    },
    {
        "id": "environment_full_simulation_safe",
        "path": "tests/fixtures/target_probe/environment_disabled_safe_manifest.json",
        "expected_status": "PASS",
        "expected_code": "TARGET_SHADOW_READY",
    },
    {
        "id": "release_lifecycle_ready",
        "path": "tests/fixtures/target_probe/release_lifecycle_ready_manifest.json",
        "expected_status": "PASS",
        "expected_code": "TARGET_SHADOW_READY",
    },
    {
        "id": "partial_installer_state_fail_closed",
        "path": "tests/fixtures/target_probe/partial_installer_state_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "RELEASE_STATE_UNSAFE",
    },
    {
        "id": "stale_release_temp_fail_closed",
        "path": "tests/fixtures/target_probe/stale_release_temp_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "RELEASE_LIFECYCLE_UNSAFE",
    },
    {
        "id": "corrupt_historical_noncurrent_safe",
        "path": "tests/fixtures/target_probe/corrupt_historical_noncurrent_manifest.json",
        "expected_status": "PASS",
        "expected_code": "TARGET_SHADOW_READY",
    },
    {
        "id": "runtime_authoritative_drift_fail_closed",
        "path": "tests/fixtures/target_probe/runtime_authoritative_drift_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "RELEASE_LIFECYCLE_UNSAFE",
    },
    {
        "id": "support_wrong_release_fail_closed",
        "path": "tests/fixtures/target_probe/support_wrong_release_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "RELEASE_LIFECYCLE_UNSAFE",
    },
    {
        "id": "old_systemd_units_fail_closed",
        "path": "tests/fixtures/target_probe/old_systemd_units_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "SYSTEMD_RUNTIME_UNREADY",
    },
    {
        "id": "service_restart_failure_fail_closed",
        "path": "tests/fixtures/target_probe/service_restart_failure_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "SYSTEMD_RUNTIME_UNREADY",
    },
    {
        "id": "operator_missing_control_group_fail_closed",
        "path": "tests/fixtures/target_probe/operator_missing_control_group_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "OPERATOR_IDENTITY_UNREADY",
    },
    {
        "id": "low_disk_fail_closed",
        "path": "tests/fixtures/target_probe/low_disk_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "RESOURCE_CAPACITY_LOW",
    },
    {
        "id": "interrupted_model_finalization_fail_closed",
        "path": "tests/fixtures/target_probe/interrupted_model_finalization_manifest.json",
        "expected_status": "FAIL",
        "expected_code": "MODEL_FINALIZATION_UNREADY",
    },
)
READY_STATUS = "READY_FOR_TARGET_CAMPAIGN"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    gates = parser.add_mutually_exclusive_group()
    gates.add_argument("--check", action="store_true", help="require all current core host gates before target-candidate qualification")
    gates.add_argument("--validate", action="store_true", help="validate development state and replay integrity; does not require or grant candidate readiness")
    parser.add_argument("--allow-dirty", action="store_true", help="ignore only uncommitted worktree changes, never unfinished blueprint gates")
    args = parser.parse_args(argv)
    report = build_report(allow_dirty=args.allow_dirty)
    if args.as_json:
        print(json.dumps(report, sort_keys=True, indent=2))
    else:
        print(f"Status: {report['status']}")
        print(f"Validation: {report['validation_status']}")
        print(f"Branch: {report['git']['branch']}")
        print(f"Commit: {report['git']['commit']}")
        print(f"Dirty tree: {report['git']['dirty']}")
        print(f"Current core gates remaining: {len(report['current_gates_remaining'])}")
        print(f"Target-shadow fixtures: {len(report['target_shadow_passed'])}/{len(REQUIRED_TARGET_SHADOW_FIXTURES)}")
        print(f"Target gates remaining: {len(report['target_gates_remaining'])}")
        for gate in report['current_gates_remaining'][:12]:
            print(f"- {gate['id']}: {gate['status']} / {gate['title']}")
        print("Physical acceptance claimed: false")
    if args.check:
        return 0 if report['status'] == READY_STATUS else 1
    if args.validate:
        return 0 if report['validation_status'] == 'PASS' else 1
    return 0


def current_gate_state() -> dict:
    try:
        data = json.loads((DOCS / 'CURRENT_GATES.json').read_text(encoding='utf-8'))
        errors = current_state.validate(data, ROOT)
        if errors:
            return {'errors': errors, 'remaining': [], 'target': [], 'completed': [], 'next_action': 'Repair current-state validation.'}
        plan = json.loads((DOCS / 'ATTEMPT03_PLAN.json').read_text(encoding='utf-8'))
        required = {row['id'] for row in plan['slots'] if row['required_before_core_candidate']}
        remaining = [row for row in data['slots'] if row['id'] in required and row['status'] not in {'HOST_VERIFIED', 'TARGET_VERIFIED'}]
        return {'errors': [], 'remaining': remaining,
                'completed': [row['id'] for row in data['slots'] if row['id'] in required and row['status'] in {'HOST_VERIFIED', 'TARGET_VERIFIED'}],
                'target': [row for row in data['slots'] if row['id'].startswith(('47.', '49.')) and row['status'] != 'TARGET_VERIFIED'],
                'next_action': data['next_action']}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {'errors': ['CURRENT_STATE_UNREADABLE:' + type(exc).__name__], 'remaining': [], 'target': [], 'completed': [], 'next_action': 'Recover the current registry and its requirement inventory.'}


def build_report(*, allow_dirty: bool = False) -> dict[str, object]:
    gates = current_gate_state()
    secrets = scan_secrets()
    shadow = target_shadow_results()
    failures = [item for item in shadow if item['status'] != 'PASS']
    git = git_state()
    valid = not (gates['errors'] or secrets or failures or (git['dirty'] and not allow_dirty))
    ready = valid and not gates['remaining']
    return {
        'schema': 2,
        'status': READY_STATUS if ready else 'NOT_READY',
        'validation_status': 'PASS' if valid else 'FAIL',
        'checkpoint_scope': 'Attempt03 current core host program; dedicated display/target campaigns remain separate',
        'git': git,
        'authority': 'docs/development/CURRENT_GATES.json + ATTEMPT03_PLAN.json',
        'state_errors': gates['errors'],
        'current_gates_remaining': gates['remaining'],
        'current_gates_completed': gates['completed'],
        'secret_findings': secrets,
        'target_shadow_passed': [item for item in shadow if item['status'] == 'PASS'],
        'target_shadow_failures': failures,
        'target_gates_remaining': gates['target'],
        'readiness_scope': 'current host requirements plus target-shadow replay; no Raspberry Pi release candidate or physical gate is implied PASS by development validation',
        'physical_acceptance_claimed': False,
        'next_action': ('Qualify the exact archive before any Raspberry Pi target campaign; physical acceptance remains open.' if ready else gates['next_action']),
    }


def target_shadow_results() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for fixture in REQUIRED_TARGET_SHADOW_FIXTURES:
        path = ROOT / fixture["path"]
        result: dict[str, Any] = {
            "id": fixture["id"],
            "path": fixture["path"],
            "status": "FAIL",
            "expected_status": fixture["expected_status"],
            "expected_code": fixture["expected_code"],
            "observed_status": None,
            "observed_code": None,
            "detail": "",
            "elapsed_ms": 0.0,
        }
        if not path.is_file() or path.is_symlink():
            result["detail"] = "fixture_missing"
            results.append(result)
            continue
        started = time.monotonic()
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            payload = TARGET_PROBE.replay_manifest(manifest)
            result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
            result["detail"] = type(exc).__name__
            results.append(result)
            continue
        observed = payload.get("gpio_identity", {}) if isinstance(payload, dict) else {}
        result["observed_status"] = payload.get("status")
        observed_codes = [
            payload.get("code"),
            observed.get("code") if isinstance(observed, dict) else None,
        ]
        for check_name in (
            "privacy_boundary", "audio_duplex", "audio_runtime", "service_identity", "release_state",
            "i2c_sht31", "environment_profile", "operator_identity", "systemd_runtime",
            "release_lifecycle", "resource_capacity", "model_finalization",
            "readiness_identity",
        ):
            check = payload.get(check_name)
            if isinstance(check, dict):
                observed_codes.append(check.get("code"))
        result["observed_code"] = next(
            (code for code in observed_codes if code == fixture["expected_code"]), observed_codes[0]
        )
        if (
            result["observed_status"] == fixture["expected_status"]
            and fixture["expected_code"] in observed_codes
            and payload.get("physical_acceptance_claimed") is False
        ):
            result["status"] = "PASS"
        else:
            result["detail"] = "replay_expectation_mismatch"
        results.append(result)
    return results


def git_state() -> dict[str, object]:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, timeout=15).stdout.strip()
    return {
        "branch": run("branch", "--show-current"),
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(run("status", "--porcelain")),
    }


def scan_secrets() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for item in SCAN_ROOTS:
        path = ROOT / item
        candidates = [path] if path.is_file() else path.rglob("*")
        for candidate in candidates:
            if not candidate.is_file() or candidate.is_symlink() or candidate.suffix not in TEXT_EXTENSIONS:
                continue
            relative = candidate.relative_to(ROOT).as_posix()
            text = candidate.read_text(encoding="utf-8", errors="replace")
            for name, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    findings.append({"file": relative, "pattern": name})
    return findings


if __name__ == "__main__":
    raise SystemExit(main())
