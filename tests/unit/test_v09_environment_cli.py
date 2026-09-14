from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from unittest import mock

from gonken_agent import cli
from gonken_agent.environment import EnvironmentClientError


STATUS_PAYLOAD = {
    "service": "READY",
    "environment": "STARTING",
    "state": {
        "mode": "manual",
        "fan_power": "off",
        "sensor_quality": "starting",
        "control_temperature_c": None,
        "last_transition_reason": "BOOT_SAFE_OFF",
        "policy": {
            "schema_version": 1,
            "generation": 1,
            "mode": "manual",
            "start_c": 28.0,
            "stop_c": 26.5,
            "minimum_on_seconds": 60,
            "minimum_off_seconds": 60,
        },
    },
    "capabilities": {
        "power_control": True,
        "software_speed_control": False,
        "fan_motion_observed": False,
    },
    "physical_evidence": False,
}

READ_PAYLOAD = {
    "reading": {
        "temperature_c": 27.6,
        "relative_humidity_pct": 61.4,
        "quality": "ready",
        "valid": True,
    },
    "state": {
        "mode": "automatic",
        "fan_power": "off",
        "sensor_quality": "ready",
        "control_temperature_c": 27.6,
        "last_transition_reason": "BOOT_SAFE_OFF",
    },
    "physical_evidence": False,
}

POLICY_PAYLOAD = {
    "policy": {
        "schema_version": 1,
        "generation": 4,
        "mode": "automatic",
        "start_c": 28.0,
        "stop_c": 26.5,
        "minimum_on_seconds": 60,
        "minimum_off_seconds": 60,
    },
    "bounds": {
        "temperature_min_c": -10.0,
        "temperature_max_c": 60.0,
        "minimum_hysteresis_c": 0.5,
        "maximum_hysteresis_c": 15.0,
    },
}

MUTATION_PAYLOAD = {
    "state": {
        "mode": "manual",
        "fan_power": "on",
        "sensor_quality": "ready",
        "control_temperature_c": 28.2,
        "last_transition_reason": "USER_MANUAL_ON",
        "policy": {
            "schema_version": 1,
            "generation": 5,
            "mode": "manual",
            "start_c": 29.0,
            "stop_c": 27.0,
            "minimum_on_seconds": 30,
            "minimum_off_seconds": 30,
        },
    },
    "policy": {
        "schema_version": 1,
        "generation": 5,
        "mode": "manual",
        "start_c": 29.0,
        "stop_c": 27.0,
        "minimum_on_seconds": 30,
        "minimum_off_seconds": 30,
    },
    "physical_evidence": False,
}

HEALTH_PAYLOAD = {
    "process_alive": True,
    "ipc_ready": True,
    "policy_valid": True,
    "sensor": "ready",
    "actuator": "HOST_FAKE",
    "controller": "ACTIVE",
    "overall": "READY",
    "physical_evidence": False,
}

PROBE_PAYLOAD = {
    "probe": "bounded_host_only",
    "destructive": False,
    "hardware_toggled": False,
    "status": "not_implemented_for_physical_hardware",
}


class FakeResponse:
    def __init__(self, result):
        self.result = result


class FakeEnvironmentClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def status(self):
        self.calls.append(("status", None))
        return STATUS_PAYLOAD

    def health(self):
        self.calls.append(("health", None))
        return HEALTH_PAYLOAD

    def read_sensor(self):
        self.calls.append(("read_sensor", None))
        return READ_PAYLOAD

    def fan_set(self, power):
        self.calls.append(("fan_set", power))
        return MUTATION_PAYLOAD

    def mode_set(self, mode):
        self.calls.append(("mode_set", mode))
        return MUTATION_PAYLOAD

    def policy_get(self):
        self.calls.append(("policy_get", None))
        return POLICY_PAYLOAD

    def policy_update(self, **params):
        self.calls.append(("policy_update", params))
        return MUTATION_PAYLOAD

    def call(self, operation):
        self.calls.append(("call", operation))
        return FakeResponse(PROBE_PAYLOAD)


