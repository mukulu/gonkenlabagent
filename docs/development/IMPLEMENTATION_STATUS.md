# GonKenLab Agent Implementation Status

This handoff is generated from `MILESTONES.json`. Update that ledger, then run
`python scripts/milestone_status.py`; CI rejects drift and missing blueprint items.
Historical implementation detail remains in Git, `TEST_MATRIX.md` and `DECISIONS.md`.
M0/M1 audit and architecture review are complete; the table covers every core implementation item.

<!-- MILESTONES -->
Checkpoint scope: **V09 checkpoint 28 host closure through M10.22; implementation continues through M10.23 while M10.24 remains target-only.**

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
| M4.2 — Audio discovery and recovery | host-verified | not-run | src/gonken_agent/audio/; src/gonken_agent/voice_runtime.py; tests/unit/test_runtime_audio.py; tests/unit/test_voice_appliance.py; docs/development/evidence/v09/checkpoint23/unit_resumption_manifest.json; docs/development/evidence/v09/checkpoint23/pretarget_affected_code_slice_rerun.log Host software covers deterministic device selection/re-enumeration, bounded capture lifecycle and recovery logic. Real ALSA/PipeWire enumeration, USB/Bluetooth hotplug, microphone/speaker routing and audible recovery remain target-run evidence. |
| M4.3 — Resampling/STT/TTS lifecycle | host-verified | not-run | src/gonken_agent/audio/resample.py; src/gonken_agent/audio/speech.py; src/gonken_agent/voice_runtime.py; tests/unit/test_runtime_audio.py; tests/unit/test_voice_appliance.py; docs/development/evidence/v09/checkpoint23/unit_resumption_manifest.json; docs/development/evidence/v09/checkpoint23/pretarget_affected_code_slice_rerun.log Host software covers FIR resampling, Whisper/Piper subprocess validation/cleanup, wake/question capture and bounded progress-cue lifecycle. Real speech recognition, audible Piper output, latency and thermal/resource behavior remain target-run evidence. |
| M5.1 — Push-to-talk and recording indication | host-verified | not-run | src/gonken_agent/interaction/gpiod_ptt.py; src/gonken_agent/interaction/push_to_talk.py; src/gonken_agent/voice_runtime.py; tests/unit/test_m5_1_ptt_runtime.py; tests/unit/test_voice_appliance.py; docs/development/evidence/v09/checkpoint23/pretarget_affected_code_slice_rerun.log Production PTT, recording LED and wake-monitoring LED adapters are host-verified with unique kernel GPIO line-name discovery and fail-closed mapping. Physical button/LED wiring, line identity, visible states, crash/power-cycle behavior and no-login operation remain target-run evidence. |
| M5.2 — Offline boundary | host-verified | not-run | src/gonken_agent/llm/ollama.py; src/gonken_agent/dashboard.py; src/gonken_agent/config.py; tests/unit/test_m2_2_config.py; tests/unit/test_m3_4_ollama_manager.py; tests/integration/test_text_runtime_process.py; docs/development/evidence/v09/checkpoint23/integration_phase.log Host tests enforce numeric loopback-only Ollama/dashboard access, no proxy/DNS/redirect credential path and offline-first configuration. Kernel-observed operation with WAN/DNS unavailable while loopback services continue remains target-run evidence. |
| M6.1 — Application service | host-verified | not-run | TEST_MATRIX.md continuation-04; tests/integration/test_cli_process.py; tests/unit/test_m6_service_manager.py Headless service command and systemd unit are host-tested as degraded supervisor. Raspberry Pi systemd start/stop/restart, reboot/no-login persistence, real audio/GPIO recovery and journal review remain target gates. |
| M6.2 — Service installer/removal | host-verified | not-run | TEST_MATRIX.md continuation-04; scripts/service_manager.py; tests/unit/test_m6_service_manager.py; tests/unit/test_m3_3_release_manager.py Atomic unit/tmpfiles install, exact conflict refusal and reversible removal are host-tested with fake systemctl. Real root install/remove, systemd-analyze verify and target ownership validation remain target gates. |
| M7.1 — Corpus and lexical index | partial | not-run | TEST_MATRIX.md continuation-grounding; text runtime guide Safe deterministic calibrated BM25 and 60-case synthetic regression pass. Real-lab 40/20 evaluation and support calibration remain open. |
| M7.2 — Grounded prompt and response contract | partial | not-run | TEST_MATRIX.md continuation-grounding; text runtime guide Untrusted-data prompt and citation/abstention format enforced. Real model factual support, contradiction and prompt-injection evaluation remain open. |
| M7.3 — Privacy-preserving telemetry | host-verified | not-run | src/gonken_agent/telemetry.py; src/gonken_agent/config.py; tests/unit/test_m2_2_config.py; tests/unit/test_grounding_observability.py; tests/unit/test_support_export.py; docs/development/DECISIONS.md (D-135); docs/development/evidence/v09/checkpoint23/unit_resumption_manifest.json Core telemetry is intentionally content-free, bounded and process-safe; persistent interaction-content logging remains outside release-core pending a separately authorized research/ethics/retention specification. Target inspection must still confirm journals/support/telemetry remain content-minimizing in real operation. |
| M7.4 — Read-only dashboard | host-verified | not-run | TEST_MATRIX.md continuation-grounding; text runtime guide Integrated text dashboard, privacy/Host/Origin/read-only tests pass. Physical runtime integration remains open. |
| M7.5 — Research benchmarks | partial | not-run | TEST_MATRIX.md continuation-grounding; text runtime guide Reproducible synthetic retrieval benchmark and result schema provided. Real grounded/ungrounded LLM, STT, latency/RAM/thermal campaign remains open. |
| M8.1 — Doctor and support bundle | host-verified | not-run | TEST_MATRIX.md continuation-07; src/gonken_agent/diagnostics.py; src/gonken_agent/support.py; scripts/collect-support.sh; tests/unit/test_diagnostics_snapshot.py; tests/unit/test_support_export.py; tests/integration/test_cli_process.py Content-free startup snapshot capture, bounded debug retention, production latest-only mode, service startup recording and support ZIP inclusion are host-tested. Real target snapshot contents must be uploaded after Raspberry Pi installation to confirm USB audio, GPIO, systemd, thermal and resource observations. |
| M8.2 — Update/rollback | host-verified | not-run | TEST_MATRIX.md continuation-06; scripts/update.sh; scripts/update_manager.py; scripts/rollback.sh; scripts/release_manager.py; tests/unit/test_m8_update_manager.py; tests/integration/test_release_lifecycle_process.py Explicit update and rollback are host-tested through immutable release activation, Git ref resolution, no-op update detection, restart orchestration and previous-release rollback. Real target update/rollback execution, future schema migrators and service restart failure handling remain target/future-version gates. |
| M8.3 — Uninstall/reinstall | host-verified | not-run | TEST_MATRIX.md continuation-05; scripts/uninstall.sh; scripts/uninstall_manager.py; tests/unit/test_m8_uninstall_manager.py; tests/integration/test_uninstall_lifecycle_process.py Keep-data uninstall, explicit purge confirmation, managed-file conflict refusal, maintenance-layout wrapper behavior and shared Ollama protection are host-tested. Real target uninstall/reinstall, user/group disposition, service stop failures and clean-image reinstall acceptance remain target gates. |
| M9.1 — Clean-install and failure campaign | partial | not-run | TEST_MATRIX.md continuation-08; docs/RASPBERRY_PI_ACCEPTANCE_RUN.md; README.md; scripts/release_readiness.py; scripts/collect-support.sh; src/gonken_agent/diagnostics.py Cloud cannot perform physical clean-image acceptance. The repository now provides a target acceptance runbook, startup hardware/software evidence capture, support ZIP export and release-readiness reporting; actual clean-install, reboot, power-loss, hotplug, latency, thermal and hardware observations remain target-run work. |
| M9.2 — Security/license review | host-verified | not-run | TEST_MATRIX.md continuation-08; scripts/release_readiness.py; tests/unit/test_release_readiness.py; CONTINUATION_01_REPORT.md; D-050/D-051, D-060-D-064, D-072 and D-073 Private target-acceptance readiness now has host-verified status, secret-pattern scanning over active release paths, privacy tests, privilege-pattern service checks, uninstall protection tests and content-free diagnostic snapshot tests. Public redistribution approval, third-party artifact licensing and target hardening observations remain later release gates. |
| M9.3 — Documentation and onboarding | host-verified | not-run | README.md; docs/RASPBERRY_PI_ACCEPTANCE_RUN.md; scripts/collect-support.sh; TEST_MATRIX.md continuation-08; docs/development/IMPLEMENTATION_STATUS.md README and target runbook cover end-user Raspberry Pi OS, SSH, bootstrap, service check, log/support export, update, rollback, uninstall, configuration and acceptance evidence collection. Target screenshots/operator feedback remain future refinements after a real Pi run. |
| M9.4 — Development-artifact disposition | host-verified | not-applicable | D-065 Development evidence retained with concise current status; no history removed. Review again before public release. |
| M9.5 — Portable Git handoff | host-verified | not-applicable | CONTINUATION_01_REPORT.md; checkpoint/continuation-01 through checkpoint/continuation-08; scripts/release_readiness.py; bootstrap.sh; docs/RASPBERRY_PI_ACCEPTANCE_RUN.md; docs/development/evidence/v09/checkpoint23/ Portable Git handoff has repeated ZIP/extraction/object-integrity evidence. Checkpoint 23 adds an explicit exact-package local-checkpoint install source so Raspberry Pi testing can bind to the downloaded commit rather than remote main. Public redistribution remains separately governed by licensing/provenance decisions. |
| M10.1 — V09 baseline audit and branch identity | host-verified | not-run | docs/development/evidence/v09/wp_a_input_evidence.txt; docs/development/evidence/v09/checkpoint23/final_unit_accounting.json; docs/development/evidence/v09/checkpoint23/final_integration_accounting.json; docs/development/evidence/v09/checkpoint23/final_release_lifecycle_accounting.json; docs/development/evidence/v09/checkpoint23/t0_final_precommit.log Checkpoint 23 final host accounting covers every unit module, every deterministic integration module, all release-lifecycle cases, and T0/control-plane validation. Canonical aggregate attempts interrupted by the external execution boundary remain preserved as diagnostic evidence and are not relabelled PASS. Real Raspberry Pi target evidence remains open. |
| M10.2 — Static environment configuration schema | host-verified | not-run | config/defaults.toml; src/gonken_agent/config.py; tests/unit/test_v09_environment_config.py; tests/unit/test_m2_2_config.py; docs/development/evidence/v09/wp_b_config_policy_tests_rerun.log; docs/development/evidence/v09/wp_b_full_unit.log; docs/development/evidence/v09/wp_b_static_gates.log Host schema/migration validation is complete and downstream simulation/environment consumers are implemented. Target installation/migration against the real Raspberry Pi filesystem and services remains open. |
| M10.3 — Environment domain and mutable policy foundation | host-verified | not-run | src/gonken_agent/environment/domain.py; src/gonken_agent/environment/policy.py; tests/unit/test_v09_environment_policy.py; docs/development/evidence/v09/wp_b_config_policy_tests_rerun.log Domain/policy contracts and downstream controller/service/CLI/voice integrations are host-verified through later V09 checkpoints. Physical target policy persistence, sensor/actuator behavior and lifecycle acceptance remain open. |
| M10.4 — Deterministic controller core | host-verified | not-run | src/gonken_agent/environment/controller.py; tests/unit/test_v09_environment_controller.py; docs/development/evidence/v09/wp_c_controller_affected_tests.log; docs/development/evidence/v09/wp_c_full_unit.log Deterministic controller semantics and downstream service/simulation integration are host-verified. Real sensor timing, relay switching, dwell/hysteresis observations and failure/recovery behavior remain physical/hybrid target gates. |
| M10.5 — Local environment service and IPC | host-verified | not-run | src/gonken_agent/environment/protocol.py; src/gonken_agent/environment/service.py; src/gonken_agent/environment/server.py; src/gonken_agent/environment/client.py; tests/unit/test_v09_environment_ipc.py; docs/development/evidence/v09/wp_d_ipc_affected_tests.log; docs/development/evidence/v09/wp_d_full_unit.log; docs/development/evidence/v09/wp_d_static_gates.log AF_UNIX service/IPC plus production/simulated backend integration are implemented and host-verified. Real service-account I2C/GPIO permissions, Pi device mapping and service behavior with physical hardware remain target-run evidence. |
| M10.6 — CLI, voice, installer, diagnostics and documentation integration | host-verified | not-run | src/gonken_agent/cli.py; src/gonken_agent/diagnostics.py; src/gonken_agent/health.py; src/gonken_agent/operations.py; src/gonken_agent/support.py; src/gonken_agent/dashboard.py; src/gonken_agent/voice_runtime.py; src/gonken_agent/environment/intents.py; src/gonken_agent/environment/responses.py; scripts/environment_service_manager.py; scripts/install.sh; scripts/release_manager.py; scripts/service_manager.py; scripts/uninstall.sh; scripts/uninstall_manager.py; packaging/systemd/gonken-environment.service; packaging/tmpfiles/gonken-environment.conf; tests/unit/test_v09_environment_cli.py; tests/unit/test_v09_environment_voice_intents.py; tests/unit/test_v09_environment_service_manager.py; tests/unit/test_diagnostics_snapshot.py; tests/unit/test_support_export.py; tests/unit/test_grounding_observability.py; tests/integration/test_cli_process.py; tests/integration/test_text_runtime_process.py; tests/integration/test_uninstall_lifecycle_process.py; docs/OPERATIONS.md; docs/development/evidence/v09/wp_e_cli_affected_tests.log; docs/development/evidence/v09/wp_f_observability_affected_tests.log; docs/development/evidence/v09/wp_g_installer_systemd_affected_tests.log; docs/development/evidence/v09/wp_h_voice_watch_affected_tests.log; docs/development/evidence/v09/wp_h_full_unit.log; docs/development/evidence/v09/wp_h_integration_subset.log; docs/development/evidence/v09/wp_h_static_gates.log; src/gonken_agent/environment/sensors/base.py; src/gonken_agent/environment/sensors/sht31.py; src/gonken_agent/environment/actuators/base.py; src/gonken_agent/environment/actuators/gpiod_relay.py; tests/unit/test_v09_environment_hardware_adapters.py; docs/development/evidence/v09/wp_i_hardware_adapters_affected_tests.log; docs/development/evidence/v09/wp_i_full_unit.log; docs/development/evidence/v09/wp_i_static_gates.log; src/gonken_agent/environment/daemon.py; tests/unit/test_v09_environment_daemon_activation.py; docs/development/evidence/v09/wp_j_daemon_activation_affected_tests.log; docs/development/evidence/v09/wp_j_full_unit.log; docs/development/evidence/v09/wp_j_static_gates.log; docs/development/evidence/v09/wp_j_integration_subset.log; src/gonken_agent/environment/service.py; tests/unit/test_v09_environment_polling_loop.py; docs/development/evidence/v09/wp_k_polling_loop_affected_tests.log; docs/development/evidence/v09/wp_k_full_unit.log; docs/development/evidence/v09/wp_k_integration_subset.log; scripts/environment_acceptance_runner.py; docs/ENVIRONMENT_ACCEPTANCE_RUN.md; docs/RASPBERRY_PI_ACCEPTANCE_RUN.md; tests/unit/test_v09_environment_acceptance_runner.py; tests/unit/test_release_readiness.py; docs/development/evidence/v09/wp_l_acceptance_scaffold_affected_tests.log; docs/development/evidence/v09/wp_l_full_unit.log; docs/development/evidence/v09/wp_l_static_gates.log; scripts/ollama_manager.py; tests/integration/test_ollama_lifecycle_process.py; docs/development/evidence/v09/wp_m_ollama_lifecycle_after_hardening.log; docs/development/evidence/v09/wp_m_release_interruption_after_hardening.log; docs/development/evidence/v09/wp_m_manager_unit.log; docs/development/evidence/v09/wp_m_static_gates.log; scripts/bounded_unittest.py; tests/unit/test_bounded_unittest_runner.py; docs/development/evidence/v09/wp_n_bounded_ci_runner_tests.log; docs/development/evidence/v09/wp_n_bounded_integration_slice.log; docs/development/evidence/v09/wp_n_static_gates.log; scripts/bounded_unittest.py; tests/unit/test_bounded_unittest_runner.py; tests/integration/test_release_lifecycle_process.py; docs/development/evidence/v09/wp_o_bounded_case_runner_tests.log; docs/development/evidence/v09/wp_o_release_lifecycle_slices.log; docs/development/evidence/v09/wp_o_static_gates.log; scripts/ci.sh; docs/development/evidence/v09/wp_p_ci_phase_selector_tests.log; docs/development/evidence/v09/wp_p_ci_phase_t0.log; docs/development/evidence/v09/wp_p_ci_bash_n.log; docs/development/evidence/v09/wp_p_compile_phase_change.log Host M10.6 includes CLI, voice, installer, diagnostics, daemon polling, target evidence scaffold, bounded CI observability, release lifecycle case-level decomposition and CI phase selection. Full physical M10.7 target acceptance remains not-run; no host evidence proves real SHT31/relay/fan/audio/wake behavior. |
| M10.7 — Real Raspberry Pi HIL and release acceptance | pending | not-run | docs/RASPBERRY_PI_ACCEPTANCE_RUN.md; docs/ENVIRONMENT_ACCEPTANCE_RUN.md; scripts/environment_acceptance_runner.py; Requires physical Pi, SHT31, relay, PENGLIN adapters, ELUTENG fan, audio and wake/latency evidence. Host tests cannot close this gate. Run the physical M10.7 acceptance campaign on the target Pi and preserve support ZIP plus private environment evidence ledger. |
| M10.8 — Simulation/HIL blueprint expansion | host-verified | not-run | docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md; docs/development/V09_SIMULATION_HIL_TRACEABILITY.csv; docs/development/V09_CHECKPOINT_16_REPORT.md; docs/development/V09_CHANGE_VERIFICATION_REPORT_CHECKPOINT_16.md; docs/development/evidence/v09/checkpoint16/focused_baseline.log; docs/development/evidence/v09/checkpoint16/baseline_t0.log Blueprint/control-plane expansion is superseded by implemented checkpoints M10.9-M10.14 and checkpoint-23 pre-target hardening. Its remaining work is only the target evidence that those later checkpoints deliberately leave open. |
| M10.9 — Simulation foundations | host-verified | not-run | TEST_MATRIX.md (Checkpoint 17); tests/unit/test_v09_environment_simulation.py; affected environment/config/IPC/daemon/CLI test slice Simulation foundations are host-verified and consumed by later CLI/voice/readiness checkpoints. Raspberry Pi execution of full simulation/hybrid profiles remains target-run evidence. |
| M10.10 — Operator simulation experience | host-verified | not-run | src/gonken_agent/cli.py; src/gonken_agent/diagnostics.py; src/gonken_agent/support.py; src/gonken_agent/dashboard.py; src/gonken_agent/operations.py; tests/unit/test_v09_environment_cli.py; tests/unit/test_v09_environment_simulation.py; tests/unit/test_diagnostics_snapshot.py; tests/unit/test_grounding_observability.py; tests/unit/test_support_export.py; docs/OPERATIONS.md; docs/development/evidence/v09/checkpoint18/operator_sim_observability_tests.log; docs/development/evidence/v09/checkpoint18/t0_static.log; docs/development/evidence/v09/checkpoint18/targeted_integration.log Operator simulation CLI, passive watch and observability are host-verified. Target execution, service permissions and real/hybrid observations remain target-run evidence. |
| M10.11 — Hybrid HIL and simulation-aware voice | host-verified | not-run | src/gonken_agent/environment/responses.py; scripts/environment_acceptance_runner.py; tests/unit/test_v09_environment_voice_intents.py; tests/unit/test_v09_environment_acceptance_runner.py; docs/development/evidence/v09/checkpoint19/affected_simulation_voice_hil_tests.log; docs/development/evidence/v09/checkpoint19/t0_static.log Hybrid/simulation voice truthfulness and physical acceptance blocking are host-verified. Full physical M10.7 target acceptance remains not-run. |
| M10.12 — Mandatory GonKen wake responsiveness and transition announcements | host-verified | not-run | config/defaults.toml; src/gonken_agent/voice_runtime.py; src/gonken_agent/interaction/gpiod_ptt.py; src/gonken_agent/cli.py; tests/unit/test_voice_appliance.py; tests/unit/test_m5_1_ptt_runtime.py; tests/unit/test_m2_1.py; docs/development/evidence/v09/checkpoint20/; docs/development/evidence/v09/checkpoint23/pretarget_affected_code_slice_rerun.log Default GonKen, tolerant matching, bounded pipelined standby capture, progress cues, wake diagnostics, wake monitoring indicator and voice-owned transition announcements are host-verified. Real microphone/STT recall/false-wake/latency, GPIO22 visibility and real progress/announcement audio remain target-gated under M10.7. |
| M10.13 — Documentation and evidence hardening | host-verified | not-run | docs/HARDWARE_SETUP.md; docs/ENVIRONMENT_CONTROL.md; docs/SIMULATION.md; docs/OPERATIONS.md; docs/TROUBLESHOOTING.md; docs/ENVIRONMENT_ACCEPTANCE_RUN.md; docs/RASPBERRY_PI_ACCEPTANCE_RUN.md; scripts/validate_v09_docs.py; tests/unit/test_v09_documentation_hardening.py; docs/development/evidence/v09/checkpoint21/; docs/development/evidence/v09/checkpoint23/ Documentation/evidence hardening is host-verified and checkpoint 23 updates the target campaign for exact-package installation, PTT/wake indicators, GPIO discovery and staged evidence return. Physical execution of those instructions remains target-run. |
| M10.14 — User simulation and sensor-deferred HIL release candidate | host-verified | not-run | scripts/environment_simulation_runner.py; scripts/v09_user_test_readiness.py; docs/USER_SIMULATION_HIL_HANDOFF.md; bootstrap.sh; tests/unit/test_v09_user_test_readiness.py; tests/integration/test_v09_user_test_release_candidate.py; docs/development/evidence/v09/checkpoint22/; docs/development/evidence/v09/checkpoint23/ Host user-test gating remains implemented. Checkpoint 23 adds exact downloaded-package installation plus pre-target runtime/mapping repairs. Raspberry Pi simulation, real relay/PENGLIN/fan actuation, SHT31, wake/audio and full M10.7 acceptance remain target NOT_RUN. |
| M10.15 — Target installer/runtime dependency repair and evidence hardening | host-verified | not-run | scripts/release_manager.py; scripts/install.sh; scripts/environment_profile_manager.py; src/gonken_agent/support.py; src/gonken_agent/diagnostics.py; tests/unit/test_m3_3_release_manager.py; tests/unit/test_v09_environment_profile_manager.py; tests/unit/test_support_export.py; tests/unit/test_diagnostics_snapshot.py; docs/development/V09_CHECKPOINT_24_REPORT.md; docs/development/V09_CHANGE_VERIFICATION_REPORT_CHECKPOINT_24.md Real target closure requires the exact checkpoint-24 archive to reach governed INSTALLATION_COMPLETE and pass the target runtime/operator preflight before relay actuation resumes. Physical relay/fan acceptance remains NOT_RUN. |
| M10.16 — Comprehensive closure blueprint and quality-system reconstruction | host-verified | not-run | docs/development/V09_COMPREHENSIVE_CLOSURE_BLUEPRINT_CHECKPOINT_25.md; MASTER_BLUEPRINT.md; TEST_MATRIX.md; DECISIONS.md; external source verification recorded in checkpoint 25 Blueprint reconstructed; implementation continues through M10.17-M10.23. M10.24 remains physical target acceptance. |
| M10.17 — Target Python dependency boundary redesign | host-verified | not-run | scripts/release_manager.py; scripts/install.sh; src/gonken_agent/support.py; requirements/README.md; tests/unit/test_m3_3_release_manager.py; tests/unit/test_support_export.py; docs/development/evidence/v09/checkpoint26/m10_17_release_lifecycle_interruption.log Allow-listed distro binding bridge and isolated target venv are host-verified, including dirty-system-metadata regression. Target build/import remains target-run evidence. Continue with M10.18 installer convergence. |
| M10.18 — Installer convergence DAG, preflight and failure-evidence hardening | host-verified | not-run | scripts/target_preflight.py; scripts/installer_failure_bundle.py; scripts/install.sh; tests/unit/test_v09_target_preflight.py; tests/unit/test_v09_installer_failure_bundle.py; tests/integration/test_install_engine_process.py; docs/development/evidence/v09/checkpoint27/m10_18_19_focused_tests.log Target prerequisite convergence and installer-owned early-failure bundle are host-verified. Real target package/device truth remains target-run evidence. |
| M10.19 — Accounts, groups, configuration and environment-profile convergence | host-verified | not-run | scripts/environment_profile_manager.py; scripts/target_preflight.py; scripts/install.sh; tests/unit/test_v09_environment_profile_manager.py; tests/unit/test_v09_target_preflight.py; docs/development/evidence/v09/checkpoint27/m10_18_19_focused_tests.log Four governed non-actuating backend profiles and identity/socket-group convergence are host-verified. Device permissions and fresh-login effect remain target-run evidence. |
| M10.20 — Systemd runtime, service-context and audio closure | host-verified | not-run | scripts/runtime_context_preflight.py; scripts/install.sh; scripts/release_manager.py; tests/unit/test_v09_runtime_context_preflight.py; tests/unit/test_m6_service_manager.py; tests/unit/test_x4_bluetooth_manager.py; docs/development/evidence/v09/checkpoint28/m10_20_runtime_service_audio.log Service/runtime-context and dedicated PipeWire/WirePlumber structural readiness are host-verified. Physical microphone/speaker/BlueZ behavior, reboot/no-login convergence and latency remain target-run evidence. |
| M10.21 — SHT31/I2C and environment simulation-hybrid-full-real readiness | host-verified | not-run | scripts/i2c_manager.py; scripts/sht31_diagnostic.py; src/gonken_agent/environment/sensors/sht31.py; scripts/environment_profile_manager.py; src/gonken_agent/environment/simulation.py; tests/unit/test_v09_i2c_manager.py; tests/unit/test_v09_sht31_diagnostic.py; tests/unit/test_v09_environment_hardware_adapters.py; docs/development/evidence/v09/checkpoint28/m10_21_inprogress_narrow.log; docs/development/evidence/v09/checkpoint28/m10_21_evidence_mode_fix.log Wire-correct SHT31 transaction, I2C convergence helper, heater/status safeguards, four-profile parity and false-green evidence-mode boundary are host-verified. Physical breakout inspection, /dev/i2c-1 target access, 0x44/0x45 detection, repeated real reads and full-real control remain target-run evidence. |
| M10.22 — Voice/environment end-to-end transaction closure | host-verified | not-run | src/gonken_agent/environment/intents.py; src/gonken_agent/voice_runtime.py; tests/unit/test_v09_environment_voice_intents.py; tests/integration/test_v09_environment_voice_transaction.py; docs/development/evidence/v09/checkpoint28/m10_22_voice_transaction.log Deterministic voice-to-daemon Unix-socket transactions and truthful failure/simulation wording are host-verified. Real wake/STT/TTS, physical relay/fan response and physical sensor query remain target-run evidence. |
| M10.23 — Clean/dirty lifecycle, support, documentation, package and Git closure | pending | not-run |  Complete lifecycle/adversarial/support/documentation/package/Git host gates and prepare the next exact checkpoint. |
| M10.24 — Final Raspberry Pi environment and release acceptance | pending | not-run |  Run exact-package physical target acceptance after M10.17-M10.23 host gates and installer completion; never infer PASS from host evidence. |
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
- Baseline Whisper wake operation is enabled for FIX5 and X4 Bluetooth is opt-in; X1 now denotes the future dedicated low-power wake backend, while X2/X3 remain disabled.
- The archive contains Git history; its inherited origin points to an earlier scratch checkout, not a reachable repository. Do not push to that path; use the documented maintainer remote when ready.

