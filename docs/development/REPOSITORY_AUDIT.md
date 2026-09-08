# GonKenLab Agent Repository Forensic Audit

**Audit date:** 2026-09-08 UTC

**Repository:** `https://github.com/mukulu/gonkenlabagent`

**Inspected application baseline:** `6682360786135136abeb0bd2a17a9d45c6f291e7`

**Development branch:** `dev/bootstrap-rearchitecture`

**Audit type:** read-only examination of application code; documentation-only changes

## 1. Executive conclusion

The repository is a small, coherent prototype, not yet a dependable headless Raspberry Pi appliance. Its most recent commits substantially improved fresh-install behavior: they introduced a repository-owned virtual environment, avoided system-Python `pip`, added a fresh-Pi bootstrap, configured openWakeWord for ONNX on Python 3.13, pinned whisper.cpp to release `b4938`, built Whisper with static project libraries, and added diagnostic scripts. Those changes address real failures encountered during earlier Raspberry Pi installation attempts.

The current repository nevertheless does not implement the newly stated end state. It has no GonKenLab Agent systemd service, no automatic assistant startup, no service-account or privilege design, no safe voice shutdown/reboot mechanism, no custom “Gonken” wake-word asset or training workflow, no local document retrieval, no telemetry/provenance dashboard, no interrupted-install recovery model, and no automated regression suite or continuous integration. Its default runtime is also not fully offline: most questions outside a narrow group are routed to Moonshot cloud AI when configured, while weather, news, and jokes call external APIs.

The repository contains incomplete renaming from the upstream “Jansky” personal-assistant concept. The resulting identity mismatch is functional, not merely cosmetic: configuration tells the user to say “Hey Jarvis,” one interactive test tells the user to say “Hey Jansky,” the runtime introduces itself as Jansky and Mayukh’s personal assistant, and the desired project is GonKenLab Agent for an AI-lab context.

The correct next action is therefore **not** a direct model-string patch and **not** immediate systemd implementation. The next action is to create an implementation-grade `MASTER_BLUEPRINT.md` that resolves the verified requirement conflicts, defines installation/runtime ownership and filesystem boundaries, specifies milestone acceptance tests, and orders the work so that service installation is built on a stable configuration and packaging foundation.

## 2. Audit mandate and evidence boundaries

### 2.1 Questions this audit answers

- What does the repository actually implement at the inspected commit?
- Which earlier installation problems have already been addressed?
- Where do code, documentation, configuration, and current requirements disagree?
- Which installation, runtime, audio, model, service, security, recovery, and testing risks are present?
- Which claims can be validated without Raspberry Pi hardware?
- Which validations must remain explicitly pending?
- What should the next engineering milestone do?

### 2.2 Evidence examined

1. All 50 tracked repository files at baseline commit `6682360`, including:
   - 26 Python files;
   - 2 shell scripts;
   - configuration and environment templates;
   - `README.md` and the 2,750-line historical `PRD.md`;
   - 9 PNG UI assets and 5 WAV filler assets.
2. All nine commits in the reachable Git history.
3. The supplied requirements note, `Pasted markdown(5).md`.
4. The supplied feasibility/build blueprint, `SOPHIA_Lab_Raspberry_Pi_Project_Feasibility_and_Build_Blueprint(3).md`.
5. Current official Ollama model metadata for `qwen3.5:2b-q4_K_M`.
6. Static and host-environment checks recorded in `TEST_MATRIX.md`.

### 2.3 Explicit limitations

The audit host is Ubuntu 24.04 on x86_64 with Python 3.12, not Raspberry Pi OS on ARM64 with Python 3.13. No Raspberry Pi, GPIO, USB audio device, system boot sequence, Ollama service, local LLM, Whisper binary/model, or Piper voice was available. The full installer was deliberately not executed because it performs privileged APT installation, runs a remote Ollama installation script, downloads large artifacts, compiles Whisper, and changes system service state. Consequently:

- static conclusions are verified;
- dependency availability is partially probed, not fully established;
- runtime/hardware claims remain unverified until executed on the target Pi;
- no claim of production readiness is justified by this audit.

## 3. Repository and history baseline

### 3.1 Git state

| Item | Observed state |
|---|---|
| Default branch | `main` |
| Original baseline HEAD | `6682360` |
| Remote | `origin` → `https://github.com/mukulu/gonkenlabagent.git` |
| Original working tree | clean |
| Reachable commits | 9 |
| Existing remote development branches | none observed |
| Audit branch created | `dev/bootstrap-rearchitecture` |
| Git object integrity | `git fsck --full --strict` passed |

