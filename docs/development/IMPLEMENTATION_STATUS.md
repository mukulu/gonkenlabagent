# GonKenLab Agent Implementation Status

This handoff is generated from `MILESTONES.json`. Update that ledger, then run
`python scripts/milestone_status.py`; CI rejects drift and missing blueprint items.
Historical implementation detail remains in Git, `TEST_MATRIX.md` and `DECISIONS.md`.
M0/M1 audit and architecture review are complete; the table covers every core implementation item.

<!-- MILESTONES -->
Checkpoint scope: **M3.4 baseline + M4 runtime/audio contracts + M5.1 controller; continuous progression active**

| Item | Software | Target acceptance | Evidence / remaining work |
|---|---|---|---|
| M2.1 — Package and identity normalization | host-verified | not-applicable | TEST_MATRIX.md (M2.1)  |
| M2.2 — Configuration authority and migration | host-verified | not-applicable | TEST_MATRIX.md (M2.2)  |
| M2.3 — Dependency profiles and locks | host-verified | not-applicable | TEST_MATRIX.md (M2.3)  |
| M2.4 — Automated test foundation | host-verified | not-applicable | TEST_MATRIX.md (M2.4)  |
| M3.1 — Bootstrap preflight | host-verified | not-run | TEST_MATRIX.md (M3.1) Physical Pi acceptance remains open. |
| M3.2 — Step engine and install state | host-verified | not-run | TEST_MATRIX.md (M3.2) Physical Pi acceptance remains open. |
| M3.3 — Immutable application release | host-verified | not-run | TEST_MATRIX.md (M3.3) Physical Pi acceptance remains open. |
| M3.4 — Ollama lifecycle and selected model | host-verified | not-run | TEST_MATRIX.md (M3.4) Physical Pi acceptance remains open. |
| M3.5 — Whisper and Piper artifacts | blocked | not-run | requirements/profiles.toml blocked voice profile Existing voice-runtime profile and noncommercial voice remain gated; immutable speech pins/build/target smoke not accepted. |
| M3.6 — Install summary | pending | not-run |  Not implemented. |
| M4.1 — Coordinator/state/health | host-verified | not-run | tests/unit/test_runtime_audio.py; TEST_MATRIX.md continuation-runtime Physical/service adapters and process-level Pi acceptance remain open. |
| M4.2 — Audio discovery and recovery | partial | not-run | tests/unit/test_runtime_audio.py; TEST_MATRIX.md continuation-runtime Selection/recovery/frame buffer tested; real ALSA enumeration, capture backend and hotplug acceptance remain open. |
| M4.3 — Resampling/STT/TTS lifecycle | partial | not-run | tests/unit/test_runtime_audio.py; TEST_MATRIX.md continuation-runtime FIR resampling and speech subprocess cleanup tested; pinned real speech binaries, tiny/base comparison and audible Pi acceptance remain open. |
| M5.1 — Push-to-talk and recording indication | partial | not-run | tests/unit/test_runtime_audio.py; TEST_MATRIX.md continuation-runtime Debounced hold/release controller tested; physical GPIO adapter, crash-default LED-off and wiring acceptance remain open. |
| M5.2 — Offline boundary | pending | not-run |  Not implemented. |
| M6.1 — Application service | pending | not-run |  Not implemented. |
| M6.2 — Service installer/removal | pending | not-run |  Not implemented. |
| M7.1 — Corpus and lexical index | pending | not-run |  Not implemented. |
| M7.2 — Grounded prompt and response contract | pending | not-run |  Not implemented. |
| M7.3 — Privacy-preserving telemetry | pending | not-run |  Not implemented. |
| M7.4 — Read-only dashboard | pending | not-run |  Not implemented. |
| M7.5 — Research benchmarks | pending | not-run |  Not implemented. |
| M8.1 — Doctor and support bundle | pending | not-run |  Not implemented. |
| M8.2 — Update/rollback | pending | not-run |  Not implemented. |
| M8.3 — Uninstall/reinstall | pending | not-run |  Not implemented. |
| M9.1 — Clean-install and failure campaign | pending | not-run |  Not implemented. |
| M9.2 — Security/license review | pending | not-run |  Not implemented. |
| M9.3 — Documentation and onboarding | pending | not-run |  Not implemented. |
| M9.4 — Development-artifact disposition | pending | not-run |  Not implemented. |
| M9.5 — Portable Git handoff | pending | not-run |  Not implemented. |
<!-- /MILESTONES -->

## Workflow

The maintainer authorized continuous, dependency-aware implementation on 2026-09-09.
After an item passes its applicable tests, update evidence, commit coherent work and
continue immediately. A milestone is not a session boundary. Record actual blockers
and advance independent work. Never equate host fixtures with Pi acceptance.

## Release constraints

- No target Pi, USB audio, GPIO, reboot, thermal or physical power-loss evidence is available in this environment.
- M3.5 must resolve the existing blocked Piper/voice policy and pin and validate the full speech chain. No checksum or dependency lock may be invented.
- The installer remains fail-closed at speech provisioning until its real prerequisite passes.
- Private development only: no project redistribution license is granted; legacy media remain quarantined.
- X1–X4 remain disabled extensions and do not delay core development.
- The archive contains Git history; its inherited origin points to an earlier scratch checkout, not a reachable repository. Do not push to that path; use the documented maintainer remote when ready.

## Resume protocol

Inspect Git status/history and this table; read the relevant blueprint and test evidence.
Select all useful dependency-ready work, implement and verify, then continue without
asking permission to cross an item boundary. Preserve failed/unrun gates explicitly.
At checkpoint close run the full applicable suite and verify a clean extracted Git archive.