## Resume protocol

Inspect Git status/history and this table; read the relevant blueprint and test evidence.
Select all useful dependency-ready work, implement and verify, then continue without
asking permission to cross an item boundary. Preserve failed/unrun gates explicitly.
At checkpoint close run the full applicable suite and verify a clean extracted Git archive.


## Continuation 08 FIX3 target evidence — 2026-09-11

The real Raspberry Pi run has now validated the immutable application release,
Ollama 0.33.3 with `qwen3.5:2b-q4_K_M`, Whisper 1.9.2, Piper 1.8.0, pinned speech
model downloads and the deterministic Piper-to-Whisper speech smoke. The next
observed blocker was `gonken-agent.service` failing at systemd namespace setup
with status `226/NAMESPACE` because optional `/srv/gonken-agent/corpus` did not
exist. FIX3 changes that path to optional namespace semantics, runs the
root-owned release reconciliation pre-start through a bounded privileged prefix,
permits that pre-start namespace to mutate only installer state, resets stale
service failure state, and supports an exact managed upgrade from the FIX2 unit.

FIX3 also opens X4 Bluetooth as an explicit opt-in extension. The core USB path
remains unchanged. When requested, bootstrap installs/prepares the headless
BlueZ/PipeWire/WirePlumber stack for `gonken-agent`, asks the operator to put one
audio device into pairing mode, pairs/trusts that device, and installs a bounded
autoconnect helper. Hardware evidence confirms onboard Bluetooth on the current
Pi 5 and AIRHUG USB audio, but Bluetooth output/microphone/reboot acceptance is
still unrun.

