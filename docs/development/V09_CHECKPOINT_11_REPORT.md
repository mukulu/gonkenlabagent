# V09 Checkpoint 11 — target-readiness and M10.7 evidence scaffold

**Date:** 2026-09-15  
**Base checkpoint:** V09 Checkpoint 10  
**Base commit:** `b07ad80c3c7f504686da35da2c4c34fed4b9f89e`  
**Scope:** Final host-side M10.6 tranche: target-readiness documentation and private evidence-file scaffold for M10.7.

## Completed

- Added `scripts/environment_acceptance_runner.py`.
- Added private evidence output contract:
  - `m10_7_evidence_manifest.json`;
  - `m10_7_private_evidence_ledger.csv`;
  - per-step JSON files under `private_evidence/`.
- Added non-destructive collection steps for platform identity, service state, `gonken-agent status`, environment status, health, sensor read, non-destructive probe, and recent journals.
- Added manual-gate placeholders for wiring inspection, reboot/no-login convergence and wake/voice evidence.
- Added explicit `--allow-actuation` requirement before fan ON/OFF cycle commands are run.
- Ensured every manifest/step records `physical_acceptance_claimed=false`.
- Added `docs/ENVIRONMENT_ACCEPTANCE_RUN.md` and linked it from the main runbook and README.
- Updated release readiness so M10.1-M10.6 are required host gates and M10.7 remains an explicit target gate.
- Added the evidence runner to the immutable release maintenance payload.
- Updated M10 ledgers, decisions, test matrix, evidence ledger and status documents.

## Verification

| Check | Result | Evidence |
|---|---:|---|
| Acceptance-scaffold affected tests | PASS, 8/8 | `docs/development/evidence/v09/wp_l_acceptance_scaffold_affected_tests.log` |
| Full host unit suite | PASS, 321/321 | `docs/development/evidence/v09/wp_l_full_unit.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_l_static_gates.log` |
| Release-readiness report | READY_FOR_TARGET_ACCEPTANCE | `docs/development/evidence/v09/wp_l_release_readiness.json` |
| Real Pi HIL | NOT_RUN / BLOCKED | M10.7 target evidence required |

## Evidence boundary

This checkpoint proves that the target evidence scaffold and documentation are host-verifiable and packaged. It does not prove I2C access, SHT31 detection, repeated CRC-valid reads, gpiochip mapping, relay polarity, PENGLIN USB switching, ELUTENG fan cycles, fan blade motion, target systemd execution, reboot/no-login convergence or wake phrase performance.

The runner can collect private evidence on the Pi, but it does not decide acceptance. Command PASS cannot replace human observation of wiring, relay/fan behavior or voice/audio behavior.

## Remaining

M10.6 is host-verified. M10.7 remains not-run and requires physical Raspberry Pi execution with the purchased SHT31, relay, PENGLIN adapters, ELUTENG fan and audio/wake setup.

## Exact next action

Run the Raspberry Pi acceptance runbook and the private M10.7 environment evidence collector on the target Pi. Preserve the support ZIP, `m10_7_evidence_manifest.json`, `m10_7_private_evidence_ledger.csv`, and `private_evidence/` directory.
