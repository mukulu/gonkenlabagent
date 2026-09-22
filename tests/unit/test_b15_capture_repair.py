from pathlib import Path
from types import SimpleNamespace
import os
import signal
import struct
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from gonken_agent.audio.speech import validate_wav, ProcessFailure
from gonken_agent.voice_runtime import AudioBackend, VoiceAppliance, VoiceRuntimeError, _transition_announcement_text


class CaptureRepairTests(unittest.TestCase):
    def backend(self, root):
        b = AudioBackend.__new__(AudioBackend)
        b.config = SimpleNamespace(audio=SimpleNamespace(processing_rate=16000))
        b.arecord = Path('/usr/bin/arecord'); b.parecord = Path('/usr/bin/parecord')
        b.input_device = 'plughw:CARD=TEST,DEV=0'; b.input_mode = 'alsa-usb'
        b.runtime_dir = root
        return b

    def test_stale_recorder_header_reproduction_then_owned_pcm_finalization(self):
        # Target-shaped failure: header promises 8 seconds; interruption wrote 1.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); dest = root/'record.wav'; data = b'\x11\x00' * 16000
            header = (b'RIFF'+struct.pack('<I',36+8*32000)+b'WAVEfmt '+struct.pack('<IHHIIHH',16,1,1,16000,32000,2,16)+b'data'+struct.pack('<I',8*32000))
            dest.write_bytes(header+data)
            with self.assertRaises(ProcessFailure): validate_wav(dest, max_seconds=9)
            b=self.backend(root)
            proc=Mock();proc.poll.return_value=0;proc.returncode=0;proc.communicate.return_value=('','')
            def spawn(args, **kw):
                self.assertEqual(args[args.index('-t')+1],'raw')
                self.assertNotIn(str(dest),args)
                kw['stdout'].write(data);kw['stdout'].flush();return proc
            with patch('gonken_agent.voice_runtime.subprocess.Popen',side_effect=spawn):
                b._record_to(dest,8,end_on_silence=True)
            self.assertEqual(validate_wav(dest)['frames'],16000)
            self.assertEqual(list(root.glob('*.pcm')),[])

    def test_empty_and_odd_pcm_never_become_valid_wav(self):
        for raw, code in [(b'', 'AUDIO_CAPTURE_EMPTY'),(b'1','AUDIO_CAPTURE_PCM_MISALIGNED')]:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp:
                b=self.backend(Path(tmp));proc=Mock();proc.poll.return_value=0;proc.returncode=0;proc.communicate.return_value=('','')
                def spawn(*args,**kw):kw['stdout'].write(raw);kw['stdout'].flush();return proc
                with patch('gonken_agent.voice_runtime.subprocess.Popen',side_effect=spawn):
                    with self.assertRaises(VoiceRuntimeError) as caught:b._record_to(Path(tmp)/'wav',1)
                self.assertEqual(caught.exception.code,code)
                self.assertEqual(list(Path(tmp).glob('*.pcm')),[])

    def test_nonzero_device_error_not_hidden_by_existing_pcm(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.backend(Path(tmp));proc=Mock();proc.poll.return_value=2;proc.returncode=2;proc.communicate.return_value=('','Permission denied')
            def spawn(*args,**kw):kw['stdout'].write(b'\0'*32000);kw['stdout'].flush();return proc
            with patch('gonken_agent.voice_runtime.subprocess.Popen',side_effect=spawn):
                with self.assertRaisesRegex(VoiceRuntimeError,'AUDIO_CAPTURE_PERMISSION_DENIED'):b._record_to(Path(tmp)/'wav',1)

    def test_complete_general_inline_question_does_not_wait_for_second_capture(self):
        a=VoiceAppliance.__new__(VoiceAppliance);a.brain=Mock();a.brain.complete_inline_command.return_value=False;a.capture_text=Mock()
        self.assertEqual(a._question_after_wake('explain photosynthesis',utterance_complete=True),'explain photosynthesis')
        a.capture_text.assert_not_called()

    def test_recovery_does_not_repeat_startup_announcement(self):
        a=VoiceAppliance.__new__(VoiceAppliance);a.stop=threading.Event();a.probe=Mock(return_value={});a.speak=Mock();a.cue_cache=Mock();a.piper=Mock();a._write_ready=Mock();a._event=Mock()
        a.config=SimpleNamespace(extensions=SimpleNamespace(wake_word=SimpleNamespace(phrase='GonKen')),runtime=SimpleNamespace(interaction_mode='wake_word'))
        self.assertTrue(a.wait_until_ready());self.assertTrue(a.wait_until_ready())
        a.speak.assert_called_once_with('GonKen assistant is ready.')
        self.assertEqual(a.probe.call_count,2)

    def test_short_announcements_and_error_truth(self):
        def event(reason,power):return {'detail':{'reason':reason,'fan_power':power},'provenance':{'sensor_is_simulated':False,'actuator_is_simulated':False}}
        self.assertEqual(_transition_announcement_text(event('AUTO_START_THRESHOLD','on')),'Fan actuator started.')
        self.assertEqual(_transition_announcement_text(event('AUTO_STOP_THRESHOLD','off')),'Fan actuator stopped.')
        self.assertIn('unconfirmed',_transition_announcement_text(event('ACTUATOR_ERROR_SAFE_OFF','off')))
        self.assertIsNone(_transition_announcement_text(event('AUTO_START_THRESHOLD','unknown')))

if __name__=='__main__':unittest.main()
