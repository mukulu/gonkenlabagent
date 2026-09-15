from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from gonken_agent.environment import (
    EnvironmentPolicy,
    EnvironmentServiceCore,
    EnvironmentServiceError,
    EnvironmentController,
    FanPower,
    PolicyBounds,
    SensorReading,
)
from gonken_agent.environment.actuators import ActuatorAdapterError, GpiodRelayFanActuator
from gonken_agent.environment.sensors import SHT31Sensor, SensorAdapterError, crc8, decode_sht31_frame
from gonken_agent.environment.sensors.sht31 import LinuxI2CDevTransport, I2C_SLAVE


def _frame(raw_temperature: int, raw_humidity: int) -> list[int]:
    temp = raw_temperature.to_bytes(2, "big")
    humidity = raw_humidity.to_bytes(2, "big")
    return [temp[0], temp[1], crc8(temp), humidity[0], humidity[1], crc8(humidity)]


class FakeTransport:
    def __init__(self, frame=None, *, read_error: Exception | None = None) -> None:
        self.frame = bytes(_frame(0x6666, 0x8000) if frame is None else frame)
        self.read_error = read_error
        self.writes: list[bytes] = []
        self.reads: list[int] = []
        self.closed = False

    def write(self, payload: bytes) -> None:
        self.writes.append(bytes(payload))

    def read(self, length: int) -> bytes:
        self.reads.append(length)
        if self.read_error is not None:
            raise self.read_error
        return self.frame[:length]

    def close(self) -> None:
        self.closed = True


class Direction:
    OUTPUT = "output"


class Value:
    ACTIVE = "active"
    INACTIVE = "inactive"


class FakeLineSettings:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class FakeRequest:
    def __init__(self, *, fail_set: bool = False) -> None:
        self.values = []
        self.released = False
        self.fail_set = fail_set

    def set_value(self, line, value):
        if self.fail_set:
            raise OSError("write failed")
        self.values.append((line, value))

    def release(self):
        self.released = True


class FakeChip:
    def __init__(self, lines):
        self.lines = list(lines)
        self.closed = False

    def get_info(self):
        return SimpleNamespace(num_lines=len(self.lines))

    def get_line_info(self, offset):
        return SimpleNamespace(name=self.lines[offset])

    def close(self):
        self.closed = True


class FakeGpiod:
    Direction = Direction
    Value = Value
    LineSettings = FakeLineSettings

    def __init__(self, *, fail_request: bool = False, fail_set: bool = False, chips=None) -> None:
        self.fail_request = fail_request
        self.fail_set = fail_set
        self.chips = dict(chips or {})
        self.requests = []
        self.last_request = None

    def Chip(self, chip_path):
        if chip_path not in self.chips:
            raise OSError("missing")
        return FakeChip(self.chips[chip_path])

    def request_lines(self, chip_path, *, consumer, config):
        if self.fail_request:
            raise OSError("busy")
        request = FakeRequest(fail_set=self.fail_set)
        self.requests.append((chip_path, consumer, config))
        self.last_request = request
        return request


