"""Single-owner streaming wake and complete-utterance capture.

Idle audio stays in a 400 ms RAM ring. Sustained speech opens one bounded
utterance, preserving the wake and its command; it is finalized on real silence,
not a two-second wall-clock boundary. At most one utterance is handed to the
consumer. No background Whisper queue exists. The producer closes the recorder
before the consumer may speak. A conservative native miss may be recovered by
one full-utterance Whisper check (never by transcribing silent windows).
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
from pathlib import Path
import os
import queue
import tempfile
import threading
import time
import wave

from .keyword_native import KeywordHit


def voiced(frame: bytes, threshold: int) -> bool:
    values = array('h'); values.frombytes(frame)
    return bool(values) and sum(x*x for x in values) >= len(values)*threshold*threshold


@dataclass(frozen=True)
class Utterance:
    pcm: bytes
    start_sample: int
    end_sample: int
    complete: bool


class UtteranceSegmenter:
    frame_bytes = 640  # 20 ms at 16 kHz PCM16
    pre_bytes = 12800  # 400 ms, includes the sustained-speech trigger

    def __init__(self, *, threshold: int = 250, silence_ms: int = 900, max_seconds: int = 12):
        if type(threshold) is not int or not 50 <= threshold <= 2000:
            raise ValueError('invalid speech threshold')
        if type(silence_ms) is not int or not 500 <= silence_ms <= 2000:
            raise ValueError('invalid speech silence')
        if type(max_seconds) is not int or not 2 <= max_seconds <= 30:
            raise ValueError('invalid utterance limit')
        self.threshold, self.quiet_limit = threshold, (silence_ms+19)//20
        self.maximum_bytes = max_seconds*32000
        self.total_samples = self.start_sample = 0
        self.pre = bytearray(); self.data = bytearray()
        self.speech_frames = self.quiet_frames = 0
        self.active = self.finished = False

    def feed(self, pcm: bytes) -> Utterance | None:
        if self.finished or not isinstance(pcm, bytes) or not pcm or len(pcm) % self.frame_bytes or len(pcm) > 2560:
            raise ValueError('invalid segmenter frame/state')
        for offset in range(0, len(pcm), self.frame_bytes):
            frame = pcm[offset:offset+self.frame_bytes]
            self.total_samples += len(frame)//2
            energy = voiced(frame, self.threshold)
            if self.active:
                self.data.extend(frame)
                self.quiet_frames = 0 if energy else self.quiet_frames + 1
                complete = self.quiet_frames >= self.quiet_limit
                limited = len(self.data) >= self.maximum_bytes
                if complete or limited:
                    self.finished = True
                    return Utterance(bytes(self.data), self.start_sample, self.total_samples, complete and not limited)
            else:
                self.pre.extend(frame); del self.pre[:-self.pre_bytes]
                self.speech_frames = self.speech_frames + 1 if energy else 0
                if self.speech_frames >= 5:
                    self.active = True
                    self.data = self.pre.copy()
                    self.start_sample = self.total_samples - len(self.data)//2
                    self.pre.clear()
        return None


def speech_after_keyword(utterance: Utterance, hit: KeywordHit, threshold: int) -> bool:
    """Don't say Yes? over words following the name. Ignore 100 ms alignment tail."""
    offset = max(0, hit.end_sample + 1600 - utterance.start_sample) * 2
    data = utterance.pcm[offset:]
    count = 0
    for pos in range(0, len(data)-639, 640):
        count = count + 1 if voiced(data[pos:pos+640], threshold) else 0
        if count >= 4:
            return True
    return False


@dataclass(frozen=True)
class StreamingWakeWindow:
    sequence: int
    path: Path
    captured_monotonic: float
    utterance_complete: bool
    native_keyword: bool
    command_activity: bool
    keyword_decode_max_ms: float
    utterance_ms: int


class StreamingWakePipeline:
    capture_mode = 'streaming-kws-vad'
    window_seconds = 0
    dropped_windows = 0

    def __init__(self, open_stream, decoder, runtime_dir: Path, *, threshold=250, silence_ms=900):
        self.open_stream, self.decoder = open_stream, decoder
        self.runtime_dir = Path(runtime_dir)
        self.threshold, self.silence_ms = threshold, silence_ms
        self.cancel = threading.Event()
        self.thread = None
        self.results = queue.Queue(maxsize=1)
        self.error = None
        self.captured_windows = 0
        self.keyword_decode_max_ms = 0.0

    def start(self):
        if self.thread is not None:
            raise RuntimeError('stream pipeline already started')
        self.thread = threading.Thread(target=self._produce, name='gonken-wake-stream', daemon=True)
        self.thread.start()

    def _produce(self):
        stream = None; path = None
        try:
            segmenter = UtteranceSegmenter(threshold=self.threshold, silence_ms=self.silence_ms)
            self.decoder.reset()
            stream = self.open_stream(cancel=self.cancel)
            hit = None
            reset_at = 30*16000
            while not self.cancel.is_set():
                frame = stream.read_frame(timeout=0.1)
                if frame is None:
                    continue
                if hit is None:
                    started = time.monotonic()
                    hit = self.decoder.feed(frame)
                    self.keyword_decode_max_ms = max(self.keyword_decode_max_ms, (time.monotonic()-started)*1000)
                utterance = segmenter.feed(frame)
                if utterance is not None:
                    # Close/reap first, then publish. No playback/capture overlap.
                    stream.close(); stream = None
                    if self.cancel.is_set():
                        return
                    fd, name = tempfile.mkstemp(prefix='voice-utterance-', suffix='.wav', dir=self.runtime_dir)
                    path = Path(name)
                    with os.fdopen(fd, 'wb') as out, wave.open(out, 'wb') as wav:
                        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
                        wav.writeframes(utterance.pcm)
                    event = StreamingWakeWindow(1, path, time.monotonic(), utterance.complete,
                        hit is not None, hit is None or speech_after_keyword(utterance, hit, self.threshold),
                        round(self.keyword_decode_max_ms, 3), len(utterance.pcm)*1000//32000)
                    self.results.put_nowait(event)
                    self.captured_windows = 1
                    path = None
                    return
                if hit is None and not segmenter.active and segmenter.total_samples >= reset_at:
                    self.decoder.reset(base_sample=segmenter.total_samples)
                    reset_at = segmenter.total_samples + 30*16000
        except BaseException as exc:
            if not self.cancel.is_set():
                self.error = exc
        finally:
            if stream is not None:
                try:
                    stream.close()
                except Exception as exc:
                    if self.error is None and not self.cancel.is_set():
                        self.error = exc
            if path is not None:
                path.unlink(missing_ok=True)

    def next_window(self, *, timeout=0.25):
        try:
            return self.results.get(timeout=timeout)
        except queue.Empty:
            if self.error is not None:
                raise self.error
            return None

    def stop(self, *, join_timeout=3.0):
        self.cancel.set()
        if self.thread is not None:
            self.thread.join(timeout=join_timeout)
            if self.thread.is_alive():
                raise RuntimeError('WAKE_CAPTURE_STOP_TIMEOUT')
        while True:
            try:
                self.results.get_nowait().path.unlink(missing_ok=True)
            except queue.Empty:
                break
