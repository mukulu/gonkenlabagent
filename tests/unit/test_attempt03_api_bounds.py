from __future__ import annotations
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('api_bounds_om',ROOT/'scripts/ollama_manager.py')
om=importlib.util.module_from_spec(s);s.loader.exec_module(om)
class ApiBoundsTests(unittest.TestCase):
 def test_success_bounded_object(self):
  with patch.object(om,'_open_api',return_value=io.BytesIO(b'{"version":"1.2.3"}')) as opened:
   self.assertEqual(om._api('http://localhost:11434','/api/version')['version'],'1.2.3')
  self.assertEqual(opened.call_args.args[0].full_url,'http://127.0.0.1:11434/api/version')
 def test_oversize_rejected(self):
  with patch.object(om,'_open_api',return_value=io.BytesIO(b'x'*(om.API_RESPONSE_LIMIT+1))):
   with self.assertRaises(om.OllamaError) as error:om._api('http://127.0.0.1:11434','/api/tags')
  self.assertEqual(error.exception.code,'OLLAMA_API_RESPONSE_TOO_LARGE')
 def test_error_body_in_200_is_error(self):
  with patch.object(om,'_open_api',return_value=io.BytesIO(b'{"error":"SECRET EOF"}')):
   with self.assertRaises(om.OllamaError) as error:om._api('http://127.0.0.1:11434','/api/chat',{})
  self.assertEqual(error.exception.code,'OLLAMA_API_ERROR');self.assertNotIn('SECRET',str(error.exception))
 def test_scalar_and_bad_unicode_rejected(self):
  for body in (b'[]',b'"x"',b'\xff'):
   with self.subTest(body=body),patch.object(om,'_open_api',return_value=io.BytesIO(body)):
    with self.assertRaises(om.OllamaError):om._api('http://127.0.0.1:11434','/api/ps')
 def test_invalid_origins_rejected_before_network(self):
  for origin in ('http://external:12','http://127.0.0.1:0','http://127.0.0.1:99999','http://127.0.0.1:abc','http://127.0.0.1:12/x'):
   with self.subTest(origin=origin),patch.object(om,'_open_api') as opened:
    with self.assertRaises(om.OllamaError):om._api(origin,'/api/version')
    opened.assert_not_called()
 def test_redirect_refused(self):
  req=om.urllib.request.Request('http://127.0.0.1:11434/api/version')
  with self.assertRaises(urllib.error.HTTPError):
   om._NoApiRedirect().redirect_request(req,io.BytesIO(),302,'redirect',{},'http://external/')
 def test_proxy_disabled(self):
  with patch.object(om.urllib.request,'build_opener') as build:
   om._open_api(om.urllib.request.Request('http://127.0.0.1:11434/api/version'),1)
  self.assertEqual(build.call_args.args[0].proxies,{})
 def test_readiness_uses_short_call_budget(self):
  with patch.object(om,'_api',return_value={'version':'1.2.3'}) as api:
   om.wait_ready('http://127.0.0.1:11434','1.2.3')
  self.assertLessEqual(api.call_args.kwargs['timeout'],2)
 def test_readiness_deadline_stops_retries(self):
  with patch.object(om.time,'monotonic',side_effect=[0,0,61,62]),patch.object(om,'_api',return_value={'version':'bad'}) as api:
   with self.assertRaises(om.OllamaError) as error:om.wait_ready('http://127.0.0.1:11434','1.2.3')
  self.assertEqual(error.exception.code,'OLLAMA_READINESS');self.assertEqual(api.call_count,1)
 def test_invalid_path_and_stream_fail(self):
  for path,stream in (('/else',False),('/api/chat',True)):
   with self.assertRaises(om.OllamaError):om._api('http://127.0.0.1:11434',path,stream=stream)
