from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from gonken_agent import support
from gonken_agent.diagnostics import _actuator_command_summary
from gonken_agent.environment.journal import parse_event_line

class EnvironmentEvidenceTests(unittest.TestCase):
    def event(self):
        return {'code':'ENV_ACTUATOR_TRANSITION','backend':'libgpiod','gpio':'GPIO23',
                'gpio_consumer':'gonken-environment','reason':'AUTO_START_THRESHOLD','mode':'automatic',
                'relay_commanded':'on','requested':'on','previous':'off','write_result':'SUCCESS',
                'start_c':28.0,'stop_c':25.0,'release_commit':'a'*40,'configuration_sha256':'b'*64,'process_id':42}
    def test_safe_journal_transition_survives_without_content(self):
        event=self.event();event.update(raw_transcript='PRIVATE_CANARY',password='SECRET_CANARY')
        fake=Mock(returncode=0,stdout=json.dumps(event)+'\nprivate line\n',stderr='')
        with patch('gonken_agent.support.shutil.which',return_value='/usr/bin/journalctl'),patch('gonken_agent.support.subprocess.run',return_value=fake):
            result=support._service_event_codes()
        env=result['units']['gonken-environment.service'];self.assertEqual(env['codes'],{'ENV_ACTUATOR_TRANSITION':1})
        self.assertEqual(env['actuator_transitions'][0]['stop_c'],25.0)
        self.assertEqual(env['actuator_transitions'][0]['release_commit'],'a'*40)
        self.assertNotIn('CANARY',json.dumps(result));self.assertFalse(env['raw_text_exported'])
    def test_duplicate_keys_nonfinite_and_unsafe_identity_rejected(self):
        for raw in ('{"code":"ENV_ACTUATOR_TRANSITION","code":"ENV_ACTUATOR_WRITE_FAILED"}',
                    '{"code":"ENV_ACTUATOR_TRANSITION","start_c":NaN}', 'x'*5000,
                    json.dumps({**self.event(),'release_commit':'SECRET_CANARY'}),
                    json.dumps({**self.event(),'backend':'SECRET_CANARY'}),
                    json.dumps({**self.event(),'process_id':True})):
            self.assertIsNone(parse_event_line(raw))
    def test_history_bounded_and_not_current_readiness(self):
        fake=Mock(returncode=0,stdout=(json.dumps(self.event())+'\n')*80,stderr='')
        with patch('gonken_agent.support.shutil.which',return_value='/usr/bin/journalctl'),patch('gonken_agent.support.subprocess.run',return_value=fake):
            env=support._service_event_codes()['units']['gonken-environment.service']
        self.assertEqual(len(env['actuator_transitions']),40)
        self.assertEqual(env['event_scope'],'current_boot_history_not_current_readiness')
    def test_reconciliation_exports_only_phase_metadata(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);events=root/'logs/events';events.mkdir(parents=True)
            data={'format':'gonken-existing-environment-reconciliation-v1','status':'READY_EXISTING_ENVIRONMENT',
                  'inputs':{'candidate_commit':'a'*40,'current_commit':'b'*40,'configuration_inputs_sha256':'c'*64,'mode_requested':'automatic'},
                  'invocation_id':'d'*32,'reason_code':'REAL_THERMOSTAT_RECONCILED','password':'SECRET_CANARY',
                  'policy':{'private':'PRIVATE_CANARY'}}
            (root/'environment-current-reconciliation.json').write_text(json.dumps(data))
            with patch.object(support,'INSTALL_EVENTS_DIR',events):result=support._existing_environment_reconciliation()
            self.assertEqual(result['recorded_status'],'READY_EXISTING_ENVIRONMENT')
            self.assertFalse(result['runtime_freshness_claimed']);self.assertNotIn('CANARY',json.dumps(result))
    def test_command_metadata_export_preserves_unknown_and_errors_not_private_content(self):
        payload={'controller_desired':'off','relay_commanded':None,'actuator_write_errors':2,
                 'gpio_claimed':True,'gpio_consumer':'gonken-environment','actuator_simulated':False,
                 'last_actuator_command_reason':'ACTUATOR_ERROR_SAFE_OFF','last_write_result':'FAILED',
                 'last_actuator_command_monotonic':4.1,'raw_transcript':'SECRET_CANARY',
                 'fan_motion_observed':True}
        result=_actuator_command_summary(payload)
        self.assertEqual(result['actuator_write_errors'],2);self.assertIsNone(result['relay_commanded'])
        self.assertEqual(result['gpio_consumer'],'gonken-environment');self.assertNotIn('CANARY',json.dumps(result))
        self.assertFalse(result['fan_motion_observed'])
    def test_absent_record_is_not_false_ready(self):
        with tempfile.TemporaryDirectory() as name,patch.object(support,'INSTALL_EVENTS_DIR',Path(name)/'logs/events'):
            self.assertEqual(support._existing_environment_reconciliation()['status'],'UNAVAILABLE')

if __name__=='__main__':unittest.main()
