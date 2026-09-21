from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from gonken_agent.config import load_config
from gonken_agent.health import Readiness
from gonken_agent.operations import doctor
from gonken_agent import runtime_readiness as rr


class DoctorContextTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(site_path=None).config

    def probe(self, valid: bool):
        with tempfile.TemporaryDirectory() as temporary:
            ready = Path(temporary) / 'ready.json'
            binding = rr.Binding('a'*40, 'fixture-profile', rr.current_boot_id())
            payload = {'status':'READY', 'code':'VOICE_RUNTIME_READY', 'wake_phrase':'GonKen',
                       'release_commit':binding.commit, 'release_profile':binding.profile,
                       'boot_id':binding.boot_id, 'service_pid':os.getpid(),
                       'service_start_ticks':rr.process_start_ticks(os.getpid()),
                       'observed_epoch':int(time.time())}
            ready.write_text(json.dumps(payload if valid else {}))
            with mock.patch('gonken_agent.operations.read_ready', side_effect=lambda _path: rr.read_ready(
                    ready, binding=binding, pending_path=Path(temporary)/'pending.json')), \
                 mock.patch('gonken_agent.voice_runtime.AudioBackend.probe', side_effect=OSError('unavailable')), \
                 mock.patch('gonken_agent.operations.environment_health', return_value={
                     'component_status': Readiness.READY,
                     'component_code':'ENVIRONMENT_READY', 'enabled':True, 'status':'READY'}):
                return doctor(self.config, probe_audio=True)

    def test_direct_audio_probe_failure_does_not_overwrite_ready_service_truth(self):
        payload = self.probe(True)
        by_name = {row['component']: row for row in payload['components']}
        self.assertEqual(payload['voice_runtime'], 'ready')
        self.assertEqual(by_name['input_audio']['code'], 'DIRECT_AUDIO_PROBE_UNAVAILABLE_SERVICE_READY')
        self.assertEqual(payload['audio_probe_context'], 'operator_process')
        self.assertEqual(payload['audio_probe_interpretation'], 'direct_probe_does_not_override_service_semantic_readiness')

    def test_existing_but_empty_ready_file_does_not_prove_service_truth(self):
        payload = self.probe(False)
        by_name = {row['component']: row for row in payload['components']}
        self.assertEqual(payload['voice_runtime'], 'waiting_or_stopped')
        self.assertEqual(by_name['input_audio']['code'], 'PHYSICAL_AUDIO_UNAVAILABLE')
        self.assertEqual(payload['audio_probe_interpretation'], 'standalone_probe')

if __name__ == '__main__': unittest.main()
