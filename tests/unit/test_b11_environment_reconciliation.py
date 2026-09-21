from __future__ import annotations
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / 'scripts') not in sys.path: sys.path.insert(0, str(ROOT / 'scripts'))
import environment_current_reconcile as reconcile

class ExistingEnvironmentTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.release = self.root/'release';self.state=self.root/'state'
        self.release.mkdir(); self.state.mkdir()
        self.candidate='b'*40; self.current='a'*40; self.invocation='c'*32
        self.site=self.root/'etc/gonken-agent/config.toml';self.site.parent.mkdir(parents=True);self.site.write_text('real-config')
        self.health={'provenance': {'sensor_backend':'sht31','actuator_backend':'libgpiod'}}
        self.policy={'mode':'automatic','generation':10,'start_c':28.0,'stop_c':25.0,'minimum_on_seconds':60,'minimum_off_seconds':60,'schema_version':1}
        self.events=[]
        def track(name, value=None):
            def fn(*a, **kw): self.events.append(name);return value
            return fn
        bindings=[(reconcile.releases,'current_commit',lambda *a:self.current),
                  (reconcile.releases,'status',track('integrity')),
                  (reconcile.services,'validate_selected_profile',track('profile')),
                  (reconcile.services,'validate_installed',track('unit')),
                  (reconcile.services,'converge_commissioned',track('restart')),
                  (reconcile.services,'commissioned_status',track('status')),
                  (reconcile.services,'run_tool',track('systemctl',subprocess.CompletedProcess([],0,stdout=self.invocation+'\n'))),
                  (reconcile.readiness,'require_agent',lambda v:Path(v)),
                  (reconcile.readiness,'read_agent',track('parse',{'enabled':True,'hardware_toggled':False})),
                  (reconcile.readiness,'probe',track('health',{'health':self.health})),
                  (reconcile.policy,'converge',track('policy',self.policy))]
        for owner,name,fn in bindings:
            patcher=patch.object(owner,name,side_effect=fn);patcher.start();self.addCleanup(patcher.stop)
    def run_reconcile(self,check=False):
        return reconcile.reconcile(self.root,self.release,self.state,self.candidate,'automatic',self.root/'unit',self.root/'tmpfiles',check=check)
    def test_existing_runtime_restart_and_policy_precede_model_work(self):
        record=self.run_reconcile()
        self.assertEqual(record['status'],'READY_EXISTING_ENVIRONMENT')
        self.assertEqual(record['policy']['stop_c'],25.0)
        self.assertFalse(record['global_activation_changed'])
        self.assertLess(self.events.index('integrity'),self.events.index('restart'))
        self.assertLess(self.events.index('parse'),self.events.index('restart'))
        self.assertLess(self.events.index('restart'),self.events.index('health'))
        self.assertLess(self.events.index('health'),self.events.index('policy'))
        self.assertEqual(self.run_reconcile(check=True)['invocation_id'],self.invocation)
        self.assertEqual(self.events.count('restart'),1)
    def test_no_current_defers_without_service_or_hardware_touch(self):
        self.current=None
        self.assertEqual(self.run_reconcile()['status'],'DEFERRED_NO_CURRENT')
        self.assertNotIn('restart',self.events)
        self.assertEqual(self.run_reconcile(check=True)['status'],'DEFERRED_NO_CURRENT')
    def test_bad_current_integrity_defers_to_new_candidate_not_old_code(self):
        with patch.object(reconcile.releases,'status',side_effect=reconcile.releases.ReleaseError('BAD_CURRENT','PRIVATE','repair',75)):
            r=self.run_reconcile()
        self.assertEqual(r['status'],'DEGRADED_EXISTING_ENVIRONMENT');self.assertNotIn('restart',self.events)
        self.assertNotIn('PRIVATE',json.dumps(r))
    def test_failed_or_simulated_daemon_is_not_claimed_ready(self):
        with patch.object(reconcile.readiness,'probe',side_effect=reconcile.readiness.ReadinessError('ENVIRONMENT_NOT_READY','private','inspect')):
            r=self.run_reconcile()
        self.assertEqual(r['status'],'DEGRADED_EXISTING_ENVIRONMENT');self.assertNotIn('policy',self.events)
        self.assertNotIn('invocation_id',r)
    def test_config_drift_invalidates_restart_receipt(self):
        self.run_reconcile();self.site.write_text('different-real-config')
        with self.assertRaisesRegex(ValueError,'stale'):self.run_reconcile(check=True)
    def test_new_service_invocation_invalidates_receipt(self):
        self.run_reconcile()
        with patch.object(reconcile,'_invocation',return_value='d'*32):
            with self.assertRaisesRegex(ValueError,'service_restarted'):self.run_reconcile(check=True)
    def test_mid_restart_config_change_is_not_ready(self):
        def restart(*a,**kw):self.site.write_text('changed')
        with patch.object(reconcile.services,'converge_commissioned',side_effect=restart):r=self.run_reconcile()
        self.assertEqual(r['status'],'DEGRADED_EXISTING_ENVIRONMENT')
    def test_readonly_parse_failure_prevents_restart(self):
        with patch.object(reconcile.readiness,'read_agent',return_value={'enabled':True,'hardware_toggled':True}):r=self.run_reconcile()
        self.assertEqual(r['status'],'DEGRADED_EXISTING_ENVIRONMENT');self.assertNotIn('restart',self.events)
    def test_symlink_receipt_refused(self):
        (self.state/'environment-current-reconciliation.json').symlink_to(self.root/'victim')
        with self.assertRaises(ValueError):self.run_reconcile()
        self.assertFalse((self.root/'victim').exists());self.assertNotIn('restart',self.events)
    def test_unknown_profile_never_kills_external_gpio_owner(self):
        source=(ROOT/'scripts/environment_current_reconcile.py').read_text()
        self.assertNotIn('pkill',source);self.assertNotIn('gpioset',source)
        with patch.object(reconcile.services,'validate_selected_profile',side_effect=reconcile.services.EnvironmentServiceError('INVALID_PROFILE','private','inspect',65)):
            self.assertEqual(self.run_reconcile()['status'],'DEGRADED_EXISTING_ENVIRONMENT')
        self.assertNotIn('restart',self.events)

if __name__=='__main__':unittest.main()
