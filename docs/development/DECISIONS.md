# GonKenLab Agent Decision Log

This is an append-oriented architecture and governance log. A decision may be superseded, but its original rationale should remain visible.

## Decision status vocabulary

- **Accepted:** governs implementation unless explicitly superseded.
- **Provisional:** working direction requiring blueprint review or evidence.
- **Deferred:** intentionally postponed with an identified trigger.
- **Rejected:** considered and not adopted.
- **Superseded:** replaced by a later decision.

---

## D-001 — Use a persistent development branch

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Develop on `dev/bootstrap-rearchitecture`, created from `origin/main` commit `6682360`.
- **Reason:** The work spans configuration, provisioning, services, audio, privacy, recovery, and tests. A meaningful history is needed for session continuity and later selective merge.
- **Consequence:** `main` is not treated as the active workspace. Release cleanup/merge is a later explicit milestone.

## D-002 — Treat repository artifacts as the continuity authority

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Later sessions reconstruct state from Git history plus `MASTER_BLUEPRINT.md`, `IMPLEMENTATION_STATUS.md`, `TEST_MATRIX.md`, `DECISIONS.md`, and the frozen baseline audit.
- **Reason:** Conversation memory is not a dependable engineering record.
- **Consequence:** Each implementation commit must update relevant control documents; a code-only milestone is incomplete.

## D-003 — Keep M0 documentation-only

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Do not change runtime/application code during the forensic-audit milestone.
- **Reason:** Current assumptions and requirements conflict; code changes before a verified baseline would hide causal relationships and prematurely commit architecture.
- **Consequence:** All runtime findings remain open after M0.

## D-004 — Preserve a frozen audit separately from the rolling blueprint

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Use `REPOSITORY_AUDIT.md` for baseline evidence and create `MASTER_BLUEPRINT.md` in M1.
- **Reason:** An audit answers “what existed”; a blueprint answers “what we will do.” Combining them makes later status difficult to interpret.
- **Consequence:** Correct factual errors in the audit if found, but do not rewrite it to make later implementation appear present at baseline.

## D-005 — Do not use automatic login to start a headless assistant

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** A future GonKenLab Agent runtime must be a system-managed service independent of an interactive login. Autologin may be documented only for a separately justified UI/kiosk mode.
- **Reason:** Headless systemd services start without user login; autologin enlarges the security surface and does not solve service lifecycle correctly.
- **Consequence:** Onboarding must configure administrative access/SSH independently from runtime startup.

## D-006 — Default to a local/offline privacy boundary

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** The future default mode must not automatically transmit user transcripts or queries to cloud services.
- **Reason:** Fully local operation and privacy sensitivity are explicit project goals; current automatic cloud fallback violates user expectations.
- **Consequence:** Cloud/network tools must be removed, disabled by default, or placed behind an explicit, observable, consent-based mode defined by the blueprint.

## D-007 — Establish one authoritative model selection

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Provisioner, runtime, service, doctor, tests, and documentation must resolve the same chat-model setting.
- **Reason:** The current repeated defaults can drift and cause setup to pull one model while runtime requests another.
- **Consequence:** M1 must define precedence, validation, migration, and model-presence/inference checks.

## D-008 — Use Qwen 3.5 2B Q4_K_M as the candidate default, pending Pi acceptance

- **Status:** Provisional
- **Date:** 2026-09-08
- **Decision:** Plan around Ollama tag `qwen3.5:2b-q4_K_M`, whose current official artifact is approximately 1.9 GB, but do not label it production-accepted until Pi 5 4GB tests pass.
- **Reason:** It is the user’s current first choice and the tag is verified to exist. Artifact existence does not prove end-to-end latency, RAM, thermal, tool, or grounded-answer suitability.
- **Consequence:** Blueprint acceptance must include context limits, inference smoke tests, performance measurements, and fallback/recovery behavior.

