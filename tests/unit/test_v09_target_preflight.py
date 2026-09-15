from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("target_preflight", ROOT / "scripts" / "target_preflight.py")
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = preflight
SPEC.loader.exec_module(preflight)


class TargetPreflightTests(unittest.TestCase):
    def test_optional_i2c_or_smbus_gap_does_not_fail_generic_prerequisite_report(self) -> None:
        required = [preflight.Check("required", True, True, "ok")]
        optional = [preflight.Check("device:i2c-1", False, False, "absent")]
        with patch.object(preflight, "prerequisite_checks", return_value=required + optional):
            report = preflight.build_report("prerequisites", "root")
        self.assertEqual(report["status"], "WARN")
        self.assertEqual(report["required_failures"], [])
        self.assertEqual(report["warnings"], ["device:i2c-1"])

    def test_required_failure_fails_closed(self) -> None:
        with patch.object(preflight, "prerequisite_checks", return_value=[preflight.Check("gpiod", True, False, "missing")]):
            report = preflight.build_report("prerequisites", "root")
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["required_failures"], ["gpiod"])

    def test_atomic_output_is_private_machine_readable_and_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "preflight.json"
            preflight.atomic_json(path, {"format": preflight.FORMAT, "status": "PASS"})
            first = json.loads(path.read_text(encoding="utf-8"))
            mode = path.stat().st_mode & 0o777
            preflight.atomic_json(path, {"format": preflight.FORMAT, "status": "WARN"})
            second = json.loads(path.read_text(encoding="utf-8"))
            leftovers = list(path.parent.glob(f".{path.name}.*"))
        self.assertEqual(first["status"], "PASS")
        self.assertEqual(second["status"], "WARN")
        self.assertEqual(mode, 0o600)
        self.assertEqual(leftovers, [])

    def test_identity_phase_includes_operator_without_granting_raw_gpio_or_i2c(self) -> None:
        calls = []
        def membership(user, groups):
            calls.append((user, tuple(groups)))
            return True, "ok"
        captured = {}
        def control(group, users):
            captured["group"] = group
            captured["users"] = list(users)
            return True, "ok"
        with patch.object(preflight, "_group_membership", side_effect=membership), patch.object(preflight, "_group_contains", side_effect=control):
            report = preflight.build_report("identities", "gonkenlab")
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(calls, [("gonken-agent", ("audio", "gpio")), ("gonken-env", ("gpio", "i2c"))])
        self.assertEqual(captured["group"], "gonken-envctl")
        self.assertEqual(captured["users"], ["gonken-agent", "gonken-env", "gonkenlab"])


if __name__ == "__main__":
    unittest.main()
