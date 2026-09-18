from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gonken_agent.config import load_config
from gonken_agent.operations import doctor


class DoctorContextTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(site_path=None).config

    def test_direct_audio_probe_failure_does_not_overwrite_ready_service_truth(self):
        with tempfile.TemporaryDirectory() as temporary:
            ready = Path(temporary) / "ready.json"
            ready.write_text("{}")
            with mock.patch("gonken_agent.operations.Path") as path_cls, \
                 mock.patch("gonken_agent.voice_runtime.AudioBackend.probe", side_effect=OSError("unavailable")), \
                 mock.patch("gonken_agent.operations.environment_health", return_value={
                     "component_status": __import__("gonken_agent.health", fromlist=["Readiness"]).Readiness.READY,
                     "component_code": "ENVIRONMENT_READY", "enabled": True, "status": "READY",
                 }):
                real_path = Path
                def path_side(value):
                    if str(value) == "/run/gonken-agent/ready.json":
                        return ready
                    return real_path(value)
                path_cls.side_effect = path_side
                payload = doctor(self.config, probe_audio=True)
        by_name = {row["component"]: row for row in payload["components"]}
        self.assertEqual(payload["voice_runtime"], "ready")
        self.assertEqual(by_name["input_audio"]["code"], "DIRECT_AUDIO_PROBE_UNAVAILABLE_SERVICE_READY")
        self.assertEqual(payload["audio_probe_context"], "operator_process")
        self.assertEqual(payload["audio_probe_interpretation"], "direct_probe_does_not_override_service_semantic_readiness")


if __name__ == "__main__":
    unittest.main()