## FIX3 finalization note — 2026-09-11

The real-Pi `226/NAMESPACE` application-service blocker is repaired in the
managed unit upgrade path. The installer now also exposes a zero-configuration
standard bootstrap, a one-command fresh-Pi launcher, and an opt-in generic
Bluetooth audio extension with explicit device selectors and trusted-device
reconnect. Host regression evidence is recorded in `TEST_MATRIX.md`.

This finalization is intended for the next physical Pi convergence run. It does
not convert the still-open M4.2/M4.3/M5.1 physical audio/GPIO acceptance gates
into host claims: the packaged service remains a governed headless supervisor
until the real capture/playback/PTT path is physically accepted.

## Continuation 08 FIX4 target evidence — 2026-09-12

The first FIX3 physical-Pi rerun stopped before the step engine with
`INSTALL_STATE`: `/var/lib/gonken-agent/install` was `0755 root:root` while its
engine/log subdirectories remained `0700` and installer records remained `0600`.
Root execution failed identically, proving this was an installer-state metadata
invariant rather than a sudo privilege problem.

Forensic source review identified the writer: the successful FIX2 speech smoke
used the generic speech `durable_bytes()` helper to write `speech.record`; that
helper re-normalized the record parent with its generic artifact default of
`0755`. FIX4 gives private speech validation records an explicit `0700` parent
contract and adds a narrowly-scoped upgrade migration that may repair only the
known root-owned `0755` target install-state root back to `0700`. Symlinks,
foreign ownership, group/other-writable state, and generic private directories
remain fail-closed. The migration preserves every installer record and downloaded
artifact and emits the observed/repaired mode.

