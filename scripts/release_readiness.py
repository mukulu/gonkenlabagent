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


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "development"
_TARGET_PROBE_SPEC = importlib.util.spec_from_file_location("gonken_release_target_probe", ROOT / "scripts" / "target_probe.py")
if _TARGET_PROBE_SPEC is None or _TARGET_PROBE_SPEC.loader is None:
    raise RuntimeError("cannot load target_probe.py")
TARGET_PROBE = importlib.util.module_from_spec(_TARGET_PROBE_SPEC)
sys.modules[_TARGET_PROBE_SPEC.name] = TARGET_PROBE
_TARGET_PROBE_SPEC.loader.exec_module(TARGET_PROBE)
REQUIRED_HOST_VERIFIED = {
    "M2.1", "M2.2", "M2.3", "M2.4",
    "M3.1", "M3.2", "M3.3", "M3.4", "M3.5", "M3.6",
    "M4.1", "M4.2", "M4.3",
    "M5.1", "M5.2",
    "M6.1", "M6.2",
    # M7.1/M7.2/M7.5 intentionally remain evaluation gates because they require
    # the real lab corpus/model/benchmark campaign.  Core privacy/dashboard
    # software must nevertheless be host-verified before target handoff.
    "M7.3", "M7.4",
    "M8.1", "M8.2", "M8.3",
    "M9.2", "M9.3", "M9.4", "M9.5",
    "M10.1", "M10.2", "M10.3", "M10.4", "M10.5", "M10.6",
    "M10.8", "M10.9", "M10.10", "M10.11", "M10.12", "M10.13", "M10.14", "M10.15",
    "M10.16", "M10.17", "M10.18", "M10.19", "M10.20", "M10.21", "M10.22", "M10.23", "M10.25", "M10.26", "M10.27", "M10.28", "M10.29", "M10.30", "M10.31", "M10.32", "M10.33", "M10.34", "M10.35", "M10.36", "M10.37", "M10.38", "M10.39", "M10.40",
}
TARGET_CAMPAIGN_ITEMS = {
    "M3.1", "M3.2", "M3.3", "M3.4", "M3.5", "M3.6",
    "M4.1", "M4.2", "M4.3",
    "M5.1", "M5.2",
    "M6.1", "M6.2",
    "M7.1", "M7.2", "M7.3", "M7.4", "M7.5",
    "M8.1", "M8.2", "M8.3", "M9.1", "M9.2", "M9.3",
    "M10.7", "M10.24",
}
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--check", action="store_true", help="exit nonzero unless the host/target-shadow gate is ready")
    parser.add_argument("--allow-dirty", action="store_true", help="ignore only uncommitted worktree changes")
    args = parser.parse_args()
    report = build_report()
    if (
        args.allow_dirty
        and report["git"]["dirty"]
        and not report["missing_milestones"]
        and not report["not_host_verified"]
        and not report["secret_findings"]
        and not report["target_shadow_failures"]
    ):
        report = {**report, "status": READY_STATUS}
    if args.as_json:
        print(json.dumps(report, sort_keys=True, indent=2))
    else:
        print(f"Status: {report['status']}")
        print(f"Branch: {report['git']['branch']}")
        print(f"Commit: {report['git']['commit']}")
        print(f"Dirty tree: {report['git']['dirty']}")
        print(f"Host verified required items: {len(report['host_verified'])}/{len(REQUIRED_HOST_VERIFIED)}")
        print(f"Target-shadow fixtures: {len(report['target_shadow_passed'])}/{len(REQUIRED_TARGET_SHADOW_FIXTURES)}")
        print(f"Target gates remaining: {len(report['target_gates_remaining'])}")
        for gate in report["target_gates_remaining"][:12]:
            print(f"- {gate['id']}: {gate['title']}")
    if args.check and report["status"] != READY_STATUS:
        return 1
    return 0


def build_report() -> dict[str, object]:
    milestones = json.loads((DOCS / "MILESTONES.json").read_text(encoding="utf-8"))
    rows = milestones["milestones"]
    by_id = {row["id"]: row for row in rows}
    missing = sorted(REQUIRED_HOST_VERIFIED - set(by_id))
    not_host_verified = sorted(
        item for item in REQUIRED_HOST_VERIFIED
        if item in by_id and by_id[item]["software"] != "host-verified"
    )
    target_gates = [
        {
            "id": row["id"],
            "title": row["title"],
            "target": row["target"],
            "remaining": row["remaining"],
        }
        for row in rows
        if row["id"] in TARGET_CAMPAIGN_ITEMS and row["target"] == "not-run"
    ]
    secrets = scan_secrets()
    target_shadow = target_shadow_results()
    target_shadow_failures = [item for item in target_shadow if item["status"] != "PASS"]
    git = git_state()
    status = READY_STATUS
    if missing or not_host_verified or secrets or git["dirty"] or target_shadow_failures:
        status = "NOT_READY"
    return {
        "schema": 1,
        "status": status,
        "checkpoint_scope": milestones["checkpoint_scope"],
        "git": git,
        "host_verified": sorted(REQUIRED_HOST_VERIFIED - set(not_host_verified) - set(missing)),
        "missing_milestones": missing,
        "not_host_verified": not_host_verified,
        "secret_findings": secrets,
        "target_shadow_passed": [item for item in target_shadow if item["status"] == "PASS"],
        "target_shadow_failures": target_shadow_failures,
        "target_gates_remaining": target_gates,
        "readiness_scope": "host/software plus required target-shadow replay gate; no Raspberry Pi release candidate or target gate is implied PASS",
        "physical_acceptance_claimed": False,
        "next_action": (
            "Host/software and required target-shadow replay gates are ready. Qualify the exact tagged archive, then on the Raspberry Pi run target_probe.py before installation and install that exact archive with "
            "./bootstrap.sh --local-checkpoint --environment-profile real-sensor-simulated-actuator --sensor-address 0x44. Require INSTALLATION_COMPLETE, verify the governed three-model roster and active model, "
            "exercise local time/date plus real-SHT31/simulated-fan tool transactions, measure latency/resource behavior, and verify reboot/no-login/model-selection persistence. "
            "Do not enable real GPIO23/ELUTENG actuation until the separately supervised WP-45C gate, and do not mark physical acceptance PASS from host or replay evidence."
        ),
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
        return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
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
