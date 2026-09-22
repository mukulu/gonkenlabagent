from __future__ import annotations
from array import array
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
import wave

from gonken_agent.audio.keyword_native import KeywordHit, NativeKeywordDetector, KeywordError
from gonken_agent.audio.wake_stream import UtteranceSegmenter, StreamingWakePipeline, StreamingWakeWindow, speech_after_keyword
from gonken_agent.audio.speech import validate_wav
from gonken_agent.config import load_config, ConfigError, _validate_values
from gonken_agent.voice_runtime import VoiceAppliance, VoiceRuntimeError, _wake_remainder


def pcm(ms, value=0): return array('h', [value] * (16*ms)).tobytes()
def feed(segmenter, data):
    result=None
    for pos in range(0,len(data),2560):
        result=segmenter.feed(data[pos:pos+2560])
        if result:return result
    return result


class SegmenterTests(unittest.TestCase):
    def test_idle_silence_is_bounded_and_never_a_whisper_window(self):
        s=UtteranceSegmenter()
        for _ in range(2500):self.assertIsNone(s.feed(pcm(80)))
        self.assertFalse(s.active);self.assertEqual(len(s.data),0);self.assertLessEqual(len(s.pre),12800)
    def test_full_inline_sentence_not_cut_at_old_two_second_boundary(self):
        s=UtteranceSegmenter();data=pcm(400)+pcm(640,2000)+pcm(240)+pcm(2560,1500)+pcm(960)
        u=feed(s,data);self.assertIsNotNone(u);self.assertTrue(u.complete)
        self.assertGreater(len(u.pcm),3*32000);self.assertIn(pcm(2560,1500),u.pcm)
    def test_short_pause_preserves_delayed_action_qualifier(self):
        s=UtteranceSegmenter();data=pcm(320)+pcm(1600,1000)+pcm(640)+pcm(800,1500)+pcm(960)
        u=feed(s,data);self.assertTrue(u.complete);self.assertIn(pcm(640)+pcm(800,1500),u.pcm)
    def test_never_execute_a_maximum_length_partial_sentence(self):
        s=UtteranceSegmenter(max_seconds=2);u=feed(s,pcm(2400,1000));self.assertFalse(u.complete);self.assertLessEqual(len(u.pcm),64000)
    def test_noisy_impulse_does_not_create_a_command(self):
        s=UtteranceSegmenter();self.assertIsNone(feed(s,pcm(80,1000)+pcm(960)));self.assertFalse(s.active)
    def test_keyword_only_vs_inline_activity(self):
        s=UtteranceSegmenter();u=feed(s,pcm(400)+pcm(640,1000)+pcm(960));hit=KeywordHit(6400,16640)
        self.assertFalse(speech_after_keyword(u,hit,250))
        s=UtteranceSegmenter();u=feed(s,pcm(400)+pcm(640,1000)+pcm(240)+pcm(640,1500)+pcm(960))
        self.assertTrue(speech_after_keyword(u,hit,250))
    def test_invalid_bounds_and_partial_frames_rejected(self):
        for kwargs in ({'threshold':0},{'silence_ms':0},{'max_seconds':0}):
            with self.assertRaises(ValueError):UtteranceSegmenter(**kwargs)
        with self.assertRaises(ValueError):UtteranceSegmenter().feed(b'bad')
    def test_command_numbers_are_not_destroyed_by_wake_stripping(self):
        self.assertEqual(_wake_remainder('GonKen, set the threshold to -2.5 degrees!', 'GonKen'),'set the threshold to -2.5 degrees')
        self.assertEqual(_wake_remainder('GonKen turn the fan on after 1.5 minutes', 'GonKen'),'turn the fan on after 1.5 minutes')


class PipelineTests(unittest.TestCase):
    def test_one_stream_to_full_wav_and_close_before_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            data=pcm(320)+pcm(640,1000)+pcm(160)+pcm(2400,2000)+pcm(960)
            class Stream:
                closed=False
                def __init__(self):self.pos=0
                def read_frame(self,**kw):
                    p=self.pos;self.pos+=2560;return data[p:p+2560]
                def close(self):self.closed=True
            stream=Stream();decoder=Mock();decoder.feed.return_value=None
            pipe=StreamingWakePipeline(lambda **kw:stream,decoder,Path(temp));pipe.start()
            event=pipe.next_window(timeout=2)
            self.assertIsNotNone(event);self.assertTrue(stream.closed);self.assertTrue(event.utterance_complete)
            self.assertFalse(event.native_keyword);self.assertTrue(event.command_activity)
            self.assertEqual(event.path.stat().st_mode & 0o777,0o600)
            with wave.open(str(event.path)) as wav:self.assertIn(pcm(2400,2000),wav.readframes(wav.getnframes()))
            self.assertEqual(pipe.dropped_windows,0);self.assertEqual(pipe.captured_windows,1)
            event.path.unlink();pipe.stop();self.assertEqual(list(Path(temp).iterdir()),[])
    def test_cancel_discards_pending_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            data=pcm(320)+pcm(640,1000)+pcm(960)
            stream=Mock();stream.read_frame.side_effect=[data[x:x+2560] for x in range(0,len(data),2560)]
            decoder=Mock();decoder.feed.return_value=None
            pipe=StreamingWakePipeline(lambda **kw:stream,decoder,Path(temp));pipe.start();pipe.thread.join(2)
            self.assertFalse(pipe.results.empty());pipe.stop();self.assertEqual(list(Path(temp).iterdir()),[])
    def test_stream_failure_propagates_without_ready_event(self):
        with tempfile.TemporaryDirectory() as temp:
            decoder=Mock()
            def fail(**kw):raise VoiceRuntimeError('AUDIO_CAPTURE_DEVICE_UNAVAILABLE')
            pipe=StreamingWakePipeline(fail,decoder,Path(temp));pipe.start();pipe.thread.join(2)
            with self.assertRaisesRegex(VoiceRuntimeError,'AUDIO_CAPTURE_DEVICE_UNAVAILABLE'):pipe.next_window(timeout=.01)
            pipe.stop();self.assertEqual(list(Path(temp).iterdir()),[])


