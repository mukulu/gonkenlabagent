# V09 Checkpoint 17 Change Verification Report

## Scope

Verify checkpoint 17: implementation of the V09 simulation/HIL foundation layer. The change must add simulated sensor and actuator backends behind the existing environment service boundary while preserving checkpoint-15 verified behavior and the physical-acceptance boundary.

## Governing instructions

- `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md`
- `docs/development/V09_SIMULATION_HIL_TRACEABILITY.csv`
- V09 checkpoint-16 continuation instruction
- Existing V09 architecture: one environment daemon owns sensor/relay state; CLI and voice are clients; host/simulation evidence cannot close physical Raspberry Pi acceptance.

## Changed-file and risk classification

| Area | Files | Risk |
|---|---|---|
| Config/schema | `config/defaults.toml`, `src/gonken_agent/config.py` | Medium, affects validation and daemon construction |
| Simulation domain | `environment/simulation.py`, simulated sensor/actuator adapters | Medium, new runtime state and fault behavior |
| Service/protocol/client | `service.py`, `protocol.py`, `client.py`, `daemon.py` | Medium/high, affects local daemon API and factory construction |
| CLI safety | `cli.py`, `test_v09_environment_cli.py` | Medium, corrects non-actuating check semantics |
| Tests | `test_v09_environment_simulation.py`, affected environment tests | Medium, core regression evidence |
| Project ledgers | development docs and evidence logs | Medium, must not create false PASS claims |

## Checks planned versus executed

| Check | Result | Evidence |
|---|---:|---|
| Simulation foundation tests | PASS, 13/13 | `docs/development/evidence/v09/checkpoint17/simulation_foundation_tests.log` |
| Affected environment/config/IPC/daemon/adapter/polling/CLI slice | PASS, 57/57 | `docs/development/evidence/v09/checkpoint17/affected_environment_slice.log` |
| T0 static gates | PASS | `docs/development/evidence/v09/checkpoint17/t0_static.log` |
| Unit phase attempt | INTERRUPTED / not PASS | `docs/development/evidence/v09/checkpoint17/unit_phase.log` |
| Active interrupted module follow-up | PASS, 8/8 | `docs/development/evidence/v09/checkpoint17/m6_service_manager_module.log` |

## Diff and generated-artifact findings

- Configuration now allows `sensor_backend=simulated` and `relay_backend=simulated` while rejecting unknown backend names.
- Simulation mutation requires explicit runtime-control enablement and the matching simulated backend axis.
- Simulation state is daemon-owned and not persisted in mutable policy.
- Simulated sensor faults and actuator behaviors are exercised through the same service/protocol path used by ordinary daemon operations.
- Responses carry backend/evidence provenance, with `physical_evidence=false` for simulation paths.
- `state.snapshot.get` and `events.get` provide passive protocol primitives for later watch conversion.
- `env serve --check` no longer calls safe-off cleanup during construction validation.
- No production hardware acceptance row was marked PASS.

## Regression protection

The affected environment slice reruns config, IPC, daemon activation, adapter, polling and CLI tests from previous checkpoints plus the new simulation tests. This protects the prior M10.6 host behavior while adding the simulation foundation.

Specific regression coverage added:

- simulated sensor values and faults are truthful;
- invalid simulated readings are rejected;
- simulated actuator unavailable and fail-next behavior do not import or require libgpiod;
- backend factories select simulated backends without physical adapters;
- simulation protocol rejects disabled control and wrong backend axes;
- AF_UNIX path returns stable simulation errors;
- actuator fail-next-write becomes `ACTUATOR_UNAVAILABLE` and safe-off behavior remains bounded;
- `env serve --check` does not call safe-off or resource cleanup that could request GPIO.

## Residual risks

- The full unit phase is not yet complete in this environment; the current attempt was externally interrupted and is preserved only as diagnostic evidence. The active module at interruption was rerun narrowly and passed 8/8.
- The evidence-mode classifier currently reflects backend mode and physical-evidence truth but does not independently prove whether execution occurred on host or Raspberry Pi. Target runners must still bind target identity and hardware evidence.
- Operator-facing simulation CLI, passive watch, diagnostics/support/dashboard simulation surfacing and voice wording are not implemented in this checkpoint.
- Physical SHT31, relay, fan, systemd and wake acceptance remain not-run.

## Readiness verdict

Checkpoint 17 is **HOST_VERIFIED for M10.9 simulation foundations** and **NOT_RUN for physical Raspberry Pi acceptance**.

## Exact next action

Proceed to checkpoint 18: implement operator simulation commands, passive watch semantics, diagnostics/support/dashboard simulation visibility and full-simulation operator tests, then rerun affected host checks before packaging.
