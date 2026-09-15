# V09 Checkpoint 17 — Simulation Foundations

**Date:** 2026-09-15  
**Base checkpoint:** V09 checkpoint 16 (`eecbf6b`)  
**Scope:** First implementation checkpoint for the V09 simulation/HIL extension.  
**Physical Raspberry Pi acceptance:** NOT_RUN / BLOCKED — no target hardware evidence was produced or claimed.

## Completed scope

Checkpoint 17 implements the M10.9 foundation layer from `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md`.

Implemented changes:

- added static configuration support for independent simulated axes:
  - `sensor_backend = "simulated"`;
  - `relay_backend = "simulated"`;
  - `simulation_runtime_control_enabled`;
  - `simulation_event_history_limit`;
- added daemon-owned simulation state with session ID, generation, bounded event log, sensor value/fault state and actuator behavior;
- added simulated sensor adapter behind the existing `EnvironmentSensor` boundary;
- added simulated actuator adapter behind the existing `FanActuator` boundary;
- added backend factory selection for physical and simulated sensor/actuator combinations;
- added backend/evidence provenance to service identity and ordinary daemon responses;
- added protocol/client operations for simulation status, reset, sensor set/fault/reset, actuator behavior/reset, passive snapshot and event retrieval;
- added host tests for simulated sensor, simulated actuator, simulation protocol, fault injection, factory selection and service behavior;
- corrected `gonken-agent env serve --check` so it validates construction/configuration without calling a safe-off cleanup path that could request or write a GPIO relay line.

## Evidence

| Check | Result | Evidence |
|---|---:|---|
| Simulation foundation unit tests | PASS, 13/13 | `docs/development/evidence/v09/checkpoint17/simulation_foundation_tests.log` |
| Affected environment/config/IPC/daemon/adapter/polling/CLI slice | PASS, 57/57 | `docs/development/evidence/v09/checkpoint17/affected_environment_slice.log` |
| `scripts/ci.sh --phase t0` | PASS | `docs/development/evidence/v09/checkpoint17/t0_static.log` |
| `scripts/ci.sh --phase unit` attempt | INTERRUPTED / not PASS | `docs/development/evidence/v09/checkpoint17/unit_phase.log` |
| Active unit module follow-up | PASS, 8/8 | `docs/development/evidence/v09/checkpoint17/m6_service_manager_module.log` |

## Current implementation truth

### Implemented and host-verified

- Simulated sensor backend and faults.
- Simulated actuator backend and fault behavior.
- Independent backend axes at config/factory level.
- Daemon-owned simulation state and provenance.
- Simulation protocol operations and client helpers.
- Passive snapshot/event protocol primitives.
- Non-actuating `env serve --check` behavior.

### Still pending

- User-facing `gonken-agent env simulate ...` CLI commands.
- Conversion of `gonken-agent env watch` to passive snapshot mode.
- Diagnostics/support/dashboard simulation visibility.
- Simulation-aware voice response wording.
- Hybrid HIL acceptance runner behavior and refusal rules.
- Mandatory `GonKen` wake implementation and progress cues.
- Hardware setup, simulation and troubleshooting documentation.

### Target-gated

- Physical SHT31 detection and CRC-valid read campaign.
- Pi 5 gpiochip/line mapping.
- Relay polarity and boot safe-off.
- PENGLIN wiring and ELUTENG fan cycles.
- Real systemd/no-login convergence.
- Real wake phrase and voice UX timing.

## Files changed

- `config/defaults.toml`
- `docs/development/DECISIONS.md`
- `docs/development/IMPLEMENTATION_STATUS.md`
- `docs/development/MASTER_BLUEPRINT.md`
- `docs/development/MILESTONES.json`
- `docs/development/TEST_MATRIX.md`
- `docs/development/V09_EVIDENCE_LEDGER.csv`
- `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md`
- `docs/development/V09_SIMULATION_HIL_TRACEABILITY.csv`
- `docs/development/V09_CHECKPOINT_17_REPORT.md`
- `docs/development/V09_CHANGE_VERIFICATION_REPORT_CHECKPOINT_17.md`
- `src/gonken_agent/cli.py`
- `src/gonken_agent/config.py`
- `src/gonken_agent/environment/__init__.py`
- `src/gonken_agent/environment/client.py`
- `src/gonken_agent/environment/daemon.py`
- `src/gonken_agent/environment/domain.py`
- `src/gonken_agent/environment/protocol.py`
- `src/gonken_agent/environment/service.py`
- `src/gonken_agent/environment/simulation.py`
- `src/gonken_agent/environment/sensors/__init__.py`
- `src/gonken_agent/environment/sensors/simulated.py`
- `src/gonken_agent/environment/actuators/__init__.py`
- `src/gonken_agent/environment/actuators/simulated.py`
- `tests/unit/test_v09_environment_cli.py`
- `tests/unit/test_v09_environment_simulation.py`

## Remaining risk

A full unit-phase PASS is not claimed in this environment. The unit phase attempt was interrupted by the current external execution boundary after partial module progress. The focused checkpoint tests and affected environment slice passed, and no failure was attributed to the checkpoint-17 simulation code.

Simulation evidence remains simulation evidence. It supports user testing and hybrid HIL preparation, but it does not close real SHT31, relay, fan, audio or wake acceptance.

## Exact next action

Implement checkpoint 18: add the user-facing `gonken-agent env simulate ...` command family, convert watch to passive `state.snapshot.get`, expose simulation provenance in diagnostics/support/dashboard, and add full-simulation operator acceptance tests.
