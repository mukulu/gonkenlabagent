from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "scripts" / "install.sh"


class TargetInstallDependencyGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = INSTALL.read_text(encoding="utf-8")

    def position(self, step_id: str) -> int:
        token = f'"{step_id}"'
        value = self.text.find(token)
        self.assertGreaterEqual(value, 0, f"missing installer step {step_id}")
        return value

    def test_target_install_dependency_order_is_explicit(self) -> None:
        ordered = [
            "release_prerequisites",
            "target_platform_preflight",
            "runtime_account",
            "release_layout",
            "immutable_release",
            "activate_release",
            "environment_account",
            "target_identity_preflight",
            "target_i2c_platform",
            "target_runtime_bindings",
            "environment_service",
            "ollama_account_and_store",
            "ollama_binary",
            "ollama_service",
            "ollama_model",
            "whisper_runtime",
            "piper_runtime",
            "speech_models",
            "speech_smoke",
            "application_service",
            "bluetooth_audio_stack",
            "bluetooth_audio_pairing",
            "bluetooth_audio_autoconnect",
            "runtime_context",
            "appliance_readiness",
        ]
        positions = [self.position(step) for step in ordered]
        self.assertEqual(positions, sorted(positions))

    def test_i2c_planned_pause_is_handled_before_failure_bundle(self) -> None:
        pause = self.text.find('if [[ "$result" == "78" ]]')
        bundle = self.text.find('INSTALL_FAILURE_BUNDLE', pause)
        self.assertGreaterEqual(pause, 0)
        self.assertGreater(bundle, pause)
        block = self.text[pause:bundle]
        self.assertIn("INSTALLATION_PAUSED", block)
        self.assertIn("exit 78", block)

    def test_environment_service_precedes_application_service_and_stays_non_actuating(self) -> None:
        self.assertLess(self.position("environment_service"), self.position("application_service"))
        registration = self.text[
            self.position("environment_service"):self.position("ollama_account_and_store")
        ]
        self.assertIn("disabled_autostart", registration)
        self.assertIn("does_not_actuate", registration)

    def test_bluetooth_capture_route_is_proven_before_appliance_readiness(self) -> None:
        self.assertLess(self.position("bluetooth_audio_pairing"), self.position("appliance_readiness"))
        manager = (ROOT / "scripts" / "bluetooth_manager.py").read_text(encoding="utf-8")
        self.assertIn("BLUETOOTH_INPUT_UNAVAILABLE", manager)
        self.assertIn("direct_capture_fallback", manager)
        self.assertIn("libspa-0.2-bluetooth", self.text)

    def test_appliance_readiness_record_is_bound_to_release_commit(self) -> None:
        runtime = (ROOT / "src" / "gonken_agent" / "voice_runtime.py").read_text(encoding="utf-8")
        appliance = (ROOT / "scripts" / "appliance_manager.py").read_text(encoding="utf-8")
        summary = (ROOT / "scripts" / "install_summary.py").read_text(encoding="utf-8")
        self.assertIn('"release_commit": _runtime_release_commit()', runtime)
        self.assertIn('recorded = value.get("release_commit")', appliance)
        self.assertIn('validate_appliance(root, commit)', summary)


if __name__ == "__main__":
    unittest.main()
