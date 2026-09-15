# V09 Change Verification Report — Checkpoint 14

## Scope

Verify the release lifecycle CI decomposition introduced after checkpoint 13.

## Changed files

- `scripts/bounded_unittest.py`
- `scripts/ci.sh`
- `tests/unit/test_bounded_unittest_runner.py`
- `tests/integration/test_release_lifecycle_process.py`
- V09 development ledgers and reports

## Risk classification

Medium. The change affects the canonical host CI orchestration and release lifecycle integration tests. It does not alter production appliance runtime behavior, environment daemon semantics, installer actuation, SHT31 reads, relay control or physical acceptance rules.

## Checks executed

| Check | Result |
|---|---:|
| `PYTHONPATH=src:$PWD python3 -m unittest -v tests.unit.test_bounded_unittest_runner` | PASS, 6/6 |
| Affected runner + release interruption/finalization slice | PASS, 10/10 |
| Individual decomposed release E2E cases | PASS, 4/4 |
| Static gates recorded in `wp_o_static_gates.log` | PASS |
| Multi-case bounded-runner attempt | INTERRUPTED / not PASS |

## Findings

- The bounded runner now supports module-level and case-level execution.
- Exclusion support allows a heavy module to be omitted from ordinary module-granularity integration and run separately at finer granularity.
- `scripts/ci.sh` now routes `tests.integration.test_release_lifecycle_process` through case-level execution without reducing coverage.
- The formerly combined release-only/default-boundary E2E test is split into named cases, so a future timeout identifies the exact release boundary.
- The decomposed release cases passed individually on the host development root.

## Residual risk

No full post-change `scripts/ci.sh` PASS is claimed. The multi-case bounded-runner attempt was interrupted by the external session boundary after partial output and is diagnostic only. Physical M10.7 remains not-run and cannot be inferred from host CI success.
