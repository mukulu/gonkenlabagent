# V09 Change Verification Report — Checkpoint 13

## Scope

Verify the host-side bounded CI runner change introduced after checkpoint 12.

## Changed files

- `scripts/bounded_unittest.py`
- `scripts/ci.sh`
- `tests/unit/test_bounded_unittest_runner.py`
- V09 development ledgers and reports

## Risk classification

Medium. The change affects the canonical host CI entry point. It does not alter production appliance runtime behavior, installer actuation, environment daemon semantics, SHT31 reads or relay control.

## Checks executed

| Check | Result |
|---|---:|
| `PYTHONPATH=src:. python3 -m unittest -v tests.unit.test_bounded_unittest_runner tests.unit.test_test_architecture` | PASS, 9/9 |
| Static gates recorded in `wp_n_static_gates.log` | PASS |
| Bounded integration slice for Ollama lifecycle + CLI process | PASS, 2/2 |
| Bounded release lifecycle aggregate attempt | INTERRUPTED / NEEDS_MANUAL_REVIEW |

## Findings

- The bounded runner correctly records passing, failing and timed-out modules.
- `scripts/ci.sh` now uses the bounded runner for unit and deterministic integration suites.
- The integration slice demonstrates heartbeat/log behavior on real project integration modules.
- The release lifecycle aggregate remains too long for the available session window, but the active module is now visible instead of hidden behind a monolithic `unittest discover` process.

## Residual risk

No full broad-CI PASS is claimed. Physical M10.7 remains not-run. The release E2E fixture may need further decomposition or a longer dedicated host run.
