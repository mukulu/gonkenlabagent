"""Canonical, non-actuating validation of published voice runtime identity.

A status file is not a heartbeat. A long-lived READY remains valid only while
its exact boot, process-start identity and selected immutable release match.
Consumers receive an allow-listed projection, never arbitrary file contents.
This stdlib-only module is also copied into the sealed maintenance payload.
"""
from __future__ import annotations

import json
import os
import re
import stat
import time
from pathlib import Path
from typing import Callable, NamedTuple

READY_FILE = Path('/run/gonken-agent/ready.json')
READINESS_FILE = Path('/run/gonken-agent/readiness.json')
CURRENT_LINK = Path('/usr/local/lib/gonken-agent/current')
BOOT_ID_FILE = Path('/proc/sys/kernel/random/boot_id')
COMMIT_RE = re.compile(r'[0-9a-f]{40}')
PROFILE_RE = re.compile(r'[a-z0-9][a-z0-9_.-]{0,63}')
BOOT_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
CODE_RE = re.compile(r'[A-Z0-9_]{3,64}')
MODEL_RE = re.compile(r'[A-Za-z0-9_./:@+-]{1,128}')


class Binding(NamedTuple):
    commit: str | None
    profile: str | None
    boot_id: str | None


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate JSON key')
        value[key] = item
    return value


def bounded_json(path: Path, limit: int = 8192) -> dict | None:
    """Refuse symlinks, FIFOs, oversized input and ambiguous JSON without blocking."""
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            return None
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            return None
        value = json.loads(raw, object_pairs_hook=_unique_object,
                           parse_constant=lambda _value: (_ for _ in ()).throw(ValueError('nonfinite')))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, UnicodeError, RecursionError):
        return None
    finally:
        if fd is not None:
            os.close(fd)


def process_start_ticks(pid: int) -> int | None:
    if type(pid) is not int or pid <= 1:
        return None
    try:
        text = Path(f'/proc/{pid}/stat').read_text(encoding='ascii')
        fields = text[text.rfind(')') + 2:].split()
        # Do not accept a zombie as a live producer merely because /proc exists.
        if fields[0] in {'Z', 'X', 'x'}:
            return None
        value = int(fields[19])
        return value if value > 0 else None
    except (OSError, ValueError, UnicodeError, IndexError):
        return None


def current_boot_id(path: Path | None = None) -> str | None:
    try:
        value = (path or BOOT_ID_FILE).read_text(encoding='ascii').strip().lower()
        return value if BOOT_RE.fullmatch(value) else None
    except (OSError, UnicodeError):
        return None


def current_release_identity(current: Path | None = None) -> tuple[str | None, str | None]:
    current = current or CURRENT_LINK
    try:
        if not current.is_symlink():
            return None, None
        target = os.readlink(current)
        match = re.fullmatch(r'releases/([0-9a-f]{40})', target)
        if not match:
            return None, None
        release = current.parent / target
        if release.is_symlink() or release.resolve(strict=True) != release:
            return None, None
        record = release / 'release.record'
        if record.is_symlink() or not record.is_file() or record.stat().st_size > 16384:
            return None, None
        values = {}
        for line in record.read_text(encoding='utf-8').splitlines():
            key, sep, value = line.partition('=')
            if not sep or key in values:
                return None, None
            values[key] = value
        if (values.get('format') != 'gonken-release-v1' or values.get('commit') != match[1]
                or values.get('validation') != 'passed' or not PROFILE_RE.fullmatch(values.get('profile', ''))):
            return None, None
        return match[1], values['profile']
    except (OSError, UnicodeError):
        return None, None


def current_binding() -> Binding:
    commit, profile = current_release_identity()
    return Binding(commit, profile, current_boot_id())


def validate_record(value: object, binding: Binding, *,
                    start_ticks: Callable[[int], int | None] | None = None,
                    now_epoch: int | None = None) -> dict | None:
    """Pure shape/identity gate, with the live process reader injected for tests."""
    if not isinstance(value, dict):
        return None
    if (not isinstance(binding.commit, str) or not COMMIT_RE.fullmatch(binding.commit)
            or not isinstance(binding.profile, str) or not PROFILE_RE.fullmatch(binding.profile)
            or not isinstance(binding.boot_id, str) or not BOOT_RE.fullmatch(binding.boot_id)):
        return None
    if (value.get('release_commit') != binding.commit or value.get('release_profile') != binding.profile
            or value.get('boot_id') != binding.boot_id):
        return None
    pid, ticks, observed = (value.get(k) for k in ('service_pid', 'service_start_ticks', 'observed_epoch'))
    if (type(pid) is not int or pid <= 1 or type(ticks) is not int or ticks <= 0
            or type(observed) is not int or observed <= 0):
        return None
    if (start_ticks or process_start_ticks)(pid) != ticks:
        return None
    if observed > (int(time.time()) if now_epoch is None else now_epoch) + 5:
        return None
    status_value, code = value.get('status'), value.get('code')
    if status_value not in {'READY', 'WAITING'} or not isinstance(code, str) or not CODE_RE.fullmatch(code):
        return None
    result = {key: value[key] for key in ('status', 'code', 'release_commit', 'release_profile',
                                         'boot_id', 'service_pid', 'service_start_ticks', 'observed_epoch')}
    for key, pattern in (('audio_backend', PROFILE_RE), ('model', MODEL_RE),
                         ('component', PROFILE_RE), ('interaction_mode', PROFILE_RE)):
        text = value.get(key)
        if isinstance(text, str) and pattern.fullmatch(text):
            result[key] = text
    phrase = value.get('wake_phrase')
    if isinstance(phrase, str) and 0 < len(phrase.strip()) <= 64 and all(c.isalnum() or c in ' -_' for c in phrase):
        result['wake_phrase'] = phrase
    digest = value.get('model_digest')
    if isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest):
        result['model_digest'] = digest
    if value.get('format') == 'gonken-voice-readiness-v1':
        result['format'] = value['format']
    if type(value.get('recoverable')) is bool:
        result['recoverable'] = value['recoverable']
    return result


def read_state(path: Path, *, expected_status: str | None = None, binding: Binding | None = None) -> dict | None:
    value = validate_record(bounded_json(path), binding or current_binding())
    if value is None or (expected_status is not None and value['status'] != expected_status):
        return None
    return value


def read_pending(path: Path | None = None, *, binding: Binding | None = None) -> dict | None:
    value = read_state(path or READINESS_FILE, binding=binding)
    if (value is None or value.get('format') != 'gonken-voice-readiness-v1'
            or 'component' not in value or type(value.get('recoverable')) is not bool):
        return None
    return value


def read_ready(path: Path | None = None, *, binding: Binding | None = None,
               pending_path: Path | None = None) -> dict | None:
    binding = binding or current_binding()
    value = read_state(path or READY_FILE, expected_status='READY', binding=binding)
    if value is None or value['code'] != 'VOICE_RUNTIME_READY' or not value.get('wake_phrase'):
        return None
    pending = read_pending(pending_path, binding=binding)
    if (pending and pending['status'] == 'WAITING' and pending['service_pid'] == value['service_pid']
            and pending['service_start_ticks'] == value['service_start_ticks']
            and pending['observed_epoch'] >= value['observed_epoch']):
        return None
    return value
