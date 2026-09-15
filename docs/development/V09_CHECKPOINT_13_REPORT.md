# V09 Checkpoint 13 — Bounded CI Module Runner

**Date:** 2026-09-15  
**Base checkpoint:** V09 checkpoint 12 (`0bae6b6fd219b83186fd716c16028652f77f4bbd`)  
**Scope:** Host-side CI observability and bounded aggregate-suite execution.  
**Physical Raspberry Pi acceptance:** NOT_RUN / BLOCKED — no target hardware evidence was produced or claimed.

## Completed scope

Checkpoint 13 does not add room-environment runtime functionality. It hardens the host quality workflow that remains relevant before or after M10.7 target work.

Implemented changes:

- added `scripts/bounded_unittest.py`;
- changed `scripts/ci.sh` T1 unit and deterministic integration phases to call the bounded runner;
- added per-module logs and JSON manifests;
- added heartbeat output so a long module remains observable;
- added environment-variable controls for CI log directory, unit/integration module timeout, and heartbeat interval;
- added tests for passing, failing and timed-out modules plus CI script wiring.

## Evidence

| Check | Result | Evidence |
|---|---:|---|
| Bounded runner unit/architecture tests | PASS, 9/9 | `docs/development/evidence/v09/wp_n_bounded_ci_runner_tests.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_n_static_gates.log` |
| Bounded integration slice | PASS, 2/2 | `docs/development/evidence/v09/wp_n_bounded_integration_slice.log` |
| Bounded release-lifecycle aggregate attempt | INTERRUPTED / NEEDS_MANUAL_REVIEW | `docs/development/evidence/v09/wp_n_bounded_release_lifecycle.log` |

## Boundary

This checkpoint improves host CI observability. It does **not** prove physical environment behavior, SHT31 reads, relay polarity, fan motion, target systemd convergence, reboot/no-login operation, or wake-phrase behavior.

## Remaining risk

The release lifecycle aggregate is now identifiable and bounded, but the long release end-to-end install test still did not complete within this container session. It should be run under a sufficiently long watchdog or decomposed further into smaller release-E2E stages.

## Exact next action

Run M10.7 on the physical Raspberry Pi, or continue host-side quality work by decomposing the release end-to-end install lifecycle into smaller observable subtests without weakening release acceptance.