## D-009 — Never advertise a wake phrase that does not match the loaded model

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Startup speech, logs, UI, tests, and documentation derive the activation phrase from the validated loaded detector model. Silent fallback to another phrase is not allowed.
- **Reason:** Current Jarvis/Jansky/Gonken divergence makes the interface nonfunctional and misleading.
- **Consequence:** Custom Gonken training and acceptance are a discrete milestone with provenance and false-trigger evidence.

## D-010 — Separate installation from runtime self-healing

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** The assistant runtime/service may diagnose, wait, retry safe runtime connections, and expose recovery instructions; it must not run APT/pip, pull code, or install system components during ordinary boot.
- **Reason:** A daemon that mutates its installation at boot complicates privileges, auditability, availability, rollback, and recovery.
- **Consequence:** Provisioning/upgrade commands and runtime service are separate components with explicit ownership.

## D-011 — Treat voice shutdown/reboot as privileged deterministic actions

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Do not implement power control through arbitrary LLM-generated commands. Any future feature uses exact allow-listed intent, local processing, explicit confirmation/cancellation, least privilege, logging, and adversarial tests.
- **Reason:** False wake/transcription, prompt injection, and normal conversational ambiguity can otherwise stop the device unexpectedly or create a privilege boundary bypass.
- **Consequence:** Feature remains unimplemented until its blueprint acceptance contract exists.

## D-012 — Distinguish readiness tiers

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Report static, host, architecture-install, Pi-software, Pi-hardware, boot/recovery, and failure/security results separately.
- **Reason:** Passing source syntax on x86 does not prove a clean ARM64 install or physical voice behavior.
- **Consequence:** “Ready” may only be printed when the relevant configured operating tier passes; hardware absence must remain visible as a degraded/blocking state as appropriate.

## D-013 — Preserve physical user-control design as a recovery/privacy path

- **Status:** Provisional
- **Date:** 2026-09-08
- **Decision:** The blueprint should retain a physical push-to-talk or equivalent manual interaction/recovery path even if the evaluated custom Gonken wake word becomes the normal interface.
- **Reason:** The feasibility blueprint gives strong privacy and reliability reasons for push-to-talk, while the current requirements prioritize hands-free wake-word use. These goals can be staged rather than falsely treated as mutually exclusive.
- **Consequence:** M1 must decide MVP/default mode, hardware requirement, LED semantics, and acceptance thresholds.

## D-014 — Do not finalize the 22-phase sketch as written

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Start with ten broad, dependency-ordered milestones from audit through release; split them into implementation-grade work items inside M1.
- **Reason:** Twenty-two predetermined phases imply architectural certainty before the audit. Coherent commit boundaries should follow dependencies and acceptance evidence.
- **Consequence:** The broad milestone list in `REPOSITORY_AUDIT.md` is a planning scaffold, not yet the master blueprint.

## Deferred decisions for M1

The master-blueprint review must resolve:

1. final installed filesystem layout and whether source remains a Git checkout on the Pi;
2. dedicated service account versus invoking administrative user;
3. supported Raspberry Pi OS/Python versions and compatibility policy;
4. dependency lock/constraints strategy across ARM64/Python versions;
5. exact offline/network feature disposition;
6. push-to-talk, wake word, or dual-mode release boundary;
7. custom Gonken wake-word training data/provenance/distribution plan;
8. local grounding/dashboard scope for the first release candidate;
9. safe shutdown/reboot authorization mechanism;
10. configuration file format, precedence, secrets, migration, and validation;
11. model/data checksum and supply-chain policy;
12. install/upgrade/uninstall/rollback interface;
13. readiness levels when microphone/speaker/GPIO are missing;
14. test framework and clean Raspberry Pi image automation strategy;
15. which development documents are retained, condensed, or removed before merge to `main`.

---

