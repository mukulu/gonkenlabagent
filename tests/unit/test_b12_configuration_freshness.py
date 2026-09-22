from __future__ import annotations
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from gonken_agent.config import load_config
from gonken_agent import runtime_readiness as rr
from gonken_agent.power_diagnostics import collect

class ConfigurationFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.cfg=load_config(site_path=None,environ={}).config
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'ready.json'
        self.binding=rr.Binding('a'*40,'pi',rr.current_boot_id())
        self.row={'status':'READY','code':'VOICE_RUNTIME_READY','wake_phrase':'GonKen',
            'release_commit':'a'*40,'release_profile':'pi','boot_id':self.binding.boot_id,
            'service_pid':os.getpid(),'service_start_ticks':rr.process_start_ticks(os.getpid()),
            'observed_epoch':int(time.time()),'configuration_sha256':rr.configuration_digest(self.cfg)}
        self.path.write_text(json.dumps(self.row))
    def read(self,config):return rr.read_ready(self.path,binding=self.binding,pending_path=self.root/'missing',config=config)
    def test_actual_same_configuration_accepted(self):self.assertIsNotNone(self.read(self.cfg))
    def test_same_process_release_but_changed_power_refused(self):
        cfg=replace(self.cfg,extensions=replace(self.cfg.extensions,voice_power=replace(self.cfg.extensions.voice_power,enabled=True)))
        self.assertIsNone(self.read(cfg))
    def test_changed_audio_endpoint_refused(self):
        self.assertIsNone(self.read(replace(self.cfg,audio=replace(self.cfg.audio,speech_end_silence_ms=1200))))
    def test_old_record_without_digest_not_full_config_evidence(self):
        self.row.pop('configuration_sha256');self.path.write_text(json.dumps(self.row));self.assertIsNone(self.read(self.cfg))
    def test_fingerprint_deterministic_and_not_private_text(self):
        h=rr.configuration_digest(self.cfg);self.assertRegex(h,r'^[0-9a-f]{64}$');self.assertEqual(h,rr.configuration_digest(self.cfg))
    def test_power_support_allowlist_excludes_canary(self):
        p=self.root/'var/lib/gonken-agent/runtime/power/last-action.json';p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'format':'gonken-power-action-v1','status':'REQUESTED','action':'REBOOT_DEVICE','action_id':'c'*32,'prompt':'SECRET_CANARY','code':'SECRET_CANARY private text'}))
        result=collect(self.cfg,root=self.root);self.assertNotIn('SECRET_CANARY',json.dumps(result));self.assertFalse(result['physical_acceptance_claimed'])
    def test_invalid_power_support_file_not_green(self):
        p=self.root/'var/lib/gonken-agent/runtime/power/last-action.json';p.parent.mkdir(parents=True);p.write_text('{"format":"junk","status":"READY"}')
        self.assertEqual(collect(self.cfg,root=self.root)['record_status'],'INVALID')

if __name__=='__main__':unittest.main()
