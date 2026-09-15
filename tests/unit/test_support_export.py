import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
from gonken_agent.config import load_config
from gonken_agent.operations import doctor
from gonken_agent import support
from gonken_agent.support import create_bundle
from gonken_agent.telemetry import Telemetry


class SupportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config=load_config(site_path=None,environ={},cli_overrides={'paths.corpus_dir':'/srv/private-person/corpus'})
        self.health=doctor(self.config.config)
        self.assertIn('environment', self.health)
        self.assertIn('environment', {row['component'] for row in self.health['components']})
    def test_bundle_exact_members_redacted_paths_no_raw_files(self):
        (self.root/'.env').write_text('SECRET=private-token')
        output=self.root/'support.zip'
        telemetry=self.root/'telemetry.jsonl';Telemetry(telemetry).append({'status':'DEGRADED'})
        create_bundle(output,self.config,self.health,telemetry)
        with zipfile.ZipFile(output) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(set(z.namelist()),{'environment.json','configuration.json','health.json','telemetry.json','environment_control.json','environment_health.json','runtime_bindings.json','install_events.json','service_events.json'})
            raw=b''.join(z.read(name) for name in z.namelist())
        self.assertNotIn(b'private-person',raw);self.assertNotIn(b'private-token',raw)
        self.assertNotIn(str(self.root).encode(),raw)
        self.assertEqual(output.stat().st_mode&0o777,0o600)

    def test_bundle_preserves_allow_listed_health_reason_codes(self):
        output=self.root/'support-codes.zip'
        create_bundle(output,self.config,self.health)
        with zipfile.ZipFile(output) as z:
            payload=json.loads(z.read('health.json'))
        rows={row['component']:row for row in payload['components']}
        self.assertEqual(rows['environment']['code'], self.health['environment']['code'])
        self.assertRegex(rows['environment']['code'], r'^[A-Z0-9_]+$')

    def test_runtime_binding_member_reports_release_interpreter_probe_without_raw_output(self):
        output=self.root/'support-runtime.zip'
        create_bundle(output,self.config,self.health)
        with zipfile.ZipFile(output) as z:
            payload=json.loads(z.read('runtime_bindings.json'))
        self.assertIn('release', payload)
        self.assertIn('venv', payload)
        self.assertIn('bindings', payload)
        self.assertEqual(set(payload['bindings']), {'gpiod','smbus'})
        self.assertNotIn('stderr', json.dumps(payload))
        self.assertNotIn('stdout', json.dumps(payload))


    def test_install_event_export_is_bounded_allow_listed_and_content_free(self):
        events_dir = self.root / 'events'
        events_dir.mkdir()
        (events_dir / '001.event').write_text(
            'format=gonken-install-event-v1\n'
            'run_id=1.2\nsequence=1\nobserved_epoch=1\n'
            'level=error\ncode=INSTALL_ACTION\nstep_id=appliance_readiness\n'
            'message=action_failed_exit_75\n',
            encoding='utf-8',
        )
        (events_dir / '002.event').write_text(
            'format=gonken-install-event-v1\n'
            'run_id=1.2\nsequence=2\nobserved_epoch=2\n'
            'level=error\ncode=BAD CODE\nstep_id=none\nmessage=secret words\n',
            encoding='utf-8',
        )
        with patch('gonken_agent.support.INSTALL_EVENTS_DIR', events_dir):
            payload = support._install_events()
        self.assertEqual(payload['status'], 'READY')
        self.assertEqual(payload['events'], [{
            'level': 'error',
            'code': 'INSTALL_ACTION',
            'step_id': 'appliance_readiness',
            'message': 'action_failed_exit_75',
        }])

    def test_service_event_export_counts_codes_without_exporting_journal_text(self):
        fake = Mock(returncode=0, stdout=(
            '[WAITING] code=WAKE_LED_GPIO_DEPENDENCY_MISSING detail=secret transcript\n'
            '[ERROR] code=INSTALL_ACTION message=private words\n'
            'ordinary journal line with sensitive words\n'
            '[WAITING] code=WAKE_LED_GPIO_DEPENDENCY_MISSING retry_seconds=5\n'
        ), stderr='')
        with patch('gonken_agent.support.shutil.which', return_value='/usr/bin/journalctl'), \
             patch('gonken_agent.support.subprocess.run', return_value=fake):
            payload = support._service_event_codes()
        for unit in support.SERVICE_UNITS:
            self.assertEqual(payload['units'][unit]['codes'], {
                'INSTALL_ACTION': 1,
                'WAKE_LED_GPIO_DEPENDENCY_MISSING': 2,
            })
        self.assertNotIn('secret', json.dumps(payload))
        self.assertNotIn('private', json.dumps(payload))

    def test_release_identity_export_binds_current_symlink_to_record(self):
        release_root = self.root / 'release-root'
        commit = 'a' * 40
        release = release_root / 'releases' / commit
        release.mkdir(parents=True)
        (release / 'release.record').write_text(
            'format=gonken-release-v1\n'
            f'commit={commit}\n'
            'profile=core-pi-trixie-py313\n'
            'validation=passed\n',
            encoding='utf-8',
        )
        (release_root / 'current').symlink_to(Path('releases') / commit)
        with patch('gonken_agent.support.RELEASE_ROOT', release_root):
            payload = support._safe_release_identity()
        self.assertEqual(payload['status'], 'READY')
        self.assertEqual(payload['commit'], commit)
        self.assertEqual(payload['profile'], 'core-pi-trixie-py313')
        self.assertEqual(payload['active_release'], f'releases/{commit}')

    def test_release_identity_rejects_unknown_record_format(self):
        release_root = self.root / 'release-root-bad-format'
        commit = 'b' * 40
        release = release_root / 'releases' / commit
        release.mkdir(parents=True)
        (release / 'release.record').write_text(
            'format=unexpected-format\n'
            f'commit={commit}\n'
            'profile=core-pi-trixie-py313\n'
            'validation=passed\n',
            encoding='utf-8',
        )
        (release_root / 'current').symlink_to(Path('releases') / commit)
        with patch('gonken_agent.support.RELEASE_ROOT', release_root):
            payload = support._safe_release_identity()
        self.assertEqual(payload['status'], 'UNAVAILABLE')

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
            self.assertIn('environment_control.json', z.namelist())
            self.assertIn('environment_health.json', z.namelist())
            env=json.loads(z.read('environment_control.json'))
            self.assertFalse(env['physical_evidence'])
            self.assertFalse(env['capabilities']['software_speed_control'])
            self.assertEqual(payload['schema'],1)
            self.assertFalse(payload['privacy']['content_logging'])