### 3.2 History interpretation

The first four commits established and renamed the upstream Jansky/PiBot prototype. The five commits from 2026-09-07 to 2026-09-08 are targeted installation repairs:

| Commit | Material effect |
|---|---|
| `4c26d04` | improved path/config/audio assumptions and began GonKenLab renaming |
| `0deaf01` | standardized `.venv`, requirements, and diagnostics |
| `e9af5c6` | moved openWakeWord to an ONNX-only installation for Python 3.13 |
| `95a787e` | added `bootstrap.sh`, pinned/reworked Whisper provisioning, added smoke test |
| `6682360` | rebuilt Whisper statically and expanded runtime diagnostics |

This history is useful and should be preserved. It also shows reactive fixes applied to a monolithic installer. The next stage should introduce explicit contracts and failure-path tests before adding more interdependent behavior.

## 4. What the repository currently builds

### 4.1 Current installation flow

`bootstrap.sh`:

1. assumes Debian/Raspberry Pi OS with `apt-get`;
2. ensures Git, curl, and CA certificates are present;
3. clones `main` by default into the invoking user’s `~/gonkenlabagent`, or updates an existing checkout;
4. refuses an existing tracked dirty checkout;
5. executes `setup.sh`.

`setup.sh`:

1. runs `apt update` and installs build/audio/Python packages;
2. creates or repairs a repository-owned `.venv`;
3. installs broad Python dependency ranges;
4. installs openWakeWord 0.6.0 without its declared dependencies, then downloads and tests ONNX models;
5. installs/starts Ollama, pulls `qwen2.5:1.5b`, and checks for non-empty inference output;
6. clones whisper.cpp, checks out `b4938`, builds a static `whisper-cli`, downloads `base.en-q5_1`, and transcribes a sample;
7. downloads a Piper voice and JSON file;
8. creates `.env` once;
9. runs `scripts/doctor.py` and `scripts/smoke_test.py`;
10. prints a manual command for starting the assistant.

This ends at a runnable development checkout. It does **not** install GonKenLab Agent as an operating-system service.

### 4.2 Current runtime flow

1. `orchestrator.py` loads JSON and `.env` configuration.
2. It resolves an AIRHUG microphone and speaker during process construction.
3. It loads Piper and validates Whisper.
4. It creates an Ollama client and keyword/LLM router.
5. It optionally constructs weather, news, and Moonshot clients from API keys.
6. It loads the bundled openWakeWord `hey_jarvis` ONNX model unless a custom existing path is supplied.
7. It speaks a Jansky greeting and begins continuous wake-word capture.
8. On detection, it records until inferred silence, transcribes, routes, speaks, and resumes wake-word listening.

### 4.3 Current state and filesystem ownership

The source checkout, virtual environment, compiled Whisper dependency, Whisper model, Piper voice, `.env`, and implicit third-party cache/model state are all associated with a user checkout. There is no declared separation among:

- immutable application code;
- system configuration;
- secrets;
- downloaded model data;
- build artifacts;
- runtime state;
- logs;
- user/developer checkout.

This is acceptable for a prototype but unsuitable as the implicit foundation for a formally installed, least-privilege, upgradeable service.

## 5. Verified strengths worth preserving

| ID | Strength | Evidence/implication |
|---|---|---|
| S-01 | Repository-owned Python environment | `setup.sh` consistently invokes `.venv/bin/python -m pip`, avoiding Raspberry Pi OS PEP 668 system-Python modification. |
| S-02 | Invalid venv detection | Installer checks interpreter isolation and availability of `pip`, then recreates a stale/incomplete venv. |
| S-03 | Whisper source pin | `WHISPER_REF=b4938` limits upstream drift. |
| S-04 | Whisper runtime validation | Installer checks help execution, static build configuration, unresolved shared libraries, and sample transcription. |
| S-05 | Recoverable Whisper model download | Empty/missing model files trigger a fresh download. |
| S-06 | ONNX-only wake-word intent | The code avoids unavailable TFLite runtime on the reported Python 3.13 ARM64 environment. |
| S-07 | Repository-relative primary paths | `config.py` largely avoids a fixed `/home/pi` installation path. |
| S-08 | Branch and install-directory overrides | Bootstrap exposes `GONKEN_BRANCH`, `GONKEN_REPO_URL`, and `GONKEN_INSTALL_DIR`. |
| S-09 | Dirty tracked-checkout guard | Bootstrap avoids overwriting tracked local changes during pull. |
| S-10 | Hardware absence distinguished from software failure | Doctor/smoke scripts issue audio warnings instead of falsely classifying unplugged hardware as a dependency installation failure. |
| S-11 | Local speech components | Whisper and Piper paths are local and no speech content is intentionally transmitted by those components. |
| S-12 | No committed credentials detected | A targeted scan of all reachable history found no credible API token/private-key pattern. |
| S-13 | Media assets structurally valid | All PNG CRC/chunk structures and WAV headers/parameters validated. |