class SHT31AdapterTests(unittest.TestCase):
    def test_crc_matches_sensirion_datasheet_example(self) -> None:
        self.assertEqual(crc8(bytes([0xBE, 0xEF])), 0x92)

    def test_decode_valid_frame_converts_temperature_and_humidity(self) -> None:
        decoded = decode_sht31_frame(_frame(0x6666, 0x8000))
        self.assertAlmostEqual(decoded.temperature_c, -45.0 + 175.0 * 0x6666 / 65535.0, places=6)
        self.assertAlmostEqual(decoded.relative_humidity_pct, 100.0 * 0x8000 / 65535.0, places=6)

    def test_decode_rejects_bad_crc(self) -> None:
        frame = _frame(0x6666, 0x8000)
        frame[2] ^= 0xFF
        with self.assertRaises(SensorAdapterError) as ctx:
            decode_sht31_frame(frame)
        self.assertEqual(ctx.exception.code, "SENSOR_CRC_FAILED")

    def test_status_read_and_heater_disable_use_exact_sht31_commands(self) -> None:
        status_word = bytes([0x20, 0x00])
        status_crc = crc8(status_word)
        transport = FakeTransport(status_word + bytes([status_crc]))
        sensor = SHT31Sensor(transport=transport, sleep_fn=lambda _seconds: None)
        self.assertTrue(sensor.heater_enabled())
        sensor.disable_heater()
        self.assertEqual(transport.writes[0], b"\xf3\x2d")
        self.assertEqual(transport.writes[1], b"\x30\x66")

    def test_soft_reset_and_clear_status_commands_are_exact(self) -> None:
        transport = FakeTransport()
        sensor = SHT31Sensor(transport=transport, sleep_fn=lambda _seconds: None)
        sensor.soft_reset(); sensor.clear_status()
        self.assertEqual(transport.writes, [b"\x30\xa2", b"\x30\x41"])

    def test_status_crc_failure_is_fail_closed(self) -> None:
        transport = FakeTransport(b"\x00\x00\xff")
        sensor = SHT31Sensor(transport=transport, sleep_fn=lambda _seconds: None)
        with self.assertRaisesRegex(SensorAdapterError, "status CRC"):
            sensor.read_status()

    def test_sensor_uses_exact_two_byte_command_then_raw_six_byte_read(self) -> None:
        transport = FakeTransport(_frame(0x6666, 0x8000))
        delays = []
        sensor = SHT31Sensor(transport=transport, address=0x44, repeatability="high", sleep_fn=delays.append)
        reading = sensor.read(now_monotonic=12.5)
        self.assertTrue(reading.is_valid())
        self.assertEqual(reading.sensor_address, 0x44)
        self.assertEqual(reading.source_backend, "sht31")
        self.assertEqual(transport.writes, [bytes([0x24, 0x00])])
        self.assertEqual(transport.reads, [6])
        self.assertGreaterEqual(delays[0], 0.015)

    def test_sensor_transport_error_is_truthful_and_never_invents_values(self) -> None:
        sensor = SHT31Sensor(transport=FakeTransport(read_error=SensorAdapterError("SENSOR_TRANSPORT_ERROR", "missing")), address=0x45, sleep_fn=lambda _delay: None)
        reading = sensor.read(now_monotonic=1.0)
        self.assertFalse(reading.is_valid())
        self.assertEqual(reading.error_code, "SENSOR_TRANSPORT_ERROR")
        self.assertEqual(reading.sensor_address, 0x45)
        self.assertIsNone(reading.temperature_c)
        self.assertIsNone(reading.relative_humidity_pct)

    def test_linux_transport_selects_slave_and_writes_reads_exact_bytes(self) -> None:
        transport = LinuxI2CDevTransport(bus_number=1, address=0x44)
        with mock.patch("gonken_agent.environment.sensors.sht31.os.open", return_value=12) as opened, \
             mock.patch("gonken_agent.environment.sensors.sht31.fcntl.ioctl") as ioctl, \
             mock.patch("gonken_agent.environment.sensors.sht31.os.write", return_value=2) as written, \
             mock.patch("gonken_agent.environment.sensors.sht31.os.read", return_value=b"abcdef") as read, \
             mock.patch("gonken_agent.environment.sensors.sht31.os.close") as closed:
            transport.write(bytes([0x24, 0x00]))
            payload = transport.read(6)
            transport.close()
        opened.assert_called_once()
        ioctl.assert_called_once_with(12, I2C_SLAVE, 0x44)
        written.assert_called_once_with(12, bytes([0x24, 0x00]))
        read.assert_called_once_with(12, 6)
        closed.assert_called_once_with(12)
        self.assertEqual(payload, b"abcdef")

    def test_owned_transport_is_recreated_after_transport_failure_for_recovery(self) -> None:
        first = FakeTransport(read_error=SensorAdapterError("SENSOR_TRANSPORT_ERROR", "unplugged"))
        second = FakeTransport(_frame(0x6666, 0x8000))
        transports = iter((first, second))
        sensor = SHT31Sensor(transport_factory=lambda **_: next(transports), address=0x44, sleep_fn=lambda _delay: None)
        failed = sensor.read(now_monotonic=1.0)
        recovered = sensor.read(now_monotonic=2.0)
        self.assertEqual(failed.error_code, "SENSOR_TRANSPORT_ERROR")
        self.assertTrue(first.closed)
        self.assertTrue(recovered.is_valid())
        self.assertEqual(second.writes, [bytes([0x24, 0x00])])

    def test_sensor_rejects_address_outside_sht31_44_45_contract(self) -> None:
        with self.assertRaises(SensorAdapterError) as ctx:
            SHT31Sensor(address=0x46)
        self.assertEqual(ctx.exception.code, "SENSOR_CONFIG_INVALID")

    def test_linux_transport_short_read_fails_closed(self) -> None:
        transport = LinuxI2CDevTransport(bus_number=1, address=0x44)
        with mock.patch("gonken_agent.environment.sensors.sht31.os.open", return_value=12), \
             mock.patch("gonken_agent.environment.sensors.sht31.fcntl.ioctl"), \
             mock.patch("gonken_agent.environment.sensors.sht31.os.read", return_value=b"abc"), \
             mock.patch("gonken_agent.environment.sensors.sht31.os.close"):
            with self.assertRaises(SensorAdapterError) as ctx:
                transport.read(6)
            transport.close()
        self.assertEqual(ctx.exception.code, "SENSOR_FRAME_INVALID")


