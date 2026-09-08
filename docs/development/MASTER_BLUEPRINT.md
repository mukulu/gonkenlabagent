# GonKenLab Agent Implementation Master Blueprint

**Blueprint revision:** 1.0-draft

**Prepared:** 2026-09-08 UTC

**Branch:** `dev/bootstrap-rearchitecture`

**Source audit:** `REPOSITORY_AUDIT.md` at checkpoint `checkpoint/audit`

**Review state:** implementation-grade draft; adversarial architecture review still required

**Implementation authorization:** runtime work must not begin until M1B review findings are adjudicated and this document is revised to an accepted version

## 1. Purpose and authority

This blueprint is the implementation contract for turning the current GonKenLab Agent prototype into a reproducible, privacy-sensitive, fully local Raspberry Pi 5 AI-lab assistant. It translates the repository audit and supplied project requirements into ordered, file-level work with explicit failure behavior, validation, rollback, and commit boundaries.

Where this blueprint conflicts with the historical `PRD.md`, this blueprint governs development. The historical PRD is retained only as provenance until the release-documentation milestone. Where a future implementation discovers evidence that makes an item unsafe or infeasible, development must pause that item, record the evidence in `IMPLEMENTATION_STATUS.md` and `DECISIONS.md`, revise this blueprint, and commit the revision before continuing.

The blueprint does not claim that every technical choice is already proven on Raspberry Pi hardware. Unverified choices are marked with gates that require target evidence.

## 2. Product definition

### 2.1 What is being built

**GonKenLab Agent** is a headless Raspberry Pi 5 4GB appliance that provides spoken, source-grounded access to a bounded corpus of GonKen AI-lab documentation. Speech-to-text, document retrieval, language-model inference, text-to-speech, and normal system tools run locally. It starts automatically after boot, remains diagnosable when peripherals are absent, and requires no interactive shell activation during normal use.

The primary research and educational contribution is not merely running a chatbot on a Raspberry Pi. It is making a constrained edge-AI assistant observable and accountable through local provenance, measurable performance, explicit privacy states, and restricted actions.

### 2.2 Required release capabilities

The release candidate must provide:

1. repeatable installation on the declared Raspberry Pi OS image;
2. Qwen 3.5 2B Q4_K_M through local Ollama, subject to the model acceptance gate;
3. local Whisper speech recognition;
4. local Piper speech synthesis;
5. a physical push-to-talk path that works without wake-word recognition;
6. an evaluated “Hey Gonken” wake-word mode that cannot be enabled as the advertised default until its acceptance gate passes;
7. a bounded local Markdown/text corpus with deterministic lexical retrieval;
8. concise answers that identify supporting sources or explicitly report insufficient support;
9. local telemetry and provenance with privacy-preserving defaults;
10. a minimal read-only dashboard, loopback-bound by default;
11. a systemd-managed runtime independent of user login;
12. clear degraded states and automatic retry when audio/Ollama are temporarily unavailable;
13. safe, exact, two-stage voice shutdown/reboot when explicitly enabled;
14. doctor, install verification, update, rollback, recovery, and uninstall procedures;
15. automated unit/integration tests plus recorded Pi hardware, reboot, and failure-injection evidence.

### 2.3 Explicit non-goals for the first release candidate

- arbitrary general-purpose cloud AI fallback;
- weather, news, or joke APIs that require internet access;
- arbitrary shell execution by the language model;
- camera or multimodal image input;
- a purchased LCD or mandatory pygame UI;
- Bluetooth as the primary supported audio path;
- embedding/vector-database retrieval;
- unrestricted LAN administration endpoints;
- automatic self-updating at boot;
- automatic graphical or console login;
- AI-controlled safety-critical fan or actuator logic.

### 2.4 Meaning of “fully offline”

“Fully offline” governs **normal runtime after provisioning**. Initial installation, dependency/model download, explicit upgrade, and optional corpus transfer may require internet or LAN access. After provisioning:

- no transcript, prompt, answer, audio, retrieved content, or telemetry is sent to an internet service;
- Ollama binds to loopback and runs with cloud features disabled;
- the assistant remains useful when the internet route is removed;
- an optional local dashboard may use the local network only after explicit configuration;
- update checks do not run automatically.

## 3. Non-negotiable engineering invariants

| ID | Invariant | Enforcement evidence |
|---|---|---|
| INV-01 | Installer, runtime, doctor, service, and tests resolve one effective chat model. | config unit tests; doctor model/digest check; install smoke test |
| INV-02 | Normal runtime performs no unapproved outbound internet request. | network-denial integration test; offline packet/connection audit |
| INV-03 | The advertised wake phrase equals the validated loaded wake model. | startup/config validation; mismatch unit test |
| INV-04 | Raw utterance audio is temporary and deleted by default on success, error, cancellation, and signal. | lifecycle/failure tests; runtime-directory inspection |
| INV-05 | The LLM never supplies a shell command for direct execution. | code review; no-shell subprocess policy; adversarial tests |
| INV-06 | Power actions require deterministic intent and confirmation outside LLM free-form output. | power state-machine tests; sudoers validation |
| INV-07 | Headless startup does not depend on autologin, shell profiles, or venv activation. | systemd/reboot test |
| INV-08 | Repeating install after success converges without corrupting configuration or state. | second/third-run comparison |
| INV-09 | A partial or corrupt downloaded artifact is never treated as installed. | checksum and interruption tests |
| INV-10 | Missing audio/GPIO produces a visible degraded state, not an ambiguous “ready” state or installer dead end. | doctor exit codes; service hotplug tests |
| INV-11 | Source material is treated as untrusted data, not executable/system instruction. | prompt-injection retrieval tests |
| INV-12 | Every grounded answer exposes valid source identifiers; unsupported answers say so. | retrieval/answer contract tests |
| INV-13 | Each milestone changes status/tests/decisions in the same commit as implementation. | pre-commit milestone checklist |
| INV-14 | Readiness claims identify their evidence tier. | test matrix and release checklist |

## 4. Supported platform and hardware contract

### 4.1 Primary supported target

