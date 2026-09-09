"""Bounded PCM16 frame queue. Capture callbacks never perform inference."""
import queue
import threading


class FrameBuffer:
    def __init__(self, rate=48000, channels=1, max_seconds=30, queue_frames=32, block_frames=4096):
        if rate <= 0 or channels not in (1, 2) or max_seconds <= 0 or queue_frames <= 0 or block_frames <= 0:
            raise ValueError('invalid capture bounds')
        self.rate, self.channels = rate, channels
        self.max_frames = int(rate * max_seconds)
        self.block_frames = block_frames
        self.queue = queue.Queue(maxsize=queue_frames)
        self.frames = self.captured_frames = self.dropped_frames = 0
        self.active = False
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self.active:
                raise RuntimeError('capture already active')
            while not self.queue.empty():
                self.queue.get_nowait()
            self.frames = self.captured_frames = self.dropped_frames = 0
            self.active = True

    def push(self, pcm):
        if not isinstance(pcm, bytes) or len(pcm) % (2 * self.channels):
            raise ValueError('PCM must contain whole signed 16-bit frames')
        frames = len(pcm) // (2 * self.channels)
        if frames > self.block_frames:
            raise ValueError('callback block exceeds bound')
        with self._lock:
            if not self.active:
                return False
            self.captured_frames += frames
            if self.captured_frames > self.max_frames:
                self.active = False
                self.dropped_frames += frames
                return False
            try:
                self.queue.put_nowait(pcm)
            except queue.Full:
                self.dropped_frames += frames
                return False
            self.frames += frames
            return True

    @property
    def duration(self):
        return self.captured_frames / self.rate

    def stop(self):
        with self._lock:
            self.active = False

    def close(self):
        self.stop()
        while not self.queue.empty():
            self.queue.get_nowait()
