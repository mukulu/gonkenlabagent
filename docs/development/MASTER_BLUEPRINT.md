# GonKenLab Agent Implementation Master Blueprint

**Blueprint revision:** 1.1-reviewed

**Prepared:** 2026-09-08 UTC

**Branch:** `dev/bootstrap-rearchitecture`

**Source audit:** `REPOSITORY_AUDIT.md` at checkpoint `checkpoint/audit`

**Review state:** adversarial review completed in `BLUEPRINT_ADVERSARIAL_REVIEW.md`; accepted for staged implementation

**Implementation authorization:** M2.1 is authorized; later work remains bound to milestone prerequisites and acceptance evidence

## 1. Purpose and authority

This blueprint is the implementation contract for turning the current GonKenLab Agent prototype into a reproducible, privacy-sensitive, fully local Raspberry Pi 5 AI-lab assistant. It translates the repository audit and supplied project requirements into ordered, file-level work with explicit failure behavior, validation, rollback, and commit boundaries.

Where this blueprint conflicts with the historical `PRD.md`, this blueprint governs development. The historical PRD is retained only as provenance until the release-documentation milestone. Where a future implementation discovers evidence that makes an item unsafe or infeasible, development must pause that item, record the evidence in `IMPLEMENTATION_STATUS.md` and `DECISIONS.md`, revise this blueprint, and commit the revision before continuing.

The blueprint does not claim that every technical choice is already proven on Raspberry Pi hardware. Unverified choices are marked with gates that require target evidence. The M1B review deliberately separates the core release from governed extensions so that experimental features cannot weaken privacy, safety, or delivery of the primary research instrument.

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
6. a bounded local Markdown/text corpus with deterministic lexical retrieval;
7. concise answers that identify supporting sources or explicitly report insufficient support;
8. local telemetry and provenance with privacy-preserving defaults;
9. a minimal read-only dashboard restricted to loopback;
10. a systemd-managed runtime independent of user login;
11. clear degraded states and automatic retry when audio/Ollama are temporarily unavailable;
12. doctor, install verification, update, rollback, recovery, and uninstall procedures;
13. automated unit/integration tests plus recorded Pi hardware, reboot, and failure-injection evidence.

The core release does **not** require wake-word activation, voice power control, direct LAN dashboard access, or Bluetooth. Those are governed extensions X1–X4. They remain planned project work, but each has an independent acceptance gate and none may delay or dilute the core release.

### 2.3 Explicit non-goals for the first release candidate

- arbitrary general-purpose cloud AI fallback;
- weather, news, or joke APIs that require internet access;
- arbitrary shell execution by the language model;
- camera or multimodal image input;
- a purchased LCD or mandatory pygame UI;
- Bluetooth as the primary supported audio path;
- continuously sampled wake-word operation;
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
| INV-03 | Any enabled wake phrase equals the validated loaded wake model and displays a distinct continuous-monitoring indicator. | GX1 startup/config/privacy-indicator tests |
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
- USB audio device, initially validated against AIRHUG USB audio;
- GPIO push button and dedicated recording LED for full physical acceptance.

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
voice = "en_GB-semaine-medium"

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

### 10.1 Push-to-talk

Push-to-talk is the mandatory reliable and privacy-forward path. Hold GPIO17 to capture; release to stop. GPIO27 red LED is on exactly while utterance audio is being captured. A keyboard/CLI trigger is allowed only for development/diagnostics.

### 10.2 Extension X1 — wake-word mode

Wake-word mode is a governed post-core extension and is absent/disabled in the core release. openWakeWord is the first evaluation candidate, not an architectural dependency. A backend spike must first prove a maintained, license-compatible, Python 3.13/AArch64 install and on-Pi inference path. When an accepted backend is enabled, short frames are processed locally and not written to disk. Documentation must explain that the microphone is continuously sampled in memory for wake detection even though utterance recording begins only after activation.

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
| G5 Service | enable/start/stop/restart/reboot/hotplug/degraded/recovery pass |
| G7 Release | clean-install repeat, rollback, uninstall, security/license/docs audit pass |
| GX1 Wake extension | backend/license spike, phrase/model consistency, representative FRR/FAR with intervals, distinct indicator, idle-load, and reboot pass |
| GX2 Voice-power extension | independent physical confirmation, cancellation, compromise, privilege, and physical reboot/poweroff pass |
| GX3 LAN dashboard extension | authentication, transport, token lifecycle, exposure, rate-limit, and adversarial access tests pass |
| GX4 Bluetooth extension | pair/reconnect/enumeration/latency/reboot/end-to-end tests pass |

