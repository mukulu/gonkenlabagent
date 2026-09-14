# V09 Checkpoint 09 — environment-daemon activation scaffold

**Date:** 2026-09-15  
**Base checkpoint:** V09 Checkpoint 08  
**Base commit:** `be11725bd85fa0fa1b4c4f6cf469da94ba48b2d6`  
**Scope:** M10.6 daemon-activation sub-batch, host-verifiable only.

## Completed

- Added `src/gonken_agent/environment/daemon.py`.
- Added config-to-daemon assembly for an explicitly enabled environment profile:
  - static `PolicyBounds` from `extensions.environment`;
  - daemon-owned `PolicyStore` at the configured policy path;
  - default policy creation only when the policy file is absent;
  - corrupt policy refusal without replacement;
  - `SHT31Sensor.from_config`;
  - `GpiodRelayFanActuator.from_config`;
  - `EnvironmentServiceCore` and `EnvironmentUnixServer` wiring.
- Added `EnvironmentDaemon` lifecycle wrapper.
- Added `EnvironmentServiceCore.shutdown_safe_off()` for best-effort shutdown safe-off and adapter cleanup.
- Updated `EnvironmentUnixServer.server_close()` to invoke daemon safe-off cleanup before removing the socket.
- Replaced the enabled-profile `env serve` fail-closed placeholder with a real activation scaffold.
- Added hidden `gonken-agent env serve --check` for bounded construction checks without starting a socket loop or toggling hardware.
- Added `tests/unit/test_v09_environment_daemon_activation.py`.
- Updated `tests/unit/test_v09_environment_cli.py` for the new `env serve --check` contract.
- Updated ledgers, decisions, implementation status, master blueprint and test matrix.

## Verification

| Check | Result | Evidence |
|---|---:|---|
| Daemon activation affected tests | PASS, 34/34 | `docs/development/evidence/v09/wp_j_daemon_activation_affected_tests.log` |
| Full host unit suite | PASS, 311/311 | `docs/development/evidence/v09/wp_j_full_unit.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_j_static_gates.log` |
| Targeted CLI/text integration subset | PASS, 14/14 | `docs/development/evidence/v09/wp_j_integration_subset.log` |

## Evidence boundary

This checkpoint proves host construction and protocol activation scaffolding only. Tests use fake sensor and actuator objects where behavior would otherwise touch hardware. `SHT31Sensor` and `GpiodRelayFanActuator` are constructed but still lazy-open their physical resources. No test opens `/dev/i2c-*`, imports target `smbus` from a Pi environment, requests a real `/dev/gpiochip*` line, validates relay polarity, switches PENGLIN USB power, observes ELUTENG blade motion, or proves systemd/reboot/no-login behavior.

## Remaining

M10.6 remains partial. The next dependency-ready batch should add a bounded autonomous polling/control-loop scaffold for the environment daemon so AUTOMATIC and SEMI_AUTOMATIC control can operate without a client manually invoking `sensor.read`. Target-grounded operator documentation should be finalized only after M10.7 supplies physical evidence. M10.7 remains required for real Raspberry Pi HIL.

## Exact next action

Continue M10.6 with the daemon polling/control-loop scaffold: periodically read the SHT31 through the daemon-owned adapter, feed the controller, apply actuator transitions, preserve safe-off on stale/failure/shutdown, keep resource usage bounded, and verify with fake sensor/actuator/clock tests only. Do not claim physical Raspberry Pi acceptance.
