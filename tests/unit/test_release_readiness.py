import json
import subprocess
import sys
import unittest
from pathlib import Path


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
        self.assertEqual(report["status"], "READY_FOR_TARGET_ACCEPTANCE")
        self.assertFalse(report["secret_findings"])
        self.assertFalse(report["missing_milestones"])
        self.assertFalse(report["not_host_verified"])
        remaining = {gate["id"] for gate in report["target_gates_remaining"]}
        self.assertIn("M9.1", remaining)
        self.assertIn("M10.7", remaining)
        self.assertFalse(report["physical_acceptance_claimed"])
        self.assertIn("host/software", report["readiness_scope"])
        self.assertIn("./bootstrap.sh --local-checkpoint", report["next_action"])
        self.assertIn("docs/RASPBERRY_PI_ACCEPTANCE_RUN.md", report["next_action"])
        self.assertIn("M10.7", report["next_action"])

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
        self.assertIn("Status: READY_FOR_TARGET_ACCEPTANCE", result.stdout)
        self.assertIn("Target gates remaining:", result.stdout)

    def test_target_acceptance_runbook_is_user_facing(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        runbook = (ROOT / "docs" / "RASPBERRY_PI_ACCEPTANCE_RUN.md").read_text(encoding="utf-8")
        self.assertIn("docs/RASPBERRY_PI_ACCEPTANCE_RUN.md", readme)
        for expected in (
            "./bootstrap.sh --local-checkpoint",
            "sha256sum -c SHA256SUMS_checkpoint23.txt",
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
