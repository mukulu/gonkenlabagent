"""Bounded local subprocesses with whole-process-group cancellation."""
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from ..runtime import Cancelled


class ProcessFailure(RuntimeError):
    pass


def run(argv, *, cancel, timeout=30, input_bytes=b'', max_output=1024 * 1024):
    if not isinstance(argv, (list, tuple)) or not argv or not Path(argv[0]).is_absolute():
        raise ValueError('explicit argv with absolute executable required')
    if timeout <= 0 or max_output <= 0 or len(input_bytes) > max_output:
        raise ValueError('invalid subprocess bounds')
    if cancel.is_set():
        raise Cancelled()
    # Anonymous temporary files are closed on every exit; no transcript is logged.
    with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as error:
        source.write(input_bytes)
        source.seek(0)
        process = subprocess.Popen(argv, stdin=source, stdout=output, stderr=error,
                                   shell=False, start_new_session=True,
                                   env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        deadline = time.monotonic() + timeout
        try:
            while True:
                if cancel.is_set():
                    raise Cancelled()
                if time.monotonic() >= deadline:
                    raise ProcessFailure('PROCESS_TIMEOUT')
                if max(os.fstat(output.fileno()).st_size, os.fstat(error.fileno()).st_size) > max_output:
                    raise ProcessFailure('PROCESS_OUTPUT_LIMIT')
                if process.poll() is not None:
                    break
                cancel.wait(0.02)
            if process.returncode:
                raise ProcessFailure('PROCESS_FAILED')
            output.seek(0)
            return output.read(max_output + 1)
        finally:
            # Kill surviving descendants even if the group leader already exited.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
