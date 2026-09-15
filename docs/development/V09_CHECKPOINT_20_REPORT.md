# V09 Checkpoint 20 Report — Mandatory GonKen Wake, Responsiveness and Transition Announcements

**Date:** 2026-09-15  
**Checkpoint:** `gonkenlabagent-v09-wake-responsiveness-checkpoint-20`  
**Commit:** package Git HEAD (reported in final checkpoint manifest)  
**Blueprint authority:** `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md` and V09 implementation blueprint  
**Evidence boundary:** host/software evidence only; physical Raspberry Pi wake/audio/environment acceptance remains **NOT_RUN**.

## Completed scope

Checkpoint 20 implements the M10.12 host gate:

- changed the packaged default wake phrase from `Hey Gonken` to `GonKen`;
- added a recall-oriented host transcript matcher with aliases, split-token handling and bounded one-edit handling for the `gonken` token;
- added a rolling wake transcript matcher that carries a short tail across phrase-spotting windows to reduce software-side transcript-boundary loss;
- added `gonken-agent wake status` and `gonken-agent wake status --json` with matcher metadata, alias list and explicit no-physical-evidence fields;
- added a deterministic processing-cue plan and local Piper cue-cache contract for bounded post-question progress cues;
- integrated progress-cue handling in the voice runtime while skipping cues for fast deterministic environment actions;
- added controller transition events in the environment service;
- added voice-owned transition announcements for selected automatic/semi-automatic/safe-off transitions;
- preserved simulation-aware wording and the current hardware boundary: relay/fan-power state is not blade-motion evidence and software fan speed remains unsupported.

## Files changed

- `config/defaults.toml`
- `README.md`
- `docs/INSTALLATION.md`
- `docs/OPERATIONS.md`
- `docs/RASPBERRY_PI_ACCEPTANCE_RUN.md`
- `src/gonken_agent/cli.py`
- `src/gonken_agent/voice_runtime.py`
- `src/gonken_agent/environment/service.py`
- `tests/unit/test_m2_1.py`
- `tests/unit/test_voice_appliance.py`
- `tests/unit/test_v09_environment_polling_loop.py`
- `docs/development/MILESTONES.json`
- `docs/development/IMPLEMENTATION_STATUS.md`
- `docs/development/TEST_MATRIX.md`
- `docs/development/DECISIONS.md`
- `docs/development/V09_EVIDENCE_LEDGER.csv`
- `docs/development/V09_SIMULATION_HIL_TRACEABILITY.csv`

## Verification evidence

| Check | Result | Evidence |
|---|---:|---|
| Affected wake / transition / config tests | PASS, 107/107 | `docs/development/evidence/v09/checkpoint20/affected_wake_transition_tests.log` |
| T0 static gates | PASS | `docs/development/evidence/v09/checkpoint20/t0_static.log` |
| Physical-boundary regression tests | PASS, 36/36 | `docs/development/evidence/v09/checkpoint20/physical_boundary_regression_tests.log` |
| Interrupted active unit module follow-up | PASS, 3/3 | `docs/development/evidence/v09/checkpoint20/active_unit_module_followup.log` |
| Unit phase attempt | INTERRUPTED / not PASS | `docs/development/evidence/v09/checkpoint20/unit_phase_attempt.log` |

## Non-regression and false-green controls

- `gonken-agent wake status --json` reports `physical_evidence=false` and `real_wake_acceptance=NOT_RUN`.
- Progress cue tests are host timing tests only; no real audio playback or Piper timing acceptance is claimed.
- Transition announcements are voice-owned and derived from environment daemon events; the environment daemon still does not own audio.
- Simulation-aware wording is preserved, and transition announcements do not claim blade motion or software speed control.
- Physical acceptance runner, diagnostics, support and grounding observability regressions remain protected by the checkpoint 20 boundary suite.

## Not claimed

- Real `GonKen` wake detection on microphone/audio hardware.
- Real false-activation/false-rejection statistics.
- Real phrase-end to acknowledgement latency.
- Real progress-cue playback timing or no-overlap behavior on the Pi audio stack.
- Real SHT31, relay, PENGLIN, ELUTENG or target systemd/no-login behavior.

## Remaining

- M10.13 documentation and evidence hardening.
- M10.14 user simulation and sensor-deferred HIL release-candidate work.
- M10.7 physical Raspberry Pi acceptance campaign.

## Exact next action

Continue with M10.13 documentation/evidence hardening: create or update hardware setup, simulation, troubleshooting and environment-control documents, add command/link/config documentation checks, and preserve all physical Raspberry Pi acceptance gates as open until target evidence exists.
