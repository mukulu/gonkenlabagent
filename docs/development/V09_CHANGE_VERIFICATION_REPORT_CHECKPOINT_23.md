# V09 Change Verification Report — Checkpoint 23

## Scope and acceptance criteria

**Task:** continue from checkpoint 22 through all dependency-ready blueprint work, repair false-green host gaps, fully verify the resulting host/software state, and prepare an exact-package Raspberry Pi target campaign without claiming physical acceptance.

**Input commit:** `e588f958e091ba866a05e68d14456ff63ad55173`
**Runtime/source tranche commit:** `f99ea99107d4b65a6e76bd46fd2c1940bec59958`
**Final checkpoint commit:** recorded by package-close verification after this report is committed.
**Risk:** high for cyber-physical false-green, wake/privacy behavior, GPIO identity, installer provenance and release-evidence integrity.

Acceptance for this checkpoint requires:

- no remaining dependency-ready host/software gap identified by the audit;
- wake capture architecture consistent with the V2 high-recall requirement;
- production PTT/indicator route present when configured;
- fail-closed GPIO identity rather than implicit BCM=offset assumptions;
- exact downloaded-checkpoint target installation path;
- complete post-change unit/integration/release-lifecycle accounting;
- reconciled milestone/test/evidence control plane;
- executable target runbook;
- clean exact-commit/package verification before delivery;
- physical acceptance explicitly NOT_RUN until real Raspberry Pi evidence exists.

## Governing repository instructions

- `AGENTS.md`
- `PRD.md`
- `docs/development/MASTER_BLUEPRINT.md`
- `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md`
- `docs/development/MILESTONES.json`
- `docs/development/TEST_MATRIX.md`
- `docs/development/DECISIONS.md`
- `docs/RASPBERRY_PI_ACCEPTANCE_RUN.md`

The project requires bounded/observable commands, narrow checks before broader checks, preserved interrupted/failure evidence, root-cause repair, host-vs-physical separation, one hardware owner, no arbitrary model GPIO/shell execution, and continuation-safe checkpointing.

## Changed files and risk classification

| Area | Representative files | Risk / control |
|---|---|---|
| Wake capture and interaction | `src/gonken_agent/voice_runtime.py`, wake tests | High UX/privacy risk. Bounded pipelined capture, newest-wins queue, single recognition worker, content-free metrics and duplicate-trigger guards. |
| PTT/privacy GPIO | `src/gonken_agent/interaction/gpiod_ptt.py`, `push_to_talk.py` | High physical/privacy risk. Logical GPIO line-name discovery, exclusive requests, safe-off LEDs, bounded capture/cleanup. |
| Room relay identity | `environment/actuators/gpiod_relay.py`, `environment/service.py`, CLI/tests | High actuation risk. Unique kernel line-name discovery and fail-closed missing/ambiguous mapping; physical polarity remains target-gated. |
| Package/source provenance | `bootstrap.sh`, `scripts/lib/common.sh`, `scripts/lib/install_engine.sh` | High release-integrity risk. Explicit `--local-checkpoint` only; normal remote provenance retained. |
| Readiness/control plane | release/readiness/validation scripts, milestones/test/evidence ledgers | High false-green risk. Host completion separated from target acceptance and stale plan rows superseded. |
| Target runbook/docs | `docs/RASPBERRY_PI_ACCEPTANCE_RUN.md`, README and operator docs | High operator-safety risk. Exact-package identity, GPIO STOP conditions, staged simulation/hybrid/physical tests and evidence return. |

## Original defects reproduced

1. Production wake standby still executed capture -> synchronous Whisper transcription -> next capture, contradicting the V2 requirement to minimize transcription-induced listening gaps.
2. `runtime.interaction_mode="push_to_talk"` was accepted and the debounced controller existed, but production voice runtime lacked a physical GPIO PTT/recording-LED adapter.
3. The room relay adapter treated logical `relay_bcm=23` as `/dev/gpiochip0` offset 23 rather than resolving target GPIO identity.
4. The normal bootstrap path could resolve an advertised remote ref even when the operator intended to test the exact downloaded checkpoint.
5. Historical control records contained completed M10.9-M10.14 work still represented as planned/not-run rows.
6. The rewritten target runbook briefly omitted the literal `physical_acceptance_claimed=false`; the existing acceptance regression caught it before checkpoint close.

## Checks executed