- Raspberry Pi 5 with 4GB RAM;
- Raspberry Pi OS Lite 64-bit based on Debian 13;
- AArch64 kernel and userspace;
- distribution Python 3.13;
- systemd as PID 1;
- 64GB A2-class microSD or better;
- appropriate Raspberry Pi 5 active cooling;
- adequate 5V/5A-class power supply;
- USB audio device, initially validated against AIRHUG USB audio;
- GPIO push button and dedicated recording LED for full physical acceptance.

The installer must record `/etc/os-release`, architecture, Python version, Pi model, free storage, RAM, and systemd presence. Unsupported platforms fail before mutation unless `--development-host` is explicitly selected for non-service desktop testing.

### 4.2 Development host

Python unit tests and text/file-based integration tests must run on Linux x86_64 with Python 3.12/3.13 without Raspberry Pi hardware. Host success never substitutes for Pi evidence.

### 4.3 Audio support boundary

USB audio is the supported release path. Bluetooth may be documented as experimental only after separate reconnect/reboot testing. Device numeric indexes are never authoritative across reboot.

## 5. Target repository structure

M2 will migrate incrementally toward this structure while retaining compatibility wrappers until their callers are removed:

```text
gonkenlabagent/
├── pyproject.toml
├── README.md
├── LICENSE
├── config/
│   └── defaults.toml
├── src/gonken_agent/
│   ├── cli.py
│   ├── config.py
│   ├── runtime.py
│   ├── state.py
│   ├── health.py
│   ├── logging_config.py
│   ├── audio/
│   │   ├── devices.py
│   │   ├── capture.py
│   │   ├── resample.py
│   │   ├── stt.py
│   │   └── tts.py
│   ├── interaction/
│   │   ├── push_to_talk.py
│   │   ├── wake_word.py
│   │   └── power_intent.py
│   ├── llm/
│   │   ├── ollama.py
│   │   └── prompts.py
│   ├── retrieval/
│   │   ├── corpus.py
│   │   ├── index.py
│   │   └── bm25.py
│   ├── tools/
│   │   ├── registry.py
│   │   ├── system_info.py
│   │   └── power.py
│   ├── telemetry.py
│   └── dashboard.py
├── packaging/
│   ├── artifacts.toml
│   ├── systemd/gonken-agent.service
│   ├── systemd/ollama.service.d/gonken-local.conf
│   ├── sudoers/gonken-agent-power
│   └── tmpfiles.d/gonken-agent.conf
├── requirements/
│   ├── pi-py313.lock
│   └── dev-py312.lock
├── scripts/
│   ├── lib/common.sh
│   ├── install.sh
│   ├── install-system.sh
│   ├── install-python.sh
│   ├── install-ollama.sh
│   ├── install-models.sh
│   ├── install-service.sh
│   ├── update.sh
│   ├── rollback.sh
│   ├── uninstall.sh
│   └── ci.sh
├── wakeword/
│   ├── README.md
│   ├── hey_gonken.yaml
│   └── MODEL_CARD.md
├── corpus/README.md
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── failure/
│   └── hardware/
└── docs/development/
```

The exact migration is allowed to preserve current filenames temporarily. No “after patch,” “fixed,” or version-suffix production filenames are permitted.

## 6. Installed-system architecture

### 6.1 Filesystem layout

| Path | Owner/mode intent | Purpose |
|---|---|---|
| `/opt/gonken-agent/releases/<git-sha>/` | `root:root`, not service-writable | immutable application source and release-specific venv |
| `/opt/gonken-agent/current` | root-owned atomic symlink | active validated release |
| `/etc/opt/gonken-agent/config.toml` | `root:gonken-agent`, `0640` | site configuration overrides |
| `/etc/opt/gonken-agent/environment` | `root:gonken-agent`, `0640` | explicit service environment; normally no cloud secrets |
| `/var/opt/gonken-agent/models/` | root-managed, service-readable | Whisper, Piper, and accepted wake-word artifacts |
| `/var/opt/gonken-agent/corpus/` | administrator-managed, service-readable | bounded lab documents |
| `/var/opt/gonken-agent/index/` | service-writable | derived lexical index; reproducible from corpus |
| `/var/opt/gonken-agent/telemetry/` | service-writable, private | content-free performance telemetry |
| `/var/opt/gonken-agent/interactions/` | disabled/uncreated by default | opt-in research records only |
| `/var/opt/gonken-agent/install/` | root-writable | advisory install-state/version manifest |
| `/var/cache/gonken-agent/` | service-writable | disposable cache |
| `/run/gonken-agent/` | tmpfs/runtime, service-writable | temporary WAVs, health/status socket/files |
| journald | system managed | operational logs with retention controlled by OS |

This follows the separation between static add-on software, host configuration, variable data, cache, and runtime state. `packaging/tmpfiles.d/gonken-agent.conf` or installer-created directories must encode ownership explicitly.

### 6.2 Accounts and process boundaries

| Process | Account | Network | Writable locations | Privilege |
|---|---|---|---|---|
| installer/update/rollback | root after explicit sudo preflight | internet during explicit operation | install/config/state trees | system mutation |
| `ollama.service` | `ollama` | loopback server; internet only during explicit pull | Ollama model store | no login |
| `gonken-agent.service` | `gonken-agent` system user, no shell | loopback; optional explicit dashboard bind | `/run`, index, cache, telemetry | no general sudo |
| power helper command | invoked through exact sudoers allow-list | none | none | only poweroff/reboot |
| developer process | invoking user | as explicitly configured | checkout-local dev state | no installed service mutation |

The runtime never owns its release directory and cannot replace code, dependency locks, prompts, or model manifests.

### 6.3 Release installation and rollback

Each installed release is keyed by full Git commit SHA. The installer builds the venv inside the final release directory, validates it, then atomically switches `current`. It retains the active and one previous validated release. A failed new release leaves the existing symlink untouched. Rollback switches to a previously recorded validated release, reruns config compatibility checks, restarts the service, and verifies health.

## 7. Configuration contract

### 7.1 Single authority and precedence

1. packaged `config/defaults.toml` contains the only source-controlled defaults;
2. `/etc/opt/gonken-agent/config.toml` contains administrator overrides;
3. explicit `GONKEN_*` process/service environment overrides are last;
4. CLI flags override only the specific one-shot command and are not persisted;
5. legacy `config/config.json` and checkout `.env` are read only by a one-time migration command, never simultaneously with production configuration.

