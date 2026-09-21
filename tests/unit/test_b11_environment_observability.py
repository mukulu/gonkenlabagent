from __future__ import annotations
import copy
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from gonken_agent import cli
from gonken_agent.environment.daemon import build_environment_service_core
from gonken_agent.environment.domain import FanPower, SensorReading
from gonken_agent.environment.protocol import make_request
from gonken_agent.environment.actuators import GpiodRelayFanActuator
from gonken_agent.environment.journal import EnvironmentEventJournal, sanitized_event
from tests.unit.test_v09_environment_hardware_adapters import FakeGpiod
from tests.unit.test_v09_environment_daemon_activation import _enabled_env_config, ManualClock

class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.clock=ManualClock();self.temperature=29.0;self.events=[]
        self.module=FakeGpiod(chips={'/dev/gpiochip0':[None]*23+['GPIO23']},labels={'/dev/gpiochip0':'pinctrl-rp1'})
        self.relay=GpiodRelayFanActuator(logical_bcm=23,active_high=True,gpiod_module=self.module,chip_paths=['/dev/gpiochip0'])
        class Sensor:
            def read(_, *, now_monotonic):return SensorReading(self.temperature,50.0,now_monotonic,source_backend='sht31')
            def close(_):pass
        self.core=build_environment_service_core(_enabled_env_config(temp.name),now=self.clock,
            sensor_factory=lambda cfg:Sensor(),actuator_factory=lambda cfg:self.relay,event_sink=self.events.append)
        self.addCleanup(self.core.shutdown_safe_off)
    def health(self):return self.core.handle(make_request('health.get'))
    def start_automatic(self):
        self.core.handle(make_request('policy.update',{'mode':'automatic','stop_c':25.,'expected_generation':1}))
        for t in (0.,2.,4.,61.):self.clock.set(t);self.core.poll_once()
    def test_threshold_events_are_discrete_acknowledged_and_real_backend_labelled(self):
        self.start_automatic();self.assertEqual(self.health()['actuator_commands']['relay_commanded'],'on')
        self.temperature=24.9
        for t in (63.,65.,122.):self.clock.set(t);self.core.poll_once()
        on=[x for x in self.events if x['reason']=='AUTO_START_THRESHOLD']
        off=[x for x in self.events if x['reason']=='AUTO_STOP_THRESHOLD']
        self.assertEqual(len(on),1);self.assertEqual(len(off),1)
        self.assertEqual(on[0]['relay_commanded'],'on');self.assertEqual(off[0]['relay_commanded'],'off')
        self.assertEqual(on[0]['gpio'],'GPIO23');self.assertEqual(on[0]['gpio_consumer'],'gonken-environment')
        self.assertEqual(on[0]['start_c'],28.);self.assertEqual(off[0]['stop_c'],25.)
        self.assertFalse(on[0]['fan_motion_observed']);self.assertFalse(on[0]['actuator_simulated'])
        count=len(self.events)
        for t in (124.,126.,128.):self.clock.set(t);self.core.poll_once()
        self.assertEqual(count,len(self.events))
    def test_health_snapshot_and_status_age_but_never_change_control_or_gpio(self):
        self.start_automatic();before=self.core.controller.state;writes=self.relay.command_diagnostics()['gpio_write_count']
        self.clock.set(90.)
        for op in ('health.get','status.get','state.snapshot.get'):
            value=self.core.handle(make_request(op))
            self.assertEqual(value['state']['sensor_quality'],'stale')
            self.assertEqual(value['state']['fan_power'],'on')
        self.assertEqual(self.core.controller.state,before)
        self.assertEqual(self.relay.command_diagnostics()['gpio_write_count'],writes)
        self.assertEqual(self.health()['overall'],'DEGRADED')
    def test_failed_write_is_not_controller_success_or_safe_off_proof(self):
        self.start_automatic();self.module.last_request.fail_set=True
        with self.assertRaises(Exception):self.core.handle(make_request('fan.set',{'power':'off'}))
        health=self.health();self.assertEqual(health['overall'],'DEGRADED')
        self.assertEqual(health['state']['fan_power'],'off')
        self.assertIsNone(health['actuator_commands']['relay_commanded'])
        self.assertGreater(health['actuator_commands']['actuator_write_errors'],0)
        event=self.events[-1];self.assertEqual(event['code'],'ENV_ACTUATOR_WRITE_FAILED')
        self.assertEqual(event['safe_off_result'],'FAILED');self.assertIsNone(event['relay_commanded'])
        count=len(self.events)
        for t in (63.,65.,67.):self.clock.set(t);self.core.poll_once()
        self.assertEqual(len(self.events),count)
        self.module.last_request.fail_set=False;self.clock.set(69.);self.core.poll_once()
        self.assertEqual(self.health()['actuator_commands']['relay_commanded'],'off')
        self.assertEqual(self.events[-1]['write_result'],'SUCCESS')
    def test_broken_logging_does_not_prevent_actuation(self):
        def broken(event):raise OSError('unavailable')
        self.core._event_sink=broken
        self.start_automatic()
        self.assertEqual(self.relay.command_diagnostics()['relay_commanded'],'on')
        self.assertGreater(self.health()['actuator_commands']['event_delivery_errors'],0)
    def test_changes_only_ignores_sensor_jitter_and_poll_counts(self):
        self.start_automatic();base=self.core.handle(make_request('state.snapshot.get'))
        other=copy.deepcopy(base);other['state']['last_reading']['temperature_c']=32.938281
        other['state']['last_reading']['relative_humidity_pct']=72.4141281;other['polling']['poll_count']+=500
        other['polling']['poll_error_count']+=10
        self.assertEqual(cli._environment_watch_signature(base),cli._environment_watch_signature(other))
        other['actuator_commands']['relay_commanded']='off'
        self.assertNotEqual(cli._environment_watch_signature(base),cli._environment_watch_signature(other))
    def test_changes_only_emits_new_error_or_configuration(self):
        self.start_automatic();base=self.core.handle(make_request('state.snapshot.get'))
        for section,key,value in [('polling','last_poll_error_code','SENSOR_UNAVAILABLE'),('provenance','configuration_sha256','changed')]:
            other=copy.deepcopy(base);other[section][key]=value
            self.assertNotEqual(cli._environment_watch_signature(base),cli._environment_watch_signature(other))

