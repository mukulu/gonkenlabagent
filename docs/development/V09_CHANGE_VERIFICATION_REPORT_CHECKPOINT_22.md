# V09 Change Verification Report — Checkpoint 22

## Scope and acceptance criteria

**Task:** implement M10.14 user simulation and sensor-deferred HIL release-candidate gating from checkpoint 21.
**Branch:** `v09-m10.14-user-test-rc`
**Base commit:** `9d37e32`
**Risk:** medium/high for release-evidence integrity and operator hardware safety; the host implementation must not actuate hardware or convert simulation into physical acceptance.

Acceptance requires a deterministic full-simulation campaign, a non-actuating sensor-simulated/libgpiod construction check, exact-commit release evidence, a clean-tree final gate, user handoff instructions, documentation validation, affected non-regression checks and continued `NOT_RUN` state for M10.7 physical gates.

## Governing repository instructions

- `AGENTS.md`
- `docs/development/MASTER_BLUEPRINT.md`
- `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md`
- `docs/development/MILESTONES.json`
- `docs/development/TEST_MATRIX.md`
- `docs/development/DECISIONS.md`

The project requires continuation-safe checkpoints, bounded commands, preservation of interrupted evidence, narrow-before-broad testing and strict separation of host/simulation evidence from Raspberry Pi physical acceptance.

## Changed files and risk classification

| Area | Files | Risk |
|---|---|---|
| M10.14 evidence runner | `scripts/environment_simulation_runner.py` | Medium: false-green simulation or hidden physical access would invalidate the gate. |
| Release-candidate gate | `scripts/v09_user_test_readiness.py` | High evidence-integrity risk: stale/dirty/unknown evidence must not produce the final READY label. |
| User HIL handoff | `docs/USER_SIMULATION_HIL_HANDOFF.md`; README | High operator-safety risk if GPIO/wiring prerequisites are ambiguous. |
| Documentation validation | `scripts/validate_v09_docs.py`; documented-command register | Medium: must catch stale/missing user-test instructions without executing hardware. |
| Regression protection | new unit/integration tests | Medium: must challenge false physical claims and stale evidence. |
| Control plane | blueprint/status/milestones/test/decision/traceability/evidence docs | Medium: checkpoint must remain self-describing and resumable. |

## Original defect / gap reproduction

Checkpoint 21 left M10.14 `software=pending`, `target=not-run` and had no machine gate able to emit the required user-test readiness label from fresh evidence. There was no dedicated deterministic full-simulation campaign binding the result to a commit, and no single staged user handoff joining full simulation to sensor-deferred supervised HIL.

During implementation, the first end-to-end gate run correctly refused readiness when the new handoff document did not satisfy the documentation validator's exact safety term. The document was corrected before milestone status was changed. A later broad affected-regression command hit the execution timeout during the existing environment acceptance-runner module; the partial log was preserved, the active module was isolated, and all independent remaining modules were completed separately. The first T0 close attempt then rejected CRLF line endings introduced by the checkpoint CSV append path. The historical ledgers were preserved, the new rows were normalized to LF, `git diff --check` passed and T0 passed on rerun.

## Checks executed

| Check | Command/method | Result | Evidence |
|---|---|---:|---|
| New readiness/runner + docs | targeted unittest slice | PASS, 10/10 | `checkpoint22/new_gate_and_docs_tests.log` |
| Acceptance runner | isolated module | PASS, 7/7 | `checkpoint22/acceptance_runner_module.log` |
| Remaining affected regression | isolated affected modules | PASS, 47/47 | `checkpoint22/remaining_affected_modules.log` |
| Initial aggregate attempt | bounded aggregate | INTERRUPTED / TIMEOUT | `checkpoint22/affected_regression_attempt_interrupted.log` |
| Interrupted active case follow-up | single test | PASS, 1/1 | `checkpoint22/acceptance_runner_active_followup.log` |
| Documentation validator | `scripts/validate_v09_docs.py --json` | PASS | `checkpoint22/docs_validator.json` |
| T0 | `./scripts/ci.sh --phase t0` | PASS after repairing appended CSV CRLF line endings | `checkpoint22/t0_static.log` |
| Final clean M10.14 gate | exact checkpoint commit; generated outside committed tree | pending until final commit/package close | external checkpoint-22 verification bundle |
| Change-verification report structure | skill validator | PASS | `checkpoint22/change_report_validator.log` |

## Generated artifacts and manual review

The simulation runner produces `m10_14_simulation_manifest.json` and `m10_14_simulation_ledger.csv`. The final committed package is verified using fresh external evidence so the manifest can bind to the exact final commit without changing that commit afterward. The target user handoff was manually reviewed for stage order, no-mains/low-voltage boundaries, GPIO-mapping STOP behavior and explicit distinction between relay command and blade-motion evidence.

## Regression protection

- Unit tests reject physical-acceptance claims in simulation manifests, missing required simulation steps and stale/unknown commit identity.
- Integration testing drives the real public CLI/service boundary in full simulation and confirms the hybrid profile check does not toggle hardware.
- Existing acceptance-runner tests confirm simulated/hybrid payloads remain blocked from physical PASS.
- Existing CLI simulation tests preserve passive-watch behavior and the non-actuating `env serve --check` contract.
- Lifecycle/update/uninstall/support tests protect rollback/recovery and evidence export surfaces required by M10.14.

## Skipped or unavailable checks

No real Raspberry Pi, SHT31, relay, PENGLIN fan path, physical audio or real wake path is available in this environment. Those checks are not marked PASS. The full unit aggregate is not claimed because the project history shows repeated execution-boundary interruption; checkpoint 22 uses completed bounded affected modules and T0 instead.

## Residual risks and rollback

- The actual Pi 5 gpiochip mapping may differ from the current `/dev/gpiochip0` offset-23 adapter assumption. The handoff blocks actuation on mismatch.
- Relay polarity, boot pulses, fan current path and blade motion require supervised physical evidence.
- Rollback remains the existing immutable-release/update-manager path; checkpoint 22 adds no new direct hardware mutation mechanism.

## Readiness verdict

**HOST M10.14 IMPLEMENTATION GATE PASS.** The final package-level READY label remains conditional on the post-commit clean-tree, exact-commit simulation/readiness gate described below; physical acceptance remains NOT_RUN.

**Physical acceptance:** `NOT_RUN`.
**M10.7:** open.
**Authorization boundary:** this verification authorizes no deployment or physical actuation by itself; supervised target testing begins only after the user installs the final committed checkpoint and follows the handoff preconditions.

No commit, push, merge, deployment, publication, or destructive action is authorized by this report alone. The checkpoint commit is performed under the project's user-authorized continuation/checkpoint workflow; no push, deployment or physical actuation is performed here.