## D-015 — Use GonKenLab Agent as the sole active product identity

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Active code, prompts, speech, UI, tests, services, and user documentation will use “GonKenLab Agent.” SOPHIA-Lab remains research-background material; Jansky, Jarvis, PiBot, and Mayukh-specific behavior are historical only.
- **Reason:** The repository and stated lab use case already establish GonKenLab Agent; mixed identity currently breaks activation instructions and institutional fit.
- **Consequence:** M2 removes inherited identity while preserving history/audit evidence.

## D-016 — Distinguish offline runtime from online provisioning

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Normal runtime must be fully local and require no internet. Initial installation and explicit administrator-invoked updates may use internet access.
- **Reason:** Models and dependencies must first reach the Pi, but installation traffic does not justify transmitting operational speech or prompts later.
- **Consequence:** Offline tests block internet while allowing loopback and separately classify optional local-LAN dashboard traffic.

## D-017 — Use a dedicated non-login runtime account

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** `gonken-agent.service` runs as a `gonken-agent` system user with no login shell; Ollama remains a separate `ollama` service/account.
- **Reason:** Runtime should not inherit the administrator’s home, secrets, source ownership, or general privileges.
- **Consequence:** Audio, GPIO, state, cache, model, corpus, and power permissions must be explicitly defined and tested.

## D-018 — Use immutable installed releases with an atomic current pointer

- **Status:** Provisional
- **Date:** 2026-09-08
- **Decision:** Install root-owned releases under `/opt/gonken-agent/releases/<commit>` with release-local venvs and switch `/opt/gonken-agent/current` only after validation; retain one prior validated release.
- **Reason:** It separates development checkout from installed runtime and makes rollback comprehensible after failed upgrades.
- **Consequence:** M1B must test whether disk/time cost is proportionate on a 64GB microSD and whether a simpler alternative provides equivalent recovery.

## D-019 — Separate static, configuration, variable, cache, and runtime data

- **Status:** Provisional
- **Date:** 2026-09-08
- **Decision:** Use `/opt/gonken-agent`, `/etc/opt/gonken-agent`, `/var/opt/gonken-agent`, `/var/cache/gonken-agent`, and `/run/gonken-agent`, with journald for operational logs.
- **Reason:** The current checkout mixes code, venv, builds, models, secrets, and runtime state under a user directory.
- **Consequence:** M1B must verify FHS/systemd practicality and ensure service hardening permits required device/state access.

## D-020 — Use TOML configuration with explicit precedence

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Source-controlled `config/defaults.toml` is the only packaged default authority; site TOML overrides it; explicit `GONKEN_*` environment values override site config; CLI values are one-shot. Legacy JSON/`.env` are migration inputs only.
- **Reason:** Python 3.13 includes `tomllib`, TOML is readable, and explicit precedence prevents installer/runtime drift.
- **Consequence:** Unknown/invalid settings fail validation, and effective-config output shows sources while redacting sensitive values.

## D-021 — Lock target dependencies and verify non-Python artifacts

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Maintain exact, hashed locks for the primary Pi target and development host, plus a checked artifact manifest for Ollama, Whisper, Piper, wake-word resources, and model metadata.
- **Reason:** Broad ranges and file-existence checks cannot reproduce or repair installations reliably.
- **Consequence:** Updating a dependency or artifact requires regenerating locks/manifests and rerunning applicable gates.

## D-022 — Make push-to-talk mandatory and wake word acceptance-gated

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Physical push-to-talk is the supported privacy/recovery path. “Hey Gonken” is implemented and evaluated but remains disabled until phrase/model consistency, false-accept/reject, load, reboot, and licensing gates pass.
- **Reason:** This satisfies the desired hands-free direction without allowing an untrained or misleading wake phrase to block basic use.
- **Consequence:** Failure of the wake-word gate does not block a valid PTT release, but the limitation must be explicit.

