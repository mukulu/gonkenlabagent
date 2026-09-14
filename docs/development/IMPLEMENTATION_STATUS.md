# GonKenLab Agent Implementation Status

This handoff is generated from `MILESTONES.json`. Update that ledger, then run
`python scripts/milestone_status.py`; CI rejects drift and missing blueprint items.
Historical implementation detail remains in Git, `TEST_MATRIX.md` and `DECISIONS.md`.
M0/M1 audit and architecture review are complete; the table covers every core implementation item.

<!-- MILESTONES -->
Checkpoint scope: **V09 environment-control foundation from FIX7 checkpoint**

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
| M10.1 — V09 baseline audit and branch identity | host-verified | not-run | docs/development/evidence/v09/wp_a_input_evidence.txt; docs/development/evidence/v09/wp_a_focused_60_tests_after_v09_foundation.log; docs/development/evidence/v09/wp_a_isolated_cli_run_test.log Broad CI baseline attempt was interrupted by timeout at the integration stage; the apparent slow CLI-run test passed alone. Real Raspberry Pi evidence remains open. |
| M10.2 — Static environment configuration schema | host-verified | not-run | config/defaults.toml; src/gonken_agent/config.py; tests/unit/test_v09_environment_config.py; tests/unit/test_m2_2_config.py; docs/development/evidence/v09/wp_b_config_policy_tests_rerun.log; docs/development/evidence/v09/wp_b_full_unit.log; docs/development/evidence/v09/wp_b_static_gates.log Host validation covers schema-2 defaults, disabled environment section, schema-1 site migration and static bounds. Target install migration remains open. Full integration/CI remains NEEDS_MANUAL_REVIEW due existing Ollama lifecycle timeout in this environment. |
| M10.3 — Environment domain and mutable policy foundation | host-verified | not-run | src/gonken_agent/environment/domain.py; src/gonken_agent/environment/policy.py; tests/unit/test_v09_environment_policy.py; docs/development/evidence/v09/wp_b_config_policy_tests_rerun.log Pure host tests cover domain/policy contracts only. Controller, IPC, CLI, voice, installer, diagnostics and physical HIL remain open. |
| M10.4 — Deterministic controller core | host-verified | not-run | src/gonken_agent/environment/controller.py; tests/unit/test_v09_environment_controller.py; docs/development/evidence/v09/wp_c_controller_affected_tests.log; docs/development/evidence/v09/wp_c_full_unit.log Host validation covers pure deterministic controller semantics only: MANUAL, SEMI_AUTOMATIC, AUTOMATIC, DISABLED, dwell, hysteresis, median valid samples, staleness safe-off, recovery and policy-update stop behavior. No hardware adapter, daemon, IPC, CLI, voice, installer or physical Pi actuation is implemented yet. |
| M10.5 — Local environment service and IPC | host-verified | not-run | src/gonken_agent/environment/protocol.py; src/gonken_agent/environment/service.py; src/gonken_agent/environment/server.py; src/gonken_agent/environment/client.py; tests/unit/test_v09_environment_ipc.py; docs/development/evidence/v09/wp_d_ipc_affected_tests.log; docs/development/evidence/v09/wp_d_full_unit.log; docs/development/evidence/v09/wp_d_static_gates.log Host validation covers bounded JSON protocol validation, host-fake service core, AF_UNIX server/client, socket mode, closed operation parameters, client error propagation and no hardware/shell imports. It does not implement production SHT31/libgpiod adapters, systemd unit installation, CLI command, voice action, dashboard, or real Pi actuation. |
| M10.6 — CLI, voice, installer, diagnostics and documentation integration | partial | not-run | src/gonken_agent/cli.py; src/gonken_agent/diagnostics.py; src/gonken_agent/health.py; src/gonken_agent/operations.py; src/gonken_agent/support.py; src/gonken_agent/dashboard.py; tests/unit/test_v09_environment_cli.py; tests/unit/test_diagnostics_snapshot.py; tests/unit/test_support_export.py; tests/unit/test_grounding_observability.py; tests/integration/test_text_runtime_process.py; docs/development/evidence/v09/wp_e_cli_affected_tests.log; docs/development/evidence/v09/wp_f_observability_affected_tests.log; docs/development/evidence/v09/wp_f_full_unit.log; docs/development/evidence/v09/wp_f_static_gates.log; docs/development/evidence/v09/wp_f_integration_subset.log CLI and diagnostics/support/dashboard sub-batches are host-verified through the shared environment client/observability boundaries. M10.6 remains partial: installer/systemd environment unit wiring, deterministic voice intents, watch-mode/operator documentation and production SHT31/libgpiod hardware adapters remain. Real Pi evidence remains open. |
| M10.7 — Real Raspberry Pi HIL and release acceptance | pending | not-run |  Requires physical Pi, SHT31, relay, PENGLIN adapters, ELUTENG fan, audio and wake/latency evidence. Host tests cannot close this gate. |
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
