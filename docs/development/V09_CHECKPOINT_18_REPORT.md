# V09 Checkpoint 18 — Operator Simulation CLI, Passive Watch and Simulation Observability

**Date:** 2026-09-15  
**Base checkpoint:** V09 checkpoint 17 (`17e2a96d0382ad666e086af4e3d7ddd8bc65298b`)  
**Scope:** M10.10 operator simulation experience implementation.  
**Physical Raspberry Pi acceptance:** NOT_RUN / BLOCKED — no target hardware evidence was produced or claimed.

## Completed scope

Checkpoint 18 implements the operator-facing simulation experience from `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md`:

- `gonken-agent env simulate status`;
- `gonken-agent env simulate reset`;
- `gonken-agent env simulate sensor set --temperature-c ... --humidity-pct ...`;
- `gonken-agent env simulate sensor unavailable`;
- `gonken-agent env simulate sensor crc-error`;
- `gonken-agent env simulate sensor stale --age-seconds ...`;
- `gonken-agent env simulate sensor recover --temperature-c ... --humidity-pct ...`;
- `gonken-agent env simulate sensor reset`;
- `gonken-agent env simulate fan show`;
- `gonken-agent env simulate fan behavior normal|unavailable|fail-next-write`;
- `gonken-agent env simulate fan unavailable`;
- `gonken-agent env simulate fan fail-next-write`;
- `gonken-agent env simulate fan reset`.

`env watch` now reads `state.snapshot.get` and is therefore passive.  It no longer calls `sensor.read` on every row.  The watch row includes sensor/actuator provenance, fan state, transition reason, policy generation and `physical_evidence=false`.

Diagnostics, public environment health, support export and dashboard sanitization now include bounded simulation/snapshot summaries so simulation state can be observed without raw content or physical acceptance claims.

## Evidence

| Check | Result | Evidence |
|---|---:|---|
| Operator simulation and observability affected tests | PASS, 54/54 | `docs/development/evidence/v09/checkpoint18/operator_sim_observability_tests.log` |
| T0 static gates | PASS | `docs/development/evidence/v09/checkpoint18/t0_static.log` |
| Targeted CLI/text integration subset | PASS, 14/14 | `docs/development/evidence/v09/checkpoint18/targeted_integration.log` |
| Unit phase attempt | INTERRUPTED / not PASS | `docs/development/evidence/v09/checkpoint18/unit_phase.log` |
| Active interrupted module follow-up | PASS, 3/3 | `docs/development/evidence/v09/checkpoint18/release_readiness_module.log` |

## Current implementation truth

### Implemented and host-verified

- Operator simulation CLI command family.
- Passive `env watch` via daemon snapshot.
- Full-simulation CLI-over-Unix-socket scenario.
- Simulation provenance in diagnostics/support/dashboard paths.
- Continued physical-evidence separation.

### Still pending

- Simulation-aware voice response wording.
- Hybrid HIL evidence/refusal behavior.
- Mandatory default `GonKen` wake phrase and high-recall matcher.
- Post-question progress cues and voice-owned autonomous environment announcements.
- Documentation hardening and real target acceptance.

### Target-gated

- Physical SHT31 detection and CRC-valid read campaign.
- Pi 5 gpiochip/line mapping.
- Relay polarity and boot safe-off.
- PENGLIN wiring and ELUTENG fan cycles.
- Real systemd/no-login convergence.
- Real wake phrase and voice UX timing.

## Exact next action

Proceed to Checkpoint 19: implement simulation-aware voice/hybrid-HIL evidence rules, including truthful voice wording for simulated values and refusal/blocking behavior when physical acceptance commands encounter simulated backends.
