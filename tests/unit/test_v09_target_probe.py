from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("target_probe", ROOT / "scripts" / "target_probe.py")
assert SPEC and SPEC.loader
target_probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = target_probe
SPEC.loader.exec_module(target_probe)


class FakeChip:
    def __init__(self, lines, *, label="pinctrl-rp1", name="gpiochip0"):
        self.lines = list(lines)
        self.label = label
        self.name = name
        self.closed = False

    def get_info(self):
        return SimpleNamespace(num_lines=len(self.lines), label=self.label, name=self.name)

    def get_line_info(self, offset):
        return SimpleNamespace(name=self.lines[offset])

    def close(self):
        self.closed = True


class FakeGpiod:
    def __init__(self, chips):
        self.chips = chips

    def Chip(self, path):
        return FakeChip(self.chips[path])


def fake_stat_for_same_device(path):
    return SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_rdev=os.makedev(254, 0))


class TargetProbeTests(unittest.TestCase):
    def fixture(self, name: str) -> dict[str, object]:
        path = ROOT / "tests" / "fixtures" / "target_probe" / name
        return json.loads(path.read_text(encoding="utf-8"))

    def test_live_gpio_collection_records_canonical_identity_and_alias_paths(self):
        rp1 = [None] * 54
        for bcm in (2, 3, 17, 22, 23, 27):
            rp1[bcm] = f"GPIO{bcm}"
        chips = target_probe._collect_gpiochips(
            gpiod_module=FakeGpiod({"/dev/gpiochip0": rp1, "/dev/gpiochip4": list(rp1)}),
            chip_paths=("/dev/gpiochip0", "/dev/gpiochip4"),
            stat_func=fake_stat_for_same_device,
        )
        self.assertEqual(len(chips), 2)
        for chip in chips:
            self.assertTrue(str(chip["canonical_chip_id"]).startswith("char:254:0:"))
            self.assertEqual(chip["alias_paths"], ["/dev/gpiochip0", "/dev/gpiochip4"])
            self.assertEqual(chip["line_names"]["23"], "GPIO23")

    def test_checkpoint34_duplicate_rp1_alias_fixture_replays_pass(self):
        result = target_probe.replay_manifest(self.fixture("checkpoint34_duplicate_rp1_alias_manifest.json"))
        self.assertEqual(result["status"], "PASS")
        gpio = result["gpio_identity"]
        self.assertEqual(gpio["status"], "PASS")
        self.assertEqual(gpio["code"], "GPIO_HEADER_RESOLVED")
        self.assertEqual(gpio["lines"]["GPIO23"]["alias_paths"], ["/dev/gpiochip0", "/dev/gpiochip4"])
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_distinct_duplicate_header_fixture_fails_closed(self):
        result = target_probe.replay_manifest(self.fixture("distinct_duplicate_header_manifest.json"))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["gpio_identity"]["code"], "GPIO_HEADER_UNRESOLVED")

    def test_capability_ready_fixture_replays_full_target_shadow_gate(self):
        result = target_probe.replay_manifest(self.fixture("capability_ready_audio_identity_release_manifest.json"))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["code"], "TARGET_SHADOW_READY")
        self.assertEqual(result["audio_duplex"]["code"], "AUDIO_DUPLEX_ROUTE_RESOLVED")
        self.assertEqual(result["service_identity"]["code"], "SERVICE_IDENTITY_RESOLVED")
        self.assertEqual(result["release_state"]["code"], "RELEASE_STATE_SAFE")
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_ambiguous_audio_fixture_fails_closed(self):
        result = target_probe.replay_manifest(self.fixture("ambiguous_audio_route_manifest.json"))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["code"], "AUDIO_ROUTE_UNRESOLVED")
        self.assertEqual(result["audio_duplex"]["status"], "FAIL")

    def test_missing_service_identity_fixture_fails_closed(self):
        result = target_probe.replay_manifest(self.fixture("missing_service_identity_manifest.json"))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["code"], "SERVICE_IDENTITY_UNRESOLVED")
        self.assertIn("gonken-agent:gpio", result["service_identity"]["detail"])
        self.assertIn("gonken-env:i2c", result["service_identity"]["detail"])

    def test_dirty_release_state_fixture_fails_closed(self):
        result = target_probe.replay_manifest(self.fixture("dirty_release_state_manifest.json"))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["code"], "RELEASE_STATE_UNSAFE")
        self.assertIn("installer_dirty", result["release_state"]["detail"])

    def test_i2c_sht31_ready_full_real_fixture_replays_full_gate(self):
        result = target_probe.replay_manifest(self.fixture("i2c_sht31_ready_full_real_manifest.json"))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["code"], "TARGET_SHADOW_READY")
        self.assertEqual(result["i2c_sht31"]["code"], "I2C_SHT31_READY")
        self.assertEqual(result["environment_profile"]["code"], "ENVIRONMENT_PROFILE_READY")
        self.assertEqual(result["environment_profile"]["profile"], "full-real")
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_i2c_reboot_required_fixture_fails_closed(self):
        result = target_probe.replay_manifest(self.fixture("i2c_reboot_required_manifest.json"))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["code"], "I2C_REBOOT_REQUIRED")
        self.assertEqual(result["i2c_sht31"]["detail"], "reboot_then_resume_same_installer")

    def test_absent_sht31_fixture_fails_closed(self):
        result = target_probe.replay_manifest(self.fixture("sht31_absent_real_sensor_manifest.json"))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["code"], "I2C_SHT31_UNRESOLVED")
        self.assertEqual(result["i2c_sht31"]["detail"], "sensor_not_found")

    def test_full_real_environment_fixture_requires_relay_gpio23_even_when_gpio_is_not_top_level_required(self):
        result = target_probe.replay_manifest(self.fixture("environment_full_real_missing_relay_manifest.json"))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["code"], "ENVIRONMENT_PROFILE_UNREADY")
        self.assertIn("relay_gpio23", result["environment_profile"]["detail"])

    def test_full_simulation_environment_profile_does_not_require_physical_i2c_or_gpio(self):
        result = target_probe.replay_manifest(self.fixture("environment_disabled_safe_manifest.json"))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["code"], "TARGET_SHADOW_READY")
        self.assertEqual(result["environment_profile"]["profile"], "full-simulation")
        self.assertEqual(result["i2c_sht31"]["status"], "FAIL")
        self.assertFalse(result["requirements"]["i2c_sht31"])

    def test_manifest_capture_is_content_free_and_non_actuating(self):
        rp1 = [None] * 54
        for bcm in (2, 3, 17, 22, 23, 27):
            rp1[bcm] = f"GPIO{bcm}"
        with mock.patch.object(target_probe, "_git_commit", return_value="a" * 40), \
             mock.patch.object(target_probe, "_pi_model", return_value={"model": "fixture", "revision": "", "kernel": "test", "os_release": {}}), \
             mock.patch.object(target_probe, "_python_info", return_value={"version": "3.13", "executable": "/usr/bin/python3", "libgpiod": "available"}), \
             mock.patch.object(target_probe, "_audio_inventory", return_value={"capture_routes": [], "playback_routes": [], "selected_route": None}), \
             mock.patch.object(target_probe, "_bluetooth_inventory", return_value={"controller": "", "devices": []}), \
             mock.patch.object(target_probe, "_unit_state", return_value={"active": "unknown"}), \
             mock.patch.object(target_probe, "_systemd_version", return_value="systemd 999"), \
             mock.patch.object(target_probe, "_identity", return_value={"service_users": {}, "operator_groups": []}), \
             mock.patch.object(target_probe, "_release_state", return_value={"current": "", "installer_state": {}}):
            manifest = target_probe.collect_manifest(
                gpiod_module=FakeGpiod({"/dev/gpiochip0": rp1}),
                chip_paths=("/dev/gpiochip0",),
                stat_func=fake_stat_for_same_device,
            )
        self.assertEqual(manifest["format"], target_probe.FORMAT)
        self.assertFalse(manifest["physical_acceptance_claimed"])
        self.assertEqual(manifest["privacy"]["raw_audio_included"], False)
        self.assertEqual(manifest["privacy"]["transcripts_included"], False)
        self.assertEqual(manifest["i2c"]["sht31_targeted_probe"]["status"], "not_probed_non_actuating_manifest")

    def test_atomic_output_is_private_and_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "target-manifest.json"
            target_probe.atomic_json(path, {"format": target_probe.FORMAT, "status": "PASS"})
            first = json.loads(path.read_text(encoding="utf-8"))
            mode = path.stat().st_mode & 0o777
            target_probe.atomic_json(path, {"format": target_probe.FORMAT, "status": "FAIL"})
            second = json.loads(path.read_text(encoding="utf-8"))
            leftovers = list(path.parent.glob(f".{path.name}.*"))
        self.assertEqual(first["status"], "PASS")
        self.assertEqual(second["status"], "FAIL")
        self.assertEqual(mode, 0o600)
        self.assertEqual(leftovers, [])

    def test_cli_replay_exit_codes(self):
        good = ROOT / "tests" / "fixtures" / "target_probe" / "checkpoint34_duplicate_rp1_alias_manifest.json"
        bad = ROOT / "tests" / "fixtures" / "target_probe" / "distinct_duplicate_header_manifest.json"
        ok = subprocess.run([sys.executable, str(ROOT / "scripts" / "target_probe.py"), "--replay", str(good), "--json"], text=True, capture_output=True, check=False)
        failed = subprocess.run([sys.executable, str(ROOT / "scripts" / "target_probe.py"), "--replay", str(bad), "--json"], text=True, capture_output=True, check=False)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["status"], "PASS")
        self.assertEqual(failed.returncode, 75)
        self.assertEqual(json.loads(failed.stdout)["status"], "FAIL")

    def test_cli_replay_exit_codes_for_capability_fixtures(self):
        good = ROOT / "tests" / "fixtures" / "target_probe" / "capability_ready_audio_identity_release_manifest.json"
        bad = ROOT / "tests" / "fixtures" / "target_probe" / "ambiguous_audio_route_manifest.json"
        ok = subprocess.run([sys.executable, str(ROOT / "scripts" / "target_probe.py"), "--replay", str(good), "--json"], text=True, capture_output=True, check=False)
        failed = subprocess.run([sys.executable, str(ROOT / "scripts" / "target_probe.py"), "--replay", str(bad), "--json"], text=True, capture_output=True, check=False)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["code"], "TARGET_SHADOW_READY")
        self.assertEqual(failed.returncode, 75)
        self.assertEqual(json.loads(failed.stdout)["code"], "AUDIO_ROUTE_UNRESOLVED")

    def test_cli_replay_exit_codes_for_i2c_environment_fixtures(self):
        good = ROOT / "tests" / "fixtures" / "target_probe" / "i2c_sht31_ready_full_real_manifest.json"
        bad = ROOT / "tests" / "fixtures" / "target_probe" / "i2c_reboot_required_manifest.json"
        ok = subprocess.run([sys.executable, str(ROOT / "scripts" / "target_probe.py"), "--replay", str(good), "--json"], text=True, capture_output=True, check=False)
        failed = subprocess.run([sys.executable, str(ROOT / "scripts" / "target_probe.py"), "--replay", str(bad), "--json"], text=True, capture_output=True, check=False)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["environment_profile"]["code"], "ENVIRONMENT_PROFILE_READY")
        self.assertEqual(failed.returncode, 75)
        self.assertEqual(json.loads(failed.stdout)["code"], "I2C_REBOOT_REQUIRED")


if __name__ == "__main__":
    unittest.main()
