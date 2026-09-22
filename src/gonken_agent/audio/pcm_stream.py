"""Bounded nonblocking raw PCM pipe. The owning voice loop closes it before TTS."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time


class PCMStreamError(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(code)


class PCMInputStream:
    """One recorder, 80 ms S16_LE/16 kHz/mono frames, bounded stderr and buffers.

    This API accepts only a fixed argv built by AudioBackend, never model text.
    Partial reads are retained. EOF, stalled input and nonzero exits are not
    silence. Capture and stderr are never persisted by this class.
    """
    frame_bytes = 2560

    def __init__(self, args: list[str], *, stall_seconds: float = 5.0):
        self.process = None
        self.selector = selectors.DefaultSelector()
        self.buffer = bytearray()
        self.stderr = bytearray()
        self.closed = False
        self.stall_seconds = stall_seconds
        self.last_data = time.monotonic()
        try:
            self.process = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
            for pipe, name in ((self.process.stdout, 'audio'), (self.process.stderr, 'error')):
                os.set_blocking(pipe.fileno(), False)
                self.selector.register(pipe, selectors.EVENT_READ, name)
        except (OSError, ValueError) as exc:
            self.close()
            raise PCMStreamError('AUDIO_STREAM_START_FAILED', type(exc).__name__) from exc

    def _failure(self, default='AUDIO_STREAM_EOF'):
        # Hardware/runtime diagnostics only, no raw audio or transcription.
        text = bytes(self.stderr).decode('utf-8', errors='replace').casefold()
        if 'permission denied' in text or 'access denied' in text:
            default = 'AUDIO_CAPTURE_PERMISSION_DENIED'
        elif 'resource busy' in text:
            default = 'AUDIO_CAPTURE_DEVICE_BUSY'
        elif any(s in text for s in ('no such device', 'unknown pcm', 'no such entity')):
            default = 'AUDIO_CAPTURE_DEVICE_UNAVAILABLE'
        return PCMStreamError(default, f'recorder_rc={self.process.poll()}')

    def read_frame(self, *, timeout: float = 0.25) -> bytes | None:
        if self.closed:
            raise PCMStreamError('AUDIO_STREAM_CLOSED')
        deadline = time.monotonic() + max(0, min(timeout, 5.0))
        while len(self.buffer) < self.frame_bytes:
            if self.process.poll() is not None:
                # Drain diagnostic bytes without accepting stale buffered audio.
                try:
                    self.stderr.extend(os.read(self.process.stderr.fileno(), 4096))
                    del self.stderr[:-4096]
                except (BlockingIOError, OSError):
                    pass
                raise self._failure()
            if time.monotonic() - self.last_data > self.stall_seconds:
                raise self._failure('AUDIO_STREAM_STALLED')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            for key, _ in self.selector.select(min(remaining, 0.25)):
                try:
                    data = os.read(key.fileobj.fileno(), self.frame_bytes if key.data == 'audio' else 4096)
                except BlockingIOError:
                    continue
                if not data:
                    if key.data == 'audio':
                        raise self._failure()
                    self.selector.unregister(key.fileobj)
                    continue
                if key.data == 'audio':
                    self.last_data = time.monotonic()
                    self.buffer.extend(data)
                else:
                    self.stderr.extend(data)
                    del self.stderr[:-4096]
        result = bytes(self.buffer[:self.frame_bytes])
        del self.buffer[:self.frame_bytes]
        return result

    def prime(self, *, cancel, timeout: float = 5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cancel.is_set():
                raise PCMStreamError('AUDIO_CAPTURE_CANCELLED')
            frame = self.read_frame(timeout=0.1)
            if frame is not None:
                self.buffer[:0] = frame
                return
        raise self._failure('AUDIO_STREAM_STALLED')

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.selector.close()
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    self.process.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=1)
            for pipe in (self.process.stdout, self.process.stderr):
                if pipe is not None:
                    pipe.close()
        self.buffer.clear()
        self.stderr.clear()
