from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from gonken_agent import runtime_readiness as rr
from gonken_agent.component_status import collect
from gonken_agent.config import load_config
from gonken_agent.llm import admin
from gonken_agent.llm.qualification import RECORD_FORMAT

ROOT = Path(__file__).resolve().parents[2]


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ready = self.root / 'ready.json'
        self.pending = self.root / 'readiness.json'
        self.binding = rr.Binding('a' * 40, 'fixture-profile', rr.current_boot_id())
        self.value = {
            'status': 'READY', 'code': 'VOICE_RUNTIME_READY', 'wake_phrase': 'GonKen',
            'audio_backend': 'alsa-usb', 'model': 'qwen3:0.6b', 'model_digest': 'b' * 64,
            'release_commit': self.binding.commit, 'release_profile': self.binding.profile,
            'boot_id': self.binding.boot_id, 'service_pid': os.getpid(),
            'service_start_ticks': rr.process_start_ticks(os.getpid()),
            'observed_epoch': int(time.time()),
        }
        self.ready.write_text(json.dumps(self.value))

    def read(self):
        return rr.read_ready(self.ready, binding=self.binding, pending_path=self.pending)

    def test_live_bound_record_passes(self):
        self.assertEqual(self.read(), self.value)

    def test_unknown_release_never_grants_ready(self):
        self.assertIsNone(rr.read_ready(self.ready, binding=rr.Binding(None, None, self.binding.boot_id)))

    def test_missing_file(self):
        self.ready.unlink()
        self.assertIsNone(self.read())

    def test_identity_and_type_mutations_rejected(self):
        cases = {
            'release_commit': 'c' * 40, 'release_profile': 'old-profile',
            'boot_id': '00000000-0000-0000-0000-000000000000',
            'service_pid': 99999999, 'service_start_ticks': self.value['service_start_ticks'] + 1,
            'observed_epoch': int(time.time()) + 600, 'status': 'active', 'code': 'OTHER_CODE',
            'wake_phrase': '\x1b[bad',
        }
        for key, item in cases.items():
            with self.subTest(key=key):
                self.ready.write_text(json.dumps(dict(self.value, **{key: item})))
                self.assertIsNone(self.read())
        for key in ('service_pid', 'service_start_ticks', 'observed_epoch'):
            with self.subTest(boolean=key):
                self.ready.write_text(json.dumps(dict(self.value, **{key: True})))
                self.assertIsNone(self.read())

    def test_stopped_producer_rejected(self):
        self.assertIsNone(rr.validate_record(self.value, self.binding, start_ticks=lambda _pid: None))

    def test_missing_boot_identity_rejected(self):
        self.assertIsNone(rr.validate_record(self.value, self.binding._replace(boot_id=None)))

    def test_long_running_ready_not_expired_by_arbitrary_ttl(self):
        self.ready.write_text(json.dumps(dict(self.value, observed_epoch=1)))
        self.assertIsNotNone(self.read())

    def test_new_waiting_state_overrides_ready(self):
        value = dict(self.value, format='gonken-voice-readiness-v1', status='WAITING',
                     code='AUDIO_CAPTURE_FAILED', component='audio_capture', recoverable=True)
        self.pending.write_text(json.dumps(value))
        self.assertIsNone(self.read())
        self.assertEqual(rr.read_pending(self.pending, binding=self.binding)['component'], 'audio_capture')

    def test_old_or_different_process_waiting_does_not_override(self):
        value = dict(self.value, format='gonken-voice-readiness-v1', status='WAITING',
                     code='AUDIO_CAPTURE_FAILED', component='audio_capture', recoverable=True,
                     service_start_ticks=1)
        self.pending.write_text(json.dumps(value))
        self.assertIsNotNone(self.read())

    def test_private_extra_fields_are_not_exported(self):
        self.ready.write_text(json.dumps(dict(self.value, transcript='PRIVATE_CANARY', debug='PRIVATE_CANARY')))
        self.assertNotIn('PRIVATE_CANARY', json.dumps(self.read()))

    def test_symlink_refused(self):
        target = self.root / 'target'; self.ready.rename(target); self.ready.symlink_to(target)
        self.assertIsNone(self.read())

    def test_fifo_refused_without_blocking(self):
        self.ready.unlink(); os.mkfifo(self.ready)
        self.assertIsNone(self.read())

    def test_oversize_invalid_utf8_nonfinite_and_duplicate_refused(self):
        for raw in (b'x'*8193, b'\xff', b'{"status":"READY","status":"WAITING"}', b'{"v":NaN}'):
            with self.subTest(raw=raw[:40]):
                self.ready.write_bytes(raw)
                self.assertIsNone(self.read())

    def test_current_binding_requires_valid_current_record(self):
        current = self.root / 'current'
        release = self.root / 'releases' / ('a' * 40)
        release.mkdir(parents=True)
        current.symlink_to('releases/' + 'a'*40)
        record = release / 'release.record'
        record.write_text('format=gonken-release-v1\ncommit=' + 'a'*40 + '\nprofile=fixture-profile\nvalidation=passed\n')
        self.assertEqual(rr.current_release_identity(current), ('a'*40, 'fixture-profile'))
        record.write_text(record.read_text() + 'profile=other\n')
        self.assertEqual(rr.current_release_identity(current), (None, None))

    def test_model_switch_rejects_stale_ready(self):
        with mock.patch.object(rr, 'current_binding', return_value=self.binding):
            self.assertTrue(admin._ready_model(self.ready, 'qwen3:0.6b'))
            self.ready.write_text(json.dumps(dict(self.value, service_start_ticks=1)))
            self.assertFalse(admin._ready_model(self.ready, 'qwen3:0.6b'))

    def test_standalone_maintenance_import_has_no_package_dependency(self):
        for src in ('scripts/appliance_manager.py', 'src/gonken_agent/runtime_readiness.py'):
            shutil.copy2(ROOT / src, self.root / Path(src).name)
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        result = subprocess.run([sys.executable, '-E', '-s', str(self.root/'appliance_manager.py'), '--help'],
                                env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_support_phase_filters_untrusted_record_contents(self):
        from gonken_agent import support
        self.ready.write_text(json.dumps(dict(self.value, transcript='SUPPORT_PRIVATE_CANARY')))
        with mock.patch.object(rr, 'current_binding', return_value=self.binding), \
             mock.patch.object(rr, 'READY_FILE', self.ready), \
             mock.patch.object(rr, 'READINESS_FILE', self.pending):
            phase = support._evidence_phase_context()
        self.assertEqual(phase['voice_ready']['status'], 'READY')
        self.assertNotIn('SUPPORT_PRIVATE_CANARY', json.dumps(phase))


class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(site_path=None).config
        self.ready = {'status': 'READY', 'code': 'VOICE_RUNTIME_READY', 'model': self.config.llm.model,
                      'wake_phrase': 'GonKen', 'model_digest': 'a'*64}
        self.env = {'enabled': True, 'static': {'sensor_backend':'sht31','relay_backend':'simulated'},
                    'ipc': {'status':'READY','overall':'READY','sensor':'ready','actuator':'READY',
                            'snapshot': {'fan_power':'off'},
                            'simulation': {'actuator_is_simulated':True,'sensor_is_simulated':False}}}

    def collect(self, ready=None, roster=None, env=None):
        with mock.patch('gonken_agent.component_status.read_ready', return_value=ready), \
             mock.patch('gonken_agent.component_status.bounded_json', return_value=roster), \
             mock.patch('gonken_agent.component_status.collect_environment_diagnostics', return_value=env or self.env):
            return collect(self.config)['components']

    def test_stale_voice_does_not_hide_healthy_environment(self):
        c = self.collect()
        self.assertEqual(c['voice_conversation']['status'], 'DEGRADED')
        self.assertEqual(c['temperature_humidity_sensor']['status'], 'READY')
        self.assertFalse(c['room_fan_control']['physical_motion_observed'])
        self.assertTrue(c['room_fan_control']['simulated'])

    def test_broker_implementation_not_model_tool_qualification(self):
        c = self.collect(ready=self.ready)
        self.assertEqual(c['voice_conversation']['status'], 'READY')
        self.assertEqual(c['llm_environment_tool_broker']['status'], 'DEGRADED')
        self.assertTrue(c['llm_environment_tool_broker']['implementation_available'])

    def test_qualified_bound_model_tools_ready(self):
        roster = {'format': RECORD_FORMAT, 'status': 'READY', 'context_tokens':self.config.llm.context_tokens,
                  'models':[{'tag':self.config.llm.model, 'digest':'a'*64, 'inference_status':'PASS',
                             'tool_call_smoke':'PASS', 'stages':[{'stage':s, 'status':'PASS'} for s in
                                                             ('IDENTITY','INFERENCE','TOOLS','UNLOAD')]}]}
        self.assertEqual(self.collect(ready=self.ready, roster=roster)['llm_environment_tool_broker']['status'], 'READY')
        roster['models'][0]['digest'] = 'b'*64
        self.assertEqual(self.collect(ready=self.ready, roster=roster)['llm_environment_tool_broker']['status'], 'DEGRADED')

    def test_disabled_environment_is_not_ready_or_fault(self):
        c = self.collect(ready=self.ready, env={'enabled':False})
        for name in ('environment_controller','temperature_humidity_sensor','room_fan_control'):
            self.assertEqual(c[name]['status'], 'DISABLED')

    def test_wrong_selected_model_not_ready(self):
        self.ready['model'] = 'other:1'
        c = self.collect(ready=self.ready)
        self.assertEqual(c['voice_conversation']['status'], 'DEGRADED')
        self.assertEqual(c['llm_environment_tool_broker']['status'], 'DEGRADED')


if __name__ == '__main__':
    unittest.main()
