# GonKenLab Agent Implementation Status

This handoff is generated from `MILESTONES.json`. Update that ledger, then run
`python scripts/milestone_status.py`; CI rejects drift and missing blueprint items.
Historical implementation detail remains in Git, `TEST_MATRIX.md` and `DECISIONS.md`.
M0/M1 audit and architecture review are complete; the table covers every core implementation item.

<!-- MILESTONES -->
Checkpoint scope: **Continuation 04: M6.1/M6.2 governed service lifecycle plus M8.2 explicit rollback entrypoint**

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
| M3.5 — Whisper and Piper artifacts | host-verified | not-run | SPEECH_ARTIFACT_LIFECYCLE.md; TEST_MATRIX.md (M3.5); tests/unit/test_m3_5_speech_manager.py; tests/integration/test_speech_lifecycle_process.py Real Raspberry Pi build/download/install, Piper synthesis, Whisper transcription, audio hardware and reboot acceptance remain open. |
| M3.6 — Install summary | host-verified | not-run | TEST_MATRIX.md (M3.6); scripts/install_summary.py; tests/unit/test_m3_6_install_summary.py Target invocation after real M3.5 provisioning remains unrun; service and hardware readiness remain M6/T4/T5 gates. |
| M4.1 — Coordinator/state/health | host-verified | not-run | tests/unit/test_runtime_audio.py; TEST_MATRIX.md continuation-runtime Physical/service adapters and process-level Pi acceptance remain open. |
| M4.2 — Audio discovery and recovery | partial | not-run | tests/unit/test_runtime_audio.py; TEST_MATRIX.md continuation-runtime Selection/recovery/frame buffer tested; real ALSA enumeration, capture backend and hotplug acceptance remain open. |
| M4.3 — Resampling/STT/TTS lifecycle | partial | not-run | tests/unit/test_runtime_audio.py; TEST_MATRIX.md continuation-runtime FIR resampling and speech subprocess cleanup tested; pinned real speech binaries, tiny/base comparison and audible Pi acceptance remain open. |
| M5.1 — Push-to-talk and recording indication | partial | not-run | tests/unit/test_runtime_audio.py; TEST_MATRIX.md continuation-runtime Debounced hold/release controller tested; physical GPIO adapter, crash-default LED-off and wiring acceptance remain open. |
| M5.2 — Offline boundary | partial | not-run | TEST_MATRIX.md continuation-grounding; text runtime guide Core text path allows numeric-loopback only, no DNS/proxy/redirect/tool/cloud path. Kernel-observed Pi network denial and voice runtime acceptance remain open. |
| M6.1 — Application service | host-verified | not-run | TEST_MATRIX.md continuation-04; tests/integration/test_cli_process.py; tests/unit/test_m6_service_manager.py Headless service command and systemd unit are host-tested as degraded supervisor. Raspberry Pi systemd start/stop/restart, reboot/no-login persistence, real audio/GPIO recovery and journal review remain target gates. |
| M6.2 — Service installer/removal | host-verified | not-run | TEST_MATRIX.md continuation-04; scripts/service_manager.py; tests/unit/test_m6_service_manager.py; tests/unit/test_m3_3_release_manager.py Atomic unit/tmpfiles install, exact conflict refusal and reversible removal are host-tested with fake systemctl. Real root install/remove, systemd-analyze verify and target ownership validation remain target gates. |
| M7.1 — Corpus and lexical index | partial | not-run | TEST_MATRIX.md continuation-grounding; text runtime guide Safe deterministic calibrated BM25 and 60-case synthetic regression pass. Real-lab 40/20 evaluation and support calibration remain open. |
| M7.2 — Grounded prompt and response contract | partial | not-run | TEST_MATRIX.md continuation-grounding; text runtime guide Untrusted-data prompt and citation/abstention format enforced. Real model factual support, contradiction and prompt-injection evaluation remain open. |
| M7.3 — Privacy-preserving telemetry | partial | not-run | TEST_MATRIX.md continuation-grounding; text runtime guide Content-free bounded process-serialized JSONL rotation implemented. Opt-in persistent research interaction records/retention remain gated. |
| M7.4 — Read-only dashboard | host-verified | not-run | TEST_MATRIX.md continuation-grounding; text runtime guide Integrated text dashboard, privacy/Host/Origin/read-only tests pass. Physical runtime integration remains open. |
| M7.5 — Research benchmarks | partial | not-run | TEST_MATRIX.md continuation-grounding; text runtime guide Reproducible synthetic retrieval benchmark and result schema provided. Real grounded/ungrounded LLM, STT, latency/RAM/thermal campaign remains open. |
| M8.1 — Doctor and support bundle | partial | not-run | tests/unit/test_support_export.py; TEST_MATRIX.md continuation-support Categorical doctor and private allow-listed support ZIP tested. Detailed target versions/services/audio/GPIO/resource probes remain open. |
| M8.2 — Update/rollback | partial | not-run | TEST_MATRIX.md continuation-04; scripts/rollback.sh; scripts/release_manager.py; tests/integration/test_release_lifecycle_process.py Explicit rollback to the previous post-verified immutable release is host-tested and restarts the app service. Update entrypoint, schema migrators, compatibility policy, target rollback and failure-injection service restart remain open. |
| M8.3 — Uninstall/reinstall | pending | not-run |  Not implemented. |
| M9.1 — Clean-install and failure campaign | blocked | not-run | TEST_MATRIX.md continuation-01 full regression Full clean-image failure campaign requires physical Pi and post-service target validation. Host unit/integration suites remain passing through M6.2. |
| M9.2 — Security/license review | partial | not-run | CONTINUATION_01_REPORT.md; D-050/D-051 and D-060–D-064 New-code review, inherited identity invariant, privacy tests, privilege-pattern service checks and credential-pattern scan pass. Target hardening, artifact licenses and redistribution approval remain open. |
| M9.3 — Documentation and onboarding | partial | not-run | TEST_MATRIX.md continuation-grounding; text runtime guide Text diagnostic onboarding commands and service lifecycle source contracts are tested. Target installation/service/hardware operational guide remains open. |
| M9.4 — Development-artifact disposition | host-verified | not-applicable | D-065 Development evidence retained with concise current status; no history removed. Review again before public release. |
| M9.5 — Portable Git handoff | host-verified | not-applicable | CONTINUATION_01_REPORT.md; checkpoint/continuation-01 Private checkpoint transport verified: ZIP integrity, extracted branch/tag/HEAD, executable modes, clean Git and strict object checks. Core release gates remain open. |
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
