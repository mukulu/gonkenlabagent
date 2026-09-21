from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import ollama_qualification_matrix as m
class ExperimentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.output=Path(self.tmp.name)/'result.json';self.calls=[]
 def api(self,endpoint,path,payload=None,**kw):
  self.calls.append((path,payload))
  if path=='/api/version':return {'version':'0.12.1'}
  if path=='/api/tags':return {'models':[{'name':'qwen3:0.6b','digest':'7df6b6e09427'+'a'*52,'details':{'quantization_level':'Q4_K_M'}}]}
  if path=='/api/ps':return {'models':[]}
  return {'model':'qwen3:0.6b','done':True,'message':{'content':'{"ready":true}'}}
 def run_case(self,**kw):return m.experiment('http://127.0.0.1:11434','qwen3:0.6b','schema',2048,128,self.output,maintenance_confirmed=True,api=kw.pop('api',self.api),**kw)
 def test_one_case_no_content_and_no_overwrite(self):
  r=self.run_case();self.assertEqual(r['status'],'PASS');self.assertNotIn('"ready":true',self.output.read_text());self.assertFalse(r['tool_execution'])
  with self.assertRaises(FileExistsError):self.run_case()
 def test_confirmation_required(self):
  with self.assertRaises(ValueError):m.experiment('http://127.0.0.1:11434','qwen3:0.6b','plain',2048,128,self.output,maintenance_confirmed=False,api=self.api)
  self.assertEqual(self.calls,[]);self.assertFalse(self.output.exists())
 def test_failure_preserved_with_cleanup_error(self):
  def broken(endpoint,path,payload=None,**kw):
   if path=='/api/chat':raise m.om.OllamaError('FIRST' if payload.get('messages') else 'CLEANUP','SECRET','fix')
   return self.api(endpoint,path,payload,**kw)
  r=self.run_case(api=broken);self.assertEqual(r['failure']['code'],'FIRST');self.assertEqual(r['cleanup_failure']['code'],'CLEANUP');self.assertNotIn('SECRET',self.output.read_text())
 def test_active_model_not_unloaded(self):
  def active(endpoint,path,payload=None,**kw):
   if path=='/api/ps':return {'models':[{'name':'active'}]}
   return self.api(endpoint,path,payload,**kw)
  r=self.run_case(api=active);self.assertEqual(r['status'],'FAIL');self.assertNotIn('/api/chat',[v[0] for v in self.calls])
 def test_untrusted_tool_never_accepted(self):
  r=m.response_summary({'model':'qwen3:0.6b','done':True,'message':{'tool_calls':[{'function':{'name':'reboot','arguments':{}}}]}},'tools','qwen3:0.6b')
  self.assertEqual(r['status'],'FAIL')
 def test_valid_tool_summary(self):
  r=m.response_summary({'model':'qwen3:0.6b','done':True,'message':{'tool_calls':[{'function':{'name':'readiness_probe','arguments':{}}}]}},'tools','qwen3:0.6b')
  self.assertEqual(r['status'],'PASS')
 def test_bounds_and_models(self):
  for ctx,out in ((0,10),(2048,3000),(True,10),(32769,10)):
   with self.assertRaises(ValueError):m.case_payload('qwen3:0.6b','plain',ctx,out)
  with self.assertRaises(ValueError):m.case_payload('evil','plain',2048,128)
 def test_all_shapes(self):
  for case in m.CASES:
   p=m.case_payload('qwen3:0.6b',case,2048,128)
   self.assertEqual(p['keep_alive'],0);self.assertFalse(p['think']);self.assertFalse(p['stream'])
 def test_resident_after_cleanup_fails(self):
  count=0
  def api(endpoint,path,payload=None,**kw):
   nonlocal count
   if path=='/api/ps':
    count+=1
    return {'models':[] if count==1 else [{'name':'qwen3:0.6b'}]}
   return self.api(endpoint,path,payload,**kw)
  self.assertEqual(self.run_case(api=api)['status'],'FAIL')