Python code must not repeat fallback literals for model, endpoint, phrase, paths, or hardware names. The installer obtains the model through the same config loader/CLI used by runtime and doctor.

### 7.2 Initial schema

```toml
schema_version = 1

[assistant]
name = "GonKenLab Agent"
language = "en"

[runtime]
mode = "offline"
interaction_mode = "push_to_talk"

[llm]
provider = "ollama"
base_url = "http://127.0.0.1:11434"
model = "qwen3.5:2b-q4_K_M"
context_tokens = 2048
max_output_tokens = 160
keep_alive = "5m"

[audio]
input_match = "AIRHUG"
output_match = "AIRHUG"
capture_rate = 48000
processing_rate = 16000

[stt]
model = "base.en-q5_1"
threads = 4

[tts]
voice = "en_GB-semaine-medium"

[interaction]
wake_phrase = "Hey Gonken"
wake_model = ""
wake_threshold = 0.5
wake_word_enabled = false
push_to_talk_gpio = 17
recording_led_gpio = 27

[retrieval]
enabled = true
top_k = 3
minimum_score = 0.0

[privacy]
raw_audio_retention = "delete"
interaction_logging = false
telemetry_content = false

[dashboard]
enabled = true
bind = "127.0.0.1"
port = 8080

[power]
voice_control_enabled = false
confirmation_timeout_seconds = 10
```

Exact values may change after adversarial review, but the authority/validation model may not be weakened without a recorded decision.

### 7.3 Validation rules

- unknown keys are errors, not silently ignored;
- invalid enum, port, URL scheme, path escape, sample-rate relation, GPIO conflict, threshold, context, or retention value prevents readiness;
- `runtime.mode=offline` rejects non-loopback LLM endpoints and all cloud/network tool registrations;
- wake-word enablement requires existing artifact, manifest checksum, matching phrase/model-card identifier, and accepted status;
- GPIO input and recording LED cannot share a pin;
- site config is never rewritten by ordinary runtime;
- `gonken-agent config show --effective` redacts sensitive values and records each setting’s source;
- config migration makes a timestamped backup and is repeatable.

## 8. Dependency and artifact policy

### 8.1 Python dependencies

- `pyproject.toml` defines project metadata, entry points, and human-maintained compatible ranges.
- Target installation uses `requirements/pi-py313.lock` with exact versions and hashes.
- Host development uses a separate exact `requirements/dev-py312.lock`.
- Headless core excludes pygame; UI becomes an optional dependency group.
- Test tools are separate from runtime dependencies.
- `pip check`, import checks, license inventory, and a deterministic smoke suite run before release activation.
- The openWakeWord `--no-deps` workaround remains isolated and documented until upstream metadata is compatible; every manually supplied dependency and wheel hash is explicit.

### 8.2 Non-Python artifacts

`packaging/artifacts.toml` records, for each artifact:

- logical name and version;
- canonical source URL;
- target architecture;
- SHA-256;
- expected size range;
- license and redistribution status;
- install destination;
- validation command;
- provenance date.

Downloads use a same-filesystem `.partial` path, timeout/retry with bounded backoff, checksum and size validation, then atomic rename. Existing final files are revalidated; zero-byte, wrong-size, or wrong-checksum files are quarantined and replaced.

Whisper source is pinned to an immutable commit corresponding to the accepted release. The Ollama binary version is pinned for the supported image. The Ollama model tag and full local digest are both recorded after controlled validation; tag-only presence is insufficient for the release gate.

### 8.3 Licensing gate

Before redistribution, record licenses/provenance for source code, face PNGs, filler WAVs, Piper voice, Whisper model, Qwen model, openWakeWord feature models, negative datasets, synthetic voices, and custom wake model. An artifact with unclear or incompatible redistribution rights is downloaded by the installer from its source rather than committed or bundled. README cannot claim MIT coverage over third-party assets without qualification.

## 9. Runtime architecture

### 9.1 State machine

```text
BOOTING -> WAITING_DEPENDENCIES -> IDLE
IDLE -> WAKE_MONITORING | RECORDING
WAKE_MONITORING -> RECORDING
RECORDING -> TRANSCRIBING -> RETRIEVING -> GENERATING -> SPEAKING -> IDLE
ANY_ACTIVE -> DEGRADED | STOPPING
DEGRADED -> WAITING_DEPENDENCIES -> IDLE
GENERATING -> AWAITING_POWER_CONFIRMATION -> POWER_ACTION | IDLE
```

State transitions are centralized and tested. Audio callbacks enqueue bounded frames/events only; they do not run STT, retrieval, LLM, TTS, or power logic. One coordinator owns interaction execution so overlapping activations cannot create concurrent model/audio pipelines on 4GB RAM.

### 9.2 Health/readiness

Health contains independent component states: config, filesystem, Ollama server, selected model, Whisper, Piper, input audio, output audio, GPIO, retrieval index, dashboard, and privacy mode. Overall states are:

- `READY`: configured interaction path and required software pass;
- `DEGRADED`: service is alive and diagnosable but a recoverable peripheral/dependency is unavailable;
- `FAILED`: configuration, artifact integrity, or unrecoverable software contract failed;
- `MAINTENANCE`: explicit install/update/index/benchmark operation.

The CLI exposes human and JSON health. Exit codes are fixed: `0 READY`, `2 DEGRADED`, `1 FAILED`, `3 unsupported invocation/platform`.

### 9.3 Graceful process lifecycle

SIGTERM/SIGINT stop new activation, close input streams, cancel bounded work, delete temporary audio, finish or stop playback within the configured timeout, close HTTP/audio resources, publish final status, and exit normally. `os._exit` is prohibited. Temporary artifacts use context managers rooted in `/run/gonken-agent`.

### 9.4 Audio behavior

- enumerate inputs/outputs with channel and supported-rate metadata;
- prefer a configured stable ALSA card/device identity or unique name match;
- treat zero matches as degraded and multiple matches as ambiguous unless an explicit selector resolves them;
- re-enumerate before stream open and after device errors;
- retry with capped exponential backoff and periodic health updates;
- use captured frame counts for duration/silence logic;
- use anti-aliased resampling such as `scipy.signal.resample_poly`;
- bound queues and drop/report overflow rather than grow memory without limit;
- mute/close command capture during TTS and test feedback behavior;
- validate actual audible playback manually; a completed subprocess alone is not proof of sound.

