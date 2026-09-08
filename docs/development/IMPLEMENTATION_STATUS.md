# GonKenLab Agent Implementation Status

This file is the authoritative short handoff for a later development session. Verify it against Git before acting.

## Current State

- **Working branch:** `dev/bootstrap-rearchitecture`
- **Inspected application baseline:** `6682360786135136abeb0bd2a17a9d45c6f291e7`
- **Current control milestone:** M3.2 — Step engine and install state
- **Blueprint revision:** 1.6-implementation
- **Accepted blueprint checkpoint:** `checkpoint/blueprint` (resolve its exact commit with `git rev-list -n 1 checkpoint/blueprint`)
- **M2.1 implementation checkpoint:** `checkpoint/m2.1-license-gate` (created after the tested commit; resolve it with `git rev-list -n 1 checkpoint/m2.1-license-gate`)
- **M2.1 completed checkpoint:** `checkpoint/m2.1` (resolve its exact commit with `git rev-list -n 1 checkpoint/m2.1`)
- **M2.2 completed checkpoint:** `checkpoint/m2.2` (resolve its exact commit with `git rev-list -n 1 checkpoint/m2.2`)
- **M2.3 completed checkpoint:** `checkpoint/m2.3` (resolve its exact commit with `git rev-list -n 1 checkpoint/m2.3`)
- **M2.4 completed checkpoint:** `checkpoint/m2.4` (created after the tested commit; resolve it with `git rev-list -n 1 checkpoint/m2.4`)
- **M2.4 clean-checkout test commit:** `d79ac48515db7d613c0ba5a020981a3953fa0b87`
- **M3.1 completed checkpoint:** `checkpoint/m3.1` (created after the tested commit; resolve it with `git rev-list -n 1 checkpoint/m3.1`)
- **M3.1 clean-checkout test commit:** `29b5143febfea299454f56f05a75be06bffd790c`
- **Last verification date:** 2026-09-08 UTC
- **Target:** Raspberry Pi 5 4GB, Raspberry Pi OS Lite 64-bit
- **Audit host:** Ubuntu 24.04 x86_64, Python 3.12 (not target hardware)

## Completed

