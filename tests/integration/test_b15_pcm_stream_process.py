"""Real child-process pipe/cancellation tests; no microphone or Raspberry Pi."""
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from gonken_agent.audio.pcm_stream import PCMInputStream, PCMStreamError
from gonken_agent.audio.keyword_native import NativeKeywordDetector, KeywordError


class PCMProcessTests(unittest.TestCase):
    def test_fragmented_raw_reads_are_lossless_and_stderr_is_bounded(self):
        script="import os,time;os.write(2,b'e'*20000);os.write(1,b'a'*333);time.sleep(.03);os.write(1,b'a'*2227);time.sleep(3)"
        stream=PCMInputStream([sys.executable,'-c',script])
        try:
            stream.prime(cancel=threading.Event());self.assertEqual(stream.read_frame(),b'a'*2560)
            self.assertLessEqual(len(stream.stderr),4096)
        finally:stream.close()
        self.assertIsNotNone(stream.process.poll());self.assertTrue(stream.process.stdout.closed)
    def test_stalled_child_is_not_silence_and_is_reaped(self):
        stream=PCMInputStream([sys.executable,'-c','import time;time.sleep(10)'],stall_seconds=.15)
        start=time.monotonic()
        try:
            with self.assertRaisesRegex(PCMStreamError,'AUDIO_STREAM_STALLED'):
                while True:stream.read_frame(timeout=.1)
        finally:stream.close()
        self.assertLess(time.monotonic()-start,2.5);self.assertIsNotNone(stream.process.poll())
    def test_device_error_not_reported_ready(self):
        stream=PCMInputStream([sys.executable,'-c',"import os;os.write(2,b'Permission denied');raise SystemExit(3)"])
        try:
            with self.assertRaises(PCMStreamError) as caught:stream.prime(cancel=threading.Event())
            self.assertIn(caught.exception.code,{'AUDIO_CAPTURE_PERMISSION_DENIED','AUDIO_STREAM_EOF'})
        finally:stream.close()
    def test_cancel_during_prime_does_not_wait_for_deadline(self):
        stream=PCMInputStream([sys.executable,'-c','import time;time.sleep(10)'])
        cancel=threading.Event();cancel.set();start=time.monotonic()
        try:
            with self.assertRaisesRegex(PCMStreamError,'AUDIO_CAPTURE_CANCELLED'):stream.prime(cancel=cancel)
        finally:stream.close()
        self.assertLess(time.monotonic()-start,2.5)
    def test_forced_cleanup_of_child_ignoring_sigint_is_bounded(self):
        stream=PCMInputStream([sys.executable,'-c','import signal,time,os;signal.signal(signal.SIGINT,signal.SIG_IGN);os.write(1,b"a"*2560);time.sleep(10)'])
        stream.prime(cancel=threading.Event());start=time.monotonic();stream.close();stream.close()
        self.assertLess(time.monotonic()-start,2.5);self.assertEqual(stream.process.returncode,-9)
    def test_native_missing_library_fails_closed_before_decoder_creation(self):
        with tempfile.TemporaryDirectory() as t,patch('gonken_agent.audio.keyword_native.C.CDLL',side_effect=OSError('missing')):
            with self.assertRaisesRegex(KeywordError,'WAKE_NATIVE_LIBRARY_MISSING'):NativeKeywordDetector('GonKen',Path(t))
    def test_native_missing_model_fails_closed(self):
        with tempfile.TemporaryDirectory() as t,patch.object(NativeKeywordDetector,'MODEL',Path(t)/'missing'):
            try:
                with self.assertRaisesRegex(KeywordError,'WAKE_NATIVE_MODEL_MISSING'):NativeKeywordDetector('GonKen',Path(t))
            except AssertionError as exc:
                if 'WAKE_NATIVE_LIBRARY_MISSING' in str(exc):self.skipTest('distro native library absent on this host')
                raise
    def test_actual_native_abi_silence_reset_close_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as t:
            try:d=NativeKeywordDetector('GonKen',Path(t))
            except KeywordError as e:
                if e.code in {'WAKE_NATIVE_LIBRARY_MISSING','WAKE_NATIVE_MODEL_MISSING'}:self.skipTest(e.code)
                raise
            try:
                for _ in range(25):self.assertIsNone(d.feed(bytes(2560)))
                with self.assertRaises(ValueError):d.feed(b'x')
                d.reset(base_sample=32000);self.assertIsNone(d.feed(bytes(2560)))
                self.assertEqual(d.position,33280)
            finally:d.close()
            d.close();self.assertEqual(list(Path(t).iterdir()),[])

if __name__=='__main__':unittest.main()
