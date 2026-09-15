# V09 Change Verification Report — Checkpoint 12

## Scope

Verify the checkpoint 12 host-quality change: make the Ollama/release interruption test harness bounded and reproducible so known broad-CI stalls do not hide real V09 status.

## Changed files

- `scripts/ollama_manager.py`
- `scripts/release_manager.py`
- `tests/integration/test_ollama_lifecycle_process.py`
- `docs/development/*` checkpoint/evidence ledgers

## Risk classification

Medium. The runtime product path is unchanged unless explicit test-failure environment variables are set. The affected logic is test-only interruption injection, but it guards release and Ollama lifecycle evidence, so the verification burden is higher than a documentation-only change.

## Checks executed

| Check | Result |
|---|---:|
| `python3 -m unittest tests.integration.test_ollama_lifecycle_process -v` | PASS, 5/5 |
| `python3 -m unittest tests.integration.test_release_lifecycle_process.ActivationInterruptionTests -v` | PASS, 3/3 |
| `python3 -m unittest -v tests.unit.test_m3_4_ollama_manager tests.unit.test_m3_3_release_manager` | PASS, 23/23 |
| Static dependency/syntax/compile/config/diff gates | PASS |
| Full release lifecycle aggregate | INTERRUPTED / NEEDS_MANUAL_REVIEW |
| Full unit aggregate attempt | INTERRUPTED / NEEDS_MANUAL_REVIEW |

## Findings

- The former Ollama interruption fixture no longer requires killing a parent shell to simulate an interrupted manager process.
- Interrupted child commands now return bounded signal-style exit codes and can be resumed successfully.
- The default integration test remains representative and bounded; exhaustive before/during/after coverage is still available through `GONKEN_EXHAUSTIVE_OLLAMA_BOUNDARIES=1`.
- No physical Raspberry Pi acceptance is changed or claimed.

## Readiness verdict

Checkpoint 12 is acceptable as host-quality hardening with explicit aggregate-CI limitations. It does not close M10.7.
