#!/usr/bin/env python3
"""Check the local source contract; never pretend this verifies a live remote."""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

ORIGINS = {'git@github.com:mukulu/gonkenlabagent.git', 'https://github.com/mukulu/gonkenlabagent.git'}
AUTHOR = 'John Francis Mukulu'
EMAIL = 'john.f.mukulu@gmail.com'

def check(root: Path, allow_dirty: bool = False) -> dict:
    def git(*args):
        return subprocess.check_output(['git','-C',str(root),*args], stderr=subprocess.DEVNULL, text=True, timeout=15).strip()
    errors=[]
    try:
        branch=git('symbolic-ref','--short','HEAD')
        commit=git('rev-parse','HEAD')
        tree=git('rev-parse','HEAD^{tree}')
        origin=git('config','--get','remote.origin.url')
        if origin not in ORIGINS: errors.append('ORIGIN_NOT_CANONICAL')
        if git('config','user.name') != AUTHOR or git('config','user.email') != EMAIL: errors.append('LOCAL_IDENTITY_MISMATCH')
        if git('log','-1','--format=%an|%ae|%cn|%ce') != f'{AUTHOR}|{EMAIL}|{AUTHOR}|{EMAIL}': errors.append('HEAD_AUTHORSHIP_MISMATCH')
        if not allow_dirty and git('status','--porcelain'): errors.append('WORKTREE_DIRTY')
        if git('rev-parse','--is-shallow-repository') != 'false': errors.append('SHALLOW_HISTORY')
        if not (root/'.git').is_dir(): errors.append('PORTABLE_GIT_DIRECTORY_REQUIRED')
    except (OSError,subprocess.SubprocessError):
        return {'status':'FAIL','errors':['GIT_CONTRACT_UNREADABLE'],'remote_verified':False}
    return {'status':'FAIL' if errors else 'PASS','branch':branch,'commit':commit,'tree':tree,'errors':errors,'remote_verified':False,'physical_acceptance':False}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); p.add_argument('--allow-dirty',action='store_true')
    a=p.parse_args(argv); value=check(a.root,a.allow_dirty); print(json.dumps(value,sort_keys=True)); return 0 if value['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
