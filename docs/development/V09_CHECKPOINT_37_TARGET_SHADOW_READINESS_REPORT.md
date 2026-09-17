# V09 Checkpoint 37 Report — Target-Shadow Readiness Gate

## Scope

Checkpoint 37 integrates the checkpoint-36 target-shadow replay evidence into `scripts/release_readiness.py`. The readiness script now reports `READY_FOR_HOST_TARGET_SHADOW_GATE` only when required host milestones are verified, secret scanning is clean, the worktree boundary is explicit, and required target-shadow fixtures replay with their expected results.

## Completed

- Added M10.30 and M10.31 to the release-readiness required host-verified set.
- Added executable replay checks for the checkpoint-34 duplicate-RP1-alias fixture and the distinct-duplicate-header fail-closed fixture.
- Changed readiness scope from target-acceptance wording to internal host/target-shadow gate wording.
- Added regression coverage proving target-shadow replay success is reported and target-shadow failure blocks readiness.
- Synchronized `MASTER_BLUEPRINT.md`, `DECISIONS.md`, `TEST_MATRIX.md`, `MILESTONES.json` and generated implementation status.

## Evidence Boundary

The checkpoint is host/software plus target-shadow replay evidence only. It does not create a user-facing Raspberry Pi candidate, does not claim `INSTALLATION_COMPLETE`, and does not close physical relay, fan, SHT31, wake, speech, reboot, update, rollback or reinstall acceptance.

## Verification

- `PYTHONPATH=src:. python3 -m unittest tests.unit.test_release_readiness -v`
- `python3 scripts/release_readiness.py --json --allow-dirty`
- `./scripts/ci.sh --phase t0`

Final package verification must be performed from a clean tagged clone before distribution.

## Remaining

Continue the reliability-first sequence by adding sanitized real-target manifests and expanding target-shadow replay coverage for audio fallback, service identity and dirty installer/release states. Only after the host/target-shadow release-candidate gate and exact-archive qualification are complete may a future Raspberry Pi `RELEASE_CANDIDATE` be prepared.
