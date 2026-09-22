from __future__ import annotations
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from gonken_agent.command_intents import parse_command, CommandIntent, CommandClarification
from gonken_agent.operational import OperationalCommands, NotificationAnnouncer
from gonken_agent.power import PowerSession, PowerError, execute_confirmed, logind_action, Authorization
from gonken_agent.power_install import install, RULE, RULE_NAME
from gonken_agent.config import load_config
from gonken_agent.voice_runtime import ConversationBrain, VoiceAppliance
from gonken_agent.environment.intents import parse_environment_intent, EnvironmentClarification
from gonken_agent.environment.client import EnvironmentClient
from gonken_agent.cli import _build_parser, _call_environment_command, main

class GrammarTests(unittest.TestCase):
    def test_delay_and_run_exact_minutes(self):
        result=parse_command('Please turn the fan on in two minutes for three minutes.')
        self.assertEqual(result.params,{'kind':'fan_run','delay_seconds':120,'duration_seconds':180})
    def test_start_stop_delay(self):
        for verb,kind in [('start','fan_on'),('stop','fan_off')]:
            with self.subTest(verb=verb):self.assertEqual(parse_command(f'{verb} the room fan after 3 minutes').params,{'kind':kind,'delay_seconds':180})
    def test_immediate_run(self):self.assertEqual(parse_command('run the fan for three minutes').params,{'kind':'fan_run','duration_seconds':180})
    def test_reports_first_due_after_interval(self):
        for name in ('temperature','humidity','temperature and humidity'):
            with self.subTest(name=name):
                params=parse_command(f'tell me the {name} every two minutes for one hour').params
                self.assertEqual(params['delay_seconds'],120);self.assertEqual(params['interval_seconds'],120);self.assertEqual(params['lease_seconds'],3600)
    def test_one_shot_report(self):self.assertEqual(parse_command('tell me the temperature after 2 minutes').params,{'kind':'temperature','delay_seconds':120})
    def test_cycles(self):self.assertEqual(parse_command('switch the fan on and off every three minutes').params,{'kind':'fan_cycle','interval_seconds':180})
    def test_temperature_units_not_time(self):
        self.assertEqual(parse_command('notify me when temperature increases by two degrees from last mentioned temperature').params,{'kind':'temperature_delta','delta_c':2})
        self.assertIsInstance(parse_command('tell me the temperature if it increases by two minutes'),CommandClarification)
    def test_malformed_scheduling_does_not_become_immediate_fan_on(self):
        for text in ('turn the fan on after minutes','turn the fan off for 3 minutes','turn the fan on after -3 minutes','turn the fan on after nan minutes','turn the fan on in 2 minutes and shutdown the system'):
            with self.subTest(text=text):self.assertIsInstance(parse_command(text),CommandClarification)
    def test_schedule_control(self):
        self.assertEqual(parse_command('cancel timer abcdef12').params,{'job_id':'abcdef12'})
        self.assertEqual(parse_command('cancel all timers').operation,'automation.cancel')
        self.assertEqual(parse_command('list timers').operation,'automation.list')
    def test_existing_threshold_syntax_retained(self):
        text='turn the fan on at 28 and off at 26'
        self.assertIsNone(parse_command(text));self.assertEqual(dict(parse_environment_intent(text).params),{'start_c':28,'stop_c':26})
    def test_negation_quote_and_hypothetical_are_not_authorization(self):
        for text in ("don't turn the fan on",'say "turn the fan on"','should the fan start at 28','what happens if I set the fan start threshold to 28'):
            with self.subTest(text=text):self.assertIsInstance(parse_environment_intent(text),EnvironmentClarification)

