# GonKenLab Agent Implementation Status

This file is the authoritative short handoff for a later development session. Verify it against Git before acting.

## Current State

- **Working branch:** `dev/bootstrap-rearchitecture`
- **Inspected application baseline:** `6682360786135136abeb0bd2a17a9d45c6f291e7`
- **Current control milestone:** M2.1 — Package and identity normalization; licensing gate blocked
- **Blueprint revision:** 1.1-reviewed
- **Accepted blueprint checkpoint:** `checkpoint/blueprint` (resolve its exact commit with `git rev-list -n 1 checkpoint/blueprint`)
- **M2.1 implementation checkpoint:** `checkpoint/m2.1-license-gate` (created after the tested commit; resolve it with `git rev-list -n 1 checkpoint/m2.1-license-gate`)
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
- [x] Added and passed 15 standard-library host tests plus offline wheel-content validation.

## In Progress

- M2.1 implementation is complete except its mandatory licensing/provenance governance gate.
- Maintainer project-license/authority approval was requested but no selection was received.
- Unknown PNG/WAV rights and Piper/noncommercial-artifact disposition remain unresolved.
- M2.2 is not authorized while these M2.1 acceptance items are open.

## Not Started

- [ ] M2.2 — Configuration authority and migration.
- [ ] M2.3 — Dependency profiles and locks.
- [ ] M2.4 — Automated test foundation.
- [ ] M3 — Idempotent provisioning.
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
- C-03: GonKenLab/Jansky/Jarvis identity and activation mismatch.
- C-04: no custom Gonken wake-word training/artifact/evaluation chain; reassigned to governed extension X1 rather than the core release.
- C-05: no local grounding/provenance/telemetry implementation.
- C-06: no evidence for rerun, interruption, reboot, or unattended-readiness claims.

### High

- H-01 through H-18 are open; see the audit.

### Architecture gates introduced by M1B

- AR-19: inventory is complete, but project-source authority/license and media/artifact disposition remain pending maintainer approval; redistribution is explicitly blocked.
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
- M2.1 standard-library host suite: 15 of 15 tests pass with no network, model, audio, GPIO, UI, or extension dependency.
- Package CLI version/status checks and deliberate unimplemented-runtime exit code pass.
- Offline local-backend wheel build passes; wheel contains only `gonken_agent` package files and metadata.
- Active-surface inherited-identity scan passes; historical PRD/audit/decision evidence is intentionally excluded.
- Provenance hash/coverage checks pass for every tracked PNG/WAV and every legacy Python requirement.

## Tests Failing or Blocked

- Doctor under the audit host: expected FAIL because the repository has not been provisioned there.
- Router/wake/smoke scripts under the audit host: dependency/runtime unavailable.
- All Raspberry Pi ARM64 runtime, audio, GPIO, service, reboot, and failure-injection tests: BLOCKED pending implementation and target hardware.
- Full installer execution: NOT RUN during documentation-only forensic audit.
- M2.1 licensing acceptance: BLOCKED pending maintainer source-license/authority decision and unknown-media disposition.
- Package publication and a public portable Git ZIP: BLOCKED; neither is an approved redistributable release.

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
- Package metadata makes no license claim and declares no runtime dependencies until M2.3 verifies profiles/locks.
- M2.1 host tests use `unittest` so this package-boundary check itself adds no dependency; D-029’s planned pytest architecture remains assigned to M2.4.

See `DECISIONS.md` for rationale and status.

## Next Recommended Action

Close the M2.1 licensing gate. The maintainer must confirm authority for the
project source/documentation and choose a license or explicitly keep
redistribution blocked. Then prove rights for or remove/replace all 14 PNG/WAV
assets, and record the Piper plus noncommercial voice/wake-artifact disposition.
Update `packaging/provenance.toml`, `LICENSE_PROVENANCE.md`, package metadata,
control documents, and validation. Do not begin M2.2 until these decisions pass.

## Session Start Protocol

Every later session should:

1. run `git status --short --branch` and inspect recent history;
2. read this file, `MASTER_BLUEPRINT.md` when present, `TEST_MATRIX.md`, and `DECISIONS.md`;
3. verify claimed status against repository evidence;
4. select only the next acceptance-bounded item;
5. implement and test it without advancing past failed acceptance criteria;
6. update control documents in the same commit;
7. use a meaningful commit message and stop at a clean boundary.
