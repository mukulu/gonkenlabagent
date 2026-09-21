"""Replay the B10 Pi tool-only failure without weakening required-model gates."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.unit.test_v09_model_roster_manager import manager, ROOT
from gonken_agent.llm.qualification import qualified_rows

class AlternateModelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.roster = manager.read_roster(ROOT / 'packaging/ollama-model-roster.toml')
        self.models = [{'name': s['tag'], 'digest': s['digest_prefix'] + 'a'*52,
                        'details': {'quantization_level': s['quantization']}}
                       for s in self.roster['models']]
        self.failed_tag = self.roster['models'][-1]['tag']
        self.resident = False
        self.semantic_failure = False

    def api(self, endpoint, path, body=None, **kw):
        if path == '/api/tags': return {'models': self.models}
        if path == '/api/ps': return {'models': self.models[:1] if self.resident else []}
        if path == '/api/chat':
            if body.get('tools') and body['model'] == self.failed_tag:
                if self.semantic_failure:
                    return {'model': body['model'], 'done': True, 'message': {'content': 'PRIVATE_CANARY'}}
                raise manager.om.OllamaError('OLLAMA_API_HTTP', 'PRIVATE_CANARY', 'inspect', 69,
                                             diagnostics={'http_status': 500, 'api_path': '/api/chat'})
            return {'model': body['model'], 'done': True,
                    'message': {'tool_calls': [{'function': {'name': 'readiness_probe', 'arguments': {}}}]}}
        raise AssertionError(path)

    def provision(self):
        with patch.object(manager.om, '_api', side_effect=self.api), patch.object(
                manager.om, 'smoke_model', return_value={'total_ns': 3}):
            return manager.provision(self.root, self.roster, 'http://127.0.0.1:11434', 2048, 'preseeded-offline')

    def test_alternate_http_error_is_reported_but_default_remains_qualified(self):
        result = self.provision()
        self.assertEqual(result['status'], 'READY')
        self.assertEqual(result['roster_capabilities_status'], 'DEGRADED')
        self.assertIsNone(result['current_failure'])
        alternate = result['models'][-1]
        self.assertEqual(alternate['capability_status'], 'TOOL_INCOMPATIBLE')
        self.assertEqual(alternate['stages'][-1]['stage'], 'UNLOAD')
        self.assertEqual(alternate['stages'][-1]['status'], 'PASS')
        self.assertEqual(result['optional_failures'][0]['stage'], 'TOOLS')
        self.assertNotIn('PRIVATE_CANARY', json.dumps(result))
        capabilities = qualified_rows(result, self.models, context_tokens=2048)
        self.assertFalse(capabilities[self.failed_tag]['tools'])
        self.assertTrue(capabilities[self.roster['default_model']]['tools'])
        with patch.object(manager.om, '_api', side_effect=self.api):
            self.assertEqual(manager.status(self.root, self.roster, 'http://127.0.0.1:11434')['status'], 'READY')

    def test_required_default_http_error_still_aborts(self):
        self.failed_tag = self.roster['default_model']
        with self.assertRaises(manager.om.OllamaError): self.provision()
        record = manager._read_json(manager._record_path(self.root))
        self.assertEqual(record['status'], 'FAIL')
        self.assertEqual(record['current_failure']['stage'], 'TOOLS')
        self.assertIsNone(manager._selection(self.root))

    def test_existing_selected_alternate_is_not_silently_downgraded(self):
        manager._write_selection(self.root, self.failed_tag, None)
        with self.assertRaises(manager.om.OllamaError): self.provision()
        self.assertEqual(manager._selection(self.root)['model'], self.failed_tag)

    def test_semantic_alternate_failure_has_the_same_explicit_disposition(self):
        self.semantic_failure = True
        record = self.provision()
        self.assertEqual(record['models'][-1]['capability_status'], 'TOOL_INCOMPATIBLE')
        self.assertFalse(qualified_rows(record, self.models)[self.failed_tag]['tools'])
        self.assertNotIn('PRIVATE_CANARY', json.dumps(record))

    def test_unload_failure_is_not_optional(self):
        self.resident = True
        with self.assertRaises(manager.RosterError): self.provision()
        self.assertEqual(manager._read_json(manager._record_path(self.root))['current_failure']['stage'], 'UNLOAD')

    def test_post_tool_failure_residency_still_aborts(self):
        original = self.api
        last_unloaded = []
        def api(e, p, b=None, **kw):
            if p == '/api/chat' and b.get('messages') == []:
                last_unloaded[:] = [b['model']]
            if p == '/api/ps' and last_unloaded == [self.failed_tag]:
                return {'models': [self.models[-1]]}
            return original(e, p, b, **kw)
        self.api = api
        with self.assertRaises(manager.RosterError): self.provision()
        record = manager._read_json(manager._record_path(self.root))
        self.assertEqual(record['current_failure']['stage'], 'UNLOAD')
        self.assertEqual(record['status'], 'FAIL')

    def test_network_or_auth_tool_failure_is_not_relabelled_compatibility(self):
        for code, status in [('OLLAMA_API_HTTP', 401), ('OLLAMA_API_TIMEOUT', None)]:
            original = self.api
            def api(e, p, b=None, **kw):
                if p == '/api/chat' and b.get('tools') and b['model'] == self.failed_tag:
                    raise manager.om.OllamaError(code, 'PRIVATE_CANARY', 'inspect', 69, diagnostics={'http_status': status})
                return original(e, p, b, **kw)
            self.api = api
            with self.assertRaises(manager.om.OllamaError): self.provision()
            self.api = original
            self.assertEqual(manager._read_json(manager._record_path(self.root))['status'], 'FAIL')

    def test_catalog_metadata_drift_is_rejected_before_network(self):
        manifest = self.root / 'roster.toml'
        manifest.write_text((ROOT / 'packaging/ollama-model-roster.toml').read_text().replace('default-low-latency', 'wrong-role'))
        with self.assertRaises(manager.RosterError) as error:manager.read_roster(manifest)
        self.assertEqual(error.exception.code, 'MODEL_ROSTER_CATALOG_DRIFT')
