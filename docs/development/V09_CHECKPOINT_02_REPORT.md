# V09 Checkpoint 02 — Deterministic controller core

**Date:** 2026-09-15
**Branch:** `v09-environment-foundation`
**Baseline checkpoint:** V09 Checkpoint 01 at commit `91a2647a6416ab061484e2bf1e993da44fa1cfc1`
**Development version:** `0.2.0.dev0`
**Governing blueprint:** `GONKEN-V09-BP-GOLD-2026-09-15`

## Completed

1. Rechecked and classified the existing Ollama lifecycle interruption/recovery timeout before controller work.  The isolated test again exceeded the bounded container run and left an `ollama_manager.py install-binary` process alive; it is recorded as an existing integration-fixture/harness risk, not as M10.4 controller evidence.
2. Added `src/gonken_agent/environment/controller.py` as a pure deterministic controller core with no I2C, GPIO, audio, systemd, Ollama, shell or network imports.
3. Added `ControllerState`, `ControllerError` and `EnvironmentController` exports under `gonken_agent.environment`.
4. Implemented tested state-machine semantics for MANUAL, SEMI_AUTOMATIC, AUTOMATIC and DISABLED modes.
5. Implemented median valid-sample control temperature, three-sample recovery gating, stale-sensor safe-off for autonomous modes, min-on/min-off dwell, hysteresis transitions, explicit user overrides and policy-update stop behavior.
6. Updated M10 ledgers, decisions, test matrix, evidence ledger and implementation status.

## Controller semantics now host-verified

- Boot initializes the relay-power boundary to OFF.
- MANUAL permits deliberate ON/OFF and does not auto-change based on temperature or sensor failure.
- DISABLED rejects ON and remains safe-off.
- SEMI_AUTOMATIC never auto-starts from temperature alone; explicit ON arms the semi cycle, and low temperature can auto-stop/disarm after dwell.
- AUTOMATIC starts at or above `start_c` and stops at or below `stop_c`, subject to dwell and startup/recovery valid-sample gates.
- Sensor stale/failed/unavailable state forces OFF in AUTO/SEMI but does not overwrite deliberate MANUAL actuator state.
- Generic ON/OFF in AUTO switches atomically to MANUAL plus the requested state.
- Policy updates may stop a running AUTO/SEMI fan when the new stop condition is satisfied, but SEMI policy changes never auto-start an unarmed cycle.

## Verified evidence

| Evidence | Result | Boundary |
|---|---:|---|
| `docs/development/evidence/v09/wp_c_ollama_lifecycle_timeout_recheck.log` | TIMEOUT / INTERRUPTED | Existing integration-fixture risk; not a controller PASS/FAIL |
| `docs/development/evidence/v09/wp_c_controller_affected_tests.log` | PASS, 50/50 | Host-only controller/domain/policy/config tests |
| `docs/development/evidence/v09/wp_c_full_unit.log` | PASS, 262/262 | Full host unit suite; no integration or hardware evidence |
| `docs/development/evidence/v09/wp_c_static_gates.log` | PASS | Dependency lock, milestone drift, release-readiness allow-dirty, Bash syntax, compileall, TOML/JSON parse and diff-check gates |

## Remaining

- M10.5 local environment service and AF_UNIX IPC: not implemented.
- M10.6 CLI, voice, installer, diagnostics and documentation integration: not implemented.
- M10.7 real Raspberry Pi HIL/release acceptance: not run and unavailable in this environment.
- Broad integration/CI still needs manual review around the existing Ollama lifecycle interruption fixture.

## Blocked items / risks

- No SHT31 driver, relay adapter, daemon, socket, CLI command or voice action exists yet.
- No physical Raspberry Pi evidence exists for I2C, SHT31 CRC reads, libgpiod line ownership, relay polarity, PENGLIN USB switching, ELUTENG fan behavior, wake phrase, reboot/no-login behavior or update/rollback with environment hardware.
- The controller reports software relay-power state only; it does not prove physical blade motion or speed.

## Exact next action

Implement M10.5 with tests first: define the versioned local protocol/client/server contract and a host-only fake-service path for `status.get`, `sensor.read`, `health.get`, `fan.set`, `mode.set`, `policy.get`, `policy.update` and bounded error handling.  Do not import `smbus`, `gpiod` or real hardware libraries in the first service/IPC tests.

## Continuation instruction

Continue from this recorded checkpoint and execute the next dependency-ready batch.
