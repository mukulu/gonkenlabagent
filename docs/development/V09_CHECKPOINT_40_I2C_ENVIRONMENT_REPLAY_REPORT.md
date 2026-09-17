# V09 Checkpoint 40 — I2C/SHT31 and Environment Profile Target-Shadow Replay

## Scope

Checkpoint 40 executes the next dependency-ready reliability batch after exact archive qualification. It expands `target_probe.py --replay` and release readiness to cover I2C/SHT31 and static environment-profile semantics while preserving the rule that replay evidence is not Raspberry Pi physical acceptance.

## Changes

- Added opt-in `target_shadow_requirements.i2c_sht31` replay validation for `/dev/i2c-1`, supported SHT31 address evidence, heater-off status and planned `I2C_REBOOT_REQUIRED` pause states.
- Added opt-in `target_shadow_requirements.environment_profile` validation for `full-simulation`, `sensor-deferred-relay`, `real-sensor-simulated-actuator` and `full-real`.
- Added replay fixtures for full-real ready, planned I2C reboot, absent SHT31, missing full-real relay GPIO23 evidence and simulation-safe profile handling.
- Expanded `release_readiness.py` to require 11 target-shadow fixtures and M10.35 host verification.
- Updated the blueprint, decisions, milestone ledger, test matrix and implementation status.

## Evidence Boundary

All new evidence is host/target-shadow replay evidence. Live manifest capture remains content-free and non-actuating. No new check requests GPIO lines, toggles relay/fan hardware, scans an I2C address, reads audio, stores transcripts, or claims physical acceptance.

## Verification Plan

- Focused replay/readiness unit tests.
- Adjacent documentation/install dependency tests.
- Python compile checks for touched code/tests.
- Milestone/status synchronization.
- Release readiness with dirty-tree override before commit, then clean readiness after commit.
- T0 static gate.
- Exact archive qualification from a clean tagged clone.

## Remaining Work

The host/target-shadow release-candidate gate is still not complete for a user-facing Raspberry Pi candidate. Remaining work includes sanitized real-target manifests, additional dirty-state and restart/failure fixtures from the reliability blueprint, exact candidate archive qualification and then the real M10.24 Raspberry Pi campaign through `INSTALLATION_COMPLETE`, physical SHT31, relay/fan, audio, wake/voice, reboot/no-login, update, rollback and reinstall evidence.
