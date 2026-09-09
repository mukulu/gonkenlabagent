"""Bounded, sequential coordinator with injectable local-only pipeline adapters.

Adapters must honor the cancellation event and release resources before returning.
This module does not claim that physical capture/GPIO adapters are installed.
"""
import queue
import signal
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from .state import State, StateMachine


class Cancelled(Exception):
    pass


@dataclass(frozen=True)
class Activation:
    text: str | None = None

    def __post_init__(self):
        if self.text is not None and (not self.text.strip() or len(self.text) > 4096):
            raise ValueError('text must contain 1–4096 characters')


class Coordinator:
    def __init__(self, pipeline, observer=lambda state, code: None):
        self.pipeline = pipeline
        self.observer = observer
        self.machine = StateMachine()
        self.cancel = threading.Event()
        self.events = queue.Queue(maxsize=1)
        self._activation_lock = threading.Lock()
        self._busy = False
        self._closed = False
        self._transition(State.WAITING)
        self.refresh()

    @property
    def state(self):
        return self.machine.state

    def _transition(self, state, code='OK'):
        self.machine.transition(state)
        self.observer(state.value, code)

    def refresh(self):
        if self.cancel.is_set() or self.state not in {State.WAITING, State.DEGRADED}:
            return
        if self.state == State.DEGRADED:
            self._transition(State.WAITING)
        try:
            ready = self.pipeline.ready()
        except Exception:
            ready = False
        self._transition(State.IDLE if ready else State.DEGRADED,
                         'OK' if ready else 'DEPENDENCY_UNAVAILABLE')

    def activate(self, text=None):
        event = Activation(text)
        with self._activation_lock:
            if self._busy or self.cancel.is_set() or self.state != State.IDLE:
                return False
            self._busy = True
            self.events.put_nowait(event)
            return True

    def request_stop(self):
        # Signal handlers only set the event. The coordinator owns cleanup/state.
        self.cancel.set()

    def _check(self):
        if self.cancel.is_set():
            raise Cancelled()

    def step(self):
        if self._closed:
            return None
        if self.cancel.is_set():
            self.close()
            return None
        try:
            event = self.events.get_nowait()
        except queue.Empty:
            self.refresh()
            return None
        try:
            self._check()
            text = event.text
            if text is None:
                self._transition(State.RECORDING)
                # Capture owns its temporary audio context through transcription.
                with self.pipeline.capture(self.cancel) as audio:
                    self._check()
                    self._transition(State.TRANSCRIBING)
                    text = self.pipeline.transcribe(audio, self.cancel)
                self._check()
            if not isinstance(text, str) or not text.strip() or len(text) > 4096:
                raise ValueError('invalid transcription')
            self._transition(State.RETRIEVING)
            sources = self.pipeline.retrieve(text, self.cancel)
            self._check()
            self._transition(State.GENERATING)
            answer = self.pipeline.generate(text, sources, self.cancel)
            self._check()
            if event.text is None:
                self._transition(State.SPEAKING)
                self.pipeline.speak(answer, self.cancel)
                self._check()
            self._transition(State.IDLE)
            return answer
        except Cancelled:
            if not self.cancel.is_set():
                self._transition(State.DEGRADED, 'CANCELLED')
        except Exception:
            self._transition(State.DEGRADED, 'PIPELINE_FAILED')
        finally:
            with self._activation_lock:
                self._busy = False
            self.events.task_done()
            if self.cancel.is_set():
                self.close()
        return None

    def serve(self, poll_seconds=0.05):
        try:
            while not self.cancel.is_set():
                self.step()
                self.cancel.wait(poll_seconds)
        finally:
            self.close()

    def close(self):
        if self._closed:
            return
        self.cancel.set()
        self._closed = True
        if self.state != State.STOPPING:
            self._transition(State.STOPPING)
        try:
            self.pipeline.close()
        finally:
            while True:
                try:
                    self.events.get_nowait()
                    self.events.task_done()
                except queue.Empty:
                    break


@contextmanager
def signal_handlers(coordinator):
    previous = {}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, lambda *_: coordinator.request_stop())
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
