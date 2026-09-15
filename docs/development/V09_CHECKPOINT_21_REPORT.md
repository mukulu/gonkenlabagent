# V09 Checkpoint 21 Report — Documentation and Evidence Hardening

**Date:** 2026-09-15  
**Checkpoint:** `gonkenlabagent-v09-docs-evidence-checkpoint-21`  
**Blueprint authority:** `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md` and V09 implementation blueprint  
**Evidence boundary:** host/documentation evidence only; physical Raspberry Pi environment/wake/audio acceptance remains **NOT_RUN**.

## Completed scope

Checkpoint 21 implements the M10.13 host documentation/evidence gate:

- added `docs/HARDWARE_SETUP.md` for low-voltage wiring, placement, relay/PENGLIN/ELUTENG boundaries and stop conditions;
- added `docs/ENVIRONMENT_CONTROL.md` for daemon ownership, static config, mutable policy, mode semantics, CLI and voice boundaries;
- added `docs/SIMULATION.md` for full simulation, hybrid HIL, evidence modes and simulation-aware voice boundaries;
- added `docs/TROUBLESHOOTING.md` for symptom-based diagnosis without raw GPIO/I2C bypasses;
- updated README, installation, operations, Raspberry Pi acceptance and environment acceptance runbooks with cross-links and `GonKen` default consistency;
- added `docs/development/V09_DOCUMENTED_COMMANDS.csv` as a documented-command register;
- added `scripts/validate_v09_docs.py` and wired it into `scripts/ci.sh --phase t0`;
- hardened `scripts/environment_acceptance_runner.py` manifest output with `evidence_boundary`, `required_uploads` and `manual_gate_step_ids`;
- added documentation/evidence regression tests.

## Files changed

- `README.md`
- `docs/HARDWARE_SETUP.md`
- `docs/ENVIRONMENT_CONTROL.md`
- `docs/SIMULATION.md`
- `docs/TROUBLESHOOTING.md`
- `docs/ENVIRONMENT_ACCEPTANCE_RUN.md`
- `docs/INSTALLATION.md`
- `docs/OPERATIONS.md`
- `docs/RASPBERRY_PI_ACCEPTANCE_RUN.md`
- `docs/development/V09_DOCUMENTED_COMMANDS.csv`
- `scripts/validate_v09_docs.py`
- `scripts/ci.sh`
- `scripts/environment_acceptance_runner.py`
- `scripts/install.sh`
- `tests/unit/test_v09_documentation_hardening.py`
- `tests/unit/test_v09_environment_acceptance_runner.py`
- development ledgers and evidence files

## Verification evidence

| Check | Result | Evidence |
|---|---:|---|
| Documentation/evidence affected tests | PASS, 11/11 | `docs/development/evidence/v09/checkpoint21/affected_docs_evidence_tests.log` |
| Broad affected regression slice | PASS, 79/79 | `docs/development/evidence/v09/checkpoint21/affected_broad_regression_tests.log` |
| T0 static gates with docs validator | PASS | `docs/development/evidence/v09/checkpoint21/t0_static.log` |
| Unit phase attempt | INTERRUPTED / not PASS | `docs/development/evidence/v09/checkpoint21/unit_phase.log` |
| Interrupted active unit module follow-up | PASS, 8/8 | `docs/development/evidence/v09/checkpoint21/interrupted_active_m6_service_manager.log` |

## Non-regression and false-green controls

- T0 now fails if required V09 docs are missing, local links break, documented commands no longer parse, `extensions.environment` keys are undocumented, stale `Hey_Gonken` default examples return, or simulation/physical separation language disappears.
- The acceptance runner manifest explicitly records that the collector is not an oracle and cannot prove fan blade motion, wake behavior or physical acceptance from JSON success.
- Physical acceptance runner simulation blocking remains unchanged: simulated or hybrid backend JSON is retained for diagnosis but cannot close M10.7.
- `env watch` remains documented as passive and `env read` remains the active read-now command.

## Not claimed

- Real SHT31 detection or repeated CRC-valid reads.
- Real Pi 5 gpiochip mapping.
- Relay active polarity, PENGLIN wiring or ELUTENG fan cycles.
- Fan blade motion or software speed control.
- Target systemd/no-login convergence.
- Real `GonKen` wake behavior or progress-cue timing.

## Remaining

- M10.14 user simulation and sensor-deferred HIL release-candidate work.
- M10.7 physical Raspberry Pi acceptance campaign.

## Exact next action

Continue with M10.14: create the user simulation and sensor-deferred HIL release-candidate gate only if full simulation, sensor-deferred real-fan paths, voice/manual controls, passive watch, evidence export, rollback/recovery and documentation gates pass. Keep SHT31 physical acceptance open until real target evidence exists.
