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
        self._commanded = FanPower.OFF

    @classmethod
    def from_config(cls, env_config: Any) -> "GpiodRelayFanActuator":
        return cls(
            logical_bcm=int(env_config.relay_bcm),
            active_high=bool(env_config.relay_active_high),
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
        matches: list[RelayLineIdentity] = []
        for chip_path in self._paths():
            try:
                chip = gpiod.Chip(chip_path)
            except Exception:
                continue
            try:
                info = chip.get_info()
                count = int(getattr(info, "num_lines"))
                chip_label = str(getattr(info, "label", "") or "")
                if not 1 <= count <= 4096:
                    continue
                for offset in range(count):
                    try:
                        line_info = chip.get_line_info(offset)
                    except Exception:
                        continue
                    if getattr(line_info, "name", None) == expected:
                        matches.append(
                            RelayLineIdentity(
                                chip_path,
                                offset,
                                self._active_high,
                                self._consumer,
                                self.logical_bcm,
                                expected,
                                chip_label,
                            )
                        )
            finally:
                self._close_chip(chip)
        if not matches:
            raise ActuatorAdapterError("ACTUATOR_GPIO_LINE_NOT_FOUND", f"no unique line named {expected}")
        if len(matches) != 1:
            rp1 = [item for item in matches if "pinctrl-rp1" in item.chip_label.casefold()]
            if len(rp1) != 1:
                raise ActuatorAdapterError("ACTUATOR_GPIO_LINE_AMBIGUOUS", f"multiple lines named {expected}")
            matches = rp1
        self.identity = matches[0]
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
                raise ActuatorAdapterError("ACTUATOR_UNAVAILABLE", "cannot request relay GPIO line") from exc
            self._commanded = FanPower.OFF

    def set_power(self, power: FanPower | bool | str) -> None:
        requested = FanPower.parse(power)
        with self._lock:
            self.open()
            assert self.identity is not None
            try:
                self._request.set_value(self.identity.line_offset, self._value.ACTIVE if requested == FanPower.ON else self._value.INACTIVE)
            except Exception as exc:
                raise ActuatorAdapterError("ACTUATOR_UNAVAILABLE", "cannot set relay GPIO line") from exc
            self._commanded = requested

    def safe_off(self) -> None:
        with self._lock:
            self.open()
            assert self.identity is not None
            try:
                self._request.set_value(self.identity.line_offset, self._value.INACTIVE)
            except Exception as exc:
                raise ActuatorAdapterError("ACTUATOR_UNAVAILABLE", "cannot force relay safe OFF") from exc
            self._commanded = FanPower.OFF

    def close(self) -> None:
        with self._lock:
            if self._request is not None:
                assert self.identity is not None
                try:
                    self._request.set_value(self.identity.line_offset, self._value.INACTIVE)
                finally:
                    release = getattr(self._request, "release", None)
                    if callable(release):
                        release()
                    self._request = None
                    self._commanded = FanPower.OFF

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
                "active_high": identity.active_high,
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