## D-023 — Include local grounding and provenance in release scope

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Deterministic lexical retrieval over bounded Markdown/text, source identifiers, unsupported-answer behavior, content-free telemetry, and a read-only dashboard are required release capabilities.
- **Reason:** They distinguish the project as an accountable AI-lab instrument rather than a generic personal voice assistant.
- **Consequence:** Embeddings/vector databases and implicit PDF parsing remain out of first-release scope.

## D-024 — Remove internet-dependent assistant features from the release path

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Automatic Moonshot handoff and internet weather/news/joke tools will not be registered in normal release runtime.
- **Reason:** Disabled keys do not resolve the conceptual/privacy conflict created by cloud-first routing.
- **Consequence:** Time/system information remain local allow-listed tools; any future network mode requires a new explicit governance decision.

## D-025 — Support USB audio first

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** USB microphone/speaker is the acceptance target. Bluetooth remains experimental until pairing, reconnect, enumeration, boot, and latency behavior pass a separate matrix.
- **Reason:** USB reduces a large source of setup and reboot variability while preserving the user’s available AIRHUG device.
- **Consequence:** Documentation must not imply Bluetooth has the same support level.

## D-026 — Bind the dashboard to loopback by default

- **Status:** Provisional
- **Date:** 2026-09-08
- **Decision:** The first dashboard binds `127.0.0.1`; SSH forwarding is the supported safe access path. LAN binding is an explicit administrator choice after access control is decided.
- **Reason:** Transcripts/provenance/health can be sensitive, and a local network is not automatically trusted.
- **Consequence:** M1B must assess whether this is usable enough for the lab demonstration and define authentication before LAN exposure.

## D-027 — Use exact two-stage power intent with least privilege

- **Status:** Provisional
- **Date:** 2026-09-08
- **Decision:** Voice power control uses finite-state request/confirmation/cancel phrases and an exact root-owned allow-list; the LLM does not decide or construct the command. It is disabled until security/hardware tests pass.
- **Reason:** The feature is useful for headless operation but has material false-trigger and privilege risks.
- **Consequence:** M1B must challenge voice-only confirmation sufficiency and the effect of a compromised service account.

## D-028 — Support one primary Pi OS/Python target first

- **Status:** Provisional
- **Date:** 2026-09-08
- **Decision:** First acceptance targets Raspberry Pi OS Lite 64-bit based on Debian 13, AArch64, distribution Python 3.13.
- **Reason:** The next deployment is intended to start from a freshly formatted current image, and earlier failures occurred on Python 3.13. Broad OS compatibility would multiply untested paths.
- **Consequence:** M1B must verify the actual image before implementation; other platforms receive a clear unsupported/development-host result.

## D-029 — Use tiered pytest and install-failure testing

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Unit tests must run without network/models/hardware; separate integration, failure, and Pi hardware suites exercise real boundaries. Interactive scripts are not counted as automated regression tests.
- **Reason:** The current tests cannot isolate logic regressions or substantiate installer reliability.
- **Consequence:** Each milestone records exact tier/environment/results in `TEST_MATRIX.md`.

## D-030 — Defer development-document disposition to release review

- **Status:** Deferred
- **Date:** 2026-09-08
- **Decision:** Decide in M9 whether audit/blueprint/status/test/decision documents remain in `main`, are condensed, or are excluded from the production tree.
- **Reason:** They are currently necessary for session resilience and accountable development; their final audience is not yet known.
- **Consequence:** Do not remove or rewrite them merely to simplify intermediate diffs.

## D-031 — Separate the core release from governed extensions

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** The core release requires USB audio, push-to-talk, recording LED, local STT/retrieval/LLM/TTS, provenance, content-free telemetry, loopback dashboard, systemd, and lifecycle operations. Wake word, voice power, direct LAN dashboard, and Bluetooth are extensions X1–X4 with independent gates.
- **Reason:** M1B found that combining all desired features made experimental privacy/security risks obscure the feasible research contribution described in the supplied feasibility blueprint.
- **Consequence:** Extension failure cannot block or weaken the core release, and extension dependencies/privileges do not enter the core profile.