## FIX5 appliance-readiness implementation — 2026-09-12

**Base:** FIX4 `4d777ca95d908f94e83e90da42e11e1097c75171`.

**Real-Pi evidence motivating FIX5:** FIX4 completed immutable release,
Ollama/Qwen, Whisper/Piper, speech smoke, `gonken-agent.service`, Bluetooth
pair/trust/connect and Bluetooth autoconnect, but the running service remained a
diagnostic supervisor and reported physical voice acceptance pending. Manual
`orchestrator.py`/legacy attempts were not accepted production runtime paths.

### Implemented in FIX5

- production `gonken-agent service` runs the actual local voice appliance;
- `gonken-agent run` starts the same wake runtime manually;
- `gonken-agent talk --seconds N` provides one explicit manual voice turn;
- wake phrase defaults to `Hey Gonken` and initial phrase spotting uses local
  Whisper only;
- dynamic ALSA USB selection and managed Bluetooth PipeWire route support;
- real input/output open probe and real Piper ready announcement;
- ephemeral `/run/gonken-agent/ready.json` readiness contract;
- final installer `appliance_readiness` gate and honest READY summary;
- Bluetooth radio/service/rfkill/power reconciliation before stack acceptance;
- corrected headless PipeWire user-session startup behavior;
- ALSA utilities added as governed target prerequisites;
- local prompt packaged inside each immutable release;
- streamed launcher normalizes package-manager locale and diagnoses blocked
  Wi-Fi without guessing WLAN country;