These features should be refactored into the future architecture, not discarded wholesale.

## 6. Findings summary

Severity describes impact on the requested unattended, privacy-sensitive Raspberry Pi appliance—not merely on the present manual prototype.

| Severity | Count | Meaning |
|---|---:|---|
| Critical | 6 | Requested end state cannot safely or truthfully operate |
| High | 18 | Likely fresh-install, reboot, privacy, recovery, or maintainability failure |
| Medium | 16 | Correctness, testability, documentation, or operational weakness |
| Low | 7 | Cleanup or clarity issue that should be addressed opportunistically |

## 7. Critical findings

### C-01 — No GonKenLab Agent service or boot orchestration exists

There is no tracked `.service` unit, service installer, service user, boot dependency contract, restart policy, readiness protocol, or journal retrieval command. `setup.sh` ends by telling the user to manually run `.venv/bin/python orchestrator.py`. The requirement that reboot return automatically to a listening assistant is therefore not implemented.

**Consequence:** the principal headless-appliance objective is absent.

**Blueprint obligation:** define service boundaries only after configuration, filesystem ownership, executable entry point, and dependency lifecycle are fixed. Automatic graphical login should not be enabled merely to start a headless daemon; a system service does not require user autologin.

### C-02 — “Fully offline/private” behavior conflicts with actual routing

The router sends nearly every non-simple question to `cloud_handoff`; weather, news, and jokes use network APIs. If Moonshot credentials are configured, the user’s transcribed question is transmitted to an external service without an explicit per-query privacy confirmation or visible mode indicator.

**Consequence:** the current system cannot be represented as fully offline, and the privacy boundary is unclear.

**Blueprint obligation:** make local/offline operation the authoritative default; prohibit automatic cloud fallback; explicitly classify or remove network features; test operation with network disabled.

### C-03 — Project identity and activation behavior are inconsistent

The repository name/README says GonKenLab Agent, but runtime and internal files still say Jansky; the bundled activation model is “Hey Jarvis”; `tests/test_wake_word.py` instructs “Hey Jansky”; and the “on camera” path introduces the device as Mayukh’s personal assistant.

**Consequence:** demonstrations, spoken instructions, tests, and actual detection disagree.

**Blueprint obligation:** define one product identity and one activation contract. A displayed/spoken phrase must never differ from the loaded detector model.

### C-04 — No custom “Gonken” wake-word model or reproducible training/evaluation chain exists

No training data, generation procedure, model artifact, model checksum, threshold study, license/provenance record, false-positive corpus, or Raspberry Pi acceptance test exists. The current code silently falls back to Jarvis when a configured custom file is missing.

**Consequence:** simply changing `wake_phrase` would create a nonfunctional and misleading assistant.

**Blueprint obligation:** treat training, asset provenance, deployment, detector validation, threshold calibration, and fallback policy as a separate milestone. Missing custom models must not silently claim another phrase.

### C-05 — The stated AI-lab assistant capability is absent

The supplied feasibility blueprint defines source-grounded access to local lab documents, provenance, telemetry, and a constrained answer policy. The repository has no corpus, ingestion, chunking, index, retrieval, citation/provenance, dashboard, raw-audio retention policy, or groundedness tests.

**Consequence:** current code is a generic voice assistant, not the proposed evidence-grounded AI-lab instrument.

**Blueprint obligation:** explicitly decide whether local grounding is release scope or a later project milestone; do not let the repository’s inherited prototype silently redefine the project.

### C-06 — No release-grade evidence supports “safe to rerun” or unattended readiness

There are no clean-image, second-run, interrupted-APT, interrupted-pip, interrupted-model, power-loss, boot, restart, audio-renumbering, network-late, low-disk, or upgrade tests. The installer’s final “ready” message is based on same-session software checks and may succeed with no configured audio hardware.

