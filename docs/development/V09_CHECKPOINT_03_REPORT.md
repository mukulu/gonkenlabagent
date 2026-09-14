# V09 Checkpoint 03 — Local service and IPC foundation

**Date:** 2026-09-15
**Branch:** `v09-environment-foundation`
**Baseline checkpoint:** V09 Checkpoint 02 at commit `2780d9e38b978be508ee13259e97f3380307e826`
**Development version:** `0.2.0.dev0`
**Governing blueprint:** `GONKEN-V09-BP-GOLD-2026-09-15`

## Completed

1. Added `src/gonken_agent/environment/protocol.py` with bounded JSON protocol v1, request/response dataclasses, size caps, top-level unknown-field rejection and fixed operation/error allowlists.
2. Added `src/gonken_agent/environment/service.py` with a host-testable `EnvironmentServiceCore`, deterministic scripted sensor source and service metadata that keeps `hardware_backend=host_fake` and `physical_evidence=false`.
3. Added `src/gonken_agent/environment/server.py` with local AF_UNIX server behavior: one bounded newline-delimited request per connection, `0660` socket mode and refusal to replace a non-socket path.
4. Added `src/gonken_agent/environment/client.py` with bounded local client calls and explicit daemon-error propagation.
5. Added `tests/unit/test_v09_environment_ipc.py` covering protocol rejection, closed operation parameters, host-fake status/health/sensor read, fan/mode/policy operations, client error propagation and socket lifecycle.
6. Updated M10 ledgers, decisions, test matrix, evidence ledger and implementation status.

## IPC semantics now host-verified

- Only `status.get`, `sensor.read`, `health.get`, `fan.set`, `mode.set`, `policy.get`, `policy.update` and non-destructive `probe.run` are accepted.
- Unknown protocol fields, unknown operations, non-object params and unknown operation parameters fail closed.
- `fan.set` and `mode.set` use the deterministic controller result; client-side errors do not become fake success.
- `policy.update` preserves generation-conflict behavior and validates values through the existing policy layer.
- The AF_UNIX test server creates a `0660` socket and removes it on close.
- The implementation imports no `smbus`, `gpiod`, `subprocess`, raw GPIO setter or shell surface.
- Every host-fake service payload is kept separate from physical evidence.

## Verified evidence

| Evidence | Result | Boundary |
|---|---:|---|
| `docs/development/evidence/v09/wp_d_ipc_affected_tests.log` | PASS, 59/59 | Host-only IPC/controller/domain/policy/config tests |
| `docs/development/evidence/v09/wp_d_full_unit.log` | PASS, 271/271 | Full host unit suite; no integration or hardware evidence |
| `docs/development/evidence/v09/wp_d_static_gates.log` | PASS | Dependency lock, milestone drift, release-readiness allow-dirty, Bash syntax, compileall, TOML/JSON parse and diff-check gates |

## Remaining

- M10.6 CLI, voice, installer, diagnostics and documentation integration: not implemented.
- M10.7 real Raspberry Pi HIL/release acceptance: not run and unavailable in this environment.
- Production SHT31 and libgpiod relay adapters are not implemented in this checkpoint.
- Broad integration/CI remains under the existing Ollama lifecycle interruption timeout caveat from M10.4.

## Blocked items / risks

- No physical Raspberry Pi evidence exists for I2C, SHT31 CRC reads, libgpiod line ownership, relay polarity, PENGLIN USB switching, ELUTENG fan behavior, wake phrase, reboot/no-login behavior or update/rollback with environment hardware.
- The service core currently simulates the hardware boundary and must not be presented as real actuation.
- The AF_UNIX server is host-verified as a Python service object; systemd unit installation, user/group ownership and service restart behavior remain later work.

## Exact next action

Implement M10.6 in safe sub-batches.  First add `gonken-agent env` CLI commands over `EnvironmentClient` for status, temperature/humidity read, fan on/off, mode set, policy get/update, health and JSON output.  Then extend diagnostics/installer/service unit wiring and finally deterministic voice-domain actions.  Do not add real hardware adapters before the CLI/client boundary is stable unless specifically working on the M10.7 hardware tranche.

## Continuation instruction

Continue from this recorded checkpoint and execute the next dependency-ready batch.