| Check | Command/method | Result | Evidence |
|---|---|---:|---|
| Focused wake/PTT/GPIO/source regressions | affected narrow modules followed by combined slice | **PASS, 190/190** | `evidence/v09/checkpoint23/pretarget_affected_code_slice_rerun.log` |
| Post-change unit accounting | canonical phase + bounded smallest-uncertain batches | **PASS, 39 modules / 377 tests** | `final_unit_accounting.json` and referenced logs |
| Post-change deterministic integration accounting | canonical phase + bounded resumptions | **PASS, 10 modules / 46 tests** | `final_integration_accounting.json` and referenced logs |
| Release lifecycle | canonical phase + per-case resumptions | **PASS, 8/8 actual cases** | `final_release_lifecycle_accounting.json` |
| T0 after control reconciliation | `./scripts/ci.sh --phase t0` | **PASS** | `t0_after_control_plane.log` |
| Milestone/status generation | `python3 scripts/milestone_status.py` / `--check` | run during checkpoint reconciliation; final check required after report creation | generated `IMPLEMENTATION_STATUS.md` |
| Diff hygiene | `git diff --check` | PASS before report close; rerun required after final reports | repository check |

### Interrupted/diagnostic evidence

The canonical unit/integration/release aggregate invocations exceeded the external execution window in multiple places. They are retained as INTERRUPTED/TIMEOUT and are not counted as PASS. The project resumed from the smallest uncertain module/case and obtained complete accounting.

One manual integration follow-up invoked a nonexistent speech test method; that command ERROR is retained as diagnostic evidence. Every actual speech lifecycle test subsequently passed.

The runbook-literal regression was a real checkpoint-authoring defect. It was repaired at the documentation source, then the affected acceptance/documentation checks passed.

## Generated artifacts and manual review

Generated or maintained checkpoint-23 evidence includes:

- `final_unit_accounting.json` and bounded unit logs;
- `final_integration_accounting.json` and bounded integration logs;
- `final_release_lifecycle_accounting.json` and lifecycle logs;
- T0/control logs;
- updated milestone/status/test/evidence/decision records;
- exact-package Raspberry Pi acceptance runbook.

Hardware wiring/runbook changes were manually reviewed against the project's low-voltage-only, stop-on-uncertainty and no-physical-claim rules. No mains-control procedure is introduced. The room fan remains distinct from the Raspberry Pi Active Cooler and software speed control is not claimed.

## Regression protection

- wake pipeline tests cover capture/recognition overlap, bounded queue/drop behavior and single-trigger lifecycle;
- PTT adapter tests cover GPIO discovery, pull-up/active-low button, LED safe-off acquisition/cleanup, bounded capture and max-hold behavior;
- relay tests cover missing/ambiguous/unique logical GPIO discovery and runtime identity;
- installer tests cover explicit local-checkpoint source binding without changing default remote-source behavior;
- documentation validation checks checkpoint control consistency, runbook boundary terms and documented-command executability;
- release readiness now requires the host-complete core and M10.8-M10.14 host milestones while deliberately excluding evaluation/physical gates that cannot be proven on host.

## Skipped or unavailable checks

Not run and not represented as PASS:

- real Raspberry Pi gpiochip/line observation;
- real SHT31 detection/CRC/placement/fault-recovery;
- relay active polarity/boot pulse/contact electrical behavior;
- PENGLIN continuity/back-power and real fan motion;
- real microphone/speaker/PTT/indicator/wake performance;
- target systemd no-login/reboot/recovery;
- target update/rollback where no previous validated target release exists;
- M7.1/M7.2/M7.5 real lab corpus/model/benchmark evaluation inputs and target performance campaign.

## Residual risks and rollback

- The first physical campaign can expose Pi/OS-specific device permissions, GPIO labels, audio routes, electrical polarity or timing behavior not observable on the host.
- Pipelined Whisper standby increases concurrent capture/recognition activity; host tests bound the queue, but Raspberry Pi CPU/thermal/latency must be measured.
- Logical line-name discovery depends on the target kernel exposing the expected `GPIO<n>` names; absence/ambiguity fails closed and should be returned as evidence rather than worked around blindly.
- A relay ON command remains command-state evidence, not blade-motion proof.
- The environment subsystem's current hardware supports software power ON/OFF only, not programmable fan speed.
- Immutable-release rollback remains available at the software architecture level; target rollback acceptance requires at least two validated target releases.

## Readiness verdict

**HOST/SOFTWARE: PASS, subject to final clean-commit/package-close verification.**

The dependency-ready host/software blueprint work identified by the pre-target audit is complete and has full bounded test accounting. The package may be labelled `READY_FOR_RASPBERRY_PI_TARGET_CAMPAIGN` only after a clean exact-commit clone/archive and fresh-extraction validation pass. That label means readiness to begin target acceptance, not target acceptance itself.

**PHYSICAL RASPBERRY PI ACCEPTANCE: NOT_RUN.**

No commit, push, deployment to the user's Pi, physical actuation, or publication is performed by this verification report. The delivered runbook requires explicit supervised target execution.
