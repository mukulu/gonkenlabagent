# V09 Checkpoint 35 Report — Reliability-First Control Plane And Canonical GPIO Alias Identity

## Purpose

Checkpoint 35 applies the post-checkpoint-34 reliability-first prompt without producing a Raspberry Pi candidate. It replaces the next-candidate boundary with a host/target-shadow release-candidate gate and starts the canonical GPIO identity repair required by the latest target evidence.

## Implemented

- Added `V09_POST_CKPT34_RELIABILITY_FIRST_BLUEPRINT.md` with the failure chronology, capability criticality matrix, installer state model, target manifest schema, dirty-state matrix, host/target-shadow gate, false-green review and WP-A through WP-M continuation plan.
- Updated `MASTER_BLUEPRINT.md`, `DECISIONS.md`, `TEST_MATRIX.md`, `MILESTONES.json` and generated `IMPLEMENTATION_STATUS.md` for M10.30.
- Extended the shared GPIO resolver to compute canonical character-device identity using device major/minor and `/sys/dev/char` realpath when available.
- Deduplicated gpiochip device-node aliases before GPIO line ambiguity decisions.
- Added `canonical_chip_id` and `alias_paths` to GPIO preflight JSON.
- Added regression coverage for duplicate `/dev/gpiochip*` aliases of the same RP1 device while preserving fail-closed behavior for genuinely distinct complete header-like controllers.

## Verification

| Check | Result | Evidence |
|---|---:|---|
| Focused GPIO/hardware adapter suite | PASS — 32 tests | `PYTHONPATH=src python3 -m unittest tests.unit.test_v09_gpio_identity_preflight tests.unit.test_m5_1_ptt_runtime tests.unit.test_v09_environment_hardware_adapters -v` |
| Focused GPIO preflight suite | PASS — 3 tests | `PYTHONPATH=src python3 -m unittest tests.unit.test_v09_gpio_identity_preflight -v` |
| Installer/docs/release-readiness cascade | PASS — 19 tests | `PYTHONPATH=src python3 -m unittest tests.unit.test_v09_install_dependency_graph tests.unit.test_release_readiness tests.unit.test_v09_documentation_hardening -v` |
| Compile/static syntax | PASS | `python3 -m compileall -q src scripts tests/unit/test_v09_gpio_identity_preflight.py` |
| Milestone/status synchronization | PASS | `python3 scripts/milestone_status.py --check` |
| Whitespace | PASS | `git diff --check` |
| T0 CI phase | PASS | `./scripts/ci.sh --phase t0` |

## Broader Check Boundary

A full unit discovery run executed 488 tests and reported 7 errors, all from tests that attempted to create AF_UNIX sockets. A minimal probe also failed with `PermissionError: [Errno 1] Operation not permitted` when calling `socket.socket(AF_UNIX, SOCK_STREAM).bind(...)`. This indicates the current Work runtime prohibits Unix-domain socket creation. The result is recorded as a blocked broader environment check, not as a code regression and not as a PASS.

## Target Boundary

No physical Raspberry Pi acceptance is claimed. No `RELEASE_CANDIDATE` or `STABLE_FINAL_RELEASE` status is claimed. M10.24 remains open until the exact future candidate completes the real Raspberry Pi install, repeated rerun, reboot/no-login, SHT31, relay/fan, wake/voice, fault, update/rollback/reinstall and support/privacy gates.

## Next Action

Continue from checkpoint 35 into the next dependency-ready reliability batch. The next strong candidate is the target-probe/target-shadow tranche: implement a sanitized non-actuating target manifest command, add a fixture for the checkpoint-34 duplicate RP1 alias topology, and require target-shadow replay before any Pi candidate package.
