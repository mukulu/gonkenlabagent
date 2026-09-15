# V09 Change Verification Report — Checkpoint 20

**Change:** Mandatory `GonKen` wake, voice responsiveness and transition-announcement host tranche  
**Commit:** package Git HEAD (reported in final checkpoint manifest)  
**Date:** 2026-09-15  
**Risk classification:** medium/high for voice UX and event semantics; target physical acceptance still blocked.

## Scope and governing instructions

The checkpoint implements the M10.12 host-verifiable software tranche required by `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md`: default `GonKen`, improved host transcript matching, progress-cue scheduling, local cue-cache contract, wake diagnostics and voice-owned transition announcements. The change must not claim real wake, real audio timing or physical hardware acceptance.

## Changed-file classification

| Area | Files | Risk |
|---|---|---|
| Wake / voice runtime | `src/gonken_agent/voice_runtime.py` | High: wake matching, threading, cue timing and transition announcements |
| Operator diagnostics | `src/gonken_agent/cli.py` | Medium: adds `wake status` command and JSON output |
| Environment service events | `src/gonken_agent/environment/service.py` | Medium: event exposure must remain read-only and bounded |
| Configuration/docs | `config/defaults.toml`; README/docs | Medium: default interaction phrase changed |
| Tests/ledgers | unit tests and development docs | Low/medium: evidence integrity and continuation state |

## Checks executed

| Check | Result | Evidence |
|---|---:|---|
| Affected wake / transition / config tests | PASS, 107/107 | `docs/development/evidence/v09/checkpoint20/affected_wake_transition_tests.log` |
| T0 static gates | PASS | `docs/development/evidence/v09/checkpoint20/t0_static.log` |
| Physical-boundary regression tests | PASS, 36/36 | `docs/development/evidence/v09/checkpoint20/physical_boundary_regression_tests.log` |
| Interrupted active unit module follow-up | PASS, 3/3 | `docs/development/evidence/v09/checkpoint20/active_unit_module_followup.log` |
| Unit phase attempt | INTERRUPTED / not PASS | `docs/development/evidence/v09/checkpoint20/unit_phase_attempt.log` |
| `git diff --check` | PASS | command run at checkpoint close |

## Findings

- The `GonKen` default and host matcher behavior are covered by unit tests.
- Explicit operator configuration of `Hey Gonken` remains narrower than the default alias-expansion path, preventing an unrequested broadening when an administrator chooses the longer phrase.
- Progress cues are bounded and cancellable at the scheduling layer, but real audio playback timing remains untested.
- Controller transition events are bounded in-memory host evidence and are not physical fan evidence.
- Voice transition announcements preserve simulation and fan-motion limitations.

## Residual risk

- Full `scripts/ci.sh --phase unit` did not complete under the execution boundary and is not claimed as PASS.
- Real wake tuning, microphone/STT false activation, progress cue audio behavior and transition announcements on the Pi require M10.7 target evidence.
- The rolling transcript matcher reduces host transcript-boundary loss but does not prove a fully overlapped real audio capture pipeline.

## Readiness verdict

**HOST CHECKPOINT PASS for M10.12 software scope.**  
**PHYSICAL ACCEPTANCE NOT_RUN.**
