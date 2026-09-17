import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import release_readiness


ROOT = Path(__file__).resolve().parents[2]


class ReleaseReadinessTests(unittest.TestCase):
    def test_report_is_ready_for_target_acceptance_from_clean_tree(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/release_readiness.py", "--json", "--allow-dirty"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "READY_FOR_HOST_TARGET_SHADOW_GATE")
        self.assertFalse(report["secret_findings"])
        self.assertFalse(report["missing_milestones"])
        self.assertFalse(report["not_host_verified"])
        self.assertEqual(len(report["target_shadow_passed"]), 22)
        self.assertFalse(report["target_shadow_failures"])
        remaining = {gate["id"] for gate in report["target_gates_remaining"]}
        self.assertIn("M9.1", remaining)
        self.assertIn("M10.7", remaining)
        self.assertIn("M10.24", remaining)
        self.assertIn("M10.30", report["host_verified"])
        self.assertIn("M10.31", report["host_verified"])
        self.assertIn("M10.32", report["host_verified"])
        self.assertIn("M10.33", report["host_verified"])
        self.assertIn("M10.34", report["host_verified"])
        self.assertIn("M10.35", report["host_verified"])
        self.assertIn("M10.36", report["host_verified"])
        self.assertIn("M10.26", report["host_verified"])
        self.assertIn("M10.28", report["host_verified"])
        self.assertFalse(report["physical_acceptance_claimed"])
        self.assertIn("target-shadow", report["readiness_scope"])
        self.assertIn("no Raspberry Pi release candidate", report["readiness_scope"])
        self.assertIn("./bootstrap.sh --local-checkpoint", report["next_action"])
        self.assertIn("docs/RASPBERRY_PI_ACCEPTANCE_RUN.md", report["next_action"])
        self.assertIn("M10.7", report["next_action"])
        self.assertIn("M10.24", report["next_action"])
        self.assertIn("INSTALLATION_COMPLETE", report["next_action"])
        self.assertIn("target_probe.py", report["next_action"])

    def test_human_report_has_exact_boundary_language(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/release_readiness.py", "--allow-dirty"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Status: READY_FOR_HOST_TARGET_SHADOW_GATE", result.stdout)
        self.assertIn("Target-shadow fixtures: 22/22", result.stdout)
        self.assertIn("Target gates remaining:", result.stdout)

    def test_target_shadow_fixture_failure_blocks_readiness(self) -> None:
        bad_shadow = [{
            "id": "fixture",
            "status": "FAIL",
            "path": "tests/fixtures/target_probe/missing.json",
            "detail": "fixture_missing",
        }]
        with patch.object(release_readiness, "target_shadow_results", return_value=bad_shadow):
            report = release_readiness.build_report()
        self.assertEqual(report["status"], "NOT_READY")
        self.assertTrue(report["target_shadow_failures"])

    def test_target_acceptance_runbook_is_user_facing(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        runbook = (ROOT / "docs" / "RASPBERRY_PI_ACCEPTANCE_RUN.md").read_text(encoding="utf-8")
        self.assertIn("docs/RASPBERRY_PI_ACCEPTANCE_RUN.md", readme)
        for expected in (
            "./bootstrap.sh --local-checkpoint",
            "sha256sum -c <delivered-sha256-manifest>",
            "git reset --hard HEAD",
            "test -x ./bootstrap.sh",
            "gpioinfo --strict GPIO17",
            "gpioinfo --strict GPIO22",
            "gpioinfo --strict GPIO23",
            "gpioinfo --strict GPIO27",
            "collect-support.sh",
            "journalctl -u gonken-agent.service",
            "sudo reboot",
            "update.sh",
            "rollback.sh",
            "uninstall.sh",
            "BLOCKED_NO_PREVIOUS_VALIDATED_RELEASE",
        ):
            self.assertIn(expected, runbook)


if __name__ == "__main__":
    unittest.main()