class EnvironmentCliTests(unittest.TestCase):
    def run_cli(self, arguments, fake=None):
        client = fake or FakeEnvironmentClient()
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(cli, "_make_environment_client", return_value=client):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = cli.main(["env", "--socket", "/tmp/gonken-env.sock", *arguments])
        return result, stdout.getvalue(), stderr.getvalue(), client


    def test_env_serve_disabled_exits_without_fake_hardware(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = cli.main(["env", "--json", "serve", "--no-site"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(result, 0, stderr.getvalue())
        self.assertEqual(payload["code"], "ENVIRONMENT_DISABLED")
        self.assertFalse(payload["enabled"])
        self.assertFalse(payload["hardware_toggled"])
        self.assertFalse(payload["physical_evidence"])

    def test_env_serve_enabled_fails_closed_until_hardware_backend_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = f"{temporary}/site.toml"
            with open(site, "w", encoding="utf-8") as handle:
                handle.write("[extensions.environment]\nenabled = true\n")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = cli.main(["env", "--json", "serve", "--site", site])
        payload = json.loads(stderr.getvalue())
        self.assertEqual(result, cli.EXIT_FAILED)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(payload["code"], "ENV_HARDWARE_BACKEND_NOT_IMPLEMENTED")

    def test_status_json_uses_ipc_client_and_reports_no_physical_evidence(self) -> None:
        result, stdout, stderr, client = self.run_cli(["status", "--json"])
        payload = json.loads(stdout)
        self.assertEqual(result, 0, stderr)
        self.assertEqual(client.calls, [("status", None)])
        self.assertEqual(payload["state"]["mode"], "manual")
        self.assertFalse(payload["physical_evidence"])
        self.assertFalse(payload["capabilities"]["software_speed_control"])
        self.assertFalse(payload["capabilities"]["fan_motion_observed"])

        result, stdout, stderr, client = self.run_cli(["--json", "status"])
        self.assertEqual(result, 0, stderr)
        self.assertEqual(json.loads(stdout)["state"]["mode"], "manual")
        self.assertEqual(client.calls, [("status", None)])

    def test_temperature_and_humidity_commands_read_sensor_once(self) -> None:
        result, stdout, stderr, client = self.run_cli(["temperature"])
        self.assertEqual(result, 0, stderr)
        self.assertIn("Temperature: 27.6 C", stdout)
        self.assertIn("Physical Pi evidence: False", stdout)
        self.assertEqual(client.calls, [("read_sensor", None)])

        result, stdout, stderr, client = self.run_cli(["humidity"])
        self.assertEqual(result, 0, stderr)
        self.assertIn("Humidity: 61.4 %RH", stdout)
        self.assertEqual(client.calls, [("read_sensor", None)])

    def test_fan_mode_and_policy_mutations_pass_typed_arguments_only(self) -> None:
        result, _stdout, stderr, client = self.run_cli(["fan", "on"])
        self.assertEqual(result, 0, stderr)
        self.assertEqual(client.calls, [("fan_set", "on")])

        result, _stdout, stderr, client = self.run_cli(["mode", "set", "automatic"])
        self.assertEqual(result, 0, stderr)
        self.assertEqual(client.calls, [("mode_set", "automatic")])

        result, _stdout, stderr, client = self.run_cli([
            "policy",
            "set",
            "--expected-generation",
            "4",
            "--mode",
            "semi-automatic",
            "--start-c",
            "29",
            "--stop-c",
            "27",
            "--minimum-on-seconds",
            "30",
        ])
        self.assertEqual(result, 0, stderr)
        self.assertEqual(client.calls[0][0], "policy_update")
        self.assertEqual(
            client.calls[0][1],
            {
                "expected_generation": 4,
                "mode": "semi-automatic",
                "start_c": 29.0,
                "stop_c": 27.0,
                "minimum_on_seconds": 30,
            },
        )

    def test_policy_show_health_and_probe_are_non_mutating_client_calls(self) -> None:
        result, stdout, stderr, client = self.run_cli(["policy", "show"])
        self.assertEqual(result, 0, stderr)
        self.assertIn("Policy generation: 4", stdout)
        self.assertEqual(client.calls, [("policy_get", None)])

        result, stdout, stderr, client = self.run_cli(["health"])
        self.assertEqual(result, 0, stderr)
        self.assertIn("Overall: READY", stdout)
        self.assertEqual(client.calls, [("health", None)])

        result, stdout, stderr, client = self.run_cli(["probe"])
        self.assertEqual(result, 0, stderr)
        self.assertIn("Hardware toggled: False", stdout)
        self.assertEqual(client.calls, [("call", "probe.run")])


    def test_watch_reads_sensor_repeatedly_without_mutating_policy_or_hardware(self) -> None:
        result, stdout, stderr, client = self.run_cli(["watch", "--count", "2", "--interval", "0"])
        self.assertEqual(result, 0, stderr)
        self.assertEqual(client.calls, [("read_sensor", None), ("read_sensor", None)])
        self.assertEqual(stdout.count("physical_evidence=False"), 2)
        self.assertIn("fan=off", stdout)

        result, stdout, stderr, client = self.run_cli(["watch", "--count", "2", "--interval", "0", "--json"])
        self.assertEqual(result, 0, stderr)
        rows = [json.loads(line) for line in stdout.splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertFalse(rows[0]["physical_evidence"])
        self.assertEqual(client.calls, [("read_sensor", None), ("read_sensor", None)])

    def test_daemon_rejection_is_reported_without_fake_success(self) -> None:
        class RejectingClient(FakeEnvironmentClient):
            def fan_set(self, power):
                self.calls.append(("fan_set", power))
                raise EnvironmentClientError("ENV_DISABLED", "environment control is disabled")

        result, stdout, stderr, client = self.run_cli(["--json", "fan", "on"], fake=RejectingClient())
        payload = json.loads(stderr)
        self.assertEqual(result, cli.EXIT_FAILED)
        self.assertEqual(stdout, "")
        self.assertEqual(client.calls, [("fan_set", "on")])
        self.assertEqual(payload["code"], "ENV_DISABLED")
        self.assertIn("disabled", payload["message"])

    def test_policy_set_without_fields_fails_before_daemon_call(self) -> None:
        result, stdout, stderr, client = self.run_cli(["policy", "set"])
        self.assertEqual(result, cli.EXIT_FAILED)
        self.assertEqual(stdout, "")
        self.assertEqual(client.calls, [])
        self.assertIn("policy set requires at least one field", stderr)


if __name__ == "__main__":
    unittest.main()
