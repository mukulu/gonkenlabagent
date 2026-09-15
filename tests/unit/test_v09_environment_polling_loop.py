from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from gonken_agent.config import load_config
from gonken_agent.environment import (
    EnvironmentController,
    EnvironmentDaemon,
    EnvironmentMode,
    EnvironmentPolicy,
    EnvironmentPollingLoop,
    EnvironmentServiceCore,
    FanCapability,
    FanPower,
    PolicyBounds,
    SensorReading,
    TransitionReason,
)
from gonken_agent.environment.protocol import make_request
from gonken_agent.environment.sensors import SensorAdapterError


class ManualClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def set(self, value: float) -> None:
        self.value = value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class FakeActuator:
    def __init__(self, *, fail_set_power: bool = False) -> None:
        self.fail_set_power = fail_set_power
        self.commands: list[FanPower] = []
        self.safe_off_calls = 0
        self.closed = False

    def set_power(self, power) -> None:
        if self.fail_set_power:
            raise RuntimeError("relay write failed")
        self.commands.append(FanPower.parse(power))

    def safe_off(self) -> None:
        self.safe_off_calls += 1
        self.commands.append(FanPower.OFF)

    def close(self) -> None:
        self.closed = True

    def capabilities(self) -> FanCapability:
        return FanCapability(power_control=True, software_speed_control=False, fan_motion_observed=False)


class FakeSensor:
    def __init__(self, readings: list[SensorReading]) -> None:
        self.readings = list(readings)
        self.calls = 0
        self.closed = False

    def read(self, *, now_monotonic: float) -> SensorReading:
        self.calls += 1
        if self.readings:
            sample = self.readings.pop(0)
        else:
            sample = SensorReading(28.5, 55.0, observed_monotonic=now_monotonic, sensor_address=0x44)
        return SensorReading(
            sample.temperature_c,
            sample.relative_humidity_pct,
            observed_monotonic=now_monotonic,
            sensor_address=sample.sensor_address,
            source_backend=sample.source_backend,
            crc_valid=sample.crc_valid,
            error_code=sample.error_code,
        )

    def close(self) -> None:
        self.closed = True


def _core(
    *,
    clock: ManualClock,
    policy: EnvironmentPolicy,
    sensor_read=None,
    sensor_adapter=None,
    actuator=None,
    valid_samples_to_recover: int = 1,
) -> EnvironmentServiceCore:
    bounds = PolicyBounds()
    controller = EnvironmentController(
        policy=policy.validated(bounds=bounds),
        bounds=bounds,
        now_monotonic=clock(),
        valid_samples_to_recover=valid_samples_to_recover,
    )
    return EnvironmentServiceCore(
        controller=controller,
        bounds=bounds,
        sensor_read=sensor_read,
        sensor_adapter=sensor_adapter,
        fan_actuator=actuator,
        now=clock,
    )


