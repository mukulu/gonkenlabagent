# V09 Checkpoint 38 Report — Target-Shadow Capability Replay

## Scope

Checkpoint 38 broadens target-shadow replay from GPIO identity into explicit opt-in checks for duplex audio capability, service-user identity and release-state cleanliness. It preserves the checkpoint-36/37 GPIO fixtures as historical evidence while adding capability fixtures that exercise the next failure classes before another Raspberry Pi package is considered.

## Completed

- Added `target_shadow_requirements` handling to `scripts/target_probe.py --replay`.
- Added replay sections for privacy boundary, audio duplex route, service identity and release state.
- Added a full capability-ready fixture plus fail-closed fixtures for ambiguous audio, missing service groups and dirty/invalid release state.
- Updated `scripts/release_readiness.py` so all six required replay fixtures must produce their expected status, code and exit behavior.
- Synchronized `MASTER_BLUEPRINT.md`, `DECISIONS.md`, `TEST_MATRIX.md`, `MILESTONES.json` and generated implementation status.

## Evidence Boundary

This is host/software and target-shadow replay evidence only. It does not create a Raspberry Pi release candidate, does not claim Bluetooth success, does not prove physical microphone/speaker behavior, does not claim `INSTALLATION_COMPLETE`, and does not close relay, fan, SHT31, wake, reboot, update, rollback or reinstall acceptance.

## Verification

- `PYTHONPATH=src:. python3 -m unittest tests.unit.test_v09_target_probe -v`
- `PYTHONPATH=src:. python3 -m unittest tests.unit.test_release_readiness -v`

Final checkpoint verification must rerun adjacent gates, static checks, T0 and package verification from a clean tagged clone.

## Remaining

Continue the reliability-first sequence by adding sanitized real-target manifests, expanding dirty-state/model-based installer fixtures and qualifying the exact archive. A future Raspberry Pi `RELEASE_CANDIDATE` remains blocked until the complete host/target-shadow release-candidate gate is satisfied.
