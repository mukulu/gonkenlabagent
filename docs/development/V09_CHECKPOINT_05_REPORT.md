# V09 Checkpoint 05 — Environment observability, support, and dashboard fields

**Date:** 2026-09-15  
**Branch:** `v09-environment-foundation`  
**Baseline checkpoint:** V09 Checkpoint 04 at commit `a38c7bee71e4116d3c629104fb7fe151fd130721`  
**Development version:** `0.2.0.dev0`  
**Governing blueprint:** `GONKEN-V09-BP-GOLD-2026-09-15`

## Completed

1. Added non-destructive room-environment diagnostics to `src/gonken_agent/diagnostics.py`.
2. Added `gonken-environment.service`, `i2cdetect`, and `gpioinfo` to bounded startup snapshot visibility.
3. Added environment diagnostic fields for static configuration, device presence, socket/policy path status, systemd state, IPC read-only health, and capability boundary.
4. Added an `environment` health component in `src/gonken_agent/health.py` and wired it into `doctor` output in `src/gonken_agent/operations.py`.
5. Extended support bundles in `src/gonken_agent/support.py` with `environment_control.json` and `environment_health.json` while preserving redacted configuration and content-free telemetry rules.
6. Extended read-only dashboard snapshots in `src/gonken_agent/dashboard.py` with sanitized environment status, capability and target-evidence fields.
7. Updated tests in:
   - `tests/unit/test_diagnostics_snapshot.py`;
   - `tests/unit/test_support_export.py`;
   - `tests/unit/test_grounding_observability.py`;
   - `tests/integration/test_text_runtime_process.py`.
8. Updated M10 ledgers, decisions, test matrix, evidence ledger and implementation status.

## Observability semantics now host-verified

- Routine diagnostics are non-destructive: they do not toggle relays, open GPIO lines, mutate policy, perform arbitrary I2C transactions, or claim hardware acceptance.
- Environment diagnostics distinguish configured static values, device/path presence, systemd state and read-only IPC health.
- Support bundles include environment-control state but preserve content-free and path-redaction expectations.
- Dashboard status includes sanitized environment status and preserves `physical_evidence=false` and `software_speed_control=false`.
- `doctor` can report voice/system readiness and environment partial capability separately.

## Verified evidence

| Evidence | Result | Boundary |
|---|---:|---|
| `docs/development/evidence/v09/wp_f_observability_affected_tests.log` | PASS, 29/29 | Host-only diagnostics/support/dashboard unit slice |
| `docs/development/evidence/v09/wp_f_full_unit.log` | PASS, 278/278 | Full host unit suite; no physical Pi evidence |
| `docs/development/evidence/v09/wp_f_static_gates.log` | PASS | Dependency lock, milestone drift, release-readiness allow-dirty, Bash syntax, compileall, TOML/JSON parse and diff-check gates |
| `docs/development/evidence/v09/wp_f_integration_subset.log` | PASS, 10/10 | Targeted dashboard/text/support integration subset; not a broad CI PASS |
| `docs/development/evidence/v09/wp_f_broad_ci_bounded.log` | INTERRUPTED | Broad CI bounded attempt reached the known Ollama lifecycle interruption/recovery fixture and was cleaned up; not a PASS and not attributed to this observability tranche |

## Remaining

- M10.6 installer/systemd environment-service wiring remains unimplemented.
- M10.6 deterministic voice environment intents and result-derived spoken responses remain unimplemented.
- M10.6 watch-mode/operator documentation remains open.
- Production SHT31 and libgpiod relay adapters remain unimplemented.
- M10.7 real Raspberry Pi HIL/release acceptance remains not run and unavailable in this environment.
- Broad integration/CI remains under the existing Ollama lifecycle interruption timeout caveat from M10.4; the bounded Checkpoint 05 broad-CI attempt was interrupted at the same fixture and preserved as `wp_f_broad_ci_bounded.log`.

## Blocked items / risks

- No physical Raspberry Pi evidence exists for I2C, SHT31 CRC reads, libgpiod line ownership, relay polarity, PENGLIN USB switching, ELUTENG fan behavior, wake phrase, reboot/no-login behavior or update/rollback with environment hardware.
- Environment IPC health is read-only and can prove only that the daemon responded, not that physical hardware is wired or accepted.
- Support/dashboard/doctor now expose environment fields, but production service installation, runtime directory ownership, group permissions and systemd lifecycle are still later M10.6 work.

## Exact next action

Continue M10.6 with installer/systemd environment-service wiring or deterministic voice environment intents.  Preserve the existing boundary: installer work may provision accounts, groups, paths and units, but it must keep generic upgrades disabled by default and must not treat missing hardware as physical acceptance.

## Continuation instruction

Continue from this recorded checkpoint and execute the next dependency-ready batch.