- [x] Cloned and verified current `origin/main` baseline.
- [x] Created `dev/bootstrap-rearchitecture` from `6682360`.
- [x] Inspected all 50 tracked files and all nine reachable commits.
- [x] Inspected the supplied requirements note and feasibility/build blueprint.
- [x] Recorded a comprehensive forensic audit with stable finding IDs.
- [x] Established a persistent test matrix and decision log.
- [x] Confirmed the official Ollama tag `qwen3.5:2b-q4_K_M` exists.
- [x] Made no runtime/application-code changes during M0.
- [x] Completed M0 documentation commit `f71c371` and tag `checkpoint/audit`.
- [x] Created implementation-grade `MASTER_BLUEPRINT.md` revision 1.0-draft.
- [x] Mapped every Critical and High audit finding to implementation work and acceptance gates.
- [x] Resolved the audit’s deferred architecture questions at accepted, provisional, or explicitly deferred status.
- [x] Preserved M1A as documentation-only; no runtime code was changed.
- [x] Committed M1A as `docs: add implementation master blueprint` and tagged it `checkpoint/blueprint-draft`.
- [x] Completed all 18 mandatory M1B attack questions and recorded dispositions in `BLUEPRINT_ADVERSARIAL_REVIEW.md`.
- [x] Resolved all Critical M1B findings through scope, privilege, transaction, and interruption-recovery changes.
- [x] Revised the implementation contract to `MASTER_BLUEPRINT.md` revision 1.1-reviewed.
- [x] Added planned verification IDs for every Critical and High audit finding.
- [x] Committed M1B as `docs: harden blueprint after architecture review` and tagged it `checkpoint/blueprint`.
- [x] Preserved M1B as documentation-only; no runtime code was changed.
- [x] Created the dependency-light `src/gonken_agent` package and `gonken-agent` CLI.
- [x] Moved the inspected orchestrator behind a narrow, explicit source-compatibility adapter.
- [x] Centralized package identity and removed inherited personal/product identity from active prompts, speech, UI, tests, and current user documentation.
- [x] Separated the extension namespace and verified core import without optional dependencies.
- [x] Created machine-readable source/assets/dependencies provenance with hashes for all 14 tracked media files.
- [x] Excluded legacy runtime modules and all unknown media from the wheel policy.
- [x] Added and passed 16 standard-library host tests plus offline wheel-content validation.
- [x] Closed M2.1 conservatively without inventing a project license: no license is granted and redistribution is prohibited.
- [x] Quarantined all unknown PNG/WAV media as internal compatibility evidence excluded from packages, releases, and public exports.
- [x] Restricted GPL/noncommercial Piper voice and wake artifacts to internal legacy evaluation pending a future release-compatible decision.
- [x] Completed M2.1 and authorized M2.2 as the next bounded work package.
- [x] Added the typed, dependency-free configuration authority and sole source-controlled defaults TOML.
- [x] Enforced defaults → site TOML → explicit environment → one-shot CLI precedence for every schema field.
- [x] Added strict schema/value validation, loopback-only endpoints/binds, safe normalized paths, GPIO/audio constraints, and rejection of unsupported extensions.
- [x] Added redacted human/JSON effective-config output with non-sensitive per-field source attribution.
- [x] Added atomic, repeatable, non-destructive legacy JSON/`.env` migration with timestamp/hash backups and restrictive permissions.
- [x] Routed installer, doctor, compatibility runtime, and legacy component construction through the same model, endpoint, audio, and path authority.
- [x] Passed 42 dependency-free host tests and an isolated offline wheel install that located its shipped defaults.
- [x] Completed M2.2 and authorized M2.3 as the next bounded work package.
- [x] Added a machine-readable dependency authority and four deterministic, hash-enforcing, wheel-only locks.
- [x] Kept the maintained core/dev profiles exactly dependency-free and separated pygame into optional UI locks for host and target.
- [x] Removed root `requirements.txt`, quarantined its remaining ranges as unaccepted legacy input, and removed mandatory pygame from legacy setup/doctor behavior.
- [x] Kept openWakeWord and Piper/TTS out of accepted locks with explicit blocking evidence and next gates.
- [x] Verified the selected pygame 2.6.1 CPython 3.13/AArch64 wheel filename and PyPI SHA-256 without claiming a download or Pi install.
- [x] Passed 51 dependency-free host tests, deterministic lock verification, license reporting, an isolated clean wheel install, `pip check`, and core import with pygame/openWakeWord absent.
- [x] Completed M2.3 and authorized M2.4 as the next bounded work package.
- [x] Reclassified all three inherited interactive probes into explicit live-integration or physical-hardware programs outside automated discovery.
- [x] Added `scripts/ci.sh` as the single dependency-free T0/T1 entry point; it installs nothing and initiates no network, Ollama, model, audio, GPIO, or privilege operation.
- [x] Added deterministic fake-client and JSON fixtures for legacy router behavior and process-boundary integration coverage for the maintained CLI.
- [x] Corrected the joke-route expectation to `get_joke`, made phrase matching reject substrings, and removed the unsupported spoken wake-phrase claim from the manual probe.
- [x] Added opt-in guards that exit 2 before optional imports when manual/live programs are invoked unintentionally.
- [x] Passed 63 unit tests and three deterministic integration tests from the repository entry point.
- [x] Recorded D-055: retain pytest-discoverable structure while the exact empty dev profile uses `unittest`; do not claim an unavailable pytest execution.
- [x] Completed M2.4 and authorized M3.1 as the next bounded work package.
- [x] Replaced the legacy bootstrap fall-through with a fail-closed M3.1 preflight that never invokes `setup.sh` or mutates packages, services, configuration, checkout content, or installed releases.
- [x] Enforced the exact Raspberry Pi 5 / official Raspberry Pi OS Trixie / AArch64 / 64-bit / Python 3.13 / systemd production contract and a separate explicit Linux Python 3.12/3.13 development-host contract.
- [x] Added disk, RAM, plausible TLS-time, required-command, source-protocol, unique advertised-ref, and exact resolved-commit validation.
- [x] Added direct-root, sudo-root invoking-user, non-root one-time sudo validation, sudo-unavailable, and sudo-failure boundaries without assuming `sudo` exists for direct root.
- [x] Reject tracked, staged, and untracked changes, unexpected origins, symlink checkout paths, and nonempty non-Git paths before remote source access.
- [x] Create staging only after success, with mode 700 and a mode-600 non-sourceable record of source, image/platform fingerprints, interpreter/init versions, resources, time, and invoking identity.
- [x] Added the M3.1 onboarding draft and D-056; default bootstrap execution stops explicitly at `M3_2_UNAVAILABLE` until the resumable installer exists.
- [x] Passed 81 dependency-free unit tests and six deterministic process-integration tests (87 total), including local-only Git ref resolution and failure-ordering checks.
- [x] Completed M3.1 and authorized M3.2 as the next bounded work package.

