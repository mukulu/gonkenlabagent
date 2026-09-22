"""Content-free power diagnostics; reads no conversation, journal or audio data."""
from __future__ import annotations
import re
from pathlib import Path
from .power_install import RULE, RULE_NAME
from .runtime_readiness import bounded_json, current_boot_id


def collect(config, *, root: Path=Path('/')) -> dict:
    root=Path(root)
    result={'format':'gonken-power-status-v1','enabled':config.extensions.voice_power.enabled,
            'confirmation_required':True,'model_authority':False,'inhibitor_bypass':False,
            'physical_acceptance_claimed':False,'last_action':None}
    rule=root/'etc/polkit-1/rules.d'/RULE_NAME
    try:
        result['rule_matches']=not rule.is_symlink() and rule.stat().st_size<=4096 and rule.read_text()==RULE
    except (OSError,UnicodeError):result['rule_matches']=False
    result['busctl_present']=(root/'usr/bin/busctl').is_file()
    raw=bounded_json(root/'var/lib/gonken-agent/runtime/power/last-action.json',4096)
    if raw is None:return result
    statuses={'PREPARING','AUTHORIZED_SAFE_OFF','REQUESTED','FAILED_OR_UNCERTAIN'}
    if raw.get('format')!='gonken-power-action-v1' or raw.get('status') not in statuses or raw.get('action') not in {'REBOOT_DEVICE','POWEROFF_DEVICE'}:
        result['record_status']='INVALID';return result
    safe={k:raw[k] for k in ('format','action','status')}
    for key,pattern in [('action_id',r'[0-9a-f]{32}'),('code',r'[A-Z_]{3,64}'),
                        ('boot_id',r'[0-9a-f-]{36}'),('release_commit',r'(?:[0-9a-f]{40}|development)'),
                        ('created_at',r'[0-9T:.+Z-]{15,40}')]:
        value=raw.get(key)
        if isinstance(value,str) and re.fullmatch(pattern,value):safe[key]=value
    boot=current_boot_id(root/'proc/sys/kernel/random/boot_id')
    result['last_action_scope']='CURRENT_BOOT' if boot and safe.get('boot_id')==boot else 'HISTORICAL_OR_UNKNOWN'
    result['last_action']=safe
    return result
