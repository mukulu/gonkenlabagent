from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sht31_diagnostic", ROOT / "scripts" / "sht31_diagnostic.py")
assert SPEC and SPEC.loader
diag = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = diag
SPEC.loader.exec_module(diag)


class Reading:
    def __init__(self, valid: bool, *, temp=22.0, humidity=50.0, error=None):
        self.temperature_c = temp if valid else None
        self.relative_humidity_pct = humidity if valid else None
        self.error_code = error
        self._valid = valid
    def is_valid(self):
        return self._valid


class FakeSensor:
    def __init__(self, readings, *, heater=False):
        self.readings = list(readings)
        self.closed = False
        self.heater = heater
    def heater_enabled(self):
        return self.heater
    def disable_heater(self):
        self.heater = False
    def read(self, *, now_monotonic):
        return self.readings.pop(0)
    def close(self):
        self.closed = True


def factory_for(mapping):
    def factory(*, bus_number, address, repeatability):
        assert bus_number == 1
        assert repeatability == "high"
        return FakeSensor(mapping[address])
    return factory


class SHT31DiagnosticTests(unittest.TestCase):
    def test_discover_accepts_exactly_one_valid_supported_address(self) -> None:
        factory = factory_for({0x44: [Reading(True)], 0x45: [Reading(False, error="SENSOR_UNAVAILABLE")]})
        address, errors = diag.discover(bus=1, sensor_factory=factory)
        self.assertEqual(address, 0x44)
        self.assertEqual(errors, {0x45: "SENSOR_UNAVAILABLE"})

    def test_discover_rejects_ambiguous_two_sensor_result(self) -> None:
        factory = factory_for({0x44: [Reading(True)], 0x45: [Reading(True)]})
        with self.assertRaisesRegex(RuntimeError, "SHT31_ADDRESS_AMBIGUOUS"):
            diag.discover(bus=1, sensor_factory=factory)

    def test_discover_rejects_no_valid_sensor(self) -> None:
        factory = factory_for({
            0x44: [Reading(False, error="SENSOR_CRC_FAILED")],
            0x45: [Reading(False, error="SENSOR_UNAVAILABLE")],
        })
        with self.assertRaisesRegex(RuntimeError, "SHT31_ADDRESS_NOT_FOUND"):
            diag.discover(bus=1, sensor_factory=factory)

    def test_campaign_reports_every_invalid_read_and_never_claims_physical_acceptance(self) -> None:
        readings = [Reading(True, temp=21.0, humidity=45.0), Reading(False, error="SENSOR_CRC_FAILED"), Reading(True, temp=23.0, humidity=55.0)]
        result = diag.campaign(0x44, bus=1, reads=3, sensor_factory=lambda **_: FakeSensor(readings))
        self.assertEqual(result["valid_reads"], 2)
        self.assertEqual(result["invalid_reads"], 1)
        self.assertEqual(result["error_counts"], {"SENSOR_CRC_FAILED": 1})
        self.assertFalse(result["all_valid"])
        self.assertTrue(result["heater_off_verified"])
        self.assertEqual(result["temperature_c"]["mean"], 22.0)
        self.assertEqual(result["relative_humidity_pct"]["mean"], 50.0)

    def test_campaign_turns_heater_off_before_room_monitoring(self) -> None:
        sensor = FakeSensor([Reading(True)], heater=True)
        result = diag.campaign(0x44, bus=1, reads=1, sensor_factory=lambda **_: sensor)
        self.assertTrue(result["heater_initially_enabled"])
        self.assertTrue(result["heater_off_verified"])
        self.assertFalse(sensor.heater)

    def test_json_output_is_bounded_and_marks_acceptance_false(self) -> None:
        with patch.object(diag, "discover", return_value=(0x44, {})), \
             patch.object(diag, "campaign", return_value={
                 "reads_requested": 2, "valid_reads": 2, "invalid_reads": 0,
                 "error_counts": {}, "temperature_c": {"min": 20.0, "max": 21.0, "mean": 20.5},
                 "relative_humidity_pct": {"min": 40.0, "max": 41.0, "mean": 40.5}, "all_valid": True,
                 "heater_initially_enabled": False, "heater_off_verified": True,
             }):
            output = StringIO()
            with redirect_stdout(output):
                rc = diag.main(["--address", "auto", "--reads", "2", "--json"])
        payload = json.loads(output.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(payload["address"], "0x44")
        self.assertFalse(payload["physical_acceptance_claimed"])

    def test_usage_rejects_unsupported_address_without_opening_sensor(self) -> None:
        errors = StringIO()
        with redirect_stderr(errors):
            rc = diag.main(["--address", "0x46", "--reads", "1"])
        self.assertEqual(rc, 64)
        self.assertIn("SHT31_DIAGNOSTIC_USAGE", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
