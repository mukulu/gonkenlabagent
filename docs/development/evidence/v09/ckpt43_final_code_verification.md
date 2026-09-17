# Checkpoint 43 final code-change verification evidence

## Scope

Verification of the checkpoint-42 -> checkpoint-43 semantic-convergence diff after RC1 qualification, with special attention to evidence output ownership, readiness freshness, hardware-instance portability, privacy, regression protection and package handoff.

## Verification-discovered repairs

- Explicit `--output-dir` now must be an existing real directory; collectors do not create a root-owned custom directory under sudo.
- Checkpoint-43 target instructions no longer embed the current lab Bluetooth device address.
- Semantic readiness now binds `release_profile` and `service_start_ticks` in addition to release commit, boot ID, service PID and observation time.

## Executed post-repair checks

- 102-test focused evidence/readiness/voice/target-shadow/responsibility portfolio: PASS.
- 12 speech-lifecycle cases: PASS. Broad aggregation exceeded the interactive execution boundary and was decomposed without rerunning already completed work blindly.
- 34 install-summary/Bluetooth tests: PASS.
- 124 environment configuration/controller/service/simulation/CLI/voice/acceptance tests: PASS.
- 12 install/uninstall interruption and recovery tests: PASS.
- `git diff --check`: PASS.

## Regression protection

New or strengthened regression assertions cover:

- missing explicit output directory is rejected and not created;
- operator-selected evidence directory therefore cannot become an inaccessible root-created parent merely because collection used sudo;
- stale readiness is rejected on release profile mismatch;
- stale readiness is rejected when a PID has a different process-start identity;
- new target instructions require an operator-supplied Bluetooth selector instead of a lab-instance constant.

## Residual boundary

Host, simulation, process and target-shadow evidence remain below real Raspberry Pi acceptance. Service-user microphone/speaker behavior, acoustic wake/interaction, SHT31 placement/read quality, relay/fan electrical behavior and blade motion, and reboot/no-login lifecycle remain target-run gates for the final exact archive.

## Source-handoff consistency closeout

Final handoff review found that the convergence report still described immutable packaging as future work. That wording was correct when the report was first written but would be stale inside the delivered checkpoint. The report now closes source-level work explicitly and treats the final ZIP hash/archive qualification as external handoff evidence, which avoids a self-referential archive-hash problem. This is documentation/control-plane only and does not alter runtime behavior.
