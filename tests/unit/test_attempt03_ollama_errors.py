from __future__ import annotations
import importlib.util
import io
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
from gonken_agent.llm.errors import http_metadata, BODY_LIMIT
from gonken_agent.llm.ollama import OllamaClient, OllamaError
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('a03_om',ROOT/'scripts/ollama_manager.py'); om=importlib.util.module_from_spec(s); s.loader.exec_module(om)
class ErrorTests(unittest.TestCase):
 def test_preserves_shape_but_never_content(self):
  data=http_metadata(500,'/api/chat',{'model':'qwen3:0.6b','messages':[{'content':'PRIVATE_SENTENCE'}], 'format':{'type':'object'},'tools':[{}],'options':{'num_ctx':2048,'num_predict':32}},b'{"error":"EOF PRIVATE_SENTENCE password=NEVER_EXPORT"}')
  self.assertEqual(data['http_status'],500); self.assertEqual(data['server_error_class'],'EOF'); self.assertEqual(data['format_kind'],'schema')
  self.assertNotIn('PRIVATE_SENTENCE',json.dumps(data)); self.assertNotIn('NEVER_EXPORT',json.dumps(data)); self.assertFalse(data['root_cause_confirmed'])
 def test_oversize_bounded(self):
  data=http_metadata(500,'/api/chat',{},b'x'*(BODY_LIMIT+1)); self.assertTrue(data['body_truncated']); self.assertEqual(data['body_bytes_examined'],BODY_LIMIT)
 def test_unknown_body_not_invented(self): self.assertEqual(http_metadata(500,'/api/chat',{},b'not json')['server_error_class'],'UNCLASSIFIED')
 def test_installer_error_metadata_and_privacy(self):
  e=urllib.error.HTTPError('http://127.0.0.1/api/chat',500,'server',{},io.BytesIO(b'{"error":"out of memory token=SECRET_CANARY"}'))
  with patch.object(om,'_open_api',side_effect=e):
   with self.assertRaises(om.OllamaError) as raised:om._api('http://127.0.0.1:11434','/api/chat',{'model':'qwen3:0.6b'})
  self.assertEqual(raised.exception.diagnostics['server_error_class'],'OUT_OF_MEMORY'); self.assertNotIn('SECRET_CANARY',str(raised.exception))
 def test_runtime_error_metadata(self):
  c=OllamaClient(SimpleNamespace(base_url='http://127.0.0.1:11434',model='qwen3:0.6b'))
  response=MagicMock();response.status=500;response.read.return_value=b'{"error":"EOF SECRET_CANARY"}'
  conn=MagicMock();conn.getresponse.return_value=response
  with patch.object(c,'_connection',return_value=conn):
   with self.assertRaises(OllamaError) as raised:c.request('POST','/api/chat',{'model':'qwen3:0.6b'},threading.Event())
  self.assertEqual(raised.exception.diagnostics['server_error_class'],'EOF'); self.assertNotIn('SECRET_CANARY',str(raised.exception)); response.close.assert_called_once()
 def test_error_object_in_http_success_not_ready(self):
  c=OllamaClient(SimpleNamespace(base_url='http://127.0.0.1:11434',model='qwen3:0.6b'))
  response=MagicMock();response.status=200;response.read.return_value=b'{"error":"EOF"}'
  conn=MagicMock();conn.getresponse.return_value=response
  with patch.object(c,'_connection',return_value=conn):
   with self.assertRaisesRegex(OllamaError,'OLLAMA_API_ERROR'): c.request('POST','/api/chat',{},threading.Event())
