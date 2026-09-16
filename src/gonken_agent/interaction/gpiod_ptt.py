"""libgpiod v2 push-to-talk button and recording-LED adapter.

The configuration exposes Raspberry Pi logical BCM identities.  This adapter
*does not* assume that a BCM number is also a gpiochip line offset.  At open it
scans the available gpiochip line metadata for the canonical ``GPIO<n>`` names,
requires a unique match for both the button and LED, and only then acquires the
lines.  Real Raspberry Pi mapping, electrical polarity and crash/boot behaviour
remain target acceptance gates; host tests inject a fake gpiod module.
"""

from __future__ import annotations

import glob
from dataclasses import dataclass
from typing import Any, Iterable

from gonken_agent.gpio_resolver import GpioResolveError, resolve_named_gpio_line


class PttHardwareError(RuntimeError):
    """Bounded categorical GPIO failure for the production PTT path."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = " ".join(str(detail).replace("\r", " ").replace("\n", " ").split())[:240]


@dataclass(frozen=True, slots=True)
class GpioLineIdentity:
    logical_bcm: int
    chip_path: str
    line_offset: int
    line_name: str
    chip_label: str = ""
    chip_name: str = ""
    resolution_basis: str = ""


class GpiodPushToTalkHardware:
    """Own one active-low button input and one active-high recording LED."""

    def __init__(
        self,
        *,
        button_bcm: int,
        led_bcm: int,
        consumer: str = "gonken-agent-ptt",
        gpiod_module: Any | None = None,
        chip_paths: Iterable[str] | None = None,
    ) -> None:
        for label, value in (("button_bcm", button_bcm), ("led_bcm", led_bcm)):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 53:
                raise PttHardwareError("PTT_GPIO_CONFIG_INVALID", f"{label} must be BCM 0..53")
        if button_bcm == led_bcm:
            raise PttHardwareError("PTT_GPIO_CONFIG_INVALID", "button and LED GPIO must differ")
        if not isinstance(consumer, str) or not consumer.strip():
            raise PttHardwareError("PTT_GPIO_CONFIG_INVALID", "consumer must be non-empty")
        self.button_bcm = button_bcm
        self.led_bcm = led_bcm
        self.consumer = consumer.strip()
        self._gpiod = gpiod_module
        self._chip_paths = tuple(chip_paths) if chip_paths is not None else None
        self._direction = self._bias = self._value = None
        self._request = None
        self.button_identity: GpioLineIdentity | None = None
        self.led_identity: GpioLineIdentity | None = None

    @classmethod
    def from_config(cls, config: Any, **kwargs: Any) -> "GpiodPushToTalkHardware":
        return cls(
            button_bcm=int(config.interaction.push_to_talk_gpio),
            led_bcm=int(config.interaction.recording_led_gpio),
            **kwargs,
        )

    def _load_symbols(self) -> tuple[Any, Any, Any, Any]:
        if self._gpiod is None:
            try:
                import gpiod  # type: ignore[import-not-found]
                from gpiod.line import Bias, Direction, Value  # type: ignore[import-not-found]
            except Exception as exc:  # pragma: no cover - host tests inject fakes
                raise PttHardwareError("PTT_GPIO_DEPENDENCY_MISSING", "python3-libgpiod is not importable") from exc
            self._gpiod = gpiod
            self._direction, self._bias, self._value = Direction, Bias, Value
        elif all(hasattr(self._gpiod, name) for name in ("Direction", "Bias", "Value")):
            self._direction = self._gpiod.Direction
            self._bias = self._gpiod.Bias
            self._value = self._gpiod.Value
        elif hasattr(self._gpiod, "line"):
            self._direction = self._gpiod.line.Direction
            self._bias = self._gpiod.line.Bias
            self._value = self._gpiod.line.Value
        else:
            raise PttHardwareError("PTT_GPIO_DEPENDENCY_INVALID", "gpiod lacks line symbols")
        return self._gpiod, self._direction, self._bias, self._value

    def _paths(self) -> tuple[str, ...]:
        paths = self._chip_paths
        if paths is None:
            paths = tuple(sorted(glob.glob("/dev/gpiochip*")))
        clean = tuple(path for path in paths if isinstance(path, str) and path.startswith("/dev/gpiochip"))
        if not clean:
            raise PttHardwareError("PTT_GPIO_UNAVAILABLE", "no gpiochip devices found")
        return clean

    @staticmethod
    def _close_chip(chip: Any) -> None:
        close = getattr(chip, "close", None)
        if callable(close):
            close()

    def _find_named_line(self, logical_bcm: int, *, gpiod: Any) -> GpioLineIdentity:
        expected = f"GPIO{logical_bcm}"
        try:
            resolved = resolve_named_gpio_line(
                gpiod=gpiod, logical_bcm=logical_bcm, chip_paths=self._paths()
            )
        except GpioResolveError as exc:
            if exc.reason == "not_found":
                raise PttHardwareError("PTT_GPIO_LINE_NOT_FOUND", expected) from exc
            if exc.reason == "ambiguous":
                raise PttHardwareError("PTT_GPIO_LINE_AMBIGUOUS", exc.detail) from exc
            raise PttHardwareError("PTT_GPIO_CONFIG_INVALID", exc.detail) from exc
        return GpioLineIdentity(
            logical_bcm=logical_bcm,
            chip_path=resolved.chip_path,
            line_offset=resolved.line_offset,
            line_name=resolved.line_name,
            chip_label=resolved.chip_label,
            chip_name=resolved.chip_name,
            resolution_basis=resolved.resolution_basis,
        )


    def open(self) -> None:
        if self._request is not None:
            return
        gpiod, direction, bias, value = self._load_symbols()
        button = self._find_named_line(self.button_bcm, gpiod=gpiod)
        led = self._find_named_line(self.led_bcm, gpiod=gpiod)
        if button.chip_path != led.chip_path:
            raise PttHardwareError("PTT_GPIO_CHIP_MISMATCH", "button and LED resolved on different gpiochips")
        try:
            button_settings = gpiod.LineSettings(
                direction=direction.INPUT,
                bias=bias.PULL_UP,
                active_low=True,
            )
            led_settings = gpiod.LineSettings(
                direction=direction.OUTPUT,
                output_value=value.INACTIVE,
            )
            request = gpiod.request_lines(
                button.chip_path,
                consumer=self.consumer,
                config={
                    button.line_offset: button_settings,
                    led.line_offset: led_settings,
                },
            )
        except Exception as exc:
            raise PttHardwareError("PTT_GPIO_UNAVAILABLE", "cannot request PTT/LED GPIO lines") from exc
        self.button_identity = button
        self.led_identity = led
        self._request = request
        # Reinforce the requested initial LED state after line acquisition.
        try:
            self._request.set_value(led.line_offset, value.INACTIVE)
        except Exception as exc:
            self.close(suppress_errors=True)
            raise PttHardwareError("PTT_LED_UNAVAILABLE", "cannot force recording LED off") from exc

    def pressed(self) -> bool:
        self.open()
        assert self.button_identity is not None
        try:
            observed = self._request.get_value(self.button_identity.line_offset)
        except Exception as exc:
            raise PttHardwareError("PTT_BUTTON_UNAVAILABLE", "cannot read PTT button") from exc
        return observed == self._value.ACTIVE

    def led(self, on: bool) -> None:
        if type(on) is not bool:
            raise PttHardwareError("PTT_LED_VALUE_INVALID", "LED state must be boolean")
        self.open()
        assert self.led_identity is not None
        try:
            self._request.set_value(
                self.led_identity.line_offset,
                self._value.ACTIVE if on else self._value.INACTIVE,
            )
        except Exception as exc:
            raise PttHardwareError("PTT_LED_UNAVAILABLE", "cannot set recording LED") from exc

    def identities(self) -> dict[str, object]:
        self.open()
        assert self.button_identity is not None and self.led_identity is not None
        return {
            "button_bcm": self.button_identity.logical_bcm,
            "button_chip_path": self.button_identity.chip_path,
            "button_line_offset": self.button_identity.line_offset,
            "button_chip_label": self.button_identity.chip_label,
            "button_resolution_basis": self.button_identity.resolution_basis,
            "led_bcm": self.led_identity.logical_bcm,
            "led_chip_path": self.led_identity.chip_path,
            "led_line_offset": self.led_identity.line_offset,
            "led_chip_label": self.led_identity.chip_label,
            "led_resolution_basis": self.led_identity.resolution_basis,
            "physical_acceptance_claimed": False,
        }

    def close(self, *, suppress_errors: bool = False) -> None:
        request = self._request
        self._request = None
        if request is None:
            return
        error: BaseException | None = None
        if self.led_identity is not None and self._value is not None:
            try:
                request.set_value(self.led_identity.line_offset, self._value.INACTIVE)
            except BaseException as exc:
                error = exc
        try:
            release = getattr(request, "release", None)
            if callable(release):
                release()
        except BaseException as exc:
            error = error or exc
        if error is not None and not suppress_errors:
            raise PttHardwareError("PTT_GPIO_CLEANUP_FAILED", "could not guarantee software LED cleanup") from error

class GpiodWakeMonitoringLed:
    """Exclusive active-high indicator for continuous wake-audio monitoring.

    The line is resolved by its Raspberry Pi ``GPIO<n>`` metadata name rather
    than by assuming a character-device offset.  Opening initializes OFF;
    callers explicitly set ON only while standby capture is active.
    """

    def __init__(
        self,
        *,
        logical_bcm: int,
        consumer: str = "gonken-agent-wake-monitor",
        gpiod_module: Any | None = None,
        chip_paths: Iterable[str] | None = None,
    ) -> None:
        if isinstance(logical_bcm, bool) or not isinstance(logical_bcm, int) or not 0 <= logical_bcm <= 53:
            raise PttHardwareError("WAKE_LED_GPIO_CONFIG_INVALID", "logical BCM must be 0..53")
        self.logical_bcm = logical_bcm
        self.consumer = consumer
        self._gpiod = gpiod_module
        self._chip_paths = tuple(chip_paths) if chip_paths is not None else None
        self._direction = self._value = None
        self._request = None
        self.identity: GpioLineIdentity | None = None

    @classmethod
    def from_config(cls, config: Any, **kwargs: Any) -> "GpiodWakeMonitoringLed":
        return cls(logical_bcm=int(config.extensions.wake_word.monitoring_led_gpio), **kwargs)

    def _load_symbols(self) -> tuple[Any, Any, Any]:
        if self._gpiod is None:
            try:
                import gpiod  # type: ignore[import-not-found]
                from gpiod.line import Direction, Value  # type: ignore[import-not-found]
            except Exception as exc:  # pragma: no cover - host tests inject fakes
                raise PttHardwareError("WAKE_LED_GPIO_DEPENDENCY_MISSING", "python3-libgpiod is not importable") from exc
            self._gpiod = gpiod
            self._direction, self._value = Direction, Value
        elif hasattr(self._gpiod, "Direction") and hasattr(self._gpiod, "Value"):
            self._direction, self._value = self._gpiod.Direction, self._gpiod.Value
        elif hasattr(self._gpiod, "line"):
            self._direction, self._value = self._gpiod.line.Direction, self._gpiod.line.Value
        else:
            raise PttHardwareError("WAKE_LED_GPIO_DEPENDENCY_INVALID", "gpiod lacks line symbols")
        return self._gpiod, self._direction, self._value

    def _paths(self) -> tuple[str, ...]:
        paths = self._chip_paths if self._chip_paths is not None else tuple(sorted(glob.glob("/dev/gpiochip*")))
        clean = tuple(path for path in paths if isinstance(path, str) and path.startswith("/dev/gpiochip"))
        if not clean:
            raise PttHardwareError("WAKE_LED_GPIO_UNAVAILABLE", "no gpiochip devices found")
        return clean

    def _resolve(self, gpiod: Any) -> GpioLineIdentity:
        expected = f"GPIO{self.logical_bcm}"
        try:
            resolved = resolve_named_gpio_line(
                gpiod=gpiod, logical_bcm=self.logical_bcm, chip_paths=self._paths()
            )
        except GpioResolveError as exc:
            if exc.reason == "not_found":
                raise PttHardwareError("WAKE_LED_GPIO_LINE_NOT_FOUND", expected) from exc
            if exc.reason == "ambiguous":
                raise PttHardwareError("WAKE_LED_GPIO_LINE_AMBIGUOUS", exc.detail) from exc
            raise PttHardwareError("WAKE_LED_GPIO_CONFIG_INVALID", exc.detail) from exc
        return GpioLineIdentity(
            logical_bcm=self.logical_bcm,
            chip_path=resolved.chip_path,
            line_offset=resolved.line_offset,
            line_name=resolved.line_name,
            chip_label=resolved.chip_label,
            chip_name=resolved.chip_name,
            resolution_basis=resolved.resolution_basis,
        )


    def open(self) -> None:
        if self._request is not None:
            return
        gpiod, direction, value = self._load_symbols()
        identity = self._resolve(gpiod)
        try:
            settings = gpiod.LineSettings(direction=direction.OUTPUT, output_value=value.INACTIVE)
            request = gpiod.request_lines(
                identity.chip_path,
                consumer=self.consumer,
                config={identity.line_offset: settings},
            )
            request.set_value(identity.line_offset, value.INACTIVE)
        except Exception as exc:
            raise PttHardwareError("WAKE_LED_GPIO_UNAVAILABLE", "cannot request wake monitoring LED") from exc
        self.identity = identity
        self._request = request

    def set(self, on: bool) -> None:
        if type(on) is not bool:
            raise PttHardwareError("WAKE_LED_VALUE_INVALID", "wake LED state must be boolean")
        self.open()
        assert self.identity is not None
        try:
            self._request.set_value(
                self.identity.line_offset,
                self._value.ACTIVE if on else self._value.INACTIVE,
            )
        except Exception as exc:
            raise PttHardwareError("WAKE_LED_GPIO_UNAVAILABLE", "cannot set wake monitoring LED") from exc

    def metadata(self) -> dict[str, object]:
        self.open()
        assert self.identity is not None
        return {
            "logical_bcm": self.identity.logical_bcm,
            "chip_path": self.identity.chip_path,
            "line_offset": self.identity.line_offset,
            "chip_label": self.identity.chip_label,
            "chip_name": self.identity.chip_name,
            "resolution_basis": self.identity.resolution_basis,
            "physical_acceptance_claimed": False,
        }

    def close(self, *, suppress_errors: bool = False) -> None:
        request = self._request
        self._request = None
        if request is None:
            return
        error: BaseException | None = None
        if self.identity is not None and self._value is not None:
            try:
                request.set_value(self.identity.line_offset, self._value.INACTIVE)
            except BaseException as exc:
                error = exc
        try:
            release = getattr(request, "release", None)
            if callable(release):
                release()
        except BaseException as exc:
            error = error or exc
        if error is not None and not suppress_errors:
            raise PttHardwareError("WAKE_LED_GPIO_CLEANUP_FAILED", "cannot guarantee wake monitoring LED off") from error
