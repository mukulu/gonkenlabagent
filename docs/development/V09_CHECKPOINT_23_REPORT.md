# V09 Checkpoint 23 Report — Pre-Target Completion Audit and Raspberry Pi Campaign Handoff

**Date:** 2026-09-15
**Checkpoint:** `gonkenlabagent-v09-pi-target-campaign-checkpoint-23`
**Input checkpoint:** checkpoint 22 commit `e588f958e091ba866a05e68d14456ff63ad55173`
**Runtime/source tranche commit:** `f99ea99107d4b65a6e76bd46fd2c1940bec59958`
**Blueprint authority:** `docs/development/MASTER_BLUEPRINT.md`, `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md`
**Evidence boundary:** checkpoint 23 closes dependency-ready host/software work found by the pre-target audit. It does **not** claim Raspberry Pi physical acceptance.

## Completed

Checkpoint 23 continued past the checkpoint-22 M10.14 gate and performed a pre-target false-green/completeness audit before asking the user to install the package on the Raspberry Pi.

The audit found and repaired four material host/software gaps:

1. **Wake standby blind intervals.** The previous runtime still stopped listening while synchronous Whisper transcription ran. Standby now uses a bounded pipelined capture/recognition path with a newest-wins queue, single recognition worker, drop accounting, duplicate-trigger protection and the existing `GonKen` matcher/interaction lifecycle.
2. **Production PTT and privacy indicators.** `runtime.interaction_mode="push_to_talk"` now has a production libgpiod v2 adapter for logical GPIO17 plus recording indicator GPIO27, and wake standby owns the GPIO22 monitoring indicator. GPIO identities are discovered from kernel line names rather than treating BCM numbers as character-device offsets.
3. **Room-relay GPIO identity.** The environment relay adapter now resolves the configured logical BCM pin through a unique kernel line name such as `GPIO23`, fails closed on missing/ambiguous mappings, and exposes the resolved chip/offset identity in environment status/health. This removes the checkpoint-22 `/dev/gpiochip0:23` software assumption. Physical relay polarity/boot/contact/fan behavior remains target-gated.
4. **Exact downloaded-checkpoint installation.** `./bootstrap.sh --local-checkpoint` binds a target campaign to the clean packaged Git commit and uses the package's own Git object database. Normal production/update installation continues to use the governed advertised HTTPS source/ref path.

The control plane was then reconciled so host-complete work is not left artificially `partial`, while genuinely target/evaluation-dependent milestones remain open. `M4.2`, `M4.3`, `M5.1`, `M5.2`, and `M7.3` are host-verified with `target=not-run`; `M7.1`, `M7.2`, `M7.5`, `M9.1`, and `M10.7` remain open where their required evidence is not available on the host.

The Raspberry Pi runbook was rewritten as an exact-checkpoint campaign covering package verification, local-checkpoint install, real wake/audio, PTT/indicators, GPIO mapping, full simulation, relay/fan manual operation, simulated-sensor real-actuator HIL, SHT31-deferred/real-sensor stages, offline behavior, reboot/no-login, lifecycle, performance/thermal observation and evidence return.

## Verified evidence

### Affected checkpoint-23 regression

- `docs/development/evidence/v09/checkpoint23/pretarget_affected_code_slice_rerun.log`: **PASS, 190/190**.
- `docs/development/evidence/v09/checkpoint23/t0_after_runtime_source_changes.log`: **PASS**.

### Final post-change unit accounting

`docs/development/evidence/v09/checkpoint23/final_unit_accounting.json` records **PASS: 39 modules / 377 tests**.

The canonical unit phase was externally interrupted after 15 modules and is not called PASS. All modules were subsequently accounted for in bounded batches against the post-change tree. During that process, a real documentation regression was found: the rewritten Raspberry Pi runbook omitted the literal `physical_acceptance_claimed=false` contract required by the acceptance-runner regression. The runbook was repaired and the affected tests/validator reran PASS.

### Final deterministic integration accounting

`docs/development/evidence/v09/checkpoint23/final_integration_accounting.json` records **PASS: 10 modules / 46 tests**.

The aggregate integration phase was externally interrupted; remaining modules were resumed from the smallest uncertain point. One manual diagnostic invocation named a nonexistent speech-test method and produced an ERROR. That command is preserved as diagnostic evidence; every actual speech integration test was then run and passed.

### Final release-lifecycle accounting

`docs/development/evidence/v09/checkpoint23/final_release_lifecycle_accounting.json` records **PASS: 8/8 actual release-lifecycle cases**. Aggregate attempts interrupted by the execution boundary remain marked interrupted rather than being rewritten as PASS.

### Static/control gate

`docs/development/evidence/v09/checkpoint23/t0_after_control_plane.log` records a T0 PASS on the checkpoint-23 control plane. A final package-close T0 and exact-commit readiness refresh are still required after this report/control tranche is committed.

