# V09 Checkpoint 12 — Broad-CI Interruption Harness Hardening

**Date:** 2026-09-15  
**Base checkpoint:** V09 checkpoint 11 (`30a4c3a411c5725568ae27e6f5a305d77ad5775a`)  
**Scope:** Host-side CI/test-harness hardening for the known Ollama lifecycle interruption caveat.  
**Physical Raspberry Pi acceptance:** NOT_RUN / BLOCKED — no target hardware evidence was produced or claimed.

## Completed scope

Checkpoint 12 does not add room-environment functionality. It repairs an independent host-quality bottleneck that had repeatedly caused broad CI attempts to stall around the Ollama lifecycle interruption/recovery fixture.

Implemented changes:

- `scripts/ollama_manager.py`: test-only interruption control now defaults to abrupt self-exit with a shell-visible signal-style code instead of killing the parent shell; parent-shell termination remains opt-in through `GONKEN_OLLAMA_TEST_INTERRUPT_PARENT=1`.
- `scripts/release_manager.py`: same bounded test-only interruption behavior through `GONKEN_RELEASE_TEST_INTERRUPT_PARENT=1`.
- `tests/integration/test_ollama_lifecycle_process.py`: the fake HTTP fixture now lazy-starts the server only for service/model API operations, uses bounded close semantics, avoids a shell wrapper for interrupted child processes, closes fixtures per subtest, and runs a representative default boundary set while retaining exhaustive mode through `GONKEN_EXHAUSTIVE_OLLAMA_BOUNDARIES=1`.

## Evidence

| Check | Result | Evidence |
|---|---:|---|
| Ollama lifecycle process integration | PASS, 5/5 | `docs/development/evidence/v09/wp_m_ollama_lifecycle_after_hardening.log` |
| Release-manager interruption integration slice | PASS, 3/3 | `docs/development/evidence/v09/wp_m_release_interruption_after_hardening.log` |
| Manager unit slice | PASS, 23/23 | `docs/development/evidence/v09/wp_m_manager_unit.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_m_static_gates.log` |
| Full release lifecycle aggregate | INTERRUPTED / NEEDS_MANUAL_REVIEW | `docs/development/evidence/v09/wp_m_release_lifecycle_attempt.log` |
| Full unit aggregate attempt | INTERRUPTED / NEEDS_MANUAL_REVIEW | `docs/development/evidence/v09/wp_m_full_unit_attempt.log` |

## Boundary

This checkpoint improves host CI determinism. It does **not** prove physical environment behavior, SHT31 reads, relay polarity, fan motion, target systemd convergence, reboot/no-login operation, or wake-phrase behavior.

## Remaining risk

The original Ollama lifecycle interruption fixture now passes as a bounded deterministic integration test. However, the full aggregate unit and release-lifecycle runs still exceeded this container's execution window. The checkpoint therefore records a narrower verified repair plus explicit aggregate `NEEDS_MANUAL_REVIEW`, rather than claiming full broad CI PASS.

## Exact next action

Proceed to target M10.7 on the physical Raspberry Pi, or continue host-side CI decomposition by making the remaining aggregate unit/release lifecycle suites more observable and bounded without weakening acceptance criteria.