class GpiodRelayAdapterTests(unittest.TestCase):
    def test_relay_requests_line_inactive_and_reports_power_only_capability(self) -> None:
        module = FakeGpiod()
        relay = GpiodRelayFanActuator(
            chip_path="/dev/gpiochip-test",
            line_offset=23,
            active_high=True,
            gpiod_module=module,
        )
        relay.open()
        self.assertEqual(len(module.requests), 1)
        chip_path, consumer, config = module.requests[0]
        self.assertEqual(chip_path, "/dev/gpiochip-test")
        self.assertEqual(consumer, "gonken-environment")
        settings = config[23]
        self.assertEqual(settings.kwargs["direction"], Direction.OUTPUT)
        self.assertFalse(settings.kwargs["active_low"])
        self.assertEqual(settings.kwargs["output_value"], Value.INACTIVE)
        caps = relay.capabilities()
        self.assertTrue(caps.power_control)
        self.assertFalse(caps.software_speed_control)
        self.assertFalse(caps.fan_motion_observed)

    def test_relay_sets_logical_power_and_safe_off_on_close(self) -> None:
        module = FakeGpiod()
        relay = GpiodRelayFanActuator(line_offset=23, active_high=False, gpiod_module=module)
        relay.set_power(FanPower.ON)
        relay.set_power("off")
        request = module.last_request
        self.assertEqual(request.values, [(23, Value.ACTIVE), (23, Value.INACTIVE)])
        self.assertEqual(relay.commanded_power, FanPower.OFF)
        relay.close()
        self.assertEqual(request.values[-1], (23, Value.INACTIVE))
        self.assertTrue(request.released)
        settings = module.requests[0][2][23]
        self.assertTrue(settings.kwargs["active_low"])

    def test_relay_discovers_logical_bcm_by_line_name_without_chip0_offset_assumption(self) -> None:
        lines = [None] * 40
        lines[7] = "GPIO23"
        module = FakeGpiod(chips={"/dev/gpiochip4": lines})
        relay = GpiodRelayFanActuator(
            logical_bcm=23,
            active_high=True,
            gpiod_module=module,
            chip_paths=["/dev/gpiochip4"],
        )
        relay.open()
        self.assertEqual(module.requests[0][0], "/dev/gpiochip4")
        self.assertIn(7, module.requests[0][2])
        identity = relay.resolved_identity()
        self.assertEqual(identity["logical_bcm"], 23)
        self.assertEqual(identity["line_name"], "GPIO23")
        self.assertEqual(identity["line_offset"], 7)
        self.assertFalse(identity["physical_acceptance_claimed"])

    def test_relay_discovery_fails_closed_for_missing_or_ambiguous_line_name(self) -> None:
        with self.subTest("missing"):
            relay = GpiodRelayFanActuator(
                logical_bcm=23, active_high=True,
                gpiod_module=FakeGpiod(chips={"/dev/gpiochip4": ["GPIO22"]}),
                chip_paths=["/dev/gpiochip4"],
            )
            with self.assertRaises(ActuatorAdapterError) as ctx:
                relay.open()
            self.assertEqual(ctx.exception.code, "ACTUATOR_GPIO_LINE_NOT_FOUND")
        with self.subTest("ambiguous"):
            relay = GpiodRelayFanActuator(
                logical_bcm=23, active_high=True,
                gpiod_module=FakeGpiod(chips={"/dev/gpiochip0": ["GPIO23"], "/dev/gpiochip4": ["GPIO23"]}),
                chip_paths=["/dev/gpiochip0", "/dev/gpiochip4"],
            )
            with self.assertRaises(ActuatorAdapterError) as ctx:
                relay.open()
            self.assertEqual(ctx.exception.code, "ACTUATOR_GPIO_LINE_AMBIGUOUS")

    def test_relay_write_failure_is_reported_as_actuator_unavailable(self) -> None:
        relay = GpiodRelayFanActuator(line_offset=23, active_high=True, gpiod_module=FakeGpiod(fail_set=True))
        with self.assertRaises(ActuatorAdapterError) as ctx:
            relay.set_power(FanPower.ON)
        self.assertEqual(ctx.exception.code, "ACTUATOR_UNAVAILABLE")


