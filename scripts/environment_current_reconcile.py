#!/usr/bin/env python3
"""Reconcile an existing thermostat before unrelated model provisioning.

This is an independent, best-effort upgrade phase, NOT candidate activation.
A missing/incompatible current release is explicitly deferred; final candidate
commissioning/readiness remains mandatory. Only the existing environment service
owns hardware. No arbitrary GPIO process is killed and no relay is driven here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import environment_service_manager as services
import environment_readiness as readiness
import environment_policy_manager as policy
import release_manager as releases

FORMAT = 'gonken-existing-environment-reconciliation-v1'


def _inputs(root: Path, release_root: Path, candidate: str, mode: str, start_c=None, stop_c=None) -> dict:
    if not re.fullmatch('[0-9a-f]{40}', candidate) or mode not in policy.MODES:
        raise ValueError('invalid_reconciliation_identity')
    digest = hashlib.sha256()
    for rel in ('etc/gonken-agent/config.toml', 'etc/gonken-agent/environment'):
        path = root / rel
        if path.is_symlink(): raise ValueError('unsafe_configuration_path')
        digest.update(rel.encode())
        if path.exists():
            if not path.is_file() or path.stat().st_size > 65536: raise ValueError('unsafe_configuration_size')
            digest.update(path.read_bytes())
    return {'candidate_commit': candidate, 'current_commit': releases.current_commit(release_root),
            'configuration_inputs_sha256': digest.hexdigest(), 'mode_requested': mode, 'thresholds_requested': [start_c, stop_c]}


def _invocation(systemctl: Path) -> str:
    result = services.run_tool(systemctl, 'show', '--property=InvocationID', '--value', services.SERVICE_NAME)
    value = result.stdout.strip()
    if not re.fullmatch('[0-9a-f]{32}', value): raise ValueError('service_invocation_unavailable')
    return value


def _save(path: Path, data: dict) -> None:
    if path.is_symlink() or path.parent.is_symlink(): raise ValueError('unsafe_reconciliation_record')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix='.environment-current.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, indent=2, sort_keys=True); stream.write('\n')
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def reconcile(root: Path, release_root: Path, state_root: Path, candidate: str,
              mode: str, unit: Path, tmpfiles: Path, *, systemctl: Path = Path('/usr/bin/systemctl'),
              check: bool = False, start_c=None, stop_c=None) -> dict:
    """Return truthful phase outcome; failures do not block new candidate repair."""
    record_path = state_root / 'environment-current-reconciliation.json'
    identity = _inputs(root, release_root, candidate, mode, start_c, stop_c)
    if check:
        if record_path.is_symlink() or not record_path.is_file() or record_path.stat().st_size > 16384:
            raise ValueError('reconciliation_not_recorded')
        record = json.loads(record_path.read_text(), object_pairs_hook=readiness._pairs)
        if (record.get('format') != FORMAT or record.get('inputs') != identity
                or record.get('physical_acceptance_claimed') is not False
                or record.get('status') not in {'READY_EXISTING_ENVIRONMENT', 'DEFERRED_NO_CURRENT', 'DEGRADED_EXISTING_ENVIRONMENT'}):
            raise ValueError('reconciliation_record_stale')
        if record['status'] == 'READY_EXISTING_ENVIRONMENT':
            if record.get('invocation_id') != _invocation(systemctl): raise ValueError('service_restarted')
            agent = readiness.require_agent(str(release_root / 'releases' / identity['current_commit'] / '.venv/bin/gonken-agent'))
            services.commissioned_status(root, systemctl, 'full-real')
            readiness.probe(agent, 'full-real', timeout=5, interval=0.25)
            policy.converge(agent, mode, check=True, start_c=start_c, stop_c=stop_c)
        return record
    record = {'format': FORMAT, 'inputs': identity, 'status': 'RUNNING' if identity['current_commit'] else 'DEFERRED_NO_CURRENT',
              'physical_acceptance_claimed': False, 'global_activation_changed': False,
              'scope': 'existing_environment_only', 'reason_code': 'NO_CURRENT_RELEASE'}
    _save(record_path, record)  # reject unsafe destinations before a restart; retain interruption state
    if identity['current_commit'] is not None:
        try:
            # Current only: historical inactive releases are not prerequisites.
            releases.status(release_root, state_root, None, 'gonken-agent')
            services.validate_selected_profile(root, 'full-real')
            services.validate_installed(root, unit, tmpfiles)
            agent = readiness.require_agent(str(release_root / 'releases' / identity['current_commit'] / '.venv/bin/gonken-agent'))
            # Require a successful non-actuating parse before any service restart.
            config = readiness.read_agent(agent, ['env', 'serve', '--check', '--json'], 5)
            if config.get('enabled') is not True or config.get('hardware_toggled') is not False:
                raise ValueError('current_runtime_configuration_incompatible')
            services.run_tool(systemctl, 'daemon-reload')
            services.converge_commissioned(root, systemctl, 'full-real')
            health = readiness.probe(agent, 'full-real', timeout=30, interval=1)['health']
            selected_policy = policy.converge(agent, mode, start_c=start_c, stop_c=stop_c)
            if _inputs(root, release_root, candidate, mode, start_c, stop_c) != identity:
                raise ValueError('configuration_or_current_changed_during_reconciliation')
            record.update(status='READY_EXISTING_ENVIRONMENT', reason_code='REAL_THERMOSTAT_RECONCILED',
                          invocation_id=_invocation(systemctl), policy=selected_policy,
                          sensor_backend=health['provenance']['sensor_backend'],
                          actuator_backend=health['provenance']['actuator_backend'])
        except (releases.ReleaseError, services.EnvironmentServiceError, readiness.ReadinessError,
                OSError, ValueError, subprocess.TimeoutExpired) as exc:
            record.update(status='DEGRADED_EXISTING_ENVIRONMENT', reason_code=getattr(exc, 'code', type(exc).__name__),
                          remediation='candidate_activation_and_final_environment_checks_still_required')
    _save(record_path, record)
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--system-root', default='/')
    parser.add_argument('--release-root', required=True)
    parser.add_argument('--state-root', required=True)
    parser.add_argument('--candidate-commit', required=True)
    parser.add_argument('--mode', required=True, choices=policy.MODES)
    parser.add_argument('--unit-template', required=True)
    parser.add_argument('--tmpfiles-template', required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--start-c', type=float)
    parser.add_argument('--stop-c', type=float)
    args = parser.parse_args(argv)
    try:
        root = Path(args.system_root)
        paths = [root, Path(args.release_root), Path(args.state_root), Path(args.unit_template), Path(args.tmpfiles_template)]
        if any(not p.is_absolute() or '..' in p.parts for p in paths): raise ValueError('absolute_paths_required')
        if root == Path('/') and not args.check and os.geteuid() != 0: raise PermissionError('root_required')
        result = reconcile(*paths[:3], args.candidate_commit, args.mode, *paths[3:], check=args.check, start_c=args.start_c, stop_c=args.stop_c)
        prefix = 'OK' if result['status'] == 'READY_EXISTING_ENVIRONMENT' else 'DEFERRED'
        print(f"[{prefix}] code=ENV_CURRENT_RECONCILIATION status={result['status']} reason={result['reason_code']} "
              f"current={result['inputs']['current_commit'] or 'none'} candidate_activated=false physical_acceptance=false")
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired, releases.ReleaseError, services.EnvironmentServiceError, readiness.ReadinessError) as exc:
        print(f"[ERROR] code=ENV_CURRENT_RECONCILIATION_INVALID reason={getattr(exc, 'code', type(exc).__name__)}", file=sys.stderr)
        return 75

if __name__ == '__main__': raise SystemExit(main())
