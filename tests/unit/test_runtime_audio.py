import math
import struct
import sys
import tempfile
import threading
import unittest
import wave
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from gonken_agent.runtime import Coordinator, Cancelled
from gonken_agent.state import State, StateMachine
from gonken_agent.health import ComponentHealth, Readiness, summary
from gonken_agent.audio.devices import Device, DeviceUnavailable, select, Recovery
from gonken_agent.audio.capture import FrameBuffer
from gonken_agent.audio.resample import resample
from gonken_agent.audio.process import run, ProcessFailure
from gonken_agent.audio.speech import Piper, Whisper, validate_wav, speech_text
from gonken_agent.interaction.push_to_talk import PushToTalk


class Pipeline:
    def __init__(self, ready=True, hook=lambda stage: None):
        self.is_ready, self.hook = ready, hook
        self.closed = self.audio_open = self.spoken = False
    def ready(self): return self.is_ready
    @contextmanager
    def capture(self, cancel):
        self.audio_open = True
        try:
            self.hook('capture')
            yield 'audio'
        finally: self.audio_open = False
    def transcribe(self, audio, cancel):
        self.hook('transcribe')
        return 'question'
    def retrieve(self, text, cancel):
        if self.audio_open: raise AssertionError('audio retained during retrieval')
        self.hook('retrieve')
        return ['source']
    def generate(self, text, sources, cancel):
        self.hook('generate')
        return 'answer'
    def speak(self, answer, cancel):
        if self.audio_open: raise AssertionError('capture active during TTS')
        self.hook('speak')
        self.spoken = True
    def close(self): self.closed = True


