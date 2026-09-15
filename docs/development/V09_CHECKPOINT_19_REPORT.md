# V09 Checkpoint 19 — Simulation-aware voice and hybrid-HIL blocking

**Checkpoint ID:** `V09-CP19-SIM-AWARE-VOICE-HYBRID-HIL`  
**Date:** 2026-09-15  
**Base checkpoint:** Checkpoint 18 (`d06d5073752cd8d62328135c696ed18fa7d8acb7`)  
**Evidence class:** host/simulation only  
**Physical Raspberry Pi acceptance:** NOT_RUN / BLOCKED TARGET GATE

## Completed scope

Checkpoint 19 implements the M10.11 host-verifiable tranche:

- simulation-aware voice response wording;
- hybrid-HIL/physical-acceptance refusal rules in the environment acceptance runner;
- documentation updates for voice wording and acceptance-runner blocking;
- status, milestone, decision, test-matrix and evidence-ledger updates.

## Files changed

- `src/gonken_agent/environment/responses.py`
- `scripts/environment_acceptance_runner.py`
- `tests/unit/test_v09_environment_voice_intents.py`
- `tests/unit/test_v09_environment_acceptance_runner.py`
- `docs/ENVIRONMENT_ACCEPTANCE_RUN.md`
- `docs/OPERATIONS.md`
- `docs/development/IMPLEMENTATION_STATUS.md`
- `docs/development/MILESTONES.json`
- `docs/development/TEST_MATRIX.md`
- `docs/development/DECISIONS.md`
- `docs/development/V09_EVIDENCE_LEDGER.csv`
- `docs/development/V09_CHECKPOINT_19_REPORT.md`
- `docs/development/V09_CHANGE_VERIFICATION_REPORT_CHECKPOINT_19.md`

## Verification evidence

| Check | Result | Evidence |
|---|---:|---|
| Affected simulation/voice/HIL tests | PASS, 72/72 | `docs/development/evidence/v09/checkpoint19/affected_simulation_voice_hil_tests.log` |
| Static gates | PASS | `docs/development/evidence/v09/checkpoint19/t0_static.log` |
| Unit phase attempt | INTERRUPTED / not PASS | `docs/development/evidence/v09/checkpoint19/unit_phase_attempt.log` |
| Interrupted active module follow-up | PASS, 23/23 | `docs/development/evidence/v09/checkpoint19/interrupted_active_runtime_audio.log` |

## Evidence boundary

The new voice wording is host-verified using fake daemon results. The physical acceptance runner blocking rule is host-verified using fake command payloads that report hybrid/simulation provenance. This evidence proves the software boundary, not real SHT31, relay, PENGLIN, ELUTENG fan, wake, or target service behavior.

## Remaining work

- M10.12 default `GonKen` wake, high-recall matching, continuous/overlapping listening, progress cues and transition announcements.
- M10.13 documentation hardening and documentation command/reference checks.
- M10.14 user simulation and sensor-deferred HIL release candidate.
- M10.7 physical Raspberry Pi acceptance.

## Exact next action

Proceed to M10.12: implement the mandatory `GonKen` wake/responsiveness tranche with host tests first, while preserving existing wake behavior as configurable fallback and leaving real wake acceptance to the target campaign.