## In Progress

- No implementation package is currently in progress.
- M3.2 is the next and only authorized implementation package.

## Not Started

- [x] M2.2 — Configuration authority and migration.
- [x] M2.3 — Dependency profiles and locks.
- [x] M2.4 — Automated test foundation.
- [x] M3.1 — Bootstrap preflight.
- [ ] M3.2 — Step engine and install state.
- [ ] M3.3–M3.6 — Immutable release and dependency/model provisioning.
- [ ] M4 — Runtime reliability.
- [ ] M5 — Interaction and privacy modes.
- [ ] M6 — Headless service and privileged operations.
- [ ] M7 — Grounding and observability, subject to blueprint scope confirmation.
- [ ] M8 — Diagnostics, upgrades, recovery, and uninstall.
- [ ] M9 — Verification and release candidate.

## Known Issues

The full issue descriptions and evidence are in `REPOSITORY_AUDIT.md`.

### Critical

- C-01: no GonKenLab Agent systemd/boot service.
- C-02: runtime is not offline by default in routing behavior.
- C-03: RESOLVED for active package/user surfaces by M2.1/V-C03. Historical documents and technical legacy detector identifiers remain explicitly isolated.
- C-04: no custom Gonken wake-word training/artifact/evaluation chain; reassigned to governed extension X1 rather than the core release.
- C-05: no local grounding/provenance/telemetry implementation.
- C-06: no evidence for rerun, interruption, reboot, or unattended-readiness claims.

### High

- H-01/H-02 are resolved on active paths by M2.2. H-03/H-04 are resolved at the M3.1 preflight boundary and must be revalidated when M3.2 adds mutations. H-08 is resolved for the maintained package by M2.3. H-06 is resolved for the package foundation but reopens for every future runtime dependency addition; H-07 remains open until a real Python 3.13/AArch64 download and Pi venv pass. H-05 and H-09 through H-18 remain open.

### Architecture gates introduced by M1B

- AR-19: M2.1 development disposition is resolved through explicit no-redistribution and quarantine policies. A future public release remains blocked until project-source authority/license and media/artifact rights are approved.
- Qwen 3.5 2B Q4_K_M has not yet passed Raspberry Pi latency/RAM/thermal/quality acceptance.
- Direct LAN dashboard, wake word, voice power, and Bluetooth remain unimplemented extensions X1–X4.

## Tests Passing

