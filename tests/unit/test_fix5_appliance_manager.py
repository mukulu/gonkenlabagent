from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/appliance_manager.py"


def load_module():
    spec = importlib.util.spec_from_file_location("gonken_appliance_manager_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ApplianceManagerTests(unittest.TestCase):
    def test_ready_record_requires_content_free_runtime_contract(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ready.json"
            module.READY_FILE = path
            payload = {
                "status": "READY", "code": "VOICE_RUNTIME_READY",
                "wake_phrase": "Hey Gonken", "audio_backend": "alsa-usb",
                "model": "qwen3.5:2b-q4_K_M", "release_commit": "fixture",
                "boot_id": module.current_boot_id(), "service_pid": __import__("os").getpid(),
                "observed_epoch": 1,
            }
            path.write_text(__import__("json").dumps(payload) + "\n", encoding="utf-8")
            with mock.patch.object(module, "current_release_commit", return_value=None):
                self.assertEqual(module.read_ready()["wake_phrase"], "Hey Gonken")
            path.write_text('{"status":"READY","code":"OTHER","wake_phrase":"Hey Gonken"}\n')
            self.assertIsNone(module.read_ready())

    def test_ready_record_is_bound_to_current_immutable_release_and_boot(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ready.json"
            module.READY_FILE = path
            current = "a" * 40
            previous = "b" * 40
            base = {
                "status": "READY", "code": "VOICE_RUNTIME_READY", "wake_phrase": "GonKen",
                "boot_id": module.current_boot_id(), "service_pid": __import__("os").getpid(),
                "observed_epoch": 1,
            }
            wrong = dict(base, release_commit=previous)
            path.write_text(__import__("json").dumps(wrong) + "\n", encoding="utf-8")
            with mock.patch.object(module, "current_release_commit", return_value=current):
                self.assertIsNone(module.read_ready())
            good = dict(base, release_commit=current)
            path.write_text(__import__("json").dumps(good) + "\n", encoding="utf-8")
            with mock.patch.object(module, "current_release_commit", return_value=current):
                self.assertEqual(module.read_ready()["release_commit"], current)
            stale_boot = dict(good, boot_id="00000000-0000-0000-0000-000000000000")
            path.write_text(__import__("json").dumps(stale_boot) + "\n", encoding="utf-8")
            with mock.patch.object(module, "current_release_commit", return_value=current):
                self.assertIsNone(module.read_ready())

    def test_pending_readiness_rejects_stale_process_and_exposes_causal_code(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "readiness.json"
            module.READINESS_FILE = path
            payload = {
                "format": "gonken-voice-readiness-v1", "status": "WAITING",
                "code": "AUDIO_CAPTURE_FAILED", "component": "audio_capture",
                "recoverable": True, "release_commit": "development",
                "boot_id": module.current_boot_id(), "service_pid": __import__("os").getpid(),
                "observed_epoch": 1,
            }
            path.write_text(__import__("json").dumps(payload) + "\n", encoding="utf-8")
            with mock.patch.object(module, "current_release_commit", return_value=None):
                value = module.read_readiness()
            self.assertEqual(value["component"], "audio_capture")
            self.assertEqual(value["code"], "AUDIO_CAPTURE_FAILED")
            payload["service_pid"] = 99999999
            path.write_text(__import__("json").dumps(payload) + "\n", encoding="utf-8")
            with mock.patch.object(module, "current_release_commit", return_value=None):
                self.assertIsNone(module.read_readiness())

    def test_status_requires_enabled_active_and_runtime_ready_independently(self) -> None:
        module = load_module()
        calls = []

        def fake_systemctl(*args, **kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=0)

        with mock.patch.object(module, "systemctl", side_effect=fake_systemctl), \
             mock.patch.object(module, "read_ready", return_value={
                 "wake_phrase": "Hey Gonken", "model": "qwen", "audio_backend": "fixture"
             }):
            value = module.status()
        self.assertTrue(value["enabled"])
        self.assertTrue(value["active"])
        self.assertTrue(value["ready"])
        self.assertIn(("is-enabled", "--quiet", module.SERVICE), calls)
        self.assertIn(("is-active", "--quiet", module.SERVICE), calls)

    def test_fix7_installer_revalidates_service_and_physical_readiness_contract(self) -> None:
        install = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
        self.assertIn('"application_service" "3"', install)
        self.assertIn('"appliance_readiness" "4"', install)
        self.assertIn('"bluetooth_audio_pairing" "2"', install)
        self.assertIn('installed-status', install)
        self.assertIn('--service-uid', install)

    def test_activate_restarts_enabled_service_then_waits_for_ready(self) -> None:
        module = load_module()
        calls = []

        def fake_systemctl(*args, check=True):
            calls.append(args)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        ready = {
            "wake_phrase": "Hey Gonken",
            "model": "qwen3.5:2b-q4_K_M",
            "audio_backend": "alsa-usb",
        }
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(module.os, "geteuid", return_value=0), \
             mock.patch.object(module, "READY_FILE", Path(temporary) / "ready.json"), \
             mock.patch.object(module, "READINESS_FILE", Path(temporary) / "readiness.json"), \
             mock.patch.object(module, "systemctl", side_effect=fake_systemctl), \
             mock.patch.object(module, "read_ready", return_value=ready):
            module.activate(30)
        self.assertIn(("enable", module.SERVICE), calls)
        self.assertIn(("reset-failed", module.SERVICE), calls)
        self.assertIn(("restart", module.SERVICE), calls)


if __name__ == "__main__":
    unittest.main()
