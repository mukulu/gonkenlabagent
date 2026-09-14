"""Narrow sensor adapter interfaces for V09 environment control."""

from __future__ import annotations

from typing import Protocol

from ..domain import SensorReading


class SensorAdapterError(RuntimeError):
    """A sensor adapter was misconfigured or could not complete an operation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class EnvironmentSensor(Protocol):
    """Minimal sensor contract consumed by gonken-environment.service."""

    def read(self, *, now_monotonic: float) -> SensorReading:
        """Return one current reading or a truthful unavailable/failed reading."""
        ...

    def close(self) -> None:
        """Release any transport handles owned by the adapter."""
        ...
