# V09 Checkpoint 08 — SHT31/libgpiod hardware-adapter foundation

**Date:** 2026-09-15  
**Base checkpoint:** V09 Checkpoint 07  
**Base commit:** `e635d2f7f48d4087581e15059c1398f8c16f8295`  
**Scope:** M10.6 hardware-adapter sub-batch, host-verifiable only.

## Completed

- Added narrow sensor adapter interfaces in `src/gonken_agent/environment/sensors/base.py`.
- Added `SHT31Sensor` in `src/gonken_agent/environment/sensors/sht31.py` with lazy `smbus` import, injected-bus testability, Sensirion CRC-8 validation, single-shot command construction and physical-scale conversion.
- Added narrow actuator adapter interfaces in `src/gonken_agent/environment/actuators/base.py`.
- Added `GpiodRelayFanActuator` in `src/gonken_agent/environment/actuators/gpiod_relay.py` with lazy libgpiod import, exclusive line request shape, inactive output initialization, logical ON/OFF writes, safe-off close and power-only capability metadata.
- Updated `EnvironmentServiceCore` to synchronize controller state to an injected actuator and fail closed with `ACTUATOR_ERROR_SAFE_OFF` if actuator writes fail.
- Updated `gonken-agent env serve` failure wording: hardware adapters now exist, but supervised real-hardware daemon activation remains target-gated.
- Added `tests/unit/test_v09_environment_hardware_adapters.py`.
- Updated ledgers, decisions, implementation status, master blueprint and test matrix.

## Verification

| Check | Result | Evidence |
|---|---:|---|
| Adapter/service affected tests | PASS, 45/45 | `docs/development/evidence/v09/wp_i_hardware_adapters_affected_tests.log` |
| Full host unit suite | PASS, 305/305 | `docs/development/evidence/v09/wp_i_full_unit.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_i_static_gates.log` |

## Evidence boundary

This checkpoint provides E1 host-unit evidence for adapter logic using fake SMBus and fake libgpiod objects. It does not open `/dev/i2c-*`, request `/dev/gpiochip*`, detect a real SHT31, switch a relay, switch PENGLIN USB power, observe fan blade motion, run under target systemd, or validate reboot/no-login behavior.

## Remaining

M10.6 remains partial. The next dependency-ready batch should implement supervised `env serve` real-core construction from static config and daemon-owned policy storage, while preserving fail-closed/degraded behavior when target hardware is absent. M10.7 remains required for real Raspberry Pi HIL.

## Exact next action

Continue M10.6 with the environment-daemon activation scaffold: construct `EnvironmentServiceCore` from config, policy store, SHT31 adapter and relay adapter behind the existing AF_UNIX server; keep missing sensor/relay target evidence marked degraded or blocked, and do not claim physical acceptance.