### 9.5 Local LLM behavior

- connect only to the effective loopback Ollama endpoint in offline mode;
- set small, explicit context/output limits suitable for 4GB RAM;
- serialize inference requests;
- distinguish server unavailable, model absent, timeout, overload, malformed response, and cancellation;
- report actual model name/digest in health and telemetry;
- never route a query to cloud automatically;
- constrain spoken responses and remove Markdown formatting before TTS;
- keep model/tool routing deterministic where a local function can answer directly.

## 10. Interaction, grounding, and governance contracts

### 10.1 Push-to-talk

Push-to-talk is the mandatory reliable and privacy-forward path. Hold GPIO17 to capture; release to stop. GPIO27 red LED is on exactly while utterance audio is being captured. A keyboard/CLI trigger is allowed only for development/diagnostics.

### 10.2 Wake-word mode

Wake-word mode is a required evaluated feature but is disabled by default until all acceptance criteria pass. When enabled, short frames are processed locally and not written to disk. Documentation must explain that the microphone is continuously sampled in memory for wake detection even though utterance recording begins only after activation.

The “Hey Gonken” model requires:

- a reproducible training configuration and pinned training environment;
- model card with phrase, version, framework, checksum, data sources/licenses, limitations, and evaluation;
- several thousand generated positive examples or justified equivalent;
- large, representative negative material with lawful provenance;
- held-out positive recordings across intended speakers/accents/noise;
- hours of representative non-trigger audio;
- threshold sweep and selected operating point;
- target false-reject rate below 5% and false-accept rate below 0.5/hour as an initial gate, reported with sample counts and limitations;
- on-device real-time-factor and idle CPU/RAM measurements;
- no silent fallback to Jarvis or another phrase.

If the gate fails, push-to-talk remains the supported default and the failure is documented; thresholds are not weakened merely to close the milestone.

### 10.3 Retrieval and answer grounding

The first release supports UTF-8 `.md` and `.txt` corpus files. PDF extraction is a separate explicit ingestion step, not implicit parsing inside runtime. Corpus ingestion:

1. rejects files outside the configured corpus root and unsafe symlink traversal;
2. enforces size/count limits;
3. normalizes text without executing embedded content;
4. chunks by headings/paragraph boundaries with controlled overlap;
5. assigns `relative_path#heading:chunk_number@content_hash` identifiers;
6. builds a deterministic BM25-style lexical index;
7. writes the new index atomically with source and configuration hashes.

The prompt delimits retrieved text as untrusted source material. Documentation questions are answered only from supplied chunks. If support is insufficient, the assistant states that the available lab sources do not contain the answer. System-health questions use allow-listed local functions. Casual greetings may receive a local ungrounded response but must not be presented as sourced lab knowledge.

### 10.4 Telemetry and privacy

Default telemetry records timestamp, component timings, generated-token counts, model/digest, CPU temperature, RAM, throttling state, audio duration, health state, and source IDs—not transcript, answer text, source text, or raw audio. Interaction-content logging is opt-in research mode with a visible configuration/health warning and a documented retention/deletion procedure.

Raw audio lives only in `/run/gonken-agent`, is deleted after STT by default, and is removed on all failure/signal paths. “Retain audio” is permitted only in explicit benchmark mode with informed handling and a separate directory.

### 10.5 Dashboard

The dashboard is read-only and binds `127.0.0.1` by default. It shows health, current state, model/digest, timings, temperatures, memory, retrieved source IDs/scores, and privacy/logging mode. It exposes no shell, install, update, power, corpus-write, or configuration-write endpoint.

LAN binding requires explicit administrator configuration, documentation of exposure, and an authentication/access-control decision during adversarial review. Until that decision is implemented, loopback access through SSH forwarding is the supported mode.

### 10.6 Power actions

Power intent is parsed from normalized STT text by exact finite-state rules after an ordinary authenticated interaction trigger; the LLM does not decide it. Proposed phrases are:

- request: “shut down Gonken” or “reboot Gonken”;
- confirmation within 10 seconds: “confirm shutdown” or “confirm reboot”;
- cancellation: “cancel.”

The second phrase must match the pending action. Timeouts cancel. Any additional material or low-confidence/empty transcription cancels safely. The service invokes only a root-owned wrapper or exact `sudo -n /usr/bin/systemctl poweroff|reboot` allow-list, never `shell=True`. Feature default is disabled until T6 tests pass. A physical Pi 5 power-button shutdown remains documented as recovery.

## 11. systemd service contract

`packaging/systemd/gonken-agent.service` must implement, subject to target verification:

- `User=gonken-agent`, `Group=gonken-agent`;
- no interactive login or shell-profile dependency;
- dependency on local `ollama.service` without requiring internet availability;
- `Type=notify` with a small no-extra-dependency `NOTIFY_SOCKET` implementation, or documented revision if target review rejects it;
- `Restart=on-failure` with bounded restart interval/start limit;
- `TimeoutStopSec` sufficient for audio cleanup but bounded;
- watchdog only after reliable heartbeat behavior is implemented;
- `WorkingDirectory=/opt/gonken-agent/current`;
- `ExecStart=/opt/gonken-agent/current/.venv/bin/gonken-agent run`;
- optional `EnvironmentFile=-/etc/opt/gonken-agent/environment`;
- `RuntimeDirectory=gonken-agent`, `CacheDirectory=gonken-agent` where compatible with chosen FHS paths;
- `UMask=0027`;
- `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectHome=true`, `ProtectSystem=strict`, restricted writable paths, and a minimal address-family set;
- audio/GPIO device access explicitly allowed without using `PrivateDevices=true` blindly;
- no broad Linux capabilities and no general sudo access;
- status/log commands documented through `systemctl` and `journalctl`.

The Ollama drop-in binds loopback, enables `OLLAMA_NO_CLOUD=1`, constrains parallelism/model count for 4GB, and records the model storage location/ownership. It must not expose port 11434 to the LAN.

## 12. Installer, recovery, and operations contract

### 12.1 Bootstrap

`bootstrap.sh` remains small. It:

