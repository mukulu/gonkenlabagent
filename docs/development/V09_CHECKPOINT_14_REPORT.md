# V09 Checkpoint 14 — Release Lifecycle CI Decomposition

**Date:** 2026-09-15  
**Base checkpoint:** V09 checkpoint 13 (`e5fbcda`)  
**Scope:** Host-side release lifecycle observability and case-level decomposition.  
**Physical Raspberry Pi acceptance:** NOT_RUN / BLOCKED — no target hardware evidence was produced or claimed.

## Completed scope

Checkpoint 14 does not add new environment runtime functionality. It removes the remaining opaque release-lifecycle host quality bottleneck by converting the heavy release lifecycle module into case-level CI evidence while preserving the same release acceptance behavior.

Implemented changes:

- extended `scripts/bounded_unittest.py` with `--granularity case`;
- extended `scripts/bounded_unittest.py` with `--exclude-module`;
- changed `scripts/ci.sh` so ordinary deterministic integration modules run at module granularity, while `tests.integration.test_release_lifecycle_process` runs separately at case granularity;
- split the formerly combined release-only/default-boundary E2E method into explicit build/freeze, repeat/idempotency and target-boundary cases;
- added bounded-runner tests for case-level logs/manifests and discovery exclusion;
- updated development ledgers, decisions and evidence records.

## Evidence

| Check | Result | Evidence |
|---|---:|---|
| Bounded runner case/exclude tests | PASS, 6/6 | `docs/development/evidence/v09/wp_o_bounded_case_runner_tests.log` |
| Release lifecycle affected and decomposed slices | PASS, 10/10 affected fast slice plus 4/4 release E2E cases | `docs/development/evidence/v09/wp_o_release_lifecycle_slices.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_o_static_gates.log` |
| Multi-case bounded-runner attempt | INTERRUPTED / not PASS | `docs/development/evidence/v09/wp_o_release_case_runner_partial_attempt.log` |

## Boundary

This checkpoint improves host test evidence quality. It does **not** prove physical environment behavior, SHT31 reads, relay polarity, PENGLIN wiring, ELUTENG fan motion, target systemd convergence, reboot/no-login operation, or wake-phrase behavior.

The multi-case bounded-runner attempt is preserved as partial diagnostic evidence only. PASS evidence comes from the affected runner/unit slice and the individually rerun release lifecycle cases.

## Remaining risk

A full `scripts/ci.sh` aggregate run was not completed in this environment after the decomposition. The release lifecycle is now structurally decomposed and each formerly long E2E case passed individually, but physical M10.7 remains the next acceptance-critical gate.

## Exact next action

Run the M10.7 Raspberry Pi target campaign, or perform one final long-host `scripts/ci.sh` run in an environment with enough wall-clock allowance to collect complete bounded manifests.
