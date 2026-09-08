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
