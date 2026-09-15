"""SHT31-D I2C sensor adapter using the Linux ``i2c-dev`` byte stream.

The production transaction intentionally mirrors Sensirion's single-shot wire
protocol: select the 7-bit slave address, write exactly the two-byte command,
wait the documented conversion time, then read exactly six response bytes.
No SMBus register/command byte is inserted into the read transaction.

The module remains host-testable because tests inject a transport object with
``write(bytes)``, ``read(length)`` and ``close()`` methods.  Production uses
only Python's standard library plus the Linux ``/dev/i2c-N`` ABI.
"""
from __future__ import annotations

import errno
import fcntl
import os
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Any, Callable, Protocol, Sequence

from ..domain import SensorReading
from .base import SensorAdapterError

SHT31_DEFAULT_ADDRESS = 0x44
SHT31_ALTERNATE_ADDRESS = 0x45
SHT31_FRAME_LENGTH = 6
SHT31_STATUS_FRAME_LENGTH = 3
I2C_SLAVE = 0x0703

SHT31_SOFT_RESET_COMMAND = 0x30A2
SHT31_HEATER_ENABLE_COMMAND = 0x306D
SHT31_HEATER_DISABLE_COMMAND = 0x3066
SHT31_STATUS_READ_COMMAND = 0xF32D
SHT31_STATUS_CLEAR_COMMAND = 0x3041
SHT31_STATUS_HEATER_BIT = 13

CRC_POLYNOMIAL = 0x31
CRC_INITIAL = 0xFF

# Single-shot measurement commands from the SHT3x-DIS command table.
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


class SHT31Transport(Protocol):
    def write(self, payload: bytes) -> None: ...
    def read(self, length: int) -> bytes: ...
    def close(self) -> None: ...


class LinuxI2CDevTransport:
    """Minimal Linux i2c-dev transport with exact byte-stream semantics."""

    def __init__(self, *, bus_number: int, address: int) -> None:
        self.bus_number = bus_number
        self.address = address
        self.path = Path(f"/dev/i2c-{bus_number}")
        self._fd: int | None = None

    def open(self) -> None:
        if self._fd is not None:
            return
        try:
            fd = os.open(self.path, os.O_RDWR | getattr(os, "O_CLOEXEC", 0))
        except FileNotFoundError as exc:
            raise SensorAdapterError("SENSOR_I2C_DEVICE_MISSING", f"I2C device does not exist: {self.path}") from exc
        except PermissionError as exc:
            raise SensorAdapterError("SENSOR_I2C_PERMISSION", f"permission denied opening {self.path}") from exc
        except OSError as exc:
            raise SensorAdapterError("SENSOR_UNAVAILABLE", f"cannot open I2C device: {self.path}") from exc
        try:
            fcntl.ioctl(fd, I2C_SLAVE, self.address)
        except PermissionError as exc:
            os.close(fd)
            raise SensorAdapterError("SENSOR_I2C_PERMISSION", "permission denied selecting SHT31 address") from exc
        except OSError as exc:
            os.close(fd)
            raise SensorAdapterError("SENSOR_UNAVAILABLE", "cannot select SHT31 I2C address") from exc
        self._fd = fd

    def write(self, payload: bytes) -> None:
        self.open()
        assert self._fd is not None
        try:
            written = os.write(self._fd, payload)
        except OSError as exc:
            raise SensorAdapterError("SENSOR_TRANSPORT_ERROR", "SHT31 command write failed") from exc
        if written != len(payload):
            raise SensorAdapterError("SENSOR_TRANSPORT_ERROR", f"short SHT31 command write: {written}/{len(payload)}")

    def read(self, length: int) -> bytes:
        self.open()
        assert self._fd is not None
        try:
            payload = os.read(self._fd, length)
        except OSError as exc:
            raise SensorAdapterError("SENSOR_TRANSPORT_ERROR", "SHT31 response read failed") from exc
        if len(payload) != length:
            raise SensorAdapterError("SENSOR_FRAME_INVALID", f"short SHT31 response: {len(payload)}/{length}")
        return payload

    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


def crc8(data: bytes | bytearray | Sequence[int]) -> int:
    """Return Sensirion CRC-8 for one two-byte SHT3x word."""
    crc = CRC_INITIAL
    for raw_byte in data:
        value = int(raw_byte)
        if value < 0 or value > 0xFF:
            raise ValueError("CRC input bytes must be in range 0..255")
        crc ^= value
        for _bit in range(8):
            crc = ((crc << 1) ^ CRC_POLYNOMIAL) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
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
    temperature_c = -45.0 + 175.0 * raw_temperature / 65535.0
    relative_humidity_pct = 100.0 * raw_humidity / 65535.0
    return SHT31DecodedFrame(temperature_c, relative_humidity_pct, raw_temperature, raw_humidity)


