"""Install only GonKen's fixed logind authorization rule, never execute power."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import stat
import tempfile
from .deployment import apply_preset

from .power_policy import RULE_NAME, RULE


def install(root: Path=Path('/'), *, check=False):
    root=Path(root)
    if not root.is_absolute() or root.is_symlink() or '..' in root.parts:
        raise ValueError('POWER_INSTALL_ROOT_INVALID')
    if os.geteuid()!=0: raise PermissionError('POWER_INSTALL_REQUIRES_ROOT')
    # A missing authorization agent/bus tool is a real dependency failure, not a
    # historical acceptance gate. Do not enable a non-functional power surface.
    if not (root/'usr/bin/busctl').is_file() or not (root/'usr/share/polkit-1/actions').is_dir():
        raise ValueError('POWER_DEPENDENCY_MISSING')
    parent=root/'etc/polkit-1/rules.d'; path=parent/RULE_NAME
    for candidate in (parent, path):
        if candidate.is_symlink(): raise ValueError('POWER_RULE_PATH_UNSAFE')
    if path.exists():
        if not path.is_file() or path.stat().st_uid!=0 or path.stat().st_mode&0o022:
            raise ValueError('POWER_RULE_OWNERSHIP_UNSAFE')
        if path.read_text()!=RULE: raise ValueError('POWER_RULE_ADMIN_CONFLICT')
    elif check: raise ValueError('POWER_RULE_MISSING')
    else:
        parent.mkdir(parents=True,exist_ok=True,mode=0o755)
        fd,temp=tempfile.mkstemp(prefix='.gonken-',dir=parent)
        try:
            os.fchmod(fd,0o644)
            with os.fdopen(fd,'w') as f: f.write(RULE); f.flush(); os.fsync(f.fileno())
            # No overwrite of an administrator-created concurrent file.
            os.link(temp,path)
        finally: os.unlink(temp)
    apply_preset(root/'etc/gonken-agent/config.toml',phase='power',check=check)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    args=p.parse_args(argv)
    try:
        install(check=args.check)
        print('[OK] code=VOICE_POWER_POLICY_CONFIGURED actions=reboot,poweroff confirmation=required inhibitor_bypass=false')
        return 0
    except (OSError,ValueError) as exc:
        print(f'[ERROR] code=VOICE_POWER_POLICY_FAILED reason={type(exc).__name__}')
        return 65

if __name__=='__main__': raise SystemExit(main())
