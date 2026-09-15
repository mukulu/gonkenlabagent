from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class V09DocumentationHardeningTests(unittest.TestCase):
    def test_v09_documentation_validator_passes(self) -> None:
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "scripts/validate_v09_docs.py", "--json"],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "PASS")
        self.assertGreaterEqual(len(report["checks"]), 40)

    def test_room_environment_docs_are_user_facing_and_boundary_safe(self) -> None:
        required = {
            "docs/HARDWARE_SETUP.md": [
                "not the Raspberry Pi Active Cooler",
                "PENGLIN",
                "ELUTENG",
                "software_speed_control=false",
            ],
            "docs/ENVIRONMENT_CONTROL.md": [
                "The CLI and voice layers are clients of the daemon",
                "env watch` is passive",
                "physical_evidence=false",
            ],
            "docs/SIMULATION.md": [
                "HOST_SIMULATION",
                "TARGET_HYBRID_SENSOR_SIMULATED",
                "TARGET_HYBRID_ACTUATOR_SIMULATED",
                "SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED",
            ],
            "docs/TROUBLESHOOTING.md": [
                "Do not interpret `fan_power=on` as measured blade motion",
                "GonKen",
            ],
        }
        for relative, phrases in required.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                self.assertIn(phrase, text, relative)

    def test_wake_default_examples_are_not_stale(self) -> None:
        for relative in ("README.md", "docs/INSTALLATION.md", "docs/RASPBERRY_PI_ACCEPTANCE_RUN.md", "scripts/install.sh"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("wake_phrase=Hey_Gonken", text, relative)
            self.assertNotIn("say_Hey_Gonken", text, relative)
        self.assertIn("wake_phrase=GonKen", (ROOT / "scripts/install.sh").read_text(encoding="utf-8"))


    def test_executed_simulation_milestones_have_no_stale_planned_rows(self) -> None:
        report = json.loads(subprocess.run(
            [sys.executable, "scripts/validate_v09_docs.py", "--json"],
            cwd=ROOT, check=True, capture_output=True, text=True, timeout=20,
        ).stdout)
        control = [item for item in report["checks"] if str(item["id"]).startswith("control-")]
        self.assertGreaterEqual(len(control), 12)
        self.assertTrue(all(item["status"] == "PASS" for item in control), control)

    def test_ci_t0_invokes_v09_documentation_validator(self) -> None:
        text = (ROOT / "scripts/ci.sh").read_text(encoding="utf-8")
        self.assertIn("validate_v09_docs.py", text)
        self.assertIn("[T0] V09 documentation/evidence boundary", text)


if __name__ == "__main__":
    unittest.main()
