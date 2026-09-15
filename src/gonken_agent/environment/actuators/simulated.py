"""Simulated fan actuator adapter for V09 simulation/HIL workflows."""

from __future__ import annotations

from ..domain import FanCapability, FanPower
from ..simulation import SimulationState, SimulationStateError
from .base import ActuatorAdapterError


class SimulatedFanActuator:
    """Power-only simulated actuator that never imports or touches libgpiod."""

    def __init__(self, state: SimulationState) -> None:
        self.state = state
        self.closed = False

    @property
    def commanded_power(self) -> FanPower:
        return self.state.actuator_commanded_power

    @property
    def modeled_power(self) -> FanPower:
        return self.state.actuator_modeled_power

    def set_power(self, power: FanPower | bool | str) -> None:
        if self.closed:
            raise ActuatorAdapterError("ACTUATOR_UNAVAILABLE", "simulated actuator is closed")
        try:
            self.state.set_actuator_power(FanPower.parse(power))
        except SimulationStateError as exc:
            raise ActuatorAdapterError(str(exc.code), _public_message(exc)) from exc

    def safe_off(self) -> None:
        self.state.force_actuator_off()

    def close(self) -> None:
        self.safe_off()
        self.closed = True

    def capabilities(self) -> FanCapability:
        return FanCapability(power_control=True, software_speed_control=False, fan_motion_observed=False)


def _public_message(exc: BaseException) -> str:
    text = str(exc)
    if ": " in text:
        return text.split(": ", 1)[1]
    return text or type(exc).__name__
