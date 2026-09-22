"""Pure V09 environment-control domain objects.

The classes in this module are intentionally dependency-free.  They describe
truthful sensor, relay-power, policy-bound and transition concepts without
opening I2C, GPIO, audio, network or model resources.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class EnvironmentMode(str, Enum):
    """Allowed user-visible room-fan control modes."""

    DISABLED = "disabled"
    MANUAL = "manual"
    SEMI_AUTOMATIC = "semi_automatic"
    AUTOMATIC = "automatic"

    @classmethod
    def parse(cls, value: str | "EnvironmentMode") -> "EnvironmentMode":
        if isinstance(value, cls):
            return value
        normalized = value.strip().lower().replace("-", "_")
        aliases = {
            "semi": cls.SEMI_AUTOMATIC,
            "semi_auto": cls.SEMI_AUTOMATIC,
            "semi_automatic": cls.SEMI_AUTOMATIC,
            "auto": cls.AUTOMATIC,
            "automatic": cls.AUTOMATIC,
            "manual": cls.MANUAL,
            "disabled": cls.DISABLED,
            "off": cls.DISABLED,
        }
        try:
            return aliases[normalized]
        except KeyError as exc:
            raise ValueError(f"unsupported environment mode: {value!r}") from exc


class FanPower(str, Enum):
    """Observable software boundary for the current relay architecture."""

    OFF = "off"
    ON = "on"

    @classmethod
    def parse(cls, value: str | bool | "FanPower") -> "FanPower":
        if isinstance(value, cls):
            return value
        if isinstance(value, bool):
            return cls.ON if value else cls.OFF
        normalized = value.strip().lower()
        if normalized in {"on", "true", "1"}:
            return cls.ON
        if normalized in {"off", "false", "0"}:
            return cls.OFF
        raise ValueError(f"unsupported fan power: {value!r}")


class SensorQuality(str, Enum):
    STARTING = "starting"
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class TransitionReason(str, Enum):
    BOOT_SAFE_OFF = "BOOT_SAFE_OFF"
    USER_MANUAL_ON = "USER_MANUAL_ON"
    USER_MANUAL_OFF = "USER_MANUAL_OFF"
    USER_MODE_CHANGE = "USER_MODE_CHANGE"
    AUTO_START_THRESHOLD = "AUTO_START_THRESHOLD"
    AUTO_STOP_THRESHOLD = "AUTO_STOP_THRESHOLD"
    SEMI_USER_START = "SEMI_USER_START"
    SEMI_AUTO_STOP = "SEMI_AUTO_STOP"
    SENSOR_STALE_SAFE_OFF = "SENSOR_STALE_SAFE_OFF"
    SENSOR_RECOVERED = "SENSOR_RECOVERED"
    DWELL_HOLD = "DWELL_HOLD"
    POLICY_UPDATE_STOP_CONDITION = "POLICY_UPDATE_STOP_CONDITION"
    SHUTDOWN_SAFE_OFF = "SHUTDOWN_SAFE_OFF"
    TIMER_ON = "TIMER_ON"
    TIMER_OFF = "TIMER_OFF"
    TIMER_EXPIRED_SAFE_OFF = "TIMER_EXPIRED_SAFE_OFF"
    ACTUATOR_ERROR_SAFE_OFF = "ACTUATOR_ERROR_SAFE_OFF"
    DISABLED_SAFE_OFF = "DISABLED_SAFE_OFF"


@dataclass(frozen=True, slots=True)
class FanCapability:
    """Truthful capability boundary for the purchased relay + USB fan design."""

    power_control: bool = True
    software_speed_control: bool = False
    fan_motion_observed: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            "power_control": self.power_control,
            "software_speed_control": self.software_speed_control,
            "fan_motion_observed": self.fan_motion_observed,
        }


@dataclass(frozen=True, slots=True)
class PolicyBounds:
    """Static/admin safety envelope for mutable operating policy."""

    temperature_min_c: float = -10.0
    temperature_max_c: float = 60.0
    minimum_hysteresis_c: float = 0.5
    maximum_hysteresis_c: float = 15.0
    minimum_dwell_seconds: int = 5
    maximum_dwell_seconds: int = 3600

    def __post_init__(self) -> None:
        values = (
            self.temperature_min_c,
            self.temperature_max_c,
            self.minimum_hysteresis_c,
            self.maximum_hysteresis_c,
        )
        if not all(isinstance(value, (int, float)) and isfinite(float(value)) for value in values):
            raise ValueError("policy bounds must be finite numbers")
        if not self.temperature_min_c < self.temperature_max_c:
            raise ValueError("temperature_min_c must be below temperature_max_c")
        if not 0 < self.minimum_hysteresis_c <= self.maximum_hysteresis_c:
            raise ValueError("hysteresis bounds must be positive and ordered")
        if self.maximum_hysteresis_c > self.temperature_max_c - self.temperature_min_c:
            raise ValueError("maximum_hysteresis_c must fit inside temperature bounds")
        if not 0 <= self.minimum_dwell_seconds <= self.maximum_dwell_seconds:
            raise ValueError("dwell bounds must be ordered and non-negative")


@dataclass(frozen=True, slots=True)
class SensorReading:
    """One SHT31-style observation after transport/CRC validation."""

    temperature_c: float | None
    relative_humidity_pct: float | None
    observed_monotonic: float
    sensor_address: int | None = None
    source_backend: str = "sht31"
    crc_valid: bool = True
    error_code: str | None = None
    physical_evidence: bool = False

    def age_seconds(self, *, now_monotonic: float) -> float:
        age = now_monotonic - self.observed_monotonic
        return 0.0 if age < 0 else age

    def is_valid(self) -> bool:
        if self.error_code is not None or not self.crc_valid:
            return False
        if self.temperature_c is None or self.relative_humidity_pct is None:
            return False
        return (
            isfinite(self.temperature_c)
            and isfinite(self.relative_humidity_pct)
            and -40.0 <= self.temperature_c <= 125.0
            and 0.0 <= self.relative_humidity_pct <= 100.0
        )

    def quality(self, *, now_monotonic: float, stale_after_seconds: float) -> SensorQuality:
        if self.error_code == "SENSOR_UNAVAILABLE":
            return SensorQuality.UNAVAILABLE
        if not self.is_valid():
            return SensorQuality.FAILED
        if self.age_seconds(now_monotonic=now_monotonic) > stale_after_seconds:
            return SensorQuality.STALE
        return SensorQuality.READY

    def as_dict(self, *, now_monotonic: float | None = None, stale_after_seconds: float | None = None) -> dict[str, object]:
        payload: dict[str, object] = {
            "temperature_c": self.temperature_c,
            "relative_humidity_pct": self.relative_humidity_pct,
            "observed_monotonic": self.observed_monotonic,
            "sensor_address": self.sensor_address,
            "source_backend": self.source_backend,
            "crc_valid": self.crc_valid,
            "valid": self.is_valid(),
            "error_code": self.error_code,
            "physical_evidence": self.physical_evidence,
        }
        if now_monotonic is not None:
            payload["age_seconds"] = self.age_seconds(now_monotonic=now_monotonic)
        if now_monotonic is not None and stale_after_seconds is not None:
            payload["quality"] = self.quality(
                now_monotonic=now_monotonic,
                stale_after_seconds=stale_after_seconds,
            ).value
        return payload
