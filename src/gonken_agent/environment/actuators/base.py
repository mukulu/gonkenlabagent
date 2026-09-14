"""Narrow actuator adapter interfaces for V09 environment control."""

from __future__ import annotations

from typing import Protocol

from ..domain import FanCapability, FanPower


class ActuatorAdapterError(RuntimeError):
    """A fan actuator adapter was misconfigured or failed to apply output."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class FanActuator(Protocol):
    """Minimal power-only fan actuator contract."""

    def set_power(self, power: FanPower | bool | str) -> None:
        """Set the relay-power boundary to ON or OFF."""
        ...

    def safe_off(self) -> None:
        """Best-effort transition to the configured safe OFF state."""
        ...

    def close(self) -> None:
        """Release any hardware handles owned by the adapter."""
        ...

    def capabilities(self) -> FanCapability:
        """Return truthful hardware capability metadata."""
        ...
