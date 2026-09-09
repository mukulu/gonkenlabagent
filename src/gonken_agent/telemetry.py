"""Strict content-free, size-bounded JSONL telemetry with process-safe rotation."""
import fcntl
import json
import math
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from .state import State

ALLOWED = {'state', 'status', 'duration_ms', 'audio_seconds', 'generated_tokens',
           'temperature_c', 'ram_bytes', 'throttled', 'source_ids', 'model', 'digest'}


def validate_event(event, allowed_source_ids=()):
    if not isinstance(event, dict) or not set(event) <= ALLOWED:
        raise ValueError('unknown telemetry field; content logging is disabled')
    for key, value in event.items():
        if key == 'state' and value not in {s.value for s in State}: raise ValueError('invalid state')
        if key == 'status' and value not in {'READY','DEGRADED','FAILED','MAINTENANCE'}: raise ValueError('invalid status')
        if key in {'duration_ms','audio_seconds','generated_tokens','temperature_c','ram_bytes'}:
            if type(value) not in (float,int) or not math.isfinite(value) or not 0 <= value <= 1e15:
                raise ValueError('invalid numeric metric')
        if key == 'throttled' and type(value) is not bool: raise ValueError('invalid throttle state')
        if key == 'source_ids' and (not isinstance(value,list) or len(value)>10 or any(type(i) is not str or i not in allowed_source_ids for i in value)):
            raise ValueError('source identifiers must come from the loaded index')
        if key == 'model' and (not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,128}',value)):
            raise ValueError('invalid model identity')
        if key == 'digest' and (not isinstance(value,str) or not re.fullmatch(r'[a-f0-9]{64}', value)):
            raise ValueError('invalid model digest')
    return json.loads(json.dumps(event, allow_nan=False))


class Telemetry:
    def __init__(self, path, allowed_source_ids=(), max_bytes=512*1024, backups=2):
        self.path = Path(path).absolute()
        if self.path.parent.resolve() != self.path.parent or not self.path.parent.is_dir():
            raise ValueError('unsafe telemetry parent')
        if not 1024 <= max_bytes <= 8*1024*1024 or not 1 <= backups <= 5:
            raise ValueError('invalid telemetry bounds')
        self.allowed = frozenset(allowed_source_ids)
        self.max_bytes, self.backups = max_bytes, backups
        self.lock = threading.Lock()

    def append(self, event):
        record = validate_event(event, self.allowed)
        record['timestamp'] = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        raw = (json.dumps(record, sort_keys=True, separators=(',',':'))+'\n').encode()
        if len(raw) > self.max_bytes: raise ValueError('telemetry record exceeds file bound')
        with self.lock:
            lockfd = os.open(str(self.path)+'.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(lockfd, fcntl.LOCK_EX)
                paths = [self.path] + [Path(str(self.path)+f'.{n}') for n in range(1,self.backups+1)]
                for path in paths:
                    if path.is_symlink() or (path.exists() and not path.is_file()): raise ValueError('unsafe telemetry path')
                if self.path.exists():
                    if self.path.stat().st_size > self.max_bytes: raise ValueError('existing telemetry exceeds bound')
                    # Recover only an interrupted final record. Never ignore middle corruption.
                    data = self.path.read_bytes()
                    good = data[:data.rfind(b'\n')+1]
                    for line in good.splitlines(): json.loads(line)
                    if len(good) != len(data):
                        fd = os.open(self.path, os.O_WRONLY | os.O_NOFOLLOW)
                        try: os.ftruncate(fd,len(good)); os.fsync(fd)
                        finally: os.close(fd)
                    if len(good) + len(raw) > self.max_bytes:
                        paths[-1].unlink(missing_ok=True)
                        for i in range(len(paths)-2,-1,-1):
                            if paths[i].exists(): os.replace(paths[i],paths[i+1])
                fd = os.open(self.path, os.O_CREAT | os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW, 0o600)
                try:
                    os.fchmod(fd,0o600)
                    view = memoryview(raw)
                    while view:
                        written = os.write(fd,view)
                        view = view[written:]
                    os.fsync(fd)
                finally: os.close(fd)
            finally: os.close(lockfd)
