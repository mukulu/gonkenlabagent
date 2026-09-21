from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.unit.test_v09_model_roster_manager import manager, ROOT
from gonken_agent.llm.qualification import qualified_rows
class RosterProgressTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.roster=manager.read_roster(ROOT/'packaging/ollama-model-roster.toml')
  self.models=[{'name':s['tag'],'digest':s['digest_prefix']+'a'*52,'details':{'quantization_level':s['quantization']}} for s in self.roster['models']]
 def api(self, endpoint, path, payload=None, **kwargs):
  if path=='/api/tags':return {'models':self.models}
  if path=='/api/ps':return {'models':[]}
  if path=='/api/chat':return {'model':payload['model'],'done':True,'message':{'tool_calls':[{'function':{'name':'readiness_probe','arguments':{}}}]}}
  raise AssertionError(path)
 def run_provision(self, smoke=None):
  with patch.object(manager.om,'_api',side_effect=self.api),patch.object(manager.om,'smoke_model',side_effect=smoke or (lambda *a:{'total_ns':5})):
   return manager.provision(self.root,self.roster,'http://127.0.0.1:11434',2048,'preseeded-offline')
 def read(self):return json.loads(manager._record_path(self.root).read_text())
 def test_later_failure_preserves_completed_model_and_stage(self):
  def smoke(e,m,c):
   if m==self.roster['models'][1]['tag']:raise manager.om.OllamaError('OLLAMA_API_HTTP','RAW_PRIVATE_MESSAGE','local',69,diagnostics={'http_status':500})
   return {'total_ns':7}
  with self.assertRaises(manager.om.OllamaError):self.run_provision(smoke)
  r=self.read();self.assertEqual(r['status'],'FAIL');self.assertEqual(r['models'][0]['tool_call_smoke'],'PASS');self.assertEqual(r['current_failure']['stage'],'INFERENCE');self.assertEqual(r['current_failure']['model'],self.roster['models'][1]['tag']);self.assertNotIn('RAW_PRIVATE_MESSAGE',json.dumps(r));self.assertEqual(r['models'][1]['stages'][-1]['status'],'PASS')
 def test_unload_failure_does_not_overwrite_original(self):
  original=self.api
  def api(e,p,b=None,**kw):
   if p=='/api/ps':return {'models':[{'name':'still-loaded'}]}
   return original(e,p,b,**kw)
  self.api=api
  def smoke(*args):raise manager.om.OllamaError('FIRST_ERROR','private','fix',69)
  with self.assertRaises(manager.om.OllamaError) as caught:self.run_provision(smoke)
  self.assertEqual(caught.exception.code,'FIRST_ERROR');self.assertEqual(self.read()['current_failure']['code'],'FIRST_ERROR')
 def test_unload_unconfirmed_prevents_ready(self):
  original=self.api
  self.api=lambda e,p,b=None,**kw:{'models':[{'name':'still-loaded'}]} if p=='/api/ps' else original(e,p,b,**kw)
  with self.assertRaises(manager.RosterError):self.run_provision()
  self.assertEqual(self.read()['status'],'FAIL')
 def test_record_bound_to_model_digest(self):
  r=self.run_provision();self.assertEqual(len(qualified_rows(r,self.models,context_tokens=2048)),3)
  self.models[0]['digest']=self.models[0]['digest'][:12]+'b'*52
  self.assertNotIn(self.models[0]['name'],qualified_rows(r,self.models))
 def test_context_drift_rejected(self):self.assertEqual(qualified_rows(self.run_provision(),self.models,context_tokens=4096),{})
 def test_tool_arguments_must_be_empty(self):
  original=self.api
  def api(e,p,b=None,**kw):
   value=original(e,p,b,**kw)
   if p=='/api/chat':value['message']['tool_calls'][0]['function']['arguments']={'shell':'unsafe'}
   return value
  self.api=api
  with self.assertRaises(manager.RosterError):self.run_provision()
  self.assertEqual(self.read()['current_failure']['stage'],'ADMISSION')
 def test_old_attempt_ready_invalidated_before_network_failure(self):
  self.run_provision()
  with patch.object(manager.om,'_api',side_effect=manager.om.OllamaError('OFFLINE','private','fix',69)):
   with self.assertRaises(manager.om.OllamaError):manager.provision(self.root,self.roster,'http://127.0.0.1:11434',2048,'online')
  self.assertEqual(self.read()['status'],'FAIL');self.assertEqual(self.read()['current_failure']['stage'],'INVENTORY')
 def test_admin_ready_requires_current_qualified_selected_model(self):
  from gonken_agent.llm import admin
  from gonken_agent.config import load_config
  r=self.run_provision()
  cfg=load_config(site_path=None).config
  r['context_tokens']=cfg.llm.context_tokens
  with patch.object(admin,'_bounded_json',return_value=r),patch.object(admin,'_inventory',return_value=self.models),patch.object(admin,'_loaded_models',return_value=[]),patch.object(admin,'selection_status',return_value={'model':self.roster['default_model'],'governed_roster_active':True}):
   self.assertEqual(admin.status(cfg)['status'],'READY')
   r['models'][0]['stages'][2]['status']='FAIL'
   self.assertEqual(admin.status(cfg)['status'],'DEGRADED')
 def test_roster_fingerprint_drift_rejects(self):
  self.run_provision();self.roster['verified_at']='changed'
  with patch.object(manager.om,'_api',side_effect=self.api):
   with self.assertRaises(manager.RosterError) as error:manager.status(self.root,self.roster,'http://127.0.0.1:11434')
  self.assertEqual(error.exception.code,'MODEL_ROSTER_RECORD_STALE')
