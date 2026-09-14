# V09 Checkpoint 10 — daemon polling/control-loop scaffold

**Date:** 2026-09-15  
**Base checkpoint:** V09 Checkpoint 09  
**Base commit:** `c9b536a68f9c4d99b3aa19319c30c39cc4f1dae4`  
**Scope:** M10.6 daemon polling/control-loop sub-batch, host-verifiable only.

## Completed

- Added `EnvironmentServiceCore.poll_once()` as the daemon-owned polling/control primitive.
- Centralized sensor read handling so missing/failed sensor transport becomes a structured `SensorReading` with an error code rather than an unhandled polling-thread failure.
- Added polling metadata to daemon metadata and health output.
- Added `EnvironmentPollingLoop` with bounded interval, immediate poll cycle, stop event and deterministic stop/join behavior.
- Updated `EnvironmentDaemon.from_config()` so normal daemon serving attaches the configured polling loop.
- Updated `gonken-agent env serve` to use `EnvironmentDaemon.from_config()` for normal serving.
- Added `tests/unit/test_v09_environment_polling_loop.py`.
- Updated M10 ledgers, decisions, implementation status, master blueprint and test matrix.

## Verification

| Check | Result | Evidence |
|---|---:|---|
| Polling/control affected tests | PASS, 39/39 | `docs/development/evidence/v09/wp_k_polling_loop_affected_tests.log` |
| Full host unit suite | PASS, 316/316 | `docs/development/evidence/v09/wp_k_full_unit.log` |
| Targeted CLI/text integration subset | PASS, 14/14 | `docs/development/evidence/v09/wp_k_integration_subset.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_k_static_gates.log` |
| Bounded broad CI attempt | INTERRUPTED / not PASS | `docs/development/evidence/v09/wp_k_broad_ci_attempt.log` |

## Evidence boundary

The bounded broad CI attempt passed the full unit phase and entered deterministic integration before the external watchdog/tool timeout required process cleanup. The preserved log is retained as interruption evidence, not as PASS and not as a polling-loop failure.


This checkpoint proves host-level daemon polling behavior only. Tests use fake sensor, actuator, clock and injected adapter objects. No test opens `/dev/i2c-*`, detects a physical SHT31, requests a real gpiochip line, validates relay polarity, switches PENGLIN USB power, observes ELUTENG fan motion, starts a managed target systemd unit, reboots a Pi, or evaluates the wake phrase.

## Remaining

M10.6 is still host-partial. Target-grounded operator documentation and any target-dependent service refinements remain dependent on M10.7 evidence. M10.7 remains required for real Raspberry Pi HIL and final release acceptance.

## Exact next action

Continue with M10.6 target-readiness documentation/runbook refinement and then proceed to M10.7 physical HIL when the Raspberry Pi, SHT31, relay, PENGLIN adapters, ELUTENG fan and audio/wake setup are available. If continuing host-only, add acceptance-run scaffolds that generate private evidence files without claiming target PASS.
