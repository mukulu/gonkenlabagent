# V09 Change Verification Report — Checkpoint 04

## Scope

This report verifies the first M10.6 sub-batch: an operator-facing `gonken-agent env` CLI over the existing local `EnvironmentClient` boundary.  The change does not implement voice actions, installer/systemd environment service integration, diagnostics/support/dashboard integration, production SHT31/libgpiod adapters, or physical Raspberry Pi acceptance.

## Governing instructions and sources

- `AGENTS.md` requires dependency-ready progress, proportionate checks, updated ledgers, committed resumable checkpoints and explicit separation of host/mock evidence from Raspberry Pi evidence.
- The V09 blueprint requires `gonken-agent env` to be a direct operator route that shares the same typed local interface as voice, without exposing raw GPIO, I2C, shell execution or direct policy-file editing.
- V09 Checkpoint 03 made M10.6 dependency-ready by providing the bounded protocol, service core, AF_UNIX server and client.

## Changed-file and risk classification

| Area | Files | Risk | Verification focus |
|---|---|---|---|
| CLI parser/executor | `src/gonken_agent/cli.py` | Medium | command coverage, JSON placement, client-only boundary, error handling, no fake success |
| CLI tests | `tests/unit/test_v09_environment_cli.py` | Medium | command routing, daemon rejection, policy args, capability boundary, JSON/human output |
| Evidence and ledgers | `docs/development/*`, `docs/development/evidence/v09/*` | Medium | accurate M10.6 partial status, evidence, residual risk and next action |

## Checks executed

| Check | Result | Evidence |
|---|---:|---|
| M10.6 affected CLI/IPC/controller/config/domain/policy/config suite | PASS, 81/81 | `docs/development/evidence/v09/wp_e_cli_affected_tests.log` |
| Full host unit suite | PASS, 277/277 | `docs/development/evidence/v09/wp_e_full_unit.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_e_static_gates.log` |
| Targeted deterministic integration subset | PASS, 15/15 | `docs/development/evidence/v09/wp_e_integration_subset.log` |

## Regression protection added

- CLI tests verify that `env status --json` and `env --json status` both produce machine-readable daemon payloads.
- CLI tests verify temperature and humidity commands call `read_sensor` once and report `physical_evidence=false`.
- CLI tests verify `fan on`, `mode set` and `policy set` pass typed arguments through the client rather than constructing shell commands or editing policy files.
- CLI tests verify `policy set` without fields fails before daemon contact.
- CLI tests verify daemon rejection is reported as failure without printing success output.
- Existing M10.5 IPC tests continue to protect protocol closedness and daemon error propagation.

## Residual risks

1. The deterministic integration suite remains `NEEDS_MANUAL_REVIEW` due the existing Ollama lifecycle interruption/recovery timeout recorded at M10.4.
2. M10.6 is incomplete: voice intents, installer/systemd unit, diagnostics/support/dashboard fields, watch-mode and operator docs remain unimplemented.
3. The CLI currently depends on an already-running environment socket; production service installation and account/group ownership are later M10.6 work.
4. No SHT31/libgpiod hardware adapter or physical acceptance exists in this checkpoint.

## Readiness verdict

**M10.6 CLI sub-batch: PASS with scope limitation.**  The operator CLI surface is host-verified as an IPC client over the existing V09 environment boundary.  M10.6 remains partial, and M10.7 physical acceptance remains not-run.