## D-032 — Confirm Trixie/Python 3.13 as the single core target

- **Status:** Accepted; resolves D-028
- **Date:** 2026-09-08
- **Decision:** Target current Raspberry Pi OS Lite 64-bit based on Debian 13 Trixie and its distribution Python 3.13, without assuming an exact patch release.
- **Reason:** Current Raspberry Pi documentation identifies Trixie as the latest OS base, and Debian Trixie publishes Python 3.13 as default. Supporting a second OS generation before one clean target passes would multiply unresolved ARM dependency paths.
- **Consequence:** Preflight records exact image/package/systemd versions and fails before mutation on unsupported platforms; real Pi evidence remains mandatory.

## D-033 — Use local-software and conventional service paths

- **Status:** Accepted; supersedes D-019
- **Date:** 2026-09-08
- **Decision:** Use `/usr/local/lib/gonken-agent` for immutable releases, `/usr/local/bin/gonken-agent` as the stable entry point, `/etc/gonken-agent` for configuration, `/var/lib/gonken-agent` for state, `/srv/gonken-agent/corpus` for the administrator-visible corpus, and system cache/runtime paths.
- **Reason:** This is easier to administer and integrates more naturally with systemd-managed directories than an `/opt` + `/etc/opt` + `/var/opt` split while preserving root-owned code and separate state.
- **Consequence:** M3/M6 tests must verify mixed ownership, read-only release code, exact writable paths, and uninstall retention.

## D-034 — Retain at most two release-local virtual environments

- **Status:** Accepted with evidence gate; resolves D-018
- **Date:** 2026-09-08
- **Decision:** Keep the active and one previous validated release, each with its own venv. Require measured staging headroom and report release size before activation.
- **Reason:** Dependency rollback is otherwise unreliable, but unbounded release retention is inappropriate for microSD storage.
- **Consequence:** Low-space preflight blocks staging; failed candidates are captured for diagnosis and then safely cleaned.

## D-035 — Verify named Ollama release assets and model digests

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Install a named stable Ollama ARM64 release only after validating its upstream-published SHA-256. Record the configured model tag and local digest; any digest change is an explicit update requiring revalidation.
- **Reason:** Official releases publish asset checksums and the model API exposes digests, so a mutable privileged `curl | sh` path is unnecessary.
- **Consequence:** M3 records the selected Ollama version/checksum after target validation; the blueprint does not freeze whichever release happened to be newest during review.

## D-036 — Keep the core independent of openWakeWord

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Treat openWakeWord as the first candidate for X1, not a core dependency or predetermined backend. Select it only after a Python 3.13/AArch64, licensing, maintenance, and inference spike.
- **Reason:** Current upstream guidance supports custom training, but current issue evidence includes notebook, Raspberry Pi installation, false-positive, and license questions.
- **Consequence:** Core locks contain no wake dependencies; X1 uses a backend-neutral adapter and separate lock/model card.

## D-037 — Require a distinct continuous-monitoring indicator for wake mode

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** The red LED continues to mean only active utterance recording. Enabling X1 additionally requires a second physical indicator that is on whenever continuous wake sampling is active.
- **Reason:** Local/in-memory processing reduces data exposure but does not remove the ethically relevant fact that the microphone is continuously sampled.
- **Consequence:** A dashboard icon or documentation alone is not sufficient for GX1.

## D-038 — Give the core runtime no host-power privilege

- **Status:** Accepted; supersedes D-027 for the core release
- **Date:** 2026-09-08
- **Decision:** Do not install core sudoers, polkit, capabilities, or a helper that allows the service account to power off/reboot. X2 may proceed only with independent physical confirmation and a separately reviewed root helper.
- **Reason:** Two voice phrases reduce accidental STT activation but do not constrain a compromised network/audio-facing service account.
- **Consequence:** Core security tests prove absence of power authority. SSH/physical host controls remain the supported operations path.

