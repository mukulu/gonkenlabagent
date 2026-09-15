# V09 Checkpoint 15 — CI Phase Selection and Resumable Host Evidence

**Date:** 2026-09-15  
**Base checkpoint:** V09 checkpoint 14 (`6413627`)  
**Scope:** Host CI observability and resumability.  
**Physical Raspberry Pi acceptance:** NOT_RUN / BLOCKED — no target hardware evidence was produced or claimed.

## Completed scope

Checkpoint 15 does not add new environment runtime functionality.  It improves the canonical host evidence workflow so long host checks can be run phase-by-phase when the surrounding execution environment cannot keep one aggregate process alive long enough.

Implemented changes:

- added `scripts/ci.sh --phase PHASE`;
- supported phases: `t0`, `unit`, `integration`, `release-lifecycle`, `all`;
- added `scripts/ci.sh --list-phases` and help text;
- preserved no-argument `scripts/ci.sh` as the complete canonical T0/T1 host run;
- added tests for phase listing, help, invalid phase refusal and retained bounded-runner wiring;
- preserved interrupted aggregate and unit-phase attempts as diagnostic evidence only.

## Evidence

| Check | Result | Evidence |
|---|---:|---|
| CI phase-selector tests | PASS, 8/8 | `docs/development/evidence/v09/wp_p_ci_phase_selector_tests.log` |
| `scripts/ci.sh --phase t0` | PASS | `docs/development/evidence/v09/wp_p_ci_phase_t0.log` |
| `bash -n scripts/ci.sh` | PASS | `docs/development/evidence/v09/wp_p_ci_bash_n.log` |
| Python compile check for touched files | PASS | `docs/development/evidence/v09/wp_p_compile_phase_change.log` |
| `scripts/ci.sh --list-phases` / invalid phase refusal | PASS by unit and direct logs | `docs/development/evidence/v09/wp_p_ci_phase_list.log`; `docs/development/evidence/v09/wp_p_ci_phase_unknown.log` |
| Full aggregate CI attempt under external 240-second wrapper | INTERRUPTED / not PASS | `docs/development/evidence/v09/wp_p_full_ci_attempt_external_240s.log` |
| Standalone unit phase attempt under current tool boundary | INTERRUPTED / not PASS | `docs/development/evidence/v09/wp_p_unit_phase_attempt_interrupted.log` |

## Boundary

This checkpoint improves the execution of host evidence collection.  It does not change application logic, environment daemon behavior, installer actuation, SHT31 adapter behavior, relay control, voice actions, release activation semantics or physical target acceptance.

## Remaining risk

A full one-command `scripts/ci.sh` PASS is still not claimed in this environment.  The phase selector makes the remaining broad evidence resumable: a later environment with sufficient wall-clock allowance can run all phases, or run only the phase whose evidence is missing.

## Exact next action

Run the M10.7 Raspberry Pi target campaign, or collect complete host phase evidence by running:

```bash
./scripts/ci.sh --phase t0
./scripts/ci.sh --phase unit
./scripts/ci.sh --phase integration
./scripts/ci.sh --phase release-lifecycle
```
