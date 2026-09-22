"""Pure deterministic V09 room-environment controller.

This module intentionally owns only state-machine decisions.  It does not import
I2C, GPIO, audio, systemd, Ollama, shell, or network libraries.  Later adapter
and service layers may translate these state transitions into hardware actions,
but the policy semantics are testable on a normal host with fake readings.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from statistics import median

from .domain import (
    EnvironmentMode,
    FanCapability,
    FanPower,
    SensorQuality,
    SensorReading,
    TransitionReason,
    PolicyBounds,
)
from .policy import EnvironmentPolicy


class ControllerError(ValueError):
    """A deterministic controller command was rejected before actuation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True, slots=True)
class ControllerState:
    """Truthful in-memory controller snapshot.

    ``fan_power`` is the software relay-power boundary.  It does not prove fan
    blade motion or programmable speed for the current ELUTENG + relay design.
    """

    policy: EnvironmentPolicy
    fan_power: FanPower
    semi_armed: bool
    sensor_quality: SensorQuality
    last_reading: SensorReading | None
    control_temperature_c: float | None
    valid_sample_count: int
    last_transition_reason: TransitionReason
    last_decision_reason: TransitionReason
    last_transition_monotonic: float
    capability: FanCapability = FanCapability()

    @property
    def mode(self) -> EnvironmentMode:
        return self.policy.mode

    def as_dict(self, *, now_monotonic: float | None = None, stale_after_seconds: float | None = None) -> dict[str, object]:
        reading = None
        if self.last_reading is not None:
            reading = self.last_reading.as_dict(
                now_monotonic=now_monotonic,
                stale_after_seconds=stale_after_seconds,
            )
        return {
            "mode": self.mode.value,
            "fan_power": self.fan_power.value,
            "semi_armed": self.semi_armed,
            "sensor_quality": self.sensor_quality.value,
            "control_temperature_c": self.control_temperature_c,
            "valid_sample_count": self.valid_sample_count,
            "last_transition_reason": self.last_transition_reason.value,
            "last_decision_reason": self.last_decision_reason.value,
            "last_transition_monotonic": self.last_transition_monotonic,
            "capability": self.capability.as_dict(),
            "policy": self.policy.to_mapping(),
            "last_reading": reading,
        }


