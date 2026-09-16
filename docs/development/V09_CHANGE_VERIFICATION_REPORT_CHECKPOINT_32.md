# V09 Checkpoint 32 Change Verification Report

## Scope and risk

Verify the checkpoint-31 Raspberry Pi `release payload digest differs` repair and the broader current-release-only lifecycle boundary. High-risk areas are immutable payload integrity, activation/reconciliation, rollback availability, installer postconditions, hardware-binding checks and test-harness resumability.

## Changed code

- `scripts/release_manager.py` — **high release-integrity risk**: pre-seal smoke, transient purge, payload manifest, static current-release activation/reconciliation, noncurrent rebuild behavior.
- `scripts/install.sh` — **high installer risk**: immutable release postcondition is static; runtime hardware binding API check is separate and current-release scoped.
- `scripts/ci.sh`, `scripts/validate_v09_docs.py` — **quality-system risk**: speech lifecycle becomes case-bounded rather than a long module-level blocker.
- release/integration/unit tests — regression protection for current-only semantics, payload self-mutation, path-localized tampering and bounded interruption evidence.

## Original defect reproduced

The target built checkpoint 31, recorded an immutable digest, then activation repeatedly rejected that same candidate as changed. Source review showed executable post-seal validation could create Python cache files. The repair is tested by running the sealed CLI and then revalidating the static payload digest; no `__pycache__`/`.pyc` may appear in the release.

## Verification evidence

- Unit: PASS, 46 modules / 464 tests.
- Integration: PASS, 12 modules / 67 tests accounted.
- Release lifecycle: PASS, 11/11.
- Ollama lifecycle: PASS, 5/5.
- Speech lifecycle: PASS, 12/12 decomposed cases.
- Focused current-release contract regression: PASS.
- Python compile / shell syntax / `git diff --check`: PASS before final control-plane close.

Interrupted aggregate wrappers are retained as interruptions, not rewritten as PASS.

## Non-regression / false-green review

- A sealed current release is never executed by activation/reconciliation merely to prove static integrity.
- Runtime binding API proof remains mandatory, but occurs in a later installer gate against the current release.
- Previous releases cannot block normal current installation; explicit rollback remains available and intentionally validates the selected rollback target.
- Tampered current candidates still fail before pointer switch.
- An invalid active release is not silently rebuilt in place.
- Generic install remains non-actuating for room hardware.
- No physical acceptance is inferred from host tests.

## Readiness verdict

**HOST READY FOR CONTROL-PLANE / PACKAGE VERIFICATION.** M10.24 target acceptance remains open until exact checkpoint 32 reaches `INSTALLATION_COMPLETE` and the remaining hardware/voice campaign passes.
