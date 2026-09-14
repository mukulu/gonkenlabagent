"""SHT31-D I2C sensor adapter.

The module is safe to import on non-Raspberry-Pi hosts.  It imports the Debian
``python3-smbus`` module only when a production bus object is requested.  Unit
tests inject fake bus objects so CRC, command and conversion behavior remain
host-verifiable without touching ``/dev/i2c-*``.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Callable, Sequence, Any

from ..domain import SensorReading
from .base import SensorAdapterError

SHT31_DEFAULT_ADDRESS = 0x44
SHT31_ALTERNATE_ADDRESS = 0x45
SHT31_FRAME_LENGTH = 6

CRC_POLYNOMIAL = 0x31
CRC_INITIAL = 0xFF

# Single-shot measurement commands.  The V09 default uses high repeatability
# without clock stretching (0x2400), which fits ordinary SMBus transactions.
_SINGLE_SHOT_COMMANDS: dict[tuple[str, bool], tuple[int, float]] = {
    ("high", False): (0x2400, 0.016),
    ("medium", False): (0x240B, 0.007),
    ("low", False): (0x2416, 0.005),
    ("high", True): (0x2C06, 0.016),
    ("medium", True): (0x2C0D, 0.007),
    ("low", True): (0x2C10, 0.005),
}


@dataclass(frozen=True, slots=True)
class SHT31DecodedFrame:
    temperature_c: float
    relative_humidity_pct: float
    raw_temperature: int
    raw_humidity: int


def crc8(data: bytes | bytearray | Sequence[int]) -> int:
    """Return Sensirion CRC-8 for one two-byte SHT3x word."""

    crc = CRC_INITIAL
    for raw_byte in data:
        value = int(raw_byte)
        if value < 0 or value > 0xFF:
            raise ValueError("CRC input bytes must be in range 0..255")
        crc ^= value
        for _bit in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ CRC_POLYNOMIAL) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def decode_sht31_frame(data: bytes | bytearray | Sequence[int]) -> SHT31DecodedFrame:
    """Decode a six-byte SHT31 frame and validate both CRC bytes."""

    frame = [int(value) for value in data]
    if len(frame) != SHT31_FRAME_LENGTH:
        raise SensorAdapterError("SENSOR_FRAME_INVALID", "SHT31 frame must contain exactly 6 bytes")
    if any(value < 0 or value > 0xFF for value in frame):
        raise SensorAdapterError("SENSOR_FRAME_INVALID", "SHT31 frame bytes must be in range 0..255")

    temp_word = bytes(frame[0:2])
    humidity_word = bytes(frame[3:5])
    if crc8(temp_word) != frame[2]:
        raise SensorAdapterError("SENSOR_CRC_FAILED", "temperature CRC check failed")
    if crc8(humidity_word) != frame[5]:
        raise SensorAdapterError("SENSOR_CRC_FAILED", "humidity CRC check failed")

    raw_temperature = (frame[0] << 8) | frame[1]
    raw_humidity = (frame[3] << 8) | frame[4]
    denominator = 65535.0
    temperature_c = -45.0 + (175.0 * raw_temperature / denominator)
    relative_humidity_pct = 100.0 * raw_humidity / denominator
    return SHT31DecodedFrame(
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
        raw_temperature=raw_temperature,
        raw_humidity=raw_humidity,
    )


class SHT31Sensor:
    """Read SHT31-D measurements through an SMBus-like object."""

    def __init__(
        self,
        *,
        bus: Any | None = None,
        bus_number: int = 1,
        address: int = SHT31_DEFAULT_ADDRESS,
        repeatability: str = "high",
        clock_stretching: bool = False,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        if isinstance(bus_number, bool) or not isinstance(bus_number, int) or bus_number < 0:
            raise SensorAdapterError("SENSOR_CONFIG_INVALID", "i2c bus number must be a non-negative integer")
        if isinstance(address, bool) or not isinstance(address, int) or not 0 <= address <= 0x7F:
            raise SensorAdapterError("SENSOR_CONFIG_INVALID", "i2c address must be a 7-bit integer")
        selected_repeatability = repeatability.strip().lower().replace("-", "_")
        if selected_repeatability not in {"high", "medium", "low"}:
            raise SensorAdapterError("SENSOR_CONFIG_INVALID", "repeatability must be high, medium or low")
        self.bus_number = bus_number
        self.address = address
        self.repeatability = selected_repeatability
        self.clock_stretching = bool(clock_stretching)
        self.sleep_fn = sleep_fn
        self._bus = bus
        self._owns_bus = bus is None

    @classmethod
    def from_config(cls, env_config: Any) -> "SHT31Sensor":
        return cls(
            bus_number=int(env_config.i2c_bus),
            address=int(env_config.i2c_address),
            repeatability=str(env_config.sensor_repeatability),
        )

    def read(self, *, now_monotonic: float) -> SensorReading:
        try:
            frame = self._read_frame()
            decoded = decode_sht31_frame(frame)
        except SensorAdapterError as exc:
            return SensorReading(
                temperature_c=None,
                relative_humidity_pct=None,
                observed_monotonic=float(now_monotonic),
                sensor_address=self.address,
                source_backend="sht31",
                crc_valid=exc.code != "SENSOR_CRC_FAILED",
                error_code=exc.code,
            )
        except OSError:
            return self._unavailable_reading(now_monotonic)
        except Exception:
            return SensorReading(
                temperature_c=None,
                relative_humidity_pct=None,
                observed_monotonic=float(now_monotonic),
                sensor_address=self.address,
                source_backend="sht31",
                crc_valid=False,
                error_code="SENSOR_READ_FAILED",
            )
        return SensorReading(
            temperature_c=decoded.temperature_c,
            relative_humidity_pct=decoded.relative_humidity_pct,
            observed_monotonic=float(now_monotonic),
            sensor_address=self.address,
            source_backend="sht31",
            crc_valid=True,
            error_code=None,
        )

    def close(self) -> None:
        bus = self._bus
        if self._owns_bus and bus is not None:
            close = getattr(bus, "close", None)
            if callable(close):
                close()
        self._bus = None

    def _read_frame(self) -> list[int]:
        bus = self._ensure_bus()
        command, delay_seconds = _command_for(self.repeatability, self.clock_stretching)
        command_msb = (command >> 8) & 0xFF
        command_lsb = command & 0xFF
        bus.write_i2c_block_data(self.address, command_msb, [command_lsb])
        self.sleep_fn(delay_seconds)
        data = bus.read_i2c_block_data(self.address, 0x00, SHT31_FRAME_LENGTH)
        return [int(value) for value in data]

    def _ensure_bus(self) -> Any:
        if self._bus is not None:
            return self._bus
        try:
            import smbus  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - host tests inject bus objects
            raise SensorAdapterError("SENSOR_DEPENDENCY_MISSING", "python3-smbus is not importable") from exc
        try:
            self._bus = smbus.SMBus(self.bus_number)
        except OSError as exc:
            raise SensorAdapterError("SENSOR_UNAVAILABLE", "cannot open I2C bus") from exc
        return self._bus

    def _unavailable_reading(self, now_monotonic: float) -> SensorReading:
        return SensorReading(
            temperature_c=None,
            relative_humidity_pct=None,
            observed_monotonic=float(now_monotonic),
            sensor_address=self.address,
            source_backend="sht31",
            crc_valid=False,
            error_code="SENSOR_UNAVAILABLE",
        )


def _command_for(repeatability: str, clock_stretching: bool) -> tuple[int, float]:
    try:
        return _SINGLE_SHOT_COMMANDS[(repeatability, clock_stretching)]
    except KeyError as exc:
        raise SensorAdapterError("SENSOR_CONFIG_INVALID", "unsupported SHT31 command profile") from exc
