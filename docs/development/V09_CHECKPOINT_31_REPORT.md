# V09 Checkpoint 31 Report — Target Installation Convergence

## Purpose

Checkpoint 31 responds to the real Raspberry Pi checkpoint-30 incident as a dependency-chain convergence problem rather than another one-line patch. It preserves the already observed GPIO23/relay/fan evidence, distinguishes planned target transitions from defects, and hardens downstream prerequisites that could otherwise create another installation round trip.

## Target evidence that triggered this checkpoint

The Raspberry Pi demonstrated GPIO23 as `gpiochip0:23` and the unloaded/software-independent actuator path physically stopped/started/stopped the KKHMF/PENGLIN/ELUTENG load under explicit LOW/HIGH/LOW commands. Checkpoint 30 then successfully migrated the old active release and emitted `ACTIVATION_COMPLETE` for `34aee184d348f35db46fecacd36a369d9974c5a4`. The installer nevertheless returned failure because post-activation stale-release pruning revalidated unrelated historical commit `3b25b81c5bc7d4e24268726ad7f7b71296215a03` against the current hardware-binding manifest contract. A subsequent local rerun correctly treated activation as satisfied, authorized the operator and passed identity preflight, but represented the expected I2C reboot transition as a generic error/failure bundle. The immediately collected support bundle showed the checkpoint-30 current release/binding bridge and `/dev/i2c-1` ready.

## Implemented repair layers

1. **Release activation / garbage-collection boundary** — stale non-current/non-previous releases are statically checked and removed on a best-effort basis. Corrupt or undeletable stale releases emit `RELEASE_PRUNE_SKIPPED` and are retained; they cannot invalidate an already post-verified activation.
2. **I2C platform convergence** — after requesting I2C enablement, the helper waits boundedly for `/dev/i2c-1`. A genuine reboot requirement uses exit 78 and a persisted `paused` installer state. It no longer emits generic `INSTALL_ACTION` or creates a misleading failure bundle.
3. **Bluetooth input prerequisite** — a requested headset installation must prove either a Bluetooth HFP/HSP capture source or exactly one deterministic direct ALSA capture route for `gonken-agent` before final appliance readiness. Zero/ambiguous input routes fail early and specifically. The PipeWire Bluetooth SPA plugin package is an explicit action and postcondition dependency, and matching PipeWire nodes are no longer double-counted.
4. **Release-specific appliance readiness** — the runtime ready record includes the executing immutable commit. Appliance manager and install summary reject a readiness token belonging to a previous release, forcing the current release to restart and prove its own readiness.
5. **Installer dependency graph regression** — target prerequisite order is test-locked from platform/runtime/release through environment identities/I2C/bindings, service/model/speech, Bluetooth input route, runtime context and final physical appliance readiness.
6. **Non-actuating environment boundary retained** — generic installation does not auto-enable real fan/sensor profiles. Supervised profile selection remains after `INSTALLATION_COMPLETE`; the environment policy store safely creates MANUAL/OFF policy on deliberate first start.

## Verification

- Complete unit accounting: **46 modules / 461 tests PASS**.
- Deterministic integration accounting: **12 modules / 59 tests PASS**.
- Release lifecycle: **10/10 PASS**.
- Ollama lifecycle: **5/5 PASS**.
- Speech lifecycle: **5/5 PASS**.
- Focused checkpoint-31 control suite before broad accounting: **120/120 PASS**.
- Documentation/readiness/T0 pre-broad gate: PASS.
- Python compile, shell syntax and `git diff --check`: PASS.

Long aggregate wrappers that exceeded the execution boundary are preserved as interruptions rather than relabeled PASS. Their already-completed sub-results were retained and only the unaccounted cases were rerun.

## Evidence boundary

Checkpoint 31 is host-verified only. It does not claim `INSTALLATION_COMPLETE`, Bluetooth microphone operation, SHT31 measurements, GonKen service-controlled fan motion, wake-word operation, reboot/no-login acceptance or update/rollback/reinstall acceptance on the physical Pi. M10.24 remains open.

## Exact next action

Package checkpoint 31 from a clean committed tree, verify the delivered archive after re-extraction, and install that exact package on the Raspberry Pi. Require `INSTALLATION_COMPLETE`; allow only the governed I2C planned-pause/reboot/resume transition. If Bluetooth input cannot be enumerated, stop at the new explicit prerequisite code rather than waiting for final appliance timeout. After successful installation, reconnect SSH and continue the staged M10.24 simulation -> CLI fan -> SHT31 -> full-real -> voice/wake -> fault/reboot/update/rollback campaign.
