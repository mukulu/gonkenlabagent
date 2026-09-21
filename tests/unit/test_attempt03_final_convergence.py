"""Exercise the actual final shell gate without calling installers or hardware."""
from __future__ import annotations
import copy
from dataclasses import replace
from pathlib import Path
import subprocess
import unittest
from unittest import mock
from gonken_agent.config import load_config
from gonken_agent.component_status import required_ready
from gonken_agent import cli

ROOT = Path(__file__).resolve().parents[2]

class FinalConvergenceTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(site_path=None).config
        self.payload = {'format':'gonken-component-status-v1', 'physical_acceptance_claimed':False,
                        'components':{n:{'status':'READY'} for n in ('voice_conversation','ollama_inference','llm_environment_tool_broker')}}
        self.payload['components']['llm_environment_tool_broker']['active_model_qualified'] = True

    def with_environment(self, sensor='sht31', relay='libgpiod'):
        env = replace(self.config.extensions.environment, enabled=True, sensor_backend=sensor, relay_backend=relay)
        cfg = replace(self.config, extensions=replace(self.config.extensions, environment=env))
        value = copy.deepcopy(self.payload)
        value['components'].update({
            'environment_controller':{'status':'READY','enabled':True},
            'temperature_humidity_sensor':{'status':'READY','backend':sensor,'simulated':sensor=='simulated'},
            'room_fan_control':{'status':'READY','backend':relay,'simulated':relay=='simulated'},
        })
        return cfg,value

    def test_disabled_optional_environment_does_not_block_core(self):
        self.assertFalse(self.config.extensions.environment.enabled)
        self.assertTrue(required_ready(self.config,self.payload))

    def test_required_core_capability_failure_is_not_optional(self):
        for name in self.payload['components']:
            value=copy.deepcopy(self.payload);value['components'][name]['status']='DEGRADED'
            self.assertFalse(required_ready(self.config,value),name)

    def test_unqualified_tools_cannot_become_ready_by_label(self):
        del self.payload['components']['llm_environment_tool_broker']['active_model_qualified']
        self.assertFalse(required_ready(self.config,self.payload))

    def test_selected_environment_requires_correct_backend_evidence(self):
        for sensor,relay in [('sht31','libgpiod'),('sht31','simulated'),('simulated','simulated')]:
            with self.subTest(sensor=sensor,relay=relay):
                cfg,value=self.with_environment(sensor,relay)
                self.assertTrue(required_ready(cfg,value))
                value['components']['room_fan_control']['simulated'] = not (relay=='simulated')
                self.assertFalse(required_ready(cfg,value))

    def test_real_profile_cannot_succeed_from_simulated_fallback(self):
        cfg,value=self.with_environment()
        value['components']['room_fan_control'].update(backend='simulated',simulated=True)
        self.assertFalse(required_ready(cfg,value))

    def test_missing_stale_or_disabled_selected_environment_refuses(self):
        cfg,value=self.with_environment()
        for name in ('environment_controller','temperature_humidity_sensor','room_fan_control'):
            bad=copy.deepcopy(value);bad['components'][name]['status']='DISABLED'
            self.assertFalse(required_ready(cfg,bad))
        self.assertFalse(required_ready(cfg,self.payload))

    def test_malformed_payload_and_false_physical_claim_refuse(self):
        for value in [None,[],{},dict(self.payload,physical_acceptance_claimed=True),dict(self.payload,components={})]:
            self.assertFalse(required_ready(self.config,value))

    def test_cli_exposes_explicit_readiness_contract(self):
        self.assertTrue(cli._build_parser().parse_args(['components','--require-ready']).require_ready)

    def shell_final(self, summary=0, components=0):
        text=(ROOT/'scripts/install.sh').read_text()
        start=text.index('gonken_final_convergence() {')
        end=text.index('\ngonken_bluetooth_manager()',start)
        function=text[start:end]
        start=text.index('if gonken_final_convergence; then')
        end=text.index('if [[ "${GONKEN_SOURCE_RECORD[invoking_user]}"',start)
        tail=text[start:end]
        # No source/import of the complete privileged installer. Actual final
        # function and branch are executed with explicit non-actuating fakes.
        script=f'''set -Eeuo pipefail
        declare -A GONKEN_SOURCE_RECORD=([resolved_commit]={'a'*40} [bluetooth_audio]=requested)
        timeout() {{ shift 2; "$@"; }}
        python3() {{ printf 'SUMMARY_CALLED\n'; return {summary}; }}
        gonken_install_summary_manager() {{ printf 'fixture.py'; }}
        gonken_print_component_summary() {{ printf 'COMPONENTS_CALLED\n'; return {components}; }}
        gonken_log_event() {{ printf 'EVENT\n'; }}
        gonken_collect_install_failure() {{ printf 'BUNDLE:%s\n' "$1"; }}
        {function}
        {tail}
        '''
        return subprocess.run(['bash','-c',script],capture_output=True,text=True,timeout=3)

    def test_summary_failure_never_prints_installation_complete(self):
        result=self.shell_final(summary=75)
        self.assertEqual(result.returncode,75,result.stderr)
        self.assertNotIn('INSTALLATION_COMPLETE',result.stdout)
        self.assertNotIn('COMPONENTS_CALLED',result.stdout)
        self.assertEqual(result.stdout.count('BUNDLE:'),1)

    def test_component_failure_never_prints_installation_complete(self):
        result=self.shell_final(components=1)
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertNotIn('INSTALLATION_COMPLETE',result.stdout)
        self.assertEqual(result.stdout.count('BUNDLE:'),1)

    def test_timeout_is_failure_not_success(self):
        result=self.shell_final(summary=124)
        self.assertEqual(result.returncode,124)
        self.assertNotIn('INSTALLATION_COMPLETE',result.stdout)
        self.assertIn('BUNDLE:124',result.stdout)

    def test_fresh_success_prints_one_complete_without_fake_bluetooth_pairing(self):
        result=self.shell_final()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.count('INSTALLATION_COMPLETE'),1)
        self.assertNotIn('BUNDLE:',result.stdout)
        self.assertNotIn('paired=true',result.stdout)
        self.assertIn('paired_state=see_evidence',result.stdout)

if __name__=='__main__': unittest.main()