class CoordinatorTests(unittest.TestCase):
    def test_complete_audio_path_and_no_feedback(self):
        states = []
        pipeline = Pipeline()
        c = Coordinator(pipeline, lambda state, code: states.append(state))
        self.assertTrue(c.activate())
        self.assertFalse(c.activate())
        self.assertEqual(c.step(), 'answer')
        self.assertEqual(states, ['WAITING_DEPENDENCIES', 'IDLE', 'RECORDING', 'TRANSCRIBING', 'RETRIEVING', 'GENERATING', 'SPEAKING', 'IDLE'])
        self.assertFalse(pipeline.audio_open)
        self.assertTrue(pipeline.spoken)
        c.close()
        self.assertTrue(pipeline.closed)
        self.assertEqual(c.state, State.STOPPING)

    def test_cancel_at_each_stage_releases_audio_and_client(self):
        for stage in ('capture', 'transcribe', 'retrieve', 'generate', 'speak'):
            with self.subTest(stage=stage):
                pipeline = Pipeline(hook=lambda actual: c.request_stop() if actual == stage else None)
                c = Coordinator(pipeline)
                c.activate()
                self.assertIsNone(c.step())
                self.assertTrue(pipeline.closed)
                self.assertFalse(pipeline.audio_open)
                self.assertEqual(c.state, State.STOPPING)

    def test_failure_at_each_stage_recovers_without_raw_error(self):
        def fail(_): raise RuntimeError('private transcript /home/user')
        for stage in ('capture', 'transcribe', 'retrieve', 'generate', 'speak'):
            with self.subTest(stage=stage):
                observations = []
                pipeline = Pipeline(hook=lambda actual: fail(actual) if actual == stage else None)
                c = Coordinator(pipeline, lambda *v: observations.append(v))
                c.activate()
                c.step()
                self.assertEqual(c.state, State.DEGRADED)
                self.assertNotIn('private', str(observations))
                self.assertFalse(pipeline.audio_open)
                pipeline.hook = lambda _: None
                c.refresh()
                self.assertTrue(c.activate())
                self.assertEqual(c.step(), 'answer')
                c.close()

    def test_concurrent_activation_only_one_is_accepted(self):
        c = Coordinator(Pipeline())
        barrier = threading.Barrier(12)
        results = []
        def submit():
            barrier.wait()
            results.append(c.activate('question'))
        threads = [threading.Thread(target=submit) for _ in range(12)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(sum(results), 1)
        self.assertEqual(c.events.qsize(), 1)
        self.assertEqual(c.step(), 'answer')
        c.close()

    def test_waiting_recovery_and_shutdown_before_consumption(self):
        p = Pipeline(ready=False)
        c = Coordinator(p)
        self.assertEqual(c.state, State.DEGRADED)
        self.assertFalse(c.activate())
        p.is_ready = True
        c.step()
        self.assertTrue(c.activate())
        c.request_stop()
        c.step()
        self.assertEqual(c.events.qsize(), 0)
        self.assertTrue(p.closed)

    def test_text_mode_never_captures_or_speaks(self):
        p = Pipeline()
        c = Coordinator(p)
        c.activate('question')
        self.assertEqual(c.step(), 'answer')
        self.assertFalse(p.spoken)
        c.close()

    def test_invalid_transition_and_input_rejected(self):
        with self.assertRaises(ValueError): StateMachine().transition(State.SPEAKING)
        c = Coordinator(Pipeline())
        for text in ('', ' ' * 5, 'x' * 4097):
            with self.assertRaises(ValueError): c.activate(text)
        c.close()


class HealthTests(unittest.TestCase):
    def test_precedence_exit_codes_and_empty_is_not_ready(self):
        self.assertEqual(summary([])['exit_code'], 2)
        rows = [ComponentHealth('config', Readiness.READY, 'VALID')]
        self.assertEqual(summary(rows)['exit_code'], 0)
        rows.append(ComponentHealth('gpio', Readiness.DEGRADED, 'NOT_FOUND'))
        self.assertEqual(summary(rows)['exit_code'], 2)
        rows.append(ComponentHealth('model', Readiness.FAILED, 'DIGEST_MISMATCH'))
        self.assertEqual(summary(rows)['exit_code'], 1)
    def test_no_arbitrary_error_text(self):
        with self.assertRaises(ValueError): ComponentHealth('model', Readiness.FAILED, '/home/private')
        with self.assertRaises(ValueError): ComponentHealth('secret', Readiness.READY, 'OK')


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.a = Device('usb-A', 'AIRHUG audio', 1, 1, (48000, 16000))
        self.b = Device('usb-B', 'AIRHUG audio', 1, 1, (48000,))
    def test_selection_missing_ambiguous_exact_rate_and_renumber(self):
        for devices in ([], [self.a, self.b]):
            with self.assertRaises(DeviceUnavailable): select(devices, 'AIRHUG', 'input', 48000)
        self.assertEqual(select([self.b, self.a], 'usb-A', 'input', 16000), self.a)
        with self.assertRaises(DeviceUnavailable): select([self.b], 'usb-B', 'input', 16000)
        with self.assertRaises(ValueError): select([self.a], '', 'input', 16000)
    def test_reenumeration_backoff_and_late_hotplug(self):
        devices = []
        calls = []
        r = Recovery(lambda: calls.append(1) or devices, lambda d: d, 'AIRHUG', 'input', 48000)
        self.assertIsNone(r.attempt(0))
        self.assertIsNone(r.attempt(.1))
        self.assertEqual(len(calls), 1)
        devices.append(self.a)
        self.assertEqual(r.attempt(.25), self.a)
        self.assertEqual(r.failures, 0)
    def test_queue_frame_accounting_overflow_duration_and_close(self):
        b = FrameBuffer(rate=16000, queue_frames=1, max_seconds=.01)
        b.start()
        self.assertTrue(b.push(b'\0' * 160))
        self.assertFalse(b.push(b'\0' * 20))
        self.assertEqual(b.dropped_frames, 10)
        self.assertEqual(b.duration, .005)
        b.queue.get_nowait()
        self.assertTrue(b.push(b'\0' * 160))
        self.assertFalse(b.push(b'\0' * 2))
        self.assertFalse(b.active)
        b.close()
        self.assertTrue(b.queue.empty())
        with self.assertRaises(ValueError): b.push(b'\0')
        with self.assertRaises(ValueError): b.push(b'\0' * 10000)
    def test_resampling_suppresses_alias_without_destroying_passband(self):
        def tone(freq):
            vals = [round(15000 * math.sin(2 * math.pi * freq * i / 48000)) for i in range(4800)]
            pcm = struct.pack('<' + 'h' * len(vals), *vals)
            out = resample(pcm, 48000)
            self.assertEqual(len(out), 3200)
            samples = struct.unpack('<1600h', out)[40:-40]
            return math.sqrt(sum(x*x for x in samples) / len(samples))
        low, high = tone(1000), tone(12000)
        self.assertGreater(low, 10000)
        self.assertLess(high / low, .01)
    def test_stereo_conversion_and_rejected_ratios(self):
        self.assertEqual(resample(struct.pack('<hhhh', 100, 300, -100, -300), 16000, channels=2), struct.pack('<hh', 200, -200))
        with self.assertRaises(ValueError): resample(b'', 44100)
        with self.assertRaises(ValueError): resample(b'x', 48000)


class ProcessTests(unittest.TestCase):
    def test_success_stderr_privacy_failure_timeout_and_cancel(self):
        event = threading.Event()
        self.assertEqual(run([sys.executable, '-c', 'print("ok")'], cancel=event), b'ok\n')
        for code, kwargs in [('import sys; print("secret",file=sys.stderr);sys.exit(1)', {}), ('import time;time.sleep(10)', {'timeout': .05}), ('print("x"*10000)', {'max_output': 100})]:
            with self.assertRaises(ProcessFailure) as caught:
                run([sys.executable, '-c', code], cancel=event, **kwargs)
            self.assertNotIn('secret', str(caught.exception))
        timer = threading.Timer(.05, event.set)
        timer.start()
        with self.assertRaises(Cancelled): run([sys.executable, '-c', 'import time; time.sleep(10)'], cancel=event)
        timer.join()
    def test_reject_shell_string_and_relative_executable(self):
        for argv in ('echo test', ['echo', 'test']):
            with self.assertRaises(ValueError): run(argv, cancel=threading.Event())


class SpeechTests(unittest.TestCase):
    @staticmethod
    def wav(path):
        with wave.open(str(path), 'wb') as f:
            f.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            f.writeframes(b'\0' * 3200)
    def test_wav_and_normalization(self):
        self.assertEqual(speech_text('**Hello** [lab](https://x)\n```do harm```'), 'Hello lab')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'x.wav'
            self.wav(p)
            self.assertEqual(validate_wav(p)['frames'], 1600)
            p.write_bytes(p.read_bytes()[:-10])
            with self.assertRaises(ProcessFailure): validate_wav(p)
    def test_tts_cleanup_on_success_playback_failure_and_process_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); voice = root/'voice.onnx'; voice.touch(); Path(str(voice)+'.json').write_text('{}')
            tts = Piper('/fake/piper', voice, root)
            def fake(argv, **kw): self.wav(Path(argv[-1]))
            with patch('gonken_agent.audio.speech.run', fake):
                with tts.synthesize('hello', threading.Event()) as p: self.assertTrue(p.exists())
                self.assertFalse(p.exists())
                with self.assertRaises(RuntimeError):
                    with tts.synthesize('hello', threading.Event()) as p: raise RuntimeError('playback')
                self.assertFalse(p.exists())
            with patch('gonken_agent.audio.speech.run', side_effect=Cancelled):
                with self.assertRaises(Cancelled):
                    with tts.synthesize('hello', threading.Event()): pass
            self.assertFalse(list(root.glob('tts-*')))
    def test_stt_cleanup_and_empty_output_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); model=root/'model.bin'; model.touch(); audio=root/'in.wav'; self.wav(audio)
            stt=Whisper('/fake/whisper', model, root)
            def fake(argv, **kw): Path(argv[argv.index('-of')+1]+'.txt').write_text('hello')
            with patch('gonken_agent.audio.speech.run', fake):
                self.assertEqual(stt.transcribe(audio, threading.Event()), 'hello')
            self.assertFalse(list(root.glob('stt-*')))
            with patch('gonken_agent.audio.speech.run', return_value=b''):
                with self.assertRaises(ProcessFailure): stt.transcribe(audio, threading.Event())
            self.assertFalse(list(root.glob('stt-*')))


