from __future__ import annotations

import inspect
import threading
import unittest
from types import SimpleNamespace

from gonken_agent.environment import EnvironmentClientError
from gonken_agent.environment.intents import EnvironmentClarification, EnvironmentIntent, parse_environment_intent
from gonken_agent.environment.responses import environment_success_response
from gonken_agent.voice_runtime import ConversationBrain


READ_RESULT = {
    "reading": {
        "temperature_c": 27.6,
        "relative_humidity_pct": 61.4,
        "quality": "ready",
        "valid": True,
    },
    "physical_evidence": False,
}

STATUS_RESULT = {
    "environment": "READY",
    "state": {
        "mode": "manual",
        "fan_power": "off",
        "sensor_quality": "ready",
        "last_transition_reason": "BOOT_SAFE_OFF",
    },
    "capabilities": {
        "power_control": True,
        "software_speed_control": False,
        "fan_motion_observed": False,
    },
    "physical_evidence": False,
}

POLICY_RESULT = {
    "policy": {
        "schema_version": 1,
        "generation": 3,
        "mode": "automatic",
        "start_c": 28.0,
        "stop_c": 26.5,
        "minimum_on_seconds": 60,
        "minimum_off_seconds": 60,
    },
    "bounds": {},
}

MUTATION_RESULT = {
    "state": {
        "mode": "manual",
        "fan_power": "on",
        "sensor_quality": "ready",
        "last_transition_reason": "USER_MANUAL_ON",
    },
    "policy": {
        "schema_version": 1,
        "generation": 4,
        "mode": "manual",
        "start_c": 29.0,
        "stop_c": 27.0,
        "minimum_on_seconds": 60,
        "minimum_off_seconds": 60,
    },
    "physical_evidence": False,
}


class FakeEnvironmentClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def read_sensor(self):
        self.calls.append(("read_sensor", None))
        return READ_RESULT

    def status(self):
        self.calls.append(("status", None))
        return STATUS_RESULT

    def policy_get(self):
        self.calls.append(("policy_get", None))
        return POLICY_RESULT

    def fan_set(self, power):
        self.calls.append(("fan_set", power))
        return MUTATION_RESULT

    def mode_set(self, mode):
        self.calls.append(("mode_set", mode))
        return MUTATION_RESULT

    def policy_update(self, **params):
        self.calls.append(("policy_update", params))
        return MUTATION_RESULT


class RejectingEnvironmentClient(FakeEnvironmentClient):
    def fan_set(self, power):
        self.calls.append(("fan_set", power))
        raise EnvironmentClientError("ACTUATOR_UNAVAILABLE", "relay line unavailable")


class FakeLlmClient:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def chat_text(self, messages, _stop):
        self.calls.append(messages)
        return "General answer."

    def close(self):
        pass


class EnvironmentVoiceIntentParserTests(unittest.TestCase):
    def test_parser_maps_queries_and_status_to_allowlisted_operations(self) -> None:
        temperature = parse_environment_intent("What is the room temperature?")
        self.assertIsInstance(temperature, EnvironmentIntent)
        self.assertEqual(temperature.operation, "sensor.read")
        self.assertEqual(temperature.response_kind, "temperature")
        self.assertFalse(temperature.mutating)

        humidity = parse_environment_intent("Tell me the humidity")
        self.assertIsInstance(humidity, EnvironmentIntent)
        self.assertEqual(humidity.operation, "sensor.read")
        self.assertEqual(humidity.response_kind, "humidity")

        status = parse_environment_intent("Is the room fan on?")
        self.assertIsInstance(status, EnvironmentIntent)
        self.assertEqual(status.operation, "status.get")
        self.assertEqual(status.response_kind, "fan_status")

        policy = parse_environment_intent("What settings are you using for the fan?")
        self.assertIsInstance(policy, EnvironmentIntent)
        self.assertEqual(policy.operation, "policy.get")

    def test_parser_maps_clear_actions_and_thresholds_but_clarifies_ambiguous_temperature(self) -> None:
        on = parse_environment_intent("Turn the room fan on")
        self.assertIsInstance(on, EnvironmentIntent)
        self.assertEqual(on.operation, "fan.set")
        self.assertEqual(dict(on.params), {"power": "on"})
        self.assertTrue(on.mutating)

        mode = parse_environment_intent("Use semi automatic mode")
        self.assertIsInstance(mode, EnvironmentIntent)
        self.assertEqual(mode.operation, "mode.set")
        self.assertEqual(dict(mode.params), {"mode": "semi_automatic"})

        policy = parse_environment_intent("Use automatic mode and turn it on at 28 and off at 26.5 degrees")
        self.assertIsInstance(policy, EnvironmentIntent)
        self.assertEqual(policy.operation, "policy.update")
        self.assertEqual(policy.params["mode"], "automatic")
        self.assertEqual(policy.params["start_c"], 28.0)
        self.assertEqual(policy.params["stop_c"], 26.5)

        ambiguous = parse_environment_intent("Set the temperature to 25 degrees")
        self.assertIsInstance(ambiguous, EnvironmentClarification)
        self.assertIn("start threshold", ambiguous.message)

    def test_parser_ignores_general_conversation_and_has_no_hardware_or_shell_surface(self) -> None:
        self.assertIsNone(parse_environment_intent("Tell me a short story about Tokyo."))
        import gonken_agent.environment.intents as intents
        source = inspect.getsource(intents)
        for forbidden in ("subprocess", "smbus", "gpiod", "set_gpio", "/bin/sh"):
            self.assertNotIn(forbidden, source)