**Consequence:** reliability claims exceed the recorded evidence.

**Blueprint obligation:** define tiered readiness states and a repeatable Raspberry Pi acceptance/failure-injection matrix before promising one-command unattended setup.

## 8. High findings

### H-01 — Model configuration has multiple authorities

`qwen2.5:1.5b` appears as independent defaults in `setup.sh`, `config.py`, `config/config.json`, `brain/ollama_client.py`, and `tests/test_router.py`, with further documentation copies. Installer and runtime can therefore select different models.

The proposed `qwen3.5:2b-q4_K_M` tag is currently present in Ollama’s official library and reported as approximately 1.9 GB, but that fact alone does not establish acceptable Pi 5 4GB throughput, memory pressure, tool-calling behavior, or context limits.

**Required direction:** one validated runtime setting, exposed through a documented configuration contract and checked by doctor, tests, and service startup.

### H-02 — Ollama endpoint configuration is internally inconsistent

`setup.sh` checks `OLLAMA_URL`; Ollama CLI commands use their own default/environment; `scripts/doctor.py` hard-codes `127.0.0.1`; and `OllamaClient` hard-codes `localhost`. Changing `OLLAMA_URL` can cause readiness checks, provisioning, diagnostics, and runtime to address different servers.

### H-03 — Bootstrap-as-root breaks in a common path

`bootstrap.sh` explicitly supports UID 0 by omitting `sudo`, but then executes `setup.sh`, which unconditionally invokes `sudo`. Minimal root sessions without `sudo` can therefore pass bootstrap preflight and fail in setup.

### H-04 — Privilege preflight and lifetime are undefined

The installer can prompt for sudo after lengthy unprivileged work, does not establish credential lifetime, and mixes privileged package/service actions with user-owned source/model operations. There is no rule for which steps run as root versus the eventual runtime account.

### H-05 — Interrupted Piper download is not self-repairing

The download guard checks whether the `.onnx` path exists, not whether both model and JSON files are non-empty. A zero-byte model or a present model with missing/empty JSON causes later failure without redownload on rerun.

### H-06 — Dependency installation is not reproducible

`requirements.txt` uses broad ranges, has no constraints/lock file or hashes, and `setup.sh` upgrades pip/setuptools/wheel to then-current releases. A future rerun can resolve a materially different dependency graph from the one previously tested.

### H-07 — Python 3.13 ARM64 install risk remains

An audit-only binary-wheel probe for CPython 3.13/AArch64 found compatible current wheels for key packages including NumPy, Piper, and ONNX Runtime on a `manylinux_2_28` platform, but no matching pygame wheel under the same probe. Source compilation may still work, yet the installer does not preflight all of pygame’s likely build dependencies and requires pygame even when UI is disabled.

### H-08 — Optional UI dependency is treated as mandatory

Pygame is always installed and `doctor.py` fails if it cannot import pygame, even though `enable_ui` defaults to false and the desired minimum setup is headless. Optional features are not separated into dependency profiles.

### H-09 — Supply-chain integrity is weak

The installer executes `curl ... | sh` for Ollama and downloads wake-word models, Whisper source/tag, Whisper model, and Piper assets without repository-controlled SHA-256 verification. Whisper is tag-pinned but not commit-allowlisted; other downloads are mutable URLs or derived from installed package metadata.

### H-10 — Download/install stages lack transaction markers and resumable state

No step manifest records started/completed versions, checksums, or validation outcomes. Rerun behavior depends on file/directory presence and local tool behavior, not an explicit installation state machine.

### H-11 — Audio hardware is resolved only at process construction

The runtime raises during initialization if named devices are absent. It has no wait/retry loop, hotplug recovery, rescan, deterministic multiple-match policy, stable ALSA identifier preference, or degraded service state.

### H-12 — ALSA playback assumes device zero within a matching card

`_find_alsa_card_by_name` returns `plughw:<card>,0` from `aplay -l` without parsing the device number. USB devices with a nonzero playback device can be misaddressed.

### H-13 — Wake-word stream failure can loop without a healthy-state signal

Stream-open errors are printed and retried indefinitely. There is no bounded backoff, service watchdog, health state, or escalation. Exceptions during inference are not guarded by a stream `finally` block and can terminate the daemon detection thread.

### H-14 — Runtime shutdown is abrupt

