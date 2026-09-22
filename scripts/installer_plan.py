#!/usr/bin/env python3
"""Finalize the installer phase order without granting any runtime readiness.

The registered engine owns actions/postconditions. This pure ordering function
keeps candidate preparation ahead of the current-release switch on full targets.
Release-only host/package qualification retains its narrower activation boundary.
"""
from __future__ import annotations
import argparse
import re

DEFERRED = ('activate_release', 'environment_commissioning', 'environment_readiness', 'environment_policy', 'voice_power_configuration')


def candidate_order(steps: list[str], *, platform: str, release_only: bool = False) -> list[str]:
    if (not steps or len(steps) != len(set(steps))
            or any(not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', step) for step in steps)):
        raise ValueError('invalid_or_duplicate_registered_steps')
    if platform not in {'target', 'development'}:
        raise ValueError('invalid_platform')
    if platform != 'target' or release_only or 'activate_release' not in steps:
        return list(steps)
    anchor = 'speech_smoke' if 'speech_smoke' in steps else 'ollama_model_roster'
    if anchor not in steps or 'immutable_release' not in steps:
        raise ValueError('candidate_prerequisite_anchor_missing')
    if 'environment_policy' in steps and 'environment_readiness' not in steps:
        raise ValueError('policy_requires_environment_readiness')
    if 'environment_readiness' in steps and 'environment_commissioning' not in steps:
        raise ValueError('readiness_requires_environment_commissioning')
    retained = [step for step in steps if step not in DEFERRED]
    after = retained.index(anchor) + 1
    result = retained[:after] + [step for step in DEFERRED if step in steps] + retained[after:]
    if 'application_service' in result and result.index('application_service') < result.index('activate_release'):
        raise ValueError('service_start_before_activation')
    return result


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--platform',required=True,choices=('target','development'))
    p.add_argument('--release-only',action='store_true')
    p.add_argument('steps',nargs='+')
    args=p.parse_args(argv)
    try:
        print('\n'.join(candidate_order(args.steps,platform=args.platform,release_only=args.release_only)))
        return 0
    except ValueError as exc:
        p.error(str(exc))

if __name__=='__main__':raise SystemExit(main())