1. refuses unsupported OS/architecture before system mutation;
2. distinguishes root from non-root and performs one up-front sudo validation;
3. installs only bootstrap prerequisites;
4. clones/fetches the requested branch/ref into an explicit staging directory;
5. detects tracked and untracked conflicts for an existing development checkout;
6. records source URL/ref/commit;
7. invokes `scripts/install.sh --source <verified-tree>`;
8. never enables autologin.

The README supports two onboarding paths:

- Raspberry Pi Imager on another computer with hostname, user, network, and SSH preconfigured;
- official Raspberry Pi Network Install using wired Ethernet, monitor, keyboard, and Shift where required.

### 12.2 Step protocol

Every install step implements:

- stable step ID and version;
- precondition probe;
- planned mutation list;
- idempotent action;
- postcondition validation;
- advisory atomic state record;
- actionable failure message and relevant log path;
- rerun behavior;
- rollback implication.

State records never override actual probes. A state saying “complete” with a missing/bad artifact causes repair.

### 12.3 Readiness summary

Installer completion reports one of:

- `READY`: software, model, service, and configured connected hardware pass;
- `SOFTWARE_READY_HARDWARE_DEGRADED`: service installed and retrying, but one or more peripherals are missing/ambiguous;
- `FAILED`: required software/config/integrity/service validation failed.

Only `READY` prints that the assistant is ready for interaction. Degraded output gives exact discovery/config/doctor commands and still verifies that the service remains inspectable.

### 12.4 Update, rollback, uninstall

- `update.sh` is explicit and administrator-invoked; it never runs at boot.
- It installs a new immutable release, migrates/validates config/index schema, smoke-tests, switches atomically, restarts, and rolls back automatically if post-switch health fails.
- `rollback.sh` selects only a recorded validated release compatible with current configuration.
- `uninstall.sh` supports `--keep-data` default and explicit `--purge-data`; it disables/stops the app service, removes owned units/drop-ins/sudoers/tmpfiles/releases, reloads systemd, and reports retained paths.
- Removal of Ollama or shared downloaded models is never implicit unless this project can prove it installed/owns them and purge was explicit.

## 13. Test and evidence architecture

`TEST_MATRIX.md` tiers T0–T6 govern evidence. Implementation adds:

- pytest unit tests with no network/model/hardware;
- mocked HTTP/audio/GPIO/systemd/subprocess boundaries;
- deterministic fixture WAVs and corpus fixtures;
- shell static checks (`bash -n`, ShellCheck when available);
- install-script integration tests using command stubs and temporary roots;
- target Pi scripts that write machine-readable result bundles;
- manual checks only where audibility, wiring, or physical power behavior cannot be automated;
- failure injection at every network/download/build/service switch point;
- a local `scripts/ci.sh` that provides the same core checks intended for later CI.

### 13.1 Release gates

| Gate | Minimum evidence |
|---|---|
| G0 Source | T0 and T1 pass; no unreviewed secret/license blocker |
| G1 Install | clean target image installs; second/third run pass; corrupt/partial artifacts repair |
| G2 Software | model/STT/TTS/retrieval smoke pass without hardware; offline boundary passes |
| G3 Hardware | USB input/output, PTT/LED, full interaction, thermal run pass |
| G4 Wake word | phrase/model consistency, FRR/FAR, noise, idle-load, reboot tests pass |
| G5 Service | enable/start/stop/restart/reboot/hotplug/degraded/recovery pass |
| G6 Power | confirmation/cancellation/adversarial/privilege/manual power tests pass |
| G7 Release | clean-install repeat, rollback, uninstall, security/license/docs audit pass |

### 13.2 Provisional Pi performance acceptance

Final numeric thresholds require the first controlled Pi benchmark, but the release cannot pass if any fixed evaluation causes kernel OOM, sustained swapping that makes the service unusable, thermal throttling under the declared cooled test, or unbounded response time. The controlled benchmark records cold/warm load, first token, total generation, tokens/s, peak RAM, swap, temperature, throttling, and end-to-end time for fixed prompts. After baseline evidence, M3 records justified user-facing thresholds in this blueprint rather than inventing them retrospectively.

## 14. Implementation milestones

Each milestone below is a maximum scope, not an instruction to force all its items into one conversation. A session selects one acceptance-bounded work package, tests it, updates control documents, commits, and stops.

### M1 — Blueprint and architecture review

#### M1A — Produce implementation-grade blueprint

**Files:** `MASTER_BLUEPRINT.md`, `IMPLEMENTATION_STATUS.md`, `DECISIONS.md`, `TEST_MATRIX.md`.

**Actions:** resolve the audit’s deferred choices at blueprint level; define architecture, invariants, work packages, failures, tests, rollback, and traceability.

**Validation:** every C/H audit finding maps to work; all deferred decisions are accepted/provisional/deferred with a gate; no runtime code diff; Markdown/diff consistency passes.

**Commit:** `docs: add implementation master blueprint`.

#### M1B — Adversarial architecture review

**Precondition:** M1A committed.

**Attack questions:** unverified OS/package assumptions; power loss at every step; partial APT/pip/Ollama/model/build states; privilege crossing; device changes; no-network boot; configuration migrations; source/model licenses; dashboard exposure; prompt injection; service compromise; low disk/RAM; upgrade/rollback/uninstall; development versus installed state; overly ambitious scope.

**Output:** review findings with accept/reject rationale incorporated into blueprint/decisions; no code.

**Acceptance:** no unresolved Critical review finding; High items either resolved or explicitly gated with an owner/milestone.

**Commit:** `docs: harden blueprint after architecture review`.

**Rollback:** revert only the documentation commit; audit checkpoint remains intact.

### M2 — Packaging, identity, configuration, and test foundation

#### M2.1 Package and identity normalization

**Files:** `pyproject.toml`, `src/gonken_agent/**`, compatibility `orchestrator.py`, package `__init__` files, prompts, README references.

**Actions:** create installable package and CLI; move modules with `git mv`; remove Jansky/Mayukh behavior; retain temporary wrappers only where tests need transition; set GonKenLab Agent identity in one config path.

**Failure modes:** import cycles, broken entry point, lost assets, stale hard-coded paths.

**Validation:** import/CLI unit tests; repository search for forbidden inherited identity outside historical/audit docs; no hardware required.

#### M2.2 Configuration authority and migration

**Files:** `config/defaults.toml`, `src/gonken_agent/config.py`, migration tests, `.env.example`, legacy JSON.

