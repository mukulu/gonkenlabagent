"""Daemon-owned simulation state for V09 environment/HIL workflows.

Simulation state is deliberately separate from static TOML configuration and
mutable fan policy.  It is normally ephemeral, belongs to the environment daemon,
and never proves physical SHT31, relay, fan or blade-motion behavior.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from math import isfinite
from time import monotonic
from typing import Callable

from .domain import FanPower, SensorReading

SIMULATION_SENSOR_FAULTS = frozenset({"unavailable", "read_error", "crc_error", "stale"})
SIMULATION_ACTUATOR_BEHAVIORS = frozenset({"normal", "unavailable", "fail_next_write"})


class SimulationStateError(RuntimeError):
    """A simulation operation was invalid or cannot be applied safely."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    sequence: int
    event_type: str
    generation: int
    monotonic: float
    detail: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "event_type": self.event_type,
            "generation": self.generation,
            "monotonic": self.monotonic,
            "detail": dict(self.detail),
        }


class SimulationState:
    """Thread-safe daemon-owned simulation state.

    The state is intentionally minimal: current modeled sensor value/fault and
    current modeled actuator behavior/power.  It is not persisted to the policy
    file and should be recreated on daemon start unless a future checkpoint adds
    a separately justified persistence contract.
    """

    def __init__(
        self,
        *,
        session_id: str | None = None,
        event_history_limit: int = 128,
        now: Callable[[], float] = monotonic,
    ) -> None:
        if isinstance(event_history_limit, bool) or not isinstance(event_history_limit, int):
            raise SimulationStateError("SIMULATION_INPUT_INVALID", "event_history_limit must be an integer")
        if not 1 <= event_history_limit <= 1000:
            raise SimulationStateError("SIMULATION_INPUT_INVALID", "event_history_limit must be between 1 and 1000")
        self.session_id = uuid.uuid4().hex if session_id is None else str(session_id)
        self.event_history_limit = event_history_limit
        self._now = now
        self._lock = threading.RLock()
        self._generation = 0
        self._sequence = 0
        self._last_update_monotonic: float | None = None
        self._sensor_temperature_c: float | None = None
        self._sensor_humidity_pct: float | None = None
        self._sensor_fault: str | None = None
        self._sensor_stale_age_seconds: float | None = None
        self._actuator_behavior = "normal"
        self._actuator_commanded_power = FanPower.OFF
        self._actuator_modeled_power = FanPower.OFF
        self._events: list[SimulationEvent] = []
        self._record("reset", {"scope": "initial"})

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @property
    def actuator_behavior(self) -> str:
        with self._lock:
            return self._actuator_behavior

    @property
    def actuator_commanded_power(self) -> FanPower:
        with self._lock:
            return self._actuator_commanded_power

    @property
    def actuator_modeled_power(self) -> FanPower:
        with self._lock:
            return self._actuator_modeled_power

    def reset_all(self) -> None:
        with self._lock:
            self._sensor_temperature_c = None
            self._sensor_humidity_pct = None
            self._sensor_fault = None
            self._sensor_stale_age_seconds = None
            self._actuator_behavior = "normal"
            self._actuator_commanded_power = FanPower.OFF
            self._actuator_modeled_power = FanPower.OFF
            self._record("reset", {"scope": "all"})

    def set_sensor(self, *, temperature_c: float, relative_humidity_pct: float) -> None:
        temperature = _finite_float(temperature_c, "temperature_c")
        humidity = _finite_float(relative_humidity_pct, "relative_humidity_pct")
        if not -50.0 <= temperature <= 100.0:
            raise SimulationStateError("SIMULATION_INPUT_INVALID", "temperature_c must be between -50 and 100")
        if not 0.0 <= humidity <= 100.0:
            raise SimulationStateError("SIMULATION_INPUT_INVALID", "relative_humidity_pct must be between 0 and 100")
        with self._lock:
            self._sensor_temperature_c = temperature
            self._sensor_humidity_pct = humidity
            self._sensor_fault = None
            self._sensor_stale_age_seconds = None
            self._record(
                "sensor.set",
                {"temperature_c": temperature, "relative_humidity_pct": humidity},
            )

    def fault_sensor(self, *, fault: str, stale_age_seconds: float | None = None) -> None:
        selected_fault = _normalize_sensor_fault(fault)
        selected_age: float | None = None
        if selected_fault == "stale":
            selected_age = 30.0 if stale_age_seconds is None else _finite_float(stale_age_seconds, "age_seconds")
            if selected_age < 0.0:
                raise SimulationStateError("SIMULATION_INPUT_INVALID", "age_seconds must be non-negative")
        elif stale_age_seconds is not None:
            raise SimulationStateError("SIMULATION_INPUT_INVALID", "age_seconds is only valid for stale fault")
        with self._lock:
            self._sensor_fault = selected_fault
            self._sensor_stale_age_seconds = selected_age
            self._record("sensor.fault", {"fault": selected_fault, "age_seconds": selected_age})

    def reset_sensor(self) -> None:
        with self._lock:
            self._sensor_temperature_c = None
            self._sensor_humidity_pct = None
            self._sensor_fault = None
            self._sensor_stale_age_seconds = None
            self._record("sensor.reset", {})

    def set_actuator_behavior(self, behavior: str) -> None:
        selected = _normalize_actuator_behavior(behavior)
        with self._lock:
            self._actuator_behavior = selected
            self._record("actuator.behavior", {"behavior": selected})

    def reset_actuator(self) -> None:
        with self._lock:
            self._actuator_behavior = "normal"
            self._actuator_commanded_power = FanPower.OFF
            self._actuator_modeled_power = FanPower.OFF
            self._record("actuator.reset", {})

    def simulated_sensor_reading(self, *, now_monotonic: float) -> SensorReading:
        with self._lock:
            fault = self._sensor_fault
            temperature = self._sensor_temperature_c
            humidity = self._sensor_humidity_pct
            stale_age = self._sensor_stale_age_seconds
        now_value = float(now_monotonic)
        if fault in {"unavailable", "read_error"}:
            return SensorReading(
                temperature_c=None,
                relative_humidity_pct=None,
                observed_monotonic=now_value,
                sensor_address=None,
                source_backend="simulated",
                crc_valid=False,
                error_code="SENSOR_UNAVAILABLE" if fault == "unavailable" else "SENSOR_READ_FAILED",
                physical_evidence=False,
            )
        if fault == "crc_error":
            return SensorReading(
                temperature_c=None,
                relative_humidity_pct=None,
                observed_monotonic=now_value,
                sensor_address=None,
                source_backend="simulated",
                crc_valid=False,
                error_code="SENSOR_CRC_FAILED",
                physical_evidence=False,
            )
        if temperature is None or humidity is None:
            return SensorReading(
                temperature_c=None,
                relative_humidity_pct=None,
                observed_monotonic=now_value,
                sensor_address=None,
                source_backend="simulated",
                crc_valid=True,
                error_code="SENSOR_UNAVAILABLE",
                physical_evidence=False,
            )
        observed = now_value
        if fault == "stale":
            observed = now_value - (30.0 if stale_age is None else stale_age)
        return SensorReading(
            temperature_c=temperature,
            relative_humidity_pct=humidity,
            observed_monotonic=observed,
            sensor_address=None,
            source_backend="simulated",
            crc_valid=True,
            error_code=None,
            physical_evidence=False,
        )

    def set_actuator_power(self, power: FanPower | str | bool) -> None:
        requested = FanPower.parse(power)
        with self._lock:
            if self._actuator_behavior == "unavailable":
                raise SimulationStateError("ACTUATOR_UNAVAILABLE", "simulated actuator is unavailable")
            if self._actuator_behavior == "fail_next_write":
                self._actuator_behavior = "normal"
                self._record("actuator.fail_next_write", {"requested_power": requested.value})
                raise SimulationStateError("ACTUATOR_UNAVAILABLE", "simulated actuator failed next write")
            self._actuator_commanded_power = requested
            self._actuator_modeled_power = requested
            self._record("actuator.set_power", {"power": requested.value})

    def force_actuator_off(self) -> None:
        with self._lock:
            self._actuator_commanded_power = FanPower.OFF
            self._actuator_modeled_power = FanPower.OFF
            self._record("actuator.safe_off", {"power": FanPower.OFF.value})

    def as_dict(self) -> dict[str, object]:
        with self._lock:
            return {
                "simulation_session_id": self.session_id,
                "simulation_generation": self._generation,
                "last_simulation_update_monotonic": self._last_update_monotonic,
                "sensor": {
                    "temperature_c": self._sensor_temperature_c,
                    "relative_humidity_pct": self._sensor_humidity_pct,
                    "fault": self._sensor_fault,
                    "stale_age_seconds": self._sensor_stale_age_seconds,
                    "source_backend": "simulated",
                    "physical_evidence": False,
                },
                "actuator": {
                    "behavior": self._actuator_behavior,
                    "commanded_power": self._actuator_commanded_power.value,
                    "modeled_power": self._actuator_modeled_power.value,
                    "source_backend": "simulated",
                    "software_speed_control": False,
                    "fan_motion_observed": False,
                    "physical_evidence": False,
                },
            }

    def events(self, *, limit: int | None = None) -> list[dict[str, object]]:
        with self._lock:
            selected = self._events if limit is None else self._events[-max(0, int(limit)):]
            return [event.as_dict() for event in selected]

    def _record(self, event_type: str, detail: dict[str, object]) -> None:
        now_value = float(self._now())
        self._generation += 1
        self._sequence += 1
        self._last_update_monotonic = now_value
        self._events.append(
            SimulationEvent(
                sequence=self._sequence,
                event_type=event_type,
                generation=self._generation,
                monotonic=now_value,
                detail=dict(detail),
            )
        )
        if len(self._events) > self.event_history_limit:
            del self._events[: len(self._events) - self.event_history_limit]


