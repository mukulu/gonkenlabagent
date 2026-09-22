# GonKenLab Agent Implementation Master Blueprint

> Current Attempt03 task authority is `CURRENT_GATES.json` / `../CURRENT_STATE.md`.
> Current B15 voice repair: `b15/REPAIR_RECORD.md`, `b15/INSTALL_AND_VERIFY.md`,
> and `b15/verification/VERIFICATION.json`. Historical M-series plans below do
> not override current Attempt03/B15 source or confer physical acceptance.



**Blueprint revision:** 2.1-appliance-readiness

**Prepared:** 2026-09-12 UTC

**Branch:** `fix5-appliance-readiness`

**Source audit:** `REPOSITORY_AUDIT.md` at checkpoint `checkpoint/audit`

**Review state:** adversarial review completed in `BLUEPRINT_ADVERSARIAL_REVIEW.md`; accepted for staged implementation

**Implementation authorization:** Continuous implementation of all dependency-ready core work through M9 is authorized by the maintainer on 2026-09-09; no one-item-per-session limit.

## 1. Purpose and authority

This blueprint is the implementation contract for turning the current GonKenLab Agent prototype into a reproducible, privacy-sensitive, fully local Raspberry Pi 5 AI-lab assistant. It translates the repository audit and supplied project requirements into ordered, file-level work with explicit failure behavior, validation, rollback, and commit boundaries.

Where this blueprint conflicts with the historical `PRD.md`, this blueprint governs development. The historical PRD is retained only as provenance until the release-documentation milestone. Where a future implementation discovers evidence that makes an item unsafe or infeasible, development must pause that item, record the evidence in `IMPLEMENTATION_STATUS.md` and `DECISIONS.md`, revise this blueprint, and commit the revision before continuing.

The blueprint does not claim that every technical choice is already proven on Raspberry Pi hardware. Unverified choices are marked with gates that require target evidence. The M1B review deliberately separates the core release from governed extensions so that experimental features cannot weaken privacy, safety, or delivery of the primary research instrument.

## 2. Product definition

### 2.1 What is being built

**GonKenLab Agent** is a headless Raspberry Pi 5 4GB appliance that provides a fully local spoken assistant and can optionally ground answers in a bounded corpus of GonKen AI-lab documentation. Speech-to-text, optional document retrieval, language-model inference and text-to-speech run locally. It starts automatically after boot, remains diagnosable when peripherals are absent, and requires no interactive shell activation during normal use.

The primary research and educational contribution is not merely running a chatbot on a Raspberry Pi. It is making a constrained edge-AI assistant observable and accountable through local provenance, measurable performance, explicit privacy states, and restricted actions.

### 2.2 Required release capabilities

The release candidate must provide:

1. repeatable installation on the declared Raspberry Pi OS image;
2. Qwen 3.5 2B Q4_K_M through local Ollama, subject to the model acceptance gate;
3. local Whisper speech recognition;
4. local Piper speech synthesis;
5. an always-on, fully local wake-phrase runtime that starts under systemd without interactive login, plus explicit manual `run` and one-turn `talk` entry points;
6. automatic recovery when the microphone, speaker, Bluetooth transport, or Ollama is temporarily unavailable;
7. optional bounded local Markdown/text corpus retrieval for document-grounded workflows without preventing ordinary offline conversation when no corpus is provisioned;
8. concise spoken answers and privacy-preserving content-free operational telemetry;
9. a minimal read-only diagnostic dashboard restricted to loopback;
10. deterministic boot autostart, readiness announcement, and a content-free READY contract;
11. doctor, install verification, update, rollback, recovery, uninstall, manual service control, and log procedures;
12. optional governed Bluetooth audio with explicit device identity, pairing/trust, headless PipeWire ownership, and reconnect;
13. automated unit/integration tests plus recorded Pi hardware, reboot, wake, audio, thermal, and failure-injection evidence.

Voice power control and direct LAN dashboard access remain governed future extensions. A dedicated low-power/custom wake-word backend remains an X1 optimization; the accepted initial appliance path uses the already pinned local Whisper runtime for bounded wake-phrase spotting. Bluetooth remains opt-in and may never make the USB path unusable.

### 2.3 Explicit non-goals for the first release candidate

- arbitrary general-purpose cloud AI fallback;
- weather, news, or joke APIs that require internet access;
- arbitrary shell execution by the language model;
- camera or multimodal image input;
- a purchased LCD or mandatory pygame UI;
- Bluetooth as the only supported audio path;
- cloud-hosted wake-word processing or retained raw wake-monitor audio;
- voice-authorized shutdown or reboot;
- embedding/vector-database retrieval;
- any non-loopback dashboard bind;
- automatic self-updating at boot;
- automatic graphical or console login;
- AI-controlled safety-critical fan or actuator logic.

### 2.4 Meaning of “fully offline”

“Fully offline” governs **normal runtime after provisioning**. Initial installation, dependency/model download, explicit upgrade, and optional corpus transfer may require internet or LAN access. After provisioning:

- no transcript, prompt, answer, audio, retrieved content, or telemetry is sent to an internet service;
- Ollama binds to loopback and runs with cloud features disabled;
- the assistant remains useful when the internet route is removed;
- the core dashboard uses loopback only; direct LAN access belongs to extension X3;
- update checks do not run automatically.

## 3. Non-negotiable engineering invariants

| ID | Invariant | Enforcement evidence |
|---|---|---|
| INV-01 | Installer, runtime, doctor, service, and tests resolve one effective chat model. | config unit tests; doctor model/digest check; install smoke test |
| INV-02 | Normal runtime performs no unapproved outbound internet request. | network-denial integration test; offline packet/connection audit |
| INV-03 | The enabled wake phrase equals the effective local configuration; continuous monitoring is disclosed in status/docs, and any later physical monitoring indicator must track the same runtime state. | wake/config/runtime tests; GX1 indicator tests when hardware indicator is enabled |
| INV-04 | Raw utterance audio is temporary and deleted by default on success, error, cancellation, and signal. | lifecycle/failure tests; runtime-directory inspection |
| INV-05 | The LLM never supplies a shell command for direct execution. | code review; no-shell subprocess policy; adversarial tests |
| INV-06 | Any voice power extension requires deterministic intent plus independent physical confirmation outside LLM free-form output. | GX2 state-machine, helper, privilege, and hardware tests |
| INV-07 | Headless startup does not depend on autologin, shell profiles, or venv activation. | systemd/reboot test |
| INV-08 | Repeating install after success converges without corrupting configuration or state. | second/third-run comparison |
| INV-09 | A partial or corrupt downloaded artifact is never treated as installed. | checksum and interruption tests |
| INV-10 | Missing audio/GPIO produces a visible degraded state, not an ambiguous “ready” state or installer dead end. | doctor exit codes; service hotplug tests |
| INV-11 | Source material is treated as untrusted data, not executable/system instruction. | prompt-injection retrieval tests |
| INV-12 | Every grounded answer exposes valid source identifiers; unsupported answers say so. | retrieval/answer contract tests |
| INV-13 | Each milestone changes status/tests/decisions in the same commit as implementation. | pre-commit milestone checklist |
| INV-14 | Readiness claims identify their evidence tier. | test matrix and release checklist |
| INV-15 | The core runtime account has no shutdown/reboot privilege. | unit/sudoers/polkit/capability inventory; compromise test |
| INV-16 | Default persistent telemetry contains no transcript, answer, source text, raw audio, secret, absolute corpus path, or username. | schema/redaction tests; support-bundle inspection |

## 4. Supported platform and hardware contract

### 4.1 Primary supported target

- Raspberry Pi 5 with 4GB RAM;
- current Raspberry Pi OS Lite 64-bit based on Debian 13 “Trixie”;
- AArch64 kernel and userspace;
- distribution Python 3.13;
- systemd as PID 1;
- 64GB A2-class microSD or better;
- appropriate Raspberry Pi 5 active cooling;
- adequate 5V/5A-class power supply;
- one usable local audio input/output path; USB audio is the baseline and optional Bluetooth is accepted through its separate gate;
- GPIO push button/LED are optional physical-control enhancements rather than prerequisites for wake-voice operation.

As verified during M1B, current Raspberry Pi OS is Trixie and Debian Trixie's default `python3` is 3.13. The installer must still record the exact image release/date, `/etc/os-release`, architecture, Python patch version, Pi model, free storage, RAM, and systemd version. It must not assume a fixed Python patch release. Unsupported platforms fail before mutation unless `--development-host` is explicitly selected for non-service desktop testing.

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
│   │   └── push_to_talk.py
│   ├── extensions/
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
│   ├── extensions/sudoers/gonken-agent-power
│   └── tmpfiles.d/gonken-agent.conf
├── requirements/
│   ├── pi-trixie-py313.lock
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
├── extensions/wakeword/
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
| `/usr/local/lib/gonken-agent/releases/<git-sha>/` | `root:root`, not service-writable | immutable local application and release-specific venv |
| `/usr/local/lib/gonken-agent/current` | root-owned atomic symlink | active validated release |
| `/usr/local/bin/gonken-agent` | root-owned stable entry point | administrator CLI dispatch to the active release |
| `/etc/gonken-agent/config.toml` | `root:gonken-agent`, `0640` | site configuration overrides |
| `/etc/gonken-agent/environment` | `root:gonken-agent`, `0640` | explicit service environment; normally no cloud secrets |
| `/var/lib/gonken-agent/models/` | root-managed, service-readable | Whisper and Piper artifacts; extension artifacts remain separate until accepted |
| `/srv/gonken-agent/corpus/` | administrator-managed, service-readable | bounded, intentionally exposed lab-document tree |
| `/var/lib/gonken-agent/index/` | service-writable | derived lexical index; reproducible from corpus |
| `/var/lib/gonken-agent/telemetry/` | service-writable, private | content-free performance telemetry |
| `/var/lib/gonken-agent/interactions/` | disabled/uncreated by default | opt-in research records only |
| `/var/lib/gonken-agent/install/` | root-writable | phase journal and install/version manifest |
| `/var/cache/gonken-agent/` | service-writable | disposable cache |
| `/run/gonken-agent/` | tmpfs/runtime, service-writable | temporary WAVs, health/status socket/files |
| journald | system managed | operational logs with retention controlled by OS |

This uses the FHS local-software hierarchy for administrator-installed code, ordinary `/etc` configuration, `/var/lib` host state, `/srv` for the administrator-visible corpus, and systemd-compatible cache/runtime locations. Mixed-ownership persistent paths are created explicitly; `RuntimeDirectory=` and `CacheDirectory=` are preferred where the target systemd version supports the required ownership.

### 6.2 Accounts and process boundaries

| Process | Account | Network | Writable locations | Privilege |
|---|---|---|---|---|
| installer/update/rollback | root after explicit sudo preflight | internet during explicit operation | install/config/state trees | system mutation |
| `ollama.service` | `ollama` | loopback server; internet only during explicit pull | Ollama model store | no login |
| `gonken-agent.service` | `gonken-agent` system user, no shell | Unix sockets and loopback only | `/run`, index, cache, telemetry | no sudo, power capability, or configuration ownership |
| X2 power helper | absent from core; root-owned if later accepted | none | root-owned extension state only | exact action after independent physical confirmation |
| developer process | invoking user | as explicitly configured | checkout-local dev state | no installed service mutation |

The runtime never owns its release directory and cannot replace code, dependency locks, prompts, or model manifests.

### 6.3 Release installation and rollback

Each installed release is keyed by full Git commit SHA. The installer builds the venv in a candidate directory, validates it, makes the candidate immutable/root-owned, then atomically switches `current`. It retains the active and one previous validated release only. Before staging, it requires headroom for the candidate, downloads, temporary build products, and a safety margin based on measured prior release size. A failed candidate leaves `current` untouched.

Activation uses a root-owned phase journal containing candidate, previous release, and phase. Durable project writes use a same-filesystem temporary file, validation, file sync, atomic replacement, and parent-directory sync where power-loss persistence matters. A pre-start reconciliation operation resolves an interrupted switch: it validates a pending candidate as the service user and either completes activation or restores the recorded previous validated release. Ambiguous/corrupt root-owned metadata fails visibly rather than guessing. These guarantees apply to project releases and files, not to transactionally rolling back APT.

## 7. Configuration contract

### 7.1 Single authority and precedence

1. packaged `config/defaults.toml` contains the only source-controlled defaults;
2. `/etc/gonken-agent/config.toml` contains administrator overrides;
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
voice = "en_US-ljspeech-medium"

[interaction]
push_to_talk_gpio = 17
recording_led_gpio = 27

[retrieval]
enabled = true
top_k = 3

[privacy]
raw_audio_retention = "delete"
interaction_logging = false
telemetry_content = false
dashboard_transient_content = false

[dashboard]
enabled = true
bind = "127.0.0.1"
port = 8080

[paths]
assets_dir = "/usr/local/lib/gonken-agent/current/share/gonken-agent/face"
state_dir = "/var/lib/gonken-agent"
cache_dir = "/var/cache/gonken-agent"
runtime_dir = "/run/gonken-agent"
corpus_dir = "/srv/gonken-agent/corpus"
whisper_binary = "/usr/local/bin/whisper-cli"
whisper_model = "/var/lib/gonken-agent/models/whisper/base.en-q5_1.bin"
piper_voice = "/var/lib/gonken-agent/models/piper/en_US-ljspeech-medium/en_US-ljspeech-medium.onnx"
local_prompt = "/usr/local/lib/gonken-agent/current/share/gonken-agent/local_soul.md"

[extensions.wake_word]
enabled = false
phrase = "Hey Gonken"
model = ""
threshold = 0.5
monitoring_led_gpio = 22

