from __future__ import annotations

import json
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gonken_agent.llm.models import (
    DEFAULT_MODEL,
    MODEL_ROSTER,
    active_model,
    admitted_model,
    roster_tags,
    selection_status,
    write_selection,
)
from gonken_agent.llm.ollama import OllamaClient, OllamaError
from gonken_agent.tool_broker import (
    TOOL_SCHEMAS,
    ToolBroker,
    ToolBrokerError,
    direct_clock_intent,
    parse_tool_call,
    render_local_datetime,
)
from gonken_agent.voice_runtime import ConversationBrain


class FakeEnvironmentClient:
    def __init__(self):
        self.fan = "off"

    def read_sensor(self):
        return {
            "reading": {"temperature_c": 27.5, "relative_humidity_pct": 56.3, "quality": "ready"},
            "provenance": {"sensor_is_simulated": False, "actuator_is_simulated": True},
        }

    def status(self):
        return {
            "environment": "READY",
            "state": {"fan_power": self.fan, "mode": "manual", "sensor_quality": "ready"},
            "provenance": {"sensor_is_simulated": False, "actuator_is_simulated": True},
        }

    def fan_set(self, power):
        self.fan = power
        return self.status()


class RosterTests(unittest.TestCase):
    def test_exact_three_model_roster_and_default(self):
        self.assertEqual(
            roster_tags(),
            ("qwen3:0.6b", "lfm2.5-thinking:1.2b", "qwen3.5:0.8b"),
        )
        self.assertEqual(DEFAULT_MODEL, "qwen3:0.6b")
        self.assertTrue(all(item.tools and item.thinking for item in MODEL_ROSTER))
        self.assertEqual(admitted_model("qwen3:0.6b").digest_prefix, "7df6b6e09427")
        with self.assertRaises(ValueError):
            admitted_model("untrusted:model")

    def test_atomic_selection_generation_and_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "active-model.json"
            self.assertEqual(active_model("qwen3.5:2b-q4_K_M", path=path), "qwen3.5:2b-q4_K_M")
            first = write_selection("qwen3:0.6b", path=path, previous_model="qwen3.5:2b-q4_K_M")
            second = write_selection("qwen3.5:0.8b", path=path)
            self.assertEqual(first["generation"], 1)
            self.assertEqual(second["generation"], 2)
            self.assertEqual(second["previous_model"], "qwen3:0.6b")
            self.assertEqual(active_model("legacy", path=path), "qwen3.5:0.8b")
            self.assertTrue(selection_status("legacy", path=path)["governed_roster_active"])


class ToolBrokerTests(unittest.TestCase):
    def setUp(self):
        self.environment = FakeEnvironmentClient()
        self.broker = ToolBroker(lambda: self.environment)

    def test_read_tools_are_typed_and_grounded(self):
        sensor = parse_tool_call({"function": {"name": "environment_read_sensor", "arguments": {}}})
        answer = self.broker.execute(sensor, user_text="How warm is it in here?")
        self.assertIn("27.5 degrees Celsius", answer["spoken"])
        self.assertIn("simulated", answer["spoken"])
        status = parse_tool_call({"function": {"name": "environment_get_status", "arguments": {}}})
        self.assertIn("off", self.broker.execute(status, user_text="Is the fan running?")["spoken"])

    def test_local_clock_is_read_only_and_deterministic(self):
        fixed = datetime(2026, 9, 18, 22, 27, tzinfo=timezone.utc)
        self.assertIn("10:27 PM", render_local_datetime(fixed))
        self.assertIsNotNone(direct_clock_intent("What time is it?"))
        proposal = parse_tool_call({"function": {"name": "system_get_local_datetime", "arguments": {}}})
        result = self.broker.execute(proposal, user_text="Tell me the local date and time")
        self.assertFalse(result["mutating"])

    def test_fan_mutation_requires_independent_explicit_authorization(self):
        on = parse_tool_call({"function": {"name": "environment_set_fan_power", "arguments": {"power": "on"}}})
        self.broker.execute(on, user_text="Please start the room fan")
        self.assertEqual(self.environment.fan, "on")
        for text in (
            "Don't turn the fan on",
            'Explain the phrase "turn the fan on"',
            "What if you turned the fan on?",
            "Could you explain how to turn the fan on?",
        ):
            with self.subTest(text=text), self.assertRaises(ToolBrokerError):
                self.broker.execute(on, user_text=text)
        self.assertEqual(self.environment.fan, "on")

    def test_unknown_raw_execution_tools_are_rejected(self):
        for name in ("shell", "gpio_write", "i2c_raw", "systemctl_restart"):
            with self.subTest(name=name), self.assertRaises(ToolBrokerError):
                parse_tool_call({"function": {"name": name, "arguments": {}}})

    def test_two_read_only_calls_can_share_one_bounded_transaction(self):
        calls = [
            {"function": {"name": "environment_read_sensor", "arguments": {}}},
            {"function": {"name": "environment_get_status", "arguments": {}}},
        ]
        spoken = self.broker.execute_calls(calls, user_text="Tell me the room temperature and whether the fan is on")
        self.assertIn("27.5 degrees Celsius", spoken)
        self.assertIn("off", spoken)
        self.assertEqual(self.environment.fan, "off")


    def test_duplicate_mutations_in_one_turn_are_rejected(self):
        call = {"function": {"name": "environment_set_fan_power", "arguments": {"power": "on"}}}
        with self.assertRaises(ToolBrokerError):
            self.broker.execute_calls([call, call], user_text="Turn the fan on")