- Bash syntax for `bootstrap.sh` and `setup.sh`.
- Python byte-compilation for tracked Python source.
- JSON parsing for `config/config.json`.
- `git diff --check`.
- `git fsck --full --strict`.
- PNG structural/CRC validation for all face assets.
- WAV header/parameter validation for all filler assets.
- Targeted history scan found no credible committed secret.
- M2.1 standard-library host suite: 16 of 16 tests pass with no network, model, audio, GPIO, UI, or extension dependency.
- Package CLI version/status checks and deliberate unimplemented-runtime exit code pass.
- Offline local-backend wheel build passes; wheel contains only `gonken_agent` package files and metadata.
- Active-surface inherited-identity scan passes; historical PRD/audit/decision evidence is intentionally excluded.
- Provenance hash/coverage checks pass for every tracked PNG/WAV and every legacy Python requirement.
- M2.2 standard-library host suite: 42 of 42 tests pass, including every-field source/precedence coverage, invalid values, privacy redaction, and migration failure paths.
- Installer, doctor, compatibility runtime, and Ollama CLI/client configuration-convergence checks pass without invoking hardware or network.
- Isolated offline wheel build/install passes; the installed CLI locates shipped defaults outside the checkout and reports the Qwen 3.5 authority.
- M2.3 standard-library host suite: 51 of 51 tests pass, including profile boundaries, deterministic lock rendering, exact hashes, blocked-profile behavior, and machine-readable license reporting.
- M2.4 repository entry point: 63 of 63 unit tests and 3 of 3 deterministic process-integration tests pass (66 total), with automated/manual boundaries enforced by regression tests.
- A local no-hardlink clone of commit `d79ac48515db7d613c0ba5a020981a3953fa0b87` passed the same entry point in a fresh standard-library-only virtual environment and remained clean.
- The live Ollama router, microphone/speaker pipeline, and wake detector programs all fail closed with exit 2 before importing optional dependencies unless their explicit opt-in variable is set.
- Clean x86/Python 3.12 dev-lock and wheel install passes without `--ignore-requires-python`; `pip check` reports no broken requirements.
- Isolated installed-core import passes with pygame and openWakeWord absent; CLI status remains honestly not runtime-ready.
- PyPI metadata verification passes for the exact pygame 2.6.1 CPython 3.13/AArch64 wheel filename and recorded SHA-256.
- M3.1 suite: 81 of 81 unit tests and 6 of 6 deterministic integration tests pass, including V-H03/V-H04 privilege cases, exact platform/resource rejections, checkout preservation, local source resolution, private record permissions, and prevention of legacy installer fall-through.
- A local no-hardlink clone of M3.1 implementation commit `29b5143febfea299454f56f05a75be06bffd790c` passed the same entry point in a fresh standard-library-only virtual environment and remained clean.

## Tests Failing or Blocked

- Doctor under the audit host: expected FAIL because the repository has not been provisioned there.
- Live router and physical audio/wake manual programs: NOT RUN because their services, dependencies, devices, and recorded-environment evidence are unavailable on the audit host.
- All Raspberry Pi ARM64 runtime, audio, GPIO, service, reboot, and failure-injection tests: BLOCKED pending implementation and target hardware.
- Networked AArch64 `pip download`, optional-UI installation/import, and the physical Pi Python 3.13 venv install: BLOCKED because this environment cannot reach the package index and has no Pi. Metadata verification is not promoted to install evidence.
- The retained full prototype installer has not been rerun and is not an accepted installer; M3 owns its replacement.
- Physical Raspberry Pi M3.1 preflight and a real target-to-GitHub HTTPS/ref probe remain BLOCKED; fixture and development-host success are not promoted to T2/T3 evidence.
- `bootstrap.sh` is intentionally preflight-only until M3.2; this checkpoint is not install-ready.
- Package publication, a public repository export, and a public portable Git ZIP: BLOCKED by the deliberate no-redistribution policy.
- Unknown-media rights and a release-compatible Piper/voice/wake licensing plan remain release/runtime blockers, not grounds for inventing M2.3 locks.

Exact commands and interpretations are in `TEST_MATRIX.md`.

## Current Decisions

