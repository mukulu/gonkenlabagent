from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "install-gonken.sh"
BOOTSTRAP = ROOT / "bootstrap.sh"
INSTALLER = ROOT / "scripts" / "install.sh"


class V09ResponsibilityBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.launcher = LAUNCHER.read_text(encoding="utf-8")
        self.bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        self.installer = INSTALLER.read_text(encoding="utf-8")

    def test_launcher_is_acquisition_and_bootstrap_delegation_only(self) -> None:
        self.assertIn('exec ./bootstrap.sh --source-url "$SOURCE_URL" --ref "$SOURCE_REF"', self.launcher)
        self.assertIn('apt-get install -y ca-certificates git python3', self.launcher)
        for forbidden in (
            "installer_failure_bundle.py",
            "target_probe.py",
            "appliance_manager.py",
            "release_manager.py",
            "source.record",
            "APPLIANCE_NOT_READY",
        ):
            self.assertNotIn(forbidden, self.launcher)

    def test_bootstrap_owns_source_record_preflight_and_installer_handoff(self) -> None:
        self.assertIn("source.record", self.bootstrap)
        self.assertIn("gonken_validate_target_platform", self.bootstrap)
        self.assertIn("gonken_validate_resources", self.bootstrap)
        self.assertIn("gonken_establish_privilege", self.bootstrap)
        self.assertIn('exec "$SCRIPT_DIR/scripts/install.sh"', self.bootstrap)
        for forbidden in (
            "installer_failure_bundle.py",
            "appliance_manager.py",
            "INSTALL_STEP_ACTION",
            "APPLIANCE_NOT_READY",
        ):
            self.assertNotIn(forbidden, self.bootstrap)

    def test_installer_owns_dag_readiness_and_failure_bundle(self) -> None:
        self.assertIn('INSTALL_FAILURE_BUNDLE="$SCRIPT_DIR/installer_failure_bundle.py"', self.installer)
        self.assertIn('gonken_appliance_manager()', self.installer)
        self.assertIn('\"appliance_readiness\" \"4\"', self.installer)
        self.assertIn('gonken_run_registered_steps', self.installer)
        self.assertNotIn('git clone ', self.installer)

    def test_critical_responsibilities_have_exactly_one_declared_owner(self) -> None:
        texts = {
            "launcher": self.launcher,
            "bootstrap": self.bootstrap,
            "installer": self.installer,
        }
        markers = {
            "source_record": "source.record",
            "failure_bundle": "installer_failure_bundle.py",
            "appliance_readiness": "gonken_appliance_manager()",
        }
        expected = {
            "source_record": {"bootstrap", "installer"},  # producer + required consumer
            "failure_bundle": {"installer"},
            "appliance_readiness": {"installer"},
        }
        for responsibility, marker in markers.items():
            owners = {name for name, text in texts.items() if marker in text}
            self.assertEqual(owners, expected[responsibility], responsibility)


if __name__ == "__main__":
    unittest.main()
