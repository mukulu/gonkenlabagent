# V09 Checkpoint 19 — Change verification report

## Scope

Verify the checkpoint 19 change set that adds simulation-aware voice response wording and physical acceptance runner blocking for simulated/hybrid backend evidence.

## Risk classification

| Area | Risk | Reason |
|---|---:|---|
| Voice responses | Medium | User-facing statements affect physical-evidence truthfulness and must not overclaim simulation results. |
| Acceptance runner | Medium-high | M10.7 evidence collection must not silently close physical gates while simulation is active. |
| Runtime hardware control | Low | No GPIO/I2C access path was added. |
| Documentation | Low-medium | Documents now describe the evidence boundary and must remain aligned with implemented behavior. |

## Checks executed

| Check | Result | Evidence |
|---|---:|---|
| Affected simulation/voice/HIL tests | PASS, 72/72 | `docs/development/evidence/v09/checkpoint19/affected_simulation_voice_hil_tests.log` |
| T0 static gates | PASS | `docs/development/evidence/v09/checkpoint19/t0_static.log` |
| Unit phase attempt | INTERRUPTED / not PASS | `docs/development/evidence/v09/checkpoint19/unit_phase_attempt.log` |
| Interrupted active module follow-up | PASS, 23/23 | `docs/development/evidence/v09/checkpoint19/interrupted_active_runtime_audio.log` |

## Findings

- Voice temperature/humidity responses now say `In simulation` when the sensor is simulated and explicitly state that this is not a physical room reading.
- Voice fan/action responses now distinguish simulated actuator power from room fan relay power and retain the no blade-motion/no speed-control boundary.
- The physical acceptance runner now inspects parsed command JSON and marks steps `BLOCKED` with `SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED` when simulation/hybrid provenance appears.
- Parsed hybrid/simulation evidence is retained for engineering review but cannot close full M10.7 physical acceptance.

## Residual risk

Full `scripts/ci.sh --phase unit` did not finish within this environment's execution boundary. The active module was rerun narrowly and passed, but this is not a full-unit PASS. Physical M10.7 remains not-run.

## Verdict

Checkpoint 19 is host-verified for its affected scope and ready for the next dependency-ready implementation tranche. It is not a physical Raspberry Pi acceptance checkpoint.