## Current implementation truth

### Host/software verified

- V09 environment simulation and hybrid architecture;
- MANUAL / SEMI_AUTOMATIC / AUTOMATIC / DISABLED controller semantics;
- deterministic environment voice actions and truthful simulation provenance;
- passive environment watch and evidence separation;
- default `GonKen` wake matching plus pipelined standby capture architecture;
- bounded post-request progress cues and voice-owned environment announcements;
- production PTT path and recording/wake indicators at the software/libgpiod boundary;
- fail-closed logical-BCM GPIO line discovery for PTT/indicators and room relay;
- exact downloaded-checkpoint install mode;
- immutable release/update/rollback/uninstall host lifecycle machinery;
- content-minimizing telemetry/privacy boundary;
- documentation/command/control-plane validation;
- M10.14 simulation/HIL release-candidate gate.

### Still target/evaluation dependent

- M10.7 real Raspberry Pi physical acceptance;
- actual Pi gpiochip/line identities and physical wiring;
- relay active polarity, boot/shutdown pulse behavior and electrical contact suitability;
- PENGLIN continuity/back-power safety and physical ELUTENG blade movement;
- SHT31 I2C address, CRC-valid campaign, placement sanity and unplug/recovery;
- real `GonKen` wake recall/false wakes/latency across target microphones/accents/noise;
- real PTT button and visible GPIO22/GPIO27 indicator behavior;
- real no-login/systemd convergence, reboot/recovery and target lifecycle;
- M7.1/M7.2/M7.5 real lab corpus/model/benchmark evaluation inputs and target performance evidence.

No host result closes these target gates.

## Changed scope

Checkpoint 23 affects the voice runtime, GPIO interaction adapter, environment relay adapter/status, bootstrap/release-source handling, tests, documentation, development ledgers and evidence. The authoritative diff is the repository difference from checkpoint-22 commit `e588f958e091ba866a05e68d14456ff63ad55173` to the final checkpoint-23 package commit. This report intentionally avoids a self-referential final commit hash; the package-close verification/delivery summary records that exact commit after the report is committed.

## Quality outcomes and false-green repairs

- Wake host status can no longer claim the blueprint's continuous-listening property while using the old capture/transcribe/capture loop.
- PTT configuration can no longer be accepted without a production runtime path.
- BCM numbers are no longer silently treated as libgpiod offsets in the new PTT/indicator or room-relay adapters.
- A downloaded checkpoint campaign no longer silently installs whatever remote `main` advertises instead of the downloaded checkpoint.
- Historical `PLANNED / NOT_RUN` M10.9-M10.14 rows are superseded by executed evidence rather than remaining contradictory to milestone state.
- Readiness remains scoped to host/software completion; `physical_acceptance_claimed=false` is retained through target handoff and evidence collection.

## Remaining / blocked items

1. **M10.7 physical acceptance: NOT_RUN.** It requires the user's Raspberry Pi and attached hardware.
2. **SHT31 gate:** may remain BLOCKED if the sensor is unavailable; the package supports sensor-deferred HIL without converting that block to PASS.
3. **M7.1/M7.2/M7.5:** require the specified lab corpus/model/benchmark or target measurements; synthetic host substitutes are not accepted as those results.
4. **Update/rollback target campaign:** if checkpoint 23 is the first validated installed release, rollback to a previous validated release may legitimately be `BLOCKED_NO_PREVIOUS_VALIDATED_RELEASE`; it must not be fabricated as PASS.
5. **Physical relay/fan truth:** software can know the requested/resolved relay state but cannot infer blade motion without manual/independent observation.

## Exact next action

1. Complete the checkpoint-23 control commit.
2. Generate fresh exact-commit M10.14 simulation evidence and run strict release/user-test readiness against a clean tree.
3. Clone that exact commit into a clean package stage, run package preflight/validation, create the checkpoint ZIP and verify it from a fresh extraction.
4. Only after the extracted ZIP passes those gates, hand it to the user as `READY_FOR_RASPBERRY_PI_TARGET_CAMPAIGN` with `physical_acceptance_claimed=false`.
5. On the Raspberry Pi, begin with `docs/RASPBERRY_PI_ACCEPTANCE_RUN.md`, use `./bootstrap.sh --local-checkpoint`, and return the support/evidence bundle and manual observations for the next evidence-driven repair cycle.

## Continuation instruction

**Continue from checkpoint 23 using the uploaded Raspberry Pi target evidence. Verify the exact checkpoint-23 package/commit/config first; classify every result as host, simulation, hybrid, or physical evidence; repair only the smallest failed layer; rerun affected host regressions and only the uncertain target gates; do not restart architecture discovery or close M10.7 without real evidence.**