class EnvironmentPollingLoopTests(unittest.TestCase):
    def test_poll_once_reads_sensor_and_applies_auto_transition(self) -> None:
        clock = ManualClock(100.0)
        policy = EnvironmentPolicy.default().updated(
            bounds=PolicyBounds(),
            mode=EnvironmentMode.AUTOMATIC,
            minimum_on_seconds=5,
            minimum_off_seconds=5,
        )
        actuator = FakeActuator()
        source = FakeSensor([SensorReading(29.1, 57.0, observed_monotonic=clock(), sensor_address=0x44)])
        core = _core(clock=clock, policy=policy, sensor_read=source.read, actuator=actuator)
        clock.advance(6.0)

        result = core.poll_once()

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"]["sensor_quality"], "ready")
        self.assertEqual(result["state"]["fan_power"], FanPower.ON.value)
        self.assertEqual(result["state"]["last_transition_reason"], TransitionReason.AUTO_START_THRESHOLD.value)
        self.assertEqual(actuator.commands[-1], FanPower.ON)
        self.assertEqual(core.daemon_metadata()["poll_count"], 1)
        events = core.handle(make_request("events.get", {"limit": 4}))
        controller_events = [event for event in events["events"] if event.get("event_type") == "controller.transition"]
        self.assertEqual(controller_events[-1]["detail"]["reason"], TransitionReason.AUTO_START_THRESHOLD.value)
        self.assertFalse(controller_events[-1]["physical_evidence"])
        self.assertFalse(result["physical_evidence"])

    def test_poll_once_converts_sensor_exception_to_degraded_safe_off(self) -> None:
        clock = ManualClock(20.0)
        bounds = PolicyBounds()
        policy = EnvironmentPolicy.default().updated(bounds=bounds, mode=EnvironmentMode.SEMI_AUTOMATIC)
        actuator = FakeActuator()
        core = _core(
            clock=clock,
            policy=policy,
            sensor_read=lambda *, now_monotonic: (_ for _ in ()).throw(SensorAdapterError("SENSOR_UNAVAILABLE", "missing")),
            actuator=actuator,
        )
        core.controller.set_fan_power(FanPower.ON, now_monotonic=clock())

        result = core.poll_once()

        self.assertTrue(result["ok"])
        self.assertEqual(result["reading"]["error_code"], "SENSOR_UNAVAILABLE")
        self.assertEqual(result["state"]["fan_power"], FanPower.OFF.value)
        self.assertEqual(result["state"]["last_transition_reason"], TransitionReason.SENSOR_STALE_SAFE_OFF.value)
        self.assertEqual(actuator.commands[-1], FanPower.OFF)
        self.assertEqual(core.daemon_metadata()["last_poll_error_code"], "SENSOR_UNAVAILABLE")

    def test_poll_once_records_actuator_error_without_killing_daemon_path(self) -> None:
        clock = ManualClock(50.0)
        policy = EnvironmentPolicy.default().updated(
            bounds=PolicyBounds(),
            mode=EnvironmentMode.AUTOMATIC,
            minimum_on_seconds=5,
            minimum_off_seconds=5,
        )
        actuator = FakeActuator(fail_set_power=True)
        source = FakeSensor([SensorReading(30.0, 58.0, observed_monotonic=clock(), sensor_address=0x44)])
        core = _core(clock=clock, policy=policy, sensor_read=source.read, actuator=actuator)
        clock.advance(6.0)

        result = core.poll_once()

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "ACTUATOR_UNAVAILABLE")
        self.assertEqual(result["state"]["fan_power"], FanPower.OFF.value)
        self.assertEqual(result["state"]["last_transition_reason"], TransitionReason.ACTUATOR_ERROR_SAFE_OFF.value)
        self.assertEqual(actuator.safe_off_calls, 1)
        self.assertEqual(core.daemon_metadata()["poll_error_count"], 1)
        self.assertEqual(core.daemon_metadata()["last_poll_error_code"], "ACTUATOR_UNAVAILABLE")

    def test_background_polling_loop_is_bounded_and_stoppable(self) -> None:
        clock = ManualClock(0.0)
        policy = EnvironmentPolicy.default().updated(bounds=PolicyBounds(), mode=EnvironmentMode.MANUAL)
        source = FakeSensor([SensorReading(27.0, 50.0, observed_monotonic=0.0, sensor_address=0x44)])
        core = _core(clock=clock, policy=policy, sensor_read=source.read, actuator=FakeActuator())
        loop = EnvironmentPollingLoop(core, interval_seconds=0.01)

        loop.start()
        try:
            time.sleep(0.04)
        finally:
            loop.stop(timeout_seconds=1.0)

        self.assertFalse(loop.running)
        self.assertGreaterEqual(core.daemon_metadata()["poll_count"], 1)
        self.assertIsNotNone(loop.last_result)

    def test_environment_daemon_from_config_attaches_polling_loop_without_physical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            env = load_config(
                site_path=None,
                environ={},
                cli_overrides={
                    "extensions.environment.enabled": True,
                    "extensions.environment.poll_interval_seconds": 0.5,
                    "extensions.environment.socket_path": str(Path(tempdir) / "control.sock"),
                    "extensions.environment.policy_path": str(Path(tempdir) / "policy.json"),
                },
            ).config.extensions.environment
            clock = ManualClock(10.0)
            sensor = FakeSensor([SensorReading(27.0, 50.0, observed_monotonic=10.0, sensor_address=0x44)])
            actuator = FakeActuator()
            daemon = EnvironmentDaemon.from_config(
                env,
                now=clock,
                sensor_factory=lambda _env: sensor,
                actuator_factory=lambda _env: actuator,
            )
            try:
                self.assertIsNotNone(daemon.polling_loop)
                self.assertEqual(daemon.polling_loop.interval_seconds, 0.5)
                result = daemon.poll_once()
                self.assertTrue(result["ok"])
                self.assertFalse(result["physical_evidence"])
                self.assertEqual(daemon.server.core.daemon_metadata()["poll_count"], 1)
            finally:
                daemon.close()
            self.assertFalse(Path(env.socket_path).exists())
            self.assertTrue(actuator.safe_off_calls >= 1)
            self.assertTrue(sensor.closed)


if __name__ == "__main__":
    unittest.main()