**Actions:** implement schema validation and precedence; effective-config/redaction command; migrate JSON/`.env`; make model/endpoint/wake/audio/path settings single-source.

**Failure modes:** unknown keys, invalid types, path escape, env/file inversion, partial migration.

**Validation:** table-driven unit tests for every field and precedence; legacy migration repeat; invalid config fails without rewrite.

#### M2.3 Dependency profiles and locks

**Files:** `pyproject.toml`, `requirements/*.lock`, dependency-generation documentation.

**Actions:** split headless core, wake-word, optional UI, and dev/test; pin/hashes for Pi Python 3.13; document openWakeWord exception; remove mandatory pygame.

**Failure modes:** ARM wheel absence, source-build drift, incompatible NumPy/ONNX/Piper/openWakeWord.

**Validation:** clean x86 dev install; AArch64 resolution probe; Pi venv install; `pip check`; import tests; license report.

#### M2.4 Automated test foundation

**Files:** `tests/unit/**`, `tests/integration/**`, `scripts/ci.sh`, test configuration.

**Actions:** convert interactive scripts to explicitly marked hardware tests; add deterministic unit fixtures and mocks; correct router/joke and wake-phrase contradictions.

**Acceptance:** T0/T1 pass from clean checkout; no unit test requires Ollama, network, audio, or GPIO.

**Commit boundary:** `refactor: establish package and configuration foundation` (split into smaller coherent commits if needed).

**Rollback:** compatibility wrapper keeps baseline manual launch until new entry point passes.

### M3 — Idempotent provisioning and artifact lifecycle

#### M3.1 Bootstrap preflight

**Files:** `bootstrap.sh`, `scripts/lib/common.sh`, preflight tests, onboarding draft.

**Actions:** root/sudo logic; platform/disk/RAM/time/network checks; source/ref recording; tracked/untracked conflict check; staging directory; structured errors.

**Validation:** command-stub tests for root, sudo user, no sudo, unsupported OS/arch, no network, low disk, existing checkout states.

#### M3.2 Step engine and install state

**Files:** `scripts/install.sh`, shell library, install-state schema/tests.

**Actions:** stable step protocol, atomic state/log writes, actual postcondition probes, resume semantics, cleanup traps, failure codes.

**Validation:** interrupt before/during/after every fake step; rerun converges; false complete state repairs.

#### M3.3 Immutable application release

**Files:** install-python/release functions, tmpfiles packaging.

**Actions:** create account/paths; build release-specific venv; install locked deps; validate CLI/imports; atomic symlink activation; retain previous release.

**Validation:** failed venv/dependency/smoke never moves `current`; successful upgrade and rollback in temporary root, then Pi.

#### M3.4 Ollama lifecycle and selected model

**Files:** `scripts/install-ollama.sh`, Ollama drop-in, artifact manifest, config/doctor integration.

**Actions:** pin/install ARM64 Ollama; keep separate service user; loopback/local-only settings; start/readiness; pull effective configured model; record full digest; deterministic API smoke; configure single loaded model/parallelism for 4GB.

**Failure modes:** installer unavailable, service missing/fails, port conflict, late readiness, interrupted/corrupt pull, insufficient storage, tag/digest mismatch, model OOM/timeout.

**Validation:** service enabled/active; API version; effective model equals pulled tag/digest; inference contract; no cloud; interrupted pull rerun; model benchmark record.

#### M3.5 Whisper, Piper, and wake support artifacts

**Files:** `scripts/install-models.sh`, artifact manifest, build helpers.

**Actions:** immutable Whisper source/build validation; checked model/voice/JSON downloads; repair partial Piper states; install openWakeWord feature models; do not install/advertise custom wake model until accepted.

**Validation:** checksum, executable/import, sample STT, non-empty valid WAV TTS, zero-byte/missing-pair repair, architecture linkage check.

#### M3.6 Install summary

**Files:** installer, doctor interface.

**Actions:** classify READY/degraded/failed; install service only when M6 assets exist; give exact remediation; never hide hardware warnings.

**Acceptance:** G1 and G2 software portions pass on the target; second/third install has no unintended diff; interruption matrix evidence recorded.

**Commit:** `feat: implement idempotent system provisioning` (use per-component commits if acceptance remains coherent).

**Rollback:** previous release remains active; downloaded shared artifacts are not deleted on failure.

### M4 — Runtime lifecycle and resilient local speech pipeline

#### M4.1 Coordinator/state/health

**Files:** runtime, state, health, logging modules.

**Actions:** centralized transitions, bounded worker queues, cancellation, structured logging, component health, normal signal cleanup.

**Validation:** transition table, concurrent activation rejection, cancellation at every state, no `os._exit`, client/stream cleanup.

#### M4.2 Audio discovery and recovery

**Files:** audio devices/capture modules.

**Actions:** stable selector policy, ambiguity detection, re-enumeration, retry/backoff, frame-accurate capture/silence, bounded queues.

**Validation:** mocked 0/1/multiple/hotplug devices; supported/unsupported rates; overflow; hardware enumeration/replug.

#### M4.3 Resampling/STT/TTS lifecycle

**Files:** resample/STT/TTS modules.

**Actions:** proper resampling, subprocess timeouts/cancel, context-managed TTS output, speech-text normalization.

**Validation:** deterministic WAV fixtures, no temp files after success/failure/signal, benchmark tiny/base if included, audible Pi test.

**Acceptance:** G2 speech software and relevant G3 audio pass; service-ready runtime can remain degraded and recover.

**Commit:** `refactor: add resilient runtime and audio lifecycle`.

**Rollback:** retain compatibility launch path until M6 service switch.

### M5 — Interaction modes, custom wake word, and privacy enforcement

#### M5.1 Push-to-talk and recording indication

**Files:** interaction module, GPIO adapter, config, hardware tests, wiring docs.

**Actions:** hold-to-record/release-to-process; debounce; red recording LED; GPIO cleanup; CLI/mock adapter.

**Failure modes:** missing permissions/device, stuck button, bounce, process crash leaving LED on, pin conflict.

**Validation:** unit timing/state tests; physical button/LED; signal/crash cleanup; LED semantics observed.

#### M5.2 “Hey Gonken” training package

