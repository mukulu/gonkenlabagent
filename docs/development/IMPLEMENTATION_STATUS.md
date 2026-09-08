# GonKenLab Agent Implementation Status

This file is the authoritative short handoff for a later development session. Verify it against Git before acting.

## Current State

- **Working branch:** `dev/bootstrap-rearchitecture`
- **Inspected application baseline:** `6682360786135136abeb0bd2a17a9d45c6f291e7`
- **Current control milestone:** M1 — Master blueprint and adversarial review
- **Blueprint revision:** 1.0-draft
- **Current draft checkpoint:** `checkpoint/blueprint-draft` (resolve its exact commit with `git rev-list -n 1 checkpoint/blueprint-draft`)
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

## In Progress

- [ ] M1B — adversarial architecture review of blueprint revision 1.0-draft.

## Not Started

- [ ] M2 — Packaging/configuration/state foundation.
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
- C-04: no custom Gonken wake-word training/artifact/evaluation chain.
- C-05: no local grounding/provenance/telemetry implementation.
- C-06: no evidence for rerun, interruption, reboot, or unattended-readiness claims.

### High

- H-01 through H-18 are open; see the audit.

## Tests Passing

- Bash syntax for `bootstrap.sh` and `setup.sh`.
- Python byte-compilation for tracked Python source.
- JSON parsing for `config/config.json`.
- `git diff --check`.
- `git fsck --full --strict`.
- PNG structural/CRC validation for all face assets.
- WAV header/parameter validation for all filler assets.
- Targeted history scan found no credible committed secret.

## Tests Failing or Blocked

- Doctor under the audit host: expected FAIL because the repository has not been provisioned there.
- Router/wake/smoke scripts under the audit host: dependency/runtime unavailable.
- All Raspberry Pi ARM64 runtime, audio, GPIO, service, reboot, and failure-injection tests: BLOCKED pending implementation and target hardware.
- Full installer execution: NOT RUN during documentation-only forensic audit.

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

See `DECISIONS.md` for rationale and status.

## Next Recommended Action

Perform M1B against `MASTER_BLUEPRINT.md` revision 1.0-draft. Attack its platform, filesystem, rollback, Ollama, wake-word, privacy-indicator, power-control, systemd, dashboard, offline-verification, APT/interruption, corpus, and scope assumptions. Incorporate accepted findings as revision 1.1-reviewed, commit `docs: harden blueprint after architecture review`, then tag `checkpoint/blueprint`. Do not implement M2 code during that review.

## Session Start Protocol

Every later session should:

1. run `git status --short --branch` and inspect recent history;
2. read this file, `MASTER_BLUEPRINT.md` when present, `TEST_MATRIX.md`, and `DECISIONS.md`;
3. verify claimed status against repository evidence;
4. select only the next acceptance-bounded item;
5. implement and test it without advancing past failed acceptance criteria;
6. update control documents in the same commit;
7. use a meaningful commit message and stop at a clean boundary.