## D-039 — Use `Type=exec` and no core watchdog

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** The first service unit uses `Type=exec`, bounded `Restart=on-failure`, and application health/doctor interfaces. It does not implement `sd_notify` or `WatchdogSec`.
- **Reason:** No dependent unit currently requires application-level readiness, and no measured hang mode yet justifies heartbeat complexity.
- **Consequence:** Notification/watchdog support requires later evidence and tests; it cannot be added as ornamental hardening.

## D-040 — Restrict the core dashboard to loopback

- **Status:** Accepted; resolves D-026
- **Date:** 2026-09-08
- **Decision:** Core configuration rejects non-loopback dashboard binds. SSH forwarding is the supported laptop access path. Direct LAN/phone access is X3.
- **Reason:** A read-only interface can still expose transcripts, institutional filenames, sources, and health data; authentication without a transport/threat model is insufficient.
- **Consequence:** X3 must decide authentication, transport, token lifecycle, rate limiting, and browser-origin behavior before non-loopback binding.

## D-041 — Describe package installation as convergent, not transactional

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** APT/dpkg, pip downloads, and Ollama pulls use postcondition-driven detection, repair, and rerun. Atomic rollback claims apply only to project-owned release/config/index activation.
- **Reason:** Linux package managers and shared model stores cannot be truthfully rolled back as part of one project transaction.
- **Consequence:** Documentation and tests distinguish external provisioning recovery from project release rollback.

## D-042 — Use a durable activation journal and pre-start reconciliation

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Root-owned activation state records candidate, previous release, and phase. Durable writes use same-filesystem staging and atomic replacement; pre-start reconciliation completes or restores an interrupted activation before the app starts.
- **Reason:** Atomic rename prevents torn pointers but does not by itself explain power loss after switching and before post-restart health validation.
- **Consequence:** M3/M8 failure tests interrupt every journal/write/switch/restart boundary; corrupt ambiguity fails visibly.

## D-043 — Retain BM25 only behind a frozen retrieval evaluation

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Use deterministic lexical retrieval first, with at least 40 answerable and 20 unanswerable frozen questions. Initial targets are hit@3 ≥85%, unsupported-answer abstention ≥90%, and valid-source-ID coverage 100%.
- **Reason:** BM25 is proportionate for a bounded text corpus, but architectural simplicity is not evidence of adequate retrieval or grounded answers.
- **Consequence:** Thresholds and index configuration are frozen before final evaluation; a more complex retriever requires measured failure and a new decision.

## D-044 — Make licensing an M2.1 governance gate

- **Status:** Accepted gate; exact project license pending maintainer decision
- **Date:** 2026-09-08
- **Decision:** Build a source/assets/dependencies inventory in M2.1 and obtain explicit maintainer approval for the project/distribution license before claiming a redistributable package.
- **Reason:** Piper is GPL-3.0-or-later, individual voices vary, and other models/assets have separate terms. M1B should not invent the maintainer's licensing choice.
- **Consequence:** Unknown bundled provenance or an unresolved project-license decision blocks release but does not block creation of the package/test skeleton.

## D-045 — Separate transient provenance display from persistent content logging

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Persistent telemetry is content-free by default. The loopback dashboard may optionally display current/last transcript, answer, and escaped source excerpts from memory; restart clears them. Persistence remains explicit research mode.
- **Reason:** Students need inspectable provenance, but observability does not require default retention of speech or generated content.
- **Consequence:** Tests verify that transient display content never enters telemetry/support bundles and that absolute paths/usernames are redacted.

## D-046 — Assign planned verification IDs to every Critical/High audit finding

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Blueprint Section 15 maps each C/H finding to a stable planned verification ID and core/extension disposition.
- **Reason:** A milestone reference alone can create apparent traceability without an executable acceptance test.
- **Consequence:** Implementation sessions must preserve these IDs in `TEST_MATRIX.md`, replacing planned procedures with exact commands/results as tests are created and run.