**Files:** `wakeword/README.md`, YAML, model card, training lock/notebook reference, evaluation script/results.

**Actions:** pin working training method; document data/provenance; produce ONNX classifier; build held-out evaluation; threshold sweep; on-Pi load/performance.

**Failure modes:** broken upstream notebook, ONNX export mismatch, licensing uncertainty, accent bias, high false activation/rejection.

**Validation:** G4. If failed, mark experimental and keep disabled.

#### M5.3 Runtime wake integration

**Files:** wake module, state coordinator, config/health/docs.

**Actions:** manifest/phrase validation, in-memory frames only, bounded queue, VAD/noise options only if measured, no silent fallback.

#### M5.4 Offline boundary

**Files:** router/tool registry, remove/disable cloud/weather/news/network joke modules, Ollama config, network tests.

**Actions:** local functions only; no cloud handoff; explicit offline health; network denial test.

**Acceptance:** PTT path passes; wake mode passes or remains explicitly disabled; INV-02/03/04 pass.

**Commit:** `feat: add governed local interaction modes`.

**Rollback:** PTT remains functional if wake mode is disabled/reverted.

### M6 — systemd orchestration and safe power control

#### M6.1 Application service

**Files:** systemd unit, notifier, install-service script, tmpfiles, docs.

**Actions:** dedicated account, hardening, readiness/watchdog decision, startup dependencies, restart limits, journal status.

**Failure modes:** Ollama late/down, audio missing/late, permission denied, config invalid, restart loop, SD read-only/full.

**Validation:** `systemd-analyze verify`; enable/start/stop/restart; status; crash; no-login boot; degraded/hotplug recovery; journal clarity.

#### M6.2 Service installer/removal

**Files:** install/uninstall scripts.

**Actions:** atomic unit/drop-in/sudoers install; daemon reload; ownership validation; reversible removal.

#### M6.3 Power intent and privilege

**Files:** interaction/power modules, root-owned wrapper or sudoers file, tests/docs.

**Actions:** exact request-confirm-cancel state; `sudo -n`; no shell; audit event; feature flag.

**Validation:** `visudo -cf`; allowed commands only; wrong/crossed/expired/injected phrases cancel; physical poweroff/reboot and automatic service return after reboot.

**Acceptance:** G5 passes; G6 required before enabling voice power control.

**Commit:** `feat: install headless service and safe power controls`.

**Rollback:** disable app service, restore prior units/drop-ins/sudoers, daemon-reload; SSH remains available.

### M7 — Grounding, provenance, telemetry, and dashboard

#### M7.1 Corpus and lexical index

**Files:** retrieval modules, corpus README/fixtures, index CLI/tests.

**Actions:** safe discovery, deterministic chunking/IDs/BM25, atomic index, stale detection.

**Validation:** fixed relevance set, reproducibility, path/symlink/size rejection, corrupted/stale index recovery.

#### M7.2 Grounded prompt and response contract

**Files:** prompts, coordinator, answer data structures, tests.

**Actions:** untrusted-source delimiters, support threshold, source IDs, “not found” response, local system tool separation.

**Validation:** known/unknown questions, contradictory sources, injected instructions, invalid citations, no-source behavior.

#### M7.3 Privacy-preserving telemetry

**Files:** telemetry, schema/docs/tests.

**Actions:** content-free default JSONL, atomic/serialized writes, rotation/limits, opt-in interaction records.

#### M7.4 Read-only dashboard

**Files:** dashboard/templates/static/tests.

**Actions:** loopback default, health/metrics/provenance, no mutation routes, safe escaping/CSP as appropriate.

**Validation:** route/access tests, HTML escaping, no transcript when disabled, no control endpoints, bind-address test.

#### M7.5 Research benchmarks

**Files:** benchmark scripts, question/answer gold set, export schemas.

**Actions:** compare grounded/ungrounded, model/STT options, latency/RAM/thermal; preserve evidence without overstating generality.

**Acceptance:** INV-11/12 pass; fixed evaluation and dashboard privacy tests pass.

**Commit:** `feat: add local grounding and observable provenance`.

**Rollback:** disable dashboard/retrieval only through validated config; core diagnostic CLI remains.

### M8 — Diagnostics, support, update, rollback, and uninstall

#### M8.1 Doctor and support bundle

**Files:** health/doctor CLI, support collector, redaction tests, docs.

**Actions:** effective config source, component versions/digests, service state, audio/GPIO inventory, logs tail, disk/RAM/temp/throttling, readiness exit codes; safe archive without secrets/transcripts by default.

#### M8.2 Update/rollback

**Files:** update/rollback scripts, schema migrators/tests.

**Actions:** immutable staged release, backup, compatibility check, atomic switch, post-switch health, automatic rollback.

#### M8.3 Uninstall/reinstall

**Files:** uninstall script/tests/docs.

**Actions:** keep-data default, explicit purge inventory/confirmation, shared Ollama ownership protection, clean reinstall using retained data.

**Acceptance:** G5 operational recovery and G7 update/rollback/uninstall portions pass.

**Commit:** `feat: add diagnostics and lifecycle recovery`.

**Rollback:** scripts themselves are versioned in immutable releases; manual recovery command documented.

### M9 — Release-candidate verification and handoff

#### M9.1 Clean-install and failure campaign

Run the full T0–T6 matrix on a freshly imaged supported Pi. Include no audio, late audio, renumbered/multiple audio, late/no network at runtime, interrupted downloads/builds, corrupt files, low disk simulation, killed runtime, repeated install, reboot, power commands, rollback, uninstall/reinstall, and offline boundary.

#### M9.2 Security/license review

Review service hardening, file permissions, sudoers, dashboard exposure, prompt/tool injection, secrets/redaction, dependency/artifact inventory, and third-party licenses.

#### M9.3 Documentation and onboarding

Replace stale README/PRD instructions with concise entry points and detailed linked guides for procurement, Raspberry Pi Imager, Network Install/Shift, SSH, one-command install, hardware wiring, operation, privacy, doctor, logs, update, rollback, uninstall, and troubleshooting. Commands must be tested by a clean-room reader procedure.

#### M9.4 Development-artifact disposition

Decide whether to retain, condense, or remove `docs/development`. Preserve necessary decisions/test evidence in release docs. Never delete Git history merely to make `main` appear cleaner.