class EnvironmentVoiceResponseTests(unittest.TestCase):
    def test_responses_are_derived_from_daemon_results_and_do_not_claim_speed_or_motion(self) -> None:
        intent = EnvironmentIntent("fan.set", {"power": "on"}, "fan_set", mutating=True)
        response = environment_success_response(intent, MUTATION_RESULT)
        self.assertIn("Room fan power is on", response)
        self.assertIn("daemon's relay-power state", response)
        self.assertIn("not physical blade rotation", response)

        status = EnvironmentIntent("status.get", {}, "fan_status")
        response = environment_success_response(status, STATUS_RESULT)
        self.assertIn("Room fan power is off", response)
        self.assertIn("not blade motion or software speed", response)


class ConversationBrainEnvironmentActionTests(unittest.TestCase):
    def _brain(self, env_client):
        brain = ConversationBrain.__new__(ConversationBrain)
        brain.client = FakeLlmClient()
        brain.system_prompt = "system"
        brain.history = []
        brain.environment_client_factory = lambda: env_client
        return brain

    def test_environment_action_uses_daemon_client_before_llm_and_does_not_add_chat_history(self) -> None:
        env = FakeEnvironmentClient()
        brain = self._brain(env)
        answer = brain.reply("Turn the fan on", threading.Event())
        self.assertIn("Room fan power is on", answer)
        self.assertEqual(env.calls, [("fan_set", "on")])
        self.assertEqual(brain.client.calls, [])
        self.assertEqual(brain.history, [])

    def test_policy_update_passes_typed_params_only(self) -> None:
        env = FakeEnvironmentClient()
        brain = self._brain(env)
        answer = brain.reply("Use automatic mode and turn it on at 28 and off at 26.5", threading.Event())
        self.assertIn("Fan policy is updated", answer)
        self.assertEqual(env.calls[0][0], "policy_update")
        self.assertEqual(env.calls[0][1], {"mode": "automatic", "start_c": 28.0, "stop_c": 26.5})

    def test_daemon_rejection_is_spoken_without_fake_success(self) -> None:
        env = RejectingEnvironmentClient()
        brain = self._brain(env)
        answer = brain.reply("Turn the fan on", threading.Event())
        self.assertIn("actuator is unavailable", answer)
        self.assertIn("did not change", answer)
        self.assertEqual(brain.client.calls, [])

    def test_ambiguous_environment_request_clarifies_without_client_or_llm_call(self) -> None:
        env = FakeEnvironmentClient()
        brain = self._brain(env)
        answer = brain.reply("Set the temperature to 25 degrees", threading.Event())
        self.assertIn("start threshold", answer)
        self.assertEqual(env.calls, [])
        self.assertEqual(brain.client.calls, [])

    def test_general_question_still_uses_local_llm_path(self) -> None:
        env = FakeEnvironmentClient()
        brain = self._brain(env)
        answer = brain.reply("Explain what Python is.", threading.Event())
        self.assertEqual(answer, "General answer.")
        self.assertEqual(env.calls, [])
        self.assertEqual(len(brain.client.calls), 1)
        self.assertEqual(len(brain.history), 2)


if __name__ == "__main__":
    unittest.main()