### 13.2 Provisional Pi performance acceptance

Final numeric thresholds require the first controlled Pi benchmark, but the release cannot pass if any fixed evaluation causes kernel OOM, sustained swapping that makes the service unusable, thermal throttling under the declared cooled test, or unbounded response time. The controlled benchmark records cold/warm load, first token, total generation, tokens/s, peak RAM, swap, temperature, throttling, and end-to-end time for fixed prompts. Qwen 3.5 2B Q4_K_M remains the first candidate, not a pre-declared passing result. After baseline evidence, M3 records justified user-facing thresholds in this blueprint; any fallback model requires a decision and repeated grounding-quality tests.

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

**Output:** `BLUEPRINT_ADVERSARIAL_REVIEW.md` with accept/reject rationale incorporated into blueprint/decisions; no code.

**Acceptance:** no unresolved Critical review finding; High items either resolved or explicitly gated with an owner/milestone.

**Commit:** `docs: harden blueprint after architecture review`.

**Rollback:** revert only the documentation commit; audit checkpoint remains intact.

### M2 — Packaging, identity, configuration, and test foundation

#### M2.1 Package and identity normalization

**Files:** `pyproject.toml`, `src/gonken_agent/**`, compatibility `orchestrator.py`, package `__init__` files, prompts, README references.

**Actions:** create installable package and CLI; move modules with `git mv`; remove Jansky/Mayukh behavior; retain temporary wrappers only where tests need transition; set GonKenLab Agent identity in one config path; encode core-versus-extension module boundaries; create a source/assets/dependencies license inventory and obtain a maintainer-approved project/distribution license decision before claiming redistributability.

**Failure modes:** import cycles, broken entry point, lost assets, stale hard-coded paths, extension dependency leaking into core, unapproved/incompatible project or third-party license claims.

**Validation:** import/CLI unit tests; repository search for forbidden inherited identity outside historical/audit docs; core import works with extension packages absent; license inventory has no unknown bundled source/asset; no hardware required.

#### M2.2 Configuration authority and migration

**Files:** `config/defaults.toml`, `src/gonken_agent/config.py`, migration tests, `.env.example`, legacy JSON.

**Actions:** implement schema validation and precedence; effective-config/redaction command; migrate JSON/`.env`; make model/endpoint/audio/path settings single-source; keep extension settings disabled and reject unsupported enablement/non-loopback dashboard bind.

**Failure modes:** unknown keys, invalid types, path escape, env/file inversion, partial migration.

**Validation:** table-driven unit tests for every field and precedence; legacy migration repeat; invalid config fails without rewrite.

#### M2.3 Dependency profiles and locks

**Files:** `pyproject.toml`, `requirements/*.lock`, dependency-generation documentation.

**Actions:** split headless core, post-spike extension, optional UI, and dev/test profiles; pin/hashes for Trixie/Python 3.13; keep openWakeWord absent from core; remove mandatory pygame.

**Failure modes:** ARM wheel absence, source-build drift, incompatible NumPy/ONNX/Piper, accidental extension dependency, GPL/voice-license mismatch.

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

**Actions:** create account/paths; build release-specific venv; install locked deps; validate CLI/imports; measure release/staging space; journal and atomically activate; retain active plus one previous release; install pre-start reconciliation.

**Validation:** failed venv/dependency/smoke never moves `current`; low-space preflight; interruption around candidate finalization/journal/symlink; successful activation/reconciliation/rollback in temporary root, then Pi.

#### M3.4 Ollama lifecycle and selected model

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

They are resolved in this revision by removing core power privilege, distinguishing convergent provisioning from project-atomic activation, specifying a durable activation journal/pre-start reconciliation contract, and separating X1–X4 from core release gates. No Critical M1B issue remains open. AR-19 licensing remains a High release gate assigned to M2.1; it requires an explicit maintainer-approved decision rather than an invented M1B license choice.

## 18. Exact next action

Implement M2.1 only: establish the `src/gonken_agent` package skeleton and CLI, normalize the sole GonKenLab Agent identity, keep compatibility wrappers where tests require them, encode core-versus-extension import boundaries, and create the source/assets/dependencies licensing inventory for maintainer decision. Add deterministic unit tests that require no Ollama, network, audio, GPIO, or extension dependency. Update all control documents and commit the coherent work before beginning M2.2.

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