class ServiceHardwareBoundaryTests(unittest.TestCase):
    def test_service_applies_controller_state_to_injected_actuator(self) -> None:
        class RecordingActuator:
            def __init__(self) -> None:
                self.calls = []

            def set_power(self, power):
                self.calls.append(FanPower.parse(power))

            def capabilities(self):
                from gonken_agent.environment import FanCapability

                return FanCapability()

        actuator = RecordingActuator()
        core = EnvironmentServiceCore.with_defaults(fan_actuator=actuator, now=lambda: 10.0)
        from gonken_agent.environment.protocol import make_request

        result = core.handle(make_request("fan.set", {"power": "on"}))
        self.assertEqual(result["state"]["fan_power"], "on")
        self.assertEqual(actuator.calls, [FanPower.ON])
        self.assertFalse(result["physical_evidence"])

    def test_service_fails_closed_when_actuator_write_fails(self) -> None:
        class FailingActuator:
            def __init__(self) -> None:
                self.safe_off_called = False

            def set_power(self, power):
                raise RuntimeError("relay failure")

            def safe_off(self):
                self.safe_off_called = True

            def capabilities(self):
                from gonken_agent.environment import FanCapability

                return FanCapability()

        actuator = FailingActuator()
        core = EnvironmentServiceCore.with_defaults(fan_actuator=actuator, now=lambda: 10.0)
        from gonken_agent.environment.protocol import make_request

        with self.assertRaises(EnvironmentServiceError) as ctx:
            core.handle(make_request("fan.set", {"power": "on"}))
        self.assertEqual(ctx.exception.code, "ACTUATOR_UNAVAILABLE")
        self.assertTrue(actuator.safe_off_called)
        self.assertEqual(core.controller.state.fan_power, FanPower.OFF)
        self.assertEqual(core.controller.state.last_transition_reason.value, "ACTUATOR_ERROR_SAFE_OFF")


if __name__ == "__main__":
    unittest.main()
