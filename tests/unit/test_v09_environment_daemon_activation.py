from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gonken_agent import cli
from gonken_agent.config import load_config
from gonken_agent.environment import (
    EnvironmentClient,
    EnvironmentDaemonError,
    FanCapability,
    FanPower,
    SensorReading,
    build_environment_service_core,
    build_environment_unix_server,
    policy_bounds_from_config,
)


class FakeSensor:
    def __init__(self) -> None:
        self.closed = False
        self.calls = 0

    def read(self, *, now_monotonic: float) -> SensorReading:
        self.calls += 1
        return SensorReading(
            temperature_c=29.0,
            relative_humidity_pct=55.0,
            observed_monotonic=now_monotonic,
            sensor_address=0x44,
            source_backend="fake_sht31",
        )

    def close(self) -> None:
        self.closed = True


class FakeActuator:
    def __init__(self) -> None:
        self.commands: list[FanPower] = []
        self.safe_off_called = False
        self.closed = False

    def set_power(self, power) -> None:
        self.commands.append(FanPower.parse(power))

    def safe_off(self) -> None:
        self.safe_off_called = True
        self.commands.append(FanPower.OFF)

    def close(self) -> None:
        self.closed = True

    def capabilities(self) -> FanCapability:
        return FanCapability(power_control=True, software_speed_control=False, fan_motion_observed=False)

    def resolved_identity(self):
        return {
            "logical_bcm": 23,
            "line_name": "GPIO23",
            "chip_path": "/dev/gpiochip4",
            "line_offset": 7,
            "active_high": True,
            "physical_acceptance_claimed": False,
        }


class ManualClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def set(self, value: float) -> None:
        self.value = value


def _enabled_env_config(tempdir: str):
    return load_config(
        site_path=None,
        environ={},
        cli_overrides={
            "extensions.environment.enabled": True,
            "extensions.environment.socket_path": str(Path(tempdir) / "control.sock"),
            "extensions.environment.policy_path": str(Path(tempdir) / "policy.json"),
        },
    ).config.extensions.environment


class EnvironmentDaemonActivationTests(unittest.TestCase):
    def test_bounds_are_derived_from_static_config(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bounds = policy_bounds_from_config(_enabled_env_config(tempdir))
        self.assertEqual(bounds.temperature_min_c, -10.0)
        self.assertEqual(bounds.temperature_max_c, 60.0)
        self.assertEqual(bounds.minimum_hysteresis_c, 0.5)
        self.assertEqual(bounds.maximum_hysteresis_c, 15.0)

    def test_build_core_creates_default_policy_and_uses_injected_adapters_without_hardware_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            env = _enabled_env_config(tempdir)
            sensor = FakeSensor()
            actuator = FakeActuator()
            clock = ManualClock(10.0)
            core = build_environment_service_core(
                env,
                now=clock,
                sensor_factory=lambda _env: sensor,
                actuator_factory=lambda _env: actuator,
            )
            self.assertTrue(Path(env.policy_path).is_file())
            self.assertEqual(core.daemon_metadata()["hardware_backend"], "sht31+libgpiod")
            self.assertFalse(core.daemon_metadata()["physical_evidence"])
            status = core.handle(__import__("gonken_agent.environment.protocol", fromlist=["make_request"]).make_request("status.get"))
            self.assertFalse(status["physical_evidence"])
            self.assertFalse(status["capabilities"]["software_speed_control"])
            self.assertEqual(status["actuator_runtime_identity"]["status"], "RESOLVED")
            self.assertEqual(status["actuator_runtime_identity"]["logical_bcm"], 23)
            self.assertEqual(status["actuator_runtime_identity"]["chip_path"], "/dev/gpiochip4")
            self.assertEqual(status["actuator_runtime_identity"]["line_offset"], 7)
            self.assertFalse(status["actuator_runtime_identity"]["physical_acceptance_claimed"])
            for moment in (11.0, 12.0, 13.0):
                clock.set(moment)
                result = core.handle(__import__("gonken_agent.environment.protocol", fromlist=["make_request"]).make_request("sensor.read"))
            self.assertEqual(result["state"]["sensor_quality"], "ready")
            self.assertEqual(sensor.calls, 3)
            fan = core.handle(__import__("gonken_agent.environment.protocol", fromlist=["make_request"]).make_request("fan.set", {"power": "on"}))
            self.assertEqual(fan["state"]["fan_power"], "on")
            self.assertEqual(actuator.commands[-1], FanPower.ON)
            core.shutdown_safe_off()
            self.assertTrue(actuator.safe_off_called)
            self.assertTrue(actuator.closed)
            self.assertTrue(sensor.closed)

    def test_corrupt_policy_fails_closed_without_replacing_operator_file(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            env = _enabled_env_config(tempdir)
            policy_path = Path(env.policy_path)
            policy_path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(EnvironmentDaemonError) as caught:
                build_environment_service_core(
                    env,
                    sensor_factory=lambda _env: FakeSensor(),
                    actuator_factory=lambda _env: FakeActuator(),
                )
            self.assertEqual(caught.exception.code, "POLICY_INVALID")
            self.assertEqual(policy_path.read_text(encoding="utf-8"), "not-json")

    def test_disabled_config_refuses_core_build(self) -> None:
        env = load_config(site_path=None, environ={}).config.extensions.environment
        with self.assertRaises(EnvironmentDaemonError) as caught:
            build_environment_service_core(env)
        self.assertEqual(caught.exception.code, "ENVIRONMENT_DISABLED")

    def test_unix_server_uses_configured_socket_and_cleans_up_safe_off(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            env = _enabled_env_config(tempdir)
            actuator = FakeActuator()
            server = build_environment_unix_server(
                env,
                now=ManualClock(1.0),
                sensor_factory=lambda _env: FakeSensor(),
                actuator_factory=lambda _env: actuator,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                client = EnvironmentClient(env.socket_path, timeout_seconds=2.0)
                status = client.status()
                self.assertEqual(status["service"], "READY")
                self.assertFalse(status["physical_evidence"])
                self.assertFalse(status["capabilities"]["software_speed_control"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2.0)
            self.assertFalse(Path(env.socket_path).exists())
            self.assertTrue(actuator.safe_off_called)

    def test_cli_env_serve_check_builds_config_without_starting_socket_or_claiming_physical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            site = Path(tempdir) / "site.toml"
            site.write_text(
                "[extensions.environment]\n"
                "enabled = true\n"
                f"socket_path = \"{Path(tempdir) / 'control.sock'}\"\n"
                f"policy_path = \"{Path(tempdir) / 'policy.json'}\"\n",
                encoding="utf-8",
            )
            fake_core = SimpleNamespace(
                daemon_metadata=lambda: {"hardware_backend": "fake", "physical_evidence": False},
                shutdown_safe_off=lambda: None,
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch.object(cli, "build_environment_service_core", create=True, return_value=fake_core):
                # The CLI imports build_environment_service_core inside the command; patch the package-level symbol too.
                with mock.patch("gonken_agent.environment.build_environment_service_core", return_value=fake_core):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        result = cli.main(["env", "serve", "--site", str(site), "--check", "--json"])
            payload = json.loads(stdout.getvalue())
            self.assertEqual(result, 0, stderr.getvalue())
            self.assertEqual(payload["code"], "ENVIRONMENT_DAEMON_CONFIG_OK")
            self.assertFalse(payload["physical_evidence"])
            self.assertFalse(payload["hardware_toggled"])
            self.assertFalse(Path(tempdir, "control.sock").exists())


if __name__ == "__main__":
    unittest.main()