- The repository, not chat history, is the continuity authority.
- The development branch is `dev/bootstrap-rearchitecture`.
- M0 changes documentation only.
- Automatic login is not a dependency for a headless system service.
- Offline/local operation is the default privacy boundary for the future design.
- Installer/runtime model settings must converge on one authority.
- A custom wake phrase cannot be advertised unless its matching model is loaded and validated.
- Voice shutdown/reboot cannot be implemented as arbitrary LLM-generated shell execution.
- GonKenLab Agent is the single product identity; Jansky/Jarvis/Mayukh behavior will be removed from active code and documentation.
- Offline governs normal runtime; internet is permitted only for explicit installation/update operations.
- Push-to-talk is the mandatory reliable path; “Hey Gonken” remains disabled until its evaluation gate passes.
- Local grounding, provenance, content-free telemetry, and a read-only dashboard are release scope.
- USB audio is the supported release path; Bluetooth is experimental until separately accepted.
- Installed runtime will use a dedicated non-login service account and will not own application code.
- The core release is push-to-talk, USB-audio, loopback-dashboard, and has no host-power privilege.
- Wake word, voice power, direct LAN dashboard, and Bluetooth are governed extensions and do not block core release.
- Installed releases use `/usr/local/lib/gonken-agent`; configuration uses `/etc/gonken-agent`; state uses `/var/lib/gonken-agent`; the corpus uses `/srv/gonken-agent/corpus`.
- The service uses `Type=exec` without a core watchdog; health/readiness remains application-level.
- APT/Ollama provisioning is convergent and repairable, not transactionally rolled back; atomic rollback applies to project-owned activation.
- Power-loss recovery uses a root-owned activation journal and pre-start reconciliation.
- Persistent telemetry is content-free; optional dashboard interaction content is transient memory only.
- The active Python package imports only the standard library; optional features live behind an extension namespace and separate future profiles.
- The inspected runtime is retained as `legacy_orchestrator.py`; `orchestrator.py` is now a narrow compatibility launcher.
- Package metadata makes no license claim; the maintained headless core remains dependency-free until runtime dependencies are selected and verified.
- Exact locks are generated from `requirements/profiles.toml`; all accepted locks require hashes and wheels, while blocked profiles deliberately have no lock.
- Python 3.12 is a supported host-development interpreter; the production target remains Python 3.13 on Trixie/AArch64.
- M2.1 used `unittest` as a transitional dependency-free runner; M2.4 resolved the runner choice under D-055.
- M2.4 retains `unittest` as the executable dependency-free runner under D-055; pytest-compatible naming is preserved, but pytest has not been installed or claimed.
- No project license is granted; continued work is private development and redistribution remains prohibited until a later explicit decision.
- Unknown PNG/WAV media and noncommercial voice/wake artifacts are quarantined from packages, releases, and public exports.
- `config/defaults.toml` is the only active default-value authority; legacy JSON and `.env` are never loaded by normal runtime.
- Site configuration is read-only to normal runtime; migration refuses to replace a differing destination.
- Effective-config output redacts filesystem paths and reports only source category/environment/CLI identifiers.
- Bootstrap preflight is the sole accepted admission boundary: target facts and source identity fail closed, its record is never shell-sourced, and the retained prototype installer cannot be reached from it.
- Initial 8 GiB free-space and approximately 3.5 GiB target-memory thresholds are conservative admission gates pending physical-Pi recalibration, not performance claims.

See `DECISIONS.md` for rationale and status.

## Next Recommended Action

Implement M3.2 only. Add `scripts/install.sh` and the stable step/state engine.
Each step must declare an ID/version, precondition, planned mutations,
idempotent action, actual postcondition, rerun behavior, and rollback
implication. Atomically write logs/advisory state while treating probes as the
authority. Revalidate—never source—the M3.1 record. Use temporary roots and
stubs to interrupt every fake-step boundary, prove convergence and repair of
false-complete state, and preserve actionable failures. Do not install real
releases, dependencies, models, services, or hardware; stop before M3.3.

## Session Start Protocol

Every later session should:

1. run `git status --short --branch` and inspect recent history;
2. read this file, `MASTER_BLUEPRINT.md` when present, `TEST_MATRIX.md`, and `DECISIONS.md`;
3. verify claimed status against repository evidence;
4. select only the next acceptance-bounded item;
5. implement and test it without advancing past failed acceptance criteria;
6. update control documents in the same commit;
7. use a meaningful commit message and stop at a clean boundary.
