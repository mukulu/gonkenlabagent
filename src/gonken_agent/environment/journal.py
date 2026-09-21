"""Bounded content-free journal sink; slow stdout cannot stall the controller."""
from __future__ import annotations
import json
import queue
import math
import re
import sys
import threading
from typing import Mapping, TextIO
from .domain import EnvironmentMode, TransitionReason

CODES = frozenset({'ENV_ACTUATOR_TRANSITION', 'ENV_ACTUATOR_WRITE_FAILED'})
FIELDS = frozenset({'code','backend','actuator_simulated','gpio','gpio_claimed','gpio_consumer',
                   'previous','requested','relay_commanded','reason','mode','monotonic',
                   'control_temperature_c','start_c','stop_c','write_result','safe_off_result',
                   'actuator_write_errors','fan_motion_observed','physical_evidence',
                   'release_commit','configuration_sha256','process_id'})

def sanitized_event(event: Mapping[str, object]) -> dict[str, object]:
    if event.get('code') not in CODES: raise ValueError('invalid_environment_event')
    payload = {key: event[key] for key in FIELDS if key in event}
    for key in ('code','backend','gpio','gpio_consumer','reason','mode','write_result','safe_off_result'):
        value = payload.get(key)
        if value is not None and (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value)):
            raise ValueError('invalid_event_token')
    for key in ('previous','requested','relay_commanded'):
        if payload.get(key) not in {None,'on','off'}: raise ValueError('invalid_command_state')
    for key in ('monotonic','control_temperature_c','start_c','stop_c'):
        value = payload.get(key)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
            raise ValueError('invalid_event_number')
    for key in ('gpio_claimed','actuator_simulated'):
        value = payload.get(key)
        if value is not None and type(value) is not bool: raise ValueError('invalid_event_flag')
    if 'actuator_write_errors' in payload:
        value = payload['actuator_write_errors']
        if type(value) is not int or value < 0: raise ValueError('invalid_event_count')
    for key, allowed in (
            ('backend', {'libgpiod','simulated','host_fake'}),
            ('mode', {mode.value for mode in EnvironmentMode}),
            ('reason', {reason.value for reason in TransitionReason}),
            ('write_result', {'SUCCESS','FAILED','RELEASE_FAILED'}),
            ('safe_off_result', {'SUCCESS','FAILED'}),
            ('gpio_consumer', {'gonken-environment'})):
        value = payload.get(key)
        if value is not None and value not in allowed: raise ValueError('invalid_event_enum')
    if payload.get('gpio') is not None and not re.fullmatch(r'GPIO[0-9]{1,2}', payload['gpio']):
        raise ValueError('invalid_event_gpio')
    for key, length in (('release_commit',40),('configuration_sha256',64)):
        value = payload.get(key)
        if value is not None and value != 'unknown' and (not isinstance(value,str) or not re.fullmatch('[0-9a-f]{'+str(length)+'}', value)):
            raise ValueError('invalid_event_identity')
    if 'process_id' in payload and (type(payload['process_id']) is not int or payload['process_id'] <= 0):
        raise ValueError('invalid_event_process')
    payload['fan_motion_observed'] = payload['physical_evidence'] = False
    return payload

def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value: raise ValueError('duplicate_event_key')
        value[key] = item
    return value


def parse_event_line(line: str) -> dict[str, object] | None:
    """Parse only bounded, typed actuator metadata; never export raw journal text."""
    if not line.startswith('{') or len(line.encode('utf-8', errors='replace')) > 4096:
        return None
    try:
        event = json.loads(line, object_pairs_hook=_unique_pairs,
                           parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite')))
        if not isinstance(event,dict): return None
        return sanitized_event(event)
    except (ValueError, TypeError, OverflowError):
        return None


class EnvironmentEventJournal:
    def __init__(self, stream: TextIO | None = None, capacity: int = 64):
        if type(capacity) is not int or not 1 <= capacity <= 256: raise ValueError('invalid_queue_capacity')
        self.stream = sys.stdout if stream is None else stream
        self.queue: queue.Queue[str] = queue.Queue(capacity)
        self.stop = threading.Event()
        self.dropped_events = 0
        self.thread = threading.Thread(target=self._run, name='gonken-environment-journal', daemon=True)
        self.thread.start()

    def __call__(self, event: Mapping[str, object]) -> None:
        if self.stop.is_set(): self.dropped_events += 1; return
        # Unknown fields (including transcript/answer/exception text) never reach stdout.
        payload = sanitized_event(event)
        text = json.dumps(payload, sort_keys=True, ensure_ascii=True, allow_nan=False)
        if len(text.encode()) > 4096: raise ValueError('environment_event_oversized')
        try: self.queue.put_nowait(text)
        except queue.Full: self.dropped_events += 1

    def _run(self):
        while not self.stop.is_set() or not self.queue.empty():
            try: text = self.queue.get(timeout=0.1)
            except queue.Empty: continue
            try:
                self.stream.write(text + '\n'); self.stream.flush()
            except Exception:
                self.dropped_events += 1
                self.stop.set()
                return
            finally: self.queue.task_done()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=1.0)

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
