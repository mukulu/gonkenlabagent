# V09 Change Verification Report — Checkpoint 03

## Scope

This report verifies the M10.5 local environment service and IPC foundation on branch `v09-environment-foundation`.  The change adds protocol, service-core, AF_UNIX server and client code plus host-only tests.  It does not implement the user-facing CLI, voice actions, installer/systemd integration, diagnostics/dashboard integration, hardware adapters or physical Raspberry Pi acceptance.

## Governing instructions and sources

- `AGENTS.md` requires dependency-ready progress, proportionate checks, updated ledgers, committed resumable checkpoints and explicit separation of host/mock evidence from Raspberry Pi evidence.
- The V09 blueprint requires a single-owner `gonken-environment.service` boundary with bounded AF_UNIX JSON operations before CLI and voice routes are attached.
- V09 Checkpoint 02 required M10.5 to define protocol/client/server tests and implement a local IPC service boundary without importing hardware libraries.

## Changed-file and risk classification

| Area | Files | Risk | Verification focus |
|---|---|---|---|
| Protocol | `src/gonken_agent/environment/protocol.py` | Medium | operation allowlist, size bounds, unknown-field rejection, response validation |
| Service core | `src/gonken_agent/environment/service.py` | Medium | controller-policy translation, closed params, daemon errors, host-fake evidence boundary |
| AF_UNIX server | `src/gonken_agent/environment/server.py` | Medium | bounded request handling, socket mode, non-socket refusal, cleanup |
| Local client | `src/gonken_agent/environment/client.py` | Medium | bounded daemon call, response parsing, no fake success on error |
| Tests | `tests/unit/test_v09_environment_ipc.py` | Medium | positive/negative IPC, service and socket paths |
| Development ledgers | `docs/development/*`, `docs/development/evidence/v09/*` | Medium | accurate M10.5 status, evidence, residual risk and next action |

## Checks executed

| Check | Result | Evidence |
|---|---:|---|
| M10.5 affected IPC/controller/config/domain/policy suite | PASS, 59/59 | `docs/development/evidence/v09/wp_d_ipc_affected_tests.log` |
| Full host unit suite | PASS, 271/271 | `docs/development/evidence/v09/wp_d_full_unit.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_d_static_gates.log` |

## Regression protection added

- Protocol tests reject unsupported protocol versions, unknown operations, unknown top-level fields, non-object params and oversized response data.
- Source-inspection tests protect the IPC/service layer from accidental `smbus`, `gpiod`, `subprocess`, shell or raw GPIO setter imports.
- Service-core tests protect status/health/sensor-read semantics and preserve `physical_evidence=false`.
- Mutation tests protect policy generation conflicts, disabled-mode ON rejection and bad parameter rejection.
- Socket tests protect `0660` local socket creation, removal on close and refusal to replace non-socket paths.
- Client tests protect against fake success when the daemon returns `ENV_DISABLED`.

## Residual risks

1. The deterministic integration suite remains `NEEDS_MANUAL_REVIEW` due the existing Ollama lifecycle interruption/recovery timeout recorded at M10.4.
2. M10.5 does not create or install `gonken-environment.service`; systemd, account/group ownership and installer migration remain M10.6 work.
3. M10.5 does not implement real SHT31 or libgpiod relay adapters; all service evidence is host-fake and explicitly not physical acceptance.
4. CLI and voice routes remain unavailable until M10.6 attaches them to `EnvironmentClient`.

## Readiness verdict

**M10.5 host IPC checkpoint: PASS with integration-suite caveat.**  The bounded local service/client/server foundation is host-verified.  M10.6 is now dependency-ready.  M10.7 physical acceptance remains not-run.