class OllamaToolContractTests(unittest.TestCase):
    def _config(self):
        return SimpleNamespace(
            base_url="http://127.0.0.1:11434",
            model="qwen3:0.6b",
            keep_alive="5m",
            context_tokens=2048,
            max_output_tokens=160,
        )

    def test_tools_payload_disables_thinking_by_default(self):
        client = OllamaClient(self._config())
        payload = client._chat_payload(
            [{"role": "user", "content": "How warm is the room?"}],
            structured=False,
            tools=TOOL_SCHEMAS,
        )
        self.assertIs(payload["think"], False)
        self.assertEqual(payload["model"], "qwen3:0.6b")
        self.assertEqual(len(payload["tools"]), 4)

    def test_tool_calls_are_bounded_and_structured(self):
        client = OllamaClient(self._config())
        with mock.patch.object(
            client,
            "request",
            return_value={
                "model": "qwen3:0.6b",
                "done": True,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "environment_read_sensor", "arguments": {}}}
                    ],
                },
            },
        ):
            result = client.chat_message(
                [{"role": "user", "content": "How warm is the room?"}],
                threading.Event(),
                tools=TOOL_SCHEMAS,
            )
        self.assertEqual(result["tool_calls"][0]["function"]["name"], "environment_read_sensor")


class ConversationRoutingTests(unittest.TestCase):
    def _brain(self):
        brain = ConversationBrain.__new__(ConversationBrain)
        brain.history = []
        brain.system_prompt = "You are GonKen."
        brain.environment_client_factory = lambda: self.environment
        brain.tool_broker = ToolBroker(brain.environment_client_factory)
        brain.client = mock.Mock()
        brain.client.model = DEFAULT_MODEL
        brain.client.model_identity.return_value = {"model": DEFAULT_MODEL, "digest": "a" * 64}
        brain.tool_context_tokens = 2048
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        brain.roster_record_path = Path(tmp.name) / "roster.json"
        brain.roster_record_path.write_text(json.dumps({
            "format": "gonken-ollama-roster-record-v2", "status": "READY", "context_tokens": 2048,
            "models": [{"tag": DEFAULT_MODEL, "digest": "a" * 64, "inference_status": "PASS",
                        "tool_call_smoke": "PASS", "stages": [
                            {"stage": stage, "status": "PASS"}
                            for stage in ("IDENTITY", "INFERENCE", "TOOLS", "UNLOAD")]}]}))
        return brain

    def setUp(self):
        self.environment = FakeEnvironmentClient()

    def test_time_bypasses_model(self):
        brain = self._brain()
        answer = brain.reply("What time is it?", threading.Event())
        self.assertIn("local time", answer)
        self.assertEqual(brain.last_metrics["route"], "system_clock_fast_path")
        self.assertFalse(brain.last_metrics["content_logged"])
        brain.client.chat_message.assert_not_called()

    def test_common_temperature_paraphrase_uses_deterministic_environment_fast_path(self):
        brain = self._brain()
        answer = brain.reply("How warm is the room?", threading.Event())
        self.assertIn("27.5 degrees Celsius", answer)
        brain.client.chat_message.assert_not_called()

    def test_less_direct_paraphrase_can_fall_back_to_typed_tool(self):
        brain = self._brain()
        brain.client.chat_message.return_value = {
            "content": "",
            "tool_calls": [{"function": {"name": "environment_read_sensor", "arguments": {}}}],
        }
        answer = brain.reply("Could you check the room conditions for me?", threading.Event())
        self.assertIn("27.5 degrees Celsius", answer)
        self.assertEqual(brain.last_metrics["route"], "llm_typed_tool")
        self.assertIn("wall_ns", brain.last_metrics)
        brain.client.chat_message.assert_called_once()

    def test_model_cannot_mutate_fan_for_hypothetical(self):
        brain = self._brain()
        brain.client.chat_message.return_value = {
            "content": "",
            "tool_calls": [{"function": {"name": "environment_set_fan_power", "arguments": {"power": "on"}}}],
        }
        answer = brain.reply("Hypothetically, make the room breezy for an example.", threading.Event())
        self.assertIn("did not perform", answer)
        self.assertEqual(self.environment.fan, "off")


if __name__ == "__main__":
    unittest.main()
