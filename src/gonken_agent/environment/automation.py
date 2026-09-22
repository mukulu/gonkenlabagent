"""Bounded daemon-owned timers and numeric notifications; no device or audio I/O.

The environment service supplies its authoritative snapshot and its existing
actuator path. Jobs are monotonic and boot-scoped. There is no shell, eval, cron,
raw GPIO access, persistent conversation content or replay after restart.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import secrets
from typing import Callable, Mapping, Any

MAX_JOBS = 32
MAX_DELAY_SECONDS = 86400
MAX_LEASE_SECONDS = 28800
MIN_REPEAT_SECONDS = 60
MAX_NOTICES = 32
NOTICE_TTL_SECONDS = 30
FAN_KINDS = frozenset({'fan_on', 'fan_off', 'fan_run', 'fan_cycle'})
REPORT_KINDS = frozenset({'temperature', 'humidity', 'environment', 'temperature_delta'})
KINDS = FAN_KINDS | REPORT_KINDS


class AutomationError(ValueError):
    def __init__(self, message: str):
        self.code = 'BAD_REQUEST'
        super().__init__(message)


def number(value: object, name: str, low: float, high: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise AutomationError(f'{name}_out_of_bounds')
    return float(value)


@dataclass
class Job:
    id: str
    kind: str
    due: float
    expires: float
    interval: float
    duration: float
    delta: float
    baseline: float | None
    phase: str = 'waiting'
    runs: int = 0
    pending: str | None = None


class Automation:
    """Called only while the owning daemon's lock is held."""
    def __init__(self):
        self.generation = secrets.token_hex(16)
        self.jobs: dict[str, Job] = {}
        self.history: deque[dict] = deque(maxlen=32)
        self.notices: dict[str, dict] = {}
        self.receipts: dict[str, dict] = {}
        self.last_announced_temperature: float | None = None
        self.dropped_notices = 0

    @staticmethod
    def reading(snapshot: Mapping[str, Any], now: float) -> dict | None:
        if snapshot.get('sensor_quality') != 'ready': return None
        reading = snapshot.get('last_reading')
        if (not isinstance(reading, dict) or reading.get('valid') is not True
                or reading.get('quality') not in {'ready', 'GOOD', 'good'}):
            return None
        age = reading.get('age_seconds')
        temperature, humidity = reading.get('temperature_c'), reading.get('relative_humidity_pct')
        if (type(age) not in (int, float) or not math.isfinite(age) or not 0 <= age <= 10
                or type(temperature) not in (int, float) or not math.isfinite(temperature)
                or type(humidity) not in (int, float) or not math.isfinite(humidity)):
            return None
        return {'temperature_c': float(temperature), 'relative_humidity_pct': float(humidity),
                'observed_monotonic': now - age}

    def add(self, params: Mapping[str, Any], *, now: float, snapshot: dict,
            minimum_on: float, minimum_off: float) -> dict:
        allowed = {'kind', 'delay_seconds', 'interval_seconds', 'duration_seconds', 'lease_seconds', 'delta_c'}
        if set(params) - allowed:
            raise AutomationError('unknown_schedule_parameter')
        kind = params.get('kind')
        if not isinstance(kind, str) or kind not in KINDS:
            raise AutomationError('unknown_schedule_kind')
        if len(self.jobs) >= MAX_JOBS:
            raise AutomationError('schedule_capacity_reached')
        delay = number(params.get('delay_seconds', 0), 'delay_seconds', 0, MAX_DELAY_SECONDS)
        interval = number(params.get('interval_seconds', 0), 'interval_seconds', 0, 3600)
        duration = number(params.get('duration_seconds', 0), 'duration_seconds', 0, MAX_DELAY_SECONDS)
        delta = number(params.get('delta_c', 2), 'delta_c', 0.5, 10)
        lease = number(params.get('lease_seconds', MAX_LEASE_SECONDS), 'lease_seconds', 60, MAX_LEASE_SECONDS)
        if interval and interval < MIN_REPEAT_SECONDS:
            raise AutomationError('repeat_interval_too_short')
        if kind in {'fan_on', 'fan_off'} and (interval or duration or 'delta_c' in params or 'lease_seconds' in params):
            raise AutomationError('one_shot_fan_does_not_repeat')
        if kind == 'fan_run' and (duration < minimum_on or interval or 'delta_c' in params or 'lease_seconds' in params):
            raise AutomationError('fan_duration_must_respect_minimum_on')
        if kind == 'fan_cycle' and (not interval or interval < max(minimum_on, minimum_off) or duration or 'delta_c' in params):
            raise AutomationError('fan_cycle_must_respect_dwell')
        if kind in REPORT_KINDS and duration:
            raise AutomationError('report_duration_not_applicable')
        if kind != 'temperature_delta' and 'delta_c' in params:
            raise AutomationError('delta_only_for_temperature_change')
        if kind == 'temperature_delta' and (interval or delay):
            raise AutomationError('temperature_change_is_not_a_time_interval')
        if kind in FAN_KINDS:
            if snapshot.get('mode') == 'disabled':
                raise AutomationError('controller_disabled')
            composites = {'fan_run', 'fan_cycle'}
            if any(j.kind in FAN_KINDS and (j.kind in composites or kind in composites) for j in self.jobs.values()):
                raise AutomationError('cancel_existing_fan_schedule_first')
        reading = self.reading(snapshot, now)
        if kind == 'temperature_delta' and reading is None:
            raise AutomationError('fresh_temperature_required_for_change_alert')
        # Repeating jobs have a finite lease. One-shots are allowed their delay,
        # plus sufficient dwell grace, never an unbounded late catch-up loop.
        repeating = bool(interval) or kind == 'temperature_delta'
        expires = now + delay + (lease if repeating else duration + max(60, minimum_on, minimum_off) + 30)
        job_id = secrets.token_hex(4)
        while job_id in self.jobs: job_id = secrets.token_hex(4)
        job = Job(job_id, kind, now + delay, expires, interval, duration, delta,
                  self.last_announced_temperature if self.last_announced_temperature is not None else
                  (reading['temperature_c'] if reading else None))
        self.jobs[job.id] = job
        return self._public(job, now)

    def _finish(self, job: Job, status: str, now: float) -> None:
        self.jobs.pop(job.id, None)
        if job.pending:
            self.notices.pop(job.pending, None); self.receipts.pop(job.pending, None)
        self.history.append({'id': job.id, 'kind': job.kind, 'status': status, 'runs': job.runs})

    def cancel(self, *, now: float, job_id: str | None = None, fan_only: bool = False) -> list[str]:
        if job_id is not None and (not isinstance(job_id, str) or job_id not in self.jobs):
            raise AutomationError('timer_not_found')
        cancelled = []
        for job in list(self.jobs.values()):
            if (job_id is None or job.id == job_id) and (not fan_only or job.kind in FAN_KINDS):
                cancelled.append(job.id); self._finish(job, 'CANCELLED', now)
        return cancelled

    def _expire_notices(self, now: float) -> None:
        for token, receipt in list(self.receipts.items()):
            if receipt['expires_monotonic'] <= now:
                self.receipts.pop(token, None)
                if self.notices.pop(token, None) is not None: self.dropped_notices += 1

    def _receipt(self, kind: str, reading: dict, now: float, job_id: str | None) -> dict:
        self._expire_notices(now)
        while len(self.receipts) >= MAX_NOTICES * 2:
            token = next(iter(self.receipts)); self.receipts.pop(token)
            if self.notices.pop(token, None) is not None: self.dropped_notices += 1
        token = secrets.token_hex(16)
        receipt = dict(reading, id=token, generation=self.generation, kind=kind, job_id=job_id,
                       expires_monotonic=min(now + NOTICE_TTL_SECONDS, reading['observed_monotonic'] + NOTICE_TTL_SECONDS))
        self.receipts[token] = receipt
        return receipt

    def reading_receipt(self, snapshot: dict, *, now: float) -> dict | None:
        """A query can acknowledge a spoken numeric reading without storing text."""
        reading = self.reading(snapshot, now)
        if reading is None: return None
        r = self._receipt('temperature', reading, now, None)
        return {'id': r['id'], 'generation': r['generation']}

    def acknowledge(self, token: str, generation: str, *, now: float) -> bool:
        self._expire_notices(now)
        if generation != self.generation or not isinstance(token, str) or len(token) != 32:
            raise AutomationError('notification_identity_invalid')
        receipt = self.receipts.pop(token, None)
        if receipt is None: return False
        self.notices.pop(token, None)
        if receipt['kind'] in {'temperature', 'environment', 'temperature_delta'}:
            self.last_announced_temperature = receipt['temperature_c']
        job = self.jobs.get(receipt['job_id'])
        if job is not None and job.pending == token:
            job.pending = None
            job.baseline = receipt['temperature_c']
        return True

    def pending_notifications(self, *, now: float) -> dict:
        self._expire_notices(now)
        return {'generation': self.generation, 'notifications': list(self.notices.values())[:8],
                'dropped': self.dropped_notices}

    def _notify(self, job: Job, reading: dict, now: float) -> None:
        receipt = self._receipt(job.kind, reading, now, job.id)
        while len(self.notices) >= MAX_NOTICES:
            token = next(iter(self.notices)); self.notices.pop(token); self.receipts.pop(token, None)
            self.dropped_notices += 1
        self.notices[receipt['id']] = receipt
        job.pending = receipt['id']

    def tick(self, *, now: float, snapshot: dict, minimum_on: float, minimum_off: float,
             fan_write: Callable[[str, str], None]) -> None:
        """Run bounded due work after the owner's ordinary sensor/control cycle."""
        self._expire_notices(now)
        reading = self.reading(snapshot, now)
        fan_power = str(snapshot.get('fan_power', 'off'))
        last_transition = snapshot.get('last_transition_monotonic')
        if type(last_transition) not in (float, int) or not math.isfinite(last_transition): last_transition = now
        for job in sorted(list(self.jobs.values()), key=lambda j: (j.due, j.id)):
            if job.id not in self.jobs: continue
            if job.expires <= now:
                if job.kind in {'fan_run', 'fan_cycle'} and job.phase == 'on':
                    fan_write('off', 'TIMER_EXPIRED_SAFE_OFF'); fan_power='off'; last_transition=now
                self._finish(job, 'EXPIRED', now); continue
            if job.kind in FAN_KINDS and (snapshot.get('mode') == 'disabled' or reading is None):
                # Core sensor safety already commands OFF. Never re-arm an old ON
                # timer when the sensor later recovers.
                self._finish(job, 'CANCELLED_SENSOR_OR_MODE', now); continue
            if job.kind == 'temperature_delta':
                if reading is None: continue
                if job.pending in self.receipts: continue
                baseline = self.last_announced_temperature if self.last_announced_temperature is not None else job.baseline
                if baseline is not None and reading['temperature_c'] - baseline >= job.delta:
                    self._notify(job, reading, now); job.runs += 1
                continue
            if job.due > now: continue
            if job.kind in REPORT_KINDS:
                if reading is None:
                    if not job.interval: self._finish(job, 'FAILED_SENSOR_UNAVAILABLE', now)
                    else: job.due = now + job.interval
                    continue
                if job.pending in self.receipts:
                    # Slow voice consumer: retain one outstanding notification.
                    job.due = now + (job.interval or MIN_REPEAT_SECONDS); continue
                self._notify(job, reading, now); job.runs += 1
                if job.interval:
                    job.due = now + job.interval  # no catch-up burst
                else:
                    # Keep the receipt for acknowledgement, not an active job.
                    self.jobs.pop(job.id)
                    self.history.append({'id':job.id,'kind':job.kind,'status':'NOTIFICATION_QUEUED','runs':job.runs})
                continue
            target = ('on' if job.kind == 'fan_on' else 'off' if job.kind == 'fan_off'
                      else 'off' if job.phase == 'on' else 'on')
            dwell = minimum_on if fan_power == 'on' else minimum_off
            earliest = float(last_transition) + dwell
            if target != fan_power and now < earliest:
                job.due = earliest; continue
            fan_write(target, 'TIMER_' + job.kind.upper())
            if target != fan_power: last_transition = now
            fan_power = target; job.runs += 1; job.phase = target
            if job.kind in {'fan_on','fan_off'} or (job.kind == 'fan_run' and target == 'off'):
                self._finish(job, 'COMPLETED', now)
            elif job.kind == 'fan_run':
                job.due = now + job.duration
                job.expires = job.due + minimum_on + 30
            else:
                job.due = now + job.interval

    @staticmethod
    def _public(job: Job, now: float) -> dict:
        return {'id':job.id,'kind':job.kind,'due_in_seconds':max(0,job.due-now),
                'expires_in_seconds':max(0,job.expires-now),'interval_seconds':job.interval,
                'duration_seconds':job.duration,'delta_c':job.delta if job.kind=='temperature_delta' else None,
                'phase':job.phase,'runs':job.runs}

    def status(self, *, now: float) -> dict:
        return {'generation':self.generation,'jobs':[self._public(j,now) for j in self.jobs.values()],
                'history':list(self.history),'pending_notifications':len(self.notices),
                'dropped_notifications':self.dropped_notices,'persistent':False,
                'physical_acceptance_claimed':False,'fan_policy':'session_manual_override_no_replay'}