class SHT31Sensor:
    """Read SHT31-D measurements through an exact byte-stream transport."""

    def __init__(
        self,
        *,
        transport: SHT31Transport | None = None,
        bus_number: int = 1,
        address: int = SHT31_DEFAULT_ADDRESS,
        repeatability: str = "high",
        clock_stretching: bool = False,
        sleep_fn: Callable[[float], None] = sleep,
        transport_factory: Callable[..., SHT31Transport] = LinuxI2CDevTransport,
    ) -> None:
        if isinstance(bus_number, bool) or not isinstance(bus_number, int) or bus_number < 0:
            raise SensorAdapterError("SENSOR_CONFIG_INVALID", "i2c bus number must be a non-negative integer")
        if isinstance(address, bool) or not isinstance(address, int) or address not in {SHT31_DEFAULT_ADDRESS, SHT31_ALTERNATE_ADDRESS}:
            raise SensorAdapterError("SENSOR_CONFIG_INVALID", "SHT31 address must be 0x44 or 0x45")
        selected_repeatability = repeatability.strip().lower().replace("-", "_")
        if selected_repeatability not in {"high", "medium", "low"}:
            raise SensorAdapterError("SENSOR_CONFIG_INVALID", "repeatability must be high, medium or low")
        self.bus_number = bus_number
        self.address = address
        self.repeatability = selected_repeatability
        self.clock_stretching = bool(clock_stretching)
        self.sleep_fn = sleep_fn
        self._transport = transport
        self._transport_factory = transport_factory
        self._owns_transport = transport is None

    @classmethod
    def from_config(cls, env_config: Any) -> "SHT31Sensor":
        return cls(
            bus_number=int(env_config.i2c_bus),
            address=int(env_config.i2c_address),
            repeatability=str(env_config.sensor_repeatability),
        )

    def read(self, *, now_monotonic: float) -> SensorReading:
        try:
            decoded = decode_sht31_frame(self._read_frame())
        except SensorAdapterError as exc:
            if exc.code in {"SENSOR_I2C_DEVICE_MISSING", "SENSOR_I2C_PERMISSION", "SENSOR_UNAVAILABLE", "SENSOR_TRANSPORT_ERROR", "SENSOR_FRAME_INVALID"}:
                self._reset_owned_transport()
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
        transport = self._transport
        if self._owns_transport and transport is not None:
            transport.close()
        self._transport = None

    def read_status(self) -> int:
        """Return the CRC-validated 16-bit SHT31 status register."""
        transport = self._ensure_transport()
        transport.write(SHT31_STATUS_READ_COMMAND.to_bytes(2, "big"))
        self.sleep_fn(0.001)
        payload = transport.read(SHT31_STATUS_FRAME_LENGTH)
        if len(payload) != SHT31_STATUS_FRAME_LENGTH:
            raise SensorAdapterError("SENSOR_FRAME_INVALID", "SHT31 status frame must contain exactly 3 bytes")
        word = bytes(payload[:2])
        if crc8(word) != int(payload[2]):
            raise SensorAdapterError("SENSOR_CRC_FAILED", "SHT31 status CRC check failed")
        return (int(payload[0]) << 8) | int(payload[1])

    def heater_enabled(self) -> bool:
        return bool(self.read_status() & (1 << SHT31_STATUS_HEATER_BIT))

    def disable_heater(self) -> None:
        """Force the plausibility-check heater OFF for ordinary room monitoring."""
        transport = self._ensure_transport()
        transport.write(SHT31_HEATER_DISABLE_COMMAND.to_bytes(2, "big"))
        self.sleep_fn(0.001)

    def soft_reset(self) -> None:
        transport = self._ensure_transport()
        transport.write(SHT31_SOFT_RESET_COMMAND.to_bytes(2, "big"))
        self.sleep_fn(0.002)

    def clear_status(self) -> None:
        transport = self._ensure_transport()
        transport.write(SHT31_STATUS_CLEAR_COMMAND.to_bytes(2, "big"))
        self.sleep_fn(0.001)

    def _read_frame(self) -> list[int]:
        transport = self._ensure_transport()
        command, delay_seconds = _command_for(self.repeatability, self.clock_stretching)
        # Critical protocol contract: exactly two command bytes.  There is no
        # register byte before the subsequent six-byte read.
        transport.write(command.to_bytes(2, "big"))
        self.sleep_fn(delay_seconds)
        data = transport.read(SHT31_FRAME_LENGTH)
        return [int(value) for value in data]

    def _ensure_transport(self) -> SHT31Transport:
        if self._transport is None:
            try:
                self._transport = self._transport_factory(bus_number=self.bus_number, address=self.address)
            except SensorAdapterError:
                raise
            except Exception as exc:
                raise SensorAdapterError("SENSOR_UNAVAILABLE", "cannot create Linux I2C transport") from exc
        return self._transport


    def _reset_owned_transport(self) -> None:
        transport = self._transport
        if self._owns_transport and transport is not None:
            try:
                transport.close()
            finally:
                self._transport = None

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
