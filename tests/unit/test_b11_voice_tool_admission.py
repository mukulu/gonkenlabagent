"""Runtime tool permission derives from current model/digest/context evidence."""
from __future__ import annotations
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from gonken_agent.llm.models import DEFAULT_MODEL, LEGACY_MODEL
from gonken_agent.voice_runtime import ConversationBrain, VoiceRuntimeError, _readiness_recoverable

class RuntimeToolAdmissionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name); prompt=self.root/'prompt.md';prompt.write_text('Local assistant.')
        self.client=Mock();self.client.model=DEFAULT_MODEL
        self.client.model_identity.return_value={'model':DEFAULT_MODEL,'digest':'a'*64}
        self.client.chat_text.return_value='ready'
        self.client.chat_message.return_value={'content':'Hello.', 'tool_calls':[]}
        config=SimpleNamespace(llm=SimpleNamespace(model=DEFAULT_MODEL,context_tokens=2048),
                 paths=SimpleNamespace(local_prompt=str(prompt)),
                 extensions=SimpleNamespace(environment=SimpleNamespace(socket_path=str(self.root/'control.sock'))))
        with patch('gonken_agent.voice_runtime.OllamaClient',return_value=self.client):
            self.brain=ConversationBrain(config)
        self.path=self.root/'roster.json';self.brain.roster_record_path=self.path
        self.record={'format':'gonken-ollama-roster-record-v2','status':'READY','context_tokens':2048,
          'models':[{'tag':DEFAULT_MODEL,'digest':'a'*64,'inference_status':'PASS','tool_call_smoke':'PASS',
           'stages':[{'stage':s,'status':'PASS'} for s in ('IDENTITY','INFERENCE','TOOLS','UNLOAD')]}]}
        self.save();self.stop=threading.Event()
    def save(self): self.path.write_text(json.dumps(self.record))
    def fail_probe(self):
        with self.assertRaises(VoiceRuntimeError) as exc:self.brain.probe(self.stop)
        self.assertEqual(exc.exception.code,'LOCAL_MODEL_TOOLS_NOT_QUALIFIED')
        self.client.chat_text.assert_not_called();self.client.chat_message.assert_not_called()
    def test_matching_default_probe_and_model_turn_pass(self):
        self.assertEqual(self.brain.probe(self.stop)['digest'],'a'*64)
        self.assertEqual(self.brain.reply('Tell me a short greeting.',self.stop),'Hello.')
        self.assertTrue(self.client.chat_message.call_args.kwargs['tools'])
        self.assertEqual(self.client.model_identity.call_count,2)
        self.assertEqual(self.brain.history[0]['content'],'Tell me a short greeting.')
    def test_tool_incompatible_selected_model_refused_before_inference(self):
        self.record['models'][0]['tool_call_smoke']='FAIL';self.save();self.fail_probe()
    def test_missing_or_invalid_record_refused(self):
        self.path.unlink();self.fail_probe()
        self.path.write_text('not JSON');self.fail_probe()
    def test_wrong_context_refused(self):
        self.record['context_tokens']=1024;self.save();self.fail_probe()
    def test_wrong_digest_refused(self):
        self.client.model_identity.return_value['digest']='b'*64;self.fail_probe()
    def test_failed_unload_refused_even_with_tool_pass(self):
        self.record['models'][0]['stages'][-1]['status']='FAIL';self.save();self.fail_probe()
    def test_no_catalog_only_admission(self):
        self.record['models'][0].pop('stages');self.save();self.fail_probe()
    def test_revocation_after_startup_is_checked_before_tools(self):
        self.brain.probe(self.stop);self.path.unlink()
        with self.assertRaises(VoiceRuntimeError):self.brain.reply('Tell me a greeting.',self.stop)
        self.client.chat_message.assert_not_called()
        self.assertEqual(self.brain.history,[])
    def test_live_digest_change_is_rejected_on_next_model_turn(self):
        self.brain.probe(self.stop)
        self.client.model_identity.return_value={'model':DEFAULT_MODEL,'digest':'c'*64}
        with self.assertRaises(VoiceRuntimeError):self.brain.reply('Tell me a greeting.',self.stop)
        self.client.chat_message.assert_not_called()
    def test_legacy_rollback_is_text_only_without_qualification(self):
        self.path.unlink();self.client.model=LEGACY_MODEL
        self.client.model_identity.return_value={'model':LEGACY_MODEL,'digest':'a'*64}
        self.brain.probe(self.stop)
        self.assertEqual(self.brain.reply('Tell me a greeting.',self.stop),'ready')
        self.client.chat_message.assert_not_called()
    def test_direct_clock_is_independent_of_model_record(self):
        self.path.unlink();self.brain.reply('What time is it?',self.stop)
        self.client.model_identity.assert_not_called();self.client.chat_message.assert_not_called()
    def test_unknown_model_or_identity_mismatch_refused(self):
        self.client.model_identity.return_value={'model':'unknown:1b','digest':'a'*64}
        with self.assertRaises(VoiceRuntimeError) as exc:self.brain.probe(self.stop)
        self.assertEqual(exc.exception.code,'LOCAL_MODEL_OUTSIDE_ROSTER')
        self.assertFalse(_readiness_recoverable(exc.exception.code))
        self.assertFalse(_readiness_recoverable('LOCAL_MODEL_TOOLS_NOT_QUALIFIED'))

if __name__=='__main__':unittest.main()
