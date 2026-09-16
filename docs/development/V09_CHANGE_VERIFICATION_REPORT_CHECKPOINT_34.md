# V09 Checkpoint 34 Change Verification Report

## Scope and risk

Verify the checkpoint-34 changes that harden current-release integrity, remove transport-specific Bluetooth blockade, resolve Raspberry Pi 5 GPIO identity consistently across wake/PTT/relay, and move GPIO mapping validation before service readiness. Risk is high for release integrity/install idempotence, high for GPIO discovery because it gates physical adapters, medium-high for audio routing, and medium for installer ordering. Host verification performs no physical actuation.

## Original target defect

Checkpoint 33 built and activated its release, passed target identity/I2C/runtime binding, environment service, model/speech/application-service and audio/runtime-context steps, then failed after 180 seconds because `gonken-agent.service` repeatedly reported `WAKE_LED_GPIO_LINE_AMBIGUOUS` for GPIO22. This places the failure after installation prerequisites and before final appliance readiness, not in release activation.

The prior target support snapshot also records one 54-line gpiochip containing GPIO2, GPIO3, GPIO17, GPIO22, GPIO23 and GPIO27 as a coherent set. Checkpoint 34 uses that topology as a fallback identity signal when libgpiod chip labels are incomplete; the observed device number itself is not hard-coded.

## Changed implementation surfaces

- `scripts/release_manager.py` — single authoritative-payload definition reused by digest, manifest, owner and mutability validation; no same-commit cache repair.
- `src/gonken_agent/gpio_resolver.py` — shared fail-closed Pi5 line discovery using line names, RP1 metadata/sysfs and coherent header topology.
- `scripts/gpio_identity_preflight.py` — non-actuating GPIO17/22/23/27 installer preflight.
- `src/gonken_agent/interaction/gpiod_ptt.py` — PTT/wake use shared resolver.
- `src/gonken_agent/environment/actuators/gpiod_relay.py` — relay uses shared resolver.
- `scripts/install.sh` — early GPIO identity dependency, optional Bluetooth/direct-audio convergence and transport-neutral runtime context.
- `scripts/bluetooth_manager.py` — explicit deterministic direct-audio status.
- unit/integration/control documents — regression and traceability updates.

## Verification executed

- Complete discovered unit inventory: **47 modules / 487 tests PASS**.
- Deterministic integration excluding speech/release lifecycle: **10 modules / 44 tests PASS**.
- Speech lifecycle: **12/12 PASS**.
- Release lifecycle: **12/12 PASS**.
- Same-commit runtime-cache process regression: PASS.
- Current-only previous-release non-execution regression: PASS.
- Bluetooth busy/offline + deterministic USB success, no-fallback failure and ambiguity refusal: PASS.
- Pi5 RP1/topology and genuine ambiguity tests for PTT/wake/relay: PASS.
- Non-actuating GPIO preflight and installer-order tests: PASS.

## False-green and cascade protections

- `__pycache__` exclusion cannot hide a symlink, top-level bytecode, arbitrary non-bytecode cache content, source/config/manifest drift or mixed cache+source tampering.
- All release validators share the same authority boundary; a benign derived cache cannot fail under a different validator such as owner/mode checking.
- Bluetooth fallback is accepted only when both deterministic direct capture and non-HDMI playback are independently proven.
- GPIO preflight and runtime adapters use the same resolver, preventing installer/runtime mapping divergence.
- The resolver never assumes `gpiochip0` or BCM=line-offset.
- Multiple plausible header controllers remain a hard ambiguity failure.
- GPIO preflight requests/writes no lines, so generic installation cannot toggle relay/LED/PTT hardware.
- Historical releases are not normal runtime prerequisites; explicit rollback remains separately governed.

## Residual risk / target boundary

Host and archive checks cannot prove the real Pi's Python libgpiod metadata shape, electrical LED behavior, physical fan control through GonKen, SHT31 measurement quality, USB/Bluetooth acoustic performance or wake recognition. Exact checkpoint 34 must reach `INSTALLATION_COMPLETE`; then the physical M10.24 campaign supplies those claims.

## Readiness verdict

**HOST-VERIFIED SUBJECT TO FINAL CONTROL/ARCHIVE GATES; PHYSICAL ACCEPTANCE NOT CLAIMED.**
