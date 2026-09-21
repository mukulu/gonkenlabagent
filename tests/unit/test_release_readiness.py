import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import release_readiness


ROOT = Path(__file__).resolve().parents[2]


class ReleaseReadinessTests(unittest.TestCase):
    def test_current_unfinished_program_cannot_be_promoted(self):
        result = subprocess.run([sys.executable, "scripts/release_readiness.py", "--json", "--allow-dirty"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'NOT_READY')
        self.assertEqual(report['validation_status'], 'PASS')
        self.assertTrue(report['current_gates_remaining'])
        self.assertEqual(len(report['target_shadow_passed']), 24)
        self.assertFalse(report['target_shadow_failures'])
        self.assertFalse(report['physical_acceptance_claimed'])
        self.assertNotIn('MILESTONES.json', report['authority'])

    def test_human_report_has_exact_boundary_language(self):
        result = subprocess.run([sys.executable, "scripts/release_readiness.py", "--allow-dirty"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Status: NOT_READY', result.stdout)
        self.assertIn('Current core gates remaining:', result.stdout)
        self.assertIn('Target-shadow fixtures: 24/24', result.stdout)
        self.assertIn('Physical acceptance claimed: false', result.stdout)

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
            'sha256sum -c "$MANIFEST"',
            'tar --no-same-owner -xjf "$ARCHIVE" -C "$DEST"',
            "test -x ./bootstrap.sh",
            "gpio_identity_preflight.py",
            "--config /etc/gonken-agent/config.toml --json",
            "Dormant GPIO17/GPIO27",
            "collect-support.sh",
            "journalctl -u gonken-agent.service",
            "sudo reboot",
            "update.sh",
            "rollback.sh",
            "uninstall.sh",
            "BLOCKED_NO_PREVIOUS_VALIDATED_RELEASE",
        ):
            self.assertIn(expected, runbook)
        self.assertNotIn("git reset --hard HEAD", runbook)
        self.assertNotIn("python3 -m zipfile -e", runbook)


if __name__ == "__main__":
    unittest.main()