- user-facing README plus detailed installation, operations, Bluetooth and
  physical acceptance documentation;
- Pi 4 captured as a future separate target profile rather than weakening the
  Pi 5 gate.

### Host verification status

FIX5 host verification currently passes **226/226 unit tests**, the **35-test**
bootstrap/launcher/CLI/install-engine/support/text/uninstall integration group,
normal Ollama lifecycle checks, and the normal three-case speech lifecycle
subset. Static dependency, milestone, release-readiness, Bash, Python compile and
diff gates pass. The intentionally slow release/speech interruption matrices
remain represented by their unchanged FIX4 coverage and selected FIX5 reruns;
physical Pi wake/reboot acceptance remains **UNRUN** until the user installs this
FIX5 build on the target.

### Exact next target action after FIX5 is pushed

```bash
cd ~/gonkenlabagent
git pull --ff-only origin main
./bootstrap.sh --bluetooth-audio --bluetooth-device <DEPLOYMENT_DEVICE_MAC>
```

Accept only a final `APPLIANCE_READY`/`INSTALLATION_COMPLETE ... READY`, then
perform a real `Hey Gonken` spoken turn and reboot/no-login test.

## Continuation 08 FIX6 target evidence — 2026-09-12

FIX5 reached the new physical `appliance_readiness` gate on the real Pi but
remained in `[WAITING] code=AUDIO_CAPTURE_FAILED` for the full 180-second window.
The uploaded support snapshot simultaneously proved that the service account saw
one valid AIRHUG USB capture device and one valid AIRHUG USB playback device,
while Bluetooth was configured and unblocked. This isolated a runtime routing
regression rather than missing hardware/model dependencies.

Forensic review found that FIX5 treated the mere presence of
`/etc/gonken-agent/bluetooth-device.record` as authority to force both directions
through ALSA `default`, even though Bluetooth capture had not been revalidated and
a valid direct USB microphone existed. FIX6 replaces that assumption with
independent adaptive input/output selection: verified PipeWire/Pulse defaults are
preferred; one unambiguous direct ALSA USB path is the fallback; mixed
USB-input/Bluetooth-output is supported; a disappearing Pulse route gets one
bounded direct-ALSA retry. Bluetooth pairing is version-bumped, revalidates the
connected output route, and actively attempts a headset capture profile without
blocking a valid mixed USB-input/Bluetooth-output topology; the later appliance
gate remains authoritative for real microphone capture.

FIX6 also exports richer content-free ALSA/PipeWire route diagnostics and makes
the default sudo support bundle land in the invoking administrator's home with
usable ownership. Host verification passes **235/235 unit tests**, the **35/35**
quick integration group, four normal Ollama lifecycle checks, three normal speech
lifecycle checks, and the static dependency/milestone/release-readiness/Bash/
Python/diff gates. Selected normal release lifecycle cases passed before the
known long rollback-service fixture exceeded the aggregate execution window.
Physical wake/reboot acceptance remains UNRUN until FIX6 is installed on the Pi.


## Continuation 08 FIX7 target evidence — 2026-09-12

FIX6 reaches all prerequisite component postconditions on the Pi but terminates
before the readiness action with `INSTALL_PRECONDITION`. This is now isolated to
a contract error: `appliance_readiness` inherited an application-service
postcondition that required `systemctl is-active`, even though readiness activation
is itself responsible for converging/restarting the service. FIX7 splits
installed+enabled structural status from active runtime status and advances both
application-service and appliance-readiness step versions to force revalidation.

The same support bundle revealed a second real-target defect: the service process
had euid 999 but its Pulse/WirePlumber probes attempted `/run/user/0`. FIX6 used
systemd `%U` in a system unit, which refers to the system manager identity rather
than safely deriving `User=gonken-agent`. FIX7 generates the user-session audio
environment from the actual runtime-account UID and safely upgrades the exact
known FIX6 governed unit.

Automatic audio discovery is now lazy and wired-first: usable USB routes are
preferred, then the exact configured Bluetooth route; input/output may differ,
and Bluetooth remains available when USB is unplugged. This is intended to reuse
the user's already-connected Wi-Fi/Bluetooth and currently plugged USB audio
rather than treating them as mutually exclusive provisioning modes.

Host verification: **240/240 unit tests**, **35/35 quick integration tests**, four
normal Ollama lifecycle tests, three normal speech lifecycle tests, representative
release low-space/rollback tests, and static dependency/milestone/release-
readiness/Bash/Python/diff gates pass. Physical `APPLIANCE_READY`, spoken turn and
reboot/no-login acceptance remain the next target gate.

## V09 Checkpoint 03 — local service and IPC foundation — 2026-09-15

**Base:** V09 Checkpoint 02 `2780d9e38b978be508ee13259e97f3380307e826`.

