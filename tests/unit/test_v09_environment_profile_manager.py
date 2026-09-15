from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("environment_profile_manager", ROOT / "scripts" / "environment_profile_manager.py")
assert SPEC and SPEC.loader
profile_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile_manager)


class EnvironmentProfileManagerTests(unittest.TestCase):
    def test_every_governed_profile_is_atomic_exact_and_idempotent(self) -> None:
        for name in profile_manager.PROFILE_SPECS:
            with self.subTest(profile=name), tempfile.TemporaryDirectory() as temporary:
                site = Path(temporary) / "config.toml"
                first = profile_manager.ensure_profile(site, name=name, group="ignored")
                second = profile_manager.ensure_profile(site, name=name, group="ignored")
                self.assertEqual(first, "CREATED")
                self.assertEqual(second, "ALREADY_CONFIGURED")
                self.assertEqual(site.read_text(encoding="utf-8"), profile_manager.profile_text(name))
                self.assertEqual(site.stat().st_mode & 0o777, 0o640)
                self.assertEqual(profile_manager.detect_managed_profile(site), name)
                self.assertEqual(list(site.parent.glob(f".{site.name}.*")), [])

    def test_managed_profiles_transition_atomically_without_actuation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "config.toml"
            profile_manager.ensure_profile(site, name="full-simulation", group="ignored")
            result = profile_manager.ensure_profile(site, name="real-sensor-simulated-actuator", group="ignored")
            self.assertEqual(result, "TRANSITIONED_FROM_FULL_SIMULATION")
            self.assertEqual(profile_manager.detect_managed_profile(site), "real-sensor-simulated-actuator")
            self.assertNotIn("systemctl", site.read_text(encoding="utf-8"))

    def test_existing_unknown_admin_configuration_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "config.toml"
            original = '[extensions.environment]\nenabled = false\n[other]\nvalue = 1\n'
            site.write_text(original, encoding="utf-8")
            with self.assertRaises(profile_manager.ProfileError) as raised:
                profile_manager.ensure_profile(site, name="full-simulation", group="ignored")
            self.assertEqual(raised.exception.code, "ENV_PROFILE_CONFLICT")
            self.assertEqual(site.read_text(encoding="utf-8"), original)

    def test_symlink_site_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.toml"
            target.write_text(profile_manager.PROFILE_TEXT, encoding="utf-8")
            site = root / "config.toml"
            site.symlink_to(target)
            with self.assertRaises(profile_manager.ProfileError) as raised:
                profile_manager.ensure_profile(site, name="sensor-deferred-relay", group="ignored")
            self.assertEqual(raised.exception.code, "ENV_PROFILE_UNSAFE")

    def test_profiles_cover_all_backend_parity_combinations_and_safe_off(self) -> None:
        pairs = {(spec["sensor_backend"], spec["relay_backend"]) for spec in profile_manager.PROFILE_SPECS.values()}
        self.assertEqual(pairs, {("simulated", "simulated"), ("simulated", "libgpiod"), ("sht31", "simulated"), ("sht31", "libgpiod")})
        for spec in profile_manager.PROFILE_SPECS.values():
            self.assertEqual(spec["safe_state"], "off")
            self.assertEqual(spec["relay_bcm"], 23)
            self.assertTrue(spec["relay_active_high"])

    def test_real_sensor_profiles_pin_bus_address_and_high_repeatability(self) -> None:
        for name in ("real-sensor-simulated-actuator", "full-real"):
            spec = profile_manager.PROFILE_SPECS[name]
            self.assertEqual(spec["i2c_bus"], 1)
            self.assertEqual(spec["i2c_address"], 0x44)
            self.assertEqual(spec["sensor_repeatability"], "high")

    def test_real_sensor_profiles_support_only_governed_44_or_45_addresses(self) -> None:
        for address in (0x44, 0x45):
            spec = profile_manager.profile_spec("full-real", sensor_address=address)
            self.assertEqual(spec["i2c_address"], address)
        with self.assertRaises(profile_manager.ProfileError) as ctx:
            profile_manager.profile_spec("full-real", sensor_address=0x46)
        self.assertEqual(ctx.exception.code, "ENV_PROFILE_SENSOR_ADDRESS")

    def test_managed_real_sensor_profile_can_transition_between_44_and_45(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "config.toml"
            first = profile_manager.ensure_profile(site, name="full-real", group="ignored", sensor_address=0x44)
            second = profile_manager.ensure_profile(site, name="full-real", group="ignored", sensor_address=0x45)
            self.assertEqual(first, "CREATED")
            self.assertEqual(second, "TRANSITIONED_FROM_FULL_REAL")
            self.assertTrue(profile_manager.exact_profile(site, "full-real", sensor_address=0x45))
            self.assertEqual(profile_manager.read_environment(site)["i2c_address"], 0x45)

    def test_simulated_sensor_profile_rejects_nondefault_sensor_address_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "config.toml"
            with self.assertRaises(profile_manager.ProfileError) as ctx:
                profile_manager.ensure_profile(site, name="full-simulation", group="ignored", sensor_address=0x45)
        self.assertEqual(ctx.exception.code, "ENV_PROFILE_SENSOR_ADDRESS")

    def test_backward_compatible_sensor_deferred_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "config.toml"
            result = profile_manager.ensure_sensor_deferred(site, group="ignored")
            self.assertEqual(result, "CREATED")
            self.assertTrue(profile_manager.exact_profile(site))


if __name__ == "__main__":
    unittest.main()
