# V09 Checkpoint 32 Report — Current-Release Immutable Seal Convergence

## Purpose

Checkpoint 32 responds to the exact checkpoint-31 Raspberry Pi failure and to the repeated pattern of historical-release coupling. It makes the current release the sole authority for normal installation/runtime health, repairs a post-seal self-mutation defect, and improves long-test decomposition so checkpoint closure remains resumable.

## Target evidence that triggered this checkpoint

Exact checkpoint 31 (`8c9bd8b6a657f1a793c038bec8319d1f868315c7`) built successfully on the Raspberry Pi and then failed activation with `RELEASE_INVALID: release payload digest differs`. The same boundary reproduced after reboot. The support bundle showed the previously active checkpoint-30 release, isolated hardware binding, GPIO23 identity and I2C platform as READY. This incident therefore was not caused by comparing the new candidate with a previous release.

## Root cause

Checkpoint 31 performed executable smoke before recording the digest **and then executed validation from the already sealed release again**. Python runtime execution can create `__pycache__` / `.pyc` artifacts. Those new files were outside the recorded payload and made static activation validation reject the candidate. Reboot/rerun could not repair it.

## Implemented repair

1. **Pre-seal execution only** — CLI identity, `pip check` and hardware-binding API smoke complete while the candidate is still mutable and readable by the service account.
2. **Transient cleanup before digest** — interpreter/build caches are purged before sealing.
3. **Payload localization manifest** — a bounded manifest records each payload path/type/digest so future integrity drift reports identify changed/missing/unexpected paths instead of only an aggregate hash mismatch.
4. **Static post-seal contract** — build postcondition, activation, reconciliation and ordinary status use non-mutating static integrity checks. They do not execute the sealed runtime.
5. **Current-release-only runtime gate** — target binding API capability is checked in the later `target_runtime_bindings` installer step against the selected/current release only.
6. **Historical isolation** — normal installation/reconciliation never executes or revalidates a previous release. Prior release identity is retained only for bookkeeping and explicit rollback. Explicit rollback may validate the recorded previous release because the operator is intentionally selecting it as current.
7. **Invalid noncurrent rebuild** — a stale/noncurrent release at the requested commit that fails the static contract can be removed and rebuilt from the current source. An invalid *active* release fails closed and is never rewritten in place.
8. **Bounded speech lifecycle** — the eight interruption scenarios are separate test cases and `ci.sh` has a case-bounded `speech-lifecycle` phase.

## Verification

- Complete unit accounting: **46 modules / 464 tests PASS**.
- Complete integration discovery: **12 modules / 67 tests accounted PASS**.
- Release lifecycle: **11/11 PASS**.
- Ollama lifecycle: **5/5 PASS**.
- Speech lifecycle: **12/12 PASS** after decomposing the eight interruption boundaries.
- Current-release seal regression: build -> sealed CLI execution -> static digest validation -> repeat/idempotence PASS.
- Current-only migration tests: previous runtime is deliberately corrupted and activation still succeeds because normal activation does not execute/revalidate it.
- Tamper rejection and interruption/finalization recovery: PASS.
- Aggregate commands interrupted by the external execution boundary remain recorded as INTERRUPTED; only their unaccounted cases were rerun.

## Evidence boundary

Checkpoint 32 is host/software evidence only. Existing GPIO23/fan physical evidence remains valid, and checkpoint-30 I2C/binding evidence remains useful, but no checkpoint-32 `INSTALLATION_COMPLETE`, SHT31 measurement, GonKen-controlled fan motion, Bluetooth microphone, wake/STT/TTS, reboot/no-login or update/rollback physical acceptance is claimed.

## Exact next action

Commit and package checkpoint 32 from a clean repository, verify the delivered ZIP after extraction, then install that exact checkpoint on the Raspberry Pi with `./bootstrap.sh --local-checkpoint --bluetooth-audio --bluetooth-device 41:42:06:42:05:80`. Require `INSTALLATION_COMPLETE`; if any target gate fails, preserve the new failure bundle and return to the smallest failing source layer without editing the live immutable release.
