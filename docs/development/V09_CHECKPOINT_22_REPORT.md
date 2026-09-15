# V09 Checkpoint 22 Report — User Simulation and Sensor-Deferred HIL Release-Candidate Gating

**Date:** 2026-09-15
**Checkpoint:** `gonkenlabagent-v09-user-sim-hil-release-candidate-checkpoint-22`
**Base:** checkpoint 21 commit `9d37e32`
**Blueprint authority:** `docs/development/MASTER_BLUEPRINT.md` §22.10 and `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md`
**Evidence boundary:** host/software release-candidate readiness only. Raspberry Pi physical acceptance remains **NOT_RUN**.

## Completed

M10.14 now has an explicit, false-green-resistant user-test gate:

- added `scripts/environment_simulation_runner.py`, which drives a fresh isolated full-simulation campaign through the public AF_UNIX/CLI/controller path;
- the campaign verifies full-simulation provenance, manual ON/OFF, AUTO hysteresis, SEMI explicit-start/auto-stop/no-restart, stale-sensor safe-off/recovery and passive-watch non-observer behavior;
- the same runner validates the simulated-sensor/libgpiod profile only through the non-actuating `env serve --check` path and records `physical_actuation_tested=false`;
- added `scripts/v09_user_test_readiness.py`, which requires the established host milestones, base release-readiness, V09 documentation validation, required handoff artifacts and a fresh exact-commit M10.14 simulation manifest;
- stale or unknown-commit simulation evidence is rejected;
- a dirty tree can produce only `DEVELOPMENT_READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL`; the final READY label requires a clean tree;
- added `docs/USER_SIMULATION_HIL_HANDOFF.md` with ordered full-simulation, manual real-relay/fan, sensor-deferred HIL, voice, monitoring and evidence-export stages;
- target GPIO mapping/wiring uncertainty is an explicit STOP condition rather than an inferred PASS;
- updated README, documentation validation, documented-command register and development-control ledgers.

## Verified evidence

| Check | Result | Evidence |
|---|---:|---|
| New M10.14 gate/runner plus documentation tests | PASS, 10/10 | `docs/development/evidence/v09/checkpoint22/new_gate_and_docs_tests.log` |
| Physical-acceptance-runner regression module | PASS, 7/7 | `docs/development/evidence/v09/checkpoint22/acceptance_runner_module.log` |
| Remaining affected CLI/simulation/voice/release/update/uninstall/support slice | PASS, 47/47 | `docs/development/evidence/v09/checkpoint22/remaining_affected_modules.log` |
| First broad affected-regression attempt | INTERRUPTED / TIMEOUT; not PASS | `docs/development/evidence/v09/checkpoint22/affected_regression_attempt_interrupted.log` |
| Active test at interruption rerun narrowly | PASS, 1/1 | `docs/development/evidence/v09/checkpoint22/acceptance_runner_active_followup.log` |
| Documentation validator | PASS | `docs/development/evidence/v09/checkpoint22/docs_validator.json` |
| T0 static/checkpoint gate | PASS after one repaired line-ending defect | `docs/development/evidence/v09/checkpoint22/t0_static.log` |

The interrupted aggregate was not repeated unchanged. Its active acceptance-runner module was isolated and passed 7/7, while the independent remaining affected modules passed 47/47. The first T0 attempt then caught CRLF line endings introduced while appending new CSV evidence rows; those rows were normalized back to LF, `git diff --check` passed, and T0 passed on rerun. The failed T0 log is preserved as diagnostic evidence.

## Current implementation truth

### Host-verified

- full-simulation release evidence runner;
- exact-commit/clean-tree release-candidate gate;
- manual/AUTO/SEMI/stale-recovery/passive-watch deterministic simulation campaign;
- non-actuating construction check for the simulated-sensor/libgpiod hybrid profile;
- user handoff documentation and documentation-command validation;
- simulation/hybrid evidence remains separated from physical acceptance.

### Target NOT_RUN

- Pi 5 gpiochip/line mapping;
- SHT31 detection, CRC-valid measurement campaign and placement sanity;
- relay active polarity and boot behavior;
- PENGLIN VBUS/GND continuity and back-power safety;
- real ELUTENG fan ON/OFF cycles and blade observation;
- real `GonKen` wake recall/false wakes/latency;
- real Piper progress-cue and announcement timing;
- no-login/systemd convergence, reboot, clean install, update/rollback on the target.

## Changed files

- `README.md`
- `docs/USER_SIMULATION_HIL_HANDOFF.md`
- `scripts/environment_simulation_runner.py`
- `scripts/v09_user_test_readiness.py`
- `scripts/validate_v09_docs.py`
- `tests/unit/test_v09_user_test_readiness.py`
- `tests/integration/test_v09_user_test_release_candidate.py`
- `docs/development/MASTER_BLUEPRINT.md`
- `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md`
- `docs/development/MILESTONES.json`
- `docs/development/IMPLEMENTATION_STATUS.md`
- `docs/development/TEST_MATRIX.md`
- `docs/development/DECISIONS.md`
- `docs/development/V09_SIMULATION_HIL_TRACEABILITY.csv`
- `docs/development/V09_DOCUMENTED_COMMANDS.csv`
- `docs/development/V09_EVIDENCE_LEDGER.csv`
- checkpoint-22 evidence and verification reports.

## Blocked items / risks

1. **M10.7 remains NOT_RUN.** No host check can replace physical evidence.
2. **SHT31 remains a physical gate.** The handoff is intentionally sensor-deferred.
3. **GPIO mapping remains target-gated.** The current relay adapter assumes `/dev/gpiochip0` offset 23 for the BCM23 seed. The operator must establish that mapping before actuation; otherwise STOP and return mapping evidence.
4. **Relay command is not blade-motion evidence.** Manual observation remains required.
5. **Full-simulation `HOST_SIMULATION` is a backend evidence token.** Target platform identity is recorded separately by the target evidence collector; the token is never interpreted as physical evidence.
6. The historical full unit phase has repeatedly been interrupted by the execution boundary in prior checkpoints. This checkpoint therefore uses bounded affected regressions plus T0; it does not manufacture a full-unit PASS.

## Exact next action

After the final clean checkpoint package emits `READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL`, install that exact package on the Raspberry Pi and follow `docs/USER_SIMULATION_HIL_HANDOFF.md` from Stage A onward. Do not actuate the real relay until the GPIO mapping and low-voltage wiring preflight pass. Export the support ZIP, M10.7 manifest/private evidence ledger, mapping output and manual observation note, then upload them for the evidence-driven checkpoint-23 continuation.

## Continuation instruction

**Continue from checkpoint 22 using the uploaded target evidence. Verify exact package/config identity, classify simulation/hybrid/physical results, repair only the smallest failed layer, and rerun only uncertain target gates. Do not restart architecture discovery or claim M10.7 physical acceptance without real evidence.**
