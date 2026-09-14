# V09 Change Verification Report — Checkpoint 01

## Scope

This verification covers commit `608304e1cf088e9be7661b13effa3f6e747c65a6` on branch `v09-environment-foundation`.  The change starts the V09 room-environment implementation line from the FIX7 checkpoint and implements only host-verifiable foundation work: version bump, static schema-2 environment configuration, pure domain objects, mutable policy validation/persistence, milestone/status/test documentation and evidence capture.

Out of scope: deterministic controller behavior, SHT31 driver, libgpiod relay driver, environment daemon, AF_UNIX IPC, CLI/voice actions, installer/systemd integration, diagnostics integration and physical Raspberry Pi HIL.

## Governing instructions and sources

- `AGENTS.md` requires dependency-ready progress, proportionate checks, updated development ledgers, committed checkpoints and separation of host evidence from Raspberry Pi evidence.
- `GONKEN_NEXT_COMPREHENSIVE_IMPLEMENTATION_BLUEPRINT(2).md` governs V09 and requires the first implementation action to begin from the pinned FIX7 commit, bump to `0.2.0.dev0`, update development ledgers, add tests first for static schema-2 migration and pure environment domain/policy objects, and avoid hardware actuation at this stage.
- Source hashes and baseline identity are recorded in `docs/development/evidence/v09/wp_a_input_evidence.txt`.

## Changed-file and risk classification

| Area | Files | Risk | Verification focus |
|---|---|---|---|
| Package version | `pyproject.toml`, `src/gonken_agent/__init__.py`, version-sensitive tests/fixtures | Low | CLI version and dependent tests updated consistently |
| Static config authority | `config/defaults.toml`, `src/gonken_agent/config.py`, `tests/unit/test_m2_2_config.py`, `tests/unit/test_v09_environment_config.py` | Medium | Schema-2 defaults, schema-1 site migration, typed validation, source attribution and path redaction |
| Environment domain/policy | `src/gonken_agent/environment/*`, `tests/unit/test_v09_environment_policy.py` | Medium | Closed policy schema, generation conflicts, bounds, no unsupported speed/motion claims, atomic writes |
| Development ledgers/evidence | `docs/development/*`, `docs/development/evidence/v09/*` | Medium | Milestone/status drift, explicit interrupted checks, host-vs-Pi separation |

## Checks executed

| Check | Result | Evidence |
|---|---:|---|
| Focused 60-test baseline slice before changes | PASS, 60/60 | `docs/development/evidence/v09/wp_a_focused_60_tests_baseline.log` |
| Broad baseline `scripts/ci.sh` under watchdog | TIMEOUT / INTERRUPTED | `docs/development/evidence/v09/wp_a_ci_baseline.log` |
| Isolated CLI-run integration after baseline interruption | PASS | `docs/development/evidence/v09/wp_a_isolated_cli_run_test.log` |
| V09 config/domain/policy affected suite | PASS, 42/42 | `docs/development/evidence/v09/wp_b_config_policy_tests_rerun.log` |
| Focused 60-test regression after changes | PASS, 60/60 | `docs/development/evidence/v09/wp_a_focused_60_tests_after_v09_foundation.log` |
| Full unit suite after changes | PASS, 254/254 | `docs/development/evidence/v09/wp_b_full_unit.log` |
| Full integration suite after changes | TIMEOUT / INTERRUPTED | `docs/development/evidence/v09/wp_b_full_integration.log` |
| Isolated Ollama lifecycle recovery test | TIMEOUT / INTERRUPTED | `docs/development/evidence/v09/wp_b_isolated_ollama_lifecycle_test.log` |
| Static gates: dependency lock, milestone check, release-readiness allow-dirty, Bash syntax, compileall, TOML/JSON parse, `git diff --check` | PASS | `docs/development/evidence/v09/wp_b_static_gates.log` |
| Post-commit Git status, fsck, milestone check, package version, release-readiness JSON | PASS except intentionally dirty during log capture | `docs/development/evidence/v09/wp_b_post_commit_integrity.log` |
| Final clean repository check after amended commit | PASS | shell output: `git status --short` empty; `git fsck --full --strict`; version `0.2.0.dev0`; release-readiness dirty=false |

## Regression protection added

- Existing configuration validation tests now cover environment static fields and schema 3 rejection.
- New V09 config tests cover disabled-by-default environment schema, schema-1 site compatibility, static cross-field bounds and relay GPIO collision with existing interaction/wake/I2C pins.
- New V09 policy tests cover truthful capability flags, sensor staleness/CRC quality, mode aliases, default policy, invalid thresholds/dwell, optimistic generation conflicts, closed mapping, atomic persistence and corrupt-policy failure.

## Residual risks

1. Full integration/CI is not clean in this container because an existing Ollama lifecycle interruption/recovery test exceeded the bounded run. This is recorded as `NEEDS_MANUAL_REVIEW` and must be inspected before using full CI as a release-quality gate for V09.
2. No hardware library, daemon, IPC, CLI or voice integration exists yet; therefore no environment action can be executed by this checkpoint.
3. No physical Raspberry Pi evidence exists for SHT31, relay, PENGLIN USB wiring, ELUTENG fan, wake phrase, reboot/no-login behavior or update/rollback with environment hardware.
4. `scripts/release_readiness.py` still reports FIX7 target-acceptance readiness; it does not mean V09 environment acceptance is complete. M10.4-M10.7 remain pending in the milestone ledger.

## Readiness verdict

**Host foundation checkpoint: PASS with integration-suite caveat.**  M10.1-M10.3 are host-verified.  M10.4-M10.7 are not implemented or physically accepted.  The repository is committed and resumable at this checkpoint; the next dependency-ready work is M10.4 after reviewing/classifying the existing Ollama lifecycle timeout.
