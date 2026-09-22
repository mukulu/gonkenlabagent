"""Explicit, session-bound power confirmation and a fixed logind adapter.

The model has no execution route here. Acknowledgement audio must complete before
execute_confirmed is called. The environment daemon remains the sole relay owner.
"""
from __future__ import annotations

import json
import math
import os
import re
import secrets
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
from .runtime_readiness import current_boot_id
from .release_identity import runtime_release_identity
from .command_intents import normalized

ACTIONS = {'REBOOT_DEVICE':'Reboot', 'POWEROFF_DEVICE':'PowerOff'}
CONFIRM = {'REBOOT_DEVICE':'confirm restart', 'POWEROFF_DEVICE':'confirm shutdown'}

class PowerError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)

@dataclass(frozen=True)
class Authorization:
    id: str
    action: str
    session: str
    expires: float


def power_intent(text: str) -> str | None:
    value = normalized(text)
    if value is None: return None
    if re.fullmatch(r'(?:restart|reboot) (?:the )?(?:raspberry pi|device|system)(?: now)?', value): return 'REBOOT_DEVICE'
    if re.fullmatch(r'(?:shut down|shutdown|power off) (?:the )?(?:raspberry pi|device|system)(?: now)?', value): return 'POWEROFF_DEVICE'
    return None


def power_related(text: str) -> bool:
    value = normalized(text) or ''
    if re.fullmatch(r'power off (?:the )?(?:room )?fan', value): return False
    return bool(power_intent(text) or re.search(r'\b(?:reboot|restart|shutdown|shut down|power off|confirm restart|confirm shutdown)\b', value) or value in {'cancel','cancel restart','cancel shutdown'})


class PowerSession:
    def __init__(self, *, enabled: bool = False, clock=time.monotonic, ttl: float = 20.0):
        if type(enabled) is not bool or type(ttl) not in (float,int) or not math.isfinite(ttl) or not 5 <= ttl <= 30:
            raise ValueError('invalid_power_policy')
        self.enabled=enabled; self.clock=clock; self.ttl=ttl
        self.session=secrets.token_hex(16); self.pending: Authorization|None=None; self.armed: Authorization|None=None

    def begin(self) -> None:
        self.session=secrets.token_hex(16); self.cancel()

    def cancel(self) -> None:
        self.pending=None; self.armed=None

    def handle(self, text: str) -> str | None:
        value=normalized(text) or ''
        action=power_intent(text)
        # A new direct request replaces a pending action, never confirms it.
        if action:
            self.cancel()
            if not self.enabled: return 'Voice power control is disabled. No power action was requested.'
            self.pending=Authorization(secrets.token_hex(16),action,self.session,self.clock()+self.ttl)
            name='Restart' if action=='REBOOT_DEVICE' else 'Shut down'
            return f'{name} the Raspberry Pi now? Say {CONFIRM[action]} or cancel.'
        if value in {'cancel','cancel restart','cancel shutdown'}:
            self.cancel(); return 'Power action cancelled.'
        if value.startswith('confirm '):
            pending=self.pending
            self.pending=None; self.armed=None
            if pending is None or pending.session != self.session or self.clock() >= pending.expires:
                return 'There is no current power request to confirm.'
            if value != CONFIRM[pending.action]: return 'Confirmation did not match. Power action cancelled.'
            self.armed=pending
            return 'Restarting now.' if pending.action=='REBOOT_DEVICE' else 'Shutting down now.'
        if self.pending or self.armed:
            self.cancel()
        if power_related(text):
            return 'No power action was taken. Use restart the Raspberry Pi or shut down the Raspberry Pi, then the matching confirmation.'
        return None

    def consume(self) -> Authorization | None:
        action=self.armed; self.armed=None
        if action is None: return None
        if self.clock() >= action.expires or action.session != self.session:
            raise PowerError('POWER_CONFIRMATION_EXPIRED')
        return action


