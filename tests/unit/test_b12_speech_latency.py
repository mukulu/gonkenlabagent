from __future__ import annotations
from array import array
import math
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave

from gonken_agent.audio.endpoint import SpeechEndpoint
from gonken_agent.voice_runtime import AudioBackend, EnvironmentTransitionAnnouncer
from gonken_agent.environment.responses import environment_success_response
from gonken_agent.environment.intents import EnvironmentIntent
from gonken_agent.power import logind_action, PowerError

RATE=16000
def pcm(seconds, amplitude=0):
    return array('h',[int(amplitude*math.sin(2*math.pi*440*i/RATE)) for i in range(int(RATE*seconds))]).tobytes()
def wav(path,data):
    with wave.open(str(path),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(data)

class EndpointTests(unittest.TestCase):
    def test_sustained_speech_then_silence_ends_before_eight_seconds(self):
        d=SpeechEndpoint(RATE)
        self.assertFalse(d.feed(pcm(.3)))
        self.assertFalse(d.feed(pcm(.4,2000)))
        self.assertFalse(d.feed(pcm(.6)))
        self.assertTrue(d.feed(pcm(.4)))
        self.assertLess(d.frames/50,2)
    def test_no_speech_does_not_shorten_maximum(self):
        d=SpeechEndpoint(RATE)
        for _ in range(8):self.assertFalse(d.feed(pcm(1)))
    def test_constant_noise_does_not_clip_to_short_window(self):
        d=SpeechEndpoint(RATE)
        for _ in range(8):self.assertFalse(d.feed(pcm(1,600)))
    def test_short_pause_and_transient_noise_do_not_trigger(self):
        d=SpeechEndpoint(RATE);self.assertFalse(d.feed(pcm(.1,2500)));self.assertFalse(d.feed(pcm(2)))
        self.assertFalse(d.feed(pcm(.6,2500)));self.assertFalse(d.feed(pcm(.4)));self.assertFalse(d.feed(pcm(.8,2500)))
    def test_partial_bytes_bounded_tail(self):
        d=SpeechEndpoint(RATE)
        for _ in range(100):d.feed(b'\x00')
        self.assertLess(len(d.tail),d.frame_bytes)
        with self.assertRaises(ValueError):d.feed(b'0'*300000)
    def test_wav_and_raw_incremental_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'capture.wav';d=SpeechEndpoint(RATE)
            path.write_bytes(b'RIFF');self.assertFalse(d.observe(path))
            data=pcm(.4,2500)+pcm(1.2);wav(path,data)
            self.assertFalse(d.observe(path))
            self.assertTrue(d.observe(path))
            raw=Path(tmp)/'capture.pcm';raw.write_bytes(data);r=SpeechEndpoint(RATE)
            self.assertFalse(r.observe(raw,raw=True));self.assertTrue(r.observe(raw,raw=True))
    def test_wrong_wav_format_cannot_trigger_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.wav'
            with wave.open(str(path),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(pcm(.4,2000)+pcm(2))
            self.assertFalse(SpeechEndpoint(RATE).observe(path))
    def test_actual_alsa_path_stops_process_then_validates_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'voice.wav'
            backend=AudioBackend.__new__(AudioBackend);backend.arecord=Path('/usr/bin/arecord');backend.input_device='hw:test'
            backend.input_mode='alsa-usb';backend.config=SimpleNamespace(audio=SimpleNamespace(processing_rate=RATE))
            class Process:
                returncode=None
                def poll(self):return self.returncode
                def send_signal(self,sig):self.returncode=130
                def communicate(self,timeout):return ('','')
                def kill(self):self.returncode=-9
                def wait(self,timeout):return self.returncode
            process=Process()
            def spawn(args,**kw):
                kw['stdout'].write(pcm(.4,2500)+pcm(1.2));kw['stdout'].flush();return process
            with patch('gonken_agent.voice_runtime.subprocess.Popen',side_effect=spawn),patch('gonken_agent.voice_runtime.time.sleep'):
                backend._record_to(path,8,end_on_silence=True)
            self.assertEqual(process.returncode,130);self.assertTrue(backend.last_capture_metadata['speech_endpointing'])
    def test_question_path_requests_endpoint_not_wake_path(self):
        from gonken_agent.voice_runtime import VoiceAppliance
        a=VoiceAppliance.__new__(VoiceAppliance);a.stop=threading.Event();a.config=SimpleNamespace(audio=SimpleNamespace(speech_endpointing=True,processing_rate=RATE))
        a.audio=Mock();a.audio.capture.return_value=Path('test');a._transcribe_captured_audio=Mock(return_value='a question')
        self.assertEqual(a.capture_text(8),'a question');a.audio.capture.assert_called_once_with(8,cancel=a.stop,end_on_silence=True)

class ShortSpeechTests(unittest.TestCase):
    def test_real_temperature_short_but_invalid_never_current(self):
        intent=EnvironmentIntent('sensor.read',{},'temperature')
        result={'reading':{'valid':True,'quality':'ready','temperature_c':27.4,'relative_humidity_pct':50,'source_backend':'sht31'}}
        text=environment_success_response(intent,result,concise=True);self.assertLess(len(text.split()),14)
        result['reading']['quality']='stale';self.assertIn('do not have a current',environment_success_response(intent,result,concise=True))
    def test_simulated_temperature_remains_explicit(self):
        result={'reading':{'valid':True,'quality':'ready','temperature_c':27.4,'relative_humidity_pct':50,'source_backend':'simulated'}}
        self.assertIn('In simulation',environment_success_response(EnvironmentIntent('sensor.read',{},'temperature'),result,concise=True))
    def test_fan_command_does_not_become_motion_claim(self):
        result={'state':{'fan_power':'on','mode':'manual'}}
        text=environment_success_response(EnvironmentIntent('fan.set',{},'fan_set'),result,concise=True)
        self.assertIn('by command',text);self.assertNotIn('spinning',text);self.assertLess(len(text.split()),20)
    def test_announcer_polls_at_most_once_a_second_and_generation_resets(self):
        clock=[10.];client=Mock();client.events.return_value={'generation':'a','events':[]}
        ann=EnvironmentTransitionAnnouncer(lambda:client,clock=lambda:clock[0]);ann.pending();ann.pending();self.assertEqual(client.events.call_count,1)
        clock[0]=11.;client.events.return_value={'generation':'b','events':[]};ann.pending();self.assertEqual(ann._generation,'b')
    def test_root_cannot_use_adapter_to_bypass_inhibitors(self):
        runner=Mock()
        with self.assertRaisesRegex(PowerError,'NOT_ROOT'):logind_action('REBOOT_DEVICE',run=runner,effective_uid=lambda:0)
        runner.assert_not_called()

if __name__=='__main__':unittest.main()
