"""Host-only regression for the supplied real-sensor/simulated-actuator incident."""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gonken_agent.environment.daemon import environment_configuration_sha256, build_environment_service_core
from gonken_agent.environment.protocol import make_request
from gonken_agent.environment.domain import FanPower, SensorReading
from tests.unit.test_v09_environment_daemon_activation import _enabled_env_config, FakeSensor, FakeActuator, ManualClock
from tests.unit.test_v09_environment_service_manager import EnvironmentServiceFixture

ROOT = Path(__file__).resolve().parents[2]
# Match the installed sibling-module import environment for CLI-only managers.
sys.path.insert(0, str(ROOT / 'scripts'))
import environment_profile_manager as profiles
import environment_readiness as readiness
import environment_policy_manager as policy_manager


class RealEnvironmentTests(unittest.TestCase):
    def test_exact_known_simulation_profile_migrates_idempotently_to_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / 'config.toml'
            profiles.ensure_profile(site, name='real-sensor-simulated-actuator', group='unused')
            profiles.ensure_profile(site, name='full-real', group='unused')
            before = site.read_bytes()
            self.assertTrue(profiles.exact_profile(site, 'full-real', sensor_address=0x44))
            profiles.ensure_profile(site, name='full-real', group='unused')
            self.assertEqual(before, site.read_bytes())
            self.assertIs(profiles.read_environment(site)['simulation_runtime_control_enabled'], False)
            self.assertEqual(profiles.read_environment(site)['relay_backend'], 'libgpiod')

    def test_profile_status_checks_sensor_address_and_bool_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / 'config.toml'
            site.write_text(profiles.profile_text('full-real', sensor_address=0x45))
            with mock.patch('sys.stderr'):
                self.assertEqual(profiles.main(['status','--site',str(site),'--expect-profile','full-real','--sensor-address','0x44']),75)
            site.write_text(profiles.profile_text('full-real').replace('i2c_bus = 1','i2c_bus = true'))
            self.assertIsNone(profiles.detect_managed_profile(site))

    def test_full_real_service_starts_without_historical_physical_pass_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = EnvironmentServiceFixture(Path(tmp))
            self.assertEqual(fixture.run('install').returncode,0)
            site = fixture.system_root / 'etc/gonken-agent/config.toml'
            site.parent.mkdir(parents=True)
            site.write_text(profiles.profile_text('full-real'))
            result = fixture.run('converge', profile='full-real')
            self.assertEqual(result.returncode,0,result.stderr)
            log = fixture.systemctl_log.read_text()
            self.assertIn('enable gonken-environment.service',log)
            self.assertIn('restart gonken-environment.service',log)
            self.assertEqual(fixture.run('commissioned-status',profile='full-real').returncode,0)

    def test_full_real_never_claims_success_for_simulated_or_stale_daemon(self):
        payload = {'overall':'READY','sensor':'ready','actuator':'READY','physical_evidence':False,
            'provenance': {'sensor_backend':'sht31','actuator_backend':'libgpiod',
                'sensor_is_simulated':False,'actuator_is_simulated':False,'physical_evidence':False,
                'release_commit':'a'*40,'configuration_sha256':'b'*64}}
        self.assertTrue(readiness.validate_payload(payload,'full-real',expected_commit='a'*40,expected_config='b'*64)[0])
        for field, value in [('actuator_backend','simulated'),('actuator_is_simulated',True),('release_commit','c'*40),('configuration_sha256','d'*64)]:
            bad = json.loads(json.dumps(payload));bad['provenance'][field]=value
            self.assertFalse(readiness.validate_payload(bad,'full-real',expected_commit='a'*40,expected_config='b'*64)[0], field)
        payload['overall']='STARTING';payload['sensor']='starting'
        self.assertTrue(readiness.validate_payload(payload,'full-real',expected_commit='a'*40,expected_config='b'*64,binding_only=True)[0])
        self.assertFalse(readiness.validate_payload(payload,'full-real')[0])

    def test_read_only_construction_has_effective_config_fingerprint_no_hardware(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _enabled_env_config(tmp); sensor=FakeSensor();actuator=FakeActuator()
            core = build_environment_service_core(cfg, initialize_policy=False,
                sensor_factory=lambda c:sensor,actuator_factory=lambda c:actuator)
            self.assertEqual(core.daemon_metadata()['configuration_sha256'],environment_configuration_sha256(cfg))
            self.assertNotEqual(environment_configuration_sha256(cfg),environment_configuration_sha256(dataclasses.replace(cfg,relay_backend='simulated')))
            core.handle(make_request('health.get'))
            self.assertEqual(sensor.calls,0);self.assertEqual(actuator.commands,[])
            self.assertFalse(Path(cfg.policy_path).exists())

    def test_real_profile_auto_crossings_safe_off_and_no_simulation_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg=_enabled_env_config(tmp);clock=ManualClock();actuator=FakeActuator();sensor=FakeSensor()
            temp = [29.0]
            def reading(*,now_monotonic):
                return SensorReading(temperature_c=temp[0],relative_humidity_pct=50., observed_monotonic=now_monotonic,
                    sensor_address=0x44,source_backend='sht31',crc_valid=True)
            sensor.read=reading
            core=build_environment_service_core(cfg,now=clock,sensor_factory=lambda c:sensor,actuator_factory=lambda c:actuator)
            self.assertIsNone(core.simulation_state)
            core.handle(make_request('policy.update',{'mode':'automatic','expected_generation':1}))
            for n in [0.,2.,4.]:clock.set(n);core.poll_once()
            self.assertEqual(core.controller.state.fan_power,FanPower.OFF) # minimum OFF dwell
            clock.set(61.);core.poll_once()
            self.assertEqual(actuator.commands[-1],FanPower.ON)
            temp[0]=25.
            for n in [63.,65.]:clock.set(n);core.poll_once()
            self.assertEqual(core.controller.state.fan_power,FanPower.ON) # minimum ON dwell
            clock.set(122.);core.poll_once()
            self.assertEqual(actuator.commands[-1],FanPower.OFF)
            temp[0]=29.
            for n in [183.,185.,187.]:clock.set(n);core.poll_once()
            self.assertEqual(actuator.commands[-1],FanPower.ON)
            temp[0]=None
            clock.set(189.);core.poll_once()
            self.assertEqual(actuator.commands[-1],FanPower.OFF) # fault overrides dwell
            self.assertIsNone(core.simulation_state)
            with self.assertRaises(Exception):core.handle(make_request('simulation.sensor.set',{'temperature_c':30.,'relative_humidity_pct':50.}))
            saved=json.loads(Path(cfg.policy_path).read_text())
            self.assertEqual(saved['mode'],'automatic')
            core.shutdown_safe_off()

    def test_policy_manager_changes_only_mode_and_is_idempotent(self):
        before={'mode':'manual','generation':8,'schema_version':1,'start_c':27.,'stop_c':25.5,
            'minimum_on_seconds':90,'minimum_off_seconds':120}
        after={**before,'generation':9,'mode':'automatic'}
        with mock.patch.object(policy_manager,'read_agent',side_effect=[{'policy':before},{'policy':after},{'policy':after}]) as call:
            self.assertEqual(policy_manager.converge(Path('/agent'),'automatic'),after)
            self.assertEqual(call.call_args_list[1].args[1],['env','policy','set','--expected-generation','8','--mode','automatic','--json'])
        with mock.patch.object(policy_manager,'read_agent',return_value={'policy':after}) as call:
            policy_manager.converge(Path('/agent'),'automatic');self.assertEqual(call.call_count,1)
        with mock.patch.object(policy_manager,'read_agent',return_value={'policy':before}) as call:
            with self.assertRaises(ValueError):policy_manager.converge(Path('/agent'),'automatic',check=True)
            self.assertEqual(call.call_count,1)

    def test_policy_manager_rejects_concurrent_or_unexpected_threshold_change(self):
        before={'mode':'manual','generation':8,'schema_version':1,'start_c':27.,'stop_c':25.5,'minimum_on_seconds':90,'minimum_off_seconds':120}
        after={**before,'generation':9,'mode':'automatic','start_c':30.}
        with mock.patch.object(policy_manager,'read_agent',side_effect=[{'policy':before},{'policy':after},{'policy':after}]):
            with self.assertRaisesRegex(ValueError,'postcondition'):policy_manager.converge(Path('/agent'),'automatic')

    def test_readiness_rejects_nonfinite_budget_and_unbound_binding_probe(self):
        for t,i in [(float('nan'),1),(1,float('inf')),(0,0)]:
            with self.assertRaises(readiness.ReadinessError):readiness.probe(Path('/agent'),'full-real',timeout=t,interval=i)
        with self.assertRaises(readiness.ReadinessError):readiness.probe(Path('/agent'),'full-real',timeout=1,interval=0,binding_only=True)

if __name__ == '__main__': unittest.main()
