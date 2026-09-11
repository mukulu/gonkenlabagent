# GonKenLab Agent Implementation Status

This handoff is generated from `MILESTONES.json`. Update that ledger, then run
`python scripts/milestone_status.py`; CI rejects drift and missing blueprint items.
Historical implementation detail remains in Git, `TEST_MATRIX.md` and `DECISIONS.md`.
M0/M1 audit and architecture review are complete; the table covers every core implementation item.

<!-- MILESTONES -->
Checkpoint scope: **Continuation 08: private release-candidate readiness and Raspberry Pi acceptance runbook**

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
| M8.1 — Doctor and support bundle | host-verified | not-run | TEST_MATRIX.md continuation-07; src/gonken_agent/diagnostics.py; src/gonken_agent/support.py; scripts/collect-support.sh; tests/unit/test_diagnostics_snapshot.py; tests/unit/test_support_export.py; tests/integration/test_cli_process.py Content-free startup snapshot capture, bounded debug retention, production latest-only mode, service startup recording and support ZIP inclusion are host-tested. Real target snapshot contents must be uploaded after Raspberry Pi installation to confirm USB audio, GPIO, systemd, thermal and resource observations. |
| M8.2 — Update/rollback | host-verified | not-run | TEST_MATRIX.md continuation-06; scripts/update.sh; scripts/update_manager.py; scripts/rollback.sh; scripts/release_manager.py; tests/unit/test_m8_update_manager.py; tests/integration/test_release_lifecycle_process.py Explicit update and rollback are host-tested through immutable release activation, Git ref resolution, no-op update detection, restart orchestration and previous-release rollback. Real target update/rollback execution, future schema migrators and service restart failure handling remain target/future-version gates. |
| M8.3 — Uninstall/reinstall | host-verified | not-run | TEST_MATRIX.md continuation-05; scripts/uninstall.sh; scripts/uninstall_manager.py; tests/unit/test_m8_uninstall_manager.py; tests/integration/test_uninstall_lifecycle_process.py Keep-data uninstall, explicit purge confirmation, managed-file conflict refusal, maintenance-layout wrapper behavior and shared Ollama protection are host-tested. Real target uninstall/reinstall, user/group disposition, service stop failures and clean-image reinstall acceptance remain target gates. |
| M9.1 — Clean-install and failure campaign | partial | not-run | TEST_MATRIX.md continuation-08; docs/RASPBERRY_PI_ACCEPTANCE_RUN.md; README.md; scripts/release_readiness.py; scripts/collect-support.sh; src/gonken_agent/diagnostics.py Cloud cannot perform physical clean-image acceptance. The repository now provides a target acceptance runbook, startup hardware/software evidence capture, support ZIP export and release-readiness reporting; actual clean-install, reboot, power-loss, hotplug, latency, thermal and hardware observations remain target-run work. |
| M9.2 — Security/license review | host-verified | not-run | TEST_MATRIX.md continuation-08; scripts/release_readiness.py; tests/unit/test_release_readiness.py; CONTINUATION_01_REPORT.md; D-050/D-051, D-060-D-064, D-072 and D-073 Private target-acceptance readiness now has host-verified status, secret-pattern scanning over active release paths, privacy tests, privilege-pattern service checks, uninstall protection tests and content-free diagnostic snapshot tests. Public redistribution approval, third-party artifact licensing and target hardening observations remain later release gates. |
| M9.3 — Documentation and onboarding | host-verified | not-run | README.md; docs/RASPBERRY_PI_ACCEPTANCE_RUN.md; scripts/collect-support.sh; TEST_MATRIX.md continuation-08; docs/development/IMPLEMENTATION_STATUS.md README and target runbook cover end-user Raspberry Pi OS, SSH, bootstrap, service check, log/support export, update, rollback, uninstall, configuration and acceptance evidence collection. Target screenshots/operator feedback remain future refinements after a real Pi run. |
| M9.4 — Development-artifact disposition | host-verified | not-applicable | D-065 Development evidence retained with concise current status; no history removed. Review again before public release. |
| M9.5 — Portable Git handoff | host-verified | not-applicable | CONTINUATION_01_REPORT.md; checkpoint/continuation-01 through checkpoint/continuation-08; scripts/release_readiness.py; docs/RASPBERRY_PI_ACCEPTANCE_RUN.md Private checkpoint transport has been repeatedly verified through ZIP integrity, extracted branch/tag/HEAD, executable modes, clean Git and strict object checks. Continuation-08 is the private release-candidate handoff for Raspberry Pi acceptance testing; public release remains gated by target evidence and licensing decisions. |
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
