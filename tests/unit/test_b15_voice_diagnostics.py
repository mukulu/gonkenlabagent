from types import SimpleNamespace
from unittest.mock import patch
import json
import unittest
from gonken_agent.support import _voice_metric_line, _service_event_codes
from gonken_agent.voice_runtime import _readiness_recoverable

class VoiceDiagnosticsTests(unittest.TestCase):
    def test_metrics_preserve_latency_not_private_content(self):
        r=_voice_metric_line('[INFO] code=WAKE_STREAM_METRICS native_keyword=True fallback=False utterance_ms=2340 keyword_decode_max_ms=2.56 transcription_ms=3200 prompt=SECRET_CANARY')
        self.assertEqual(r['transcription_ms'],3200);self.assertEqual(r['keyword_decode_max_ms'],2.56);self.assertTrue(r['native_keyword']);self.assertNotIn('SECRET',json.dumps(r))
    def test_invalid_unbounded_or_nonfinite_values_omitted(self):
        for value in ('nan','inf','-1','1e309','999999999999999999'):
            self.assertIsNone(_voice_metric_line('[INFO] code=VOICE_CAPTURE_METRICS capture_ms='+value))
        self.assertIsNone(_voice_metric_line('[INFO] code=PRIVATE_EVENT capture_ms=100'))
    def test_support_owns_a_bounded_content_free_metrics_list(self):
        text='\n'.join('[INFO] code=VOICE_CAPTURE_METRICS capture_ms=1200 transcription_ms=3100 transcript=SECRET' for _ in range(30))
        with patch('gonken_agent.support.shutil.which',return_value='/bin/journalctl'),patch('gonken_agent.support.subprocess.run',return_value=SimpleNamespace(stdout=text,returncode=0)):
            result=_service_event_codes()
        rows=result['units']['gonken-agent.service']['voice_metrics']
        self.assertEqual(len(rows),20);self.assertFalse(result['units']['gonken-agent.service']['raw_text_exported']);self.assertNotIn('SECRET',json.dumps(result))
    def test_missing_native_dependency_not_an_infinite_recoverable_start(self):
        self.assertFalse(_readiness_recoverable('WAKE_NATIVE_LIBRARY_MISSING'))
        self.assertTrue(_readiness_recoverable('AUDIO_STREAM_EOF'))

if __name__=='__main__':unittest.main()