#### M9.5 Portable Git handoff

Create a ZIP containing the repository directory and `.git`; verify branch, tags, objects, clean status, archive integrity, and checksum after extraction. Provide exact push/merge instructions.

**Acceptance:** all required G0–G7 gates pass or an explicitly approved release limitation is documented; no Critical/High issue is silently open; `main`-ready diff reviewed.

**Commit:** `chore: prepare GonKenLab Agent release candidate`.

**Tag:** `checkpoint/release-candidate` followed by a semantic release tag only after acceptance.

## 15. Audit-finding traceability

| Audit finding | Blueprint work |
|---|---|
| C-01 no app service | M6.1–M6.2, G5 |
| C-02 not offline | INV-02, M5.4, G2 |
| C-03 identity mismatch | M2.1, M5.2–M5.3 |
| C-04 no Gonken model chain | M5.2–M5.3, G4 |
| C-05 no grounded lab assistant | M7, INV-11/12 |
| C-06 readiness/idempotency unproven | M3, M9.1, G1–G7 |
| H-01 model authorities | M2.2, M3.4, INV-01 |
| H-02 endpoint mismatch | M2.2, M3.4, M5.4 |
| H-03 root bootstrap | M3.1 |
| H-04 privilege preflight | M3.1, Section 6.2 |
| H-05 Piper partial state | M3.5, INV-09 |
| H-06 dependency drift | M2.3, Section 8 |
| H-07 Python/ARM risk | M2.3, G1 |
| H-08 pygame mandatory | M2.3 |
| H-09 supply chain | Section 8.2–8.3, M3 |
| H-10 no resumable state | M3.2, INV-08/09 |
| H-11 audio construction failure | M4.2, INV-10 |
| H-12 ALSA device zero | M4.2 |
| H-13 wake stream health | M4.1–M4.2, M5.3 |
| H-14 abrupt exit | M4.1, Section 9.3 |
| H-15 TTS temp leak | M4.3, INV-04 |
| H-16 unsafe power gap | M6.3, INV-05/06, G6 |
| H-17 lifecycle undefined | M8 |
| H-18 service permissions | Section 6.2, M6, G5 |

Medium and Low findings are assigned within M2, M4, M8, and M9 and remain tracked in `IMPLEMENTATION_STATUS.md` until closed.

## 16. Milestone completion checklist

Before every implementation commit:

- [ ] selected work package and preconditions recorded;
- [ ] unrelated user changes preserved;
- [ ] success path tested at the applicable tier;
- [ ] failure and rerun paths tested;
- [ ] diff reviewed for secrets, hard-coded host paths, and inherited names;
- [ ] `TEST_MATRIX.md` contains commands/environment/results;
- [ ] `IMPLEMENTATION_STATUS.md` reflects completed/open/next action;
- [ ] new or changed architecture decisions appended to `DECISIONS.md`;
- [ ] blueprint item status updated without erasing original requirements;
- [ ] rollback/recovery verified or explicitly blocked;
- [ ] commit message describes the coherent outcome;
- [ ] working tree clean after commit.

## 17. M1B adversarial review checklist

The next session must attack this draft rather than rewrite it stylistically. At minimum determine:

1. Is Debian 13/Python 3.13 support too narrow or incorrectly assumed for the user’s next clean image?
2. Does `/opt` + `/etc/opt` + `/var/opt` create unnecessary complexity compared with packaging conventions/systemd directory management?
3. Is per-release venv rollback worth microSD use and install time on a 64GB card?
4. Can Ollama version/model digests be pinned and upgraded without brittle installation?
5. Can openWakeWord 0.6.0 and custom training remain maintainable given upstream activity and reported notebook breakage?
6. Are wake-word acceptance sample sizes, diversity, licensing, and thresholds operationally attainable?
7. Does continuous local wake monitoring require a second indicator or a different privacy explanation?
8. Is the proposed power confirmation adequate under STT errors and a compromised service account?
9. Does the service hardening permit PortAudio/ALSA/GPIO, loopback Ollama, and optional dashboard without hidden privilege failures?
10. Does `Type=notify`/watchdog add value proportional to implementation complexity?
11. Are dashboard loopback defaults usable enough, and what authentication is required before LAN binding?
12. Can the offline boundary be verified without falsely treating local LAN traffic as internet exfiltration?
13. Are the installer’s transaction/rollback claims implementable around non-transactional APT and Ollama pulls?
14. What happens on power loss before/after each atomic rename, symlink switch, service restart, and config migration?
15. Can a full reinstall preserve user corpus/config while rejecting incompatible schema?
16. Is BM25 sufficient for the intended Joy of Py/lab corpus, and how will supported-answer quality be evaluated?
17. Does the combined scope remain feasible within the project’s time/budget, and which feature must be deferred first if evidence demands reduction?
18. Are all C/H findings truly covered by an acceptance test rather than only prose?

## 18. Exact next action

Perform M1B adversarial architecture review against this draft and the actual repository. Record concrete review findings, accept/reject each proposed change, revise this blueprint to `1.1-reviewed`, append decisions, update status/test matrix, commit as `docs: harden blueprint after architecture review`, and tag `checkpoint/blueprint` only after no Critical review issue remains unresolved.

Do not implement M2 code during that review session.

## 19. Primary references

- [Raspberry Pi official getting-started and headless setup documentation](https://www.raspberrypi.com/documentation/computers/getting-started.html)
- [Ollama official Linux installation and service documentation](https://docs.ollama.com/linux)
- [Ollama official configuration and local-only FAQ](https://docs.ollama.com/faq)
- [Official Ollama qwen3.5:2b-q4_K_M entry](https://ollama.com/library/qwen3.5:2b-q4_K_M)
- [systemd execution environment and managed-directory documentation](https://www.freedesktop.org/software/systemd/man/systemd.exec.html)
- [systemd service documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [Filesystem Hierarchy Standard 3.0](https://refspecs.linuxfoundation.org/FHS_3.0/fhs-3.0.html)
- [openWakeWord repository, usage, evaluation, training, and licensing](https://github.com/dscripka/openWakeWord)
- [whisper.cpp release b4938](https://github.com/ggml-org/whisper.cpp/releases/tag/b4938)
- [Maintained Piper repository](https://github.com/OHF-Voice/piper1-gpl)