def audit(record: dict, directory: Path) -> None:
    """One bounded atomic content-free action record, external to the release."""
    directory=Path(directory)
    if directory.is_symlink(): raise PowerError('POWER_AUDIT_UNSAFE')
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    st=directory.stat()
    if st.st_uid != os.geteuid() or st.st_mode & 0o022: raise PowerError('POWER_AUDIT_UNSAFE')
    path=directory/'last-action.json'
    if path.is_symlink(): raise PowerError('POWER_AUDIT_UNSAFE')
    data=json.dumps(record,sort_keys=True).encode()
    if len(data)>4096: raise PowerError('POWER_AUDIT_TOO_LARGE')
    fd,tmp=tempfile.mkstemp(prefix='.power-',dir=directory)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
        dfd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def logind_action(action: str, *, run=subprocess.run, effective_uid=os.geteuid) -> None:
    if action not in ACTIONS: raise PowerError('POWER_ACTION_INVALID')
    if effective_uid() == 0: raise PowerError('POWER_RUN_AS_GONKEN_AGENT_NOT_ROOT')
    argv=['/usr/bin/busctl','--system','--timeout=5','call','org.freedesktop.login1',
          '/org/freedesktop/login1','org.freedesktop.login1.Manager',ACTIONS[action],'b','false']
    try:
        result=run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                   timeout=6,check=False,env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'})
    except subprocess.TimeoutExpired as exc: raise PowerError('POWER_REQUEST_OUTCOME_UNKNOWN') from exc
    except OSError as exc: raise PowerError('POWER_HELPER_UNAVAILABLE') from exc
    if result.returncode != 0: raise PowerError('POWER_DENIED_OR_INHIBITED')


def execute_confirmed(authorization: Authorization, *, client_factory, environment_required: bool,
                      real_environment: bool = False, audit_dir: Path = Path('/var/lib/gonken-agent/runtime/power'),
                      execute=logind_action, clock=time.monotonic) -> dict:
    if (not isinstance(authorization,Authorization) or authorization.action not in ACTIONS
            or clock()>=authorization.expires): raise PowerError('POWER_CONFIRMATION_EXPIRED')
    client=None; token=None
    record={'format':'gonken-power-action-v1','action_id':authorization.id,'action':authorization.action,
            'status':'PREPARING','content_logging':False,'physical_acceptance_claimed':False,
            'created_at':datetime.now(timezone.utc).isoformat(), 'boot_id':current_boot_id(),
            'release_commit':runtime_release_identity().commit}
    try:
        if environment_required:
            client=client_factory()
            health=client.health()
            provenance=health.get('provenance',{})
            if real_environment and (provenance.get('actuator_backend')!='libgpiod' or provenance.get('actuator_is_simulated') is not False):
                raise PowerError('POWER_ENVIRONMENT_IDENTITY_MISMATCH')
            prepared=client.prepare_power(authorization.action)
            token=prepared.get('token')
            if (prepared.get('safe_off_acknowledged') is not True or not isinstance(token,str)
                    or not re.fullmatch('[0-9a-f]{32}', token) or prepared.get('action') != authorization.action):
                raise PowerError('POWER_SAFE_OFF_NOT_ACKNOWLEDGED')
            final_provenance=prepared.get('provenance',{})
            if real_environment and (final_provenance.get('actuator_backend')!='libgpiod' or final_provenance.get('actuator_is_simulated') is not False):
                raise PowerError('POWER_ENVIRONMENT_IDENTITY_CHANGED')
        if clock()>=authorization.expires: raise PowerError('POWER_CONFIRMATION_EXPIRED')
        record['status']='AUTHORIZED_SAFE_OFF'
        audit(record,audit_dir)
        execute(authorization.action)
        record['status']='REQUESTED'
        # The process may be terminated after logind accepts. The preceding
        # fsynced authorization record survives even when this update cannot.
        try: audit(record,audit_dir)
        except Exception: pass
        return record
    except Exception as exc:
        if client is not None and token is not None:
            try: client.release_power(token)
            except Exception: pass
        record['status']='FAILED_OR_UNCERTAIN'
        record['code']=exc.code if isinstance(exc,PowerError) else 'POWER_PREPARATION_FAILED'
        try: audit(record,audit_dir)
        except Exception: pass
        if isinstance(exc,PowerError): raise
        raise PowerError('POWER_PREPARATION_FAILED') from exc
