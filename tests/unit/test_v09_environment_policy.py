from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gonken_agent.environment import (
    EnvironmentMode,
    EnvironmentPolicy,
    FanCapability,
    PolicyBounds,
    PolicyError,
    PolicyStore,
    SensorQuality,
    SensorReading,
)


class EnvironmentDomainTests(unittest.TestCase):
    def test_capability_boundary_never_claims_speed_or_motion_feedback(self) -> None:
        self.assertEqual(
            FanCapability().as_dict(),
            {
                "power_control": True,
                "software_speed_control": False,
                "fan_motion_observed": False,
            },
        )

    def test_sensor_reading_quality_rejects_crc_error_and_staleness(self) -> None:
        reading = SensorReading(
            temperature_c=27.5,
            relative_humidity_pct=61.0,
            observed_monotonic=10.0,
            sensor_address=0x44,
        )
        self.assertTrue(reading.is_valid())
        self.assertEqual(reading.quality(now_monotonic=11.0, stale_after_seconds=5.0), SensorQuality.READY)
        self.assertEqual(reading.quality(now_monotonic=30.0, stale_after_seconds=5.0), SensorQuality.STALE)
        bad_crc = SensorReading(27.5, 61.0, 10.0, crc_valid=False)
        self.assertEqual(bad_crc.quality(now_monotonic=11.0, stale_after_seconds=5.0), SensorQuality.FAILED)

    def test_mode_parser_accepts_operator_aliases_without_llm_authority(self) -> None:
        self.assertEqual(EnvironmentMode.parse("semi-auto"), EnvironmentMode.SEMI_AUTOMATIC)
        self.assertEqual(EnvironmentMode.parse("auto"), EnvironmentMode.AUTOMATIC)
        with self.assertRaises(ValueError):
            EnvironmentMode.parse("comfort")


class EnvironmentPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bounds = PolicyBounds()

    def test_default_policy_is_manual_with_demonstration_thresholds(self) -> None:
        policy = EnvironmentPolicy.default().validated(bounds=self.bounds)
        self.assertEqual(policy.mode, EnvironmentMode.MANUAL)
        self.assertEqual(policy.start_c, 28.0)
        self.assertEqual(policy.stop_c, 26.0)
        self.assertEqual(policy.minimum_on_seconds, 60)
        self.assertEqual(policy.minimum_off_seconds, 60)

    def test_invalid_thresholds_and_dwell_are_rejected_before_persistence(self) -> None:
        invalid = [
            {"start_c": 26.0, "stop_c": 26.0},
            {"start_c": 28.0, "stop_c": 27.8},
            {"start_c": 70.0, "stop_c": 26.5},
            {"minimum_on_seconds": 1},
            {"minimum_off_seconds": 5000},
        ]
        policy = EnvironmentPolicy.default()
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(PolicyError):
                policy.updated(bounds=self.bounds, **kwargs)

    def test_generation_conflict_rejects_stale_policy_writer(self) -> None:
        policy = EnvironmentPolicy.default()
        with self.assertRaisesRegex(PolicyError, "POLICY_GENERATION_CONFLICT"):
            policy.updated(bounds=self.bounds, expected_generation=99, mode="automatic")
        updated = policy.updated(bounds=self.bounds, expected_generation=1, mode="automatic")
        self.assertEqual(updated.generation, 2)
        self.assertEqual(updated.mode, EnvironmentMode.AUTOMATIC)

    def test_mapping_contract_is_closed_and_round_trips(self) -> None:
        policy = EnvironmentPolicy.default().updated(bounds=self.bounds, mode="semi_automatic")
        payload = policy.to_mapping()
        self.assertEqual(EnvironmentPolicy.from_mapping(payload, bounds=self.bounds), policy)
        payload["extra"] = "not allowed"
        with self.assertRaisesRegex(PolicyError, "unknown policy key"):
            EnvironmentPolicy.from_mapping(payload, bounds=self.bounds)

    def test_policy_store_creates_default_atomically_with_restricted_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "policy.json"
            store = PolicyStore(path, bounds=self.bounds)
            policy = store.load_or_create_default()
            self.assertEqual(policy, EnvironmentPolicy.default())
            self.assertEqual(store.load(), policy)
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o777, 0o640)
            temps = list(Path(temporary).glob("*.tmp"))
            self.assertEqual(temps, [])

    def test_corrupt_policy_file_fails_closed_instead_of_guessing_auto_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "policy.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaisesRegex(PolicyError, "ENV_POLICY_JSON_INVALID"):
                PolicyStore(path, bounds=self.bounds).load()

    def test_policy_store_preserves_old_generation_when_new_policy_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "policy.json"
            store = PolicyStore(path, bounds=self.bounds)
            old = store.load_or_create_default()
            with self.assertRaises(PolicyError):
                store.save(old.updated(bounds=self.bounds, start_c=26.0, stop_c=26.0))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["generation"], old.generation)

    def test_nonmutating_default_and_access_validation_do_not_create_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "policy.json"
            store = PolicyStore(path, bounds=self.bounds)
            self.assertEqual(store.default_policy(), EnvironmentPolicy.default())
            store.validate_access()
            self.assertFalse(path.exists())

    def test_permission_error_is_not_mislabeled_invalid_json(self) -> None:
        store = PolicyStore(Path("/fixture/policy.json"), bounds=self.bounds)
        with mock.patch.object(Path, "read_text", side_effect=PermissionError("denied")), \
             mock.patch.object(Path, "exists", return_value=True), \
             mock.patch("gonken_agent.environment.policy.os.access", return_value=True):
            with self.assertRaises(PolicyError) as caught:
                store.load()
        self.assertEqual(caught.exception.code, "ENV_POLICY_PERMISSION_DENIED")


if __name__ == "__main__":
    unittest.main()