### Implemented in M10.5

- bounded protocol v1 in `src/gonken_agent/environment/protocol.py` with fixed operation allowlist, top-level unknown-field rejection, request/response size caps and stable error mapping;
- host-testable `EnvironmentServiceCore` in `src/gonken_agent/environment/service.py` that translates `status.get`, `sensor.read`, `health.get`, `fan.set`, `mode.set`, `policy.get`, `policy.update` and non-destructive `probe.run` into controller/policy actions;
- `EnvironmentUnixServer` in `src/gonken_agent/environment/server.py` using AF_UNIX, `0660` socket mode, one bounded newline-delimited JSON request per connection and refusal to replace a non-socket path;
- `EnvironmentClient` in `src/gonken_agent/environment/client.py` for local callers;
- unit coverage in `tests/unit/test_v09_environment_ipc.py` for protocol rejection, closed operation parameters, host-fake status/health/sensor reads, client error propagation, policy generation conflict, disabled-mode rejection and Unix socket lifecycle.

### Evidence

M10.5 affected tests pass **59/59** and the full host unit suite passes **271/271**. Static gates pass. The service reports `physical_evidence=false` and `hardware_backend=host_fake`, so this checkpoint is not hardware acceptance.

### Remaining

M10.6 should add the operator-facing `gonken-agent env` CLI over this client boundary, then extend diagnostics/installer/service wiring and deterministic voice-domain actions. Production hardware adapters and real Raspberry Pi HIL remain open under M10.7.

## V09 Checkpoint 04 — operator CLI environment commands — 2026-09-15

**Base:** V09 Checkpoint 03 `e91c4739eec0e2eabe2cb939e959117027d889a6`.

### Implemented in M10.6 first sub-batch

- added `gonken-agent env` as the operator-facing IPC client surface in `src/gonken_agent/cli.py`;
- added status, health, temperature, humidity, combined read, fan on/off, mode set, policy show/set and bounded non-destructive probe commands;
- made human-readable output report daemon-returned state and preserve `physical_evidence=false` rather than implying hardware proof;
- made JSON output available both as `gonken-agent env --json status` and as the blueprint-style `gonken-agent env status --json`;
- ensured fan/mode/policy mutations pass typed arguments through `EnvironmentClient` rather than touching policy files, GPIO, I2C or shell commands directly;
- added `tests/unit/test_v09_environment_cli.py` to verify command routing, JSON output, daemon rejection handling, capability boundary and policy-set validation.

### Evidence

M10.6 CLI affected tests pass **81/81**.  The full host unit suite passes **277/277**.  Static gates pass.  A targeted deterministic integration subset covering CLI/text/support behavior passes **15/15**.  The CLI sub-batch is therefore host-verified as an IPC client, not as a real environment daemon or hardware acceptance.

### Remaining

M10.6 remains **partial**.  The next dependency-ready sub-batches are diagnostics/support/dashboard environment fields, installer/systemd environment-service wiring, deterministic voice environment intents, watch-mode/operator documentation, and later production hardware adapters.  M10.7 physical HIL remains not-run.


## V09 Checkpoint 05 — environment observability/support/dashboard — 2026-09-15

**Base:** V09 Checkpoint 04 `a38c7bee71e4116d3c629104fb7fe151fd130721`.

### Implemented in M10.6 second sub-batch

- added non-destructive environment diagnostics in `src/gonken_agent/diagnostics.py`;
- added `gonken-environment.service`, `i2cdetect` and `gpioinfo` to bounded startup snapshot awareness;
- added an `environment` component to health summaries and `doctor` output;
- added `environment_control.json` and `environment_health.json` to support bundles;
- added sanitized environment state to read-only dashboard snapshots;
- added tests for content-free diagnostics, support member redaction, dashboard environment status and integration `/api/status` visibility.

### Evidence

M10.6 observability affected tests pass **29/29** and the full host unit suite passes **278/278**.  Static gates pass.  A targeted dashboard/text/support integration subset passes **10/10**.  A bounded broad-CI attempt was interrupted at the existing Ollama lifecycle interruption/recovery fixture and preserved as `wp_f_broad_ci_bounded.log`; it is not a PASS and not attributed to this tranche.  These checks are host-only and do not prove SHT31 reads, relay actuation, fan motion, systemd deployment, or Raspberry Pi HIL.

### Remaining

M10.6 remains **partial**.  Installer/systemd environment-service wiring, deterministic voice environment intents, watch-mode/operator documentation and production hardware adapters remain open.  M10.7 physical HIL remains not-run.

## V09 Checkpoint 06 — environment service installer/systemd wiring — 2026-09-15

**Base:** V09 Checkpoint 05 `0dddb5d86996fe995a1de384a9a0fb482df3127c`.

### Implemented in M10.6 installer/systemd sub-batch

- added structural `gonken-environment.service` and environment tmpfiles contract;
- added `scripts/environment_service_manager.py`;
- updated installer/release/uninstall paths to provision `gonken-env`, `gonken-envctl`, state/cache/runtime directories and service files without enabling or starting the environment service by default;
- kept voice dependency soft through `Wants=`/`After=` rather than `Requires=`;
- kept `gonken-agent env serve` fail-closed for enabled profiles before accepted hardware-daemon activation.

### Evidence

M10.6 installer/systemd affected tests passed **41/41**. The full host unit suite passed **285/285**. Static gates passed. Isolated release lifecycle and uninstall integration checks passed. These checks prove structural packaging and lifecycle behavior only; they do not prove target systemd execution, SHT31, relay, fan, or real Pi acceptance.

### Remaining

M10.6 remained partial after this checkpoint: deterministic voice environment intents, watch mode, production hardware adapters and target-grounded documentation remained open. M10.7 physical HIL remained not-run.

## V09 Checkpoint 07 — deterministic voice intents and watch mode — 2026-09-15

**Base:** V09 Checkpoint 06 `3ad094ac9a04a888ffbf55cdd839f8b115fc4b4b`.

### Implemented in M10.6 voice/watch sub-batch

- added deterministic environment intent parsing in `src/gonken_agent/environment/intents.py`;
- added daemon-result-derived spoken responses in `src/gonken_agent/environment/responses.py`;
- routed clear environment commands through `ConversationBrain.reply()` before ordinary local LLM chat;
- added `gonken-agent env watch` as a repeated IPC read path with human and newline-JSON output;
- documented operator and voice boundaries in `docs/OPERATIONS.md`.

### Evidence

M10.6 voice/watch affected tests passed **43/43**. The full host unit suite passed **295/295**. A targeted CLI/text integration subset passed **14/14**. Static gates passed. These checks prove deterministic parsing, typed client routing and no-fake-success responses only; they do not prove a live environment daemon, hardware adapters or physical Pi acceptance.

### Remaining

M10.6 remained partial after this checkpoint: production SHT31/libgpiod adapters, real hardware-daemon activation and target-grounded documentation remained open. M10.7 physical HIL remained not-run.

## V09 Checkpoint 08 — SHT31/libgpiod hardware-adapter foundation — 2026-09-15

**Base:** V09 Checkpoint 07 `e635d2f7f48d4087581e15059c1398f8c16f8295`.

### Implemented in M10.6 hardware-adapter sub-batch

