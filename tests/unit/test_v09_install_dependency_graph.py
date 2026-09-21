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

    def test_registration_order_is_explicit_before_candidate_phase_finalization(self) -> None:
        ordered = [
            "release_prerequisites",
            "target_platform_preflight",
            "runtime_account",
            "release_layout",
            "immutable_release",
            "activate_release",
            "environment_account",
            "target_identity_preflight",
            "environment_profile",
            "target_i2c_platform",
            "target_runtime_bindings",
            "target_gpio_identity",
            "environment_service",
            "environment_commissioning",
            "environment_readiness",
            "environment_policy",
            "ollama_account_and_store",
            "ollama_binary",
            "ollama_service",
            "ollama_model",
            "ollama_model_roster",
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
        engine = self.text[self.text.index('if gonken_run_registered_steps; then'):]
        pause = engine.index('if [[ "$result" == "78" ]]')
        bundle = engine.index('gonken_collect_install_failure "$result"')
        self.assertLess(pause, bundle)
        block = engine[pause:bundle]
        self.assertIn("INSTALLATION_PAUSED", block)
        self.assertIn("exit 78", block)
        helper = self.text[self.text.index('gonken_collect_install_failure()'):self.text.index('gonken_final_convergence()')]
        self.assertIn('python3 "$INSTALL_FAILURE_BUNDLE"', helper)

    def test_environment_service_precedes_application_service_and_stays_non_actuating(self) -> None:
        self.assertLess(self.position("environment_service"), self.position("application_service"))
        registration = self.text[
            self.position("environment_service"):self.position("ollama_account_and_store")
        ]
        self.assertIn("disabled_autostart", registration)
        self.assertIn("does_not_actuate", registration)

    def test_environment_profile_and_commissioning_are_explicit_optional_boundaries(self) -> None:
        self.assertLess(self.position("environment_profile"), self.position("target_gpio_identity"))
        self.assertLess(self.position("environment_service"), self.position("environment_commissioning"))
        self.assertLess(self.position("environment_profile"), self.position("environment_commissioning"))
        self.assertLess(self.position("environment_commissioning"), self.position("environment_readiness"))
        self.assertIn("installer_plan.py", self.text)
        self.assertIn("gonken_environment_activation_precondition", self.text)
        region = self.text[self.position("environment_service"):self.position("ollama_account_and_store")]
        self.assertIn('GONKEN_SOURCE_RECORD[environment_profile]', region)
        self.assertIn("explicit_full_real_or_simulated_profile_enable_restart_and_verify_current_daemon", region)
        self.assertIn("only_environment_daemon_owns_relay_safe_off_and_selected_policy", region)

    def test_install_completion_reports_independent_component_truth(self):
        body = self.text[self.text.index('gonken_print_component_summary()'):self.text.index('gonken_collect_install_failure()')]
        self.assertIn('components --require-ready', body)
        self.assertNotIn('status=READY', body)
        components = (ROOT / 'src/gonken_agent/component_status.py').read_text()
        for name in ('voice_conversation','ollama_inference','environment_controller',
                     'temperature_humidity_sensor','room_fan_control','llm_environment_tool_broker'):
            self.assertIn(name, components)
        self.assertIn('if gonken_final_convergence; then', self.text)
        self.assertIn('INSTALL_FINAL_CONVERGENCE_FAILED', self.text)
        self.assertLess(self.text.index('if gonken_final_convergence; then'), self.text.index("printf '[READY] code=INSTALLATION_COMPLETE"))

    def test_bluetooth_capture_route_is_proven_before_appliance_readiness(self) -> None:
        self.assertLess(self.position("bluetooth_audio_pairing"), self.position("appliance_readiness"))
        manager = (ROOT / "scripts" / "bluetooth_manager.py").read_text(encoding="utf-8")
        self.assertIn("BLUETOOTH_INPUT_UNAVAILABLE", manager)
        self.assertIn("direct_capture_fallback", manager)
        self.assertIn("libspa-0.2-bluetooth", self.text)

    def test_release_seal_and_runtime_checks_are_separate_current_release_gates(self) -> None:
        release_postcondition = self.text[
            self.text.index("gonken_release_postcondition()"):
            self.text.index("gonken_release_action()")
        ]
        bindings_postcondition = self.text[
            self.text.index("gonken_target_runtime_bindings_postcondition()"):
            self.text.index("gonken_target_runtime_bindings_action()")
        ]
        self.assertIn('validate-static', release_postcondition)
        self.assertNotIn(' bindings-check ', release_postcondition)
        self.assertIn('bindings-check', bindings_postcondition)
        self.assertNotIn(' validate ', bindings_postcondition)

        manager = (ROOT / "scripts" / "release_manager.py").read_text(encoding="utf-8")
        reconcile = manager[manager.index("def reconcile("):manager.index("def activate(")]
        activate = manager[manager.index("def activate("):manager.index("def prune_releases(")]
        self.assertIn("policy=structural_current_only", reconcile)
        self.assertNotIn("validate_release(", reconcile)
        self.assertIn("validate_release_static(", activate)
        self.assertNotIn("validate_release(", activate)

    def test_post_seal_installer_and_services_disable_python_bytecode_writes(self) -> None:
        self.assertIn("export PYTHONDONTWRITEBYTECODE=1", self.text)
        self.assertIn("export PYTHONNOUSERSITE=1", self.text)
        for relative in (
            "packaging/systemd/gonken-agent.service",
            "packaging/systemd/gonken-environment.service",
            "packaging/systemd/gonken-bluetooth-autoconnect.service",
        ):
            unit = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("Environment=PYTHONDONTWRITEBYTECODE=1", unit)
            self.assertIn("Environment=PYTHONNOUSERSITE=1", unit)

    def test_checkpoint32_managed_service_templates_are_accepted_as_upgrade_predecessors(self) -> None:
        expected = {
            "scripts/service_manager.py": "6c26949db3e43805a54fd7cbfc731175740cd32b253c634700242b65429ec17c",
            "scripts/environment_service_manager.py": "67123397d52a5895a9f60ce98205d8830d7a566b20e4ab183003f6dbabcd225b",
            "scripts/bluetooth_manager.py": "6e2e426fac110bab9476ceefbe5947feae829773d5e325c75d23ddea2eeb73ce",
        }
        for relative, digest in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(digest, text, relative)

    def test_bluetooth_preference_allows_direct_audio_fallback(self) -> None:
        pairing = self.text[
            self.text.index("gonken_bluetooth_pair_postcondition()"):
            self.text.index("gonken_bluetooth_pair_action()")
        ]
        self.assertIn("--allow-direct-fallback", pairing)
        manager = (ROOT / "scripts" / "bluetooth_manager.py").read_text(encoding="utf-8")
        self.assertIn("BLUETOOTH_OPTIONAL_UNAVAILABLE", manager)
        self.assertIn("AUDIO_DIRECT_FALLBACK_READY", manager)
        self.assertIn("direct_playback_fallback", manager)

    def test_gpio_identity_is_proven_non_actuating_before_services_and_appliance(self) -> None:
        self.assertLess(self.position("target_runtime_bindings"), self.position("target_gpio_identity"))
        self.assertLess(self.position("target_gpio_identity"), self.position("environment_service"))
        self.assertLess(self.position("target_gpio_identity"), self.position("appliance_readiness"))
        registration = self.text[self.position("target_gpio_identity"):self.position("environment_service")]
        self.assertIn("non_actuating_selected_capability_gpio_identity", registration)
        self.assertIn("does_not_request_write_or_toggle_any_gpio_line", registration)

    def test_runtime_context_is_transport_neutral_when_bluetooth_is_requested(self) -> None:
        post = self.text[self.text.index("gonken_runtime_context_postcondition()"):self.text.index("gonken_runtime_context_action()")]
        action = self.text[self.text.index("gonken_runtime_context_action()"):self.text.index("gonken_appliance_postcondition()")]
        self.assertNotIn("--require-pipewire", post)
        self.assertNotIn("--require-pipewire", action)
        self.assertIn("--require-ready", post)
        self.assertIn("--require-ready", action)

        bluetooth_region = self.text[self.text.index("gonken_bluetooth_stack_postcondition()"):self.text.index("gonken_runtime_context_manager()")]
        self.assertIn("gonken_bluetooth_direct_audio_ready", bluetooth_region)
        self.assertIn("BLUETOOTH_OPTIONAL_STACK_UNAVAILABLE", bluetooth_region)
        self.assertIn("BLUETOOTH_OPTIONAL_PAIRING_UNAVAILABLE", bluetooth_region)
        self.assertIn("BLUETOOTH_OPTIONAL_AUTOCONNECT_SKIPPED", bluetooth_region)

    def test_appliance_readiness_record_is_bound_to_release_commit(self) -> None:
        runtime = (ROOT / "src" / "gonken_agent" / "voice_runtime.py").read_text(encoding="utf-8")
        appliance = (ROOT / "scripts" / "appliance_manager.py").read_text(encoding="utf-8")
        summary = (ROOT / "scripts" / "install_summary.py").read_text(encoding="utf-8")
        self.assertIn('"release_commit": _runtime_release_commit()', runtime)
        self.assertIn('rr.read_ready(READY_FILE', appliance)
        canonical = (ROOT / 'src/gonken_agent/runtime_readiness.py').read_text()
        self.assertIn("value.get('release_commit') != binding.commit", canonical)
        self.assertIn('validate_appliance(root, commit, str(roster["active_model"]), str(roster["active_digest"]))', summary)


if __name__ == "__main__":
    unittest.main()