class EventJournalTests(unittest.TestCase):
    def test_allowlist_and_single_line_json(self):
        stream=io.StringIO()
        with EnvironmentEventJournal(stream) as journal:
            journal({'code':'ENV_ACTUATOR_TRANSITION','backend':'libgpiod','reason':'AUTO_START_THRESHOLD',
                     'requested':'on','relay_commanded':'on','raw_transcript':'PRIVATE_CANARY',
                     'password':'SECRET_CANARY','physical_evidence':True})
        text=stream.getvalue();self.assertNotIn('CANARY',text)
        event=json.loads(text);self.assertEqual(event['relay_commanded'],'on');self.assertFalse(event['physical_evidence'])
        self.assertEqual(text.count('\n'),1)
    def test_invalid_unbounded_or_nonfinite_tokens_rejected(self):
        for fields in ({'reason':'private text\nsecret'}, {'start_c':float('nan')},{'mode':{'password':'SECRET'}}, {'requested':'yes'}, {'gpio_claimed':'true'}):
            with self.assertRaises(ValueError):sanitized_event({'code':'ENV_ACTUATOR_TRANSITION',**fields})
    def test_blocked_journal_is_bounded_and_nonblocking_for_producer(self):
        entered=threading.Event();release=threading.Event()
        class BlockedStream:
            def write(self,text):entered.set();release.wait(3)
            def flush(self):pass
        journal=EnvironmentEventJournal(BlockedStream(),capacity=2)
        try:
            event={'code':'ENV_ACTUATOR_TRANSITION','requested':'off'}
            journal(event);self.assertTrue(entered.wait(1))
            for _ in range(100):journal(event)
            self.assertLessEqual(journal.queue.qsize(),2);self.assertGreater(journal.dropped_events,0)
        finally:release.set();journal.close()
    def test_failed_output_does_not_throw_into_control(self):
        class FailedStream:
            def write(self,text):raise OSError('PRIVATE')
            def flush(self):pass
        journal=EnvironmentEventJournal(FailedStream())
        journal({'code':'ENV_ACTUATOR_TRANSITION'});journal.close()
        self.assertGreater(journal.dropped_events,0)

if __name__=='__main__':unittest.main()