After its main loop, `orchestrator.py` calls `os._exit(0)` to kill lingering daemon threads. This bypasses ordinary interpreter cleanup and is unsuitable as a long-term service-lifecycle strategy.

### H-15 — Generated speech files leak during normal assistant use

`PiperTTS.synthesize()` creates a temporary WAV. Test scripts delete it, but `Orchestrator._speak()` does not. Repeated interactions accumulate temporary files.

### H-16 — Voice power control has no safety architecture

Shutdown/reboot is not implemented. Adding a direct LLM-routed shell call would introduce accidental activation, transcription-error, prompt-injection, and privilege-escalation risks.

**Required direction:** exact allow-listed intents, local-only detection, explicit verbal or physical confirmation, cancellation window, auditable result, least-privilege helper, and tests proving ordinary conversation cannot trigger power control.

### H-17 — Upgrade, uninstall, and rollback are undefined

There is no schema/version migration, compatibility policy, package ownership manifest, uninstall path, service disable/remove procedure, model retention decision, or rollback to last known-good application version.

### H-18 — Service-account access requirements are unverified

Audio groups, GPIO permissions, cache/model ownership, shutdown authorization, working directory, environment file permissions, and access to Ollama have not been defined or tested for a non-login service account.

## 9. Medium findings

### M-01 — `.env` overrides the process environment

`Config._load_env_file()` writes every parsed key into `os.environ` without preserving an already supplied service/process value. This reverses the common precedence rule in which explicit runtime environment variables override a file.

### M-02 — `.env` is copied only once and cannot receive new template keys

Future required or recommended settings will not appear in existing installations. A configuration migration/validation approach is needed.

### M-03 — `Config.save()` can persist host-specific absolute paths

The method serializes resolved runtime state, including absolute paths and `project_root`, back into tracked `config/config.json`. Though currently unused, it can reintroduce nonportable configuration.

### M-04 — `whisper_path` is omitted from relative-path normalization

Several configured paths are resolved against the repository, but `whisper_path` is not included in that normalization list.

### M-05 — Local personality file is not used by the local model

`local_soul.md` is checked by doctor but never loaded into the Ollama routing prompt. The active prompt is hard-coded in `brain/tool_definitions.py`.

### M-06 — Router policy is inherited and inconsistent with local capability goals

The router comments assume a 1.5B model cannot answer nontrivial questions and forces cloud handoff. This policy becomes stale when the model changes and bypasses any future local grounding unless redesigned.

### M-07 — Router test contains an inconsistent expectation

`tests/test_router.py` expects “Tell me a joke” to produce `ToolType.NONE`, while fallback routing explicitly maps joke phrases to `ToolType.JOKE`. Results can also vary with live model output.

### M-08 — Files under `tests/` are interactive scripts, not an automated suite

They have no mocks/fixtures, use live Ollama/audio/models, and are not separated into unit, integration, and hardware tests. `test_audio_pipeline.py` declares test functions with positional component arguments that a pytest runner would interpret as fixtures, but no fixtures exist and pytest is not a declared dependency.

### M-09 — Wake-word test names the wrong phrase

The test instructs “Hey Jansky,” while default code loads “hey_jarvis.” It cannot meaningfully validate the configured activation contract.

### M-10 — Ollama inference smoke test validates only non-empty output

The prompt asks for exactly `OK`, but setup accepts any non-empty response. It does not validate JSON/tool support, configured runtime endpoint, or the exact model digest.

### M-11 — Audio downsampling is simple decimation

48 kHz input is converted to 16 kHz using every third sample without an anti-aliasing filter. This is fast but can reduce speech quality and should be benchmarked against a proper resampler.

### M-12 — Silence timing can reuse the same audio block

`record_until_silence()` polls every 100 ms and repeatedly examines the latest buffered block rather than consuming exactly one new block per silence count. Maximum-duration accounting is also based on polling iterations rather than captured frames.

### M-13 — Fixed 3:1 sample-rate rule is duplicated and inconsistent

AudioManager requires exactly 48 kHz → 16 kHz, while WakeWordDetector allows any integer multiple. Configuration can change one stage without a central validation of the full audio contract.

### M-14 — HTTP clients are not explicitly closed

Ollama, Moonshot, weather, news, and joke paths create clients without a coordinated lifecycle. The joke tool creates a new client per request.

### M-15 — Error handling is mostly console text

There is no structured logging, stable error code taxonomy, redaction policy, log rotation/retention plan, health summary, or command that collects a support bundle.

