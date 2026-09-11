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

    def test_unsafe_snapshot_input_rejected(self):
        bad = self.root / "bad.json"
        bad.write_text('{"schema":1,"privacy":{"content_logging":true}}\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_snapshot(bad)


if __name__ == "__main__":
    unittest.main()