class PTTAdapter:
    def __init__(self): self.calls=[]; self.ready=True
    def available(self): return self.ready
    def led(self, on): self.calls.append(('led', on))
    def start_capture(self): self.calls.append(('start',))
    def stop_capture(self): self.calls.append(('stop',))
    def submit(self): self.calls.append(('submit',))
    def close(self): self.calls.append(('close',))


class PTTTests(unittest.TestCase):
    def test_bounce_hold_release_and_led_before_submit(self):
        a=PTTAdapter(); p=PushToTalk(a)
        for pressed, now in [(True, 0), (False, .01), (True,.02), (True,.06), (False,.1), (False,.14)]: p.update(pressed, now)
        self.assertEqual(a.calls, [('led',False),('led',True),('start',),('stop',),('led',False),('submit',)])
        p.close()
    def test_stuck_button_cancels_no_processing_until_release(self):
        a=PTTAdapter(); p=PushToTalk(a, max_hold=1)
        for value,t in [(True,0),(True,.04),(True,2),(True,3)]: p.update(value,t)
        self.assertNotIn(('submit',), a.calls)
        self.assertEqual(a.calls.count(('start',)),1)
        for value,t in [(False,4),(False,4.1),(True,5),(True,5.1)]: p.update(value,t)
        self.assertEqual(a.calls.count(('start',)),2)
        p.close()
    def test_missing_device_and_start_failure_fail_closed(self):
        a=PTTAdapter(); a.ready=False; p=PushToTalk(a)
        p.update(True,0); p.update(True,.04)
        self.assertNotIn(('start',),a.calls)
        p.close()
        a=PTTAdapter(); p=PushToTalk(a)
        a.start_capture=lambda: (_ for _ in ()).throw(OSError('denied'))
        p.update(True,0)
        with self.assertRaises(OSError): p.update(True,.04)
        self.assertEqual(a.calls[-2:],[('led',False),('close',)])
