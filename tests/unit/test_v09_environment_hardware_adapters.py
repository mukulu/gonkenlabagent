from __future__ import annotations

import unittest
from types import SimpleNamespace

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


def _frame(raw_temperature: int, raw_humidity: int) -> list[int]:
    temp = raw_temperature.to_bytes(2, "big")
    humidity = raw_humidity.to_bytes(2, "big")
    return [temp[0], temp[1], crc8(temp), humidity[0], humidity[1], crc8(humidity)]


class FakeBus:
    def __init__(self, frame=None, *, read_error: OSError | None = None) -> None:
        self.frame = _frame(0x6666, 0x8000) if frame is None else list(frame)
        self.read_error = read_error
        self.writes = []
        self.reads = []
        self.closed = False

    def write_i2c_block_data(self, address, command_msb, payload):
        self.writes.append((address, command_msb, list(payload)))

    def read_i2c_block_data(self, address, register, length):
        self.reads.append((address, register, length))
        if self.read_error is not None:
            raise self.read_error
        return self.frame[:length]

    def close(self):
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


class FakeGpiod:
    Direction = Direction
    Value = Value
    LineSettings = FakeLineSettings

    def __init__(self, *, fail_request: bool = False, fail_set: bool = False) -> None:
        self.fail_request = fail_request
        self.fail_set = fail_set
        self.requests = []
        self.last_request = None

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

    def test_sensor_uses_high_repeatability_command_and_injected_bus(self) -> None:
        bus = FakeBus(_frame(0x6666, 0x8000))
        delays = []
        sensor = SHT31Sensor(bus=bus, address=0x44, repeatability="high", sleep_fn=delays.append)
        reading = sensor.read(now_monotonic=12.5)
        self.assertTrue(reading.is_valid())
        self.assertEqual(reading.sensor_address, 0x44)
        self.assertEqual(reading.source_backend, "sht31")
        self.assertEqual(bus.writes, [(0x44, 0x24, [0x00])])
        self.assertEqual(bus.reads, [(0x44, 0x00, 6)])
        self.assertGreaterEqual(delays[0], 0.015)

    def test_sensor_returns_truthful_unavailable_reading_on_bus_error(self) -> None:
        sensor = SHT31Sensor(bus=FakeBus(read_error=OSError("missing")), address=0x45, sleep_fn=lambda _delay: None)
        reading = sensor.read(now_monotonic=1.0)
        self.assertFalse(reading.is_valid())
        self.assertEqual(reading.error_code, "SENSOR_UNAVAILABLE")
        self.assertEqual(reading.sensor_address, 0x45)


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