[extensions.voice_power]
enabled = false
```

Exact values may change after adversarial review, but the authority/validation model may not be weakened without a recorded decision.

### 7.3 Validation rules

- unknown keys are errors, not silently ignored;
- invalid enum, port, URL scheme, path escape, sample-rate relation, GPIO conflict, threshold, context, or retention value prevents readiness;
- `runtime.mode=offline` rejects non-loopback LLM endpoints and all cloud/network tool registrations;
- the core dashboard rejects every non-loopback bind; X3 must introduce a separate accepted schema and access-control contract;
- wake-word enablement requires the X1 package, accepted backend, existing artifact, manifest checksum, matching phrase/model-card identifier, distinct monitoring indicator, and accepted GX1 evidence;
- voice-power enablement requires the X2 package and accepted GX2 evidence; core installation contains no power authorization;
- GPIO input and recording LED cannot share a pin;
- an enabled wake-monitoring LED cannot share the push-to-talk or recording LED pin;
- site config is never rewritten by ordinary runtime;
- `gonken-agent config show --effective` redacts sensitive values and records each setting’s source;
- config migration stages and validates a copy, retains a timestamped backup, and is repeatable; newer/unknown schemas are not rewritten;
- release readiness requires a retrieval threshold recorded in validated index metadata rather than a corpus-independent score invented in default configuration.

## 8. Dependency and artifact policy

### 8.1 Python dependencies

- `pyproject.toml` defines project metadata, entry points, and human-maintained compatible ranges.
- Target installation uses `requirements/pi-trixie-py313.lock` with exact versions and hashes.
- Host development uses a separate exact `requirements/dev-py312.lock`.
- Headless core excludes pygame; UI becomes an optional dependency group.
- Test tools are separate from runtime dependencies.
- `pip check`, import checks, license inventory, and a deterministic smoke suite run before release activation.
- Wake-word dependencies are absent from the core lock. X1 creates a separate exact lock only after a backend spike proves Python 3.13/AArch64 installation, inference, maintenance, and license compatibility; `--no-deps` is not an accepted production dependency strategy by itself.

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

Whisper source is pinned to an immutable commit corresponding to the accepted release. Ollama uses a named stable ARM64 release asset and its upstream-published SHA-256 rather than piping a mutable installer into a privileged shell. The Ollama model source tag and full local digest are both recorded after controlled validation; tag-only presence is insufficient. A changed digest is an explicit model update that repeats quality, memory, latency, thermal, and offline gates.

### 8.3 Licensing gate

Before redistribution, record licenses/provenance for source code, face PNGs, filler WAVs, Piper package and voice, Whisper model, Qwen model, and every extension artifact/data source. Current maintained Piper is GPL-3.0-or-later and individual voice licenses vary; M2.1 must therefore create the inventory and record a maintainer-approved project/distribution license decision before a redistributable package is claimed. An artifact with unclear or incompatible redistribution rights is excluded or downloaded separately under an accepted policy. README cannot claim MIT coverage over third-party assets without qualification.

M2.1 closes for continued private development through D-050/D-051: no project
license is granted, redistribution is prohibited, unknown media is quarantined,
and noncommercial artifacts are legacy internal-evaluation inputs only. This
does not satisfy the future release license gate; it prevents a false release
claim while allowing configuration work to proceed.

## 9. Runtime architecture

### 9.1 State machine

```text
BOOTING -> WAITING_DEPENDENCIES -> IDLE
IDLE -> RECORDING
RECORDING -> TRANSCRIBING -> RETRIEVING -> GENERATING -> SPEAKING -> IDLE
ANY_ACTIVE -> DEGRADED | STOPPING
DEGRADED -> WAITING_DEPENDENCIES -> IDLE
```

X1 may add `IDLE -> WAKE_MONITORING -> RECORDING` only after GX1. X2 may add a power-request state only after GX2. State transitions are centralized and tested. Audio callbacks enqueue bounded frames/events only; they do not run STT, retrieval, LLM, TTS, or privileged logic. One coordinator owns interaction execution so overlapping activations cannot create concurrent model/audio pipelines on 4GB RAM.

### 9.2 Health/readiness

Health contains independent component states: config, filesystem, Ollama server, selected model, Whisper, Piper, input audio, output audio, GPIO, retrieval index, dashboard, and privacy mode. Installed extensions add their own state without weakening core readiness. Overall states are:

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
- treat Qwen 3.5 2B Q4_K_M as the selected candidate until the fixed Pi benchmark passes; any fallback requires a recorded decision rather than silent substitution;
- never route a query to cloud automatically;
- constrain spoken responses and remove Markdown formatting before TTS;
- keep model/tool routing deterministic where a local function can answer directly.

## 10. Interaction, grounding, and governance contracts

### 10.1 Voice activation and manual fallback

The production appliance starts in local wake-phrase standby after boot. The initial accepted wake detector reuses the pinned Whisper runtime in bounded windows and deletes temporary audio after transcription. `gonken-agent run` provides the same continuous runtime in the foreground and `gonken-agent talk --seconds N` provides an explicit one-turn fallback. GPIO push-to-talk remains a useful optional physical-control path and may be enabled later without becoming a prerequisite for the basic voice appliance.

### 10.2 Extension X1 — dedicated low-power wake backend

X1 no longer represents whether the appliance can use a wake phrase at all. The baseline appliance can phrase-spot locally with the already accepted Whisper runtime. X1 is the governed optimization path for a dedicated wake backend such as openWakeWord/custom model when a backend spike proves maintenance, license, Python 3.13/AArch64 installation, on-Pi inference, false-reject/false-accept performance, idle CPU/thermal behavior, phrase/model consistency and any physical monitoring-indicator requirements. Failure of X1 leaves the Whisper wake path available.

The “Hey Gonken” model requires:

- a reproducible training configuration and pinned training environment;
- model card with phrase, version, framework, checksum, data sources/licenses, limitations, and evaluation;
- several thousand generated positive examples or justified equivalent;
- large, representative negative material with lawful provenance;
- held-out positive recordings across intended speakers/accents/noise;
- hours of representative non-trigger audio;
- threshold sweep and selected operating point;
- at least 200 held-out intended activations across at least 10 speakers, including intended accent/noise variation;
- at least 24 hours of representative held-out non-trigger audio;
- false-reject and false-accept point estimates with confidence intervals, initially targeting FRR below 5% and FAR below 0.5/hour without hiding subgroup results;
- on-device real-time-factor and idle CPU/RAM measurements;
- a second physical indicator, distinct from the red recording LED, that is on whenever continuous wake monitoring is active;
- no silent fallback to Jarvis or another phrase.

If GX1 fails, the extension remains disabled and the failure is documented; thresholds are not weakened merely to close the milestone. Core release acceptance is unaffected.

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

Default persistent telemetry records timestamp, component timings, generated-token counts, model/digest, CPU temperature, RAM, throttling state, audio duration, health state, and corpus-relative source IDs—not transcript, answer text, source text, raw audio, absolute paths, usernames, or secrets. Interaction-content logging is opt-in research mode with a visible configuration/health warning and a documented retention/deletion procedure.

Raw audio lives only in `/run/gonken-agent`, is deleted after STT by default, and is removed on all failure/signal paths. “Retain audio” is permitted only in explicit benchmark mode with informed handling and a separate directory.

### 10.5 Dashboard

The core dashboard is read-only and binds only `127.0.0.1`. It shows health, current state, model/digest, timings, temperatures, memory, corpus-relative source IDs/scores, and privacy/logging mode. When `dashboard_transient_content=true`, it may show the current/last transcript, answer, and safely escaped retrieved excerpts from process memory; this content is not written to persistent telemetry and disappears on restart. It exposes no shell, install, update, power, corpus-write, or configuration-write endpoint.

Core configuration rejects non-loopback binds. Loopback access through SSH forwarding is the supported laptop path. Direct LAN/phone access is extension X3 and requires authentication plus an explicit transport, token lifecycle, rate-limit, exposure, and threat-model decision before any non-loopback bind is accepted.

### 10.6 Extension X2 — power actions

Voice-authorized power is absent from the core release, and the core service account has no corresponding sudoers, polkit, capability, or helper access. This resolves the unsafe baseline gap without granting a network/audio-facing service availability control over the host. Administrator shutdown/reboot through SSH and the documented Raspberry Pi physical power-button behavior remain available.

If X2 is later implemented, intent is parsed from normalized STT text by exact finite-state rules; the LLM does not decide it. Proposed request phrases are:

- request: “shut down Gonken” or “reboot Gonken”;
- cancellation: “cancel.”

The requested action must then be confirmed by an independent physical hold/gesture within a short timeout. Any mismatch, timeout, additional material, or low-confidence/empty transcription cancels safely. A narrowly reviewed root-owned helper independently verifies the confirmation protocol and exposes exactly poweroff/reboot; it never accepts a command string or uses `shell=True`. GX2 must model service-account compromise as well as accidental speech. Two consecutive voice phrases are not sufficient confirmation.

## 11. systemd service contract

`packaging/systemd/gonken-agent.service` must implement, subject to target verification:

- `User=gonken-agent`, `Group=gonken-agent`;
- no interactive login or shell-profile dependency;
- dependency on local `ollama.service` without requiring internet availability;
- `Type=exec`; application-level readiness is exposed through health/doctor rather than a custom notification protocol;
- `Restart=on-failure` with bounded restart interval/start limit;
- `TimeoutStopSec` sufficient for audio cleanup but bounded;
- no watchdog in the core unit; add one only after a measured hang mode and heartbeat tests justify it;
- `WorkingDirectory=/usr/local/lib/gonken-agent/current`;
- `ExecStart=/usr/local/lib/gonken-agent/current/.venv/bin/gonken-agent run`;
- optional `EnvironmentFile=-/etc/gonken-agent/environment`;
- `RuntimeDirectory=gonken-agent`, `CacheDirectory=gonken-agent` where compatible with chosen FHS paths;
- `UMask=0027`;
- `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectHome=true`, a read-only system view, restricted writable paths, and a minimal address-family set, applied incrementally against hardware tests;
- target-proven audio/GPIO supplementary groups or scoped udev permissions; `PrivateDevices=true` is prohibited for this hardware-facing process;
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

M3.1 implements the admission boundary for items 1, 2, 5, and 6 and writes a
private, non-sourceable facts record only after every check passes. M3.2
implements item 7 as a probe-authoritative engine handoff. M3.3 adds target
bootstrap prerequisites, verified exact-commit acquisition directly into a
candidate, the release-local venv, immutable finalization, and durable atomic
activation. M3.4 adds a checksum-pinned Ollama release, exact service policy,
and full-digest-bound Qwen state. M3.5 adds checksum-pinned Whisper/Piper
artifact provisioning and a real content-free speech-chain smoke; target
execution then prints `M3_6_INSTALL_SUMMARY` with `status=DEGRADED`,
`ready=false`, and never falls through to legacy `setup.sh`. The apparent item-7 `--source` interface is concretely implemented
as the private `--source-record` plus a refetch of its exact commit so mutable
checkout contents never become the installed payload. D-056–D-059, D-066,
`RELEASE_ACTIVATION_SCHEMA.md`, `OLLAMA_MODEL_LIFECYCLE.md`, and
`SPEECH_ARTIFACT_LIFECYCLE.md` record the staged contract.

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

### 12.3 Transaction and interruption truth boundary

The installer is not one atomic transaction. APT/dpkg and Ollama model pulls mutate external/shared stores and cannot truthfully be rolled back as a unit. Those steps are **convergent provisioning**: detect active package-manager processes without killing them blindly, inspect actual dpkg/APT/Ollama state, run narrowly indicated repair, and repeat an idempotent postcondition-driven step.

Atomic activation applies to project-owned release pointers, generated indexes, configuration replacements, and state records. The root-owned phase journal records prepared, switched, post-verified, and rolled-back states. Project writes use same-filesystem staging and durable replacement. A pre-start reconciliation command runs before the app service after interruption; it completes a validated pending activation or restores the recorded prior validated release. The detailed interruption matrix in `BLUEPRINT_ADVERSARIAL_REVIEW.md` is binding.

### 12.4 Readiness summary

Installer completion reports one of:

- `READY`: software, model, service, and configured connected hardware pass;
- `SOFTWARE_READY_HARDWARE_DEGRADED`: service installed and retrying, but one or more peripherals are missing/ambiguous;
- `FAILED`: required software/config/integrity/service validation failed.

Only `READY` prints that the assistant is ready for interaction. Degraded output gives exact discovery/config/doctor commands and still verifies that the service remains inspectable.

### 12.5 Update, rollback, uninstall

- `update.sh` is explicit and administrator-invoked; it never runs at boot.
- It installs a new immutable release, stages and validates config/index schema, smoke-tests, journals activation, switches atomically, restarts, and rolls back the project release automatically if post-switch health fails.
- `rollback.sh` selects only a recorded validated release compatible with current configuration.
- `uninstall.sh` supports `--keep-data` default and explicit `--purge-data`; it disables/stops the app service, removes owned core units/drop-ins/tmpfiles/releases, reloads systemd, and reports retained paths. Extension-owned privilege files are removed only when that extension was actually installed.
- Removal of Ollama or shared downloaded models is never implicit unless this project can prove it installed/owns them and purge was explicit.

## 13. Test and evidence architecture

`TEST_MATRIX.md` tiers T0–T6 govern evidence. Implementation adds:

- pytest-discoverable unit tests with no network/model/hardware; the
  standard-library runner remains accepted until pytest and its complete graph
  can be exact/hash-locked and installed from a controlled wheelhouse (D-055);
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
| G5 Service | enable/start/stop/restart/reboot/hotplug/degraded/recovery pass |
| G7 Release | clean-install repeat, rollback, uninstall, security/license/docs audit pass |
| GX1 Wake extension | backend/license spike, phrase/model consistency, representative FRR/FAR with intervals, distinct indicator, idle-load, and reboot pass |
| GX2 Voice-power extension | independent physical confirmation, cancellation, compromise, privilege, and physical reboot/poweroff pass |
| GX3 LAN dashboard extension | authentication, transport, token lifecycle, exposure, rate-limit, and adversarial access tests pass |
| GX4 Bluetooth extension | pair/reconnect/enumeration/latency/reboot/end-to-end tests pass |

### 13.2 Provisional Pi performance acceptance

Final numeric thresholds require the first controlled Pi benchmark, but the release cannot pass if any fixed evaluation causes kernel OOM, sustained swapping that makes the service unusable, thermal throttling under the declared cooled test, or unbounded response time. The controlled benchmark records cold/warm load, first token, total generation, tokens/s, peak RAM, swap, temperature, throttling, and end-to-end time for fixed prompts. Qwen 3.5 2B Q4_K_M remains the first candidate, not a pre-declared passing result. After baseline evidence, M3 records justified user-facing thresholds in this blueprint; any fallback model requires a decision and repeated grounding-quality tests.

## 14. Implementation milestones

Milestones are acceptance and traceability units, not conversation limits. Implement a coherent dependency-ready item, run its proportionate success/failure tests, update evidence/status/decisions, and commit. Immediately continue to the next ready item in the same session. Multiple items or milestones may be grouped in one coherent tested commit. Do not repeat broad testing without a concrete remaining risk; run the full applicable regression suite at checkpoint close.

A failed requirement blocks that requirement and its genuine dependants, not unrelated host-testable work. Record the blocker, the missing evidence and its release impact, then continue independent work. Distinguish software implementation, host T0/T1 evidence, target T2–T6 acceptance and release acceptance. Mocked tests never close hardware gates. Stop only for completion, an actual dependency/access/decision barrier with no useful independent work, or an execution/context limit requiring a resumable committed checkpoint. Never weaken acceptance criteria to increase milestone counts. Never require new permission solely to cross a milestone.

### M1 — Blueprint and architecture review

#### M1A — Produce implementation-grade blueprint

**Files:** `MASTER_BLUEPRINT.md`, `IMPLEMENTATION_STATUS.md`, `DECISIONS.md`, `TEST_MATRIX.md`.

**Actions:** resolve the audit’s deferred choices at blueprint level; define architecture, invariants, work packages, failures, tests, rollback, and traceability.

**Validation:** every C/H audit finding maps to work; all deferred decisions are accepted/provisional/deferred with a gate; no runtime code diff; Markdown/diff consistency passes.

**Commit:** `docs: add implementation master blueprint`.

#### M1B — Adversarial architecture review

**Precondition:** M1A committed.

**Attack questions:** unverified OS/package assumptions; power loss at every step; partial APT/pip/Ollama/model/build states; privilege crossing; device changes; no-network boot; configuration migrations; source/model licenses; dashboard exposure; prompt injection; service compromise; low disk/RAM; upgrade/rollback/uninstall; development versus installed state; overly ambitious scope.

**Output:** `BLUEPRINT_ADVERSARIAL_REVIEW.md` with accept/reject rationale incorporated into blueprint/decisions; no code.

**Acceptance:** no unresolved Critical review finding; High items either resolved or explicitly gated with an owner/milestone.

**Commit:** `docs: harden blueprint after architecture review`.

**Rollback:** revert only the documentation commit; audit checkpoint remains intact.

### M2 — Packaging, identity, configuration, and test foundation

#### M2.1 Package and identity normalization

**Implementation status (2026-09-08): COMPLETE.** Package/CLI, compatibility
boundary, identity normalization, extension isolation, inventory, and host
validation are implemented. The project deliberately grants no license and
prohibits redistribution; unknown media and noncommercial artifacts are
quarantined from packages/releases/public exports. Release licensing remains a
later blocker, but M2.2 may proceed.

**Files:** `pyproject.toml`, `src/gonken_agent/**`, compatibility `orchestrator.py`, package `__init__` files, prompts, README references.

**Actions:** create installable package and CLI; move modules with `git mv`; remove Jansky/Mayukh behavior; retain temporary wrappers only where tests need transition; set GonKenLab Agent identity in one config path; encode core-versus-extension module boundaries; create a source/assets/dependencies license inventory and obtain a maintainer-approved project/distribution license decision before claiming redistributability.

**Failure modes:** import cycles, broken entry point, lost assets, stale hard-coded paths, extension dependency leaking into core, unapproved/incompatible project or third-party license claims.

**Validation:** import/CLI unit tests; repository search for forbidden inherited identity outside historical/audit docs; core import works with extension packages absent; license inventory has no unknown bundled source/asset; no hardware required.

#### M2.2 Configuration authority and migration

**Implementation status (2026-09-08): COMPLETE.** The package now loads the
single shipped `config/defaults.toml`, strict site TOML, explicit environment
overrides, and one-shot CLI overrides with per-field source attribution. The
effective-config CLI redacts paths. Legacy JSON/`.env` are explicit,
non-destructive migration inputs with atomic output, restricted backups, and
repeat behavior. The installer, doctor, compatibility runtime, and component
constructors no longer carry independent model, endpoint, audio, or artifact
fallbacks. Forty-two dependency-free host tests plus an isolated offline wheel
install pass; Pi behavior remains unclaimed.

**Files:** `config/defaults.toml`, `src/gonken_agent/config.py`, migration tests, `.env.example`, legacy JSON.

**Actions:** implement schema validation and precedence; effective-config/redaction command; migrate JSON/`.env`; make model/endpoint/audio/path settings single-source; keep extension settings disabled and reject unsupported enablement/non-loopback dashboard bind.

**Failure modes:** unknown keys, invalid types, path escape, env/file inversion, partial migration.

**Validation:** table-driven unit tests for every field and precedence; legacy migration repeat; invalid config fails without rewrite.

#### M2.3 Dependency profiles and locks

**Implementation status (2026-09-08): COMPLETE for the maintained package
foundation.** A machine-readable profile authority now renders four exact,
hash-enforcing, wheel-only locks: empty headless-core and standard-library
development locks plus separate pygame UI locks for Python 3.12/x86_64 and
Python 3.13/AArch64. The legacy broad input is quarantined outside every
accepted path. Wake and TTS profiles fail closed without locks because their
backend/license/runtime gates remain unresolved. Fifty-one host tests, an
isolated wheel install, `pip check`, core import with pygame/openWakeWord
absent, deterministic lock verification, and a license report pass. Upstream
metadata proves the selected UI wheel identity/hash for the target, but no
networked cross-download or physical Pi venv was available; those remain
explicitly blocked and no Pi success is claimed.

**Files:** `pyproject.toml`, `requirements/*.lock`, dependency-generation documentation.

**Actions:** split headless core, post-spike extension, optional UI, and dev/test profiles; pin/hashes for Trixie/Python 3.13; keep openWakeWord absent from core; remove mandatory pygame.

**Failure modes:** ARM wheel absence, source-build drift, incompatible NumPy/ONNX/Piper, accidental extension dependency, GPL/voice-license mismatch.

**Validation:** clean x86 dev install; AArch64 resolution probe; Pi venv install; `pip check`; import tests; license report.

#### M2.4 Automated test foundation

**Implementation status (2026-09-08): COMPLETE.** `scripts/ci.sh` is the
single dependency-free T0/T1 entry point. It runs 63 unit and three deterministic
process integration tests and cannot discover the opt-in live/manual probes.
The three former top-level interactive scripts now live under explicit
integration/manual or hardware boundaries, return exit 2 before importing
external dependencies unless enabled, and document evidence requirements.
Fake-client fixtures cover legacy router decisions without HTTP/Ollama; the joke
expectation now matches `get_joke`, phrase matching rejects substrings, and the
legacy wake probe advertises no unsupported spoken phrase. D-055 retains
pytest-compatible naming but does not invent an unverified pytest dependency
graph. Clean-checkout validation passes; no Pi/runtime readiness is claimed.

**Files:** `tests/unit/**`, `tests/integration/**`, `scripts/ci.sh`, test configuration.

**Actions:** convert interactive scripts to explicitly marked hardware tests; add deterministic unit fixtures and mocks; correct router/joke and wake-phrase contradictions.

**Acceptance:** T0/T1 pass from clean checkout; no unit test requires Ollama, network, audio, or GPIO.

**Commit boundary:** `refactor: establish package and configuration foundation` (split into smaller coherent commits if needed).

**Rollback:** compatibility wrapper keeps baseline manual launch until new entry point passes.

### M3 — Idempotent provisioning and artifact lifecycle

#### M3.1 Bootstrap preflight

**Implementation status (2026-09-08): COMPLETE.** `bootstrap.sh` and
`scripts/lib/common.sh` now validate the exact target or an explicit bounded
development host, minimum disk/RAM, plausible TLS time, required commands,
direct-root/sudo-root/non-root identity, one sudo credential check, existing
tracked/staged/untracked state and origin, and a unique advertised source
branch/tag. Only success creates a mode-700 staging directory and mode-600
non-sourceable record containing the resolved commit and observed platform,
image, interpreter, init, and resource evidence. Default execution stops at
`M3_2_UNAVAILABLE`; it cannot invoke the prototype installer. Eighty-one unit
and six deterministic integration tests pass on the audit host. Physical Pi
and real remote-source validation remain blocked and are not inferred from
fixtures.

**Files:** `bootstrap.sh`, `scripts/lib/common.sh`, preflight tests, onboarding draft.

**Actions:** root/sudo logic; platform/disk/RAM/time/network checks; source/ref recording; tracked/untracked conflict check; staging directory; structured errors.

**Validation:** command-stub tests for root, sudo user, no sudo, unsupported OS/arch, no network, low disk, existing checkout states.

#### M3.2 Step engine and install state

**Implementation status (2026-09-08): COMPLETE.** `scripts/install.sh` and
`scripts/lib/install_engine.sh` implement the stable eight-field step contract,
strict non-evaluating M3.1 record parsing and independent host/ref
revalidation, authoritative postcondition probes, private same-directory
atomic state/event records, exclusive boot/PID/start-identity locking, stale
lock recovery, cooperative cleanup traps, and opt-in test-only interruption
points. Bootstrap now routes through the engine and stops at
`M3_3_UNAVAILABLE`; no real provisioning occurs. Ninety-two unit tests and 16
deterministic integration tests pass on the audit host, including all
before/during/after boundaries for two fake steps and abrupt-kill recovery.
Physical target and power-loss evidence remain blocked and are not inferred
from host processes.

**Files:** `scripts/install.sh`, shell library, install-state schema/tests.

**Actions:** stable step protocol, atomic state/log writes, actual postcondition probes, resume semantics, cleanup traps, failure codes.

**Validation:** interrupt before/during/after every fake step; rerun converges; false complete state repairs.

#### M3.3 Immutable application release

**Implementation status (2026-09-09): COMPLETE at T0/T1 host tier.** Commit
`0ea9db1` implements target prerequisite/account creation, exact recorded-commit
fetch and archive validation, platform lock selection, local wheel build,
release-local venv installation, CLI/status/`pip check` smoke tests, payload
hash/size/ownership/immutability validation, same-filesystem candidate
finalization, a root-owned four-phase activation journal, atomic constrained
`current`, maintenance locking, rerun reconciliation, rollback, and validated
active-plus-previous retention. A release-local pre-start helper is present but
is not wired to systemd before M6. The deterministic suite interrupts every
candidate-finalization, journal, pointer, and post-switch boundary; failed
postchecks restore the prior release. Physical Pi, real root/service-account,
filesystem power-loss, and reboot evidence remain blocked and are not inferred
from temporary-root tests. See `RELEASE_ACTIVATION_SCHEMA.md`.

**Files:** install-python/release functions, tmpfiles packaging.

**Actions:** create account/paths; build release-specific venv; install locked deps; validate CLI/imports; measure release/staging space; journal and atomically activate; retain active plus one previous release; install pre-start reconciliation.

**Validation:** failed venv/dependency/smoke never moves `current`; low-space preflight; interruption around candidate finalization/journal/symlink; successful activation/reconciliation/rollback in temporary root, then Pi.

#### M3.4 Ollama lifecycle and selected model

**Status:** Complete at T0/T1 in `980e09c`; real target acceptance remains blocked. See `OLLAMA_MODEL_LIFECYCLE.md` and `TEST_MATRIX.md`.

**Files:** `scripts/install-ollama.sh`, Ollama drop-in, artifact manifest, config/doctor integration.

**Actions:** download a named stable ARM64 Ollama release and verify its published SHA-256; keep separate service user; loopback/local-only settings; start/readiness; pull effective configured model; record full digest; deterministic API smoke; configure single loaded model/parallelism for 4GB.

**Failure modes:** installer unavailable, service missing/fails, port conflict, late readiness, interrupted/corrupt pull, insufficient storage, tag/digest mismatch, model OOM/timeout.

**Validation:** service enabled/active; API version; effective model equals pulled tag/digest; inference contract; no cloud; interrupted pull rerun; model benchmark record.

#### M3.5 Whisper and Piper artifacts

**Files:** `scripts/install-models.sh`, artifact manifest, build helpers.

**Actions:** immutable Whisper source/build validation; checked model/voice/JSON downloads; repair partial Piper states; do not install wake-word dependencies or artifacts in the core profile.

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

### M5 — Core interaction and privacy enforcement

#### M5.1 Push-to-talk and recording indication

**Files:** interaction module, GPIO adapter, config, hardware tests, wiring docs.

**Actions:** hold-to-record/release-to-process; debounce; red recording LED; GPIO cleanup; CLI/mock adapter.

**Failure modes:** missing permissions/device, stuck button, bounce, process crash leaving LED on, pin conflict.

**Validation:** unit timing/state tests; physical button/LED; signal/crash cleanup; LED semantics observed.

#### M5.2 Offline boundary

**Files:** router/tool registry, remove/disable cloud/weather/news/network joke modules, Ollama config, network tests.

**Actions:** local functions only; no cloud handoff; explicit offline health; network denial test.

**Acceptance:** PTT/recording-indicator path passes; loopback-only runtime works with external network/DNS unavailable; INV-02/04/15/16 pass. Wake-word packages are absent or disabled.

**Commit:** `feat: add governed local interaction modes`.

**Rollback:** retain the tested CLI trigger as a diagnostic fallback while the physical path is repaired; do not enable continuous capture.

### X1 — “Hey Gonken” governed wake-word extension

**Preconditions:** core release gates pass; backend/licensing/Python 3.13/AArch64 spike accepted; a second physical monitoring indicator is available.

**Files:** `extensions/wakeword/**`, extension adapter/config/lock, model card, training configuration, evaluation scripts/results, privacy documentation.

**Actions:** select and pin a maintainable backend; document lawful data/provenance; train/export the phrase classifier; freeze held-out evaluation; sweep thresholds; integrate bounded in-memory inference and the distinct monitoring indicator.

**Failure modes:** broken training environment, dependency/ONNX mismatch, unclear feature-model license, accent/subgroup bias, high FAR/FRR, indicator failure, excessive Pi load.

**Acceptance:** GX1 and INV-03 pass. Failure leaves the extension uninstalled/disabled and does not alter core PTT behavior.

### M6 — Core systemd orchestration

#### M6.1 Application service

**Files:** systemd unit, install-service script, tmpfiles, docs.

**Actions:** dedicated account; `Type=exec`; target-proven audio/GPIO permissions; incremental hardening; startup dependencies; restart limits; pre-start activation reconciliation; journal status; no power privilege.

**Failure modes:** Ollama late/down, audio missing/late, permission denied, config invalid, restart loop, SD read-only/full.

**Validation:** `systemd-analyze verify`; enable/start/stop/restart; status; crash; no-login boot; degraded/hotplug recovery; journal clarity.

#### M6.2 Service installer/removal

**Files:** install/uninstall scripts.

**Actions:** atomic unit/drop-in/tmpfiles install; daemon reload; ownership validation; assert no sudoers/polkit/capability grant; reversible removal.

**Acceptance:** G5 passes; core compromise tests confirm the runtime account cannot power off/reboot.

**Commit:** `feat: install governed headless service`.

**Rollback:** disable app service, restore prior units/drop-ins/tmpfiles, daemon-reload; SSH remains available.

### X2 — Physically confirmed voice-power extension

**Preconditions:** core G5/G7 pass; independent physical confirmation design and root-helper threat model accepted.

**Actions:** exact voice request/cancel state, short confirmation window, root helper independently verifies physical confirmation, exact poweroff/reboot operations only, no shell or free-form arguments.

**Acceptance:** GX2 and INV-05/06 pass under accidental-speech, STT-error, malicious-document, and compromised-service scenarios. Failure leaves no installed privilege file.

### M7 — Grounding, provenance, telemetry, and dashboard

#### M7.1 Corpus and lexical index

**Files:** retrieval modules, corpus README/fixtures, index CLI/tests.

**Actions:** safe discovery, deterministic chunking/IDs/BM25, atomic index, stale detection.

**Validation:** frozen set with at least 40 answerable and 20 unanswerable questions; initial hit@3 target ≥85%; reproducibility; path/symlink/size rejection; corrupted/stale index recovery; calibrated support threshold stored in index metadata.

#### M7.2 Grounded prompt and response contract

**Files:** prompts, coordinator, answer data structures, tests.

**Actions:** untrusted-source delimiters, support threshold, source IDs, “not found” response, local system tool separation.

**Validation:** known/unknown questions, contradictory sources, injected instructions, invalid citations, no-source behavior; initial unsupported-answer abstention target ≥90% and valid-source-ID coverage 100%, with failures and sample size reported.

#### M7.3 Privacy-preserving telemetry

**Files:** telemetry, schema/docs/tests.

**Actions:** content-free default JSONL, atomic/serialized writes, rotation/limits, opt-in interaction records.

#### M7.4 Read-only dashboard

**Files:** dashboard/templates/static/tests.

**Actions:** loopback-only health/metrics/provenance; optional in-memory transient interaction display; no mutation routes; corpus-relative IDs; safe escaping/CSP as appropriate; reject non-loopback bind.

**Validation:** route/access tests, HTML escaping, transient content cleared by restart and never written to telemetry, no transcript when disabled, no absolute path/secret leakage, no control endpoints, non-loopback rejection.

#### M7.5 Research benchmarks

**Files:** benchmark scripts, question/answer gold set, export schemas.

**Actions:** compare grounded/ungrounded, model/STT options, latency/RAM/thermal; preserve evidence without overstating generality.

**Acceptance:** INV-11/12 pass; fixed evaluation and dashboard privacy tests pass.

**Commit:** `feat: add local grounding and observable provenance`.

**Rollback:** disable dashboard/retrieval only through validated config; core diagnostic CLI remains.

### X3 — Authenticated direct-LAN dashboard extension

**Preconditions:** core dashboard passes; transport, authentication, token lifecycle, rate-limit, browser-origin, and local-network threat model accepted.

**Acceptance:** GX3. Until then, SSH forwarding is the only supported remote dashboard access.

### X4 — Bluetooth audio extension

**Preconditions:** USB audio and all core audio/reboot gates pass.

**Actions:** define pairing ownership, stable device selection, reconnect/backoff, boot ordering, latency, capture/playback switching, and privacy-indicator behavior for the chosen device.

**Acceptance:** GX4. Until then, Bluetooth is documented as experimental and is not selected by default.

### M8 — Diagnostics, support, update, rollback, and uninstall

#### M8.1 Doctor and support bundle

**Files:** health/doctor CLI, support collector, redaction tests, docs.

**Actions:** effective config source, component versions/digests, service state, audio/GPIO inventory, logs tail, disk/RAM/temp/throttling, readiness exit codes; safe archive without secrets/transcripts by default.

#### M8.2 Update/rollback

**Files:** update/rollback scripts, schema migrators/tests.

**Actions:** immutable staged release, non-destructive schema staging/backup, compatibility check, root-owned phase journal, atomic switch, post-switch health, project-release rollback, and pre-start reconciliation after interruption.

#### M8.3 Uninstall/reinstall

**Files:** uninstall script/tests/docs.

**Actions:** keep-data default, explicit purge inventory/confirmation, shared Ollama ownership protection, clean reinstall using retained data.

**Acceptance:** G5 operational recovery and G7 update/rollback/uninstall portions pass.

**Commit:** `feat: add diagnostics and lifecycle recovery`.

**Rollback:** scripts themselves are versioned in immutable releases; manual recovery command documented.

### M9 — Release-candidate verification and handoff

#### M9.1 Clean-install and failure campaign

Run the full applicable T0–T6 core matrix on a freshly imaged supported Pi. Include no audio, late audio, renumbered/multiple audio, no external network at runtime, interrupted APT/download/model/build/journal/switch/restart operations, corrupt files, low disk simulation, killed runtime, repeated install, reboot, project rollback, uninstall/reinstall, offline boundary, and proof that the core runtime cannot invoke host power actions. Extension tests run only for extensions proposed for installation.

#### M9.2 Security/license review

Review service hardening, file permissions, absence or scope of privilege files, dashboard exposure, prompt/tool injection, secrets/redaction, dependency/artifact inventory, project license, and third-party licenses.

#### M9.3 Documentation and onboarding

Replace stale README/PRD instructions with concise entry points and detailed linked guides for procurement, Raspberry Pi Imager, Network Install/Shift, SSH, one-command install, hardware wiring, operation, privacy, doctor, logs, update, rollback, uninstall, and troubleshooting. Commands must be tested by a clean-room reader procedure.

#### M9.4 Development-artifact disposition

Decide whether to retain, condense, or remove `docs/development`. Preserve necessary decisions/test evidence in release docs. Never delete Git history merely to make `main` appear cleaner.

#### M9.5 Portable Git handoff

Create a ZIP containing the repository directory and `.git`; verify branch, tags, objects, clean status, archive integrity, and checksum after extraction. Provide exact push/merge instructions.

**Acceptance:** core gates G0, G1, G2, G3, G5, and G7 pass or an explicitly approved release limitation is documented; no Critical/High core issue is silently open; `main`-ready diff reviewed. GX1–GX4 do not block core release unless an extension is proposed for installation.

**Commit:** `chore: prepare GonKenLab Agent release candidate`.

**Tag:** `checkpoint/release-candidate` followed by a semantic release tag only after acceptance.

## 15. Audit-finding and planned-test traceability

| Audit finding | Blueprint work | Planned verification evidence | Release disposition |
|---|---|---|---|
| C-01 no app service | M6.1–M6.2, G5 | V-C01: enable/start/stop/restart/no-login reboot/degraded recovery | Core blocker |
| C-02 not offline | INV-02, M5.2, G2 | V-C02: loopback-up/external-route-and-DNS-down run plus connection-attempt audit | Core blocker |
| C-03 identity mismatch | M2.1 | V-C03: forbidden-identity repository/runtime scan and prompt/CLI assertions | Core blocker |
| C-04 no Gonken model chain | X1, GX1 | V-X1-01: phrase/artifact/model-card/checksum/evaluation/indicator/reboot suite | Extension blocker; not core |
| C-05 no grounded lab assistant | M7, INV-11/12 | V-C05: frozen retrieval/abstention/source-ID/prompt-injection evaluation | Core blocker |
| C-06 readiness/idempotency unproven | M3, M9.1, core gates | V-C06: clean image, second/third install, interruption campaign, reboot evidence bundle | Core blocker |
| H-01 model authorities | M2.2, M3.4, INV-01 | V-H01: precedence matrix and installer/runtime/doctor/service equality | Core blocker |
| H-02 endpoint mismatch | M2.2, M3.4, M5.2 | V-H02: loopback endpoint validation and Ollama readiness/API tests | Core blocker |
| H-03 root bootstrap | M3.1 | V-H03: root/non-root/sudo-user/no-sudo command-stub matrix | Core blocker |
| H-04 privilege preflight | M3.1, Section 6.2 | V-H04: one preflight, noninteractive failure, no partial privileged mutation | Core blocker |
| H-05 Piper partial state | M3.5, INV-09 | V-H05: zero-byte/missing-pair/bad-checksum repair plus audible output | Core blocker |
| H-06 dependency drift | M2.3, Section 8 | V-H06: hash-locked clean install, `pip check`, import and license inventory | Core blocker |
| H-07 Python/ARM risk | M2.3, G1 | V-H07: Trixie/Python 3.13/AArch64 resolution and real Pi venv install | Core blocker |
| H-08 pygame mandatory | M2.3 | V-H08: headless core install/import with pygame absent | Core blocker |
| H-09 supply chain | Section 8.2–8.3, M3 | V-H09: URL/version/checksum/license manifest and corrupt-download rejection | Core blocker |
| H-10 no resumable state | M3.2–M3.3, INV-08/09 | V-H10: interruption before/during/after every fake and real activation phase | Core blocker |
| H-11 audio construction failure | M4.2, INV-10 | V-H11: zero-device startup remains diagnosable/degraded and later recovers | Core blocker |
| H-12 ALSA device zero | M4.2 | V-H12: 0/1/multiple/renumber/hotplug selector and physical enumeration | Core blocker |
| H-13 wake stream health | X1, GX1 | V-X1-02: stream overflow/error/reopen/indicator/idle-load suite | Extension blocker; not core |
| H-14 abrupt exit | M4.1, Section 9.3 | V-H14: SIGTERM/SIGINT/cancel at each state with resource cleanup | Core blocker |
| H-15 TTS temp leak | M4.3, INV-04 | V-H15: success/error/signal temp-artifact lifecycle inspection | Core blocker |
| H-16 unsafe power gap | INV-05/06/15, X2 | V-H16: core account cannot power host; V-X2-01 physical-confirm/helper/compromise suite | Core absence-of-privilege blocker; capability is extension |
| H-17 lifecycle undefined | M8 | V-H17: explicit update/rollback/keep-data uninstall/reinstall and ownership tests | Core blocker |
| H-18 service permissions | Section 6.2, M6, G5 | V-H18: unit verify/security score plus audio/GPIO/filesystem/loopback access on Pi | Core blocker |

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

## 17. M1B adversarial review closure

All 18 mandatory attack questions were adjudicated in `BLUEPRINT_ADVERSARIAL_REVIEW.md`. Four entered review as Critical:

- voice-only power confirmation and service compromise;
- false whole-installer rollback claims around APT/Ollama;
- undefined power-loss behavior around activation;
- combined core/experimental scope.

They were resolved by removing core power privilege, distinguishing convergent provisioning from project-atomic activation, specifying a durable activation journal/pre-start reconciliation contract, and originally isolating X1–X4. The later appliance-readiness revision promotes baseline Whisper wake operation and opt-in X4 Bluetooth while keeping X2/X3 and the dedicated X1 backend independently gated. No Critical M1B issue remains open. AR-19 remains a High release gate: M2.1 resolved its development disposition through an explicit no-redistribution policy, but a future public release still requires maintainer-approved licensing and provenance.

## 18. Exact next action

Read the current machine-readable milestone ledger and generated status table. Resolve M3.5 artifact/dependency policy where evidence permits, while advancing independent M4/M5/M7 software work with explicit interfaces. Continue through every dependency-ready item; reserve service activation and target acceptance until their real prerequisites pass. Commit tested progress and package the exact clean Git state. The checkpoint name must describe demonstrated scope without implying that skipped or partial milestones are complete.

## 19. Primary references

- [Raspberry Pi official getting-started and headless setup documentation](https://www.raspberrypi.com/documentation/computers/getting-started.html)
- [Raspberry Pi OS documentation confirming current Trixie base](https://www.raspberrypi.com/documentation/computers/os.html)
- [Debian Trixie default Python 3.13 package](https://packages.debian.org/trixie/python3)
- [Ollama official Linux installation and service documentation](https://docs.ollama.com/linux)
- [Ollama official configuration and local-only FAQ](https://docs.ollama.com/faq)
- [Ollama model-list API including model digest](https://docs.ollama.com/api/tags)
- [Ollama releases with published asset checksums](https://github.com/ollama/ollama/releases)
- [Official Ollama qwen3.5:2b-q4_K_M entry](https://ollama.com/library/qwen3.5:2b-q4_K_M)
- [systemd execution environment source documentation](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml)
- [systemd service source documentation](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml)
- [Filesystem Hierarchy Standard `/usr/local`](https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch04s09.html)
- [Filesystem Hierarchy Standard `/var/lib`](https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch05s08.html)
- [openWakeWord repository, usage, evaluation, training, and licensing](https://github.com/dscripka/openWakeWord)
- [whisper.cpp release b4938](https://github.com/ggml-org/whisper.cpp/releases/tag/b4938)
- [Maintained Piper package, Python/AArch64 wheels, provenance, and GPL license](https://pypi.org/project/piper-tts/)

## 18. FIX5 appliance-readiness renovation (2026-09-12)

### 18.1 Release meaning

A successful bootstrap is no longer allowed to mean only "software installed".
For the Pi 5 production profile, normal completion means the installed system is
an operational local voice appliance:

```text
boot -> systemd -> local dependencies -> physical audio -> wake standby
     -> wake phrase -> STT -> local Qwen -> Piper -> speaker -> standby
```

The long-running appliance starts through `gonken-agent.service`; interactive
shell login or console auto-login is neither required nor desired. The service
must remain enabled across reboot and recover from temporarily unavailable local
dependencies without reinstalling models.

### 18.2 Initial wake-word implementation

The first accepted always-on wake path uses the already pinned local Whisper
runtime for bounded phrase spotting of the configured wake phrase. This closes
the functional appliance gap without introducing a second unprovisioned ML
artifact. A dedicated low-power wake-word model remains an X1 optimization and
must be separately pinned, licensed and benchmarked before replacing the
baseline.

Wake monitoring must not persist microphone chunks or transcripts. Raw capture
files are temporary and removed after each bounded operation.

### 18.3 Final appliance readiness record

The runtime owns `/run/gonken-agent/ready.json`. The record is ephemeral,
content-free and valid only while the service is physically ready. It contains
categorical state such as wake phrase, audio backend and local model identity;
it contains no user speech or model answer.

The final installer step restarts the service, waits for `systemctl active` plus
this valid ready record, and fails with bounded service/journal evidence if the
runtime cannot become ready. `INSTALLATION_COMPLETE` may print `READY` only
after this gate passes.

### 18.4 Physical audio contract

Appliance readiness requires the configured input and output path to be opened
on the target. For USB-only operation, ALSA card numbers are resolved dynamically
from configured name matching rather than cached numeric indices. For managed
Bluetooth, the dedicated `gonken-agent` PipeWire graph is used through ALSA's
PipeWire default route.

The ready announcement performs a real Piper synthesis/playback operation. A
runtime that cannot open its physical input or play synthesized speech remains
in retry/wait state rather than claiming readiness.

### 18.5 Bluetooth prerequisite reconciliation

When X4 Bluetooth is requested, every dependency is explicitly postconditioned:

- BlueZ installed and `bluetooth.service` active;
- a controller exists;
- hard rfkill block is rejected with remediation;
- soft rfkill is unblocked automatically;
- controller `Powered=yes` is established;
- lingering `gonken-agent` user manager exists;
- PipeWire/PipeWire-Pulse/WirePlumber are active and `pactl` responds;
- the selected device is paired, trusted and connected;
- an output route is present when the device advertises output;
- trusted-device autoconnect is enabled.

The package must use distro-global PipeWire user-unit enablement and start those
units in the lingering user manager; it must not assume it can create per-user
enablement symlinks under the root-managed service home.

### 18.6 Network bootstrap boundary

The outer HTTPS installer cannot repair a Wi-Fi radio that has no legal WLAN
country before it has network access. Raspberry Pi Imager therefore remains the
preferred authority for Wi-Fi SSID/passphrase/country and SSH. The launcher may
diagnose blocked Wi-Fi but must not guess a regulatory country. Ethernet is an
accepted initial transport and unused blocked Wi-Fi does not fail installation.

### 18.7 Manual-operation contract

Both automatic and manual paths are required:

- automatic: `gonken-agent.service`, enabled at boot;
- foreground continuous voice: `gonken-agent run` after stopping the service;
- one explicit voice turn: `gonken-agent talk --seconds N`;
- service start/stop/restart/status through systemd;
- bounded current/live logs through journald;
- `doctor --probe-ollama --probe-audio` for explicit diagnostics;
- private support bundle through the maintained collector.

Legacy `orchestrator.py` and `run --legacy-source` are not accepted production
entry points and must not be recommended to users.

### 18.8 Documentation split

`README.md` is the user-facing path only: prepare Pi, one-command installation,
Bluetooth option, `READY`, wake phrase and links. Operational commands live in
`docs/OPERATIONS.md`; detailed install/network recovery lives in
`docs/INSTALLATION.md`; Bluetooth internals live in `docs/BLUETOOTH_AUDIO.md`;
engineering authority remains under `docs/development/`.

### 18.9 Pi 4 portability

Raspberry Pi 4 is a future target profile, not an alias for the validated Pi 5
profile. It requires separate RAM/thermal/inference/wake/audio evidence and may
need different model/concurrency limits. Do not relax the Pi 5 preflight gate
until that profile exists and passes its own acceptance campaign.

### 18.10 FIX5 regression gates

Before packaging FIX5:

- unit tests for wake matching, local unstructured Qwen chat, ALSA selection,
  physical turn cleanup, Bluetooth controller reconciliation and readiness
  summary;
- installer-engine interruption/resume suite;
- CLI/service/manual-operation integration tests;
- release and normal speech lifecycle tests;
- Bash syntax, Python compilation and `git diff --check`;
- consumer-side application of the generated patch to an untouched FIX4
  checkpoint followed by focused tests.

Physical acceptance remains mandatory after host verification: live wake, spoken
turn, no-login reboot, Bluetooth reconnect and recovery must be observed on the
Pi before FIX5 is called a proven appliance release.


## 19. FIX6 adaptive physical-audio reconciliation (2026-09-12)

### 19.1 Evidence

The first FIX5 physical appliance gate timed out on `AUDIO_CAPTURE_FAILED` even
though its content-free startup snapshot enumerated a usable USB microphone and
USB speaker. Bluetooth was also configured. The failure therefore came from
transport routing, not absence of audio hardware.

### 19.2 Runtime rule

Audio input and output are independent resources. For each direction the runtime
must evaluate current route evidence in this order:

```text
managed Bluetooth requested
  -> dedicated PipeWire/Pulse endpoint exists and is usable? -> prefer it
  -> otherwise exactly one eligible direct ALSA USB path?    -> use fallback
  -> otherwise wait with categorical route diagnostics
```

A Bluetooth record is identity/configuration evidence only; it is never proof
that a current capture/playback route exists. Numeric ALSA indexes remain
non-authoritative. A Pulse endpoint that fails after selection may trigger one
direct-ALSA fallback attempt when an unambiguous fallback is available.

### 19.3 Pairing/readiness rule

A headset-capable Bluetooth device must expose the required Bluetooth output before
its pairing step can satisfy. Bootstrap must attempt an available HFP/HSP profile
when microphone capability is advertised, but pairing is not the authority for
whole-appliance input readiness: one unambiguous direct USB microphone may supply
the accepted input path when the Bluetooth capture source is unavailable. The
final appliance-readiness boundary must perform the real capture. Pairing and
appliance-readiness step versions advance when this contract changes so old
advisory completion records cannot suppress revalidation.

### 19.4 Diagnostics

Content-free debug snapshots include hardware PCM inventories plus PipeWire/Pulse
server/default-source/default-sink/source/sink summaries. Runtime audio command
failures expose bounded stderr/device/backend metadata but never recorded speech.
The default sudo support-export workflow returns a user-owned archive in the
invoking administrator's home.

### 19.5 Acceptance

FIX6 is not physically accepted until the current Pi reaches `APPLIANCE_READY`,
completes a real `Hey Gonken` turn, and repeats that behavior after reboot with no
interactive login. A later clean-card campaign must then reproduce the same
result from the one-command installer.


## 20. FIX7 boot/audio convergence and service-environment correction (2026-09-12)

### 20.1 Real-target evidence

FIX6 completed service/Bluetooth installation but stopped immediately at
`INSTALL_PRECONDITION` for `appliance_readiness`. The same target had already
proved the production voice core manually when run as `gonken-agent` with
`XDG_RUNTIME_DIR=/run/user/<gonken-agent-uid>` and the matching session bus. The
FIX6 support snapshot showed the service process itself ran as UID 999 while
Pulse/WirePlumber commands nevertheless attempted `/run/user/0`.

### 20.2 Structural service precondition

The application-service boundary and appliance-readiness precondition must prove
the governed unit/tmpfiles/runtime-environment files and boot enablement, not
require the long-running process to already be active. `appliance_manager
activate` owns start/restart and the wait for physical `READY`. This prevents a
transient audio/service state from blocking the very action responsible for
repairing it.

### 20.3 Correct user-session environment

Never use system-unit `%U` as the service-account UID. The installer resolves the
actual `gonken-agent` UID and generates `/etc/gonken-agent/runtime-environment`
with its `XDG_RUNTIME_DIR` and D-Bus session path. The generated file contains no
secrets, is validated as governed state, participates in exact managed upgrades,
and is removed by uninstall.

### 20.4 Wired-first, existing-connection policy

Audio capture and playback are independent and dynamically rediscovered. For
`auto`, each direction uses the first proven route in this order:

1. connected PipeWire/Pulse USB endpoint;
2. one unambiguous direct ALSA USB endpoint;
3. the exact configured/connected Bluetooth endpoint.

Existing BlueZ bonds/connections are reused. USB presence never causes Bluetooth
unpairing; Bluetooth remains the fallback. Constructor-time hardware absence is
not fatal: route discovery is deferred into readiness/recovery so boot may race
USB enumeration or Bluetooth reconnection without entering a restart storm.

### 20.5 FIX7 evidence gate

Host gates cover structural-vs-active service semantics, generated runtime UID
environment, managed FIX6 unit migration, wired-first ordering, USB-to-Bluetooth
fall-through, lazy route discovery, uninstall cleanup, full unit discovery, quick
integrations, normal Ollama/speech lifecycle and static checks. Real Pi closure
requires bootstrap `READY`, a spoken wake turn, then reboot/no-login return to
wake standby.


## 21. V09 room-environment subsystem implementation line (2026-09-15)

### 21.1 Governing V09 blueprint

V09 is governed by `GONKEN-V09-BP-GOLD-2026-09-15`, supplied as
`GONKEN_NEXT_COMPREHENSIVE_IMPLEMENTATION_BLUEPRINT(2).md`.  The local source
checkpoint for this branch is FIX7 commit
`3b25b81c5bc7d4e24268726ad7f7b71296215a03` on `fix7-appliance-resilience`.
The first implementation branch is `v09-environment-foundation` and the Python
development line is `0.2.0.dev0`.

The V09 governing rule is unchanged from the blueprint: AI may interpret or
express intent, but deterministic software owns policy and deterministic hardware
code owns actuation.  Host/mock evidence must not be promoted to physical
Raspberry Pi acceptance.

### 21.2 V09 milestone structure

The M10 series implements the V09 environment subsystem.  Physical Raspberry Pi
and electrical acceptance remain target-gated until M10.7.

#### M10.1 V09 baseline audit and branch identity

Pin the FIX7 baseline, record source package hashes, create the V09 branch, run
the focused baseline host slice, attempt broad CI under a bounded watchdog, and
record any timeout or interrupted evidence without converting it into false PASS.

#### M10.2 Static environment configuration schema

Bump the static configuration authority from schema 1 to schema 2; add a disabled
`extensions.environment` section with SHT31, relay, socket, policy and hard-bound
fields; preserve typed source attribution; and accept schema-1 site files as
migration inputs without downgrading the effective schema.

#### M10.3 Environment domain and mutable policy foundation

Add pure dependency-free environment domain and policy objects: modes,
capabilities, sensor-reading quality, static policy bounds, mutable policy schema
1, generation-conflict handling, closed JSON mapping and atomic policy-file
persistence.  This milestone must not import hardware libraries or actuate GPIO.

#### M10.4 Deterministic controller core

Implement the tested MANUAL, SEMI_AUTOMATIC, AUTOMATIC and DISABLED state
machine, including hysteresis, dwell, median valid samples, stale-sensor safe-off,
recovery, reason codes and threshold-change semantics.

Checkpoint 02 implements this as a dependency-free `EnvironmentController` with
no hardware imports.  Host tests cover explicit manual control, DISABLED safe-off,
SEMI start/auto-stop semantics, AUTO dwell/hysteresis, stale-sensor safe-off,
recovery sequencing, policy-update stop behavior and the rule that direct ON/OFF
in AUTO switches to MANUAL plus the requested relay-power boundary.

#### M10.5 Local environment service and IPC

Implement the single-owner `gonken-environment.service`, bounded AF_UNIX JSON v1
protocol, client library, service lifecycle, permissions model and in-process
degraded states for absent hardware.

#### M10.6 CLI, voice, installer, diagnostics and documentation integration

Expose `gonken-agent env` commands, deterministic voice environment intents,
result-derived spoken responses, schema migration/install hooks, systemd unit,
support-bundle fields, read-only dashboard status and operator documentation.

#### M10.7 Real Raspberry Pi HIL and release acceptance

Run the physical SHT31, relay, PENGLIN USB switching, ELUTENG fan, voice, wake,
latency, reboot/no-login, update/rollback and fault-injection campaign on the
pinned Pi/hardware/config.  This is the first milestone allowed to close physical
environment acceptance.

## V09 implementation checkpoint 03 — local IPC foundation

M10.5 has now implemented the host-verifiable local IPC foundation requested by the V09 blueprint: protocol v1, a host-fake service core, AF_UNIX server, client wrapper and unit tests. This is an implementation-status note, not a revision to the governing architecture. The hardware-owner rule remains unchanged: production SHT31 and relay access must later enter only behind the environment service boundary. Host-fake service evidence is explicitly not Raspberry Pi acceptance.

## V09 implementation checkpoint 04 — operator CLI client surface

M10.6 has begun with the host-verifiable operator CLI layer.  `gonken-agent env` now uses the shared `EnvironmentClient` boundary for status, health, sensor read, fan power, mode, policy and probe operations.  This preserves the V09 rule that the CLI is a client of the single-owner environment service, not an independent GPIO/I2C actor.  Human and JSON output must continue to report daemon-returned state and must not convert `physical_evidence=false` into a hardware acceptance claim.

This checkpoint does not complete M10.6.  Voice-domain intents, installer/systemd environment-service integration, diagnostics/support/dashboard fields, watch-mode documentation and production hardware adapters remain subsequent dependency-ready work.  M10.7 remains the first milestone eligible to claim physical SHT31/relay/fan/Raspberry Pi acceptance.


## V09 implementation checkpoint 05 — environment observability surfaces

M10.6 now also includes host-verifiable diagnostics/support/dashboard environment visibility.  Startup snapshots, `doctor`, support bundles and the read-only dashboard can report the environment static configuration boundary, configured I2C/relay fields, service/socket visibility, read-only daemon health where available, and explicit capability flags.  These surfaces remain non-destructive: they do not scan arbitrary I2C devices, toggle relays, open GPIO lines, mutate policy, or claim physical acceptance.

This checkpoint still does not complete M10.6.  Installer/systemd provisioning, deterministic voice-domain intents, watch-mode/operator documentation and production SHT31/libgpiod adapters remain subsequent dependency-ready work.  M10.7 remains the first milestone eligible to claim physical SHT31/relay/fan/Raspberry Pi acceptance.

## V09 implementation checkpoint 06 — environment service installer/systemd wiring

M10.6 now includes host-verifiable installer and systemd scaffolding for the separate room-environment controller.  The release payload contains `environment_service_manager.py`, `gonken-environment.service` and `gonken-environment.conf`; target installation provisions the non-login `gonken-env` owner, the `gonken-envctl` control-socket client group, runtime/state/cache tmpfiles and an exact managed unit.  The voice service has only a soft `Wants`/`After` relationship with `gonken-environment.service`; it never `Requires` it.

The structural service remains disabled by default for generic upgrades and the hidden `gonken-agent env serve` entry point fails closed when the static environment profile is enabled before production SHT31/libgpiod adapters exist.  This checkpoint therefore verifies provisioning boundaries, release inclusion, service-file conflict refusal and uninstall retention/purge behavior, but it does not claim systemd target execution, hardware detection or physical fan acceptance.

M10.6 still remains partial.  Deterministic voice-domain intents, watch-mode/operator documentation and production SHT31/libgpiod hardware adapters remain subsequent dependency-ready work.  M10.7 remains the first milestone eligible to claim physical SHT31/relay/fan/Raspberry Pi acceptance.

## V09 implementation checkpoint 07 — deterministic voice intents and watch mode

M10.6 now includes host-verifiable deterministic voice environment intents and result-derived spoken responses. Clear temperature, humidity, fan-state, fan-power, mode and threshold phrases are parsed before the ordinary LLM path and converted into typed environment-client calls. Ambiguous phrases clarify instead of mutating policy. Spoken responses derive from daemon results or daemon errors and do not claim fan speed, blade motion or physical Raspberry Pi acceptance. `gonken-agent env watch` is a repeated IPC read path, not direct sensor access.

This checkpoint still does not complete M10.6. Production SHT31/libgpiod adapters and target-grounded operator documentation remain subsequent dependency-ready work. M10.7 remains the first milestone eligible to claim physical SHT31/relay/fan/Raspberry Pi acceptance.

## V09 implementation checkpoint 08 — SHT31 and libgpiod adapter foundation

M10.6 now includes host-verifiable production adapter modules behind the environment service boundary. `SHT31Sensor` implements an SMBus-style SHT31-D reader with lazy `python3-smbus` import, high/medium/low single-shot command selection, CRC-8 validation, Sensirion conversion formulas and truthful unavailable/CRC-failed `SensorReading` results. `GpiodRelayFanActuator` implements a libgpiod-v2-style relay request with exclusive line ownership, configured active-high/active-low semantics, initial inactive output, explicit logical ON/OFF writes, safe-off release and a capability boundary that remains power-only.

The service core can now synchronize controller state to an injected actuator and fail closed with `ACTUATOR_ERROR_SAFE_OFF` if an actuator write fails. This is still host evidence only. The hidden `gonken-agent env serve` path remains fail-closed for enabled profiles because supervised hardware-daemon activation has not yet been physically accepted on the target Pi. M10.7 remains required for I2C enablement, SHT31 detection, CRC read quality, Pi 5 gpiochip mapping, relay polarity, PENGLIN USB switching, ELUTENG fan cycles, reboot/no-login convergence and real wake/voice acceptance.

## V09 implementation checkpoint 09 — environment-daemon activation scaffold

M10.6 now includes a host-verifiable `gonken-agent env serve` activation scaffold for the separate environment daemon. The new `src/gonken_agent/environment/daemon.py` assembles `EnvironmentServiceCore` from the validated static environment configuration, daemon-owned `PolicyStore`, `SHT31Sensor`, and `GpiodRelayFanActuator`, then exposes that core through the existing bounded AF_UNIX server. The enabled daemon path creates a missing default policy atomically, refuses corrupt policy files without replacement, reports `physical_evidence=false`, and uses lazy adapter construction so the process can start in a degraded/readable state without treating host construction as real hardware proof.

The service remains disabled by default for generic installations and upgrades. The hidden `gonken-agent env serve --check` path validates daemon construction without starting a socket loop or toggling hardware. Server shutdown now performs best-effort safe-off and adapter cleanup. This checkpoint does not add a background autonomous polling loop and does not close physical acceptance; M10.7 remains required for I2C enablement, SHT31 detection, repeated CRC-valid reads, Pi 5 gpiochip mapping, relay polarity, PENGLIN USB switching, ELUTENG fan cycles, reboot/no-login convergence and wake/voice target evidence.

## V09 implementation checkpoint 10 — daemon polling/control-loop scaffold

M10.6 now includes a host-verifiable bounded polling/control-loop scaffold for `gonken-environment.service`. `EnvironmentServiceCore.poll_once()` centralizes daemon-owned sensor reads, controller observation, actuator reconciliation and degraded-state recording. `EnvironmentPollingLoop` provides a stoppable background thread using the configured poll interval, and `EnvironmentDaemon.from_config()` attaches that loop to the AF_UNIX daemon lifecycle. The polling path catches sensor transport exceptions as structured unavailable/failed readings so AUTO/SEMI can fail closed, records actuator write failures without terminating the polling thread, and retains `physical_evidence=false` in all returned state.

This checkpoint still does not complete M10.6 in the physical sense and does not close M10.7. The polling scaffold is tested only with fake sensor/actuator/clock objects. It does not prove target `/dev/i2c-*` access, SHT31 detection, repeated CRC-valid readings, Pi 5 gpiochip mapping, relay polarity, PENGLIN USB switching, ELUTENG fan cycles, systemd runtime under target permissions, reboot/no-login convergence, or wake/voice acceptance.

## 21.12 Checkpoint 11 — M10.7 private evidence scaffold and target-readiness closure

The final host-side M10.6 tranche adds a target evidence scaffold rather than a new physical claim. `scripts/environment_acceptance_runner.py` creates a private M10.7 evidence directory containing `m10_7_evidence_manifest.json`, `m10_7_private_evidence_ledger.csv`, and per-step JSON evidence files under `private_evidence/`. The runner records platform identity, service state, `gonken-agent status --json`, environment status/health/read/probe output, and recent voice/environment journals. It deliberately records `physical_acceptance_claimed=false` in every manifest and step file.

The runner is non-destructive by default. Fan ON/OFF evidence is blocked unless the operator supplies `--allow-actuation`; the runbook requires power-off wiring inspection and physical supervision before using that flag. The runner still cannot prove blade motion, relay polarity, representative SHT31 placement, reboot/no-login convergence or wake phrase performance without human/target evidence.

M10.6 is now host-verified as a complete software/documentation/scaffold tranche. M10.7 remains the first valid gate for physical Raspberry Pi, SHT31, relay, PENGLIN, ELUTENG fan, systemd/reboot and voice/wake acceptance.

## V09 implementation checkpoint 13 — bounded CI module runner

Host-side quality work now includes a bounded per-module unittest runner. `scripts/ci.sh` still executes the T0 static gates and the T1 unit/integration suites, but each test module runs as an independent subprocess with an explicit timeout, heartbeat output, per-module log file and JSON manifest. This does not reduce the required test set; it makes a broad run auditable when a module is slow, interrupted or failed.

This checkpoint addresses the previous false-unknown quality state where monolithic aggregate runs could be interrupted without identifying the active module. It does not close physical M10.7 acceptance and it does not claim that the heavier release lifecycle aggregate has passed in this container. The release lifecycle is now observable and bounded; completing it still requires either a long enough host run or further decomposition of the release end-to-end fixture.

### Checkpoint 14 — Release lifecycle CI decomposition

Checkpoint 14 keeps V09 in the host-verifiable quality phase and does not add new physical acceptance claims. The bounded unittest runner now supports two execution granularities: module-level for ordinary unit/integration modules and case-level for release lifecycle E2E cases that are heavier and need finer evidence. `scripts/ci.sh` runs `tests.integration.test_release_lifecycle_process` separately with `--granularity case`, and the release-only/default-boundary E2E test has been decomposed into named build/freeze, repeat/idempotency, target-boundary and low-space cases.

This change improves observability and continuation safety without weakening release acceptance. The same host release behavior remains tested, but a future timeout now identifies the exact case rather than only the aggregate module. M10.7 physical Raspberry Pi evidence remains not-run.

## V09 implementation checkpoint 15 — CI phase selection and resumable host evidence

M10.6 host-quality tooling now includes phase-selectable `scripts/ci.sh` execution.  The canonical default remains the complete T0/T1 host check order, but operators may now run `--phase t0`, `--phase unit`, `--phase integration` and `--phase release-lifecycle` independently, or combine phases explicitly.  This does not reduce test coverage or acceptance criteria; it makes long host evidence collection resumable when an external session boundary interrupts a full aggregate run.

The change is limited to CI orchestration and tests.  It does not alter environment runtime behavior, daemon polling, CLI/voice control, installer actuation, SHT31 reads, relay control, or physical acceptance.  M10.7 remains the first gate allowed to claim real Raspberry Pi SHT31/relay/fan/audio/wake behavior.

## 22. V09 simulation/HIL blueprint extension and continuation plan (2026-09-15)

### 22.1 Governing expansion prompt and execution boundary

Checkpoint 16 is governed by `GonKenAgent_V09_CKPT15_to_Simulation_HIL_Blueprint_Expansion_Master_Prompt_V2_GOLD.md`.  Its execution mode is blueprint/control-plane expansion only: no simulation runtime, GPIO behavior, I2C behavior, production environment CLI, production daemon logic or runtime wake phrase is changed in this checkpoint.

The current checkpoint-15 package remains the implementation baseline.  Its M10.6 host behavior is preserved, and M10.7 real Raspberry Pi HIL/release acceptance remains not-run.  The purpose of checkpoint 16 is to make the next implementation tranches precise, safe, staged and cold-resumable.

### 22.2 New V2 product decisions

The next implementation line SHALL add first-class simulation and hybrid-HIL support through the same environment service, policy, controller, IPC, CLI, diagnostics, voice boundary and evidence discipline as physical hardware.  Sensor simulation and actuator simulation are independent backend axes, not a single ambiguous `simulation=true` flag.

The shipped/default wake phrase SHALL become `GonKen`.  Real Pi wake testing remains required for tuning and final evidence, but it is no longer a gate to adopting the one-word phrase.  The previous `Hey GonKen` form should remain an accepted recognition alias unless collision tests prove otherwise.

Checkpoint 16 also records two safety/design defects to fix before user-test handoff:

1. `env serve --check` is not yet proven non-actuating because cleanup can call an actuator safe-off path that lazily opens GPIO.
2. `env watch` is not yet a passive tail-like observer because repeated sensor-read IPC can alter sampling, recovery and controller timing.

### 22.3 Simulation architecture

Simulation is implemented as adapters behind the single `gonken-environment.service` owner:

```text
sensor_backend = sht31 | simulated
relay_backend  = libgpiod | simulated
```

This produces four supported operating/evidence modes: full simulation, simulated sensor plus real actuator, real sensor plus simulated actuator and full physical.  All outputs must report backend provenance and physical evidence boundaries.  A Raspberry Pi run with simulated backends is target execution, but not physical sensor/fan acceptance.

The authoritative design details are in `docs/development/V09_SIMULATION_HIL_EXTENSION_PLAN.md` and the requirement-to-checkpoint mapping is in `docs/development/V09_SIMULATION_HIL_TRACEABILITY.csv`.

### 22.4 Checkpoint sequence for the extension

#### M10.8 Simulation/HIL blueprint expansion

Update the authoritative blueprint/control artifacts for independent sensor/actuator simulation, hybrid HIL, passive watch, non-actuating checks, simulation-aware voice, autonomous announcements, mandatory high-recall `GonKen` wake, hardware setup documentation, documentation quality gates, evidence separation and the continuation plan.  This is a planning/control checkpoint only; no runtime simulation feature is claimed.

#### M10.9 Simulation foundations

Implement static config validation for `sensor_backend=simulated` and `relay_backend=simulated`, explicit backend factories, simulated sensor and actuator adapters, daemon-owned ephemeral simulation state, simulation provenance fields, protocol operations and core unit tests.  This checkpoint must not require real hardware and must not change the physical acceptance state.

#### M10.10 Operator simulation experience

Implement `gonken-agent env simulate ...` commands, passive `env watch`, simulation fault injection, backend/provenance status, diagnostics/support/dashboard simulation visibility and full-simulation acceptance tests.  Watch must use a passive snapshot operation rather than causing extra samples or actuator reconciliation.

#### M10.11 Hybrid HIL and simulation-aware voice

Implement and test simulated sensor plus real actuator, real sensor plus simulated actuator, voice response provenance, hybrid evidence classification and physical-runner refusal when simulated backends are active.  Physical actuation remains gated by explicit operator configuration and target evidence.

#### M10.12 Mandatory GonKen wake, responsiveness and transition announcements

Implement `GonKen` as the shipped/default wake phrase, retain backward-compatible `Hey GonKen` recognition, add a recall-first tolerant matcher and fixture corpus, reduce capture/transcription blind gaps with overlapping or continuous standby analysis, add wake diagnostics, add post-question progress cues generated locally with Piper, and add voice-owned autonomous environment transition announcements with one-audio-owner arbitration.

#### M10.13 Documentation and evidence hardening

Create or revise README, `docs/HARDWARE_SETUP.md`, `docs/ENVIRONMENT_CONTROL.md`, `docs/SIMULATION.md`, `docs/OPERATIONS.md`, `docs/TROUBLESHOOTING.md`, physical acceptance docs and evidence runners.  Add documentation checks for paths, commands, options, services, config keys, wake phrase consistency, simulation/physical separation and cross-links.

#### M10.14 User simulation and sensor-deferred HIL release candidate

Produce the first user-test package labelled `READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL` if and only if full simulation, sensor-deferred real-fan testing, voice/manual fan controls, live watch, evidence export, rollback/recovery and documentation gates pass.  If SHT31 remains unavailable, keep the SHT31 physical gate BLOCKED while allowing real-relay/fan and simulation/hybrid testing to proceed.

#### M10.15 Target installer/runtime dependency repair and evidence hardening

Repair the Raspberry Pi target failure discovered by the first checkpoint-23 campaign before any relay actuation resumes.  The Pi target release must deliberately expose the Debian-managed `python3-libgpiod` and `python3-smbus` bindings to the immutable application virtual environment while development profiles remain isolated.  Candidate validation and a separate target-install step must execute import/API checks with the actual release interpreter under both long-running service-account contexts before installation can proceed to appliance readiness.

The installer must authorize the validated non-root invoking operator for the `gonken-envctl` control socket only; it must never grant that operator raw `gpio` or `i2c` privilege.  The installer must make the required login-session refresh explicit.  A root-owned, non-actuating maintenance helper may create the exact sensor-deferred profile only when the site configuration is absent, must refuse to overwrite divergent administrator configuration, and must never start the environment service or acquire GPIO/I2C resources.

Support/diagnostic export must bind evidence to the active immutable release commit/profile, report whether the application interpreter can use the required hardware APIs, report distro package versions, preserve safe health reason codes and legitimate `inactive`/`disabled` service states, and include only bounded content-free installer/service event codes.  Target acceptance remains BLOCKED until the repaired exact checkpoint reaches governed `INSTALLATION_COMPLETE`, the fresh operator login can use the environment control socket, and the target runtime-binding gate is READY.

### 22.5 Target evidence after user upload

After the user runs the target package and uploads evidence, the next development session must verify package identity and configuration, classify each evidence item as full simulation, hybrid or physical, identify root cause for failures, fix the smallest correct layer, rerun affected host checks, issue the next package and rerun only uncertain target tests.  Do not restart architecture discovery.

### 22.5 Checkpoint 17 — Simulation foundations implementation

Checkpoint 17 implements the first runtime layer of the V09 simulation/HIL extension.  It adds independent simulated sensor and simulated actuator backends behind the existing environment service boundary, rather than creating a separate CLI-owned simulator or weakening the physical controller architecture.

The static configuration schema now accepts `sensor_backend = "simulated"` and `relay_backend = "simulated"` as independent axes while preserving `sht31` and `libgpiod` as the physical backend names.  Simulation runtime mutation remains explicitly controlled by `simulation_runtime_control_enabled`; default configuration remains non-simulating and environment-disabled unless deliberately configured.

The new daemon-owned simulation state records a session identifier, generation, bounded event history, sensor value/fault state and actuator behavior.  Protocol operations for `simulation.status.get`, sensor set/fault/reset, actuator behavior/reset, `state.snapshot.get` and `events.get` expose this state through the same bounded AF_UNIX contract as physical environment operations.  These operations are host-verified, but they do not claim SHT31, relay, fan or Raspberry Pi acceptance.

Checkpoint 17 also closes one safety defect from checkpoint 16: `gonken-agent env serve --check` is now tested as a construction/configuration check that does not call the daemon shutdown safe-off path and therefore does not request or write a relay line merely to validate configuration.  Real daemon shutdown still retains safe-off semantics once resources have actually been acquired.

Remaining simulation/HIL work moves to the operator and evidence layers: `gonken-agent env simulate ...`, passive `env watch`, diagnostics/support/dashboard provenance, simulation-aware voice wording, hybrid HIL evidence classification, wake/progress work and documentation hardening.  M10.7 physical Raspberry Pi acceptance remains not-run.


### 22.6 Checkpoint 18 — Operator simulation experience implementation

Checkpoint 18 implements the user-facing operator simulation layer planned in M10.10.  The simulator remains inside the single environment-service boundary: `gonken-agent env simulate ...` is an IPC client, not a second hardware owner and not a direct policy-file editor.  Simulation mutations remain guarded by static backend axes and `simulation_runtime_control_enabled`; simulated-sensor commands are rejected when the sensor backend is physical, and simulated-actuator commands are rejected when the relay backend is physical.

`gonken-agent env watch` is now passive.  It calls `state.snapshot.get` and displays the daemon-owned latest state instead of repeatedly calling `sensor.read`.  This removes the observer effect identified in checkpoint 16: additional watch terminals should not create extra sensor samples, accelerate recovery, alter median windows, change dwell timing or trigger actuator writes.  `gonken-agent env read` remains the explicit active read-now operation.

Diagnostics, support bundles, public environment health and the loopback dashboard now carry simulation and snapshot summaries with backend provenance and `physical_evidence=false`.  This improves user simulation and later hybrid-HIL debugging without allowing simulated evidence to close physical Raspberry Pi acceptance.

### 22.9 Checkpoint 21 — Documentation and evidence hardening implementation

Checkpoint 21 implements the M10.13 host documentation/evidence gate. It adds dedicated user-facing documents for hardware setup, environment control, simulation/hybrid-HIL practice and troubleshooting, while preserving `OPERATIONS.md` as an operating overview rather than a single overloaded manual.

The checkpoint also makes documentation drift testable. `scripts/validate_v09_docs.py` is now part of T0 and checks required documentation files, local markdown links, documented command parsing, environment static config-key coverage, wake default consistency and boundary terms such as `physical_evidence=false`, `software_speed_control=false`, `fan_motion_observed=false`, `HOST_SIMULATION`, `TARGET_HYBRID_SENSOR_SIMULATED`, `TARGET_HYBRID_ACTUATOR_SIMULATED` and `SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED`.

The M10.7 evidence runner is hardened at the manifest layer. It now records an explicit `evidence_boundary`, the required upload set and manual gate identifiers. The runner remains an evidence collector, not an acceptance oracle. JSON success cannot prove blade motion, wake/audio behavior, PENGLIN continuity, relay polarity or SHT31 placement.

This checkpoint closes M10.13 at host/documentation level only. It does not close M10.7 real Raspberry Pi acceptance and does not prove any physical sensor, relay, fan, wake or systemd/no-login behavior.


### 22.10 Checkpoint 22 — M10.14 user-test release-candidate gating

Checkpoint 22 implements the host/software gate for the first supervised user simulation and sensor-deferred HIL handoff. The release-candidate label is `READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL`; it is a statement that the package has passed its host readiness gates for supervised target testing, not a Raspberry Pi physical-acceptance verdict. M10.7, SHT31 physical acceptance, relay/PENGLIN/fan physical behavior, blade motion, target wake/audio behavior and reboot/no-login convergence remain `NOT_RUN` until target evidence exists.

The checkpoint adds two explicit gate layers. `scripts/environment_simulation_runner.py` drives a fresh full-simulation campaign through the public AF_UNIX/CLI boundary, including manual fan control, AUTO hysteresis, SEMI explicit-start/no-autostart semantics, stale-sensor safe-off/recovery and passive-watch non-observer behavior. It also validates the simulated-sensor/libgpiod profile through the existing non-actuating `env serve --check` path; this proves construction/configuration readiness only and never toggles GPIO. `scripts/v09_user_test_readiness.py` then requires the established host milestones, documentation gate, base release-readiness gate, required handoff files and a fresh commit-bound simulation manifest whose physical-acceptance fields remain false/`NOT_RUN`.

A dirty development tree can produce only `DEVELOPMENT_READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL` when the explicit development override is used. The final user-test label requires a clean tree and a simulation manifest bound to the exact current commit. This prevents an old or unknown-commit manifest from being reused as fresh release evidence.

The target handoff is `docs/USER_SIMULATION_HIL_HANDOFF.md`. It orders testing from full simulation to supervised relay/fan work. Before any real actuator command, the operator must inspect GPIO character-device mapping and wiring. **Historical checkpoint-22 state:** the adapter still assumed `/dev/gpiochip0` line offset 23 for the configured BCM23 seed. Checkpoint 23 resolves that software assumption by discovering a unique kernel line named `GPIO23` and exposing the resolved gpiochip/offset through environment status; actual target line identity, relay polarity, wiring and fan motion remain physical gates.

Checkpoint 22 therefore closes only M10.14's host/software readiness tranche. It deliberately leaves M10.7 open for evidence-driven continuation after the user uploads the target support/evidence bundle.


### 22.11 Checkpoint 23 — Pre-target completion audit and false-green repair

Checkpoint 23 is the final dependency-ready **host/software** tranche before the Raspberry Pi campaign. It does not add a new V09 product milestone merely to create work after M10.14; instead it audits the already-declared blueprint against the production runtime, repairs host-visible false-green gaps, refreshes control-plane truth, and prepares an exact-package target handoff.

The audit found three material gaps that checkpoint-22 readiness had not exposed. First, checkpoint 20 had improved the `GonKen` transcript matcher but the production wake loop still stopped capture while Whisper synchronously transcribed each window. Checkpoint 23 replaces that intentional deaf interval with a bounded producer/consumer wake pipeline: capture continues while the previous window is recognized, only one Whisper consumer runs, the queue is bounded and newest-wins, stale windows are dropped with content-free metrics, and standby is stopped before the assistant speaks or captures the active question. This closes the **software architecture** requirement for overlapping/continuous wake capture; it does not claim physical wake recall.

Second, the configured push-to-talk and privacy-indicator GPIOs had controller/configuration coverage but no production libgpiod adapter. Checkpoint 23 adds production PTT GPIO17, wake-monitoring GPIO22 and recording-LED GPIO27 ownership through unique kernel line-name discovery, with fail-closed handling for absent/ambiguous mappings and safe LED-off acquisition/cleanup behavior. Host fakes prove the contract; target wiring and visible behavior remain not-run.

Third, the room-fan relay still treated the logical BCM23 seed as `/dev/gpiochip0` offset 23. Checkpoint 23 removes that assumption. `relay_bcm` remains the operator-facing logical identity, while production resolves a unique kernel line named `GPIO23`, reports the actual gpiochip path/offset in status/health, and refuses actuator acquisition if the identity is missing or ambiguous. This reduces target risk without pretending to prove active-high polarity, boot pulses, contact wiring, PENGLIN continuity or blade motion.

Checkpoint 23 also makes a downloaded acceptance archive installable as the **exact tested source**. `./bootstrap.sh --local-checkpoint` validates a clean packaged Git checkout, records its full HEAD commit as the source identity and uses that checkout as the immutable-release source. The ordinary remote HTTPS/`main` installation path remains the production default. The target acceptance runbook now requires checksum/Git verification followed by `--local-checkpoint`, preventing an acceptance campaign from silently switching to newer remote code.

The control plane is corrected at the same checkpoint. M4.2, M4.3, M5.1, M5.2 and the privacy-safe core of M7.3 are host-verified software with real-device acceptance still open. Persistent interaction-content logging is explicitly outside release-core unless a separate research/privacy protocol authorizes it. M7.1, M7.2 and M7.5 remain partial because synthetic fixtures cannot replace the approved real lab corpus, real-model factual/adversarial evaluation, or real-device benchmark. M9.1 and M10.7 remain target campaigns by definition. Historical planned rows for M10.9–M10.14 are marked superseded by their executed checkpoint evidence rather than remaining misleadingly `PLANNED / NOT_RUN`.

The **target campaign order** is now:

1. verify the delivered checkpoint ZIP, commit, clean Git state and readiness report;
2. install that exact commit using `./bootstrap.sh --local-checkpoint`;
3. prove ordinary `GonKen` wake/audio and manual `talk`;
4. collect GPIO17/22/23/27 character-device identities;
5. prove PTT and indicator behavior if wired;
6. run full environment simulation;
7. run supervised real-relay/fan manual testing, then simulated-sensor + real-actuator HIL;
8. when SHT31 is available, run real-sensor + simulated-actuator before full-real integration;
9. run reboot/no-login, safe failure/recovery, offline-boundary and performance observations;
10. collect the M10.7 private ledger and support bundle and upload all FAIL/BLOCKED/NEEDS_MANUAL_REVIEW evidence without local relabelling.

Checkpoint 23 may be labelled **`READY_FOR_RASPBERRY_PI_TARGET_CAMPAIGN`** only after fresh whole-project host phases, final documentation/control consistency, exact-commit simulation/readiness gates, and fresh-archive package verification pass. The label is not a physical acceptance claim. If target evidence later exposes a defect, continue from checkpoint 23, fix the smallest correct layer, rerun affected host regressions, issue the next checkpoint and repeat only the uncertain target gates.


## V09 implementation checkpoint 24 — target installer/runtime dependency repair

Checkpoint 24 is an evidence-driven repair of the first real Raspberry Pi installation campaign, not a reopening of the V09 architecture.  Checkpoint-23 target evidence established that Raspberry Pi OS/Trixie had installed `python3-libgpiod` and `python3-smbus` successfully, while the immutable GonKen application venv remained isolated from Debian `dist-packages`.  The production voice service consequently looped on `WAKE_LED_GPIO_DEPENDENCY_MISSING`; the same interpreter boundary would also block production PTT/recording LEDs, GPIO23 relay control and the SHT31 SMBus adapter.  The target also showed that the human login account was not a member of the `gonken-envctl` socket-client group.

The repair keeps the existing one-hardware-owner and least-privilege model.  Only the `core-pi-trixie-py313` release profile is constructed with system-site package visibility; development releases remain isolated.  Release validation executes a bounded hardware-binding API probe using the release interpreter, and the target installer adds a second validation as the `gonken-env` account after account provisioning.  The ordinary release validation path still validates the same release as the `gonken-agent` account, so both production service identities are covered.

The validated invoking non-root operator is added only to `gonken-envctl`; raw `gpio` and `i2c` groups remain reserved for the hardware-owning service account.  Because Linux supplementary-group changes do not alter the already-running login shell, successful installation emits an explicit reconnect requirement before operator environment CLI acceptance.

A new non-actuating `environment_profile_manager.py` creates the exact sensor-deferred `simulated`-sensor/`libgpiod`-actuator site profile only when no site file exists and refuses to overwrite a different administrator-owned configuration.  It never starts services, requests GPIO/I2C devices or claims physical evidence.  Support bundles now export bounded release/runtime-binding/package provenance, allow-listed installer and service event codes, and health reason codes without transcripts or raw journals.

Checkpoint 24 remains host/software evidence until the exact packaged checkpoint is installed on the Raspberry Pi.  Physical relay actuation is explicitly blocked until that installer reaches `INSTALLATION_COMPLETE`, the active release commit matches the delivered archive, application-runtime bindings pass on target, a fresh login has `gonken-envctl`, and GPIO23 mapping is reverified.


## 23. V09 comprehensive-closure blueprint and dependency convergence (2026-09-16)

The implementation-grade remaining-work specification is `docs/development/V09_COMPREHENSIVE_CLOSURE_BLUEPRINT_CHECKPOINT_25.md`. It is authoritative for the checkpoint-25 continuation where it refines older V09 text. Existing verified architecture remains preserved. Physical target evidence remains separate from host/simulation evidence.

#### M10.16 Comprehensive closure blueprint and quality-system reconstruction

Reconstruct current state from checkpoint 24 and real target evidence; model dependencies, work packages, false-green controls, SHT31/I2C readiness, lifecycle, package/Git and checkpoint rules before invasive implementation.

#### M10.17 Target Python dependency boundary redesign

Replace the checkpoint-24 broad system-site-packages dependency boundary with a controlled architecture that exposes only required distro hardware bindings or otherwise scopes dependency validation so unrelated target packages cannot invalidate a GonKen release while required APIs remain fail-closed.

#### M10.18 Installer convergence DAG, preflight and failure-evidence hardening

Turn installation into prerequisite/postcondition convergence across clean, dirty, partial and interrupted target states; produce candidate/installer evidence even when the active release is old or absent.

#### M10.19 Accounts, groups, configuration and environment-profile convergence

Prove least-privilege service/operator memberships, file/socket/device ownership and governed simulation, hybrid and full-real environment profile creation/verification without implicit actuation.

#### M10.20 Systemd runtime, service-context and audio closure

Verify application/environment/Ollama runtime contexts, no-login/restart behavior, PipeWire/BlueZ device readiness and fallback paths rather than equating process-running with appliance-ready.

#### M10.21 SHT31/I2C and environment simulation-hybrid-full-real readiness

Complete I2C enablement/reboot/device/service-user convergence, audit/correct exact SHT31 wire-protocol transactions, add bounded sensor diagnostics, preserve simulation parity and prepare all four backend combinations with target/physical gates.

#### M10.22 Voice/environment end-to-end transaction closure

Prove deterministic CLI/voice environment actions and queries through the environment daemon, preserve simulation/hybrid truthfulness and protect wake/audio arbitration and safe failure behavior.

#### M10.23 Clean/dirty lifecycle, support, documentation, package and Git closure

Run clean/dirty/interruption/update/rollback/reinstall host/target-shadow campaigns, strengthen support/privacy diagnostics, synchronize documentation, and package a clean portable Git checkpoint with executable modes/checksums/provenance.

#### M10.24 Final Raspberry Pi environment and release acceptance

Run the exact-package target campaign through installation completion, runtime/audio readiness, real relay/fan, real SHT31, controller modes, voice/wake, fault recovery, reboot/no-login and update/rollback. This remains target-gated until executed.

#### M10.25 Target activation contract migration and upgrade compatibility repair

Preserve strict current-candidate release validation while allowing only a trusted journal-bound pre-bridge current/previous release to serve as a bounded transition source. Prove exact upgrade migration, strict arbitrary-candidate refusal, rollback/status compatibility, interruption recovery and diagnostic provenance before returning to M10.24 target acceptance.

### Checkpoint 27 implementation refinement — M10.18/M10.19

M10.18 now places a source-owned, non-actuating target prerequisite gate before account/release construction and creates a private installer-owned failure bundle if any later step fails. Required core voice/GPIO prerequisites fail closed; optional real-SHT31 readiness is reported without making the generic environment-disabled install impossible.

M10.19 now treats environment configuration as four explicit parity profiles (`full-simulation`, `sensor-deferred-relay`, `real-sensor-simulated-actuator`, `full-real`). The helper may create a missing managed profile or atomically transition between exact managed profiles; it refuses unknown administrator configuration and never starts services or touches hardware. A second target preflight verifies service identities and `gonken-envctl` client authority after account convergence.

## Checkpoint 28 implementation refinement — runtime, SHT31/I2C and voice transaction

Checkpoint 28 implements M10.20-M10.22 host closure under the checkpoint-25 comprehensive blueprint. Runtime-context readiness is now an explicit prerequisite rather than something first discovered at final appliance readiness. The SHT31 transport uses raw I2C command/read semantics, with CRC validation, heater-off/status safeguards and a bounded 100-read target diagnostic. I2C platform enablement, reboot-required state and service-user device access are governed separately from sensor-address probing.

Evidence classification is also strengthened: a daemon configured with `sht31` plus `libgpiod` reports `TARGET_REAL_BACKENDS_UNVERIFIED`. Physical acceptance cannot be created from backend names. The deterministic voice path is verified through the real environment Unix socket and remains a client of the single-owner daemon.

The next host tranche is M10.23 lifecycle/support/documentation/package/Git closure. M10.24 remains exact-package Raspberry Pi acceptance and includes the already established GPIO23/fan facts plus the forthcoming real SHT31 and voice/audio evidence.

## Checkpoint 29 implementation refinement — M10.23 host closure

M10.23 is host-verified after bounded full-unit accounting (44 modules / 435 tests), complete integration-family accounting (12 modules / 57 tests), 8/8 release lifecycle cases, 5/5 Ollama lifecycle cases and 5/5 speech lifecycle cases. Support export adds allow-listed GPIO23 identity and dedicated runtime-context summaries while retaining the no-raw-log/privacy boundary. Target hardware/SHT31 documentation now matches the isolated gpiod binding bridge and raw Linux I2C sensor transport.

Release readiness requires M10.16-M10.23 and explicitly leaves M10.24 target acceptance open. M10.24 software/runbook prerequisites are host-verified, but target state remains `not-run`; only exact-package Raspberry Pi evidence may close fan/sensor/audio/voice/reboot/update/rollback gates.

## Checkpoint 30 implementation refinement — target activation migration repair

**Triggering target evidence.** On the Raspberry Pi 5, the actuator substrate is physically demonstrated: GPIO23 resolves to `gpiochip0` line 23; explicit LOW stopped the KKHMF/ELUTENG load, HIGH started it, and returning LOW stopped it. Checkpoint 29 then reached target prerequisite preflight, built the new immutable release successfully, and failed during `activate_release` with `RELEASE_BINDING_MANIFEST`. Re-running reached the same deterministic boundary. This does not invalidate the physical fan evidence and does not close M10.24.

**Root cause.** Checkpoint 29 correctly made bridge-era target candidates strict, but activation reconciliation applied that new manifest/API contract retroactively to the previously active release. The active Pi release predates the binding bridge and therefore can never satisfy the later manifest contract. The candidate itself had already passed build/final validation. The failure was an upgrade-state compatibility defect, not candidate construction failure.

**M10.25 contract.** Release evolution must model two different trust questions:

1. **Current candidate:** always satisfy the current strict manifest, isolated-runtime, binding API, immutable-payload and smoke contracts. No arbitrary pre-bridge candidate may be activated.
2. **State-bound legacy transition source:** only a release already established by the activation journal/current pointer as a prior post-verified release may use bounded compatibility to permit migration away from it. Structural immutability, release-record/owner integrity and service-user CLI identity/status smoke remain mandatory.
3. **Anti-downgrade/false-green rule:** absence of a manifest is insufficient to call a release legacy. The immutable embedded release manager must predate the bridge markers. A bridge-era release with a lost/corrupt manifest remains invalid.
4. **Rollback:** a journal-bound previous pre-bridge release remains a permitted rollback target under the same bounded transition validation. Normal activation continues to reject that same release if it is presented as an arbitrary candidate.
5. **Observability:** binding validation errors identify the release commit being checked; `RELEASE_LEGACY_TRANSITION_SOURCE` is emitted when bounded compatibility is legitimately used.
6. **Regression protection:** unit and process integration tests must reproduce the exact old-post-verified-release → new-bridge-candidate migration, preserve strict candidate rejection, exercise rollback/status, activation interruption, post-switch rollback and finalization interruption.

**Target continuation.** Package checkpoint 30 from the clean committed source. On the Pi, do not delete the old active release, activation journal or binding files manually. The corrected installer must migrate from the recorded legacy release, activate the strict new candidate, and reach governed `INSTALLATION_COMPLETE`. Only then resume M10.24 from GonKen-integrated CLI/service/audio/SHT31/voice stages. Physical GPIO23 wiring discovery does not need to be repeated unless new evidence contradicts it.


#### M10.26 Target install convergence, planned reboot and voice prerequisite hardening

Checkpoint 30 advanced materially on the real Raspberry Pi: the new strict release activated successfully, proving the checkpoint-29 current-release migration fix. The install was nevertheless reported failed after `ACTIVATION_COMPLETE` because best-effort pruning revalidated an unrelated older historical release against today's hardware-binding contract. A subsequent local rerun correctly treated activation as satisfied, authorized the operator, passed target identity checks and reached I2C enablement, where the installer requested a reboot before `INSTALLATION_COMPLETE`. The post-run support bundle then showed the current checkpoint-30 release/binding bridge and `/dev/i2c-1` ready.

**M10.26 contract.** Installation convergence must be modeled as a dependency graph, not a sequence of independent one-error patches. The repaired package shall therefore enforce all of the following together:

1. **Activation versus cleanup boundary.** Once a strict candidate is switched, post-verified and journaled, stale historical release garbage collection is best-effort maintenance. Pruning may statically verify stale immutable records before deletion, but it must not execute them or retroactively require today's runtime/binding contract. A malformed or undeletable stale release is retained with bounded `RELEASE_PRUNE_SKIPPED` evidence and cannot turn completed activation into install failure.
2. **Planned reboot semantics.** I2C enablement waits a bounded interval for `/dev/i2c-1`. If the device converges in the current boot, installation continues. If a reboot is genuinely required, the install engine records a `paused` step and exits with the governed planned-transition code; it must not emit generic `INSTALL_ACTION`, mark the step failed or generate a misleading failure bundle. Re-running the same exact checkpoint after reboot revalidates and resumes.
3. **Audio-input prerequisite closure.** When Bluetooth audio is requested, pairing may not claim the audio prerequisite complete merely because playback exists. Before the expensive appliance-readiness gate, the exact service user must enumerate either a Bluetooth HFP/HSP capture source or exactly one deterministic direct ALSA capture fallback. Zero routes fail early as `BLUETOOTH_INPUT_UNAVAILABLE`; ambiguous direct capture fails closed as `AUDIO_INPUT_AMBIGUOUS`. Actual recording/playback remains the later physical appliance gate.
4. **Release-bound readiness.** `/run/gonken-agent/ready.json` carries the immutable release commit. A stale readiness record from a previous release cannot satisfy the new release's appliance-readiness postcondition; the service must restart and prove readiness for the exact current commit. Install summary uses the same invariant.
5. **Explicit dependency ordering.** Regression tests lock the target order: distro prerequisites and target preflight -> runtime account/layout -> strict immutable release/activation -> environment identities -> I2C platform -> runtime binding contract -> environment service structure -> model/speech artifacts -> application service -> Bluetooth stack/pairing/input route -> runtime context -> physical appliance readiness. Environment hardware remains non-actuating until a supervised profile is selected after governed installation.
6. **No target-only patching.** Existing target state is diagnostic evidence, not a reason to hand-edit immutable releases, fabricate manifests, bypass microphone selection, add broad privileges or manually mark installer steps complete. Any remaining target failure returns to the smallest correct source layer with a regression test.

**Acceptance.** Host acceptance requires focused reproduction of both checkpoint-30 target transitions, dependency-order regression, complete affected unit/integration accounting, release/rollback/interruption non-regression, documentation/readiness synchronization and clean package verification. Target acceptance remains M10.24 and requires exact checkpoint-31 installation to reach `INSTALLATION_COMPLETE` followed by observed audio/voice/environment evidence.


#### M10.27 Current-release immutable seal and post-seal runtime isolation repair

**Triggering target evidence.** Exact checkpoint 31 (`8c9bd8b6a657f1a793c038bec8319d1f868315c7`) built successfully on the Raspberry Pi but activation repeatedly failed with `RELEASE_INVALID: release payload digest differs`, including after reboot. The accompanying support bundle showed the previously active checkpoint-30 release, its isolated hardware-binding bridge, GPIO23 mapping and `/dev/i2c-1` platform state were READY. The checkpoint-31 failure was therefore a defect in the new candidate's own immutable lifecycle, not a legacy-release dependency.

**Root cause.** The checkpoint-31 builder performed executable runtime smoke, recorded `payload_sha256`, froze/renamed the release, and then ran executable validation from the sealed tree. Python runtime execution may create `__pycache__`/`.pyc` artifacts. Those files were not part of the recorded digest, so the release mutated itself after the immutable seal and later static validation correctly rejected it. Rebooting or comparing older releases cannot repair this state.

**Current-release contract.**

1. All CLI identity, `pip check` and target binding API smoke must complete **before** the immutable payload is sealed.
2. Before sealing, remove interpreter/build transients (`__pycache__`, `.pyc`, `.pyo`, `.pytest_cache`), normalize candidate readability for the service account, and write a bounded payload manifest that can localize later drift.
3. Record the payload digest only after all executable checks and transient cleanup. Freeze/rename atomically afterwards.
4. After sealing, build postconditions, activation, reconciliation and ordinary status may perform only non-mutating static identity/integrity/ownership checks against the **current candidate/current release**.
5. The target hardware-binding API probe is a separate installer gate (`bindings-check`) after activation and must address the current release only. It is not part of historical-release reconciliation.
6. Previously active/historical releases are not normal-runtime dependencies and must not be executed or revalidated to establish current-release health. Historical identity is retained only for explicit rollback/update bookkeeping. An operator-requested rollback may validate the recorded previous release because that operation intentionally selects it as the new current release.
7. Running the sealed CLI must not change its payload digest or create bytecode/cache artifacts inside the immutable release tree.
8. Long lifecycle checks must be structurally decomposable. Speech lifecycle now has a dedicated case-bounded CI phase so an interruption scenario cannot monopolize a module-level run.

**Acceptance.** Host acceptance requires exact build->pre-seal smoke->purge->seal->static validation->activation->repeat tests, tamper rejection, current-only migration, interruption/finalization checks, complete unit/integration accounting, documentation/readiness synchronization and clean package verification. Target acceptance remains M10.24 and requires checkpoint 32 to reach `INSTALLATION_COMPLETE` before integrated fan/sensor/voice claims.

#### M10.28 Same-commit runtime stability, optional audio fallback and Pi5 GPIO convergence

**Triggering target evidence.** Exact checkpoint 32 (`636285827c8947ba689400c9b1dc217ea5521130`) built and activated successfully on the Raspberry Pi, passed target runtime binding, I2C, Ollama, speech and application-service gates, then stopped because the preferred AIRHUG Bluetooth address was paired but could not connect. Immediately afterwards, both the remote curl launcher and local checkpoint path for the same commit failed much earlier at `immutable_release` with `RELEASE_ACTIVE_INVALID`. The support bundle independently showed one deterministic AIRHUG USB capture route and one USB playback route, an SHT31-visible I2C platform, a healthy current `gpiod` bridge, and repeated `WAKE_LED_GPIO_LINE_AMBIGUOUS` service events.

**Root causes and contract.**

1. **Derived Python caches are not authoritative release payload.** Privileged post-seal Python entry points can create `__pycache__`, `.pyc` or `.pyo` files even below mode-0555 directories. The installer and managed services must set `PYTHONDONTWRITEBYTECODE=1` and `PYTHONNOUSERSITE=1`. If a same-commit active release differs from its recorded payload *only* by recognized Python runtime-cache artifacts, the installer may remove those derived artifacts and revalidate static integrity. Any authoritative source, configuration, executable, manifest or release-record drift remains fatal and must never be auto-repaired.
2. **Current-release convergence is independent of historical releases.** Normal bootstrap, curl install, service start and same-commit rerun operate on the requested/current commit. Historical releases remain only explicit update/rollback bookkeeping and cannot be prerequisites of ordinary runtime health.
3. **Bluetooth is a preferred optional route.** A requested Bluetooth address may be busy, powered off or connected to another host. If the exact service user can prove one deterministic direct capture route and one deterministic non-HDMI playback route (for example a USB AIRHUG device), installation continues with bounded `BLUETOOTH_OPTIONAL_UNAVAILABLE` plus `AUDIO_DIRECT_FALLBACK_READY` evidence while autoconnect may retry later. Zero or ambiguous fallback remains a real error; the installer never guesses among multiple devices.
4. **Managed-unit upgrade compatibility is explicit.** Adding bytecode-suppression environment lines changes systemd template digests. Checkpoint-32 application, environment and Bluetooth-autoconnect unit hashes are accepted as known managed predecessors so a legitimate upgrade does not become a service-file conflict. Unknown/local administrator modifications remain fail-closed.
5. **Pi5 header GPIO resolution uses controller identity, not gpiochip numbering.** The target is Raspberry Pi 5. When duplicate `GPIO<n>` names occur across gpiochips, the resolver may select a match only when exactly one candidate belongs to chip metadata labelled `pinctrl-rp1`; it must not assume `/dev/gpiochip0`. If no unique RP1 match exists, the adapter still fails closed. The rule covers PTT GPIO17, wake LED GPIO22, room-fan relay GPIO23 and recording LED GPIO27.
6. **Entry-path equivalence.** `install-gonken.sh`/curl remains a source-fetching launcher that forwards into the same governed `bootstrap.sh`/`install.sh` engine. Local-checkpoint and remote-main modes may differ in source provenance, but once they resolve the same commit their release/install convergence rules are identical and repeated execution must be idempotent.

**Acceptance.** Host acceptance requires same-commit transient-cache repair plus authoritative-tamper refusal, Bluetooth-busy/direct-USB success and no-fallback/ambiguity refusal, managed predecessor upgrades, RP1 duplicate-name resolution, complete unit/integration/lifecycle accounting, documentation/readiness consistency and exact-archive verification. Physical M10.24 remains open until exact checkpoint 33 reaches `INSTALLATION_COMPLETE` and the real CLI/SHT31/full-real/wake/fault/reboot/update/rollback campaign is observed.

#### M10.29 Authoritative runtime boundary, transport-neutral audio and early Pi5 GPIO identity convergence

**Triggering target evidence.** Exact checkpoint 33 (`e5d05d105228d4cb8cf81201435d122a89435e6f`) built and activated on the Raspberry Pi and advanced through target identity, I2C, runtime bindings, environment service, Ollama, Whisper, Piper, speech smoke, application service, Bluetooth/autoconnect and runtime-context validation. The running `gonken-agent.service` then remained in `WAKE_LED_GPIO_LINE_AMBIGUOUS` for GPIO22 until the final 180-second appliance-readiness gate failed. This proves the next defect is target GPIO identity convergence, not release activation. Earlier evidence remains valid for physical GPIO23 relay/fan actuation, SHT31 `0x44` visibility on `/dev/i2c-1`, and deterministic AIRHUG USB capture/playback.

**Immutable runtime authority.** The release authority boundary SHALL be defined once and reused by payload digest, path manifest, owner checks and mutability checks. A real non-symlink `__pycache__` directory and only `.pyc`/`.pyo` descendants are derived runtime cache, not authoritative release content. A symlink masquerading as `__pycache__`, a top-level bytecode file, any non-bytecode file hidden in a cache tree, or any source/config/executable/manifest drift remains authoritative and invalidates the release. Normal same-commit convergence SHALL NOT rewrite a valid current release to repair cache drift; managed Python entry points SHALL suppress in-tree bytecode writes and validation SHALL ignore only the narrowly defined derived cache class.

**Current-only runtime.** Normal installation, service startup and appliance operation SHALL evaluate the requested candidate/current release and SHALL NOT execute or revalidate historical releases as prerequisites. Historical release content is retained only for explicit update/rollback bookkeeping. Integrity errors continue to protect the authoritative current payload; they are not a compatibility comparison against obsolete versions.

**Transport-neutral audio.** `--bluetooth-audio` designates a preferred transport, not permission to block the base appliance when one deterministic direct USB/wired capture route and one deterministic non-HDMI playback route are already usable. Bluetooth stack/pairing/autoconnect failures may degrade to explicit warnings only when that direct route is independently proven. Zero/ambiguous direct audio remains fail-closed. Runtime-context readiness evaluates usable physical audio, not whether PipeWire happened to be requested.

**Pi5 GPIO identity.** PTT GPIO17, wake LED GPIO22, room-fan relay GPIO23 and recording LED GPIO27 SHALL use one shared resolver. Resolution order is: globally unique line-name match; unique RP1 metadata match; unique coherent Pi-header topology match containing the project header signature. The resolver SHALL inspect metadata only, SHALL NOT request a line during discovery, SHALL NOT assume `/dev/gpiochip0`, and SHALL NOT assume BCM equals line offset. If multiple coherent header candidates remain, resolution fails closed with bounded candidate details.

**Early target gate.** A non-actuating `target_gpio_identity` installer step SHALL run after current-release runtime bindings and before environment/application service readiness. It proves GPIO17/22/23/27 resolve to one coherent header chip under the actual service-user context and records a private structured artifact. A mapping problem therefore fails early rather than consuming the appliance-readiness timeout. The production PTT/wake/relay adapters use the same resolver so installer PASS cannot diverge from runtime behavior.

**Repeated-entry convergence.** Local exact-checkpoint bootstrap and the remote curl launcher SHALL converge through the same bootstrap/install/release state machine after resolving their source commit. Re-running a successfully installed same commit is required to be idempotent across runtime/service execution, derived cache creation, optional Bluetooth unavailability and reboot. Source-mode differences must not create separate release semantics.

**Host acceptance.** Complete unit accounting, deterministic integration, 12/12 speech lifecycle, 12/12 release lifecycle, adversarial authoritative-payload tests, USB/Bluetooth fallback tests, shared Pi5 GPIO resolver tests, early non-actuating GPIO preflight, installer ordering, documentation/milestone consistency, release readiness, T0 and exact-package integrity must pass. Interrupted aggregate wrappers are evidence of interruption only; all uncertain cases must be rerun at smaller granularity.

**Target acceptance.** M10.24 remains open. Exact checkpoint 34 must pass the early GPIO identity gate and reach `INSTALLATION_COMPLETE` without live-tree patching. Only then continue real GonKen CLI fan OFF/ON/OFF, SHT31 repeated reads, hybrid/full-real controller, wake/voice commands, fault recovery, reboot/no-login, update/rollback/reinstall and final support evidence.

#### M10.30 Post-checkpoint-34 reliability-first control plane and canonical GPIO alias identity

**Triggering evidence.** The post-checkpoint-34 reliability prompt and failure-pattern audit show that the project repeatedly fixed the latest reachable Pi failure while the next downstream target state remained untested. The latest reported checkpoint-34 class is `GPIO_HEADER_UNRESOLVED` where `/dev/gpiochip0` and `/dev/gpiochip4` both reported the same RP1/line identity for GPIO17/22/23/27. Treating device paths as hardware identity can create a false ambiguity.

**Reliability-first control plane.** The active blueprint SHALL no longer treat checkpoint 34 as the next user-facing candidate boundary. `docs/development/V09_POST_CKPT34_RELIABILITY_FIRST_BLUEPRINT.md` defines the forensic chronology, capability criticality, installer state model, target manifest schema, dirty-state matrix, host/target-shadow release-candidate gate, false-green review and WP-A through WP-M execution plan. A Pi candidate may not be produced until that host/target-shadow gate is complete and exact-archive verification passes.

**Canonical GPIO identity.** The shared GPIO resolver SHALL compute a canonical chip identity from the character-device major/minor and `/sys/dev/char` realpath when available. True aliases of the same kernel gpiochip are deduplicated before line-name, RP1 metadata or header-topology ambiguity decisions. The resolver output and preflight JSON SHALL include `canonical_chip_id` and `alias_paths` so future support bundles can explain why duplicate paths were or were not treated as one hardware controller.

**Fail-closed boundary.** Distinct plausible header controllers, including two non-aliased controllers with complete header-like topology, remain ambiguous and fail closed for the affected required feature/profile. The alias rule may never become a first-path-wins rule, may never hard-code `gpiochip0` or `gpiochip4`, and may never request or write a line during discovery.

**Host acceptance.** Host acceptance requires a regression proving duplicate `/dev/gpiochip*` paths with the same canonical RP1 identity deduplicate and pass, a regression proving distinct complete header-like controllers still fail, preflight JSON evidence fields for canonical ID/alias paths, focused GPIO unit tests, static syntax/compile checks, milestone/status synchronization and dirty-worktree review.

**Target acceptance.** Physical acceptance remains M10.24/WP-L. The exact future Pi candidate must capture a target hardware manifest before installation, replay it as a target-shadow fixture, pass early `target_gpio_identity`, reach `INSTALLATION_COMPLETE`, and then complete real fan, SHT31, voice, reboot/no-login, fault, update/rollback/reinstall and final support/privacy gates.

#### M10.31 Sanitized target manifest and target-shadow GPIO replay

**Purpose.** The reliability-first gate requires target evidence to become replayable host evidence. A successful Pi probe should produce a content-free, non-actuating manifest that can be committed as a sanitized fixture and used to replay topology-specific failure classes before another package is handed to the Raspberry Pi.

**Target manifest tool.** `scripts/target_probe.py` SHALL collect a `gonken-target-hardware-manifest-v1` JSON document containing platform/kernel/OS/Python/libgpiod facts, gpiochip stat/sysfs/chip/line metadata, I2C device inventory, non-content audio route inventory, Bluetooth inventory, systemd unit state, service identity groups, current release state and privacy flags. The live probe SHALL NOT request GPIO lines, toggle the relay or LEDs, scan arbitrary I2C addresses, read audio content, include transcripts/prompts/model responses, or claim physical acceptance.

**Target-shadow replay.** The same tool SHALL support `--replay <manifest>` and validate GPIO17/22/23/27 identity using the same reliability semantics as the resolver: canonical alias deduplication first, then line-name/RP1/header-topology resolution, with fail-closed behavior for genuinely distinct plausible header controllers. Replay PASS is host/target-shadow evidence only; it does not establish physical relay, sensor or voice acceptance.

**Fixtures.** The repository SHALL include a checkpoint-34 duplicate-RP1-alias manifest fixture that replays PASS and a distinct-duplicate-header fixture that replays FAIL. These fixtures prevent the alias repair from regressing into either false ambiguity or first-path-wins behavior.

**Release payload.** `target_probe.py` SHALL be copied into immutable release maintenance payloads so installed targets can capture/replay the same manifest shape without relying on a source checkout.

**Host acceptance.** Host acceptance requires replay fixture tests, live-collection tests with fake libgpiod/stat metadata, CLI replay exit-code tests, atomic private output tests, release-maintenance inclusion tests, static syntax/compile checks, milestone/status synchronization and T0 validation.

**Target acceptance.** Target acceptance remains blocked until a real Raspberry Pi runs the live probe, uploads the sanitized manifest, the manifest is reviewed for privacy, and the corresponding target-shadow fixture passes before any future Pi candidate package is produced.

#### M10.32 Release-readiness target-shadow gate

**Purpose.** Release readiness SHALL move from host-only milestone inspection to an explicit internal host/target-shadow gate. The gate may report `READY_FOR_HOST_TARGET_SHADOW_GATE` only when all required host milestones through the current reliability batch are host-verified, secret scanning is clean, the Git tree is clean or an explicit development override is used, and all required target-shadow fixtures replay with the expected PASS/FAIL outcomes.

**Required replay fixtures.** The release-readiness gate SHALL execute `scripts/target_probe.py --replay --json` against the checkpoint-34 duplicate-RP1-alias manifest and the distinct-duplicate-header fail-closed manifest. The alias fixture must return PASS with `GPIO_HEADER_RESOLVED`; the distinct duplicate fixture must return exit 75 with `GPIO_HEADER_UNRESOLVED`. Both payloads must keep `physical_acceptance_claimed` false.

**Readiness boundary.** `READY_FOR_HOST_TARGET_SHADOW_GATE` is an internal reliability status, not a Raspberry Pi candidate label and not target acceptance. It authorizes the next dependency-ready reliability work, including adding sanitized real-target manifests and exact-archive qualification. It does not authorize integrated relay, fan, SHT31, wake, speech, reboot, update, rollback or reinstall acceptance claims.

**Host acceptance.** Host acceptance requires focused release-readiness tests, target-probe replay tests, milestone/status synchronization, static syntax checks, T0 validation, clean-diff review and package verification from a clean tagged clone. A missing, malformed, unexpected-status or physical-claiming replay fixture blocks readiness.

**Target acceptance.** M10.24/WP-L remains open. A future Pi candidate may be prepared only after the host/target-shadow release-candidate gate is complete, exact-archive verification passes, and the candidate preserves the requirement to run `target_probe.py` before installation, reach `INSTALLATION_COMPLETE`, and then execute `docs/RASPBERRY_PI_ACCEPTANCE_RUN.md` on the real target.

#### M10.33 Target-shadow capability and state replay expansion

**Purpose.** Target-shadow replay SHALL broaden from GPIO identity alone to the next known classes that repeatedly changed the target failure surface: usable non-HDMI duplex audio, service-user identity/group readiness and current-release/installer state cleanliness. These checks remain replay evidence and do not replace live target operation.

**Opt-in replay contracts.** Sanitized manifests MAY declare `target_shadow_requirements`. Legacy GPIO fixtures keep their historical scope. Capability fixtures can require `audio_duplex`, `service_identity` and `release_state` so each check is explicit, reviewable and independently testable.

**Audio capability replay.** A required audio fixture must prove one selected capture route and one selected non-HDMI playback route, with no ambiguity flag. Bluetooth may be unavailable when a deterministic direct USB/wired route is selected; replay must not claim Bluetooth success from fallback evidence.

**Identity and release-state replay.** A required identity fixture must prove `gonken-agent` has `audio` and `gpio` groups and `gonken-env` has `gpio` and `i2c`. A required release-state fixture must reject dirty installer state, non-complete paused state, invalid current status and unsafe current-release paths.

**Host acceptance.** Host acceptance requires PASS and fail-closed fixtures for the expanded capability matrix, release-readiness inclusion of all required fixtures, focused target-probe/readiness tests, static syntax checks, milestone/status synchronization, T0 validation and clean tagged package verification.

**Target acceptance.** M10.24/WP-L remains open. Real microphone/speaker behavior, Bluetooth runtime behavior, service start/restart, current-release installation, `INSTALLATION_COMPLETE`, relay/fan, SHT31, voice/wake, reboot/no-login and update/rollback/reinstall still require the real Raspberry Pi campaign.

#### M10.34 Exact archive qualification gate

**Purpose.** Exact archive qualification SHALL become a repeatable host gate rather than an informal packaging ritual. The gate verifies that the delivered zip archive extracts to the intended Git commit and tag, preserves executable modes, contains no Python cache artifacts, has a clean worktree, passes repository integrity checks, passes milestone/status synchronization, passes release readiness and passes T0 from the extracted copy.

**Archive safety.** `scripts/archive_qualifier.py` SHALL reject archives with multiple roots, unsafe paths, symlinks, `__pycache__`, `.pyc` or `.pyo` content. Extraction SHALL preserve stored Unix executable permissions so the extracted archive is evaluated as it would be delivered, not as a mode-mutated local approximation.

**Readiness boundary.** A qualified archive remains an internal host/package artifact. Qualification can prove exact package integrity and replay readiness, but it cannot prove Raspberry Pi installation, service operation, physical audio, relay/fan behavior, SHT31 readings, wake/voice, reboot/no-login, update, rollback or reinstall acceptance.

**Release payload.** `archive_qualifier.py` SHALL be included in immutable release maintenance payloads so future installed/extracted release contexts carry the same qualification helper.

**Host acceptance.** Host acceptance requires archive-qualifier unit tests, execution against the previous checkpoint package with expected commit/tag, maintenance-payload contract coverage, milestone/status synchronization, static syntax checks, T0 validation and final package qualification from a clean tagged clone.

**Target acceptance.** M10.24/WP-L remains open. A future Raspberry Pi candidate may be prepared only after the broader host/target-shadow release-candidate gate is complete and the exact candidate archive passes this qualifier.

#### M10.35 Target-shadow I2C/SHT31 and environment-profile replay expansion

**Purpose.** Target-shadow replay SHALL cover the next room-environment classes that can block a reliable target cycle before integrated actuation: I2C bus readiness, planned I2C reboot pauses, SHT31 targeted diagnostic status and static environment profile consistency. These checks remain replay evidence and never replace live target SHT31, relay, fan or voice acceptance.

**I2C/SHT31 replay.** Required replay fixtures SHALL distinguish a ready `/dev/i2c-1` plus exactly one supported SHT31 address from absent sensors, unsupported addresses, heater-on state and the governed `I2C_REBOOT_REQUIRED` pause. Live manifest capture remains non-actuating and does not probe the sensor address; replay fixtures may carry sanitized diagnostic summaries gathered separately under the target runbook.

**Environment profile replay.** Required profile fixtures SHALL validate only governed profiles: `full-simulation`, `sensor-deferred-relay`, `real-sensor-simulated-actuator` and `full-real`. Simulation profiles may pass without physical I2C/GPIO. Real-sensor profiles require SHT31 replay readiness, and libgpiod relay profiles require resolved GPIO23 evidence. `full-real` must also disable simulation runtime control.

**Host acceptance.** Host acceptance requires PASS and fail-closed fixtures for ready full-real, planned I2C reboot, absent SHT31, missing full-real relay evidence and simulation-safe profile handling; release-readiness inclusion of all required fixtures; focused target-probe/readiness tests; static syntax checks; milestone/status synchronization; T0 validation; and clean tagged archive qualification.

**Target acceptance.** M10.24/WP-L remains open. A future Raspberry Pi candidate remains blocked until sanitized real-target manifests cover the exact hardware/service/release/profile state, the complete host/target-shadow release-candidate gate passes and the real Pi campaign reaches `INSTALLATION_COMPLETE` before integrated hardware evidence is claimed.

#### M10.36 Target-shadow lifecycle, runtime and resource-state replay expansion

**Purpose.** Target-shadow replay SHALL cover the remaining high-risk host-verifiable target states that previously caused dead ends or false confidence: partial installer state, stale temporary artifacts, runtime mutation of the active release, support evidence from the wrong release, old managed systemd units, service restart failure, operator control-group gaps, low disk and interrupted model finalization.

**Delivery principle.** These checks SHALL block readiness only when the manifest describes a state that can invalidate the exact current release, make installation non-convergent, make service restart/no-login operation fail, or make model/runtime evidence untrustworthy. Noncurrent corrupt historical releases SHALL NOT block by themselves when the current release, install record and rollback-selected state are clean.

**Replay contracts.** Required fixtures SHALL include both ready and fail-closed cases. Ready lifecycle replay may tolerate Python cache artifacts and corrupt unreferenced history. It must reject current authoritative drift, wrong current commit, stale symlink/temp artifacts, incomplete install records, wrong-release support collection, low resource headroom, old/conflicting managed systemd templates, service restart failure and missing `gonken-envctl` operator authorization.

**Host acceptance.** Host acceptance requires focused target-probe/readiness tests, release-readiness inclusion of all required fixtures, static syntax checks, milestone/status synchronization, T0 validation, clean Git state and exact archive qualification from a clean tagged clone.

**Target acceptance.** M10.24/WP-L remains open. These replay checks improve confidence that the next package will be usable on the Raspberry Pi, but they still do not prove physical SHT31 reads, fan motion, audio behavior, wake/voice performance, reboot/no-login persistence, update, rollback or reinstall acceptance.

#### M10.37 Single-ZIP target evidence and failure-bundle completeness

**Purpose.** The host development platform SHALL not depend on direct access to the real Raspberry Pi environment. Future target troubleshooting and package improvement SHALL depend on one comprehensive, content-free ZIP produced on the target. The ZIP must carry enough hardware, runtime, installer, service and log-code evidence for host-side diagnosis without requiring a second status report package merely to understand the failure.

**Support ZIP contract.** `collect-support.sh` SHALL automatically run the non-actuating `target_probe.py` when it is available and include the resulting sanitized target manifest inside the normal support ZIP. The support ZIP SHALL also include an evidence index, platform/resource inventory, runtime binding evidence, install-event summaries, service journal code counts, environment diagnostics, health, configuration and telemetry summaries. It SHALL continue to exclude raw audio, transcripts, prompts, model responses, credentials, Wi-Fi passphrases and arbitrary raw journal text.

**Installer-failure ZIP contract.** Early installer failures SHALL produce a single installer-owned failure ZIP that includes source/install provenance, target preflight summaries, event records, platform/resource inventory, bounded service journal code counts and a sanitized target manifest when `target_probe.py` can run. This ensures failures before immutable release activation still return decisive evidence for the next package cycle.

**Operational boundary.** A complete ZIP can establish target topology, service/runtime state, installer provenance, resource constraints and bounded failure codes. It cannot by itself prove fan blade motion, acoustic quality, SHT31 physical placement or human-observed wake behavior. Those observations must be recorded as target evidence when relevant, but package construction must not be blocked merely because this platform cannot directly run the physical environment.

**Host acceptance.** Host acceptance requires support-export unit tests for the expanded members and privacy rejection, installer-failure bundle tests for single-ZIP completeness, installed maintenance wrapper integration tests proving automatic target-manifest inclusion, static syntax checks, milestone/status synchronization, T0 validation and clean tagged archive qualification.

**Target acceptance.** M10.24/WP-L remains evidence-collected on the real Raspberry Pi. The next target cycle should upload the single support or installer-failure ZIP first. If physical observations are not machine-readable, they may accompany the ZIP as notes, but the ZIP is the primary source for host-side repair.

#### M10.38 Post-checkpoint-42 semantic convergence and canonical evidence architecture

**Triggering target evidence.** The 2026-09-17 checkpoint-42 Raspberry Pi run built and activated commit `3a0c78e`, passed target GPIO identity and the downstream installer prerequisite steps, then reached `appliance_readiness` with `gonken-agent.service` active but the application still `STARTING`. The current causal dependency was `AUDIO_CAPTURE_FAILED` (`pipewire-usb:AUDIO_CAPTURE_INVALID`, `alsa-usb:AUDIO_CAPTURE_FAILED`); the bounded journal also contained earlier `WAKE_LED_GPIO_LINE_AMBIGUOUS` history. Installer failure output was root-owned and the operator subsequently ran `collect-support.sh` to obtain a second ZIP. These facts require a whole-convergence repair, not another single-error patch.

**Audio repair and target-shadow regression.** PipeWire capture SHALL use a bounded raw signed-16-bit mono stream and application-owned canonical WAV construction before the existing WAV validator. This avoids treating an interrupted encoded-container finalization as a trustworthy recording. Stable reason codes distinguish permission, audio-server, device-unavailable, device-busy, WAV-invalid and generic backend failures. A sanitized checkpoint-42/2026-09-17 target-shadow fixture SHALL prove that structural duplex audio evidence can coexist with failed exact-service-context capture, and release readiness SHALL replay that fixture within a bounded measured budget.

**Semantic readiness.** systemd process liveness SHALL remain separate from appliance readiness. `gonken-agent` publishes a bounded readiness record containing semantic status, causal component/code, recoverability, release commit, boot identity, service PID and observation time. Service start removes stale records. The installer validates freshness/current identity, exposes the pending dependency and may fail early for known non-recoverable states rather than waiting a generic 180-second timeout. A stale READY file SHALL never satisfy a new process/reboot/release.

**Canonical evidence architecture.** One `gonken-evidence-bundle-index-v2` engine SHALL own member hashing, ZIP publication, privacy metadata, output policy, ownership return and duplicate-member handling. Normal support uses this engine directly. Installer failure adds namespaced installer evidence and merges common support payloads from the canonical support path where available; it emits one final archive, one evidence index and one final operator-readable path. Common support members SHALL not be duplicated under installer-specific names.

**Privacy and exact-consumer context.** Support may report metadata-only `gonken-agent` audio-session context and semantic readiness, but it SHALL not capture audio, transcripts, prompts/model responses, credentials or raw journals. An interactive operator's PipeWire graph SHALL not be mislabeled as service-user evidence. Stable Bluetooth identifiers are normalized when they are not required for diagnosis.

**Responsibility boundaries.** The remote launcher owns only minimal acquisition/delegation, bootstrap owns source/preflight/source-record/privilege handoff, and the installer owns the install DAG, appliance-readiness convergence and failure-bundle invocation. Structural and behavioral tests SHALL prevent these responsibilities from drifting between layers.

**Downstream convergence and lifecycle.** After the audio repair, host/target-shadow gates SHALL exercise the already-implemented playback, Whisper/Piper, wake/listening, Ollama, semantic service readiness, environment profiles, voice/environment IPC, support collection, restart/hotplug, same-commit/lifecycle and archive/readiness paths. Correcting one blocker is not sufficient if a newly reachable dependency remains untested.

**Environment status boundary.** The four governed profiles remain `full-simulation`, `sensor-deferred-relay`, `real-sensor-simulated-actuator` and `full-real`. Full-real requires real-SHT31 and libgpiod configuration with runtime simulation control disabled, but software readiness still cannot prove physical SHT31 placement, relay polarity/PENGLIN correctness or fan blade motion. `software_speed_control=false` remains mandatory and the room fan remains distinct from the Raspberry Pi Active Cooler.

**Host acceptance.** Host completion requires the checkpoint-43 focused repair suite; canonical evidence/output/privacy tests; responsibility-boundary tests; downstream voice/speech/Ollama/environment convergence; lifecycle/recovery regression; compile/static/diff/docs/milestone gates; release readiness including all 23 target-shadow fixtures; T0; a clean checkpoint commit/tag; exact archive qualification; and focused/readiness reruns from the extracted delivered archive.

**Target acceptance.** M10.24 remains open. Checkpoint 43 may produce a qualified Raspberry Pi release-candidate package, but only the exact target campaign may close microphone/speaker service-context operation, wake/acoustic behavior, real SHT31, relay/fan motion, reboot/no-login, update/rollback/reinstall and integrated physical acceptance. If target installation fails, the single emitted combined evidence ZIP is the primary next-cycle input.

#### M10.39 Checkpoint-44 V04 component/readiness and environment-convergence foundation

**Purpose.** Begin the V04 convergence cycle from exact Checkpoint 43 target evidence. Repair the semantic-readiness release-identity false-red, make current component state independent of historical event counts, and convert the observed environment-disabled/permission/manual-repair chain into governed installation behavior before the multi-model/tool-broker tranche.

**Governing V04 input.** The exact GOLD prompt is retained at `docs/development/V09_CKPT43_TO_FULL_COMPONENT_CONVERGENCE_BLUEPRINT_PROMPT_V4_GOLD.md`, SHA-256 `4e7597baaa8410d988f6f452adb9672969a734ec32f729c788055ce060d19ba8`, so continuation does not depend on prior chat context.

**Release identity.** Runtime semantic readiness SHALL derive immutable release commit/profile from the installed package path (or another equally authoritative release-owned anchor), never solely from `Path(sys.executable).resolve()`. A symlinked virtual-environment interpreter resolving to the distribution Python must retain the immutable release identity. Source-tree execution may report development only when no installed release anchor exists.

**Component readiness.** V09 SHALL maintain a versioned component readiness vocabulary that distinguishes `READY`, `DEGRADED`, `FAILED`, `WAITING`, `DISABLED`, `NOT_COMMISSIONED`, `NOT_APPLICABLE`, `NOT_TESTED`, `BLOCKED` and `UNKNOWN`. Current READY may retain historical failure provenance without being converted back to failed. Installer completion output SHALL expose voice, inference, environment controller, sensor, room-fan control and LLM/tool-broker state independently.

**Environment diagnostic purity.** `gonken-agent env serve --check` SHALL be side-effect-free: no missing policy creation, no policy timestamp/ownership mutation, no daemon socket, no GPIO request and no production sensor-sampling side effect. Policy missing/permission/JSON/write/replace failures SHALL have distinct reason codes.

**Canonical commissioning.** Bootstrap/source-record SHALL carry an optional canonical environment profile and SHT31 address. The existing `environment_profile_manager.py` remains the only managed site-profile authority. A Checkpoint-43-compatible environment-only partial configuration may be atomically completed when every supplied value agrees with the requested canonical profile; unrelated or conflicting administrator configuration fails closed.

**Permissions and dirty-target convergence.** Managed installation SHALL reconcile `/var/lib/gonken-environment`, `/var/cache/gonken-environment`, `/run/gonken-environment` and an existing safe policy file to the governed owner/group/mode contract, and commissioned-status SHALL revalidate all three metadata dimensions rather than mode alone. Final directory modes are applied after ownership changes so the setgid runtime contract remains explicit. The exact known Checkpoint-43 temporary environment drop-in may be removed automatically; unknown administrator drop-ins are preserved and block managed commissioning. Safe commissioning resets stale systemd failure state only after prerequisites are reconciled.

**Non-actuating semantic readiness.** `full-simulation` and `real-sensor-simulated-actuator` may be automatically enabled/restarted by installation, but they are not complete until daemon IPC health proves `sensor=ready`, `actuator=READY` and the exact selected backends. `sensor-deferred-relay` and `full-real` SHALL stop at a planned physical-commissioning boundary before generic install can restart a service using the real room-fan relay.

**Target-shadow regression.** The sanitized 2026-09-17 Checkpoint-43 mismatch—active immutable release `14c0438...` versus runtime readiness `development/development`—SHALL remain a required fail-closed fixture. Release readiness SHALL execute 24 required target-shadow fixtures after this checkpoint.

**Host acceptance.** Focused release-identity, appliance, environment policy/daemon/profile/service/readiness, bootstrap/source-record, installer graph, target-probe/readiness and release-manager tests must pass; compile/static/docs/milestone/T0 gates and exact archive qualification must pass before packaging.

**Target boundary.** Host verification does not establish real SHT31 placement/quality, physical relay/fan behavior, wake/audio quality, no-login reboot, or LLM-to-hardware tool transactions. The first recommended target profile is `real-sensor-simulated-actuator` so sensor/service/permissions can be validated independently before real GPIO23 actuation.


#### M10.40 Checkpoint-45 V04 multi-model, typed-tool and causal-evidence convergence

**Purpose.** Convert the Checkpoint-44 foundation into an operator-usable three-model assistant with safe semantic tools, independent component truth and causal support evidence while preserving the real-sensor/simulated-actuator safety boundary.

**Model lifecycle.** The governed roster SHALL contain exactly `qwen3:0.6b`, `lfm2.5-thinking:1.2b`, and `qwen3.5:0.8b`. First commissioning selects `qwen3:0.6b`; an admitted later selection SHALL survive idempotent installer reruns. Provisioning SHALL support online and preseeded-offline modes, validate catalog identity/quantization, preserve rollback material, enforce one-loaded-model policy and fail without destroying prior working state.

**Tool authority.** Common clock/environment operations SHALL use deterministic fast paths. Semantic fallback MAY use Ollama typed tool calls, but the model only proposes operations. A broker SHALL validate a fixed schema, explicit mutation authorization, call-count bounds and mutation serialization. Shell, systemctl, raw GPIO, raw I2C, arbitrary files/network and arbitrary Python SHALL never be model tools.

**Tool truth.** Sensor reads and fan state/actions SHALL go through the sole environment daemon owner. Tool results SHALL ground spoken output. Simulated fan commands SHALL never be described as physical blade motion, and the room fan SHALL not claim RPM.

**Operator observability.** `components`, `llm status/models/capabilities/benchmark/switch`, richer passive `env watch`, and support evidence SHALL expose voice, model, environment controller, sensor, actuator and tool-broker state independently. Direct diagnostic-probe context SHALL not overwrite current semantic service readiness.

**Causal evidence.** The one-ZIP architecture SHALL include latest install run ID, boot/release/readiness identity, current component state, bounded same-boot reason-code aggregates, permission/systemd/config provenance, Ollama roster/loaded model, tool policy, collection errors and diagnostic findings. Raw transcripts, model answers, audio and raw journals remain excluded.

**Host acceptance.** Focused model/tool/voice/environment/install/support tests, broad affected regression, compile/static/docs/milestone/T0 gates, release readiness, exact tagged archive qualification and fresh-extraction reruns SHALL pass before packaging.

**Target boundary.** Checkpoint-44 target evidence establishes a working real SHT31 path with simulated actuator, but Checkpoint 45 itself remains target-unverified until the exact package installs/qualifies all three models and exercises tool/latency/reboot gates. Real GPIO23/ELUTENG actuation remains a separate supervised WP-45C gate.