- added `src/gonken_agent/environment/sensors/base.py` and `src/gonken_agent/environment/sensors/sht31.py`;
- added `src/gonken_agent/environment/actuators/base.py` and `src/gonken_agent/environment/actuators/gpiod_relay.py`;
- added lazy-import production boundaries for `python3-smbus` and `python3-libgpiod` so ordinary host imports do not require Raspberry Pi hardware packages;
- added SHT31 CRC-8 validation, frame decoding, conversion formulas, command construction and truthful unavailable/CRC-failure readings;
- added a libgpiod relay adapter with inactive startup request, active-low/active-high handling, logical ON/OFF writes, safe-off close and power-only capability metadata;
- updated `EnvironmentServiceCore` so injected actuators receive controller state and actuator write failures force `ACTUATOR_ERROR_SAFE_OFF` without speaking or returning fake success;
- updated `gonken-agent env serve` wording so enabled profiles fail closed as target-gated hardware-daemon activation rather than pretending the adapters do not exist.

### Evidence

M10.6 hardware-adapter affected tests passed **45/45**. The full host unit suite passed **305/305**. Static gates passed. These are host tests with fake SMBus and fake libgpiod objects. They verify adapter code paths and service-boundary failure behavior, but they do not prove `/dev/i2c-*`, `/dev/gpiochip*`, SHT31 presence, relay polarity, USB switching, fan movement or target systemd execution.

### Remaining

M10.6 is still partial. The next dependency-ready batch should transition `env serve` from a fail-closed scaffold to a supervised daemon initialization path that constructs the real service core from static config and policy storage while preserving degraded-state behavior when sensor hardware is absent. M10.7 remains the first gate allowed to claim physical SHT31/relay/fan/Raspberry Pi acceptance.

## V09 Checkpoint 10 — daemon polling/control-loop scaffold — 2026-09-15

**Base:** V09 Checkpoint 09 `c9b536a68f9c4d99b3aa19319c30c39cc4f1dae4`.

### Implemented in M10.6 polling/control-loop sub-batch

- added `EnvironmentServiceCore.poll_once()` as the single host-testable daemon polling/control-cycle primitive;
- centralized sensor exception mapping so missing/failed sensor reads become structured `SensorReading` failures rather than daemon thread crashes;
- added poll metadata to daemon metadata and health payloads: poll count, poll error count, last poll time and last poll error code;
- added `EnvironmentPollingLoop`, a bounded/stoppable background thread using the configured poll interval;
- attached `EnvironmentPollingLoop` to `EnvironmentDaemon.from_config()` and to the `serve_forever()` lifecycle;
- changed `gonken-agent env serve` to use `EnvironmentDaemon.from_config()` for normal serving so enabled profiles use the polling scaffold;
- added tests for AUTO polling transitions, sensor-failure safe-off, actuator-error safe-off recording, bounded loop stop behavior and daemon-config loop attachment.

### Evidence

M10.6 polling/control affected tests passed **39/39**. The full host unit suite passed **316/316**. A targeted CLI/text integration subset passed **14/14**. These are host-only tests with fake sensor/actuator/clock objects. They verify daemon polling behavior, fail-closed transitions and lifecycle cleanup, but they do not prove physical SHT31, relay, fan, systemd or reboot behavior.

### Remaining

M10.6 is now substantially host-integrated but still **partial** because target-grounded operator documentation and any final daemon/service refinements must be completed after or alongside M10.7 target evidence. M10.7 remains not-run and is the first gate allowed to claim Raspberry Pi hardware acceptance.

## V09 Checkpoint 11 — M10.7 evidence scaffold and target-readiness documentation — 2026-09-15

**Base:** V09 Checkpoint 10 `b07ad80c3c7f504686da35da2c4c34fed4b9f89e`.

### Implemented in final M10.6 host sub-batch

- added `scripts/environment_acceptance_runner.py` as the private M10.7 environment evidence collector;
- added non-destructive collection for platform identity, voice/environment service state, daemon status/health, sensor read/probe and recent journals;
- added an explicit `--allow-actuation` gate for fan ON/OFF cycle commands;
- made every generated manifest and step file record `physical_acceptance_claimed=false`;
- added `docs/ENVIRONMENT_ACCEPTANCE_RUN.md` and linked it from the main Pi runbook and README;
- updated `scripts/release_readiness.py` so M10.1-M10.6 are required host gates and M10.7 is an explicit target gate;
- included the evidence runner in the immutable release maintenance payload.

### Evidence

M10.6 acceptance-scaffold affected tests passed **8/8**. The full host unit suite passed **321/321**. Static gates passed, and release-readiness now reports **READY_FOR_TARGET_ACCEPTANCE** with M10.7 still listed under target gates. These are host and documentation/scaffold checks only; they do not prove real I2C, SHT31, GPIO, relay, fan, systemd, reboot or wake behavior.

### Remaining

M10.6 is host-verified. M10.7 remains not-run and requires the physical Raspberry Pi, SHT31, relay, PENGLIN adapters, ELUTENG fan, audio path and wake/voice evidence. The exact next action is to run the Pi acceptance runbook and the private environment evidence collector on the target.

## V09 Checkpoint 13 — bounded CI module runner and observable aggregate checks — 2026-09-15

**Base:** V09 Checkpoint 12 `0bae6b6fd219b83186fd716c16028652f77f4bbd`.

### Implemented in host-side quality tranche

- added `scripts/bounded_unittest.py`, a standard-library test runner that discovers unittest files and runs each module in an independent subprocess;
- updated `scripts/ci.sh` so the canonical T1 unit and deterministic integration phases use the bounded runner instead of one monolithic `unittest discover` process;
- added per-module log files and JSON manifests under `build/ci-logs` by default, configurable through `GONKEN_CI_LOG_DIR`;
- added explicit per-module timeouts and heartbeat output through `GONKEN_CI_UNIT_MODULE_TIMEOUT`, `GONKEN_CI_INTEGRATION_MODULE_TIMEOUT`, and `GONKEN_CI_HEARTBEAT_SECONDS`;
- added regression tests proving pass, fail, timeout and CI-wiring behavior for the bounded runner.

### Evidence

Checkpoint 13 affected tests passed **9/9**. Static gates passed. A bounded integration slice covering the previously repaired Ollama lifecycle module and CLI process module passed **2/2** through the new runner. A bounded release-lifecycle aggregate attempt produced module-level heartbeat and logs, but the container session was interrupted while the long release end-to-end install test was still running; it remains **INTERRUPTED / NEEDS_MANUAL_REVIEW**, not a PASS.

### Remaining

M10.7 remains not-run and requires the physical Raspberry Pi, SHT31, relay, PENGLIN adapters, ELUTENG fan, audio path and wake/voice evidence. Host-side aggregate release lifecycle remains observable but still needs either a longer dedicated run or further release-E2E decomposition if the local execution window remains insufficient.

## V09 Checkpoint 14 — release lifecycle CI decomposition — 2026-09-15

**Base:** V09 Checkpoint 13 `e5fbcda`.

### Implemented in host-side quality tranche

- extended `scripts/bounded_unittest.py` with `--granularity case` so selected modules can run each unittest case in a separate subprocess with its own timeout, heartbeat, log and manifest row;
- added `--exclude-module` so ordinary integration discovery can omit a heavy module that is run separately at finer granularity;
- updated `scripts/ci.sh` to run ordinary deterministic integration at module granularity while running `tests.integration.test_release_lifecycle_process` separately at case granularity;
- decomposed the formerly combined release-only/default-boundary E2E method into named build/freeze, repeat/idempotency and target-boundary cases;
- preserved release acceptance behavior: failures and timeouts remain CI failures, and no physical target evidence is inferred from host success.

### Evidence

Checkpoint 14 bounded-runner tests passed **6/6**. The affected runner/release interruption/finalization slice passed **10/10**. The decomposed release E2E cases passed **4/4** when run individually. Static gates passed. A multi-case bounded-runner attempt was interrupted by the external session boundary after partial output and is recorded only as diagnostic evidence.