### M-16 — Bootstrap dirty-check omits untracked files

The guard checks staged and unstaged tracked changes but not untracked files. Pull/switch can still fail when an untracked path conflicts with the target branch.

## 10. Low findings

### L-01 — README duplicates the live-demo section

The same two links appear twice near the beginning.

### L-02 — README claims an MIT license but no license file is tracked

A real license file and asset/model license inventory are needed before release.

### L-03 — Historical PRD is substantially stale

`PRD.md` describes an 8GB, display-oriented Jansky assistant and embeds obsolete file paths, scripts, models, setup commands, and service examples. It is valuable as provenance but dangerous as active instructions.

### L-04 — Product naming remains in package comments and UI title

Several `__init__.py` comments, UI caption, prompts, and soul files retain Jansky.

### L-05 — Broad `except:` clauses obscure causes

Bare exception handling appears in UI cleanup and Ollama availability checks.

### L-06 — `speaking_rate` and streaming settings are unused

`PiperTTS.speaking_rate` is stored but not applied, while `enable_streaming_tts` exists in configuration without an implemented runtime path.

### L-07 — The optional on-camera response is unrelated and hard-coded

The response is not suitable for GonKenLab Agent and embeds a former owner/use case.

## 11. File-by-file inspection ledger

### 11.1 Root and configuration

| File | Inspection result |
|---|---|
| `.env.example` | API keys and AIRHUG overrides only; no model/endpoint/offline-mode setting. |
| `.gitignore` | Covers `.env`, venvs, Whisper tree, Piper voices, root wake models, temp/WAV files; no policy for indexes/logs/service-generated state yet. |
| `PRD.md` | Historical upstream implementation document; materially stale and internally inconsistent with current project. |
| `README.md` | Useful current manual setup overview but duplicates demos, promises more than tested, and remains Qwen 2.5/Jarvis-oriented. |
| `bootstrap.sh` | Clean clone/update entry point; issues H-03, M-16, and no pin/transaction/service installation. |
| `setup.sh` | Substantial prototype installer; monolithic, partly idempotent, no app service, several state/config/supply-chain gaps. |
| `requirements.txt` | Broad runtime ranges; no lock/constraints, profiles, test dependencies, or platform declaration. |
| `config.py` | Repository-relative dataclass config; precedence, portability, validation, and authority issues. |
| `config/config.json` | Active runtime overrides include old model/phrase/location. |
| `config/local_soul.md` | One-line Jansky prompt; not consumed by local runtime. |
| `config/cloud_soul.md` | Jansky/Moonshot personality; conflicts with default-offline goal. |

### 11.2 Audio and senses

| File | Inspection result |
|---|---|
| `audio/__init__.py` | Eagerly imports all audio engines; retains Jansky label. |
| `audio/audio_manager.py` | Explicit named device resolution and fallback playback are useful; lacks resilient/hotplug selection and quality resampling. |
| `audio/stt_engine.py` | Good binary/model validation and subprocess timeout; target path and performance parameters are not centrally validated. |
| `audio/tts_engine.py` | Uses maintained Python Piper interface; caller-owned temp-file contract is unsafe and speaking-rate option is ineffective. |
| `senses/__init__.py` | Eager import; retains Jansky label. |
| `senses/wake_word_detector.py` | ONNX-only detector and pause/resume queue; hard fallback, lifecycle, retry, and calibration problems. |

### 11.3 Brain and tools

| File | Inspection result |
|---|---|
| `brain/__init__.py` | Eagerly imports HTTP-dependent runtime; retains Jansky label. |
| `brain/ollama_client.py` | Basic Ollama chat/tool wrapper; old default, fixed endpoint, broad exception, no close/readiness/digest contract. |
| `brain/router.py` | Clear prototype routing structure; cloud-first policy for nontrivial queries and no grounding. |
| `brain/tool_definitions.py` | Tool schemas are understandable; prompt and descriptions remain Jansky/Qwen 2.5/cloud-oriented. |
| `brain/cloud_client.py` | Optional Moonshot client; direct privacy-boundary conflict under automatic handoff. |
| `brain/tools/__init__.py` | Only exports time/weather despite other modules; retains Jansky label. |
| `brain/tools/time_tool.py` | Local read-only function; timezone is implicit system local time. |
| `brain/tools/system_tool.py` | Local read-only health information; appropriate basis for allow-listed diagnostics. |
| `brain/tools/weather_tool.py` | Network/API-key dependent; error content can be spoken directly. |
| `brain/tools/news_tool.py` | Network/API-key dependent and US-default; not an offline feature. |
| `brain/tools/joke_tool.py` | Network dependent despite no API key; new client per request. |

