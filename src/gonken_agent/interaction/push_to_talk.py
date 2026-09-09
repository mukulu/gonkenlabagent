"""Debounced hold-to-record controller with an injected GPIO/capture adapter.

Call update at a regular interval using a monotonic clock. The physical adapter
must arrange LED-off at boot and on process death; that requires target evidence.
"""


class PushToTalk:
    def __init__(self, adapter, debounce=0.03, max_hold=30.0):
        if not 0 < debounce < 1 or max_hold <= debounce:
            raise ValueError('invalid timing bounds')
        self.adapter, self.debounce, self.max_hold = adapter, debounce, max_hold
        self.raw = self.stable = False
        self.changed_at = 0.0
        self.last_time = None
        self.started = None
        self.inhibited = False
        self.closed = False
        adapter.led(False)

    def update(self, pressed, now):
        if self.closed:
            return
        if type(pressed) is not bool or (self.last_time is not None and now < self.last_time):
            raise ValueError('boolean input and monotonic time required')
        self.last_time = now
        try:
            if pressed != self.raw:
                self.raw, self.changed_at = pressed, now
            if self.started is not None and now - self.started >= self.max_hold:
                self._stop(process=False)
                self.inhibited = True
            if self.raw == self.stable or now - self.changed_at < self.debounce:
                return
            self.stable = self.raw
            if not self.stable:
                if self.started is not None:
                    self._stop(process=True)
                self.inhibited = False
            elif not self.inhibited and self.adapter.available():
                self.adapter.led(True)
                self.adapter.start_capture()
                self.started = now
        except Exception:
            self.close()
            raise

    def _stop(self, process):
        self.started = None
        try:
            self.adapter.stop_capture()
        finally:
            self.adapter.led(False)
        if process:
            self.adapter.submit()

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.adapter.stop_capture()
        finally:
            try:
                self.adapter.led(False)
            finally:
                self.adapter.close()
