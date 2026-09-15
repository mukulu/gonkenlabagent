from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from gonken_agent.config import load_config
from gonken_agent.environment import EnvironmentClient, build_environment_service_core
from gonken_agent.environment.server import EnvironmentUnixServer
from gonken_agent.voice_runtime import ConversationBrain

ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = ROOT / "config" / "defaults.toml"


class _NoLlm:
    def __init__(self) -> None:
        self.calls = 0

    def chat_text(self, messages, stop):
        self.calls += 1
        return "unexpected llm path"

    def close(self) -> None:
        return None


class EnvironmentVoiceTransactionIntegrationTests(unittest.TestCase):
    def _config(self, temporary: str):
        return load_config(
            defaults_path=DEFAULTS,
            site_path=None,
            environ={},
            cli_overrides={
                "extensions.environment.enabled": True,
                "extensions.environment.sensor_backend": "simulated",
                "extensions.environment.relay_backend": "simulated",
                "extensions.environment.simulation_runtime_control_enabled": True,
                "extensions.environment.socket_path": str(Path(temporary) / "control.sock"),
                "extensions.environment.policy_path": str(Path(temporary) / "policy.json"),
                "extensions.environment.minimum_dwell_seconds": 0,
                "extensions.environment.valid_samples_to_recover": 1,
            },
        ).config

    def _brain(self, socket_path: str) -> ConversationBrain:
        brain = ConversationBrain.__new__(ConversationBrain)
        brain.client = _NoLlm()
        brain.system_prompt = "system"
        brain.history = []
        brain.environment_client_factory = lambda: EnvironmentClient(socket_path, timeout_seconds=1.0)
        return brain

    def test_voice_fan_on_off_traverses_real_unix_protocol_without_llm_or_physical_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self._config(temporary)
            env = config.extensions.environment
            core = build_environment_service_core(env)
            server = EnvironmentUnixServer(env.socket_path, core, socket_mode=0o600)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                brain = self._brain(env.socket_path)
                client = EnvironmentClient(env.socket_path, timeout_seconds=1.0)

                on_response = brain.reply("GonKen, turn the room fan on", threading.Event())
                on_status = client.status()
                self.assertIn("Simulated fan actuator power is on", on_response)
                self.assertEqual(on_status["state"]["fan_power"], "on")
                self.assertEqual(on_status["provenance"]["evidence_mode"], "HOST_SIMULATION")
                self.assertFalse(on_status["physical_evidence"])

                off_response = brain.reply("turn the room fan off", threading.Event())
                off_status = client.status()
                self.assertIn("Simulated fan actuator power is off", off_response)
                self.assertEqual(off_status["state"]["fan_power"], "off")
                self.assertFalse(off_status["physical_evidence"])
                self.assertEqual(brain.client.calls, 0)
                self.assertEqual(brain.history, [])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_voice_sensor_query_uses_daemon_and_labels_simulated_reading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self._config(temporary)
            env = config.extensions.environment
            core = build_environment_service_core(env)
            server = EnvironmentUnixServer(env.socket_path, core, socket_mode=0o600)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                brain = self._brain(env.socket_path)
                client = EnvironmentClient(env.socket_path, timeout_seconds=1.0)
                client.simulation_sensor_set(temperature_c=24.5, relative_humidity_pct=52.0)
                response = brain.reply("what is the room temperature", threading.Event())
                self.assertIn("In simulation", response)
                self.assertIn("not a physical room reading", response)
                self.assertEqual(brain.client.calls, 0)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_voice_daemon_unavailable_returns_truthful_failure_without_llm(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = str(Path(temporary) / "missing.sock")
            brain = self._brain(missing)
            response = brain.reply("turn the room fan on", threading.Event())
            self.assertIn("environment service is unavailable", response.lower())
            self.assertIn("cannot verify or change", response.lower())
            self.assertEqual(brain.client.calls, 0)


if __name__ == "__main__":
    unittest.main()