### Remaining

M10.7 remains not-run and requires the physical Raspberry Pi, SHT31, relay, PENGLIN adapters, ELUTENG fan, audio path, reboot/no-login convergence and wake/voice evidence. A full long-host `scripts/ci.sh` run may still be useful in an environment with enough wall-clock allowance, but the previous opaque release-lifecycle bottleneck is now decomposed into case-level evidence.

## V09 Checkpoint 15 — CI phase selection and resumable host evidence — 2026-09-15

**Base:** V09 Checkpoint 14 `6413627e236730882232636249d3892a665cae3d`.

### Implemented in host-quality sub-batch

- added `scripts/ci.sh --phase PHASE` with `t0`, `unit`, `integration`, `release-lifecycle` and `all` phases;
- added `scripts/ci.sh --list-phases` and user-facing help text;
- preserved default `scripts/ci.sh` behavior as the full canonical host check order;
- added unit coverage for phase listing, help, invalid phase refusal and retained bounded-runner wiring;
- recorded external-session interruptions as diagnostic evidence rather than as full CI PASS or product FAIL.

### Evidence

Checkpoint 15 affected CI phase-selector tests passed **8/8**.  `scripts/ci.sh --phase t0` passed.  Bash syntax and Python compile checks for the touched CI/test files passed.  A full aggregate CI attempt under an external 240-second wrapper and a separate `--phase unit` attempt were interrupted by the execution environment; those logs are preserved as diagnostic evidence only and are not claimed as PASS.

### Remaining

Host CI is now more resumable and observable, but a full one-command `scripts/ci.sh` PASS is still not claimed in this environment.  M10.7 remains not-run and requires physical Raspberry Pi evidence for I2C, SHT31, gpiochip mapping, relay polarity, PENGLIN switching, ELUTENG fan cycles, reboot/no-login convergence and wake/voice operation.


## V09 Checkpoint 18 — operator simulation CLI, passive watch and simulation observability — 2026-09-15

**Base:** V09 Checkpoint 17 `17e2a96d0382ad666e086af4e3d7ddd8bc65298b`.

### Implemented in M10.10 operator simulation sub-batch

- added `gonken-agent env simulate ...` operator commands for simulation status, reset, sensor set/unavailable/CRC-error/stale/recover/reset and simulated fan show/behavior/unavailable/fail-next-write/reset;
- converted `gonken-agent env watch` from an active `sensor.read` loop to passive `state.snapshot.get` observation, preserving explicit `env read` as the read-now operation;
- expanded watch rows to show sensor/actuator provenance, fan power, transition reason, policy generation and `physical_evidence=false`;
- exposed simulation and snapshot summaries through non-destructive diagnostics, support export, public environment health and loopback dashboard status;
- added a full-simulation CLI-over-Unix-socket test proving operator commands can set a simulated reading, run policy/controller polling and observe the resulting simulated fan state without any physical evidence claim.

### Evidence

Checkpoint 18 affected operator/simulation/observability tests passed **54/54**.  `scripts/ci.sh --phase t0` passed.  A targeted CLI/text integration subset passed **14/14**.  A bounded `scripts/ci.sh --phase unit` attempt progressed through multiple modules and was interrupted by the external execution boundary at `tests.unit.test_release_readiness`; that active module passed **3/3** when rerun narrowly.  No physical target evidence is claimed.

### Remaining

M10.10 is host-verified.  Remaining dependency-ready work moves to M10.11 simulation-aware voice/hybrid HIL evidence rules, then M10.12 mandatory `GonKen` wake/progress/announcement implementation, M10.13 documentation hardening and M10.7 real Raspberry Pi target acceptance.


### V09 checkpoint 19 — simulation-aware voice and hybrid-HIL blocking

Checkpoint 19 closes the M10.11 host gate for simulation-aware voice wording and physical acceptance runner refusal rules. Voice responses now name simulated sensor and actuator boundaries, and `environment_acceptance_runner.py` records `SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED` when JSON evidence shows simulated or hybrid backends. This is host evidence only; M10.7 physical Raspberry Pi acceptance remains open.

## V09 Checkpoint 20 — Mandatory GonKen wake, responsiveness cues and transition announcements — 2026-09-15

Checkpoint 20 implements the M10.12 host gate. The default packaged wake phrase is now `GonKen`, with a host-tested recall-oriented transcript matcher that accepts the legacy `Hey GonKen` form, split `Gon Ken` tokens and bounded one-edit variants of the `gonken` token. `gonken-agent wake status --json` reports matcher details and explicitly records `physical_evidence=false` and `real_wake_acceptance=NOT_RUN`.

The voice runtime now has a deterministic processing cue plan, a governed Piper cue cache contract, and a worker-thread answer path that can speak bounded progress cues without overlapping the final response. Fast deterministic environment actions bypass progress cues. The environment service records controller transition events, and the voice layer consumes those events to announce selected automatic/semi-automatic/safe-off transitions while preserving simulation and no-blade-motion wording. The environment daemon still does not own audio.

Evidence: affected wake/transition tests passed **107/107**; T0 static gates passed; physical-boundary regression tests passed **36/36**; the active module from the interrupted unit-phase attempt passed **3/3** when rerun narrowly. A full unit-phase PASS is not claimed. No real microphone/STT/audio wake behavior, real progress-cue timing or physical environment hardware behavior is claimed.

Remaining dependency-ready work moves to M10.13 documentation/evidence hardening and M10.14 user simulation/sensor-deferred HIL release-candidate work. M10.7 physical Raspberry Pi acceptance remains not-run.


## V09 Checkpoint 28 — runtime context, sensor transport and voice transaction closure — 2026-09-16

**Base:** V09 Checkpoint 27 `6d0bc9a`.

### Completed

- added a non-actuating runtime-context preflight for the generated systemd environment and dedicated PipeWire/WirePlumber user-session prerequisites;
- added governed Raspberry Pi I2C enable/status/service-user-openability handling without probing a sensor address during installer preflight;
- replaced register-oriented SMBus SHT31 reading with the sensor's raw command/write then six-byte read transaction over Linux I2C, while retaining CRC/conversion validation;
- added SHT31 status, heater-off enforcement, soft reset and clear-status support plus an address-discovery/repeated-read diagnostic whose default campaign is 100 reads;
- preserved four simulation/hybrid/full-real static profiles with explicit 0x44/0x45 configuration;
- removed a physical-evidence false green: real backend names now report `TARGET_REAL_BACKENDS_UNVERIFIED` rather than `TARGET_PHYSICAL`;
- added an end-to-end deterministic voice transaction test through the actual AF_UNIX daemon protocol, including unavailable-daemon refusal.

### Verified evidence

- M10.20 focused runtime/service/audio slice: **52/52 PASS** (`checkpoint28/m10_20_runtime_service_audio.log`).
- M10.21 focused sensor/release/profile slice: **77/77 PASS** (`checkpoint28/m10_21_inprogress_narrow.log`).
- evidence-mode/documentation boundary slice: **19/19 PASS** (`checkpoint28/m10_21_evidence_mode_fix.log`).
- voice-to-daemon transaction integration: **3/3 PASS** (`checkpoint28/m10_22_voice_transaction.log`).

These results are host/target-shadow evidence only. They do not prove the physical SHT31, physical audio path, real GPIO relay response through GonKen, or wake-word operation.

### Remaining

M10.23 is now the next dependency-ready host tranche: lifecycle/adversarial/support/documentation/package/Git closure. M10.24 remains the exact-package Raspberry Pi campaign and is the only gate allowed to close remaining physical evidence.
