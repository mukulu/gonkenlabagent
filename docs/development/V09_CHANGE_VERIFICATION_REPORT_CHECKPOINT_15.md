# V09 Change Verification Report — Checkpoint 15

## Scope

Verify the CI phase-selection change introduced after checkpoint 14.

## Changed files

- `scripts/ci.sh`
- `tests/unit/test_bounded_unittest_runner.py`
- V09 development ledgers and reports

## Risk classification

Low-to-medium.  The change affects the canonical host CI orchestration, but not production appliance runtime behavior, environment daemon semantics, installer actuation, SHT31 reads, relay control or physical acceptance rules.  The main risk is accidentally skipping required checks; this is controlled by preserving the no-argument full-run default and testing the phase interface.

## Checks executed

| Check | Result |
|---|---:|
| `python3 -m unittest -v tests.unit.test_bounded_unittest_runner` | PASS, 8/8 |
| `./scripts/ci.sh --phase t0` | PASS |
| `bash -n scripts/ci.sh` | PASS |
| Python compile check for `scripts` and touched unit test | PASS |
| `./scripts/ci.sh --list-phases` | PASS |
| `./scripts/ci.sh --phase unknown` | PASS as expected refusal, rc=2 |
| Full aggregate CI under external 240-second wrapper | INTERRUPTED / not PASS |
| Standalone `--phase unit` attempt under current tool boundary | INTERRUPTED / not PASS |

## Findings

- The complete default `scripts/ci.sh` path is still available with no arguments.
- Long host evidence can now be collected phase-by-phase without changing the underlying test modules or release cases.
- Unknown phases fail before checks run.
- The external execution boundary can still interrupt long phases; those interruptions are recorded as diagnostic evidence, not PASS.

## Residual risk

A full one-command host CI PASS remains unclaimed in this container.  Physical M10.7 remains not-run.  The next evidence step is either physical target acceptance or complete phase-by-phase CI collection in a longer host session.
