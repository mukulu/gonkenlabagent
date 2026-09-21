import json
import tempfile
import unittest
import tarfile
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
        output=self.root/'support.tar.bz2'
        telemetry=self.root/'telemetry.jsonl';Telemetry(telemetry).append({'status':'DEGRADED'})
        create_bundle(output,self.config,self.health,telemetry)
        with tarfile.open(output, "r:bz2") as z:
            self.assertTrue(all(member.isfile() for member in z.getmembers()))
            self.assertEqual(set(z.getnames()),{
                'collection_errors.json',
                'component_readiness.json',
                'configuration.json',
                'configuration_provenance.json',
                'diagnostic_summary.json',
                'environment.json',
                'environment_control.json',
                'environment_health.json',
                'evidence_index.json',
                'evidence_phase.json',
                'health.json',
                'install_events.json',
                'ollama_inventory.json',
                'permissions.json',
                'platform_inventory.json',
                'runtime_bindings.json',
                'resource_claims.json',
                'service_events.json',
                'systemd_effective.json',
                'target_manifest.json',
                'telemetry.json',
                'tool_broker.json',
            })
            raw=b''.join(z.extractfile(name).read() for name in z.getnames())
        self.assertNotIn(b'private-person',raw);self.assertNotIn(b'private-token',raw)
        self.assertNotIn(str(self.root).encode(),raw)
        self.assertEqual(output.stat().st_mode&0o777,0o600)
        with tarfile.open(output, "r:bz2") as z:
            index=json.loads(z.extractfile('evidence_index.json').read())
            target=json.loads(z.extractfile('target_manifest.json').read())
            resources=json.loads(z.extractfile('resource_claims.json').read())
        self.assertFalse(resources['physical_acceptance_claimed'])
        self.assertIn('target_manifest.json', {item['path'] for item in index['members']})
        self.assertEqual(target['status'], 'UNAVAILABLE')
        self.assertFalse(index['physical_acceptance_claimed'])
        self.assertEqual(index['format'], 'gonken-evidence-bundle-index-v2')
        self.assertEqual(index['bundle_kind'], 'support')
        for member in index['members']:
            self.assertRegex(member['sha256'], r'^[0-9a-f]{64}$')
            self.assertGreater(member['bytes'], 0)

    def test_bundle_preserves_allow_listed_health_reason_codes(self):
        output=self.root/'support-codes.tar.bz2'
        create_bundle(output,self.config,self.health)
        with tarfile.open(output, "r:bz2") as z:
            payload=json.loads(z.extractfile('health.json').read())
        rows={row['component']:row for row in payload['components']}
        self.assertEqual(rows['environment']['code'], self.health['environment']['code'])
        self.assertRegex(rows['environment']['code'], r'^[A-Z0-9_]+$')

    def test_runtime_binding_member_reports_release_interpreter_probe_without_raw_output(self):
        output=self.root/'support-runtime.tar.bz2'
        create_bundle(output,self.config,self.health)
        with tarfile.open(output, "r:bz2") as z:
            payload=json.loads(z.extractfile('runtime_bindings.json').read())
        self.assertIn('release', payload)
        self.assertIn('venv', payload)
        self.assertIn('bindings', payload)
        self.assertEqual(set(payload['bindings']), {'gpiod'})
        self.assertEqual(payload['sensor_transport']['type'], 'linux-i2c-dev-stdlib')
        self.assertFalse(payload['sensor_transport']['python_smbus_required'])
        self.assertNotIn('stderr', json.dumps(payload))
        self.assertNotIn('stdout', json.dumps(payload))
        self.assertIn('gpio_platform', payload)
        self.assertIn('runtime_context', payload)
        self.assertIn('audio_session', payload)
        self.assertIn('voice_readiness', payload)
        self.assertFalse(payload['audio_session']['capture_content_collected'])

    def test_audio_endpoint_metadata_redacts_stable_bluetooth_identifiers(self):
        self.assertEqual(
            support._safe_audio_endpoint("bluez_input.41_42_06_42_05_80.0"),
            "bluez_input.DEVICE.0",
        )
        self.assertEqual(
            support._safe_audio_endpoint("bluez_output.AA:BB:CC:DD:EE:FF.1"),
            "bluez_output.DEVICE.1",
        )

    def test_service_audio_probe_refuses_to_mislabel_wrong_nonroot_identity(self):
        account=Mock(pw_uid=999)
        with patch("gonken_agent.support.pwd.getpwnam", return_value=account), \
             patch("gonken_agent.support.shutil.which", return_value="/usr/bin/pactl"), \
             patch("gonken_agent.support.os.geteuid", return_value=1000), \
             patch("gonken_agent.support.subprocess.run") as run:
            payload=support._service_user_audio_context()
        self.assertEqual(payload["status"], "UNAVAILABLE")
        self.assertEqual(payload["code"], "SERVICE_IDENTITY_REQUIRED")
        run.assert_not_called()

    def test_target_manifest_member_embeds_valid_non_actuating_manifest(self):
        manifest=self.root/'target-manifest.json'
        manifest.write_text(json.dumps({
            'format': 'gonken-target-hardware-manifest-v1',
            'raspberry_pi': {'model': 'Raspberry Pi 5 Model B', 'revision': 'd04170'},
            'privacy': {
                'raw_audio_included': False,
                'transcripts_included': False,
                'prompts_or_model_responses_included': False,
            },
            'physical_acceptance_claimed': False,
        }), encoding='utf-8')
        output=self.root/'support-target.tar.bz2'
        create_bundle(output,self.config,self.health,target_manifest=manifest)
        with tarfile.open(output, "r:bz2") as z:
            payload=json.loads(z.extractfile('target_manifest.json').read())
        self.assertEqual(payload['support_member_status'], 'READY')
        self.assertEqual(payload['raspberry_pi']['model'], 'Raspberry Pi 5 Model B')
        self.assertFalse(payload['physical_acceptance_claimed'])

    def test_target_manifest_member_rejects_privacy_boundary_violation(self):
        manifest=self.root/'target-manifest-bad.json'
        manifest.write_text(json.dumps({
            'format': 'gonken-target-hardware-manifest-v1',
            'privacy': {
                'raw_audio_included': True,
                'transcripts_included': False,
                'prompts_or_model_responses_included': False,
            },
            'physical_acceptance_claimed': False,
        }), encoding='utf-8')
        output=self.root/'support-target-bad.tar.bz2'
        create_bundle(output,self.config,self.health,target_manifest=manifest)
        with tarfile.open(output, "r:bz2") as z:
            payload=json.loads(z.extractfile('target_manifest.json').read())
        self.assertEqual(payload['status'], 'INVALID')
        self.assertEqual(payload['detail'], 'target_probe_manifest_privacy_boundary_invalid')

    def test_gpio_platform_export_is_allowlisted_and_drops_raw_command_text(self):
        fake = Mock(returncode=0, stdout='gpiochip0 23\t"GPIO23"         output consumer=secret-name\n', stderr='private')
        with patch('gonken_agent.support.shutil.which', return_value='/usr/bin/gpioinfo'), \
             patch('gonken_agent.support.subprocess.run', return_value=fake), \
             patch('gonken_agent.support.Path.glob', return_value=[]):
            payload = support._gpio_platform_health()
        self.assertEqual(payload['status'], 'READY')
        self.assertEqual(payload['gpio23'], {
            'status': 'RESOLVED', 'chip': 'gpiochip0', 'line_offset': 23, 'line_name': 'GPIO23'
        })
        encoded = json.dumps(payload)
        self.assertNotIn('secret-name', encoded)
        self.assertNotIn('private', encoded)


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
            'run_id': '1.2',
            'sequence': 1,
            'observed_epoch': 1,
            'level': 'error',
            'code': 'INSTALL_ACTION',
            'step_id': 'appliance_readiness',
            'message': 'action_failed_exit_75',
        }])
        self.assertEqual(payload['latest_run_id'], '1.2')
        self.assertEqual(payload['latest_run_last_code'], 'INSTALL_ACTION')

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
            events = {row['code']: row for row in payload['units'][unit]['events']}
            self.assertEqual(events['WAKE_LED_GPIO_DEPENDENCY_MISSING']['count'], 2)
            self.assertEqual(events['WAKE_LED_GPIO_DEPENDENCY_MISSING']['first_sequence'], 1)
            self.assertEqual(events['WAKE_LED_GPIO_DEPENDENCY_MISSING']['last_sequence'], 4)
            self.assertFalse(payload['units'][unit]['raw_text_exported'])
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

    def test_evidence_phase_binds_latest_install_run_without_raw_content(self):
        phase = support._evidence_phase_context({
            "status": "READY", "latest_run_id": "1700000000.123",
            "latest_run_event_count": 4, "latest_run_last_code": "INSTALL_COMPLETE",
        })
        self.assertEqual(phase["install_run_id"], "1700000000.123")
        self.assertIn("current_runtime_state", phase["precedence"])
        self.assertFalse(phase["physical_acceptance_claimed"])


    def test_diagnostic_summary_treats_same_boot_failure_history_as_recovered_when_current_ready(self):
        files = {
            'evidence_phase.json': {'voice_ready': {'status': 'READY'}},
            'service_events.json': {'units': {'gonken-agent.service': {'codes': {'AUDIO_CAPTURE_FAILED': 2}}}},
            'permissions.json': {'entries': []},
            'component_readiness.json': {'components': {'room_fan_control': {'simulated': True},
                'temperature_humidity_sensor': {'simulated': False, 'backend': 'sht31'}}},
            'ollama_inventory.json': {'status': 'READY'},
        }
        payload = support._diagnostic_summary(files)
        codes = {row['code'] for row in payload['findings']}
        self.assertIn('VOICE_READY_WITH_RECOVERED_HISTORY', codes)
        self.assertIn('REAL_SENSOR_WITH_SIMULATED_ACTUATOR', codes)
        self.assertNotIn('VOICE_FAILED', codes)

    def test_permissions_manifest_exposes_owner_group_mode_not_file_content(self):
        state = self.root / 'state'
        state.mkdir(mode=0o750)
        with patch('gonken_agent.support.Path', wraps=Path):
            row = support._path_permission('test', state)
        self.assertTrue(row['exists'])
        self.assertIn('mode_octal', row)
        self.assertNotIn('content', row)

    def test_content_in_telemetry_rejected_before_output(self):
        telemetry=self.root/'telemetry.jsonl';telemetry.write_text('{"transcript":"secret"}\n')
        output=self.root/'support.tar.bz2'
        with self.assertRaises(ValueError):create_bundle(output,self.config,self.health,telemetry)
        self.assertFalse(output.exists());self.assertFalse(list(self.root.glob('.support-*')))
    def test_existing_symlink_and_publish_race_preserve_destination(self):
        output=self.root/'support.tar.bz2';output.write_bytes(b'old')
        with self.assertRaises(ValueError):create_bundle(output,self.config,self.health)
        self.assertEqual(output.read_bytes(),b'old')
        output.unlink();output.symlink_to(self.root/'elsewhere')
        with self.assertRaises(ValueError):create_bundle(output,self.config,self.health)
        output.unlink()
        with patch('gonken_agent.evidence.os.link',side_effect=FileExistsError):
            with self.assertRaises(FileExistsError):create_bundle(output,self.config,self.health)
        self.assertFalse(list(self.root.glob('.support-*')))
    def test_extra_health_details_are_not_exported(self):
        output=self.root/'support.tar.bz2';self.health['components'][0]['detail']='secret transcript'
        create_bundle(output,self.config,self.health)
        with tarfile.open(output, "r:bz2") as z:self.assertNotIn(b'secret',z.extractfile('health.json').read())
    def test_startup_snapshot_is_allow_listed_member(self):
        from gonken_agent.diagnostics import write_startup_snapshot
        snapshot_dir=self.root/'snapshots'
        snapshot=write_startup_snapshot(self.config.config,directory=snapshot_dir,retain=1)
        output=self.root/'support.tar.bz2'
        create_bundle(output,self.config,self.health,startup_snapshot=snapshot['latest'])
        with tarfile.open(output, "r:bz2") as z:
            self.assertIn('startup_snapshot.json',z.getnames())
            payload=json.loads(z.extractfile('startup_snapshot.json').read())
            self.assertIn('environment_control.json', z.getnames())
            self.assertIn('environment_health.json', z.getnames())
            env=json.loads(z.extractfile('environment_control.json').read())
            self.assertFalse(env['physical_evidence'])
            self.assertFalse(env['capabilities']['software_speed_control'])
            self.assertEqual(payload['schema'],1)
            self.assertFalse(payload['privacy']['content_logging'])
