from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class V09UserTestReleaseCandidateIntegrationTests(unittest.TestCase):
    def test_full_simulation_runner_and_release_gate(self) -> None:
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "simulation-evidence"
            run = subprocess.run(
                [
                    sys.executable,
                    "scripts/environment_simulation_runner.py",
                    "--output-dir",
                    str(output),
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            manifest_path = output / "m10_14_simulation_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["summary_status"], "PASS")
            self.assertFalse(manifest["physical_acceptance_claimed"])
            self.assertEqual(manifest["evidence_mode"], "HOST_SIMULATION")
            hybrid = next(
                step for step in manifest["steps"]
                if step["step_id"] == "sensor_deferred_real_actuator_profile_check"
            )
            self.assertFalse(hybrid["detail"]["hardware_toggled"])
            self.assertFalse(hybrid["detail"]["physical_actuation_tested"])
            self.assertEqual(hybrid["detail"]["evidence_mode"], "TARGET_HYBRID_SENSOR_SIMULATED")

            gate = subprocess.run(
                [
                    sys.executable,
                    "scripts/v09_user_test_readiness.py",
                    "--simulation-manifest",
                    str(manifest_path),
                    "--allow-dirty",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(gate.returncode, 0, gate.stderr + gate.stdout)
            report = json.loads(gate.stdout)
            self.assertEqual(report["status"], "DEVELOPMENT_HOST_SIMULATION_VERIFIED")
            self.assertTrue(report["development_dirty_override"])
            self.assertFalse(report["physical_acceptance_claimed"])
            self.assertEqual(report["m10_7_physical_acceptance"], "NOT_RUN")
            self.assertEqual(report["sht31_physical_acceptance"], "NOT_RUN")
            self.assertEqual(report["relay_penglin_fan_physical_acceptance"], "NOT_RUN")

            strict_gate = subprocess.run(
                [
                    sys.executable,
                    "scripts/v09_user_test_readiness.py",
                    "--simulation-manifest",
                    str(manifest_path),
                    "--allow-dirty",
                    "--check",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(strict_gate.returncode, 1, strict_gate.stderr + strict_gate.stdout)
            strict_report = json.loads(strict_gate.stdout)
            self.assertEqual(
                strict_report["status"],
                "DEVELOPMENT_HOST_SIMULATION_VERIFIED",
            )
            self.assertTrue(strict_report["development_dirty_override"])


if __name__ == "__main__":
    unittest.main()
