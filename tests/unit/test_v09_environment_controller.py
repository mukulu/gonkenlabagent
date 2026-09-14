from __future__ import annotations

import inspect
import unittest

from gonken_agent.environment import EnvironmentMode, EnvironmentPolicy, FanPower, PolicyBounds, SensorQuality, SensorReading, TransitionReason
from gonken_agent.environment.controller import ControllerError, EnvironmentController


def reading(temp: float, *, now: float, rh: float = 60.0, crc_valid: bool = True, error_code: str | None = None) -> SensorReading:
    return SensorReading(
        temperature_c=temp if error_code is None else None,
        relative_humidity_pct=rh if error_code is None else None,
        observed_monotonic=now,
        sensor_address=0x44,
        crc_valid=crc_valid,
        error_code=error_code,
    )


class EnvironmentControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bounds = PolicyBounds()

    def policy(self, mode: EnvironmentMode = EnvironmentMode.AUTOMATIC, **kwargs: object) -> EnvironmentPolicy:
        base = EnvironmentPolicy.default().updated(bounds=self.bounds, mode=mode)
        if kwargs:
            base = base.updated(bounds=self.bounds, **kwargs)
        return base

    def test_controller_is_pure_and_boots_safe_off(self) -> None:
        source = inspect.getsource(__import__("gonken_agent.environment.controller", fromlist=["unused"]))
        self.assertNotIn("smbus", source)
        self.assertNotIn("gpiod", source)
        controller = EnvironmentController(policy=EnvironmentPolicy.default(), bounds=self.bounds, now_monotonic=100.0)
        self.assertEqual(controller.state.fan_power, FanPower.OFF)
        self.assertFalse(controller.state.semi_armed)
        self.assertEqual(controller.state.mode, EnvironmentMode.MANUAL)
        self.assertEqual(controller.state.last_transition_reason, TransitionReason.BOOT_SAFE_OFF)

    def test_manual_keeps_deliberate_actuator_state_independent_of_sensor_failure(self) -> None:
        controller = EnvironmentController(policy=EnvironmentPolicy.default(), bounds=self.bounds, now_monotonic=0.0)
        state = controller.set_fan_power(True, now_monotonic=1.0)
        self.assertEqual(state.fan_power, FanPower.ON)
        self.assertEqual(state.last_transition_reason, TransitionReason.USER_MANUAL_ON)

        for now in (2.0, 3.0, 4.0):
            state = controller.observe(reading(20.0, now=now), now_monotonic=now)
        self.assertEqual(state.sensor_quality, SensorQuality.READY)
        self.assertEqual(state.fan_power, FanPower.ON)

        stale = controller.tick(now_monotonic=20.0)
        self.assertEqual(stale.sensor_quality, SensorQuality.STALE)
        self.assertEqual(stale.fan_power, FanPower.ON)
        self.assertEqual(stale.mode, EnvironmentMode.MANUAL)

    def test_disabled_mode_rejects_on_and_keeps_safe_off(self) -> None:
        controller = EnvironmentController(policy=self.policy(EnvironmentMode.DISABLED), bounds=self.bounds, now_monotonic=0.0)
        self.assertEqual(controller.state.fan_power, FanPower.OFF)
        with self.assertRaisesRegex(ControllerError, "ENV_DISABLED"):
            controller.set_fan_power(True, now_monotonic=1.0)
        state = controller.set_fan_power(False, now_monotonic=2.0)
        self.assertEqual(state.fan_power, FanPower.OFF)
        self.assertEqual(state.last_transition_reason, TransitionReason.DISABLED_SAFE_OFF)

    def test_semi_automatic_never_auto_starts_but_auto_stops_after_user_start(self) -> None:
        policy = self.policy(EnvironmentMode.SEMI_AUTOMATIC, minimum_on_seconds=60, minimum_off_seconds=60)
        controller = EnvironmentController(policy=policy, bounds=self.bounds, now_monotonic=0.0)
        for now in (1.0, 2.0, 61.0):
            state = controller.observe(reading(31.0, now=now), now_monotonic=now)
        self.assertEqual(state.sensor_quality, SensorQuality.READY)
        self.assertEqual(state.fan_power, FanPower.OFF)
        self.assertFalse(state.semi_armed)

        state = controller.set_fan_power(True, now_monotonic=62.0)
        self.assertEqual(state.fan_power, FanPower.ON)
        self.assertTrue(state.semi_armed)
        self.assertEqual(state.last_transition_reason, TransitionReason.SEMI_USER_START)

        for now in (88.0, 89.0, 90.0):
            state = controller.observe(reading(24.0, now=now), now_monotonic=now)
        self.assertEqual(state.fan_power, FanPower.ON)
        self.assertEqual(state.last_decision_reason, TransitionReason.DWELL_HOLD)

        state = controller.observe(reading(24.0, now=123.0), now_monotonic=123.0)
        self.assertEqual(state.fan_power, FanPower.OFF)
        self.assertFalse(state.semi_armed)
        self.assertEqual(state.last_transition_reason, TransitionReason.SEMI_AUTO_STOP)

        state = controller.observe(reading(32.0, now=190.0), now_monotonic=190.0)
        self.assertEqual(state.fan_power, FanPower.OFF)
        self.assertFalse(state.semi_armed)

    def test_automatic_uses_recovery_samples_hysteresis_and_dwell(self) -> None:
        policy = self.policy(EnvironmentMode.AUTOMATIC, minimum_on_seconds=5, minimum_off_seconds=5)
        controller = EnvironmentController(policy=policy, bounds=self.bounds, now_monotonic=0.0)
        state = controller.observe(reading(31.0, now=1.0), now_monotonic=1.0)
        self.assertEqual(state.sensor_quality, SensorQuality.STARTING)
        state = controller.observe(reading(31.0, now=2.0), now_monotonic=2.0)
        self.assertEqual(state.fan_power, FanPower.OFF)
        state = controller.observe(reading(31.0, now=3.0), now_monotonic=3.0)
        self.assertEqual(state.sensor_quality, SensorQuality.READY)
        self.assertEqual(state.fan_power, FanPower.OFF)
        self.assertEqual(state.last_decision_reason, TransitionReason.DWELL_HOLD)

        state = controller.observe(reading(31.0, now=6.0), now_monotonic=6.0)
        self.assertEqual(state.fan_power, FanPower.ON)
        self.assertEqual(state.last_transition_reason, TransitionReason.AUTO_START_THRESHOLD)

        for now in (7.0, 8.0, 9.0):
            state = controller.observe(reading(24.0, now=now), now_monotonic=now)
        self.assertEqual(state.fan_power, FanPower.ON)
        self.assertEqual(state.last_decision_reason, TransitionReason.DWELL_HOLD)

        state = controller.observe(reading(24.0, now=12.0), now_monotonic=12.0)
        self.assertEqual(state.fan_power, FanPower.OFF)
        self.assertEqual(state.last_transition_reason, TransitionReason.AUTO_STOP_THRESHOLD)

    def test_auto_forces_safe_off_on_stale_sensor_and_requires_recovery_sequence(self) -> None:
        policy = self.policy(EnvironmentMode.AUTOMATIC, minimum_on_seconds=5, minimum_off_seconds=5)
        controller = EnvironmentController(policy=policy, bounds=self.bounds, now_monotonic=0.0)
        for now in (10.0, 11.0, 12.0):
            state = controller.observe(reading(31.0, now=now), now_monotonic=now)
        self.assertEqual(state.fan_power, FanPower.ON)

        stale = controller.tick(now_monotonic=23.0)
        self.assertEqual(stale.sensor_quality, SensorQuality.STALE)
        self.assertEqual(stale.fan_power, FanPower.OFF)
        self.assertEqual(stale.last_transition_reason, TransitionReason.SENSOR_STALE_SAFE_OFF)

        for now in (24.0, 25.0):
            state = controller.observe(reading(31.0, now=now), now_monotonic=now)
            self.assertEqual(state.sensor_quality, SensorQuality.STARTING)
            self.assertEqual(state.fan_power, FanPower.OFF)
        state = controller.observe(reading(31.0, now=26.0), now_monotonic=26.0)
        self.assertEqual(state.sensor_quality, SensorQuality.READY)
        self.assertEqual(state.fan_power, FanPower.OFF)
        self.assertEqual(state.last_decision_reason, TransitionReason.DWELL_HOLD)
        state = controller.observe(reading(31.0, now=29.0), now_monotonic=29.0)
        self.assertEqual(state.fan_power, FanPower.ON)
        self.assertEqual(state.last_transition_reason, TransitionReason.AUTO_START_THRESHOLD)

    def test_generic_on_or_off_in_auto_switches_to_manual_with_actual_state(self) -> None:
        controller = EnvironmentController(policy=self.policy(EnvironmentMode.AUTOMATIC), bounds=self.bounds, now_monotonic=0.0)
        state = controller.set_fan_power(True, now_monotonic=1.0)
        self.assertEqual(state.mode, EnvironmentMode.MANUAL)
        self.assertEqual(state.fan_power, FanPower.ON)
        self.assertEqual(state.last_transition_reason, TransitionReason.USER_MANUAL_ON)
        for now in (2.0, 3.0, 4.0, 30.0):
            state = controller.observe(reading(20.0, now=now), now_monotonic=now)
        self.assertEqual(state.mode, EnvironmentMode.MANUAL)
        self.assertEqual(state.fan_power, FanPower.ON)

    def test_policy_update_can_stop_running_auto_fan_without_auto_starting_semi(self) -> None:
        auto_policy = self.policy(EnvironmentMode.AUTOMATIC, start_c=30.0, stop_c=25.0, minimum_on_seconds=5, minimum_off_seconds=5)
        controller = EnvironmentController(policy=auto_policy, bounds=self.bounds, now_monotonic=0.0)
        for now in (10.0, 11.0, 12.0):
            state = controller.observe(reading(31.0, now=now), now_monotonic=now)
        self.assertEqual(state.fan_power, FanPower.ON)
        for now in (18.0, 19.0, 20.0):
            state = controller.observe(reading(27.0, now=now), now_monotonic=now)
        self.assertEqual(state.fan_power, FanPower.ON)

        updated = controller.policy.updated(bounds=self.bounds, stop_c=27.5)
        state = controller.update_policy(updated, now_monotonic=21.0)
        self.assertEqual(state.fan_power, FanPower.OFF)
        self.assertEqual(state.last_transition_reason, TransitionReason.POLICY_UPDATE_STOP_CONDITION)

        semi = updated.updated(bounds=self.bounds, mode=EnvironmentMode.SEMI_AUTOMATIC)
        state = controller.update_policy(semi, now_monotonic=22.0)
        self.assertEqual(state.mode, EnvironmentMode.SEMI_AUTOMATIC)
        self.assertEqual(state.fan_power, FanPower.OFF)
        self.assertFalse(state.semi_armed)
        for now in (30.0, 31.0, 32.0):
            state = controller.observe(reading(35.0, now=now), now_monotonic=now)
        self.assertEqual(state.fan_power, FanPower.OFF)


if __name__ == "__main__":
    unittest.main()
