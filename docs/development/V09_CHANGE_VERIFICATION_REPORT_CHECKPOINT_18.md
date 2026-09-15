# V09 Checkpoint 18 Change Verification Report

## Scope

Verify checkpoint 18: implementation of the operator simulation CLI, passive watch behavior and simulation observability in diagnostics/support/dashboard while preserving checkpoint-15 verified behavior and keeping physical Raspberry Pi acceptance open.

## Governing instructions

- `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md`
- `docs/development/V09_SIMULATION_HIL_TRACEABILITY.csv`
- V09 checkpoint-17 continuation instruction
- Existing V09 invariant: one environment daemon owns sensor/relay/simulation state; CLI and voice are clients; simulation evidence cannot close physical acceptance.

## Changed-file and risk classification

| Area | Files | Risk |
|---|---|---|
| Operator CLI | `src/gonken_agent/cli.py`, `tests/unit/test_v09_environment_cli.py` | Medium, user-facing command family and passive watch semantics |
| Observability | `diagnostics.py`, `operations.py`, `support.py`, `dashboard.py`, tests | Medium, support/dashboard payload contracts and content-free visibility |
| Simulation acceptance tests | `tests/unit/test_v09_environment_simulation.py` | Medium, end-to-end host simulation confidence |
| Documentation/ledgers | `docs/OPERATIONS.md`, development status, matrix, decisions and evidence ledger | Medium, must avoid false physical acceptance language |

## Checks planned versus executed

| Check | Result | Evidence |
|---|---:|---|
| Operator simulation and observability affected tests | PASS, 54/54 | `docs/development/evidence/v09/checkpoint18/operator_sim_observability_tests.log` |
| T0 static gates | PASS | `docs/development/evidence/v09/checkpoint18/t0_static.log` |
| Targeted CLI/text integration subset | PASS, 14/14 | `docs/development/evidence/v09/checkpoint18/targeted_integration.log` |
| Unit phase attempt | INTERRUPTED / not PASS | `docs/development/evidence/v09/checkpoint18/unit_phase.log` |
| Active interrupted module follow-up | PASS, 3/3 | `docs/development/evidence/v09/checkpoint18/release_readiness_module.log` |

## Diff and generated-artifact findings

- The `env simulate` command family maps only to existing allow-listed environment client methods.
- Watch now calls `snapshot()` rather than `read_sensor()`, preventing observer effects from watch terminals.
- Diagnostics call daemon health plus optional simulation status and snapshot. Failures in optional calls degrade to bounded summary fields.
- Dashboard sanitization preserves simulation/snapshot tokens while rejecting malformed fields.
- Support bundles continue to export only constructed allow-listed JSON, now with simulation observability included through `environment_control.json` and `environment_health.json`.
- Every simulation/watch/diagnostic path preserves `physical_evidence=false` unless a future target acceptance process explicitly supplies different evidence.

## Regression protection

- CLI fake-client tests prove typed calls for simulation status, sensor mutations and actuator fault injection.
- CLI watch test proves snapshot calls replace repeated sensor reads.
- Full-simulation CLI-over-Unix-socket test exercises command parsing, client, server, daemon, simulation state and passive watch observation.
- Diagnostics/dashboard/support tests prove content-free simulation visibility and physical-evidence separation.

## Residual risks

- Full unit phase was interrupted by the external execution boundary and is not claimed as PASS.
- Simulation-aware voice wording and hybrid HIL evidence blocking are not implemented in this checkpoint.
- Physical Raspberry Pi acceptance remains not-run.

## Readiness verdict

Checkpoint 18 is **HOST_VERIFIED for M10.10 operator simulation experience**. It is **not** a physical acceptance checkpoint.