### 11.4 Orchestration and UI

| File | Inspection result |
|---|---|
| `orchestrator.py` | Working prototype composition; identity mismatch, startup fragility, temp leaks, abrupt process exit, no health/state/service contract. |
| `ui/__init__.py` | Eager pygame import can make optional UI less optional. |
| `ui/ui_manager.py` | Useful optional display prototype; hard-coded Wayland/UID 1000 assumptions contradict general headless service deployment. |

### 11.5 Diagnostics and tests

| File | Inspection result |
|---|---|
| `scripts/doctor.py` | Valuable software/hardware distinction; fixed Ollama endpoint and mandatory optional dependencies; no service/config consistency checks. |
| `scripts/smoke_test.py` | Validates Whisper/Piper and available audio; imports audio dependency at module load and cannot represent installed-but-hardware-blocked readiness distinctly. |
| `tests/test_audio_pipeline.py` | Useful manual hardware exercise; not pytest-compatible as written and requires prepared environment/hardware. |
| `tests/test_router.py` | Live-model script with stale model and inconsistent joke expectation. |
| `tests/test_wake_word.py` | Interactive live-audio script that instructs the wrong phrase. |

### 11.6 Assets

| Files | Inspection result |
|---|---|
| `assets/face/*.png` (9 files) | Structurally valid RGBA PNGs; dimensions vary from 269×205 to 296×236; provenance/license not documented. |
| `assets/fillers/*.wav` (5 files) | Valid mono 16-bit 22,050 Hz WAVs, approximately 0.50–1.41 seconds; provenance/license not documented. |

## 12. Requirements reconciliation

### 12.1 Requirements supported by both supplied sources

- Raspberry Pi 5, 4GB target.
- Local Whisper, local small LLM, and local Piper.
- Headless operation and automatic boot recovery.
- Privacy as an engineering requirement.
- Clear installation/onboarding documentation.
- Repeatable tests and measurable readiness.
- Restricted, explicit system tools instead of arbitrary shell execution.

### 12.2 Requirements that conflict or require a staged decision

| Topic | Requirements note | Feasibility blueprint | Audit disposition |
|---|---|---|---|
| Primary interaction | custom Gonken wake word, voice-only operation | push-to-talk first; wake word later | Blueprint should make both explicit modes: reliable physical/manual recovery path first, then evaluated wake-word mode. Final default needs acceptance evidence. |
| Cloud behavior | fully offline/local objective | fully local MVP | Current automatic cloud handoff must not remain the default. |
| Display | current code retains optional LCD UI | local browser dashboard; no purchased display | Keep UI optional; do not let pygame block headless install. Decide dashboard scope in blueprint. |
| Grounding/RAG | document-guided assistant mentioned | central project distinction | Treat as intended product capability, with milestone timing decided explicitly. |
| Voice power control | requested | side-effectful tools require confirmation | May be implemented only with a safety/privilege acceptance contract. |
| Autologin | suggested for convenience | systemd headless deployment | Do not require autologin for daemon startup; document SSH/admin access separately. |

### 12.3 Provisional governing principles for the blueprint

These are constraints derived from clear requirements and verified risks, not a detailed implementation plan:

1. **Repository is the session memory.** Every milestone updates status, tests, and decisions in the same commit as code.
2. **Offline is the default privacy boundary.** Network features cannot silently receive transcripts.
3. **One configuration authority per setting.** Installer, doctor, service, tests, and runtime consume the same resolved configuration.
4. **Separate install time from runtime.** The assistant service diagnoses and reports dependency/hardware states; it does not install packages or mutate source at boot.
5. **Separate immutable and mutable state.** Code, configuration/secrets, models/indexes, caches, and logs need explicit ownership and upgrade policy.
6. **No readiness claim without its evidence tier.** Host static, container/architecture, Pi software, connected-hardware, reboot, and failure-injection results remain distinct.
7. **Side effects require deterministic policy.** The LLM cannot invent or directly execute shell commands; shutdown/reboot require exact allow-listing and confirmation.
8. **Idempotency is tested behavior.** File existence alone is not proof of a valid completed step.
9. **A missing peripheral is an operational state, not an installation catastrophe.** The service should remain diagnosable and retry safely.
10. **No automatic login solely for service startup.** Headless system services must be independent of an interactive graphical/login session.

