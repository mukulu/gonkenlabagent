import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from gonken_agent.config import load_config
from gonken_agent.operations import doctor
from gonken_agent.support import create_bundle
from gonken_agent.telemetry import Telemetry


class SupportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config=load_config(site_path=None,environ={},cli_overrides={'paths.corpus_dir':'/srv/private-person/corpus'})
        self.health=doctor(self.config.config)
    def test_bundle_exact_members_redacted_paths_no_raw_files(self):
        (self.root/'.env').write_text('SECRET=private-token')
        output=self.root/'support.zip'
        telemetry=self.root/'telemetry.jsonl';Telemetry(telemetry).append({'status':'DEGRADED'})
        create_bundle(output,self.config,self.health,telemetry)
        with zipfile.ZipFile(output) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(set(z.namelist()),{'environment.json','configuration.json','health.json','telemetry.json'})
            raw=b''.join(z.read(name) for name in z.namelist())
        self.assertNotIn(b'private-person',raw);self.assertNotIn(b'private-token',raw)
        self.assertNotIn(str(self.root).encode(),raw)
        self.assertEqual(output.stat().st_mode&0o777,0o600)
    def test_content_in_telemetry_rejected_before_output(self):
        telemetry=self.root/'telemetry.jsonl';telemetry.write_text('{"transcript":"secret"}\n')
        output=self.root/'support.zip'
        with self.assertRaises(ValueError):create_bundle(output,self.config,self.health,telemetry)
        self.assertFalse(output.exists());self.assertFalse(list(self.root.glob('.support-*')))
    def test_existing_symlink_and_publish_race_preserve_destination(self):
        output=self.root/'support.zip';output.write_bytes(b'old')
        with self.assertRaises(ValueError):create_bundle(output,self.config,self.health)
        self.assertEqual(output.read_bytes(),b'old')
        output.unlink();output.symlink_to(self.root/'elsewhere')
        with self.assertRaises(ValueError):create_bundle(output,self.config,self.health)
        output.unlink()
        with patch('gonken_agent.support.os.link',side_effect=FileExistsError):
            with self.assertRaises(FileExistsError):create_bundle(output,self.config,self.health)
        self.assertFalse(list(self.root.glob('.support-*')))
    def test_extra_health_details_are_not_exported(self):
        output=self.root/'support.zip';self.health['components'][0]['detail']='secret transcript'
        create_bundle(output,self.config,self.health)
        with zipfile.ZipFile(output) as z:self.assertNotIn(b'secret',z.read('health.json'))
    def test_startup_snapshot_is_allow_listed_member(self):
        from gonken_agent.diagnostics import write_startup_snapshot
        snapshot_dir=self.root/'snapshots'
        snapshot=write_startup_snapshot(self.config.config,directory=snapshot_dir,retain=1)
        output=self.root/'support.zip'
        create_bundle(output,self.config,self.health,startup_snapshot=snapshot['latest'])
        with zipfile.ZipFile(output) as z:
            self.assertIn('startup_snapshot.json',z.namelist())
            payload=json.loads(z.read('startup_snapshot.json'))
            self.assertEqual(payload['schema'],1)
            self.assertFalse(payload['privacy']['content_logging'])
