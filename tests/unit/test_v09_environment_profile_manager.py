from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "environment_profile_manager", ROOT / "scripts" / "environment_profile_manager.py"
)
assert SPEC and SPEC.loader
profile_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile_manager)


class EnvironmentProfileManagerTests(unittest.TestCase):
    def test_create_is_atomic_exact_and_idempotent_for_test_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "config.toml"
            first = profile_manager.ensure_sensor_deferred(site, group="ignored-in-test-path")
            second = profile_manager.ensure_sensor_deferred(site, group="ignored-in-test-path")
            self.assertEqual(first, "CREATED")
            self.assertEqual(second, "ALREADY_CONFIGURED")
            self.assertEqual(site.read_text(encoding="utf-8"), profile_manager.PROFILE_TEXT)
            self.assertEqual(site.stat().st_mode & 0o777, 0o640)
            self.assertTrue(profile_manager.exact_profile(site))
            self.assertEqual(list(site.parent.glob(f".{site.name}.*")), [])

    def test_existing_different_admin_configuration_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "config.toml"
            original = '[extensions.environment]\nenabled = false\n'
            site.write_text(original, encoding="utf-8")
            with self.assertRaises(profile_manager.ProfileError) as raised:
                profile_manager.ensure_sensor_deferred(site, group="ignored")
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
                profile_manager.ensure_sensor_deferred(site, group="ignored")
            self.assertIn(raised.exception.code, {"ENV_PROFILE_UNSAFE", "ENV_PROFILE_CONFLICT"})

    def test_profile_is_sensor_simulated_real_relay_and_non_actuating(self) -> None:
        self.assertIn('sensor_backend = "simulated"', profile_manager.PROFILE_TEXT)
        self.assertIn('relay_backend = "libgpiod"', profile_manager.PROFILE_TEXT)
        self.assertIn('relay_bcm = 23', profile_manager.PROFILE_TEXT)
        self.assertIn('safe_state = "off"', profile_manager.PROFILE_TEXT)
        self.assertNotIn("systemctl", profile_manager.PROFILE_TEXT)


if __name__ == "__main__":
    unittest.main()