class EnvironmentController:
    """Deterministic room-fan controller for MANUAL/SEMI/AUTO/DISABLED modes."""

    def __init__(
        self,
        *,
        policy: EnvironmentPolicy,
        bounds: PolicyBounds,
        now_monotonic: float = 0.0,
        stale_after_seconds: float = 10.0,
        valid_samples_to_recover: int = 3,
        control_sample_count: int = 3,
    ) -> None:
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        if valid_samples_to_recover < 1:
            raise ValueError("valid_samples_to_recover must be at least 1")
        if control_sample_count < 1:
            raise ValueError("control_sample_count must be at least 1")
        self.bounds = bounds
        self.policy = policy.validated(bounds=bounds)
        self.stale_after_seconds = float(stale_after_seconds)
        self.valid_samples_to_recover = int(valid_samples_to_recover)
        self.control_sample_count = int(control_sample_count)
        self._valid_readings: list[SensorReading] = []
        self._valid_streak = 0
        self._state = ControllerState(
            policy=self.policy,
            fan_power=FanPower.OFF,
            semi_armed=False,
            sensor_quality=SensorQuality.STARTING,
            last_reading=None,
            control_temperature_c=None,
            valid_sample_count=0,
            last_transition_reason=TransitionReason.BOOT_SAFE_OFF,
            last_decision_reason=TransitionReason.BOOT_SAFE_OFF,
            last_transition_monotonic=float(now_monotonic),
        )
        if self.policy.mode == EnvironmentMode.DISABLED:
            self._state = replace(
                self._state,
                sensor_quality=SensorQuality.STARTING,
                last_transition_reason=TransitionReason.DISABLED_SAFE_OFF,
                last_decision_reason=TransitionReason.DISABLED_SAFE_OFF,
            )

    @property
    def state(self) -> ControllerState:
        return self._state

    def observe(self, reading: SensorReading, *, now_monotonic: float) -> ControllerState:
        """Record one sensor observation and run any permitted autonomous decision."""

        quality = reading.quality(
            now_monotonic=now_monotonic,
            stale_after_seconds=self.stale_after_seconds,
        )
        recovered = False
        if quality == SensorQuality.READY:
            self._valid_streak += 1
            self._valid_readings.append(reading)
            self._valid_readings = self._valid_readings[-self.control_sample_count :]
            if self._valid_streak < self.valid_samples_to_recover:
                quality = SensorQuality.STARTING
            elif self._state.sensor_quality != SensorQuality.READY:
                recovered = True
        else:
            self._clear_valid_samples()

        previous_decision_reason = self._state.last_decision_reason
        self._state = replace(
            self._state,
            policy=self.policy,
            sensor_quality=quality,
            last_reading=reading,
            control_temperature_c=self._control_temperature(),
            valid_sample_count=self._valid_streak,
        )
        self._evaluate(now_monotonic=float(now_monotonic), context="sensor")
        if recovered and self._state.last_decision_reason == previous_decision_reason:
            self._state = replace(self._state, last_decision_reason=TransitionReason.SENSOR_RECOVERED)
        return self._state

    def tick(self, *, now_monotonic: float) -> ControllerState:
        """Recompute staleness/autonomous decisions without adding a sample."""

        quality = SensorQuality.STARTING
        if self._state.last_reading is not None:
            quality = self._state.last_reading.quality(
                now_monotonic=now_monotonic,
                stale_after_seconds=self.stale_after_seconds,
            )
            if quality == SensorQuality.READY and self._valid_streak < self.valid_samples_to_recover:
                quality = SensorQuality.STARTING
        if quality in {SensorQuality.STALE, SensorQuality.FAILED, SensorQuality.UNAVAILABLE}:
            self._clear_valid_samples()
            control_temperature: float | None = None
            valid_count = 0
        else:
            control_temperature = self._control_temperature()
            valid_count = self._valid_streak
        self._state = replace(
            self._state,
            sensor_quality=quality,
            control_temperature_c=control_temperature,
            valid_sample_count=valid_count,
        )
        return self._evaluate(now_monotonic=float(now_monotonic), context="tick")

    def set_fan_power(self, on: bool | str | FanPower, *, now_monotonic: float) -> ControllerState:
        """Apply an explicit operator power command with mode-specific semantics."""

        requested = FanPower.parse(on)
        now = float(now_monotonic)
        if self.policy.mode == EnvironmentMode.DISABLED:
            if requested == FanPower.ON:
                raise ControllerError("ENV_DISABLED", "fan power cannot be enabled while environment control is disabled")
            return self._transition(FanPower.OFF, semi_armed=False, reason=TransitionReason.DISABLED_SAFE_OFF, now_monotonic=now)

        if self.policy.mode == EnvironmentMode.AUTOMATIC:
            self.policy = self.policy.updated(bounds=self.bounds, mode=EnvironmentMode.MANUAL)
            reason = TransitionReason.USER_MANUAL_ON if requested == FanPower.ON else TransitionReason.USER_MANUAL_OFF
            return self._transition(requested, semi_armed=False, reason=reason, now_monotonic=now, policy=self.policy)

        if self.policy.mode == EnvironmentMode.SEMI_AUTOMATIC:
            if requested == FanPower.ON:
                return self._transition(FanPower.ON, semi_armed=True, reason=TransitionReason.SEMI_USER_START, now_monotonic=now)
            return self._transition(FanPower.OFF, semi_armed=False, reason=TransitionReason.USER_MANUAL_OFF, now_monotonic=now)

        reason = TransitionReason.USER_MANUAL_ON if requested == FanPower.ON else TransitionReason.USER_MANUAL_OFF
        return self._transition(requested, semi_armed=False, reason=reason, now_monotonic=now)

    def scheduled_fan_power(self, power: FanPower, *, now_monotonic: float,
                            expired: bool = False) -> ControllerState:
        """Internal scheduler adapter. Dwell is enforced by the scheduler."""
        previous = self._state.fan_power
        self.set_fan_power(power, now_monotonic=now_monotonic)
        reason = (TransitionReason.TIMER_EXPIRED_SAFE_OFF if expired else
                  TransitionReason.TIMER_ON if power == FanPower.ON else TransitionReason.TIMER_OFF)
        values = {"last_decision_reason": reason}
        if self._state.fan_power != previous:
            values["last_transition_reason"] = reason
        self._state = replace(self._state, **values)
        return self._state

    def set_mode(self, mode: str | EnvironmentMode, *, now_monotonic: float) -> ControllerState:
        next_policy = self.policy.updated(bounds=self.bounds, mode=EnvironmentMode.parse(mode))
        return self.update_policy(next_policy, now_monotonic=now_monotonic)

    def update_policy(self, policy: EnvironmentPolicy, *, now_monotonic: float) -> ControllerState:
        """Install a validated policy and immediately reconcile permitted effects."""

        self.policy = policy.validated(bounds=self.bounds)
        if self.policy.mode == EnvironmentMode.DISABLED:
            return self._transition(FanPower.OFF, semi_armed=False, reason=TransitionReason.DISABLED_SAFE_OFF, now_monotonic=float(now_monotonic), policy=self.policy)
        if self.policy.mode == EnvironmentMode.SEMI_AUTOMATIC and self._state.fan_power == FanPower.OFF:
            self._state = replace(self._state, semi_armed=False)
        self._state = replace(self._state, policy=self.policy, last_decision_reason=TransitionReason.USER_MODE_CHANGE)
        return self._evaluate(now_monotonic=float(now_monotonic), context="policy_update")

    def shutdown(self, *, now_monotonic: float) -> ControllerState:
        return self._transition(FanPower.OFF, semi_armed=False, reason=TransitionReason.SHUTDOWN_SAFE_OFF, now_monotonic=float(now_monotonic))

    def actuator_error_safe_off(self, *, now_monotonic: float) -> ControllerState:
        """Record a fail-closed actuator error and force the logical state OFF."""

        return self._transition(
            FanPower.OFF,
            semi_armed=False,
            reason=TransitionReason.ACTUATOR_ERROR_SAFE_OFF,
            now_monotonic=float(now_monotonic),
        )

    def _evaluate(self, *, now_monotonic: float, context: str) -> ControllerState:
        mode = self.policy.mode
        if mode == EnvironmentMode.DISABLED:
            if self._state.fan_power == FanPower.OFF and not self._state.semi_armed:
                return self._decision(TransitionReason.DISABLED_SAFE_OFF)
            return self._transition(FanPower.OFF, semi_armed=False, reason=TransitionReason.DISABLED_SAFE_OFF, now_monotonic=now_monotonic)
        if mode == EnvironmentMode.MANUAL:
            return self._state

        if self._state.sensor_quality in {SensorQuality.STALE, SensorQuality.FAILED, SensorQuality.UNAVAILABLE}:
            if self._state.fan_power == FanPower.ON or self._state.semi_armed:
                return self._transition(
                    FanPower.OFF,
                    semi_armed=False,
                    reason=TransitionReason.SENSOR_STALE_SAFE_OFF,
                    now_monotonic=now_monotonic,
                )
            return self._decision(TransitionReason.SENSOR_STALE_SAFE_OFF)
        if self._state.sensor_quality != SensorQuality.READY or self._state.control_temperature_c is None:
            return self._state

        temperature = self._state.control_temperature_c
        if mode == EnvironmentMode.AUTOMATIC:
            if self._state.fan_power == FanPower.OFF and temperature >= self.policy.start_c:
                if self._dwell_elapsed(now_monotonic, self.policy.minimum_off_seconds):
                    return self._transition(
                        FanPower.ON,
                        semi_armed=False,
                        reason=TransitionReason.AUTO_START_THRESHOLD,
                        now_monotonic=now_monotonic,
                    )
                return self._decision(TransitionReason.DWELL_HOLD)
            if self._state.fan_power == FanPower.ON and temperature <= self.policy.stop_c:
                if self._dwell_elapsed(now_monotonic, self.policy.minimum_on_seconds):
                    reason = (
                        TransitionReason.POLICY_UPDATE_STOP_CONDITION
                        if context == "policy_update"
                        else TransitionReason.AUTO_STOP_THRESHOLD
                    )
                    return self._transition(
                        FanPower.OFF,
                        semi_armed=False,
                        reason=reason,
                        now_monotonic=now_monotonic,
                    )
                return self._decision(TransitionReason.DWELL_HOLD)
            return self._state

        if mode == EnvironmentMode.SEMI_AUTOMATIC:
            if self._state.fan_power == FanPower.ON and self._state.semi_armed and temperature <= self.policy.stop_c:
                if self._dwell_elapsed(now_monotonic, self.policy.minimum_on_seconds):
                    reason = (
                        TransitionReason.POLICY_UPDATE_STOP_CONDITION
                        if context == "policy_update"
                        else TransitionReason.SEMI_AUTO_STOP
                    )
                    return self._transition(
                        FanPower.OFF,
                        semi_armed=False,
                        reason=reason,
                        now_monotonic=now_monotonic,
                    )
                return self._decision(TransitionReason.DWELL_HOLD)
            return self._state

        return self._state

    def _transition(
        self,
        fan_power: FanPower,
        *,
        semi_armed: bool,
        reason: TransitionReason,
        now_monotonic: float,
        policy: EnvironmentPolicy | None = None,
    ) -> ControllerState:
        selected_policy = self.policy if policy is None else policy
        self.policy = selected_policy
        self._state = replace(
            self._state,
            policy=selected_policy,
            fan_power=fan_power,
            semi_armed=semi_armed,
            last_transition_reason=reason,
            last_decision_reason=reason,
            last_transition_monotonic=float(now_monotonic),
        )
        return self._state

    def _decision(self, reason: TransitionReason) -> ControllerState:
        self._state = replace(self._state, last_decision_reason=reason)
        return self._state

    def _dwell_elapsed(self, now_monotonic: float, required_seconds: int) -> bool:
        return (float(now_monotonic) - self._state.last_transition_monotonic) >= required_seconds

    def _control_temperature(self) -> float | None:
        values = [reading.temperature_c for reading in self._valid_readings if reading.temperature_c is not None]
        if not values:
            return None
        return float(median(values))

    def _clear_valid_samples(self) -> None:
        self._valid_readings.clear()
        self._valid_streak = 0