## 13. Recommended project-control architecture

The user’s proposal is sound with one refinement: preserve the audit as an immutable baseline and use four rolling control documents rather than making the blueprint carry status/history.

| Document | Lifecycle | Function |
|---|---|---|
| `REPOSITORY_AUDIT.md` | frozen except corrections | What was inspected and what the baseline actually contained |
| `MASTER_BLUEPRINT.md` | versioned contract; created next | Milestones, file-level actions, failure modes, validation, rollback, acceptance |
| `IMPLEMENTATION_STATUS.md` | updated every milestone | Complete/in-progress/pending/known issues/last verified baseline/exact next action |
| `TEST_MATRIX.md` | updated with every validation | Test ID, tier, command/procedure, environment, result, evidence, blockers |
| `DECISIONS.md` | append-oriented | Accepted/rejected architecture decisions and reasons |

A separate session-handoff file would duplicate `IMPLEMENTATION_STATUS.md` and is not recommended unless automation later requires a strict machine-only schema.

## 14. Recommended milestone workflow

The earlier 22-phase sketch is directionally complete but too granular before architecture decisions exist. A better initial structure is:

1. **M0 — Audit and control plane** (this checkpoint).
2. **M1 — Master blueprint and adversarial review.** Resolve product boundary, packaging layout, modes, privileges, recovery, and acceptance tiers.
3. **M2 — Packaging/configuration/state foundation.** Establish authoritative settings, entry points, filesystem ownership, dependency profiles, and migration rules.
4. **M3 — Idempotent provisioning.** System packages, Python environment, verified downloads, Ollama/model, Whisper/Piper, resumable step validation.
5. **M4 — Runtime reliability.** State machine, lifecycle, logs, signal handling, audio discovery/retry, degraded states.
6. **M5 — Interaction and privacy modes.** Push-to-talk/manual recovery path, custom Gonken wake word, recording indication, offline enforcement.
7. **M6 — Headless service and privileged operations.** systemd, boot ordering, service account, watchdog/restart, safe shutdown/reboot.
8. **M7 — Grounding and observability.** Local corpus/retrieval/provenance/telemetry/dashboard if confirmed in release scope.
9. **M8 — Diagnostics, upgrades, recovery, uninstall.** Doctor/support bundle, migrations, interrupted install, rollback, clean removal.
10. **M9 — Verification and release candidate.** Automated tests, Pi clean-image runs, reboot/failure injection, security review, documentation, portable Git handoff.

M1 may split milestones further. Subsequent sessions should implement only a coherent acceptance-bounded slice, not necessarily an entire broad milestone in one conversation.

## 15. Audit acceptance result

| Criterion | Result |
|---|---|
| Current remote baseline identified | PASS |
| Clean development branch created | PASS |
| Every tracked file inventoried and inspected | PASS |
| Git history inspected | PASS |
| Requirements sources reconciled | PASS |
| Application code unchanged | PASS |
| Static syntax/config/repository checks recorded | PASS |
| Raspberry Pi runtime/hardware claims clearly bounded | PASS |
| Known problems assigned stable IDs | PASS |
| Exact next action recorded | PASS |

## 16. Exact next action

Create `docs/development/MASTER_BLUEPRINT.md` for **M1 — Master blueprint and adversarial review**. It must convert every Critical and High finding above into one or more implementation items containing:

- target files/components;
- preconditions and dependencies;
- exact actions;
- privilege/ownership rules;
- success and failure states;
- static, automated, Pi, hardware, reboot, and failure-injection tests as applicable;
- rollback/uninstall implications;
- acceptance criteria;
- status/test/decision document updates;
- a commit boundary.

No runtime code should be changed until that blueprint has been reviewed for unverified assumptions and accepted findings have been incorporated.

## 17. External verification references

- [Official Ollama entry for qwen3.5:2b-q4_K_M](https://ollama.com/library/qwen3.5:2b-q4_K_M)
- [Official Ollama Qwen 3.5 tag listing](https://ollama.com/library/qwen3.5/tags)
- [whisper.cpp release b4938](https://github.com/ggml-org/whisper.cpp/releases/tag/b4938)
- [openWakeWord 0.6.0 package metadata](https://pypi.org/project/openwakeword/0.6.0/)
- [Current Piper package metadata](https://pypi.org/project/piper-tts/)
