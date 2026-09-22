"""Real local IPC/CLI processes; injected sensor/relay and no logind execution."""
from __future__ import annotations
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock
from gonken_agent.config import load_config
from gonken_agent.environment.client import EnvironmentClient, EnvironmentClientError
from gonken_agent.environment.server import EnvironmentUnixServer
from gonken_agent.environment.service import EnvironmentServiceCore, ServiceIdentity
from gonken_agent.environment.domain import SensorReading
from gonken_agent.operational import OperationalCommands, NotificationAnnouncer
from gonken_agent.power import PowerSession, execute_confirmed

ROOT=Path(__file__).resolve().parents[2]
class Hardware:
    def __init__(self):self.writes=[]
    def set_power(self,power):self.writes.append(power.value)
    def safe_off(self):self.writes.append('off')

class OperationalTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.now=0.;self.temperature=25.;self.hardware=Hardware()
        self.core=EnvironmentServiceCore.with_defaults(now=lambda:self.now,fan_actuator=self.hardware,
            sensor_read=lambda **kwargs:SensorReading(self.temperature,50.,self.now,source_backend='sht31',crc_valid=self.temperature is not None))
        self.core.identity=ServiceIdentity(sensor_backend='sht31',actuator_backend='libgpiod',evidence_mode='HOST_FAKE')
        for t in (0,1,2):self.tick(t)
        self.socket=self.root/'control.sock';self.server=EnvironmentUnixServer(self.socket,self.core,socket_mode=0o600)
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.01),daemon=True);self.thread.start()
        self.addCleanup(self.close)
        self.client=EnvironmentClient(self.socket,timeout_seconds=1)
        self.ops=OperationalCommands(lambda:self.client)
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2)
        self.assertFalse(self.thread.is_alive())
    def tick(self,at):self.now=float(at);self.core.poll_once()
    def cli(self,*argv):
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(ROOT/'src')+':'+str(ROOT)}
        return subprocess.run([sys.executable,'-m','gonken_agent','env','--socket',str(self.socket),*argv],capture_output=True,text=True,env=env,timeout=10)
    def test_delayed_voice_run_executes_only_owner_after_due_time(self):
        self.assertIn('Scheduled',self.ops.handle('turn the fan on in two minutes for three minutes'))
        self.tick(121);self.assertEqual(self.client.health()['state']['fan_power'],'off')
        self.tick(122);self.assertEqual(self.client.health()['state']['fan_power'],'on')
        self.tick(302);health=self.client.health();self.assertEqual(health['state']['fan_power'],'off')
        self.assertFalse(health['physical_evidence']);self.assertEqual(self.client.automation_list()['jobs'],[])
    def test_cli_add_list_cancel_are_real_ipc(self):
        created=self.cli('schedule','add','temperature','--after','120','--every','120','--json')
        self.assertEqual(created.returncode,0,created.stderr);job=json.loads(created.stdout)['job']
        listed=self.cli('schedule','list','--json');self.assertEqual(json.loads(listed.stdout)['jobs'][0]['id'],job['id'])
        cancelled=self.cli('schedule','cancel',job['id'],'--json');self.assertEqual(cancelled.returncode,0,cancelled.stderr)
        self.assertEqual(self.client.automation_list()['jobs'],[])
    def test_cli_invalid_boolean_numeric_never_adds_job(self):
        for value in ('nan','-1','inf'):
            with self.subTest(value=value):
                result=self.cli('schedule','add','fan_on','--after',value,'--json')
                self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.client.automation_list()['jobs'],[])
    def test_numeric_notice_then_spoken_ack_changes_baseline(self):
        self.ops.handle('tell me the temperature after two minutes');self.tick(122)
        a=NotificationAnnouncer(lambda:self.client,clock=lambda:self.now)
        self.assertIn('25.0',a.pending());self.assertIsNone(self.core.automation.last_announced_temperature)
        a.spoken();self.assertEqual(self.core.automation.last_announced_temperature,25.)
        self.assertEqual(self.client.notifications()['notifications'],[])
    def test_direct_query_baseline_changes_only_after_spoken(self):
        self.assertIn('25.0',self.ops.handle('what is the room temperature'))
        self.assertIsNone(self.core.automation.last_announced_temperature)
        self.ops.after_spoken();self.assertEqual(self.core.automation.last_announced_temperature,25.)
    def test_bad_sensor_cancels_pending_fan_job_without_recovery_replay(self):
        self.ops.handle('start the fan after two minutes');self.temperature=None;self.tick(10)
        self.temperature=25.
        for t in (122,123,124):self.tick(t)
        self.assertEqual(self.client.automation_list()['jobs'],[])
        self.assertEqual(self.client.health()['state']['fan_power'],'off')
    def test_confirmed_power_prepares_same_daemon_and_audit_before_injected_logind(self):
        session=PowerSession(enabled=True,clock=lambda:self.now)
        session.handle('restart the Raspberry Pi');session.handle('confirm restart')
        audit=self.root/'power';seen=[]
        def execute(action):
            seen.append(action);self.assertEqual(self.client.health()['state']['fan_power'],'off')
            self.assertTrue(self.client.health()['automation']['power_pending'])
            self.assertEqual(json.loads((audit/'last-action.json').read_text())['status'],'AUTHORIZED_SAFE_OFF')
        result=execute_confirmed(session.consume(),client_factory=lambda:self.client,environment_required=True,real_environment=True,audit_dir=audit,execute=execute,clock=lambda:self.now)
        self.assertEqual(result['status'],'REQUESTED');self.assertEqual(seen,['REBOOT_DEVICE'])
        self.tick(33);self.assertFalse(self.client.health()['automation']['power_pending'])
    def test_manual_action_cancels_pending_fan_timer_but_not_sensor_timer(self):
        self.ops.handle('start the fan after two minutes');self.ops.handle('tell me the humidity after two minutes')
        self.ops.handle('turn the fan off')
        self.assertEqual([j['kind'] for j in self.client.automation_list()['jobs']],['humidity'])

if __name__=='__main__': unittest.main()
