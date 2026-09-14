# V09 Checkpoint 01 — Environment foundation

**Date:** 2026-09-15  
**Branch:** `v09-environment-foundation`  
**Baseline commit:** `3b25b81c5bc7d4e24268726ad7f7b71296215a03`  
**Development version:** `0.2.0.dev0`  
**Governing blueprint:** `GONKEN-V09-BP-GOLD-2026-09-15` from `GONKEN_NEXT_COMPREHENSIVE_IMPLEMENTATION_BLUEPRINT(2).md`

## Completed

1. Established V09 branch identity and recorded hashes for the supplied blueprint, V3 prompt package and FIX7 checkpoint ZIP.
2. Bumped the Python package development line from `0.1.0.dev1` to `0.2.0.dev0` in package metadata, public version surface and version-sensitive tests.
3. Migrated static configuration authority to schema 2 by adding disabled-by-default `extensions.environment` fields for the SHT31 sensor, relay, socket path, mutable policy path and hard policy bounds.
4. Added schema-1 site-config compatibility: legacy site files that declare `schema_version = 1` are treated as migration inputs and do not downgrade the effective schema.
5. Added pure environment domain objects for modes, fan capability, sensor quality, transition reasons and static policy bounds.
6. Added mutable environment policy objects and policy-store support with schema-1 JSON, closed mappings, validation against static bounds, optimistic generation conflict detection and same-directory atomic persistence.
7. Updated `MASTER_BLUEPRINT.md`, `MILESTONES.json`, `IMPLEMENTATION_STATUS.md`, `TEST_MATRIX.md` and `DECISIONS.md` with V09/M10 state.

## Verified evidence

| Evidence | Result | Boundary |
|---|---:|---|
| `docs/development/evidence/v09/wp_a_input_evidence.txt` | recorded | Repository/blueprint/checkpoint identity only |
| `docs/development/evidence/v09/wp_a_focused_60_tests_baseline.log` | PASS, 60/60 | FIX7-focused host unit slice before V09 code |
| `docs/development/evidence/v09/wp_a_ci_baseline.log` | TIMEOUT / INTERRUPTED | Broad CI attempt preserved; not PASS and not product FAIL |
| `docs/development/evidence/v09/wp_a_isolated_cli_run_test.log` | PASS | Isolated apparent slow stage after broad CI interruption |
| `docs/development/evidence/v09/wp_b_config_policy_tests_rerun.log` | PASS, 42/42 | V09 config/domain/policy tests plus affected config regression |
| `docs/development/evidence/v09/wp_a_focused_60_tests_after_v09_foundation.log` | PASS, 60/60 | Affected focused regression after V09 foundation changes |
| `docs/development/evidence/v09/wp_b_full_unit.log` | PASS, 254/254 | Full current unit suite after V09 foundation changes |
| `docs/development/evidence/v09/wp_b_full_integration.log` | TIMEOUT / INTERRUPTED | Full integration attempt reached Ollama lifecycle test before timeout; not PASS and not product FAIL |
| `docs/development/evidence/v09/wp_b_isolated_ollama_lifecycle_test.log` | TIMEOUT / INTERRUPTED | Isolated Ollama lifecycle recovery test also exceeded bounded run in this environment |
| `docs/development/evidence/v09/wp_b_static_gates.log` | PASS | Dependency lock, milestone drift, release-readiness allow-dirty, Bash syntax, compileall, TOML/JSON parse and `git diff --check` gates passed |

## Remaining

- M10.4 deterministic controller core: not implemented.
- M10.5 local environment service and AF_UNIX IPC: not implemented.
- M10.6 CLI, voice, installer, diagnostics and documentation integration: not implemented.
- M10.7 real Raspberry Pi HIL/release acceptance: not run and unavailable in this environment.
- Full `scripts/ci.sh` needs a fresh bounded rerun after this checkpoint. Broad integration checks remain interrupted in this container, with the latest timeout isolated to the existing Ollama lifecycle interruption/recovery test rather than V09 environment code.

## Blocked items / risks

- Real SHT31 detection, CRC read quality, relay polarity, Pi 5 gpiochip mapping, USB VBUS switching, ELUTENG fan power cycles and `Gonken` wake-phrase thresholds all require physical target evidence.
- The environment configuration is present but disabled by default. No daemon, socket, CLI, voice action or installer activation exists yet.
- Policy JSON persistence is host-tested, but target ownership (`gonken-env:gonken-envctl`) and `/var/lib/gonken-environment` permissions are not yet implemented.

## Exact next action

Before implementing M10.4, inspect the existing Ollama lifecycle interruption/recovery integration test timeout and either bound it more narrowly or classify it as a known non-V09 integration risk. Then implement M10.4 with tests first: create a pure deterministic controller state-machine suite for MANUAL, SEMI_AUTOMATIC, AUTOMATIC and DISABLED behavior using fake sensor/fan/clock objects, then implement the controller logic without importing hardware libraries.

## Continuation instruction

Continue from this recorded checkpoint and execute the next dependency-ready batch.