def classify_evidence_mode(*, sensor_backend: str, actuator_backend: str) -> str:
    sensor = sensor_backend.strip().lower()
    actuator = actuator_backend.strip().lower()
    sensor_simulated = sensor == "simulated"
    actuator_simulated = actuator == "simulated"
    if sensor_simulated and actuator_simulated:
        return "HOST_SIMULATION"
    if sensor_simulated and not actuator_simulated:
        return "TARGET_HYBRID_SENSOR_SIMULATED"
    if actuator_simulated and not sensor_simulated:
        return "TARGET_HYBRID_ACTUATOR_SIMULATED"
    return "TARGET_PHYSICAL"


def _finite_float(value: float | int, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulationStateError("SIMULATION_INPUT_INVALID", f"{name} must be a finite number")
    selected = float(value)
    if not isfinite(selected):
        raise SimulationStateError("SIMULATION_INPUT_INVALID", f"{name} must be finite")
    return selected


def _normalize_sensor_fault(value: str) -> str:
    if not isinstance(value, str):
        raise SimulationStateError("SIMULATION_FAULT_INVALID", "sensor fault must be a string")
    normalized = value.strip().lower().replace("-", "_")
    if normalized not in SIMULATION_SENSOR_FAULTS:
        raise SimulationStateError("SIMULATION_FAULT_INVALID", f"unsupported sensor fault: {value}")
    return normalized


def _normalize_actuator_behavior(value: str) -> str:
    if not isinstance(value, str):
        raise SimulationStateError("SIMULATION_FAULT_INVALID", "actuator behavior must be a string")
    normalized = value.strip().lower().replace("-", "_")
    if normalized not in SIMULATION_ACTUATOR_BEHAVIORS:
        raise SimulationStateError("SIMULATION_FAULT_INVALID", f"unsupported actuator behavior: {value}")
    return normalized
