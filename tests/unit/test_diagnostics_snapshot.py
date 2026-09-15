import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gonken_agent.config import load_config
from gonken_agent import diagnostics
from gonken_agent.diagnostics import collect_snapshot, load_snapshot, write_startup_snapshot


class StartupSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = load_config(
            site_path=None,
            environ={},
            cli_overrides={
                "paths.state_dir": str(self.root / "state"),
                "paths.cache_dir": str(self.root / "cache"),
                "paths.runtime_dir": str(self.root / "run"),
                "paths.corpus_dir": str(self.root / "corpus"),
            },
        ).config

    def test_snapshot_is_content_free_and_bounded(self):
        snapshot = collect_snapshot(self.config)
        raw = json.dumps(snapshot, sort_keys=True)
        self.assertFalse(snapshot["privacy"]["content_logging"])
        self.assertFalse(snapshot["network"]["external_probe"])
        self.assertIn("audio", snapshot)
        self.assertIn("gpio", snapshot)
        self.assertIn("environment", snapshot)
        self.assertFalse(snapshot["environment"]["physical_evidence"])
        self.assertFalse(snapshot["environment"]["capabilities"]["software_speed_control"])
        self.assertEqual(snapshot["environment"]["target_acceptance"], "not_established_by_diagnostics")
        self.assertNotIn(str(self.root), raw)

    def test_write_latest_and_retained_history_then_prunes(self):
        snapshot_dir = self.root / "state" / "runtime" / "startup"
        with patch("gonken_agent.diagnostics.datetime") as clock:
            clock.now.side_effect = [
                __import__("datetime").datetime(2026, 9, 11, 0, 0, i, tzinfo=__import__("datetime").timezone.utc)
                for i in range(3)
            ]
            result1 = write_startup_snapshot(self.config, directory=snapshot_dir, retain=2)
            result2 = write_startup_snapshot(self.config, directory=snapshot_dir, retain=2)
            result3 = write_startup_snapshot(self.config, directory=snapshot_dir, retain=2)
        self.assertEqual(result1["status"], "RECORDED")
        self.assertEqual(result3["retention"], 2)
        self.assertTrue((snapshot_dir / "latest.json").is_file())
        self.assertEqual(len(list(snapshot_dir.glob("startup-*.json"))), 2)
        self.assertEqual((snapshot_dir / "latest.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(load_snapshot(result2["retained"])["schema"], 1)

    def test_production_default_keeps_only_latest(self):
        snapshot_dir = self.root / "state" / "runtime" / "startup"
        result = write_startup_snapshot(self.config, directory=snapshot_dir, mode="production")
        self.assertEqual(result["retention"], 0)
        self.assertEqual(list(snapshot_dir.glob("startup-*.json")), [])
        self.assertTrue((snapshot_dir / "latest.json").is_file())

    def test_debug_audio_snapshot_includes_bounded_pipewire_route_metadata(self):
        completed = {"available": True, "exit_code": 0, "stdout": ["fixture"], "stderr": []}
        with patch("gonken_agent.diagnostics.shutil.which", return_value="/usr/bin/fixture"), \
             patch("gonken_agent.diagnostics._run", return_value=completed), \
             patch("gonken_agent.diagnostics._bounded_lines", return_value=[]), \
             patch("gonken_agent.diagnostics._bluetooth_audio_state", return_value={"configured": True}):
            audio = diagnostics._audio("debug")
        for key in (
            "capture_pcms", "playback_pcms", "pipewire_pulse_info",
            "pipewire_default_source", "pipewire_default_sink",
            "pipewire_sources", "pipewire_sinks", "wireplumber_status",
        ):
            self.assertIn(key, audio)


    def test_environment_diagnostics_are_non_destructive_and_read_only(self):
        class FakeClient:
            def __init__(self, socket_path):
                self.socket_path = socket_path
            def health(self):
                return {
                    "overall": "READY",
                    "sensor": "ready",
                    "actuator": "HOST_FAKE",
                    "controller": "ACTIVE",
                    "physical_evidence": False,
                }
            def simulation_status(self):
                return {
                    "simulation": {
                        "active": True,
                        "runtime_control_enabled": True,
                        "sensor_is_simulated": True,
                        "actuator_is_simulated": True,
                        "evidence_mode": "HOST_SIMULATION",
                        "simulation_generation": 7,
                        "sensor": {"fault": None},
                        "actuator": {"behavior": "normal", "modeled_power": "off"},
                    },
                    "physical_evidence": False,
                }
            def snapshot(self):
                return {
                    "environment": "READY",
                    "state": {
                        "mode": "automatic",
                        "fan_power": "off",
                        "sensor_quality": "ready",
                        "last_transition_reason": "BOOT_SAFE_OFF",
                    },
                    "polling": {"poll_count": 3},
                    "provenance": {"sensor_backend": "simulated", "actuator_backend": "simulated"},
                    "physical_evidence": False,
                }
        socket_path = self.root / "run" / "env.sock"
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        socket_path.touch()
        config = load_config(
            site_path=None,
            environ={},
            cli_overrides={"extensions.environment.socket_path": str(socket_path)},
        ).config
        with patch("gonken_agent.diagnostics.Path.is_socket", return_value=True):
            diag = diagnostics.collect_environment_diagnostics(
                config,
                mode="production",
                client_factory=lambda path: FakeClient(path),
            )
        self.assertFalse(diag["physical_evidence"])
        self.assertFalse(diag["capabilities"]["software_speed_control"])
        self.assertEqual(diag["static"]["i2c_address_hex"], "0x44")
        self.assertEqual(diag["ipc"]["status"], "READY")
        self.assertEqual(diag["ipc"]["overall"], "READY")
        self.assertTrue(diag["ipc"]["simulation"]["active"])
        self.assertEqual(diag["ipc"]["simulation"]["evidence_mode"], "HOST_SIMULATION")
        self.assertEqual(diag["ipc"]["snapshot"]["mode"], "automatic")
        self.assertFalse(diag["ipc"]["snapshot"]["physical_evidence"])
        self.assertNotIn(str(self.root), json.dumps(diag, sort_keys=True))


    def test_systemctl_preserves_legitimate_nonzero_inactive_and_disabled_states(self):
        inactive = {"available": True, "exit_code": 3, "stdout": ["inactive"], "stderr": []}
        disabled = {"available": True, "exit_code": 1, "stdout": ["disabled"], "stderr": []}
        with patch("gonken_agent.diagnostics._run", side_effect=[inactive, disabled]):
            self.assertEqual(diagnostics._systemctl("is-active", "fixture.service"), "inactive")
            self.assertEqual(diagnostics._systemctl("is-enabled", "fixture.service"), "disabled")

    def test_unsafe_snapshot_input_rejected(self):
        bad = self.root / "bad.json"
        bad.write_text('{"schema":1,"privacy":{"content_logging":true}}\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_snapshot(bad)


if __name__ == "__main__":
    unittest.main()
