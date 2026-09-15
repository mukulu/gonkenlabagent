# V09 Checkpoint 31 Change Verification Report

## Scope

Verify the corrective target-install convergence change set derived from checkpoint-30 Raspberry Pi evidence. High-risk areas are release migration/rollback, installer resumability, target permissions, audio route selection, immutable release readiness, and false-green prevention. No live Raspberry Pi mutation is performed by this host verification.

## Changed-file and risk classification

- `scripts/release_manager.py`: **high migration/release risk** — activation-success versus stale-release pruning boundary.
- `scripts/i2c_manager.py`, `scripts/lib/install_engine.sh`, `scripts/install.sh`: **medium/high installer-state risk** — planned reboot pause/resume and target dependency order.
- `scripts/bluetooth_manager.py`: **high target audio risk** — early capture-route proof, explicit Bluetooth PipeWire plugin dependency, fail-closed ambiguity.
- `scripts/appliance_manager.py`, `scripts/install_summary.py`, `src/gonken_agent/voice_runtime.py`: **high false-green risk** — release-bound readiness tokens.
- control documents/tests: **medium release-governance risk** — keep target claims and next actions synchronized.

No data migration, credential handling, cloud dependency or automatic remote push is introduced.

## Original defects reproduced / converted to regression protection

1. New release activation succeeds but obsolete historical pre-bridge release causes a later binding-manifest failure during pruning.
2. I2C reboot requirement is represented as generic installer failure and creates a failure bundle despite being a planned system transition.
3. Bluetooth playback can be paired while no microphone route is proven, delaying a predictable failure until final appliance readiness.
4. A stale previous-release `ready.json` can otherwise make an upgraded release appear physically ready.
5. Installer step ordering can otherwise drift so a dependent target gate executes before its prerequisite.

Each now has direct unit/process regression protection.

## Executed verification

- Focused affected/control tests: PASS, including 120/120 final focused unit cases.
- Complete units: PASS, 46 modules / 461 tests.
- Deterministic integrations: PASS, 12 modules / 59 tests.
- Release lifecycle: PASS, 10/10 cases including target legacy migration, stale-prune-after-success, interruption, rollback and finalization.
- Ollama lifecycle: PASS, 5/5.
- Speech lifecycle: PASS, 5/5.
- `python3 -m compileall -q scripts src tests`: PASS.
- `bash -n scripts/install.sh scripts/lib/install_engine.sh`: PASS.
- `git diff --check`: PASS.
- `scripts/validate_v09_docs.py`, `scripts/release_readiness.py --check --allow-dirty`, milestone drift check and canonical T0: PASS before final package closure.

Interrupted aggregate commands are explicitly recorded as interrupted; completed case evidence was preserved and only missing cases were rerun.

## Non-regression and false-green review

- New candidates remain under strict binding/API validation; stale-release pruning never executes obsolete runtimes.
- Current/previous rollback releases remain protected from pruning.
- Planned pause is distinct from product failure and survives rerun through persisted step state.
- Bluetooth input enumeration is necessary but not sufficient: actual recording/TTS remains physical appliance evidence.
- Readiness belongs to the current immutable commit; old tokens cannot satisfy new-release readiness.
- Environment fan/sensor profiles remain supervised/non-actuating during generic installation.
- Raw GPIO23 physical success remains evidence for the actuator substrate only, not for GonKen-integrated service/voice acceptance.

## Residual target risk

The AIRHUG device must actually expose an HFP/HSP microphone source or the Pi must have exactly one intended direct capture device. This cannot be manufactured by host tests. Real `INSTALLATION_COMPLETE`, audio capture/playback, SHT31, service-controlled fan motion, wake/STT/TTS, reboot/no-login and update/rollback/reinstall remain M10.24 target gates.

## Readiness verdict

**HOST READY FOR CLEAN PACKAGE VERIFICATION / TARGET RETEST.** This is not physical acceptance.
