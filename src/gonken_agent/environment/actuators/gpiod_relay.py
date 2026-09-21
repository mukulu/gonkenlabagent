"""libgpiod relay adapter for the V09 room-fan power boundary.

The operator-facing configuration uses Raspberry Pi logical BCM identity.  The
production ``from_config`` path resolves that identity from libgpiod line names
(``GPIO<n>``) across the available gpiochips instead of assuming that BCM23 is
``/dev/gpiochip0`` offset 23.  Explicit chip/offset construction remains
available for deterministic host tests.  Real target mapping, relay polarity,
electrical safety and fan blade motion remain physical acceptance gates.
"""

from __future__ import annotations

import glob
import threading
from dataclasses import dataclass
from typing import Any, Iterable

from gonken_agent.gpio_resolver import GpioResolveError, resolve_named_gpio_line

from ..domain import FanCapability, FanPower
from .base import ActuatorAdapterError


@dataclass(frozen=True, slots=True)
class RelayLineIdentity:
    chip_path: str
    line_offset: int
    active_high: bool
    consumer: str
    logical_bcm: int | None = None
    line_name: str | None = None
    chip_label: str = ""
    chip_name: str = ""
    resolution_basis: str = ""


class GpiodRelayFanActuator:
    """Power-only relay adapter using libgpiod v2-style request_lines."""

    def __init__(
        self,
        *,
        chip_path: str | None = None,
        line_offset: int | None = None,
        logical_bcm: int | None = None,
        active_high: bool,
        consumer: str = "gonken-environment",
        gpiod_module: Any | None = None,
        chip_paths: Iterable[str] | None = None,
    ) -> None:
        if type(active_high) is not bool:
            raise ActuatorAdapterError("ACTUATOR_CONFIG_INVALID", "relay polarity must be a boolean")
        if line_offset is not None and chip_path is None:
            chip_path = "/dev/gpiochip0"
        explicit = chip_path is not None or line_offset is not None
        if explicit:
            if not isinstance(chip_path, str) or not chip_path.strip():
                raise ActuatorAdapterError("ACTUATOR_CONFIG_INVALID", "gpio chip path must be a non-empty string")
            if isinstance(line_offset, bool) or not isinstance(line_offset, int) or line_offset < 0:
                raise ActuatorAdapterError("ACTUATOR_CONFIG_INVALID", "gpio line offset must be a non-negative integer")
        if logical_bcm is not None and (isinstance(logical_bcm, bool) or not isinstance(logical_bcm, int) or not 0 <= logical_bcm <= 53):
            raise ActuatorAdapterError("ACTUATOR_CONFIG_INVALID", "logical BCM must be 0..53")
        if not explicit and logical_bcm is None:
            raise ActuatorAdapterError("ACTUATOR_CONFIG_INVALID", "logical BCM or explicit gpio line identity required")
        if not isinstance(consumer, str) or not consumer.strip():
            raise ActuatorAdapterError("ACTUATOR_CONFIG_INVALID", "consumer must be a non-empty string")
        self.logical_bcm = logical_bcm
        self._explicit_chip_path = chip_path
        self._explicit_line_offset = line_offset
        self._chip_paths = tuple(chip_paths) if chip_paths is not None else None
        self._active_high = bool(active_high)
        self._consumer = consumer
        self.identity: RelayLineIdentity | None = (
            RelayLineIdentity(chip_path, line_offset, bool(active_high), consumer, logical_bcm, None)
            if explicit else None
        )
        self._gpiod = gpiod_module
        self._direction = None
        self._value = None
        self._request = None
        self._lock = threading.RLock()
        self._commanded = FanPower.OFF  # compatibility: last acknowledged/default logical state
        self._acknowledged: FanPower | None = None
        self._write_count = 0
        self._write_errors = 0
        self._request_errors = 0
        self._last_write_result = "NOT_ATTEMPTED"

    @classmethod
    def from_config(cls, env_config: Any) -> "GpiodRelayFanActuator":
        return cls(
            logical_bcm=env_config.relay_bcm,
            active_high=env_config.relay_active_high,
        )

    @property
    def commanded_power(self) -> FanPower:
        return self._commanded

    def capabilities(self) -> FanCapability:
        return FanCapability(power_control=True, software_speed_control=False, fan_motion_observed=False)

    def _paths(self) -> tuple[str, ...]:
        paths = self._chip_paths if self._chip_paths is not None else tuple(sorted(glob.glob("/dev/gpiochip*")))
        clean = tuple(path for path in paths if isinstance(path, str) and path.startswith("/dev/gpiochip"))
        if not clean:
            raise ActuatorAdapterError("ACTUATOR_UNAVAILABLE", "no gpiochip devices found")
        return clean

    @staticmethod
    def _close_chip(chip: Any) -> None:
        close = getattr(chip, "close", None)
        if callable(close):
            close()

    def _resolve_identity(self, gpiod: Any) -> RelayLineIdentity:
        if self.identity is not None:
            return self.identity
        assert self.logical_bcm is not None
        expected = f"GPIO{self.logical_bcm}"
        try:
            resolved = resolve_named_gpio_line(
                gpiod=gpiod, logical_bcm=self.logical_bcm, chip_paths=self._paths()
            )
        except GpioResolveError as exc:
            if exc.reason == "not_found":
                raise ActuatorAdapterError("ACTUATOR_GPIO_LINE_NOT_FOUND", expected) from exc
            if exc.reason == "ambiguous":
                raise ActuatorAdapterError("ACTUATOR_GPIO_LINE_AMBIGUOUS", exc.detail) from exc
            raise ActuatorAdapterError("ACTUATOR_CONFIG_INVALID", exc.detail) from exc
        self.identity = RelayLineIdentity(
            chip_path=resolved.chip_path,
            line_offset=resolved.line_offset,
            active_high=self._active_high,
            consumer=self._consumer,
            logical_bcm=self.logical_bcm,
            line_name=resolved.line_name,
            chip_label=resolved.chip_label,
            chip_name=resolved.chip_name,
            resolution_basis=resolved.resolution_basis,
        )
        return self.identity


    def open(self) -> None:
        with self._lock:
            if self._request is not None:
                return
            gpiod, direction, value = self._load_gpiod_symbols()
            identity = self._resolve_identity(gpiod)
            try:
                settings = gpiod.LineSettings(
                    direction=direction.OUTPUT,
                    active_low=not identity.active_high,
                    output_value=value.INACTIVE,
                )
                self._request = gpiod.request_lines(
                    identity.chip_path,
                    consumer=identity.consumer,
                    config={identity.line_offset: settings},
                )
            except Exception as exc:
                self._request_errors += 1
                self._last_write_result = "REQUEST_FAILED"
                self._acknowledged = None
                raise ActuatorAdapterError("ACTUATOR_UNAVAILABLE", "cannot request relay GPIO line") from exc
            self._commanded = FanPower.OFF
            self._acknowledged = FanPower.OFF
            self._write_count += 1  # initial inactive output is an actual kernel command
            self._last_write_result = "SUCCESS"

    def _write(self, requested: FanPower) -> None:
        assert self.identity is not None and self._request is not None
        try:
            self._request.set_value(self.identity.line_offset,
                                   self._value.ACTIVE if requested == FanPower.ON else self._value.INACTIVE)
        except Exception as exc:
            self._write_errors += 1
            self._acknowledged = None  # an attempted write is not an acknowledged state
            self._last_write_result = "FAILED"
            raise ActuatorAdapterError("ACTUATOR_UNAVAILABLE", "cannot set relay GPIO line") from exc
        self._write_count += 1
        self._commanded = self._acknowledged = requested
        self._last_write_result = "SUCCESS"

    def set_power(self, power: FanPower | bool | str) -> None:
        requested = FanPower.parse(power)
        with self._lock:
            self.open()
            if self._acknowledged == requested:
                return  # retain the exclusive request; identical polls need no GPIO write
            self._write(requested)

    def safe_off(self) -> None:
        with self._lock:
            self.open()
            self._write(FanPower.OFF)

    def close(self) -> None:
        with self._lock:
            if self._request is not None:
                try:
                    self._write(FanPower.OFF)
                finally:
                    request, self._request = self._request, None
                    # After release the electrical state is not an owned command.
                    self._acknowledged = None
                    release = getattr(request, "release", None)
                    if callable(release):
                        release()

    def command_diagnostics(self) -> dict[str, object]:
        """In-memory transport facts only; does not open/resolve/request/read GPIO."""
        with self._lock:
            return {
                "gpio_claimed": self._request is not None,
                "gpio_consumer": self._consumer if self._request is not None else None,
                "relay_commanded": self._acknowledged.value if self._acknowledged is not None else None,
                "gpio_write_count": self._write_count,
                "gpio_write_errors": self._write_errors,
                "gpio_request_errors": self._request_errors,
                "last_write_result": self._last_write_result,
                "fan_motion_observed": False,
                "software_speed_control": False,
            }

    def resolved_identity(self) -> dict[str, object]:
        """Return runtime line identity after open/resolution without physical claims."""
        with self._lock:
            gpiod, _direction, _value = self._load_gpiod_symbols()
            identity = self._resolve_identity(gpiod)
            return {
                "logical_bcm": identity.logical_bcm,
                "line_name": identity.line_name,
                "chip_path": identity.chip_path,
                "line_offset": identity.line_offset,
                "chip_label": identity.chip_label,
                "chip_name": identity.chip_name,
                "resolution_basis": identity.resolution_basis,
                "active_high": identity.active_high,
                **self.command_diagnostics(),
                "physical_acceptance_claimed": False,
            }

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