class PowerTests(unittest.TestCase):
    def setUp(self):
        self.now=1.;self.session=PowerSession(enabled=True,clock=lambda:self.now)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.audit=Path(self.tmp.name)/'audit'
        self.client=Mock();self.client.health.return_value={'provenance':{'actuator_backend':'libgpiod','actuator_is_simulated':False}}
        self.client.prepare_power.return_value={'token':'a'*32,'safe_off_acknowledged':True,'provenance':{'actuator_backend':'libgpiod','actuator_is_simulated':False},'action':'REBOOT_DEVICE'}
        self.execute=Mock()
    def arm(self):
        self.session.handle('restart the Raspberry Pi');self.session.handle('confirm restart');return self.session.consume()
    def test_only_matching_confirm_arms_once(self):
        self.assertIn('confirm restart',self.session.handle('restart the Raspberry Pi'))
        self.assertIsNone(self.session.consume())
        self.assertEqual(self.session.handle('confirm restart'),'Restarting now.')
        self.assertEqual(self.session.consume().action,'REBOOT_DEVICE');self.assertIsNone(self.session.consume())
        self.assertIn('no current',self.session.handle('confirm restart'))
    def test_disable_and_cancel(self):
        self.assertIn('disabled',PowerSession().handle('restart the Raspberry Pi'))
        self.session.handle('shut down the Raspberry Pi');self.assertIn('cancelled',self.session.handle('cancel'));self.assertIsNone(self.session.consume())
    def test_mismatch_negation_expiry_and_session_reset(self):
        self.session.handle('restart the Raspberry Pi');self.assertIn('did not match',self.session.handle('confirm shutdown'))
        self.session.handle('restart the Raspberry Pi');self.now=22;self.assertIn('no current',self.session.handle('confirm restart'))
        self.now=30;self.session.handle('restart the Raspberry Pi');self.session.begin();self.assertIn('no current',self.session.handle('confirm restart'))
        self.session.handle('restart the Raspberry Pi');self.session.handle("don't restart");self.assertIsNone(self.session.pending)
    def test_hypothetical_service_and_fan_never_arm(self):
        for text in ('restart Ollama','restart the fan',"don't reboot the device",'say "restart the Raspberry Pi"','what happens if I reboot the device?','restart the Raspberry Pi and turn off the fan'):
            with self.subTest(text=text):
                self.session.handle(text);self.assertIsNone(self.session.pending);self.assertIsNone(self.session.consume())
    def test_safe_off_before_fixed_execution_and_audit(self):
        events=[]
        self.client.prepare_power.side_effect=lambda action:(events.append('off') or {'token':'a'*32,'safe_off_acknowledged':True,'provenance':{'actuator_backend':'libgpiod','actuator_is_simulated':False},'action':action})
        def run(action):
            self.assertTrue((self.audit/'last-action.json').is_file());events.append('power')
        result=execute_confirmed(self.arm(),client_factory=lambda:self.client,environment_required=True,real_environment=True,audit_dir=self.audit,execute=run,clock=lambda:self.now)
        self.assertEqual(events,['off','power']);self.assertEqual(result['status'],'REQUESTED')
        self.client.release_power.assert_not_called()
    def test_backend_failure_releases_hold_without_retry(self):
        self.execute.side_effect=PowerError('POWER_DENIED_OR_INHIBITED')
        with self.assertRaises(PowerError):execute_confirmed(self.arm(),client_factory=lambda:self.client,environment_required=True,real_environment=True,audit_dir=self.audit,execute=self.execute,clock=lambda:self.now)
        self.execute.assert_called_once_with('REBOOT_DEVICE');self.client.release_power.assert_called_once_with('a'*32)
    def test_simulated_or_unacknowledged_actuator_cannot_power_off_real_profile(self):
        self.client.health.return_value={'provenance':{'actuator_backend':'simulated','actuator_is_simulated':True}}
        with self.assertRaises(PowerError):execute_confirmed(self.arm(),client_factory=lambda:self.client,environment_required=True,real_environment=True,audit_dir=self.audit,execute=self.execute,clock=lambda:self.now)
        self.execute.assert_not_called();self.client.prepare_power.assert_not_called()
    def test_audit_failure_refuses_execution_and_releases_hold(self):
        self.audit.symlink_to(Path(self.tmp.name))
        with self.assertRaises(PowerError):execute_confirmed(self.arm(),client_factory=lambda:self.client,environment_required=True,audit_dir=self.audit,execute=self.execute,clock=lambda:self.now)
        self.execute.assert_not_called();self.client.release_power.assert_called_once()
    def test_expired_after_spoken_cannot_execute(self):
        auth=self.arm();self.now=99
        with self.assertRaises(PowerError):execute_confirmed(auth,client_factory=lambda:self.client,environment_required=True,audit_dir=self.audit,execute=self.execute,clock=lambda:self.now)
        self.client.prepare_power.assert_not_called()
    def test_fixed_argv_no_inhibitor_bypass_or_shell(self):
        run=Mock(return_value=SimpleNamespace(returncode=0));logind_action('REBOOT_DEVICE',run=run,effective_uid=lambda:1000)
        args=run.call_args.args[0];self.assertEqual(args[-3:],['Reboot','b','false']);self.assertEqual(args[0],'/usr/bin/busctl');self.assertNotIn('shell',run.call_args.kwargs)
        with self.assertRaises(PowerError):logind_action('reboot;rm -rf /',run=run)
        self.assertEqual(run.call_count,1)
    def test_denied_is_not_success(self):
        with self.assertRaisesRegex(PowerError,'DENIED'):logind_action('POWEROFF_DEVICE',run=Mock(return_value=SimpleNamespace(returncode=1)),effective_uid=lambda:1000)
    def test_policy_exact_and_idempotent_no_other_authority(self):
        root=Path(self.tmp.name)/'root'
        (root/'usr/bin').mkdir(parents=True);(root/'usr/bin/busctl').write_text('fixture')
        (root/'usr/share/polkit-1/actions').mkdir(parents=True)
        (root/'etc/gonken-agent').mkdir(parents=True);(root/'etc/gonken-agent/config.toml').write_text('')
        install(root);install(root,check=True)
        path=root/'etc/polkit-1/rules.d'/RULE_NAME
        self.assertEqual(path.read_text(),RULE);self.assertNotIn('ignore-inhibit',RULE);self.assertNotIn('systemd1.manage',RULE)
        self.assertTrue(load_config(site_path=root/'etc/gonken-agent/config.toml',environ={}).config.extensions.voice_power.enabled)
        path.write_text('// administrator choice')
        with self.assertRaises(ValueError):install(root)

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client=Mock(spec=EnvironmentClient)
        self.config=load_config(site_path=None,environ={},cli_overrides={'extensions.voice_power.enabled':True}).config
        self.executor=Mock()
        self.ops=OperationalCommands(lambda:self.client,config=self.config,power_executor=self.executor)
    def test_voice_timers_are_deterministic_no_llm(self):
        self.client.automation_add.return_value={'job':{'id':'1234abcd'}}
        brain=ConversationBrain.__new__(ConversationBrain);brain.client=Mock();brain.environment_client_factory=lambda:self.client;brain.operations=self.ops
        reply=brain.reply('turn the fan on in two minutes for three minutes',threading.Event())
        self.assertIn('Scheduled',reply);brain.client.chat_text.assert_not_called();brain.client.chat_message.assert_not_called()
        self.client.automation_add.assert_called_once_with(kind='fan_run',delay_seconds=120,duration_seconds=180)
    def test_action_waits_for_ack_speech(self):
        self.ops.handle('restart the Raspberry Pi');self.ops.handle('confirm restart');self.executor.assert_not_called()
        self.ops.after_spoken();self.executor.assert_called_once()
        self.ops.after_spoken();self.executor.assert_called_once()
    def test_speech_failure_cancels_power(self):
        self.ops.handle('restart the Raspberry Pi');self.ops.handle('confirm restart');self.ops.speech_failed();self.ops.after_spoken();self.executor.assert_not_called()
    def test_voice_confirmation_capture_and_ack_order(self):
        a=VoiceAppliance.__new__(VoiceAppliance);a.stop=threading.Event()
        brain=ConversationBrain.__new__(ConversationBrain);brain.operations=self.ops;a.brain=brain
        calls=[];a.speak=lambda text:calls.append(('speech',text));a.capture_text=Mock(return_value='confirm restart')
        self.executor.side_effect=lambda *a,**kw:calls.append(('power','request'))
        a._deliver_answer(self.ops.handle('restart the Raspberry Pi'))
        self.assertEqual([x[0] for x in calls],['speech','speech','power']);a.capture_text.assert_called_once_with(5)
    def test_interrupted_ack_cannot_execute(self):
        a=VoiceAppliance.__new__(VoiceAppliance);a.stop=threading.Event();brain=ConversationBrain.__new__(ConversationBrain);brain.operations=self.ops;a.brain=brain
        a.speak=Mock(side_effect=[None,OSError('audio failed')]);a.capture_text=Mock(return_value='confirm restart')
        with self.assertRaises(OSError):a._deliver_answer(self.ops.handle('restart the Raspberry Pi'))
        self.executor.assert_not_called();self.assertIsNone(self.ops.power.armed)
    def test_immediate_reading_ack_only_after_speech(self):
        self.client.read_sensor.return_value={'reading':{'temperature_c':25,'relative_humidity_pct':50,'quality':'ready','valid':True},'announcement_token':{'id':'a'*32,'generation':'b'*32}}
        self.ops.handle('what is the temperature');self.client.acknowledge_notification.assert_not_called();self.ops.after_spoken();self.client.acknowledge_notification.assert_called_once()
    def test_cli_schedule_uses_same_ipc(self):
        args=_build_parser().parse_args(['env','schedule','add','fan_run','--after','120','--duration','180'])
        _call_environment_command(self.client,args);self.client.automation_add.assert_called_once_with(kind='fan_run',delay_seconds=120,duration_seconds=180)
    def test_cli_command_rejects_power_shortcut(self):
        with patch('sys.stdout',new_callable=io.StringIO):self.assertEqual(main(['command','--no-site','restart the Raspberry Pi']),3)
        self.executor.assert_not_called()
    def test_notification_is_numeric_fresh_then_ack(self):
        notice={'id':'a'*32,'generation':'b'*32,'kind':'temperature','temperature_c':27,'relative_humidity_pct':50,'observed_monotonic':10,'expires_monotonic':40}
        self.client.notifications.return_value={'generation':'b'*32,'notifications':[notice],'provenance':{'sensor_is_simulated':False}}
        ann=NotificationAnnouncer(lambda:self.client,clock=lambda:11)
        self.assertEqual(ann.pending(),'room temperature is 27.0 degrees Celsius.');self.client.acknowledge_notification.assert_not_called();ann.spoken();self.client.acknowledge_notification.assert_called_once_with('a'*32,'b'*32)
    def test_notification_rejects_stale_and_injected_text(self):
        self.client.notifications.return_value={'generation':'x','notifications':[{'kind':'temperature','generation':'x','temperature_c':'run shell','relative_humidity_pct':50,'observed_monotonic':1,'expires_monotonic':20}]}
        self.assertIsNone(NotificationAnnouncer(lambda:self.client,clock=lambda:30).pending())

