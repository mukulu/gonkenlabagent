# V09 Change Verification Report — Checkpoint 05

## Scope

This report verifies the second M10.6 sub-batch: environment observability fields in diagnostics, doctor, support bundle and dashboard surfaces.  The change does not implement voice actions, installer/systemd environment service provisioning, production SHT31/libgpiod adapters, or physical Raspberry Pi acceptance.

## Governing instructions and sources

- `AGENTS.md` requires dependency-ready progress, proportionate checks, updated ledgers, committed resumable checkpoints and explicit separation of host/mock evidence from Raspberry Pi evidence.
- The V09 blueprint requires diagnostics/support/dashboard to report environment service state, sensor/relay/policy/capability fields, and partial readiness without destructive probing or false hardware claims.
- V09 Checkpoint 04 made this sub-batch dependency-ready by exposing the environment client/operator boundary.

## Changed-file and risk classification

| Area | Files | Risk | Verification focus |
|---|---|---|---|
| Diagnostics/startup snapshot | `src/gonken_agent/diagnostics.py` | Medium | non-destructive environment fields, path privacy, read-only IPC health, no hardware acceptance claim |
| Health/doctor operations | `src/gonken_agent/health.py`, `src/gonken_agent/operations.py` | Medium | partial environment health, stable component code, voice/environment separation |
| Support bundle | `src/gonken_agent/support.py` | Medium | allow-listed members, content-free output, path redaction, no raw files |
| Dashboard snapshot | `src/gonken_agent/dashboard.py` | Medium | sanitized environment status, loopback-only read API, no content persistence |
| Tests | `tests/unit/*`, `tests/integration/test_text_runtime_process.py` | Medium | observability regression and false-green prevention |
| Evidence and ledgers | `docs/development/*`, `docs/development/evidence/v09/*` | Medium | accurate M10.6 partial status, evidence, residual risk and next action |

## Checks executed

| Check | Result | Evidence |
|---|---:|---|
| M10.6 observability affected suite | PASS, 29/29 | `docs/development/evidence/v09/wp_f_observability_affected_tests.log` |
| Full host unit suite | PASS, 278/278 | `docs/development/evidence/v09/wp_f_full_unit.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_f_static_gates.log` |
| Targeted dashboard/text/support integration subset | PASS, 10/10 | `docs/development/evidence/v09/wp_f_integration_subset.log` |
| Bounded broad CI attempt | INTERRUPTED | `docs/development/evidence/v09/wp_f_broad_ci_bounded.log` |

## Regression protection added

- Diagnostics tests verify that environment snapshot data is content-free, non-destructive and does not expose local temporary root paths.
- Diagnostics tests verify the capability boundary: no software speed control and no physical evidence claim.
- Support tests verify new environment support members are present, bounded and do not leak raw files or private paths.
- Dashboard tests verify sanitized environment status appears in the read-only snapshot and rejects unsafe status codes.
- Integration tests verify `/api/status` includes environment status while preserving loopback-only and no-mutation behavior.

## Residual risks

1. The deterministic integration suite remains `NEEDS_MANUAL_REVIEW` due the existing Ollama lifecycle interruption/recovery timeout recorded at M10.4. The Checkpoint 05 bounded broad-CI attempt reached that same fixture and was interrupted/cleaned up rather than reported as either PASS or product FAIL.
2. M10.6 is incomplete: installer/systemd unit wiring, deterministic voice intents, watch-mode/operator docs and production hardware adapters remain unimplemented.
3. Environment diagnostics can report configured paths, service state and read-only daemon health, but cannot prove SHT31, relay, fan, wiring or Pi 5 gpiochip acceptance.
4. `doctor`, dashboard and support bundle now include environment fields; target-run verification is still needed to confirm that these fields are useful on the real Raspberry Pi.

## Readiness verdict

**M10.6 observability sub-batch: PASS with scope limitation.**  Diagnostics/support/dashboard are host-verified for non-destructive environment visibility.  M10.6 remains partial, and M10.7 physical acceptance remains not-run.
