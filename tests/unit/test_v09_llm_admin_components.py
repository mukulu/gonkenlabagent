from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gonken_agent.cli import _build_parser
from gonken_agent.component_status import collect
from gonken_agent.config import load_config
from gonken_agent.llm import admin
from gonken_agent.llm.models import write_selection


class LlmAdminComponentTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(site_path=None).config

    def test_cli_exposes_components_and_llm_surface(self):
        parser = _build_parser()
        self.assertEqual(parser.parse_args(["components", "--json"]).command, "components")
        self.assertEqual(parser.parse_args(["llm", "status", "--json"]).llm_command, "status")
        self.assertEqual(parser.parse_args(["llm", "switch", "qwen3:0.6b"]).model, "qwen3:0.6b")
        self.assertEqual(parser.parse_args(["llm", "benchmark", "--iterations", "2"]).iterations, 2)
        self.assertTrue(parser.parse_args(["llm", "benchmark", "--thinking"]).thinking)

    def test_component_status_keeps_real_sensor_simulated_fan_and_tools_independent(self):
        with tempfile.TemporaryDirectory() as temporary:
            ready = Path(temporary) / "ready.json"
            ready.write_text(json.dumps({
                "status": "READY", "code": "VOICE_RUNTIME_READY", "model": self.config.llm.model,
                "wake_phrase": "GonKen",
            }))
            diagnostics = {
                "enabled": True,
                "static": {"sensor_backend": "sht31", "relay_backend": "simulated"},
                "ipc": {
                    "status": "READY", "code": "READ_ONLY_HEALTH_OK", "overall": "READY",
                    "sensor": "ready", "actuator": "READY", "controller": "ACTIVE",
                    "snapshot": {"sensor_backend": "sht31", "actuator_backend": "simulated", "sensor_quality": "ready", "fan_power": "off"},
                    "simulation": {"sensor_is_simulated": False, "actuator_is_simulated": True, "evidence_mode": "TARGET_HYBRID_ACTUATOR_SIMULATED"},
                },
            }
            with mock.patch("gonken_agent.component_status.collect_environment_diagnostics", return_value=diagnostics):
                payload = collect(self.config, ready_file=ready)
        components = payload["components"]
        self.assertEqual(components["voice_conversation"]["status"], "READY")
        self.assertEqual(components["temperature_humidity_sensor"]["backend"], "sht31")
        self.assertFalse(components["temperature_humidity_sensor"]["simulated"])
        self.assertEqual(components["room_fan_control"]["backend"], "simulated")
        self.assertTrue(components["room_fan_control"]["simulated"])
        self.assertFalse(components["room_fan_control"]["physical_motion_observed"])
        self.assertEqual(components["llm_environment_tool_broker"]["status"], "READY")
        self.assertFalse(payload["physical_acceptance_claimed"])

    def test_status_reports_governed_roster_and_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            selection = Path(temporary) / "active-model.json"
            write_selection("qwen3:0.6b", path=selection, previous_model="qwen3.5:2b-q4_K_M")
            with mock.patch("gonken_agent.llm.admin.DEFAULT_SELECTION_PATH", selection), \
                 mock.patch("gonken_agent.llm.admin.selection_status") as selection_status_mock, \
                 mock.patch("gonken_agent.llm.admin._inventory", return_value=[{"name": m, "digest": "a"*64} for m in ("qwen3:0.6b", "lfm2.5-thinking:1.2b", "qwen3.5:0.8b")]), \
                 mock.patch("gonken_agent.llm.admin._loaded_models", return_value=["qwen3:0.6b"]):
                selection_status_mock.return_value = {"status": "READY", "model": "qwen3:0.6b", "generation": 1, "governed_roster_active": True}
                payload = admin.status(self.config)
        self.assertEqual(payload["status"], "READY")
        self.assertEqual(len(payload["roster"]), 3)
        self.assertEqual(sum(1 for row in payload["roster"] if row["selected"]), 1)

    def test_benchmark_records_thinking_and_resource_snapshots_without_content(self):
        fake_client = mock.Mock()
        fake_client.chat_message.return_value = {"total_duration": 10, "eval_duration": 5}
        with mock.patch("gonken_agent.llm.admin._client", return_value=fake_client), \
             mock.patch("gonken_agent.llm.admin._resource_snapshot", side_effect=[{"memory": {}, "soc_temperature_c": 45.0}, {"memory": {}, "soc_temperature_c": 46.0}]):
            payload = admin.benchmark(self.config, "qwen3:0.6b", 1, thinking=True)
        self.assertTrue(payload["thinking"])
        self.assertFalse(payload["content_logged"])
        self.assertEqual(payload["resources_before"]["soc_temperature_c"], 45.0)
        self.assertEqual(payload["resources_after"]["soc_temperature_c"], 46.0)
        fake_client.chat_message.assert_called_once()
        self.assertTrue(fake_client.chat_message.call_args.kwargs["think"])


    def test_switch_rolls_back_selection_when_new_voice_model_does_not_converge(self):
        with tempfile.TemporaryDirectory() as temporary:
            selection = Path(temporary) / "active-model.json"
            write_selection("qwen3:0.6b", path=selection, previous_model="qwen3.5:2b-q4_K_M")
            with mock.patch("gonken_agent.llm.admin.os.geteuid", return_value=0), \
                 mock.patch("gonken_agent.llm.admin.capability_smoke", return_value={"status": "PASS"}), \
                 mock.patch("gonken_agent.llm.admin._restart_and_wait", side_effect=[admin.ModelAdminError("MODEL_SWITCH_NOT_READY", "bad"), None]):
                with self.assertRaises(admin.ModelAdminError) as raised:
                    admin.switch(self.config, "qwen3.5:0.8b", selection_path=selection, ready_file=Path(temporary)/"ready.json")
            self.assertEqual(raised.exception.code, "MODEL_SWITCH_NOT_READY")
            restored = json.loads(selection.read_text())
            self.assertEqual(restored["model"], "qwen3:0.6b")

    def test_switch_rejects_nonroot_before_mutation(self):
        with mock.patch("gonken_agent.llm.admin.os.geteuid", return_value=1000):
            with self.assertRaises(admin.ModelAdminError) as raised:
                admin.switch(self.config, "qwen3.5:0.8b")
        self.assertEqual(raised.exception.code, "MODEL_SWITCH_ROOT_REQUIRED")


if __name__ == "__main__":
    unittest.main()
