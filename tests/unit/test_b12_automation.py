from __future__ import annotations
from pathlib import Path
import math
import unittest
from unittest.mock import Mock

from gonken_agent.environment.automation import Automation, AutomationError, MAX_JOBS
from gonken_agent.environment.domain import FanPower, SensorReading
from gonken_agent.environment.protocol import make_request, encode_request, parse_request_bytes
from gonken_agent.environment.service import EnvironmentServiceCore, EnvironmentServiceError

class Actuator:
    def __init__(self): self.writes=[];self.fail=False
    def set_power(self, value):
        if self.fail: raise OSError('fixture')
        self.writes.append(value.value)
    def safe_off(self):
        if self.fail: raise OSError('fixture')
        self.writes.append('off')

class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.now=0.;self.temp=25.;self.actuator=Actuator()
        def read(**kw):
            return SensorReading(self.temp,50.,self.now,crc_valid=self.temp is not None,source_backend='sht31')
        self.core=EnvironmentServiceCore.with_defaults(now=lambda:self.now,sensor_read=read,fan_actuator=self.actuator)
        for t in (0,1,2):self.tick(t)
        self.store=Mock();self.core.policy_store=self.store
    def tick(self, t):
        self.now=float(t);return self.core.poll_once()
    def call(self, op, **params):return self.core.handle(make_request(op,params))
    def add(self, **params):return self.call('automation.add',**params)['job']

    def test_delay_is_owner_polled_and_respects_minimum_off(self):
        j=self.add(kind='fan_on',delay_seconds=5)
        self.tick(7);self.assertEqual(self.core.controller.state.fan_power,FanPower.OFF)
        self.assertEqual(self.call('automation.list')['jobs'][0]['due_in_seconds'],53)
        self.tick(60);self.assertEqual(self.core.controller.state.fan_power,FanPower.ON)
        self.assertEqual(self.call('health.get')['actuator_commands']['last_actuator_command_reason'],'TIMER_ON')
        self.assertEqual(self.call('automation.list')['jobs'],[])
        self.store.save.assert_not_called()

    def test_run_pair_switches_off_after_actual_start_duration(self):
        self.call('mode.set',mode='automatic');self.store.reset_mock()
        self.add(kind='fan_run',delay_seconds=120,duration_seconds=180)
        self.tick(121);self.assertEqual(self.core.controller.state.fan_power,FanPower.OFF)
        self.tick(122);self.assertEqual(self.core.controller.state.fan_power,FanPower.ON)
        self.tick(301);self.assertEqual(self.core.controller.state.fan_power,FanPower.ON)
        self.tick(302);self.assertEqual(self.core.controller.state.fan_power,FanPower.OFF)
        self.assertEqual(self.core.controller.state.mode.value,'manual')
        self.store.save.assert_not_called()

    def test_sensor_fault_cancels_future_on_no_replay_after_recovery(self):
        self.add(kind='fan_on',delay_seconds=120)
        self.temp=None;self.tick(10)
        self.assertEqual(self.call('automation.list')['jobs'],[])
        self.temp=25
        for t in (121,122,123):self.tick(t)
        self.assertEqual(self.core.controller.state.fan_power,FanPower.OFF)

    def test_manual_override_cancels_actuator_timers_not_reports(self):
        self.add(kind='fan_on',delay_seconds=120);self.add(kind='temperature',delay_seconds=120)
        self.call('fan.set',power='off')
        self.assertEqual([j['kind'] for j in self.call('automation.list')['jobs']],['temperature'])
        self.tick(122);self.assertEqual(self.core.controller.state.fan_power,FanPower.OFF)

    def test_cycle_is_bounded_and_cancel_forces_safe_off(self):
        self.add(kind='fan_cycle',interval_seconds=180,lease_seconds=600)
        self.tick(60);self.assertEqual(self.core.controller.state.fan_power,FanPower.ON)
        self.tick(240);self.assertEqual(self.core.controller.state.fan_power,FanPower.OFF)
        self.tick(420);self.assertEqual(self.core.controller.state.fan_power,FanPower.ON)
        result=self.call('automation.cancel')
        self.assertTrue(result['safe_off_requested']);self.assertEqual(self.core.controller.state.fan_power,FanPower.OFF)
        self.assertEqual(self.call('automation.list')['jobs'],[])

    def test_cycle_expiry_stops_on_state_without_repeating(self):
        self.add(kind='fan_cycle',interval_seconds=180,lease_seconds=120)
        self.tick(60);self.assertEqual(self.core.controller.state.fan_power,FanPower.ON)
        self.tick(123);self.assertEqual(self.core.controller.state.fan_power,FanPower.OFF)
        self.assertEqual(self.call('automation.list')['jobs'],[])

    def test_overlapping_composite_rejected_without_losing_first(self):
        j=self.add(kind='fan_run',delay_seconds=90,duration_seconds=180)
        with self.assertRaises(EnvironmentServiceError):self.add(kind='fan_on',delay_seconds=100)
        self.assertEqual(self.call('automation.list')['jobs'][0]['id'],j['id'])

    def test_one_shot_sensor_notification_and_ack(self):
        self.add(kind='temperature',delay_seconds=120)
        self.tick(122)
        n=self.call('notifications.get')['notifications'][0]
        self.assertEqual(n['temperature_c'],25.0);self.assertNotIn('text',n)
        self.assertEqual(self.call('automation.list')['jobs'],[])
        self.assertTrue(self.call('notifications.ack',id=n['id'],generation=n['generation'])['acknowledged'])
        self.assertFalse(self.call('notifications.ack',id=n['id'],generation=n['generation'])['acknowledged'])

    def test_repeat_no_catchup_burst(self):
        self.add(kind='temperature',delay_seconds=120,interval_seconds=120)
        self.tick(2000)
        self.assertEqual(len(self.call('notifications.get')['notifications']),1)
        self.assertEqual(self.call('automation.list')['jobs'][0]['due_in_seconds'],120)

    def test_stale_notifications_expire_without_false_acknowledgement(self):
        self.add(kind='temperature',delay_seconds=1);self.tick(3)
        n=self.call('notifications.get')['notifications'][0];self.tick(34)
        self.assertEqual(self.call('notifications.get')['notifications'],[])
        self.assertFalse(self.call('notifications.ack',id=n['id'],generation=n['generation'])['acknowledged'])
        self.assertIsNone(self.core.automation.last_announced_temperature)

    def test_delta_measures_from_last_successfully_announced_temperature(self):
        self.add(kind='temperature_delta',delta_c=2)
        self.temp=27.;self.tick(3)
        n=self.call('notifications.get')['notifications'][0]
        self.tick(4);self.assertEqual(len(self.call('notifications.get')['notifications']),1)
        self.call('notifications.ack',id=n['id'],generation=n['generation'])
        self.temp=28.;self.tick(5);self.assertEqual(self.call('notifications.get')['notifications'],[])
        self.temp=29.;self.tick(6);self.assertEqual(len(self.call('notifications.get')['notifications']),1)

    def test_direct_sensor_announcement_updates_baseline_only_on_ack(self):
        token=self.call('sensor.read')['announcement_token']
        self.assertIsNone(self.core.automation.last_announced_temperature)
        self.call('notifications.ack',**token)
        self.assertEqual(self.core.automation.last_announced_temperature,25.)

    def test_generation_prevents_cross_restart_ack(self):
        token=self.call('sensor.read')['announcement_token']
        self.core.automation=Automation()
        with self.assertRaises(EnvironmentServiceError):self.call('notifications.ack',**token)

    def test_disabled_rejects_actuator_job(self):
        self.call('mode.set',mode='disabled')
        with self.assertRaises(EnvironmentServiceError):self.add(kind='fan_on',delay_seconds=10)
        self.assertEqual(self.call('automation.list')['jobs'],[])

    def test_invalid_params_are_not_actions(self):
        for params in ({'kind':'shell','delay_seconds':1},{'kind':'fan_on','delay_seconds':True},
                       {'kind':'temperature','interval_seconds':30},{'kind':'fan_run','duration_seconds':2},
                       {'kind':'fan_cycle','interval_seconds':3},{'kind':'temperature_delta','delta_c':'two'},
                       {'kind':'temperature_delta','interval_seconds':120},{'kind':'fan_on','command':'rm'},
                       {'kind':'fan_on','delay_seconds':math.nan},{'kind':'temperature','delay_seconds':math.inf}):
            before=list(self.actuator.writes)
            with self.subTest(params=params),self.assertRaises(EnvironmentServiceError):self.add(**params)
            self.assertEqual(self.actuator.writes,before)

    def test_job_limit_and_history_are_bounded(self):
        for _ in range(MAX_JOBS):self.add(kind='temperature',delay_seconds=100)
        with self.assertRaises(EnvironmentServiceError):self.add(kind='temperature',delay_seconds=100)
        self.call('automation.cancel');self.assertLessEqual(len(self.core.automation.history),32)

    def test_read_only_queries_do_not_fire_timers_or_sample_sensor(self):
        self.add(kind='fan_on',delay_seconds=120);self.now=200
        before=self.core._poll_count;writes=list(self.actuator.writes)
        for _ in range(10):self.call('state.snapshot.get');self.call('health.get');self.call('automation.list')
        self.assertEqual(self.core._poll_count,before);self.assertEqual(self.actuator.writes,writes)

    def test_actuator_failure_cancels_schedule_and_never_claims_success(self):
        self.add(kind='fan_on',delay_seconds=120);self.actuator.fail=True
        result=self.tick(122)
        self.assertFalse(result['ok']);self.assertEqual(self.core.automation.jobs,{})
        self.assertIsNone(self.call('health.get')['actuator_commands']['relay_commanded'])

    def test_recovery_sample_requirement_protects_timer_on(self):
        self.core.controller.valid_samples_to_recover=10
        self.add(kind='fan_on',delay_seconds=120);self.tick(122)
        self.assertEqual(self.core.controller.state.fan_power,FanPower.OFF)
        self.assertEqual(self.core.automation.jobs,{})

    def test_power_preparation_acknowledges_off_and_locks_mutation(self):
        self.call('mode.set',mode='automatic');self.store.reset_mock()
        p=self.call('power.prepare',action='REBOOT_DEVICE')
        self.assertTrue(p['safe_off_acknowledged']);self.assertEqual(self.actuator.writes[-1],'off')
        with self.assertRaises(EnvironmentServiceError):self.call('fan.set',power='on')
        with self.assertRaises(EnvironmentServiceError):self.call('power.release',token='wrong')
        self.call('power.release',token=p['token'])
        self.assertEqual(self.core.controller.state.mode.value,'automatic');self.store.save.assert_not_called()

    def test_failed_host_power_action_hold_expires_to_prior_mode(self):
        self.call('mode.set',mode='automatic')
        self.call('power.prepare',action='POWEROFF_DEVICE')
        self.tick(33)
        self.assertIsNone(self.core._power_hold)
        self.assertEqual(self.core.controller.state.mode.value,'automatic')

    def test_power_prepare_failure_does_not_invent_ack(self):
        self.actuator.fail=True
        with self.assertRaises(EnvironmentServiceError):self.call('power.prepare',action='REBOOT_DEVICE')
        self.assertIsNone(self.call('health.get')['actuator_commands']['relay_commanded'])

    def test_unknown_power_action_never_acquires_a_hold(self):
        with self.assertRaises(EnvironmentServiceError):self.call('power.prepare',action='reboot; evil')
        self.assertIsNone(self.core._power_hold)

    def test_protocol_transports_typed_schedule_no_command_string(self):
        request=make_request('automation.add',{'kind':'temperature','delay_seconds':120})
        self.assertEqual(parse_request_bytes(encode_request(request)).operation,'automation.add')

if __name__=='__main__':unittest.main()