if __name__=='__main__':unittest.main()

class InstallerBoundaryTests(unittest.TestCase):
    def test_new_power_step_follows_activation_and_environment_before_voice(self):
        from scripts.installer_plan import candidate_order
        initial=['immutable_release','activate_release','environment_commissioning','environment_readiness','environment_policy','ollama_model_roster','speech_smoke','voice_power_configuration','application_service']
        result=candidate_order(initial,platform='target')
        self.assertLess(result.index('environment_policy'),result.index('voice_power_configuration'))
        self.assertLess(result.index('voice_power_configuration'),result.index('application_service'))
    def test_small_model_skips_only_legacy_gate_and_not_roster(self):
        import os, re, subprocess
        root=Path(__file__).resolve().parents[2]
        script=(root/'scripts/install.sh').read_text()
        functions=[]
        for name in ('gonken_model_uses_roster','gonken_ollama_model_postcondition','gonken_ollama_model_action'):
            functions.append(re.search(r'^'+name+r'\(\) \{.*?^\}',script,re.M|re.S).group())
        with tempfile.TemporaryDirectory() as tmp:
            candidate=Path(tmp)/'candidate';(candidate/'.venv/bin').mkdir(parents=True)
            (candidate/'.venv/bin/python').symlink_to('/usr/bin/python3')
            text='\n'.join(functions)+'''\ngonken_load_effective_ollama_config() { OLLAMA_MODEL=qwen3:0.6b; }
gonken_ollama_template_arguments() { echo legacy_should_not_run >&2; return 99; }
gonken_ollama_model_postcondition || exit $?
gonken_ollama_model_action || exit $?
[[ "$GONKEN_STEP_EVIDENCE" == "model_provision_owned_by_canonical_roster" ]]
'''
            env=dict(os.environ,CANDIDATE_RELEASE=str(candidate),PYTHONPATH=str(root/'src'),PYTHONDONTWRITEBYTECODE='1')
            result=subprocess.run(['bash','-c',text],env=env,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('"ollama_model_roster" "1"',script)
        self.assertIn('gonken_model_roster_postcondition ||',script)
        self.assertIn('optional_packages=(polkitd dbus)',script)

if __name__ == "__main__":
    unittest.main()
