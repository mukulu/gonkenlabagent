"""libgpiod relay adapter for the V09 room-fan power boundary.

The adapter imports libgpiod only when opened in production.  Tests inject a
small fake gpiod module, which verifies line-request semantics without touching
``/dev/gpiochip*``.  Logical ON/OFF remains relay power only; it does not prove
ELUTENG blade motion or software fan-speed control.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from ..domain import FanCapability, FanPower
from .base import ActuatorAdapterError


@dataclass(frozen=True, slots=True)
class RelayLineIdentity:
    chip_path: str
    line_offset: int
    active_high: bool
    consumer: str


class GpiodRelayFanActuator:
    """Power-only relay adapter using libgpiod v2-style request_lines."""

    def __init__(
        self,
        *,
        chip_path: str = "/dev/gpiochip0",
        line_offset: int,
        active_high: bool,
        consumer: str = "gonken-environment",
        gpiod_module: Any | None = None,
    ) -> None:
        if not isinstance(chip_path, str) or not chip_path.strip():
            raise ActuatorAdapterError("ACTUATOR_CONFIG_INVALID", "gpio chip path must be a non-empty string")
        if isinstance(line_offset, bool) or not isinstance(line_offset, int) or line_offset < 0:
            raise ActuatorAdapterError("ACTUATOR_CONFIG_INVALID", "gpio line offset must be a non-negative integer")
        if not isinstance(consumer, str) or not consumer.strip():
            raise ActuatorAdapterError("ACTUATOR_CONFIG_INVALID", "consumer must be a non-empty string")
        self.identity = RelayLineIdentity(
            chip_path=chip_path,
            line_offset=line_offset,
            active_high=bool(active_high),
            consumer=consumer,
        )
        self._gpiod = gpiod_module
        self._direction = None
        self._value = None
        self._request = None
        self._lock = threading.RLock()
        self._commanded = FanPower.OFF

    @classmethod
    def from_config(cls, env_config: Any) -> "GpiodRelayFanActuator":
        return cls(
            chip_path="/dev/gpiochip0",
            line_offset=int(env_config.relay_bcm),
            active_high=bool(env_config.relay_active_high),
        )

    @property
    def commanded_power(self) -> FanPower:
        return self._commanded

    def capabilities(self) -> FanCapability:
        return FanCapability(power_control=True, software_speed_control=False, fan_motion_observed=False)

    def open(self) -> None:
        with self._lock:
            if self._request is not None:
                return
            gpiod, direction, value = self._load_gpiod_symbols()
            try:
                settings = gpiod.LineSettings(
                    direction=direction.OUTPUT,
                    active_low=not self.identity.active_high,
                    output_value=value.INACTIVE,
                )
                self._request = gpiod.request_lines(
                    self.identity.chip_path,
                    consumer=self.identity.consumer,
                    config={self.identity.line_offset: settings},
                )
            except Exception as exc:
                raise ActuatorAdapterError("ACTUATOR_UNAVAILABLE", "cannot request relay GPIO line") from exc
            self._commanded = FanPower.OFF

    def set_power(self, power: FanPower | bool | str) -> None:
        requested = FanPower.parse(power)
        with self._lock:
            self.open()
            try:
                self._request.set_value(self.identity.line_offset, self._value.ACTIVE if requested == FanPower.ON else self._value.INACTIVE)
            except Exception as exc:
                raise ActuatorAdapterError("ACTUATOR_UNAVAILABLE", "cannot set relay GPIO line") from exc
            self._commanded = requested

    def safe_off(self) -> None:
        with self._lock:
            self.open()
            try:
                self._request.set_value(self.identity.line_offset, self._value.INACTIVE)
            except Exception as exc:
                raise ActuatorAdapterError("ACTUATOR_UNAVAILABLE", "cannot force relay safe OFF") from exc
            self._commanded = FanPower.OFF

    def close(self) -> None:
        with self._lock:
            if self._request is not None:
                try:
                    self._request.set_value(self.identity.line_offset, self._value.INACTIVE)
                finally:
                    release = getattr(self._request, "release", None)
                    if callable(release):
                        release()
                    self._request = None
                    self._commanded = FanPower.OFF

    def _load_gpiod_symbols(self):
        if self._gpiod is None:
            try:
                import gpiod  # type: ignore[import-not-found]
                from gpiod.line import Direction, Value  # type: ignore[import-not-found]
            except Exception as exc:  # pragma: no cover - host tests inject a fake gpiod module
                raise ActuatorAdapterError("ACTUATOR_DEPENDENCY_MISSING", "python3-libgpiod is not importable") from exc
            self._gpiod = gpiod
            self._direction = Direction
            self._value = Value
        else:
            if hasattr(self._gpiod, "Direction") and hasattr(self._gpiod, "Value"):
                self._direction = self._gpiod.Direction
                self._value = self._gpiod.Value
            elif hasattr(self._gpiod, "line"):
                self._direction = self._gpiod.line.Direction
                self._value = self._gpiod.line.Value
            else:
                raise ActuatorAdapterError("ACTUATOR_CONFIG_INVALID", "gpiod module lacks Direction/Value symbols")
        return self._gpiod, self._direction, self._value