class StreamingConversationTests(unittest.TestCase):
    def run_turn(self, *, native, activity, heard, followup='what is the temperature', complete=True, stop_failure=False):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        path=root/'voice.wav'
        with wave.open(str(path),'wb') as wav:wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(pcm(1600,1000))
        a=VoiceAppliance.__new__(VoiceAppliance);a.stop=threading.Event();a.emit=Mock();a.publish_ready=False
        a.config=SimpleNamespace(extensions=SimpleNamespace(wake_word=SimpleNamespace(enabled=True,phrase='GonKen')))
        a.wait_until_ready=Mock(return_value=True);a.transition_announcer=None;a.notification_announcer=None
        a._write_readiness_state=Mock()
        a._transcribe_captured_audio=Mock(side_effect=lambda p:(p.unlink(),heard)[1])
        a.capture_text=Mock(return_value=followup);a.speak=Mock();a.speak_progress_cue=Mock()
        a.brain=Mock();a.brain.complete_inline_command.return_value=False;a.brain.after_spoken.return_value=None;a.brain.confirmation_pending.return_value=False
        def answer(question):a.stop.set();return '27 degrees.'
        a._answer_question=Mock(side_effect=answer)
        event=StreamingWakeWindow(1,path,0,complete,native,activity,2.0,1600)
        class Pipeline:
            window_seconds=0;dropped_windows=0;capture_mode='streaming-kws-vad'
            def start(self):pass
            def stop(self,**kw):
                if stop_failure:
                    a.stop.set()
                    raise VoiceRuntimeError('WAKE_CAPTURE_STOP_TIMEOUT')
            def next_window(self,**kw):return event
        pipe=Pipeline();count=[0]
        def factory():
            count[0]+=1
            if count[0]>1:a.stop.set()
            return pipe
        a._new_wake_capture_pipeline=factory
        led=Mock();led.metadata.return_value={'logical_bcm':22,'chip_path':'test','line_offset':22};a._new_wake_monitor_led=lambda:led
        self.assertEqual(a.wake_loop(),0)
        self.assertFalse(path.exists())
        return a
    def test_stop_failure_cleans_consumer_owned_audio_without_routing(self):
        a=self.run_turn(native=True,activity=True,heard='GonKen turn on the fan',stop_failure=True)
        a._answer_question.assert_not_called();a._transcribe_captured_audio.assert_not_called()
    def test_inline_temperature_no_yes_no_second_capture(self):
        a=self.run_turn(native=True,activity=True,heard="GonKen what's the temperature")
        a._answer_question.assert_called_once_with("what's the temperature");a.capture_text.assert_not_called();a.speak_progress_cue.assert_not_called()
        self.assertEqual(a._transcribe_captured_audio.call_count,1)
    def test_inline_general_question_no_unnecessary_capture(self):
        a=self.run_turn(native=True,activity=True,heard='GonKen explain photosynthesis')
        a._answer_question.assert_called_once_with('explain photosynthesis');a.capture_text.assert_not_called()
    def test_keyword_only_fast_yes_then_command(self):
        a=self.run_turn(native=True,activity=False,heard='not consumed')
        a._transcribe_captured_audio.assert_not_called();a.speak_progress_cue.assert_called_once_with('Yes?');a.capture_text.assert_called_once_with(8)
        a._answer_question.assert_called_once_with('what is the temperature')
    def test_native_miss_uses_complete_utterance_fallback_not_new_capture(self):
        a=self.run_turn(native=False,activity=True,heard='GonKen turn off the fan')
        a._answer_question.assert_called_once_with('turn off the fan');a.capture_text.assert_not_called()
    def test_native_false_attention_cannot_route_wakeless_inline_command(self):
        a=self.run_turn(native=True,activity=True,heard='turn on the fan')
        a._answer_question.assert_not_called();a.capture_text.assert_not_called();a.speak.assert_not_called()
    def test_background_speech_ignored_without_wake(self):
        a=self.run_turn(native=False,activity=True,heard='I went to the library')
        a._answer_question.assert_not_called();a.speak.assert_not_called()
    def test_truncated_delayed_command_never_executed(self):
        a=self.run_turn(native=True,activity=True,heard='GonKen turn fan on after',complete=False)
        a._transcribe_captured_audio.assert_not_called();a._answer_question.assert_not_called();a.capture_text.assert_not_called()


class WakeConfigurationTests(unittest.TestCase):
    def test_default_and_legacy_migration(self):
        c=load_config(site_path=None,environ={}).config
        self.assertEqual(c.extensions.wake_word.backend,'streaming')
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'site.toml';p.write_text('schema_version = 2\n[extensions.wake_word]\nenabled = true\nphrase = "GonKen"\n')
            loaded=load_config(site_path=p,environ={}).config
            self.assertEqual(loaded.extensions.wake_word.backend,'streaming')
    def test_bad_backend_and_threshold_rejected(self):
        c=load_config(site_path=None,environ={}).config
        for k,v in [('backend','unknown'),('keyword_threshold',float('nan')),('keyword_threshold',0.0)]:
            with self.subTest(k=k,v=v),self.assertRaises(ConfigError):
                _validate_values(replace(c,extensions=replace(c.extensions,wake_word=replace(c.extensions.wake_word,**{k:v}))))

if __name__=='__main__':unittest.main()
