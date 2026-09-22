from __future__ import annotations
import array
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock
import wave
from gonken_agent.audio.endpoint import complete_wake_utterance, SpeechEndpoint
from gonken_agent.voice_runtime import VoiceAppliance, VoiceCueCache, VoiceRuntimeError


def wav(path, data):
    with wave.open(str(path),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(data)

def pcm(seconds, value=0):return array.array('h',[value]*int(16000*seconds)).tobytes()

class InlineCacheTests(unittest.TestCase):
    def test_speech_resumption_invalidates_quiet_tail(self):
        d=SpeechEndpoint(16000);d.feed(pcm(.4,1000)+pcm(1));self.assertTrue(d.finished)
        self.assertFalse(d.feed(pcm(.3,1000)))
    def test_acoustic_tail_not_text_shape_decides_completeness(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'wake.wav';wav(p,pcm(.4,1000)+pcm(1))
            self.assertTrue(complete_wake_utterance(p))
            wav(p,pcm(.4,1000)+pcm(1)+pcm(.3,1000))
            self.assertFalse(complete_wake_utterance(p))
    def test_truncated_fast_command_not_executed_when_continuation_missing(self):
        a=VoiceAppliance.__new__(VoiceAppliance);a.brain=Mock();a.brain.complete_inline_command.return_value=True;a.capture_text=Mock(return_value='')
        self.assertEqual(a._question_after_wake('turn fan on'),'')
    def test_trailing_timer_qualifier_preserved(self):
        a=VoiceAppliance.__new__(VoiceAppliance);a.brain=Mock();a.brain.complete_inline_command.return_value=True;a.capture_text=Mock(return_value='after two minutes')
        self.assertEqual(a._question_after_wake('turn fan on'),'turn fan on after two minutes')
    def test_untrusted_or_missing_wave_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.wav';p.write_text('noise');self.assertFalse(complete_wake_utterance(p))
            p.unlink();self.assertFalse(complete_wake_utterance(p))
    def test_cache_reuses_only_hashed_governed_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);generated=path/'generated.wav';wav(generated,pcm(.2,100))
            calls=[]
            class Piper:
                voice=path/'voice.onnx'
                @contextmanager
                def synthesize(self,text,stop):calls.append(text);yield generated
            c=VoiceCueCache(path/'cache');p=Piper();stop=threading.Event()
            first=c.ensure(text='Yes?',piper=p,stop=stop);c.ensure(text='Yes?',piper=p,stop=stop)
            self.assertEqual(calls,['Yes?'])
            wav(first,pcm(.2,300));c.ensure(text='Yes?',piper=p,stop=stop)
            self.assertEqual(calls,['Yes?','Yes?'])
            self.assertEqual(first.stat().st_mode & 0o777,0o600)
            with self.assertRaises(VoiceRuntimeError):c.ensure(text='PRIVATE_CANARY_DO_NOT_STORE',piper=p,stop=stop)
            self.assertNotIn('PRIVATE_CANARY',c.manifest_path.read_text())
    def test_cache_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'link').symlink_to(root,target_is_directory=True)
            with self.assertRaises(VoiceRuntimeError):VoiceCueCache(root/'link').ensure(text='Yes?',piper=Mock(),stop=threading.Event())

if __name__=='__main__':unittest.main()
