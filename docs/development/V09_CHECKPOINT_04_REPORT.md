# V09 Checkpoint 04 — Operator CLI environment commands

**Date:** 2026-09-15  
**Branch:** `v09-environment-foundation`  
**Baseline checkpoint:** V09 Checkpoint 03 at commit `e91c4739eec0e2eabe2cb939e959117027d889a6`  
**Development version:** `0.2.0.dev0`  
**Governing blueprint:** `GONKEN-V09-BP-GOLD-2026-09-15`

## Completed

1. Added `gonken-agent env` command routing in `src/gonken_agent/cli.py`.
2. Added operator commands for:
   - `env status`;
   - `env health`;
   - `env temperature`;
   - `env humidity`;
   - `env read`;
   - `env fan on` / `env fan off`;
   - `env mode set <mode>`;
   - `env policy show`;
   - `env policy set ...`;
   - `env probe`.
3. Added JSON output support at both parent and leaf positions, including `gonken-agent env status --json`.
4. Kept the CLI as an IPC client only: it constructs an `EnvironmentClient` from the effective socket path or explicit `--socket` and never touches GPIO, I2C, shell, or the policy file directly.
5. Added `tests/unit/test_v09_environment_cli.py` covering routing, output, capability boundary, policy update argument shape, daemon rejection, and no-fake-success behavior.
6. Updated M10 ledgers, decisions, test matrix, evidence ledger and implementation status.

## CLI semantics now host-verified

- Human output reports daemon-returned state rather than intended action alone.
- JSON output returns the daemon/client payload for machine use.
- Capability output preserves `software_speed_control=false` and `fan_motion_observed=false`.
- Mutating commands use typed client methods: `fan_set`, `mode_set`, and `policy_update`.
- `policy set` with no fields fails before contacting the daemon.
- Daemon rejection, such as `ENV_DISABLED`, is surfaced as failure and does not print a fake success message.
- `env probe` maps only to the bounded non-destructive `probe.run` protocol operation.

## Verified evidence

| Evidence | Result | Boundary |
|---|---:|---|
| `docs/development/evidence/v09/wp_e_cli_affected_tests.log` | PASS, 81/81 | Host-only CLI/client/controller/domain/policy/config regression tests |
| `docs/development/evidence/v09/wp_e_full_unit.log` | PASS, 277/277 | Full host unit suite; no physical Pi evidence |
| `docs/development/evidence/v09/wp_e_static_gates.log` | PASS | Dependency lock, milestone drift, release-readiness allow-dirty, Bash syntax, compileall, TOML/JSON parse and diff-check gates |
| `docs/development/evidence/v09/wp_e_integration_subset.log` | PASS, 15/15 | Targeted integration subset; not a broad CI PASS |

## Remaining

- M10.6 diagnostics/support/dashboard environment fields remain unimplemented.
- M10.6 installer/systemd environment-service wiring remains unimplemented.
- M10.6 deterministic voice environment intents and result-derived spoken responses remain unimplemented.
- M10.6 watch-mode/operator documentation remains open.
- M10.7 real Raspberry Pi HIL/release acceptance remains not run and unavailable in this environment.
- Production SHT31 and libgpiod relay adapters are not implemented in this checkpoint.
- Broad integration/CI remains under the existing Ollama lifecycle interruption timeout caveat from M10.4.

## Blocked items / risks

- No physical Raspberry Pi evidence exists for I2C, SHT31 CRC reads, libgpiod line ownership, relay polarity, PENGLIN USB switching, ELUTENG fan behavior, wake phrase, reboot/no-login behavior or update/rollback with environment hardware.
- The CLI can contact only an environment daemon/socket; if that daemon is absent, the command must fail categorically rather than fabricate status.
- The current env CLI does not yet include a live watch loop; this should be added with bounded interval/count semantics in a later M10.6 sub-batch.

## Exact next action

Continue M10.6 with diagnostics/support/dashboard environment status fields or installer/systemd environment-service wiring.  Preserve the same boundary: diagnostics may inspect the environment service/client state, but ordinary doctor/support must remain non-destructive and must not toggle the relay.

## Continuation instruction

Continue from this recorded checkpoint and execute the next dependency-ready batch.
