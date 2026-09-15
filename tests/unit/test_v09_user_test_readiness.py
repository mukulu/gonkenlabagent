from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "v09_user_test_readiness.py"
SPEC = importlib.util.spec_from_file_location("v09_user_test_readiness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
readiness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(readiness)


def valid_manifest(commit: str) -> dict[str, object]:
    return {
        "schema": readiness.SIM_SCHEMA,
        "summary_status": "PASS",
        "physical_acceptance_claimed": False,
        "evidence_mode": "HOST_SIMULATION",
        "sht31_physical_acceptance": "NOT_RUN",
        "relay_fan_physical_acceptance": "NOT_RUN",
        "sensor_deferred_hil_physical_actuation_tested": False,
        "git": {"commit": commit, "dirty": False},
        "steps": [
            {
                "step_id": step,
                "status": "PASS",
                "physical_evidence_claimed": False,
            }
            for step in sorted(readiness.REQUIRED_SIM_STEPS)
        ],
    }


class UserTestReadinessValidationTests(unittest.TestCase):
    def test_valid_simulation_manifest_keeps_physical_gates_open(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(valid_manifest("abc123")), encoding="utf-8")
            errors, payload = readiness.validate_simulation_manifest(path, current_commit="abc123")
        self.assertEqual(errors, [])
        self.assertFalse(payload["physical_acceptance_claimed"])
        self.assertEqual(payload["sht31_physical_acceptance"], "NOT_RUN")
        self.assertEqual(payload["relay_fan_physical_acceptance"], "NOT_RUN")

    def test_false_physical_claim_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            payload = valid_manifest("abc123")
            payload["physical_acceptance_claimed"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            errors, _ = readiness.validate_simulation_manifest(path, current_commit="abc123")
        self.assertTrue(any("must not claim physical acceptance" in item for item in errors))

    def test_missing_required_simulation_step_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            payload = valid_manifest("abc123")
            payload["steps"] = payload["steps"][:-1]
            path.write_text(json.dumps(payload), encoding="utf-8")
            errors, _ = readiness.validate_simulation_manifest(path, current_commit="abc123")
        self.assertTrue(any("missing required PASS steps" in item for item in errors))


    def test_unknown_manifest_commit_is_rejected_when_repository_commit_is_known(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(valid_manifest("unknown")), encoding="utf-8")
            errors, _ = readiness.validate_simulation_manifest(path, current_commit="abc123")
        self.assertTrue(any("does not match current repository HEAD" in item for item in errors))

    def test_wrong_commit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(valid_manifest("oldcommit")), encoding="utf-8")
            errors, _ = readiness.validate_simulation_manifest(path, current_commit="newcommit")
        self.assertTrue(any("does not match current repository HEAD" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
