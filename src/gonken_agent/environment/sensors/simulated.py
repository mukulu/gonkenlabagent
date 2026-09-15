"""Simulated sensor adapter for V09 simulation/HIL workflows."""

from __future__ import annotations

from ..domain import SensorReading
from ..simulation import SimulationState


class SimulatedEnvironmentSensor:
    """A daemon-owned persistent simulated temperature/RH source."""

    def __init__(self, state: SimulationState) -> None:
        self.state = state
        self.closed = False

    def read(self, *, now_monotonic: float) -> SensorReading:
        if self.closed:
            return SensorReading(
                temperature_c=None,
                relative_humidity_pct=None,
                observed_monotonic=float(now_monotonic),
                sensor_address=None,
                source_backend="simulated",
                crc_valid=False,
                error_code="SENSOR_UNAVAILABLE",
                physical_evidence=False,
            )
        return self.state.simulated_sensor_reading(now_monotonic=float(now_monotonic))

    def close(self) -> None:
        self.closed = True
