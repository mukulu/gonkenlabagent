from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("i2c_manager", ROOT / "scripts" / "i2c_manager.py")
assert SPEC and SPEC.loader
i2c = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = i2c
SPEC.loader.exec_module(i2c)


class I2CManagerTests(unittest.TestCase):
    def test_status_requires_device_and_service_user_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            device = Path(temporary) / "i2c-1"
            device.touch()
            with patch.object(i2c, "I2C_DEVICE", device), \
                 patch.object(i2c, "groups_for", return_value={"i2c", "gpio"}), \
                 patch.object(i2c.shutil, "which", return_value="/usr/bin/raspi-config"), \
                 patch.object(i2c, "can_open_as_user", return_value=True):
                report = i2c.status("gonken-env")
        self.assertTrue(report["device_exists"])
        self.assertTrue(report["user_i2c_group"])
        self.assertTrue(report["ready_for_sensor_probe"])

    def test_status_fails_readiness_when_service_user_lacks_i2c(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            device = Path(temporary) / "i2c-1"
            device.touch()
            with patch.object(i2c, "I2C_DEVICE", device), \
                 patch.object(i2c, "groups_for", return_value={"gpio"}), \
                 patch.object(i2c.shutil, "which", return_value="/usr/bin/raspi-config"):
                report = i2c.status("gonken-env")
        self.assertFalse(report["ready_for_sensor_probe"])

    def test_status_requires_real_service_context_openability_not_group_name_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            device = Path(temporary) / "i2c-1"; device.touch()
            with patch.object(i2c, "I2C_DEVICE", device), \
                 patch.object(i2c, "groups_for", return_value={"i2c"}), \
                 patch.object(i2c, "can_open_as_user", return_value=False):
                report = i2c.status("gonken-env")
        self.assertTrue(report["user_i2c_group"])
        self.assertFalse(report["service_user_can_open"])
        self.assertFalse(report["ready_for_sensor_probe"])

    def test_enable_uses_noninteractive_raspi_config_and_reports_reboot(self) -> None:
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as temporary:
            device = Path(temporary) / "i2c-1"
            with patch.object(i2c, "I2C_DEVICE", device), \
                 patch.object(i2c.os, "geteuid", return_value=0), \
                 patch.object(i2c.shutil, "which", return_value="/usr/bin/raspi-config"), \
                 patch.object(i2c.subprocess, "run", return_value=completed) as run:
                result = i2c.enable()
        run.assert_called_once_with(
            ["/usr/bin/raspi-config", "nonint", "do_i2c", "0"],
            check=False, capture_output=True, text=True, timeout=30,
        )
        self.assertTrue(result["configured"])
        self.assertTrue(result["reboot_required"])

    def test_enable_requires_root_and_never_runs_raspi_config(self) -> None:
        with patch.object(i2c.os, "geteuid", return_value=1000), patch.object(i2c.subprocess, "run") as run:
            with self.assertRaises(i2c.I2CError) as ctx:
                i2c.enable()
        self.assertEqual(ctx.exception.code, "I2C_PRIVILEGE")
        run.assert_not_called()

    def test_require_ready_returns_75_without_mutating_system(self) -> None:
        with patch.object(i2c, "status", return_value={"device_exists": False, "user_i2c_group": True, "service_user_can_open": False, "ready_for_sensor_probe": False}):
            self.assertEqual(i2c.main(["status", "--user", "gonken-env", "--require-ready"]), 75)


if __name__ == "__main__":
    unittest.main()
