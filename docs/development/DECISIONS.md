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

- **Status:** Accepted release gate; private-development disposition resolved by D-050
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

## D-047 — Establish a dependency-light package before runtime migration

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** `src/gonken_agent` is the installable package boundary. Its public import and CLI use only the Python standard library in M2.1; the inspected prototype remains in `legacy_orchestrator.py` behind an explicit compatibility adapter.
- **Reason:** Moving the entire hardware/network prototype into the new namespace would make package import depend on unavailable devices and experimental features before their milestones define contracts.
- **Consequence:** `gonken-agent run` returns unsupported status until a packaged core runtime exists. `orchestrator.py` preserves the old checkout command for migration testing without representing release readiness.

## D-048 — Make absence of redistribution authority executable

- **Status:** Superseded for private development by D-050; retained as gate history
- **Date:** 2026-09-08
- **Decision:** Package metadata declares neither a license nor runtime dependencies; status reports redistribution false; unknown PNG/WAV media and the legacy runtime are excluded from wheel builds; full-repository ZIPs are not releases.
- **Reason:** No project `LICENSE` exists, source ownership authority is not attested, 14 media assets have unknown provenance, maintained Piper is GPL-3.0-or-later, and configured voice/wake artifacts include noncommercial terms.
- **Consequence:** The package/identity work can be tested and committed, but M2.1 and any public release remain blocked until the maintainer records project-license/authority and artifact decisions.

## D-049 — Keep M2.1 host validation dependency-free

- **Status:** Accepted as a transitional testing choice; D-029 remains authoritative for M2.4
- **Date:** 2026-09-08
- **Decision:** Use Python `unittest` for M2.1 package-boundary tests because the clean audit host has no pytest and M2.4 owns test-framework dependencies and suite restructuring.
- **Reason:** Adding or downloading pytest during the package skeleton milestone would violate its standard-library-only validation boundary and prematurely modify dependency profiles.
- **Consequence:** The 16 tests remain pytest-discoverable in structure if desired, but the recorded M2.1 command is `PYTHONPATH=src python -m unittest discover -s tests/unit -v`.

## D-050 — Continue under an explicit no-redistribution policy

- **Status:** Accepted; resolves the M2.1 development branch of D-044/D-048
- **Date:** 2026-09-08
- **Decision:** Grant no project license and prohibit redistribution until a future maintainer explicitly attests licensing authority and approves project/documentation terms. Local wheels and full-history ZIPs are private validation/handoff artifacts, never releases.
- **Reason:** No license selection or ownership attestation was supplied. A conservative prohibition is the only policy that does not invent permission while still allowing private engineering work to continue.
- **Consequence:** M2.1 can close and M2.2 can proceed, but publication, public repository export, public ZIP handoff, and release claims remain blocked. A future licensing decision must be explicit and cannot be inferred from continued development.

## D-051 — Quarantine unknown and noncommercial artifacts

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Retain the 14 unknown PNG/WAV files only as private legacy compatibility evidence and exclude them from packages, releases, and public exports. Treat the configured CC BY-NC-SA Piper voice and bundled openWakeWord model as internal legacy-evaluation inputs only. Maintained GPL Piper is not a declared core package dependency until a release-compatible integration/licensing decision passes.
- **Reason:** Hashes establish artifact identity, not provenance or redistribution rights. Removing these inputs from the active package/release boundary preserves implementation evidence without presenting unclear or noncommercial terms as distributable project content.
- **Consequence:** Tests enforce package exclusion and the machine-readable quarantine policy. A future public release must prove rights or remove/replace media, select compatible voice/wake artifacts, and review whether Git history must be filtered.

## D-052 — Make one shipped TOML the executable configuration authority

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** `config/defaults.toml` is the sole source-controlled default-value artifact and is installed as wheel data. A typed standard-library loader applies complete defaults, partial site TOML, explicit mapped `GONKEN_<SECTION>_<FIELD>` variables, and one-shot CLI overrides in that order. Installer, doctor, compatibility runtime, and component construction consume that authority instead of defining fallback model, endpoint, audio, or artifact values.
- **Reason:** H-01/H-02 were caused by independently reasonable defaults that could silently diverge. Typed shape/value validation and source attribution turn equality into an executable contract.
- **Consequence:** Unknown TOML/CLI keys, invalid types, non-loopback endpoints/binds, unsafe path forms, conflicting GPIO/audio settings, content-persistent privacy settings, and enabled unaccepted extensions fail configuration readiness. Unrelated installer `GONKEN_*` variables are outside the runtime map and ignored.

## D-053 — Treat legacy configuration as a guarded import, never a live layer

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Legacy `config/config.json` and `.env` are read only by the explicit migration command. Migration validates the complete prospective configuration before writing, uses same-filesystem atomic replacement for a new destination, refuses a different existing destination, preserves inputs, and stores one timestamp/hash-addressed backup per unchanged input with directory/file modes `0700`/`0600`. Populated obsolete cloud credentials and enabled legacy UI/streaming options fail rather than leaking into offline core.
- **Reason:** Loading legacy files alongside site/environment values would preserve precedence ambiguity, while rewriting them in place would make failed or repeated migrations destructive.
- **Consequence:** Repeat migration converges without output or backup churn. Normal runtime never mutates site configuration, effective output redacts paths, and a maintainer must explicitly handle unsupported legacy features rather than having them silently re-enabled.

## D-054 — Lock only dependencies that are genuinely selected

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** Make `requirements/profiles.toml` the dependency-profile authority and generate exact, hash-enforcing, wheel-only locks from it. At M2.3 the maintained headless package and standard-library test suite have zero third-party dependencies; pygame 2.6.1 is a separately locked optional UI extra. The wake and future voice-runtime profiles remain blocked and receive no placeholder locks. CPython 3.12 is supported for x86 development while CPython 3.13 remains the sole production target.
- **Reason:** The maintained runtime has not yet moved into the package. Pretending its legacy broad ranges are an accepted core graph would bless untested transitive resolution, a `--no-deps` openWakeWord workaround, GPL Piper integration, and a noncommercial voice. An exact empty lock truthfully describes the current maintained package; a blocked manifest is safer and more reconstructable than a lock that cannot pass its gates.
- **Consequence:** `requirements.txt` is removed. Its remaining ranges live only in `requirements/legacy-prototype.in`, which the retained `setup.sh` labels unaccepted; pygame is removed from that mandatory input and from required doctor imports. Future runtime work must add every selected direct/transitive wheel, version, hash, source, and license to the accepted profile, then pass cross-resolution and a physical Pi venv before claiming target support.

## D-055 — Enforce test tiers before adding a third-party runner

- **Status:** Accepted; refines D-029 without weakening its isolation rule
- **Date:** 2026-09-08
- **Decision:** Use `scripts/ci.sh` as the single T0/T1 entry point and Python's standard-library `unittest` as the executable runner at M2.4. Keep tests pytest-discoverable by convention, but do not claim pytest execution or add pytest until its complete exact/hash-locked graph can be resolved and installed from a controlled wheelhouse. Live Ollama and physical audio/wake programs use non-discoverable `*_manual.py` names, separate directories, and explicit opt-in variables.
- **Reason:** The current environment has no pytest and package-index execution is blocked. Introducing an untested or partly reconstructed pytest lock solely to satisfy a tool name would contradict M2.3's dependency policy. The governing requirement is deterministic tier isolation: default tests must not contact a network, service, model, device, or privilege boundary.
- **Consequence:** M2.4 acceptance is runner-independent and executable from the exact empty dev profile. A future switch to pytest is a reviewed dependency change, not a test rewrite. Interactive exit codes remain observations requiring environment records; they are never counted as automated regression evidence.

## D-056 — Make bootstrap preflight authoritative before provisioning

- **Status:** Accepted
- **Date:** 2026-09-08
- **Decision:** M3.1 `bootstrap.sh` performs only fail-closed preflight. It accepts the production target or an explicit development-host mode, validates local platform/resources before remote access, performs one sudo validation for non-root execution, rejects all dirty or unexpected existing checkout states, resolves a unique advertised HTTPS branch/tag to a full commit, then creates a private staging record. Until M3.2 exists, the default path exits `M3_2_UNAVAILABLE` and never invokes the retained `setup.sh`.
- **Reason:** Calling the monolithic prototype after partial checks would preserve H-03/H-04 and allow a preflight success to become an ungoverned installation. The source record also becomes a supply-chain boundary: it records facts but is never sourced as shell code. An initial 8 GiB free-space floor and approximately 3.5 GiB target-RAM floor are conservative admission thresholds for the declared 4GB/64GB target; they are not performance claims.
- **Consequence:** Direct root works without `sudo`; sudo-root retains the invoking account identity; non-root validates credentials once before remote access; unsupported OS/architecture/Python/init/board/image, implausible time, low resources, missing commands, source failure, and checkout conflicts stop before any package/service/configuration/release mutation. M3.2 must consume and independently validate the record, add convergent prerequisite/source steps, and recalibrate provisional resource thresholds from physical-Pi evidence rather than weakening them silently.

## D-057 — Make M3.2 a probe-authoritative control boundary

- **Status:** Accepted; narrows D-056 sequencing without weakening its preflight requirements
- **Date:** 2026-09-08
- **Decision:** M3.2 implements the stable step/state engine, independent M3.1 record and advertised-commit revalidation, private atomic state/event records, exclusive boot/PID/start-identity locking, stale-lock recovery, and signal cleanup before any real provisioning step is admitted. State is advisory: every invocation runs the real postcondition, repairs a false `complete`, and reconstructs missing state from a passing probe. Bootstrap routes to this engine but stops at `M3_3_UNAVAILABLE`. Source acquisition and bootstrap-prerequisite mutation move to M3.3 so the verified tree is created directly as an immutable candidate rather than as a mutable intermediate checkout.
- **Reason:** Combining engine validation with the first APT, source, venv, and activation mutations would make interruption defects harder to distinguish and would create an ungoverned source-execution gap. A control-only checkpoint allows before/during/after and abrupt-death semantics to be proven with fake steps before the engine gains target authority.
- **Consequence:** M3.2 writes only inside the effective-user-owned private bootstrap staging/state tree and installs nothing. Step records and content-free event files use same-directory atomic rename; cooperative signals remove registered temporaries and owned locks; abrupt death leaves observable `running` state and a recoverable identity-bound stale lock. The procfs-constrained fallback is conservative and recorded. M3.3 must reuse this protocol, add immutable verified source/release acquisition, and revalidate H-10 at real candidate/journal/switch boundaries; neither M3.2 success nor `--engine-only` means the assistant is installed.

## D-058 — Bind installation to an immutable commit release and durable activation truth

- **Status:** Accepted
- **Date:** 2026-09-09
- **Decision:** M3.3 refetches the exact commit in the private M3.1 source record, rejects an identity change and unsafe Git archive content, builds one local wheel, installs the applicable exact/hash runtime lock and wheel into a release-local venv, and finalizes only a completely smoke-tested payload at `/usr/local/lib/gonken-agent/releases/<commit>`. The release records its source/profile/interpreter/package/build-backend identity, lock/wheel/helper/payload digests, ownership, size, and validation result. `current` is a constrained relative symlink replaced atomically under a private four-phase activation journal and nonblocking maintenance lock. Reconciliation completes a valid pending activation or restores the recorded previous validated release; retention keeps active plus previous only.
- **Reason:** A source checkout, successful package command, or advisory step record is not sufficient installation truth. The irreversible boundary must be a self-contained validated payload whose identity can be checked independently, while interruption around pointer replacement must be recoverable without guessing. A single installed-state engine path also prevents separate bootstrap staging directories from bypassing mutual exclusion.
- **Consequence:** Target bootstrap crosses the already validated sudo boundary once, creates a dedicated non-login runtime identity, and owns code/state as root while running smoke checks as the service account. The distribution setuptools backend is an APT-managed bootstrap prerequisite whose exact observed version is recorded; runtime dependencies remain governed by project exact/hash locks. Test-only TERM/KILL injection covers every candidate/journal/pointer/postcheck boundary and is inert without an explicit gate. Host evidence closes the M3.3 mechanism but does not establish Raspberry Pi filesystem durability, service startup, or physical power-loss recovery. `M3_3_RELEASE_COMPLETE` is a package/activation result only; normal bootstrap stops at `M3_4_UNAVAILABLE` and cannot claim assistant readiness.

## D-059 — Pin stable Ollama and bind a mutable model tag to observed full digest

- **Status:** Accepted
- **Date:** 2026-09-09
- **Decision:** M3.4 admits Ollama `0.33.3` through the published ARM64 asset SHA-256 and installs it as a root-owned immutable versioned payload. It runs under a distinct non-login `ollama` account with loopback binding, `OLLAMA_NO_CLOUD=1`, one loaded model, and one parallel request. The authoritative `qwen3.5:2b-q4_K_M` catalog digest prefix is source-pinned; after pull the local tags API must supply a matching full 64-character digest, which is persisted and becomes the rerun identity. A changed full digest fails closed rather than silently updating.
- **Reason:** The newer upstream `0.34.0` entry was a pre-release at verification time, while a tag name alone is not immutable model identity. Inventing a full digest that could not be independently obtained would be weaker than recording the value actually returned by the verified local API and constraining it with the official catalog prefix.
- **Consequence:** Exact-source release maintenance owns the manifest/unit/manager inputs; checksum failure, unsafe archives, conflicting units/accounts/paths, wrong API version, digest/quantization drift, and incomplete smoke all block completion. Host fixtures establish mechanisms and interruption convergence only. Pi memory/latency/thermal behavior, real HTTPS acquisition, systemd/account creation, storage durability, reboot behavior, and M5.2 kernel-observed no-outbound-runtime enforcement remain open target gates.

## D-060 — Continuous progression and evidence-separated status

- **Status:** Accepted by maintainer instruction, 2026-09-09.
- **Decision:** Remove one-package-per-session limits. Continue after verified items; group coherent changes and commit at tested boundaries. A blocked hardware/artifact requirement does not block independent software modules.
- **Evidence:** M3.4 Git history and all 135 host tests pass; the previous status grouped completed tasks under Not Started and the blueprint explicitly instructed stopping.
- **Consequence:** MILESTONES.json is the complete item ledger; generated status is checked by CI. Software progress and target acceptance are separate. Do not label the whole project M7/M9 merely because later independent software exists. Prior next-only authorization statements are historical and superseded by this decision.

## D-061 — Advance local runtime contracts independently of speech provisioning

- **Status:** Accepted implementation choice under D-060, 2026-09-09.
- **Decision:** Implement the sequential coordinator, bounded PCM frame buffer, stable selector/retry, subprocess speech adapters and PTT controller against injected adapters while the real speech chain remains gated. The default voice runtime still fails closed.
- **Reason:** These contracts can be tested without granting fake hardware readiness or introducing an unpinned Python dependency.
- **Consequence:** Use a dependency-free 97-tap windowed-sinc anti-alias FIR for integer 16/32/48→16kHz paths. Reject unsupported ratios; deterministic spectral tests pass, but CPU/latency on Pi remains an acceptance gate. Physical capture/GPIO and pinned artifacts are still required. Temporary speech outputs are context-managed; process groups are terminated on cancel/error/timeout.

## D-062 — Deliver an explicit grounded text diagnostic before voice activation

- **Status:** Accepted implementation choice, 2026-09-09.
- **Decision:** Add `index`, `ask`, `run --text-only`, `dashboard`, and package `doctor`. `--extractive` explicitly returns a retrieved excerpt; otherwise only the effective loopback Ollama model is contacted. Plain `run` still fails closed for voice.
- **Consequence:** No hardware readiness is implied. Text mode enables end-to-end grounding/observability and signal testing now. Models cannot trigger tools. Citation shape/IDs are enforced but factual entailment and real-model injection behavior remain empirical gates. Persistent interaction content remains rejected; optional dashboard content is memory-only.

## D-063 — Separate synthetic regression from real-lab acceptance

- **Status:** Accepted, 2026-09-09.
- **Decision:** Ship ten invented equipment documents, 30 development calibration cases and a frozen 40-answerable/20-unanswerable extractive smoke set. Preserve deterministic metrics and fixture hashes.
- **Consequence:** The corpus is explicitly fictional; positives share fact templates and negatives are out of domain. These percentages cannot close real-lab retrieval/abstention, reasoning, speech or Pi benchmark gates. Real data and representative near-miss questions must precede research claims.

## D-064 — Export constructed diagnostics, never bulk-copy support files

- **Status:** Accepted, 2026-09-09.
- **Decision:** `gonken-agent support` builds a new private ZIP from redacted effective configuration, categorical health, non-identifying runtime versions and revalidated content-free telemetry. It never recursively copies logs, configuration, corpus, Git history, audio, secrets or arbitrary exception detail. Existing destinations and publication races fail without overwrite.
- **Consequence:** M8.1 advances at the host tier while detailed Pi probes remain open. A malformed/content-bearing telemetry record rejects the export; content is never silently included. Diagnostic bundles and private source checkpoints have different purposes and contents.

## D-065 — Retain traceable development evidence in private checkpoints

- **Status:** Accepted, 2026-09-09.
- **Decision:** Retain `docs/development`, the supplied feasibility source, test evidence and Git history in the private checkpoint. Replace only the confusing current-status presentation with the complete generated ledger. Use the concise current guide as the entry point.
- **Consequence:** No history or quarantined baseline material is deleted to make a checkpoint appear release-ready. Public-release disposition and license approval remain separate gates. M9.5 is recorded conservatively as partial until the final archive verification is attached to the handoff.

### D-065 transport evidence update

The private archive verification now passes. M9.5 is host-verified for transport;
the earlier pending verification note is historical. Release-candidate acceptance
remains open. The final archive is regenerated after this status update and its
transport checks are repeated.


## D-066 — Provision speech through pinned external artifacts, not app dependencies

- **Status:** Accepted
- **Date:** 2026-09-09
- **Decision:** M3.5 installs Whisper and Piper through root-owned maintenance
  tooling and immutable artifact directories. Whisper uses `whisper.cpp` v1.9.2
  plus the checked `base.en-q5_1` model. Piper uses `piper-tts==1.8.0` in a
  separate root-managed CLI venv and selects `en_US-ljspeech-medium`, replacing
  the noncommercial legacy `en_GB-semaine-medium` default.
- **Reason:** The application package must stay governed by the exact core lock,
  while speech binaries/models have different build, license, size, and runtime
  properties. A subprocess CLI boundary lets the installer validate concrete
  artifacts without quietly adding GPL/transitive packages to the app wheel.
- **Consequence:** Checksums, immutable paths, stable wrapper links, private
  install records, and rerun/repair behavior are the M3.5 source of truth.
  Redistribution remains disallowed; real Pi compilation/download, STT/TTS
  latency, audio routing, and reboot persistence remain target gates.

## D-067 — Treat speech smoke as software evidence, not appliance readiness

- **Status:** Accepted
- **Date:** 2026-09-09
- **Decision:** M3.5 requires a content-free real speech-chain smoke: Piper
  generates a fixed WAV, Whisper transcribes it, and required tokens must appear
  before `M3_5_SPEECH_COMPLETE` is emitted. The success record stores artifact
  identities and omits transcript/audio content.
- **Reason:** A successful package install alone would miss broken wrappers,
  bad model paths, incomplete downloads, or unusable binaries. At the same time,
  a host fixture cannot prove microphone, speaker, GPIO, service, thermal, or
  reboot behavior.
- **Consequence:** `--speech-only` is a tested milestone return point. M3.6 replaces the
  unavailable boundary with `M3_6_INSTALL_SUMMARY`, but the summary still reports
  `DEGRADED` and `ready=false`; this is still not `READY`.

## D-068 — Start systemd through a degraded headless supervisor

- **Status:** Accepted
- **Date:** 2026-09-09
- **Decision:** M6.1/M6.2 install `gonken-agent.service` with `ExecStart` set to
  `gonken-agent service`, not the unfinished voice `run` entry point. The service
  emits content-free degraded readiness and remains supervised until physical
  audio/GPIO acceptance can close later milestones.
- **Reason:** A systemd service that immediately executes the fail-closed voice
  path would create a restart loop and obscure the true project state. A headless
  supervisor gives boot persistence, logging, privilege boundaries and reversible
  install/remove behavior without falsely claiming microphone/speaker readiness.
- **Consequence:** Service installation can advance independently under D-060,
  while target start/stop/restart, reboot persistence, audio hotplug recovery,
  journal review and systemd-analyze verification remain hardware/target gates.

## D-069 — Roll back by reusing validated activation, not ad hoc symlink edits

- **Status:** Accepted
- **Date:** 2026-09-09
- **Decision:** The first M8.2 lifecycle entry point is `rollback.sh`, backed by
  `release_manager rollback-previous`. It rolls back only to the previous
  post-verified release recorded in the activation journal, then restarts
  `gonken-agent.service`.
- **Reason:** Release rollback should use the same validation, locking, journal
  and pruning rules as normal activation. A separate shell-only symlink switch
  would duplicate critical state-machine logic and risk producing a state that
  pre-start reconciliation cannot understand.
- **Consequence:** Explicit rollback advances at the host software tier. Update
  acquisition, schema migration/backups, target rollback execution and uninstall
  remain open lifecycle work.

## D-070 — Uninstall removes only project-owned runtime files by default

- **Status:** Accepted
- **Date:** 2026-09-09
- **Decision:** `uninstall.sh` keeps GonKenLab data by default and removes only
  the managed application service, tmpfiles definition, stable CLI symlink and
  immutable application release root. Purging `/var/lib/gonken-agent`,
  `/var/cache/gonken-agent` and `/srv/gonken-agent` requires
  `--purge-data --confirm-purge purge-gonken-agent-data`.
- **Reason:** The project must support recovery and clean reinstall without
  quietly deleting state, corpus, diagnostics or downloaded material. Shared
  Ollama units, binaries, users and model stores are not owned by application
  uninstall and must not be removed here.
- **Consequence:** M8.3 can close at the host software tier for keep-data
  uninstall, purge confirmation and conflict refusal. Real target uninstall,
  user/group disposition, service stop failures and clean-image reinstall remain
  target acceptance work.

## D-071 — Update through explicit immutable release activation

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision:** `update.sh` is an explicit administrator-invoked operation backed
  by `update_manager.py`. It resolves one unambiguous Git branch/tag, builds the
  exact immutable release for that commit, activates it through
  `release_manager`, prunes through the release retention policy, and restarts
  `gonken-agent.service`.
- **Reason:** Update must not be a boot-time network action and must not mutate
  the active installation directly. Reusing the release manager preserves the
  same validation, locking, journal, rollback and post-switch smoke checks used
  by bootstrap installation.
- **Consequence:** M8.2 closes at the host software tier for explicit
  update/rollback mechanics. Real target update/rollback, service restart
  failures and future schema migrators remain acceptance gates.

## D-072 — Treat target hardware uncertainty as captured evidence, not a cloud blocker

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision:** The headless service records a content-free startup hardware and
  software snapshot by default. Debug mode keeps a bounded recent history;
  production mode keeps only the latest snapshot unless retention is explicitly
  requested. `collect-support.sh` packages the latest startup snapshot, health,
  redacted configuration and content-free telemetry into one private support ZIP.
- **Reason:** The development cloud cannot validate USB audio enumeration,
  GPIO, Pi thermal state, reboot behavior, or real systemd journals. Waiting for
  unavailable hardware would delay independent software work, while unstructured
  raw logs would weaken privacy and make uploaded evidence harder to review.
- **Consequence:** M8.1 and M9.3 can close at the host software tier for
  diagnostic capture and operator guidance. M9.1 remains a real target campaign,
  but later sessions can use uploaded support ZIPs as evidence for the next
  repair cycle.

## D-073 — Declare a private release-candidate readiness gate before Pi testing

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision:** `scripts/release_readiness.py` is the repository-level gate for
  moving from cloud development to private Raspberry Pi acceptance testing. It
  requires all declared host-ready foundations to be host-verified, scans active
  release paths for high-risk secret patterns, reports dirty-tree state, and
  lists every remaining target gate as unrun evidence.
- **Reason:** “Ready to test on the Pi” is different from “accepted on the Pi”
  and also different from “approved for public release.” The project needs a
  strict but honest boundary that lets implementation proceed to real hardware
  without erasing the missing physical evidence.
- **Consequence:** M9.2 can close for private target-acceptance readiness at the
  host tier. Public redistribution, third-party artifact licensing and target
  hardening remain later release decisions.


## D-074 — Keep Bluetooth audio opt-in, headless, and independently recoverable

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision:** Bluetooth audio is an X4 extension selected only with
  `--bluetooth-audio` (optionally `--bluetooth-device NAME_OR_MAC`). Bootstrap
  prepares BlueZ plus a dedicated lingering `gonken-agent` PipeWire/WirePlumber
  user session, pauses at an explicit pairing action, trusts exactly one
  verified audio device, and installs a bounded reconnect helper for that
  recorded device. USB audio remains the core fallback.
- **Reason:** The target evidence confirms onboard Bluetooth and a USB AIRHUG
  audio path. Automatic discovery is useful, but silently pairing an arbitrary
  nearby device would be unsafe and a mandatory Bluetooth stack would make the
  reliable USB path more fragile.
- **Consequence:** Fresh installs remain unattended through the core path. An
  operator requesting Bluetooth receives one deliberate pairing checkpoint;
  later boots may reconnect only the recorded trusted device. Physical A2DP,
  HFP/HSP microphone/profile switching and reboot reconnect remain target gates.

## D-075 — Optional filesystem resources must not make systemd namespace setup fatal

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision:** Optional paths in service namespace directives use systemd's
  non-fatal `-` prefix. Release reconciliation is a bounded privileged
  `ExecStartPre=+` operation with explicit write access to root-owned installer
  state; the long-running service remains the unprivileged `gonken-agent` user.
- **Reason:** The physical Pi proved that `ReadOnlyPaths=/srv/gonken-agent/corpus`
  fails the service at `226/NAMESPACE` when the optional corpus directory is not
  present, before the pre-start helper can execute.
- **Consequence:** The known FIX2 unit is upgraded in place by exact hash;
  administrator-modified units still fail closed. Service-start failures now
  include bounded status/journal context and stale systemd failure counters are
  reset before retry.

## D-076 — Make the official source/ref and first-install path zero-configuration defaults

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision:** `bootstrap.sh` defaults to the official GonKenLab Agent HTTPS
  repository and `main`. A root-level `install-gonken.sh` is the thin streamed
  first-install/update launcher: it prepares only `ca-certificates`, Git and
  Python, creates/updates a clean checkout, then delegates all governed target
  mutation to `bootstrap.sh`. Unknown launcher arguments pass through unchanged.
- **Reason:** The release URL/ref are project defaults rather than information a
  normal user should repeatedly type. The outer launcher removes clone/APT
  mechanics from onboarding without duplicating the installer state machine.
- **Consequence:** The normal checkout command is `./bootstrap.sh`; the fresh-Pi
  command is one HTTPS launcher. Custom forks/refs remain explicit options.
  A dirty or diverged checkout fails closed instead of being overwritten.

## D-077 — Bluetooth identity is deployment input and audio-session access is explicit

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision:** An exact Bluetooth MAC or name substring may be supplied only as
  bootstrap input. A known exact MAC is checked directly in BlueZ before any
  discovery scan. The dedicated headless PipeWire/WirePlumber user session is
  reachable from the app/reconnect services through its own `/run/user/<uid>`
  namespace; the reconnect helper retains only `CAP_SETUID`/`CAP_SETGID` so it
  can execute `pactl` as the dedicated audio user.
- **Reason:** Device-specific identities must not become repository constants.
  Also, `ProtectHome=true` would hide `/run/user` and an empty capability set
  would prevent the reconnect helper from dropping to `gonken-agent`, making a
  nominally paired Bluetooth device unusable by the headless audio session.
- **Consequence:** Bluetooth remains opt-in and USB remains fallback, but the
  implementation now has a coherent no-login session/reconnect path suitable
  for real-Pi validation.

## D-078 — Define install completion as operational appliance readiness

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision:** Normal target bootstrap completes only after the systemd service
  has opened physical audio, confirmed the local model and written an ephemeral
  content-free voice-runtime readiness record. Package/service installation
  alone is not a `READY` outcome.
- **Reason:** Real FIX4 target evidence showed all software components and the
  service could install successfully while no supported production voice path
  was actually available to the user.
- **Consequence:** The installer has a final appliance-readiness step and waits
  for the long-running service rather than telling the operator to manually
  infer what to do next.

## D-079 — Use systemd boot activation rather than passwordless shell auto-login

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision:** Everyday appliance startup is provided entirely by enabled
  systemd services. GonKenLab Agent does not require or configure console
  auto-login or password bypass.
- **Reason:** system services start before an interactive login and therefore
  satisfy the no-touch appliance requirement without weakening account access.
- **Consequence:** A reboot is expected to end at voice wake standby even when
  nobody logs in. SSH credentials remain an administration boundary only.

## D-080 — Ship a functional Whisper phrase-spotting wake baseline first

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision:** The first production wake loop uses short, bounded local Whisper
  captures to identify the configured `Hey Gonken` phrase. A dedicated wake-word
  model remains an optimization extension.
- **Reason:** Whisper is already pinned/provisioned and avoids introducing an
  unverified second wake model at the last-mile integration stage.
- **Consequence:** Functional always-on wake behavior can be physically tested
  now; CPU/latency measurements from the Pi will determine whether a dedicated
  wake model is required later.

## D-081 — Require both automatic and manual production voice entry points

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision:** The supported production surface includes automatic
  `gonken-agent.service`, foreground `gonken-agent run`, one-turn
  `gonken-agent talk`, systemd controls, journal diagnostics and doctor probes.
  Legacy orchestrator entry points are not user-operation instructions.
- **Reason:** A headless appliance needs unattended boot operation, but repair
  and acceptance work also need a deterministic manual path independent of
  boot automation.
- **Consequence:** Operations are documented separately in
  `docs/OPERATIONS.md`; the README stays focused on installation and everyday
  use.

## D-082 — Reconcile Bluetooth radio state as a governed prerequisite

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision:** X4 stack readiness requires active BlueZ, a real controller,
  no hard block, no soft rfkill block, `Powered=yes`, and a responding dedicated
  PipeWire user session. Root setup/autoconnect may start BlueZ, unblock a soft
  block and power the controller before retrying.
- **Reason:** Real Pi pairing repeatedly timed out until the operator manually
  ran rfkill/service/controller-power commands even though Bluetooth packages
  were installed.
- **Consequence:** Bluetooth setup now tests prerequisites before pairing rather
  than reporting a downstream discovery timeout for an upstream radio problem.

## D-083 — Keep WLAN-country selection outside automatic installer mutation

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision:** Fresh-Pi documentation requires Raspberry Pi Imager (or explicit
  `raspi-config`) to set the legal WLAN country. The launcher may report blocked
  Wi-Fi, but it does not guess or silently change the country.
- **Reason:** The internet installer cannot bootstrap over unavailable Wi-Fi and
  regulatory country is deployment/location information, not a repository
  constant.
- **Consequence:** Ethernet remains an accepted first-install path. Once a valid
  country is set, normal OS tools can unblock/enable Wi-Fi.

## D-084 — Treat Raspberry Pi 4 as a separate future target profile

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision:** Do not broaden the Pi 5 production preflight to Pi 4 in FIX5.
  Pi 4 support requires its own memory, thermal, inference, wake and audio
  acceptance evidence and may require different configuration limits.
- **Reason:** Generic code structure does not establish real-time appliance
  suitability on different hardware.
- **Consequence:** Portability work is preserved without reducing the evidence
  standard of the currently proven target profile.

## D-085 — Keep physical audio discovery device-generic by default

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision:** The production defaults use `audio.input_match=auto` and
  `audio.output_match=auto`. Runtime discovery prefers one unambiguous USB audio
  card over HDMI/video outputs and fails closed when multiple USB cards make the
  choice ambiguous. Product names such as AIRHUG remain deployment evidence, not
  source constants.
- **Reason:** The clean-card installer must work with future microphones/speakers
  without turning the current Pi's hardware inventory into hard-coded policy.
- **Consequence:** Sites with several USB audio devices use explicit selectors;
  Bluetooth selection remains separately governed by its recorded identity.

## D-086 — Upgrade Bluetooth reconnect policy exactly and make headset input explicit

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision:** FIX5 may replace only the exact known FIX4 Bluetooth reconnect
  unit hash. The new helper reconciles radio readiness at boot and, for a
  headset-capable device that exposes A2DP output but no microphone source,
  selects an available HFP/HSP capture profile (preferring mSBC when available).
- **Reason:** The real Pi proved pairing/autoconnect, but the appliance contract
  requires a microphone path after reboot as well as playback. Exact-hash
  migration preserves the existing fail-closed administrator-file policy.
- **Consequence:** Fully wireless voice operation is deterministic when the
  headset supports HFP/HSP; unexpected locally edited systemd units are never
  overwritten silently.


## D-087 — Separate installed service structure from appliance runtime readiness

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision:** Installer preconditions for `application_service` and
  `appliance_readiness` validate governed files and boot enablement without
  requiring the process to already be active. `appliance_manager activate` owns
  restart/convergence and physical READY.
- **Reason:** FIX6 failed immediately at `INSTALL_PRECONDITION`, preventing the
  action intended to repair/start a transient service.
- **Consequence:** A service waiting for late audio can be converged rather than
  rejected before readiness logic runs.

## D-088 — Generate the service-user PipeWire environment from the real UID

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision:** The system service loads a generated governed runtime-environment
  file containing `/run/user/<gonken-agent-uid>` and its D-Bus path. `%U` is
  forbidden in the governed system unit for this purpose.
- **Reason:** Real support evidence showed euid 999 while Pulse/WirePlumber tried
  `/run/user/0`, whereas a manual run with `/run/user/999` successfully reached
  wake standby and completed voice turns.
- **Consequence:** Headless audio no longer depends on an incorrect system-manager
  UID expansion; upgrades and uninstall manage the generated file explicitly.

## D-089 — Prefer existing wired audio while retaining Bluetooth fallback

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision:** `auto` routing prefers usable USB for each direction, then the
  exact configured Bluetooth endpoint. Discovery is delayed/retried rather than
  treated as a constructor-time invariant.
- **Reason:** The target can expose the same AIRHUG through USB and Bluetooth and
  can boot before one transport is enumerated. Provisioning identity must not
  override actual route availability.
- **Consequence:** Existing connections are reused, wired wins when present, and
  Bluetooth becomes automatic fallback without unpairing or reinstalling.


## D-080 — Start V09 as an environment-control implementation line

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Start the V09 implementation branch from FIX7 commit `3b25b81c5bc7d4e24268726ad7f7b71296215a03`, bump the development version to `0.2.0.dev0`, and record V09 work under M10 milestones.
- **Reason:** The V09 blueprint is a substantial new cyber-physical scope and must not be hidden inside the FIX7 release-candidate status.
- **Consequence:** FIX7 target-acceptance evidence remains historically useful, but V09 completion and physical acceptance require fresh M10 evidence.

## D-081 — Add static environment schema as disabled-by-default schema 2

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Static TOML schema 2 adds `extensions.environment` with disabled defaults for SHT31, libgpiod relay, socket path, mutable policy path and hard policy bounds. Schema-1 site files are accepted as migration inputs without downgrading the effective schema.
- **Reason:** Generic upgrades must not unexpectedly actuate hardware, and static/admin authority must remain separate from mutable fan policy.
- **Consequence:** Target installation still needs a real migration/provisioning pass before environment hardware is enabled.

## D-082 — Use daemon-owned mutable environment policy JSON schema 1

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The mutable environment policy is represented as schema-1 JSON with generation, mode, start/stop thresholds and dwell values, constrained by static bounds and persisted by same-directory atomic replacement.
- **Reason:** Ordinary CLI/voice policy changes should not edit root-owned static configuration or expand the hardware safety envelope.
- **Consequence:** Policy corruption, generation conflicts and invalid threshold/dwell values fail closed; controller and service integration remain later milestones.

## D-083 — Preserve the purchased fan capability boundary

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** V09 domain objects report power control only; they do not claim software speed control or observed blade motion with the current relay/PENGLIN/ELUTENG hardware.
- **Reason:** The relay can command USB 5V power, but no tachometer, current sensor, airflow sensor or electronic speed-control path is present.
- **Consequence:** Later CLI/voice responses and diagnostics must derive from relay/controller results and must not claim physical RPM or software speed selection.

## D-090 — Keep M10.4 controller pure and treat AUTO direct ON/OFF as MANUAL override

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The M10.4 controller core is dependency-free and owns only deterministic state-machine semantics.  Direct operator ON/OFF commands while in AUTOMATIC atomically switch policy mode to MANUAL and apply the requested relay-power boundary; SEMI_AUTOMATIC never starts from temperature alone; DISABLED rejects ON and remains safe-off.
- **Reason:** The V09 governance boundary requires deterministic software to own physical-control policy while preventing the LLM, CLI or future service clients from bypassing mode semantics or inventing hardware state.
- **Consequence:** Later IPC, CLI and voice layers must report controller-returned mode/power results truthfully.  They may not claim fan motion, speed control, or successful actuation without the single-owner environment service confirming the result.

## D-091 — Classify the Ollama lifecycle interruption timeout as a non-V09 integration risk for M10.4

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The reproducible timeout in `test_every_download_extract_readiness_pull_and_smoke_boundary_recovers` is recorded as an existing integration-fixture/harness risk and does not block M10.4, because the controller core imports no Ollama, audio, systemd, I2C or GPIO code.
- **Reason:** The isolated recheck left an `ollama_manager.py install-binary` process alive after the watchdog expired in this container.  Treating this as a controller failure would be false attribution; treating it as a PASS would be false-green.
- **Consequence:** Broad integration/CI remains `NEEDS_MANUAL_REVIEW` until the lifecycle interruption fixture is repaired or bounded more narrowly.  M10.5 may proceed with targeted host tests while preserving this integration caveat.

## D-092 — Establish bounded local environment IPC before CLI and voice integration

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** M10.5 defines protocol v1 as bounded JSON over AF_UNIX with the allow-listed operations `status.get`, `sensor.read`, `health.get`, `fan.set`, `mode.set`, `policy.get`, `policy.update` and bounded non-destructive `probe.run`.  The first service path is host-fake and reports `physical_evidence=false`; it imports no `smbus`, `gpiod`, shell or model-runtime surface.
- **Reason:** The V09 architecture requires one deterministic service boundary before CLI and voice can safely share behavior.  Implementing the client/server contract before hardware adapters prevents duplicated GPIO ownership and prevents the LLM or operator path from acquiring raw hardware authority.
- **Consequence:** M10.6 must use this client boundary for CLI/voice/diagnostics integration.  M10.5 can pass host verification, but it cannot close any physical SHT31/relay/fan acceptance gate.

## D-093 — Make `gonken-agent env` an IPC client only

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The first M10.6 sub-batch exposes `gonken-agent env` commands through `EnvironmentClient`; it does not read or write the mutable policy file directly and does not import GPIO, I2C, shell or hardware adapter code.
- **Reason:** The V09 blueprint requires the CLI and voice paths to share the same deterministic environment service boundary so that one owner controls physical state and all callers receive the same daemon-confirmed result.
- **Consequence:** CLI output can report daemon-returned mode, relay-power boundary, policy and health, but it must not claim SHT31, relay, PENGLIN, fan-motion or real Raspberry Pi acceptance until M10.7 supplies target evidence.

## D-094 — Support blueprint-style JSON placement for env commands

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** `gonken-agent env` accepts JSON output flags at the parent level and at leaf commands, including the blueprint-style `gonken-agent env status --json`.
- **Reason:** The V09 operator examples include `gonken-agent env status --json`; rejecting that form would create avoidable mismatch between implementation and operator documentation.
- **Consequence:** New env CLI tests cover both `env --json status` and `env status --json` for the status command, and later documentation should prefer the blueprint-style leaf form.


## D-095 — Make environment observability non-destructive and evidence-scoped

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Diagnostics, `doctor`, support bundles and the read-only dashboard may report environment static configuration, path/socket presence, service status, read-only daemon health and capability flags, but routine observability must not toggle the relay, scan arbitrary I2C devices, open GPIO lines, mutate policy, or imply physical acceptance.
- **Reason:** The V09 blueprint requires useful support evidence while preventing false-green hardware claims and avoiding unsafe ordinary diagnostic behavior.
- **Consequence:** Environment observability can explain disabled/unavailable/degraded state and preserve `physical_evidence=false`; production hardware proof remains M10.7 HIL work.

## D-096 — Install the environment service structurally but keep autostart disabled by default

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The V09 installer/release payload now carries `gonken-environment.service`, its tmpfiles contract and `environment_service_manager.py`, but the manager deliberately does not enable or start the service during generic installation or upgrade.
- **Reason:** The V09 blueprint requires a separate environment service boundary, while the static hardware profile and physical HIL acceptance remain unfinished. Starting a supervised hardware service by default before SHT31/libgpiod adapters and target wiring are accepted would create a false actuation/acceptance path.
- **Consequence:** Host tests can verify exact managed service files, tmpfiles, release inclusion and conflict refusal. Real systemd startup, I2C/GPIO groups, relay safety and fan behavior remain target gates.

## D-097 — Use `gonken-env` for hardware ownership and `gonken-envctl` for client access

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Target installation provisions a non-login `gonken-env` account as the future environment hardware owner and a separate `gonken-envctl` group for AF_UNIX control-socket clients; `gonken-agent` joins only the client group.
- **Reason:** Voice must be able to ask the deterministic environment daemon for authorized actions without receiving raw environment I2C/GPIO privileges. This preserves one authoritative owner of physical environment state.
- **Consequence:** Production hardware adapter work must grant device access to `gonken-env`, not to the voice account. CLI/voice actions remain client operations and cannot bypass daemon validation.

## D-098 — Fail closed when `env serve` is enabled before production hardware adapters exist

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The hidden `gonken-agent env serve` systemd entry point exits harmlessly when `[extensions.environment].enabled=false`, and returns an explicit `ENV_HARDWARE_BACKEND_NOT_IMPLEMENTED` failure if the static environment profile is enabled before production SHT31/libgpiod adapters are implemented.
- **Reason:** Running the host-fake service under systemd would make the appliance appear physically ready while no SHT31 or relay boundary has been implemented or accepted.
- **Consequence:** Checkpoint 06 can verify service installation and fail-closed behavior without creating a fake hardware daemon. Later hardware-adapter work must replace the fail-closed path with a target-tested daemon only after SHT31/relay code and HIL evidence exist.


## D-099 — Route clear environment voice commands through deterministic intents before the LLM

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The production conversation path now checks a fixed allow-listed environment intent parser before ordinary local LLM chat. Clear temperature, humidity, fan status, fan on/off, mode and explicit threshold requests become typed environment-daemon operations; ambiguous environment policy requests ask for clarification.
- **Reason:** V09 requires voice-mediated control without granting the LLM arbitrary shell, GPIO, I2C, file or tool-execution authority.
- **Consequence:** Spoken environment responses must be derived from the daemon result or daemon rejection. General conversation remains local LLM text; environment actions do not enter chat history or claim physical actuation without daemon and target evidence.

## D-100 — Add `env watch` as a repeated IPC read, not direct sensor access

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** `gonken-agent env watch` repeatedly calls the environment daemon through `EnvironmentClient.read_sensor()` and may emit human rows or newline-delimited JSON. It has a bounded `--count` option for tests and scripted runs.
- **Reason:** The blueprint requires a live watch, but the single-owner hardware boundary still forbids CLI-side I2C/GPIO access.
- **Consequence:** Watch output can report temperature, humidity, mode, fan relay-power state and `physical_evidence=false`; it must not toggle hardware or create microSD sample history by default.

## D-101 — Implement SHT31 as a lazy-import SMBus adapter with CRC validation

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The production SHT31 adapter lives under `src/gonken_agent/environment/sensors/`, imports `smbus` only when a real bus is opened, validates Sensirion CRC-8 for both temperature and humidity words, returns truthful failed/unavailable `SensorReading` values instead of silently substituting stale data, and remains testable through injected fake bus objects.
- **Reason:** The environment service must own sensor reads without making ordinary host imports require Raspberry Pi I2C packages. CRC validation and unavailable/error readings prevent stale or corrupted sensor values from being presented as current room evidence.
- **Consequence:** Host tests can verify command construction, CRC and conversion behavior, but only M10.7 target runs can prove `/dev/i2c-*`, SHT31 address, wiring, placement and repeated valid CRC readings.

## D-102 — Implement relay actuation as a libgpiod power-only adapter and keep daemon activation target-gated

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The production relay adapter lives under `src/gonken_agent/environment/actuators/`, imports libgpiod only when opened, requests one configured line as output with inactive startup value, maps active-high/active-low semantics through line settings, exposes only power-control capability and performs safe-off on close. `gonken-agent env serve` remains fail-closed for enabled profiles until supervised real-hardware daemon activation is implemented and target-tested.
- **Reason:** The purchased ELUTENG/relay/PENGLIN design can switch USB fan power only. It cannot observe blade motion or program the physical three-speed selector. Keeping daemon activation target-gated prevents host adapter code from being mistaken for physical acceptance.
- **Consequence:** Host tests now cover libgpiod request/write/release semantics with fakes and service fail-closed behavior on actuator write failure. Real Pi gpiochip mapping, relay polarity, boot/off behavior and fan cycles remain M10.7 gates.

## D-103 — Replace enabled-profile `env serve` fail-closed scaffold with a degraded daemon activation scaffold

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Once the SHT31 and libgpiod adapter modules exist, an explicitly enabled environment profile may construct `EnvironmentServiceCore` from validated static config, daemon-owned policy storage, `SHT31Sensor` and `GpiodRelayFanActuator`, then expose it through the bounded AF_UNIX server. Generic installs still keep `[extensions.environment].enabled=false`; `env serve --check` validates construction without starting a socket loop or toggling hardware; all daemon metadata keeps `physical_evidence=false` until M10.7 target acceptance.
- **Reason:** The next dependency-ready step after adapter implementation is to prove the production daemon assembly path without reverting to host fakes or pretending that adapter construction proves physical SHT31/relay behavior.
- **Consequence:** Enabled profiles can now start a structurally real daemon path that degrades truthfully when sensor or actuator operations fail. Physical readiness remains open: target I2C access, SHT31 CRC reads, Pi 5 gpiochip mapping, relay polarity, boot safe-off, fan cycles and reboot/no-login behavior must still be accepted on the actual Raspberry Pi.

## D-104 — Use a bounded daemon-owned polling loop for autonomous environment control

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** `gonken-environment.service` owns a bounded background polling loop that periodically reads the configured sensor through the daemon-owned adapter, feeds the deterministic controller, reconciles the actuator state and records degraded-state metadata. CLI and voice remain clients; they do not run their own sensor loops or control GPIO/I2C directly. Sensor exceptions are converted into structured failed/unavailable readings so AUTO/SEMI can fail closed. Actuator write errors are recorded as degraded poll results and force `ACTUATOR_ERROR_SAFE_OFF` without terminating the daemon thread.
- **Reason:** Automatic and semi-automatic behavior must not depend on a user manually invoking `sensor.read`. The polling loop belongs with the single hardware owner so physical control remains deterministic, testable and isolated from LLM output.
- **Consequence:** Host tests can now verify daemon polling, safe-off behavior and lifecycle cleanup with fakes. Physical claims remain target-gated: real SHT31 reads, relay polarity, fan cycles, boot behavior and systemd/no-login convergence must be accepted under M10.7.

## D-105 — Treat the M10.7 environment acceptance runner as private evidence collection, not acceptance authority

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Add `scripts/environment_acceptance_runner.py` to collect private M10.7 environment evidence files and include it in the release maintenance payload. The runner is non-destructive by default, requires `--allow-actuation` before issuing fan ON/OFF commands, and records `physical_acceptance_claimed=false` in every manifest and step file.
- **Reason:** M10.7 needs repeatable target evidence files, but command output alone can create false-green acceptance if it is treated as proof of SHT31 placement, relay polarity, fan blade motion or wake/audio success.
- **Consequence:** The runner can prepare a structured private evidence ledger for review. M10.7 still requires supervised physical observations, reboot/no-login evidence, wiring inspection and voice/wake evidence before any physical PASS claim.

## D-106 — Make interruption-recovery fixtures bounded by default

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Test-only interruption hooks in the Ollama and release managers now default to abrupt self-exit with shell-visible signal-style exit codes, rather than killing the parent shell. Parent termination remains available only through explicit opt-in test variables. The Ollama integration fixture lazy-starts its fake HTTP server, closes fixtures per subtest, and runs a representative bounded default interruption matrix while retaining exhaustive coverage behind `GONKEN_EXHAUSTIVE_OLLAMA_BOUNDARIES=1`.
- **Reason:** Killing the parent shell during subprocess-based integration tests can orphan Python children or stall fake HTTP teardown, causing broad CI to look hung after the intended interruption. That creates a false-red/unknown quality state unrelated to V09 environment behavior.
- **Consequence:** The default Ollama lifecycle interruption test now completes and still verifies resumability at download, extract, finalize, service-readiness, model-smoke and model-pull boundaries. Full exhaustive coverage remains available for dedicated runs. Physical Raspberry Pi acceptance remains unchanged and unclaimed.

## D-107 — Run broad host unittest suites through bounded per-module subprocesses

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The canonical `scripts/ci.sh` T1 unit and deterministic integration phases now use `scripts/bounded_unittest.py` to execute every discovered test module in a separate subprocess with per-module timeout, heartbeat output, log file and manifest.
- **Reason:** Monolithic `unittest discover` could be externally interrupted while hiding the active module, creating an ambiguous `INTERRUPTED` quality state. Per-module execution preserves the same test coverage while making slow, failed or timed-out modules identifiable and resumable.
- **Consequence:** CI failures are now more diagnosable, but no acceptance criterion is weakened. A module timeout is still a failed CI run. Physical Raspberry Pi acceptance and long release-E2E completion remain separate evidence gates.

## D-108 — Run release lifecycle E2E through bounded per-case evidence

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The canonical CI now excludes `tests.integration.test_release_lifecycle_process` from the ordinary module-granularity integration pass and runs that release lifecycle module separately with `scripts/bounded_unittest.py --granularity case`. The formerly combined release-only/default-boundary E2E method is split into named cases for build/freeze, idempotent repeat, default target-boundary refusal and low-space refusal.
- **Reason:** The release lifecycle test is intentionally heavier than ordinary deterministic integration and was previously visible only as a monolithic module when interrupted. Case-level execution preserves the same acceptance logic while making the active boundary, timeout, log and result explicit.
- **Consequence:** No release acceptance criterion is weakened. A failed or timed-out release case still fails CI, but evidence now identifies the exact install/activation boundary requiring repair. Physical Raspberry Pi acceptance remains M10.7 and cannot be inferred from host release-case success.

## D-109 — Allow canonical CI phases to run independently without weakening the full gate

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** `scripts/ci.sh` now accepts `--phase t0`, `--phase unit`, `--phase integration`, `--phase release-lifecycle` and `--phase all`, plus `--list-phases`.  With no arguments it still runs the complete canonical host sequence.
- **Reason:** After the bounded runner and release case decomposition, the remaining practical problem was not hidden test coverage but external session walls interrupting the long aggregate command.  Phase selection lets a later session collect or repeat the exact phase that remains uncertain without restarting all earlier passed work.
- **Consequence:** No test is removed and no acceptance criterion is weakened.  A failed or timed-out phase still fails that phase.  Physical Raspberry Pi acceptance remains M10.7 and cannot be inferred from any host CI phase.

## D-110 — Treat checkpoint 16 as blueprint/control expansion only

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Checkpoint 16 updates the authoritative control artifacts for the simulation/HIL extension and does not implement runtime simulation, modify environment CLI commands, alter GPIO/I2C behavior, enable the environment service, or change the shipped wake phrase.
- **Reason:** The V2 prompt explicitly requires a blueprint-expansion run first so the next implementation sessions can proceed without rediscovering architecture or improvising safety-critical details.
- **Consequence:** Simulation, `GonKen` wake, progress cues, passive watch and hardware documentation remain planned implementation work. M10.7 physical acceptance remains not-run.

## D-111 — Add simulation as independent sensor and actuator backend axes

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The next implementation will support independent `sensor_backend = sht31|simulated` and `relay_backend = libgpiod|simulated` axes rather than one global simulation switch.
- **Reason:** The user needs full simulation, simulated sensor plus real fan, real sensor plus simulated fan and full physical operation as separate evidence modes.
- **Consequence:** Config validation, daemon factories, protocol, CLI, diagnostics, support bundles, voice responses and acceptance runners must all report backend provenance and prevent simulated backends from masquerading as physical acceptance.

## D-112 — Keep simulation state daemon-owned and normally ephemeral

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Simulated temperature, humidity, sensor faults and actuator behavior belong to `gonken-environment.service`, not to the mutable policy file or an external process-owned state file. Default behavior is ephemeral simulation state with explicit reset semantics.
- **Reason:** Static hardware/safety configuration, mutable operating policy and simulation state have different authority, persistence and safety implications.
- **Consequence:** Simulation mutation uses bounded IPC operations. CLI and voice remain clients and cannot bypass controller validation.

## D-113 — Make `env watch` passive before user-test handoff

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The next implementation must change watch semantics so `gonken-agent env watch` reads daemon snapshots rather than repeatedly invoking active sensor-read/control operations.
- **Reason:** A watch command should not alter recovery counts, median samples, dwell timing, autonomous decisions or actuator writes.
- **Consequence:** A passive snapshot protocol operation and tests proving no observer effect are required before the simulation/HIL user-test package.

## D-114 — Require a true non-actuating `env serve --check` path

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** `env serve --check` is not considered hardware-neutral until tests prove it cannot open/request a gpiod line or write safe-off merely to validate configuration.
- **Reason:** Checkpoint-15 behavior can report `hardware_toggled=false` while cleanup may call safe-off on a lazily-opening actuator path. That is a false-neutral safety risk.
- **Consequence:** The next implementation must distinguish configuration validation from real resource acquisition and preserve real daemon shutdown safe-off once resources have actually been opened.

## D-115 — Replace target-gated wake adoption with mandatory default `GonKen`

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The next wake implementation will make `GonKen` the shipped/default phrase without waiting for physical wake testing, while retaining target evidence for tuning and final acceptance.
- **Reason:** The V2 product decision prioritizes recall across diverse accents. Real-Pi wake tests should tune the local detector, not decide whether the phrase may be adopted.
- **Consequence:** Changing only the default string is insufficient. The implementation must reduce transcription-induced listening gaps, support governed aliases/split tokens, add a matcher corpus, preserve `Hey GonKen` as an alias unless unsafe and update docs/tests consistently.

## D-116 — Implement post-request progress cues through one audio owner

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The next voice UX implementation will add a bounded progress scheduler after question capture using a short cue such as `Just a second.` and at most one longer-wait cue. The voice runtime remains the single audio owner.
- **Reason:** The current immediate wake acknowledgement exists, but local inference can still leave the user uncertain after the request has been captured.
- **Consequence:** Legacy filler WAVs remain excluded. Cue audio must be locally generated with Piper and governed by a manifest/cache, with timing, cancellation and no-overlap tests.

## D-117 — Route autonomous environment announcements through the voice service only

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Autonomous environment transition speech, if enabled, is produced by the voice service after observing typed environment transition events. The environment daemon never owns Piper, ALSA or PipeWire.
- **Reason:** This preserves voice as a soft dependency and prevents competing audio owners.
- **Consequence:** Announcements need sequence IDs, deduplication, queue bounds, simulation-aware wording and no-overlap arbitration with direct user answers.

## D-118 — Treat GPIO chip/line mapping as explicit target evidence

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The plan separates operator-facing BCM/header identity from runtime libgpiod chip path and line offset rather than assuming BCM23 always equals `/dev/gpiochip0` offset 23.
- **Reason:** Pi 5/RP1 GPIO character-device mapping must be verified on the actual target before relay acceptance.
- **Consequence:** Config/schema migration, diagnostics and hardware docs must expose actual chip/line evidence before any physical PASS claim.

## D-119 — Add a dedicated documentation architecture before user-test handoff

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The future user-test package must contain distinct documentation ownership for installation, hardware setup, environment control, simulation, operations, troubleshooting and acceptance/evidence export.
- **Reason:** Simulation/HIL and physical wiring are safety-sensitive and cannot remain scattered through checkpoint reports.
- **Consequence:** Documentation checks must verify paths, commands, service names, config keys, wake phrase consistency and simulation/physical separation. Markdown rendering alone is not enough.

## D-120 — Preserve M10.7 as the final physical umbrella gate while adding M10.8-M10.14 continuation milestones

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Historical M10.7 remains the real Raspberry Pi HIL/release acceptance gate. M10.8-M10.14 define the simulation/HIL/wake/documentation implementation sequence leading to a user simulation and sensor-deferred HIL release candidate.
- **Reason:** This preserves checkpoint 1-15 history while giving future sessions an ordered continuation plan.
- **Consequence:** Simulation and hybrid evidence can support user testing and partial target diagnosis, but only full physical evidence can close M10.7.

## D-121 — Implement simulation as service-owned runtime state, not policy state

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Checkpoint 17 implements simulated sensor values, simulated sensor faults, simulated actuator behavior and simulation event history as daemon-owned runtime state. It is not stored in the mutable environment policy file.
- **Reason:** Operating policy and simulation state have different authority and persistence semantics. Policy affects real and simulated control; simulation state is a test/operator harness for selected backend modes.
- **Consequence:** Simulation mutation is exposed only through bounded protocol operations and can be reset independently of fan policy.

## D-122 — Keep simulation runtime mutation explicitly opt-in

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** The configuration key `simulation_runtime_control_enabled` governs whether simulation mutation operations are accepted. Merely selecting a simulated backend does not silently authorize external mutation unless this runtime-control flag is enabled.
- **Reason:** The daemon must distinguish a configured backend from an operator/test surface that can change readings or inject faults.
- **Consequence:** CLI/operator simulation commands in later checkpoints must surface `SIMULATION_DISABLED` clearly rather than assuming mutation is always available.

## D-123 — Report simulation provenance on ordinary environment results

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Environment status, health, sensor reads, poll results and simulation operations now carry provenance fields including sensor backend, actuator backend, simulated-axis flags, evidence mode and `physical_evidence=false` where appropriate.
- **Reason:** Simulation and hybrid HIL are useful only if every result remains traceable and cannot be mistaken for physical acceptance.
- **Consequence:** Later diagnostics, support bundles, dashboard and voice responses must preserve the same provenance rather than collapsing it into a generic READY state.

## D-124 — Add passive snapshot and event protocol before changing watch semantics

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Checkpoint 17 adds `state.snapshot.get` and `events.get` protocol operations before changing the user-facing watch implementation.
- **Reason:** `env watch` must eventually become a passive observer. The daemon needs a read-only snapshot surface before CLI watch can be safely moved away from active `sensor.read` calls.
- **Consequence:** Checkpoint 18 should update CLI watch and tests to prove no extra sensor sample, recovery count or actuator reconciliation occurs merely because an operator is watching.

## D-125 — Treat `env serve --check` as non-actuating construction validation

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** `gonken-agent env serve --check` now constructs and validates the daemon path but does not call the daemon shutdown safe-off path.
- **Reason:** A check command must not open/request a relay line or write OFF merely to validate static configuration.
- **Consequence:** Real daemon lifecycle still performs safe-off on shutdown once resources have actually been acquired; the check path is deliberately narrower.

## D-126 — Defer user-facing simulation CLI to checkpoint 18

- **Status:** Accepted
- **Date:** 2026-09-15
- **Decision:** Checkpoint 17 exposes simulation operations in protocol/client/core tests but does not yet add the `gonken-agent env simulate ...` command family.
- **Reason:** The lower-level service contract must be verified before adding operator ergonomics, documentation and support-bundle commitments.
- **Consequence:** Checkpoint 18 should add the CLI layer, passive watch and diagnostics/support simulation visibility using the checkpoint-17 protocol surface.


## 2026-09-15 — Checkpoint 18 operator simulation and passive watch decisions

- **Decision:** `gonken-agent env simulate ...` is the operator-facing simulation command family.  It uses the same bounded AF_UNIX environment client as normal environment commands and exposes no raw GPIO, I2C, shell or arbitrary object-construction surface.
- **Decision:** Simulation mutation is accepted only when `simulation_runtime_control_enabled=true` and the relevant backend axis is simulated.  The daemon, not the CLI, enforces the final guardrail.
- **Decision:** `gonken-agent env watch` is a passive observer of `state.snapshot.get`.  `gonken-agent env read` remains the explicit active sensor-read command.
- **Decision:** Diagnostics, support and dashboard may expose content-free simulation provenance, snapshot state and physical-evidence flags.  They must not include raw voice content, raw audio, arbitrary files or physical-acceptance claims.
- **Remaining:** Simulation-aware voice wording, hybrid HIL blocking/refusal behavior, default `GonKen` wake, progress cues and autonomous transition announcements remain separate follow-on checkpoints.

## D-094 — Simulation-aware voice wording is mandatory

**Status:** accepted in checkpoint 19.

When daemon provenance reports a simulated sensor or actuator, voice responses must explicitly identify the simulated side. A simulated temperature must not be spoken as a physical room reading, and a simulated actuator command must not be spoken as observed relay/fan hardware. This preserves the deterministic daemon boundary while preventing simulation evidence from being mistaken for M10.7 physical acceptance.

## D-095 — Physical acceptance runner blocks simulated backend JSON

**Status:** accepted in checkpoint 19.

The M10.7 physical acceptance runner may collect useful hybrid/simulation JSON, but if the parsed payload reports `sensor_is_simulated`, `actuator_is_simulated`, a simulated backend, or a hybrid/simulation evidence mode, the step is recorded as `BLOCKED` with `blocking_code=SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED`. Exit code 0 from a daemon command is not enough to close a physical gate.

## 2026-09-15 — Checkpoint 20 wake/responsiveness/announcement decisions

### D-096 — Default packaged wake phrase is `GonKen`

**Status:** accepted in checkpoint 20.

The packaged default wake phrase is now `GonKen`. The host matcher accepts the legacy `Hey GonKen` phrase, split `Gon Ken` tokens and bounded one-edit variants of the `gonken` token to reduce software-side missed activations. This is host transcript-matching evidence only; real microphone/STT/wake false-trigger and latency acceptance remains target-gated.

### D-097 — Wake diagnostics must not imply physical acceptance

**Status:** accepted in checkpoint 20.

`gonken-agent wake status --json` reports the configured phrase, matcher version, aliases and matcher boundary with `physical_evidence=false` and `real_wake_acceptance=NOT_RUN`. It is an operator diagnostic for software configuration and matching policy, not a claim that the physical Pi wake path has passed.

### D-098 — Progress cues are bounded and local to the voice runtime

**Status:** accepted in checkpoint 20.

The voice runtime may issue at most the configured bounded post-question cues when a non-deterministic answer is still pending. Deterministic environment commands should normally skip progress cues. Cue audio is produced through the local Piper cache contract and does not use quarantined legacy filler WAVs.

### D-099 — Environment transition announcements are voice-owned

**Status:** accepted in checkpoint 20.

The environment service records controller transition events; it does not own audio. The voice runtime may read those events and announce selected automatic/semi-automatic/safe-off transitions. Announcement wording must preserve simulation provenance and the current hardware boundary: relay/fan-power state is not blade-motion evidence and there is no software speed control.

## 2026-09-15 — Checkpoint 21 documentation/evidence hardening decisions

### D-100 — Documentation command/config/link validation belongs in T0

**Status:** accepted in checkpoint 21.

V09 documentation is now treated as an executable control surface. `scripts/validate_v09_docs.py` runs in the T0 phase and checks that required user-facing docs exist, local markdown links resolve, documented `gonken-agent` and evidence-runner commands parse, every static `extensions.environment` key is documented, wake examples use the `GonKen` default, and simulation/physical acceptance boundary terms remain present.

### D-101 — Environment acceptance manifests must state their non-oracle boundary

**Status:** accepted in checkpoint 21.

The M10.7 environment acceptance runner manifest now includes `evidence_boundary`, `required_uploads`, and `manual_gate_step_ids`. The runner remains an evidence collector, not an acceptance oracle. It records `physical_acceptance_claimed=false`, preserves simulation blocking codes, and makes explicit that JSON success cannot prove blade motion or wake/audio behavior.

### D-102 — User-facing environment docs are split by operational responsibility

**Status:** accepted in checkpoint 21.

The room-environment documentation is split into `HARDWARE_SETUP.md`, `ENVIRONMENT_CONTROL.md`, `SIMULATION.md`, `TROUBLESHOOTING.md`, and `ENVIRONMENT_ACCEPTANCE_RUN.md`. This avoids overloading `OPERATIONS.md` and gives the operator separate entry points for wiring safety, daemon/policy semantics, simulation practice, fault diagnosis and private target evidence collection.


## 2026-09-15 — Checkpoint 22 user-test release-candidate decisions

### D-127 — The M10.14 READY label is a supervised-test readiness label, not physical acceptance

**Status:** accepted in checkpoint 22.

`READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL` means the package has passed the required host/software gates to be installed for the staged user campaign. It cannot close M10.7, SHT31, relay/PENGLIN/fan, blade-motion, real wake/audio or target reboot/no-login acceptance.

### D-128 — Final M10.14 readiness requires clean, exact-commit simulation evidence

**Status:** accepted in checkpoint 22.

The final readiness gate accepts only a fresh M10.14 simulation manifest bound to the exact current Git commit and a clean worktree. An explicit dirty-tree development override may produce only `DEVELOPMENT_READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL`; it cannot emit the final READY label. Unknown or stale commit identity is rejected.

### D-129 — Sensor-deferred real-actuator readiness is non-actuating until target preflight succeeds

**Status:** accepted in checkpoint 22.

Host gating validates the `sensor_backend=simulated` plus `relay_backend=libgpiod` profile through the non-actuating `env serve --check` path. It does not request/write GPIO or claim real actuation. On the Pi, the operator must first verify character-device mapping, relay wiring/polarity and the documented low-voltage power path. A mapping mismatch or wiring uncertainty blocks actuation and is returned as target evidence.

### D-130 — Full-simulation release evidence keeps every physical gate explicitly open

**Status:** accepted in checkpoint 22.

The deterministic M10.14 simulation runner exercises manual, AUTO, SEMI, stale/recovery and passive-watch behavior through the public service/CLI boundary, but its manifest always records `physical_acceptance_claimed=false`, `sht31_physical_acceptance=NOT_RUN`, `relay_fan_physical_acceptance=NOT_RUN` and `sensor_deferred_hil_physical_actuation_tested=false`.

## 2026-09-15 — Checkpoint 23 pre-target completion decisions

### D-131 — Wake standby uses bounded pipelined capture rather than synchronous capture/transcribe gaps

- **Status:** Accepted in checkpoint 23.
- **Decision:** Production wake standby continuously acquires bounded audio windows through a newest-wins capture queue while the previous window is transcribed. Only one recognition consumer owns Whisper work, stale queued windows are dropped instead of accumulating, and wake capture is stopped before active-turn speech/capture so the assistant cannot recursively trigger on its own output.
- **Reason:** Checkpoint-20 matching improvements did not by themselves satisfy the V2 requirement to remove intentional transcription-induced listening gaps.
- **Consequence:** M10.12 host software can be treated as implemented only after the checkpoint-23 concurrency regression passes. Real microphone/STT recall, false wakes and wake-to-acknowledgement latency remain target evidence.

### D-132 — PTT and privacy indicators resolve logical BCM GPIOs by unique kernel line name

- **Status:** Accepted in checkpoint 23.
- **Decision:** Production push-to-talk GPIO17, wake-monitoring GPIO22 and recording-LED GPIO27 adapters resolve their logical identities from kernel gpiochip line metadata (`GPIO17`, `GPIO22`, `GPIO27`) and fail closed if missing, ambiguous, or incompatible. They do not assume BCM number equals `/dev/gpiochip0` line offset.
- **Reason:** Pi 5/RP1 character-device layout is a target property. A hidden chip/offset assumption would create false-green host evidence and unsafe target behavior.
- **Consequence:** Host tests prove the discovery/failure semantics; actual line identity, wiring and visible indicator behavior remain target-gated.

### D-133 — Room relay uses the same fail-closed logical-BCM discovery boundary

- **Status:** Accepted in checkpoint 23.
- **Decision:** `relay_bcm=23` remains the operator-facing logical pin identity, while the libgpiod relay adapter resolves a unique kernel line named `GPIO23` at runtime and reports the actual gpiochip path/offset in status/health. Missing or ambiguous mapping blocks actuator acquisition.
- **Reason:** Checkpoint 22 still carried a `/dev/gpiochip0:23` assumption even though the blueprint required a validated discovery mechanism or an explicit target runtime identity.
- **Consequence:** The software no longer asks the operator to prove a known hard-coded shortcut. Relay polarity, earliest boot behavior, contact wiring and fan motion still require physical evidence.

### D-134 — Downloaded target checkpoints install from their exact clean local Git commit

- **Status:** Accepted in checkpoint 23.
- **Decision:** `./bootstrap.sh --local-checkpoint` is the supervised acceptance-install path for a downloaded checkpoint. It validates a clean packaged Git checkout, binds the source manifest to its exact full HEAD commit and lets immutable-release construction fetch that commit from the package's own Git object database. Ordinary production installs retain the governed remote HTTPS/ref path.
- **Reason:** A downloaded checkpoint that resolves remote `main` at install time can silently test a different revision from the archive that passed host verification.
- **Consequence:** Raspberry Pi evidence can now be bound to the exact delivered package. Normal update behavior is not silently converted into local-file update semantics.

### D-135 — Persistent interaction-content recording is outside release-core

- **Status:** Accepted in checkpoint 23.
- **Decision:** M7.3 core acceptance is content-free, bounded operational telemetry plus transient in-memory diagnostics. `privacy.interaction_logging=true` and `privacy.telemetry_content=true` continue to fail closed. Persistent interaction-content recording is a separately authorized research extension requiring its own ethics/privacy purpose, retention, access and deletion specification.
- **Reason:** Treating content persistence as an unfinished core feature would pressure the appliance to weaken an established privacy boundary merely to close a milestone.
- **Consequence:** M7.3 software may be host-verified without implementing transcript/content retention. Target evidence must still verify that journals, support bundles and telemetry remain content-minimizing in real operation.

### D-136 — Checkpoint 23 is target-campaign readiness, never physical acceptance

- **Status:** Accepted in checkpoint 23.
- **Decision:** The final pre-target checkpoint may be described as `READY_FOR_RASPBERRY_PI_TARGET_CAMPAIGN` only after the final host/control/package gates pass. This label means the exact checkpoint is ready to install and test; it does not set any target milestone to PASS.
- **Reason:** The user needs a clear point at which host implementation is complete enough to move onto the Pi, while the project must preserve the host/simulation/hybrid/physical evidence boundary.
- **Consequence:** M7.1/M7.2/M7.5, M9.1 and M10.7 may remain partial/pending or target-not-run at handoff. Target failures start the next evidence-driven repair checkpoint rather than invalidating already verified independent host work.

### D-137 — Standard-library ZIP extraction is followed by exact Git mode/content restoration

- **Status:** Accepted in checkpoint 23 package close.
- **Decision:** The Raspberry Pi runbook may use `python3 -m zipfile -e` because Python is part of the supported baseline, but it must immediately run `git reset --hard HEAD` only after archive checksum verification and before Git cleanliness/executability checks. It then requires `test -x ./bootstrap.sh`.
- **Reason:** The ZIP archive stores the correct Unix executable modes, but Python's standard-library ZIP extractor does not restore them. A fresh package extraction therefore appeared dirty and left launch scripts non-executable even though the archive itself was correct.
- **Consequence:** The included Git metadata becomes the authoritative deterministic restoration mechanism for exact committed content/modes after this extractor. Any other in-place repair remains prohibited; identity or integrity failures after restoration are STOP conditions.


## 2026-09-16 — Checkpoint 24 target-evidence repair decisions

### D-138 — Pi target venvs deliberately consume distro hardware bindings

- **Status:** Accepted in checkpoint 24.
- **Decision:** Only the `core-pi-trixie-py313` immutable application release profile uses Python venv system-site package visibility so the production interpreter can consume the root-managed Debian `python3-libgpiod` and `python3-smbus` packages. Development profiles remain isolated.
- **Reason:** Checkpoint-23 target evidence proved the prior installer could install the OS bindings and still build a service venv that could not import them.
- **Consequence:** Target release validation must treat the distro package set as part of the target runtime contract and must fail closed on missing/incompatible APIs.

### D-139 — Hardware-binding validation runs through the immutable release interpreter

- **Status:** Accepted in checkpoint 24.
- **Decision:** Release validation imports `gpiod`, the required libgpiod-v2 symbols/API surface, and `smbus.SMBus` with the actual immutable release interpreter. Target installation additionally validates the release as `gonken-env`; normal release validation covers `gonken-agent`.
- **Reason:** A system-Python import check was a false green because the production service uses the release venv.
- **Consequence:** A target release that cannot use the exact hardware bindings can no longer proceed to appliance readiness or physical environment testing.

### D-140 — Human operators receive control-socket authority, not raw hardware authority

- **Status:** Accepted in checkpoint 24.
- **Decision:** The validated non-root invoking operator is added to `gonken-envctl` only. `gpio` and `i2c` remain hardware-service privileges. A fresh login session is explicitly required before the operator CLI permission is evaluated.
- **Reason:** The checkpoint-23 operator received `ENV_UNAVAILABLE: PermissionError` even though the daemon/client design expected supervised CLI access. Granting raw device groups would violate the single-owner/least-privilege architecture.
- **Consequence:** `gonken-agent env ...` becomes usable after reconnect without creating a second GPIO/I2C owner. Direct-root installs do not invent a human operator.

### D-141 — Sensor-deferred site activation is an explicit non-actuating admin operation

- **Status:** Accepted in checkpoint 24.
- **Decision:** The release ships `environment_profile_manager.py`, which may create the exact `sensor_backend=simulated` plus `relay_backend=libgpiod` profile only when the site configuration is absent, uses atomic root-owned persistence, refuses symlinks/divergent existing configuration, and never starts services or touches hardware.
- **Reason:** Beginner target setup needed a safe deterministic alternative to ad-hoc TOML editing without making generic installation enable physical actuation.
- **Consequence:** Generic installation remains environment-disabled; supervised hardware activation remains a later explicit step.

### D-142 — Support evidence must expose the runtime boundary that failed on checkpoint 23

- **Status:** Accepted in checkpoint 24.
- **Decision:** Support bundles include active immutable release identity/profile, application-interpreter hardware-binding status, Debian binding-package versions, allow-listed health reason codes, bounded installer event records, and bounded service event-code counts. Raw journals, transcripts and arbitrary error text remain excluded.
- **Reason:** The first target support bundle did not expose enough provenance/runtime detail to diagnose the venv/system-package boundary directly and collapsed legitimate service states.
- **Consequence:** Future target failures should be diagnosable without weakening privacy/content-minimization.

### D-143 — Relay actuation remains blocked until repaired installation completion

- **Status:** Accepted in checkpoint 24.
- **Decision:** No physical GPIO23 relay ON command is permitted during this repair checkpoint. The next target campaign must first show exact-package identity, `INSTALLATION_COMPLETE`, runtime-binding PASS, a fresh `gonken-envctl` operator session, healthy environment control-socket access and unique GPIO23 mapping.
- **Reason:** Manually patching checkpoint 23 would test a hand-repaired machine rather than the installer/package that must be accepted.
- **Consequence:** Existing unloaded wiring can remain physically disconnected on COM/NO/NC while software repair is verified.


## 2026-09-16 — Checkpoint 25 comprehensive-closure decisions

### D-144 — Checkpoint 24 target dependency failure reopens the binding architecture, not the hardware evidence

- **Status:** Accepted.
- **Decision:** The checkpoint-24 `system_site_packages` target-vendoring decision is subject to redesign because real target `pip check` consumed unrelated system distributions. Existing GPIO23/relay/fan physical evidence remains valid and is not repeated merely because installation failed earlier.
- **Consequence:** M10.17 must establish a controlled hardware-binding dependency boundary and regression-test dirty system Python state.

### D-145 — Installation is modeled as a convergent dependency graph

- **Status:** Accepted.
- **Decision:** Every installer step owns explicit prerequisites, repair/create behavior, postconditions, evidence, invalidation and resumability; downstream readiness cannot substitute for missing prerequisite checks.
- **Consequence:** Dirty/partial/interrupted target states are first-class test fixtures under M10.18-M10.23.

### D-146 — Environment profile creation is governed but never an implicit actuation event

- **Status:** Accepted.
- **Decision:** One profile manager owns simulation, both hybrid combinations and full-real static configuration; writing/verifying a profile never starts services or toggles GPIO/I2C.
- **Consequence:** Physical actuation remains a separate supervised acceptance action.

### D-147 — SHT31 correctness is defined by wire semantics, not fake SMBus method calls

- **Status:** Accepted.
- **Decision:** The SHT31 production adapter must express Sensirion's actual command/read transaction without adding an unintended register byte. Fake-bus tests must validate message bytes/ordering and be supplemented by target diagnostics.
- **Consequence:** The existing `read_i2c_block_data(..., 0x00, 6)` path is a forensic target for M10.21 and may not be treated as physically ready until reviewed/corrected.

### D-148 — I2C enablement/reboot/service access are installer/onboarding dependencies

- **Status:** Accepted.
- **Decision:** Raspberry Pi I2C state, required reboot, `/dev/i2c-1`, `i2c` group/device access and `gonken-env` service-context access are verified before real-sensor activation. A reboot-required state is persisted and resumed, not treated as an arbitrary sensor failure.

### D-149 — Final environment acceptance uses staged backend parity

- **Status:** Accepted.
- **Decision:** Acceptance progresses full simulation -> simulated sensor/real actuator -> real sensor/simulated actuator -> full real, preserving truthful evidence modes. Humidity remains observational unless a separately specified policy adds humidity control.

### D-150 — Checkpoint packages are merge-ready Git repositories without embedded credentials

- **Status:** Accepted.
- **Decision:** Portable checkpoints retain `.git`, a descriptive development branch/tag and `origin=https://github.com/mukulu/gonkenlabagent.git`; `main` tracks `origin/main`. Credentials are never stored and external push is never automatic without explicit authorization.

## 2026-09-16 — Checkpoint 27 installer/profile convergence decisions

### D-151 — Target preflight is release-independent and non-actuating

- **Status:** Accepted.
- **Decision:** Required OS tools/packages, the system `gpiod` API and GPIO character-device presence are re-probed before immutable release construction. I2C device presence and the transitional SMBus binding are reported as optional at generic-install time because the environment extension is not implicitly enabled.
- **Reason:** A late appliance-readiness error must not be the first signal of a prerequisite that the installer could have established earlier; optional real-sensor readiness must not make a safe generic install impossible.
- **Consequence:** The installer now persists private prerequisite evidence and revalidates current truth on rerun without opening or actuating hardware.

### D-152 — Early installer failure evidence is owned by the installer source, not the active release

- **Status:** Accepted.
- **Decision:** When target installation fails, the source package creates a private content-free failure ZIP from allow-listed source identity, preflight records and structured installer events.
- **Reason:** A candidate can fail before activation, so the currently active release may be absent or too old to diagnose the candidate that failed.
- **Consequence:** Candidate build failures remain diagnosable without raw logs, credentials, audio, prompts or model content and without requiring successful activation.

### D-153 — Environment backend parity is expressed as four governed non-actuating profiles

- **Status:** Accepted.
- **Decision:** The profile manager supports full simulation, simulated-sensor/real-actuator, real-sensor/simulated-actuator and full-real profiles. It may transition only between exact files it can prove it previously managed; unknown administrator configuration fails closed.
- **Reason:** Simulation/HIL/full-real parity must be deterministic while configuration ownership and hardware actuation remain separate concerns.
- **Consequence:** Profile selection writes validated static configuration only; service start and physical actuation remain explicit later operations.

### D-154 — D-138 broad system-site visibility is superseded by the isolated allow-listed bridge

- **Status:** Superseded by checkpoint 26.
- **Decision:** The checkpoint-24 `system_site_packages=true` target strategy is retired. Target releases remain isolated and bridge only explicitly allow-listed distro binding import payloads with provenance/hashes.
- **Reason:** Real Pi evidence showed unrelated `types-*` distributions contaminated `pip check` under broad visibility.
- **Consequence:** D-139's immutable-interpreter validation principle remains valid, but its dependency source is the checkpoint-26 bridge rather than broad system-site exposure.

## 2026-09-16 — Checkpoint 28 runtime/sensor/voice decisions

### D-155 — Dedicated user-session audio context is an installer prerequisite, not an appliance-readiness surprise

- **Status:** Accepted.
- **Decision:** The installer verifies the generated `XDG_RUNTIME_DIR`/D-Bus environment and, when Bluetooth audio is requested, the dedicated `gonken-agent` user manager, PipeWire and WirePlumber context before appliance readiness.
- **Reason:** A running system service is not sufficient evidence that the service account can reach its intended audio session.
- **Consequence:** Missing user-session audio infrastructure fails earlier with bounded prerequisite evidence; physical capture/playback still requires the Pi campaign.

### D-156 — SHT31 production access uses the sensor's raw I2C transaction contract

- **Status:** Accepted.
- **Decision:** The production adapter sends the exact 16-bit measurement/status/reset/heater commands and performs raw fixed-length reads without adding an SMBus register byte. CRC remains mandatory.
- **Reason:** Register-oriented SMBus block APIs can alter the on-wire transaction and fake-bus tests can hide that defect.
- **Consequence:** Host tests assert byte ordering and CRC; target diagnostics must still prove a real 0x44/0x45 device and repeated reads.

### D-157 — Real backend configuration is not physical acceptance evidence

- **Status:** Accepted.
- **Decision:** `sht31 + libgpiod` daemon configuration reports `TARGET_REAL_BACKENDS_UNVERIFIED`; `TARGET_PHYSICAL` is reserved for governed supervised acceptance evidence and is never derived solely from backend names.
- **Reason:** Configuration can be correct while wiring, sensor presence, relay polarity or fan motion is wrong.
- **Consequence:** The daemon cannot create a false physical PASS simply by starting with real backend names.

### D-158 — Voice environment actions must traverse the daemon transaction boundary

- **Status:** Accepted.
- **Decision:** Deterministic environment utterances bypass the LLM but use the same bounded `EnvironmentClient` AF_UNIX protocol as the CLI; unavailable/rejected daemon operations produce truthful refusal wording.
- **Reason:** Voice must not become a second GPIO/I2C owner or invent success independently of the environment service.
- **Consequence:** Host integration tests exercise real protocol serialization/state changes; microphone/STT/TTS and physical actuation remain target evidence.

## 2026-09-16 — Checkpoint 29 lifecycle/support/package decisions

### D-159 — Support evidence is allow-listed platform truth, never a raw troubleshooting dump

- **Decision:** expose only bounded GPIO23 resolution, runtime-context booleans/status, I2C/release/binding/service provenance and allow-listed event codes. Do not export raw `gpioinfo` consumer text, journal lines, transcripts, prompts or arbitrary stdout/stderr.
- **Reason:** target diagnosis needs enough provenance to locate dependency failures without weakening the offline/privacy boundary.

### D-160 — Comprehensive target readiness depends on the reconstructed closure milestones

- **Decision:** `release_readiness.py` requires M10.16-M10.23 host-verified and lists M10.24 as an open target gate. `INSTALLATION_COMPLETE` is necessary but not sufficient for physical acceptance.
- **Reason:** otherwise an older readiness gate could become false green while the new Python/I2C/SHT31/service/lifecycle requirements are still pending.

### D-161 — Portable package Git state is merge-ready but never self-pushing

- **Decision:** the delivered repository retains full Git history, `origin=https://github.com/mukulu/gonkenlabagent.git`, local `main` tracking `origin/main`, and the descriptive development branch/checkpoint tag. Credentials are not embedded and no remote push is performed automatically.
- **Reason:** the user can inspect, switch to `main`, merge the development checkpoint and push explicitly while package production itself remains side-effect free.

### D-162 — New release contracts must permit bounded migration from journal-bound legacy releases

Checkpoint 29 exposed an upgrade-contract defect on the real Raspberry Pi: the newly built bridge-era candidate passed its own strict validation, but `activate_release` first reconciled the previously active pre-bridge release and retroactively required that old release to contain the new hardware-binding manifest. Re-running the same installer therefore could never converge.

The release state machine now distinguishes **candidate validity** from **transition-source compatibility**. A newly built or arbitrarily selected release always remains subject to the current strict release contract. A release may use the legacy transition path only when it is already bound to trusted activation state as the current/previous post-verified release, targets the distro-binding profile, has no binding manifest, and its immutable embedded release manager demonstrably predates the binding-bridge contract. That path still verifies immutable payload/ownership/record integrity and executes bounded CLI identity/status smoke as the service user. A bridge-era release with a missing or corrupt manifest is never reclassified as legacy. Rollback to a state-bound legacy previous release remains possible so update safety is not sacrificed.

This compatibility is a migration mechanism, not a waiver. The goal is to move safely away from an older valid release without applying future candidate-only policy retroactively, while keeping every new candidate fail-closed.


## 2026-09-16 — Checkpoint 31 target-install convergence decisions

### D-163 — Completed activation is not contingent on stale-release garbage collection

- **Decision:** active/previous journal releases retain their explicit runtime transition contracts; unrelated stale releases are subject only to static immutable-record checks before best-effort deletion. A stale release that is malformed or cannot be removed is retained and emits `RELEASE_PRUNE_SKIPPED` rather than failing an already completed activation.
- **Reason:** checkpoint 30 reached `ACTIVATION_COMPLETE` on the Pi and then falsely failed by applying the current hardware-binding contract to unrelated historical commit `3b25b81...`. Garbage collection must not redefine the success of the activation transaction.

### D-164 — Reboot-required I2C enablement is a planned installer pause

- **Decision:** after enabling I2C, wait a bounded interval for `/dev/i2c-1`. If it does not appear, return the governed pause code 78, record the step as `paused`, emit `INSTALLATION_PAUSED`, do not create a failure bundle, and require rerunning the same exact checkpoint after reboot.
- **Reason:** checkpoint 30 emitted a generic error/failure bundle for an expected platform transition, while the immediately collected support bundle showed `/dev/i2c-1` ready. Planned system transitions must be distinct from product defects.

### D-165 — Bluetooth installation must prove an input route before appliance readiness

- **Decision:** a requested Bluetooth headset install must expose a Bluetooth HFP/HSP capture source or exactly one deterministic direct ALSA capture fallback for the service user before the pairing step is satisfied. Zero routes fail early; ambiguous routes fail closed. `libspa-0.2-bluetooth` is an explicit installer prerequisite.
- **Reason:** target evidence showed playback/pairing can exist without a usable microphone. Deferring microphone discovery to a 180-second final readiness wait creates slow, misleading failures and unnecessary target cycles.

### D-166 — Appliance readiness is immutable-release specific

- **Decision:** the voice runtime writes the executing immutable release commit into `ready.json`; appliance manager and install summary reject a readiness record whose commit differs from `/usr/local/lib/gonken-agent/current`.
- **Reason:** upgrades must not inherit a stale success token from an older process/release. The newly active release has to restart and establish its own audio/model/wake readiness.

### D-167 — Generic installation stays non-actuating; environment policy is created safely on first supervised start

- **Decision:** generic installation does not automatically enable `sensor-deferred-relay`, `real-sensor-simulated-actuator` or `full-real`. Profile selection remains supervised. A missing environment policy file is not precreated by generic install; the environment `PolicyStore` creates the safe MANUAL/OFF policy when the environment daemon is deliberately started.
- **Reason:** installer convergence must not become actuator activation. This preserves one authoritative environment owner and fail-off semantics while avoiding a false dependency on a policy file that is intentionally runtime-owned.


## 2026-09-16 — Checkpoint 32 current-release integrity decisions

### D-168 — Normal installation/runtime is current-release only

- **Decision:** Current installation and runtime health are established from the selected/current immutable release. Previously installed releases are not executed or revalidated as prerequisites of current operation. Historical commit identity remains only for release history and explicit rollback/update bookkeeping.
- **Reason:** Applying current policy or executing historical runtime code created upgrade dead ends without improving current-release correctness.
- **Consequence:** `reconcile` treats a post-verified current pointer structurally; `activate` validates only the requested candidate; stale pruning is non-runtime; ordinary `status` validates the current release. Explicit operator rollback is the only path that intentionally promotes and therefore validates the recorded previous release.

### D-169 — Executable smoke ends before the immutable seal

- **Decision:** CLI, pip and hardware-binding smoke are completed while the candidate is still mutable. Interpreter/build caches are purged, a payload-difference manifest is written, and the digest is recorded only after executable checks. Post-seal build/activation checks are static and non-mutating.
- **Reason:** Checkpoint 31 executed Python after sealing, allowing bytecode/cache creation to make the release differ from its own recorded digest.
- **Consequence:** Reboot/rerun cannot be used as a repair for a self-mutated release. Non-current invalid releases may be rebuilt from source; an invalid active release fails closed and must be replaced by a newer checkpoint rather than rewritten in place.

### D-170 — Long speech lifecycle evidence is case-bounded

- **Decision:** The previous eight-boundary speech interruption test is decomposed into independent unittest cases and `scripts/ci.sh` exposes `speech-lifecycle` as a per-case bounded phase; ordinary integration excludes both release and speech lifecycle modules.
- **Reason:** Module-level execution could exceed an external session boundary even when each individual scenario was healthy, producing repeated apparent hangs.
- **Consequence:** Each speech lifecycle scenario has its own timeout/log/result and checkpoint work can resume from the smallest unaccounted case.

### D-171 — Runtime-derived Python caches are not authoritative immutable payload

- **Decision:** Keep strict release-integrity enforcement for authoritative tracked/runtime files, but classify only Python runtime cache paths (`__pycache__`, `.pyc`, `.pyo`) as derived transients. Suppress their creation in installer/systemd runtime contexts and permit a same-commit active release to purge/revalidate only when manifest differences are exclusively those transient paths.
- **Reason:** Checkpoint 32 reached Bluetooth on the first target run, then the same current release became `RELEASE_ACTIVE_INVALID` on both curl and local reruns because privileged post-seal Python execution could create bytecode below the sealed tree.
- **Consequence:** The integrity guard remains productive: real source/config/executable/manifest tampering still fails closed. Benign interpreter cache generation cannot permanently dead-end a valid current release.

### D-172 — Requested Bluetooth is a preference, not a core runtime dependency

- **Decision:** When `--bluetooth-audio` is requested, use the selected Bluetooth device when it is available, but do not fail installation solely because it is busy/offline if the exact service user can prove one deterministic direct capture and one deterministic direct non-HDMI playback device.
- **Reason:** The checkpoint-32 target support bundle exposed usable AIRHUG USB capture and playback while the same headset address was unavailable over Bluetooth because it was connected elsewhere.
- **Consequence:** Bluetooth remains supported and autoconnect may retry later. No-fallback and ambiguous-fallback states remain explicit failures; no audio device is guessed.

### D-173 — Raspberry Pi 5 header GPIO identity is RP1-controller scoped

- **Decision:** Production GPIO discovery continues to use kernel line names rather than BCM-as-offset assumptions. On the Pi-5-only production target, duplicate `GPIO<n>` matches are resolved only when exactly one candidate is on chip metadata labelled `pinctrl-rp1`; gpiochip numeric identity is never hard-coded.
- **Reason:** Real support evidence recorded repeated `WAKE_LED_GPIO_LINE_AMBIGUOUS` even though the target GPIO inventory showed the header lines on the RP1 controller.
- **Consequence:** GPIO17/22/23/27 can coexist with unrelated gpiochips carrying duplicate names while truly ambiguous mappings still fail closed.

### D-174 — Managed systemd template evolution is explicitly predecessor-aware

- **Decision:** Each checkpoint that changes a managed systemd template records the exact hash of the immediately supported managed predecessor. Unknown unit content remains a conflict.
- **Reason:** Adding runtime bytecode-suppression environment variables is itself a legitimate package upgrade and must not trigger the exact-conflict protection designed for administrator modifications.
- **Consequence:** Checkpoint 32 → checkpoint 33 service upgrades converge automatically without weakening ownership/conflict safeguards.

## V09 checkpoint 34 — final-convergence decisions

### D34-01 — Immutable authority excludes only standard derived Python cache artifacts
- **Decision:** Use one authoritative-payload iterator for digest, manifest, ownership and mutability validation. Exclude only a real non-symlink `__pycache__` directory and `.pyc`/`.pyo` files beneath it.
- **Reason:** Checkpoint 33 could still encounter mode/owner drift from root-created caches even after cache-aware digest handling. A single authority definition prevents the same benign derivation from failing under a different validator.
- **Must avoid:** broad `*.pyc` exclusions, symlink cache directories, arbitrary files inside cache directories, source/config/manifest changes, or in-place repair of authoritative drift.
- **Consequence:** same-commit runtime caches cannot dead-end installation, while genuine current-release tampering still fails closed.

### D34-02 — Historical releases are not normal runtime prerequisites
- **Decision:** Normal installation/runtime never executes or revalidates a previous release. Previous release content is consulted only by explicit rollback/update state transitions.
- **Reason:** The product must operate from the current release; historical compatibility belongs to release engineering, not ordinary service readiness.
- **Consequence:** `RELEASE_ACTIVE_INVALID` protects the requested current release only and is not a cross-version comparison gate.

### D34-03 — Bluetooth is a preferred transport; usable physical audio is the prerequisite
- **Decision:** When deterministic direct USB/wired input and non-HDMI output are proven, Bluetooth stack/pair/autoconnect failure degrades to bounded warnings rather than blocking installation.
- **Reason:** Target evidence already provides usable AIRHUG USB capture/playback while the preferred Bluetooth device may be busy with another host.
- **Must avoid:** guessing among multiple USB devices, treating HDMI-only output as headset fallback, or claiming Bluetooth success when fallback is direct audio.
- **Consequence:** appliance readiness depends on an actual usable audio route, not the requested transport mechanism.

### D34-04 — One shared, non-actuating Pi5 GPIO resolver and an early installer gate
- **Decision:** GPIO17/22/23/27 use a shared resolver based on line names, RP1 metadata/sysfs label, and coherent header topology; a pre-service installer step runs the same resolver without requesting any line.
- **Reason:** Checkpoint 33 reached the live service but timed out because GPIO22 resolution remained ambiguous despite host RP1-label tests.
- **Must avoid:** hard-coding gpiochip0, assuming BCM equals offset, or adding a special wake-only mapping rule.
- **Consequence:** installer and runtime share one truth and target mapping defects surface before the final 180-second readiness wait.

## 2026-09-17 — Post-checkpoint-34 reliability-first decisions

### D35-01 — Do not issue a new Pi candidate until host/target-shadow gates are complete
- **Decision:** Checkpoint 34 is no longer the next user-facing candidate boundary. The project first completes the reliability-first host/target-shadow gate recorded in `V09_POST_CKPT34_RELIABILITY_FIRST_BLUEPRINT.md`.
- **Reason:** The checkpoint history shows a repeated pattern of packaging after the newest target error disappeared while newly reachable states remained untested.
- **Must avoid:** calling an internal checkpoint final, producing a Pi candidate from a single fixed symptom, or treating host-only success as `INSTALLATION_COMPLETE`.
- **Consequence:** internal checkpoints continue, but `RELEASE_CANDIDATE` and `STABLE_FINAL_RELEASE` wording remains blocked until the specified evidence tier exists.

### D35-02 — Canonical gpiochip identity deduplicates aliases before ambiguity decisions
- **Decision:** The shared GPIO resolver records character-device/sysfs canonical identity when available and deduplicates multiple `/dev/gpiochip*` paths that are aliases of the same kernel gpiochip before line ambiguity is evaluated.
- **Reason:** The post-CKPT34 evidence reports duplicate gpiochip paths with the same RP1 identity for the project header lines. Path strings alone are not hardware identity.
- **Must avoid:** first-path-wins selection, hard-coded gpiochip numbers, deduplicating distinct character devices, or actuator line requests during discovery.
- **Consequence:** true aliases can resolve safely, while genuinely distinct plausible header controllers still fail closed for the affected feature/profile.

## 2026-09-17 — Checkpoint 36 target-shadow decisions

### D36-01 — Target manifests are content-free, non-actuating evidence
- **Decision:** Use `scripts/target_probe.py` to capture sanitized target manifests. The probe records platform, gpiochip, I2C, audio-route, Bluetooth, systemd, identity and release-state metadata, but never requests GPIO lines, toggles hardware, scans arbitrary I2C addresses, captures audio, or includes transcripts/prompts/model responses.
- **Reason:** The project needs real target topology evidence that can be replayed in host tests without converting a probe into physical acceptance.
- **Must avoid:** treating a manifest capture as fan/sensor/voice success, leaking private content, or requiring source-checkout-only tooling on the installed target.
- **Consequence:** target manifests can become permanent regression fixtures after privacy review.

### D36-02 — Target-shadow replay is a release-candidate prerequisite, not final acceptance
- **Decision:** `target_probe.py --replay` validates saved manifests against GPIO identity rules and returns failure for unresolved/ambiguous required GPIO lines. Replay PASS is required before another Pi candidate but remains below real hardware acceptance.
- **Reason:** Checkpoint history shows that host mocks were too clean; replaying real target topology closes that gap without claiming physical relay/sensor/voice behavior.
- **Must avoid:** relabelling replay PASS as physical PASS or weakening fail-closed behavior for distinct duplicate header controllers.
- **Consequence:** the checkpoint-34 duplicate RP1 alias fixture is now a permanent host regression, and future Pi evidence should add more fixtures rather than replacing it.

## 2026-09-17 — Checkpoint 37 release-readiness decisions

### D37-01 — Release readiness must replay target-shadow fixtures
- **Decision:** `scripts/release_readiness.py` reports readiness only after the required target-shadow fixtures replay with their expected status, GPIO identity code, exit code and `physical_acceptance_claimed=false` boundary.
- **Reason:** A milestone ledger alone can drift from executable replay evidence. The release gate needs to exercise the same manifest path that future sanitized real-target fixtures will use.
- **Must avoid:** allowing a missing fixture, malformed JSON, wrong exit code, wrong identity code or physical-acceptance claim to pass readiness.
- **Consequence:** target-shadow replay failure blocks `READY_FOR_HOST_TARGET_SHADOW_GATE` and keeps the package below any Raspberry Pi candidate label.

### D37-02 — `READY_FOR_HOST_TARGET_SHADOW_GATE` is internal reliability status
- **Decision:** The readiness label is renamed away from target acceptance language. It means the current host/software and required target-shadow replay checks passed for this internal checkpoint.
- **Reason:** The previous `READY_FOR_TARGET_ACCEPTANCE` wording was too easy to confuse with physical Raspberry Pi acceptance or permission to ship a user-facing candidate.
- **Must avoid:** using this status as `RELEASE_CANDIDATE`, `STABLE_FINAL_RELEASE`, `INSTALLATION_COMPLETE` or M10.24 PASS evidence.
- **Consequence:** the next action remains adding sanitized real-target manifests, broadening target-shadow coverage and qualifying an exact archive before any Pi candidate can be produced.

## 2026-09-17 — Checkpoint 38 target-shadow capability decisions

### D38-01 — Expanded replay checks are explicit fixture contracts
- **Decision:** `target_probe.py --replay` supports opt-in `target_shadow_requirements` for privacy, GPIO identity, duplex audio, service identity and release state.
- **Reason:** Historical fixtures must retain their original evidentiary meaning, while new fixtures need stronger replay gates for the failure classes that surfaced after checkpoint 31.
- **Must avoid:** silently applying new strict checks to old evidence, or letting old narrow evidence satisfy a future full-capability gate.
- **Consequence:** readiness now requires a mixed fixture set: legacy GPIO fixtures plus explicit PASS/fail-closed capability fixtures.

### D38-02 — Audio fallback is capability evidence, not transport success
- **Decision:** A target-shadow audio PASS requires one selected capture route and one selected non-HDMI playback route with no ambiguity. A direct USB/wired fallback may satisfy audio capability while Bluetooth remains unavailable.
- **Reason:** Previous target runs showed Bluetooth preference could block progress even when AIRHUG USB capture/playback was available.
- **Must avoid:** treating HDMI playback as headset fallback, guessing among ambiguous capture/playback routes, or claiming Bluetooth success from direct-audio fallback.
- **Consequence:** ambiguous audio fixtures fail closed and future real-target manifests must distinguish preferred transport from usable audio capability.

### D38-03 — Service identity and release state can block replay readiness
- **Decision:** Required service identity fixtures must prove service users and group memberships; required release-state fixtures must reject dirty installer state, paused/invalid current state and unsafe current paths.
- **Reason:** Earlier failures came from wrong execution identities, partial installer states, stale release coupling and current-release invalidation after runtime activity.
- **Must avoid:** accepting root/operator success as service-user success, accepting stale/paused installer state as complete, or treating invalid current-release state as candidate-ready.
- **Consequence:** target-shadow replay can now block readiness before another target cycle spends time on known downstream failure classes.

## 2026-09-17 — Checkpoint 39 exact-archive qualification decisions

### D39-01 — Archive qualification is a first-class release gate
- **Decision:** Add `scripts/archive_qualifier.py` as the repeatable gate for delivered checkpoint zip archives. It verifies safe archive structure, no Python cache artifacts, preserved executable permissions, clean extracted Git state, expected commit/tag, `git fsck --strict`, milestone synchronization, release readiness and T0.
- **Reason:** Manual package verification is necessary but too easy to perform inconsistently. The project needs a deterministic check that evaluates the delivered archive, not only the source worktree.
- **Must avoid:** qualifying an archive that differs from the tested tag, contains runtime cache artifacts, loses executable permissions, has unsafe paths/symlinks, or relies on a dirty extracted state.
- **Consequence:** future archive handoffs can attach a machine-readable qualification report, while still remaining below physical Raspberry Pi acceptance.

### D39-02 — Archive qualification is not a Raspberry Pi candidate label
- **Decision:** The qualifier reports `physical_acceptance_claimed=false` and `raspberry_pi_candidate=false`; passing it does not authorize integrated hardware claims.
- **Reason:** Exact archive integrity is a prerequisite for a reliable target campaign, but it does not exercise target installation, systemd, audio, GPIO actuation, SHT31 or voice behavior.
- **Must avoid:** converting package cleanliness into `INSTALLATION_COMPLETE`, M10.24 PASS, `RELEASE_CANDIDATE` or `STABLE_FINAL_RELEASE`.
- **Consequence:** the next remaining work is still host/target-shadow release-candidate completion, sanitized real-target manifests and the eventual real Pi M10.24 campaign.

## 2026-09-17 — Checkpoint 40 I2C/environment target-shadow decisions

### D40-01 — SHT31 readiness is replay-gated without live probe side effects
- **Decision:** `target_probe.py --replay` supports an opt-in `i2c_sht31` requirement that validates `/dev/i2c-1`, supported SHT31 address evidence, heater-off status and planned `I2C_REBOOT_REQUIRED` pause handling from sanitized manifests.
- **Reason:** A future target cycle can waste time if I2C reboot, absent sensor or ambiguous sensor state is discovered only after packaging. Replay fixtures can preserve those classes without scanning a live bus on the host.
- **Must avoid:** making the live manifest collector probe SHT31 addresses, treating a replayed diagnostic summary as physical acceptance, or accepting unsupported SHT31 addresses.
- **Consequence:** readiness now fails closed for absent/unresolved SHT31 and planned I2C reboot states while still preserving the non-actuating manifest boundary.

### D40-02 — Environment profile replay binds profile names to required evidence
- **Decision:** `target_probe.py --replay` supports an opt-in `environment_profile` requirement for the four governed profiles. Simulation profiles can pass without hardware readiness; real-sensor profiles require SHT31 replay readiness; libgpiod relay profiles require GPIO23 identity evidence; `full-real` requires simulation runtime control disabled.
- **Reason:** Static profile drift can create false greens, especially when a profile name implies physical backends that the manifest does not actually support.
- **Must avoid:** inferring relay or sensor readiness from a profile name alone, or making simulated profiles depend on unavailable physical devices.
- **Consequence:** target-shadow replay can now distinguish safe simulation, real-sensor deferral and full-real prerequisites before any future candidate is offered to the Pi.

## 2026-09-17 — Checkpoint 41 lifecycle/runtime target-shadow decisions

### D41-01 — Readiness gates should block only evidence-invalidating or convergence-breaking states
- **Decision:** Expand target-shadow replay to lifecycle/runtime/resource/model states, but classify noncurrent corrupt history as non-blocking when the current release is exact, install completion is current, temp artifacts are absent and rollback-selected state is not implicated.
- **Reason:** The project needs a usable final package, not an indefinitely expanding checklist. Gates must prevent known false greens and target dead ends without blocking delivery for historical noise that normal runtime does not consume.
- **Must avoid:** letting stale historical releases invalidate a clean current release, or conversely allowing current-release drift, partial install state or wrong-release support evidence to pass.
- **Consequence:** delivery-blocking semantics are now tied to the current operating release and explicit rollback/update roles.

### D41-02 — Runtime, model and operator states are target-shadow prerequisites
- **Decision:** Required replay fixtures now cover old managed systemd templates, restart failures, missing operator `gonken-envctl` membership, low resource headroom and interrupted Ollama model finalization.
- **Reason:** These states can make a package appear installed while services, model smoke or operator control remain unusable.
- **Must avoid:** treating a successful host archive as enough when target service restart, model record, disk headroom or operator control evidence is unsafe.
- **Consequence:** the internal gate becomes stricter where failure is operationally meaningful, while still remaining below physical Raspberry Pi acceptance.

## 2026-09-17 — Checkpoint 42 single-ZIP target evidence decisions

### D42-01 — Host repair cycles depend on one complete target ZIP, not live device access
- **Decision:** The supported target handoff unit is now one comprehensive support or installer-failure ZIP containing sanitized target manifest, platform/resource inventory, installer provenance, bounded event summaries and evidence-index metadata.
- **Reason:** This platform will not have direct access to the physical Raspberry Pi. Requiring separate status reports or ad hoc copied terminal output has repeatedly left decisive hardware/runtime facts outside the package used for repair.
- **Must avoid:** blocking host-side package improvement merely because live hardware is unavailable here, or accepting an incomplete failure ZIP that omits board, GPIO/I2C/audio/service/resource context.
- **Consequence:** future target runs should upload the single generated ZIP first; package repair work can then replay and inspect the contained evidence without asking for a second bundle unless a human physical observation is genuinely missing.

### D42-02 — Completeness does not weaken the privacy or physical-acceptance boundary
- **Decision:** Expanded ZIP contents remain content-free and allow-listed: no raw audio, transcripts, prompts, model responses, credentials, Wi-Fi passphrases, source URLs, Bluetooth selectors or arbitrary raw journal text.
- **Reason:** The project needs richer machine-readable device evidence, not broader copying of private user content or noisy logs.
- **Must avoid:** treating ZIP completeness as fan-motion, acoustic-quality, SHT31-placement or wake-recognition proof.
- **Consequence:** a complete ZIP can drive development and troubleshooting, while physical observations remain target-collected evidence rather than host-inferred claims.

## 2026-09-17 — Checkpoint 43 semantic-convergence decisions

### D43-01 — Service liveness is not appliance readiness

- **Decision:** Keep the existing systemd `Type=exec` service architecture for this checkpoint, but make appliance readiness a freshness-bound semantic state tied to current release commit, boot ID, service PID and observation time. The state carries a causal component/reason and recoverability classification. Clear stale readiness records before each service start.
- **Rationale:** The target run proved that `systemctl` could report the service active while the voice appliance remained `STARTING`. A `Type=notify` migration would add a second change axis; the current defect can be closed more narrowly by strengthening the existing readiness protocol.
- **Consequence:** Installer status may report a specific dependency and may fail early for known non-recoverable conditions. A prior READY file cannot satisfy a restarted/rebooted/new-release process.

### D43-02 — PipeWire capture owns WAV construction above raw PCM

- **Decision:** Capture bounded PipeWire/Pulse audio as raw S16LE mono PCM and write the canonical WAV container in GonKen code before validation. Preserve ALSA and transport fallback behavior.
- **Rationale:** The current target failure was `pipewire-usb:AUDIO_CAPTURE_INVALID`; the previous path relied on an externally encoded WAV remaining valid when the recorder was interrupted at a bounded duration. Application-owned container construction removes that finalization ambiguity without hard-coding target hardware.
- **Consequence:** Capture failures are classified into permission, server-unavailable, device-unavailable, device-busy, WAV-invalid and generic backend reason codes. Real Pi evidence is still required to establish that the target microphone path is repaired.

### D43-03 — Exact service identity is the audio evidence boundary

- **Decision:** Support may collect metadata-only audio-server/source/sink evidence only when it is actually executing as `gonken-agent` or can use root to enter that identity. A different non-root caller is reported `SERVICE_IDENTITY_REQUIRED` rather than mislabeled.
- **Rationale:** The checkpoint-42 support artifacts proved runtime socket existence, while separate external evidence showed the interactive user could see AIRHUG. Those facts did not prove service-account capture.
- **Consequence:** Interactive desktop/user success cannot close the service audio gate. Stable Bluetooth-like identifiers in metadata are normalized when they are not needed for diagnosis.

### D43-04 — One canonical evidence engine owns common ZIP semantics

- **Decision:** `src/gonken_agent/evidence.py` owns the v2 index, member hashing, safe ZIP publication, output resolution, privacy boundary and sudo-caller ownership return. Normal support uses it directly; installer failure adds only namespaced installer-specific payloads and merges canonical common support payloads where available.
- **Rationale:** Checkpoint 42 still produced separate partial schemas and forced the operator to run a second collection after failure.
- **Consequence:** An ordinary failed install should emit one final combined ZIP in an operator-accessible location. `collect-support.sh` remains the successful-install support route and need not be rerun after ordinary installer failure.

### D43-05 — Current causal failure and historical failure history are separate evidence

- **Decision:** The current readiness/installer event is the causal failure record. Bounded historical service-code counts remain useful chronology but are not promoted to the present cause merely because they occur in the same journal/support artifact.
- **Rationale:** The 2026-09-17 readiness timeout contained fresh `AUDIO_CAPTURE_FAILED` plus earlier `WAKE_LED_GPIO_LINE_AMBIGUOUS` lines from a different process/attempt.
- **Consequence:** Combined evidence keeps both layers but downstream diagnosis starts from the freshness-bound current state.

### D43-06 — Checker performance is a reliability property

- **Decision:** Required target-shadow fixtures are replayed in-process after loading the probe implementation once; fixture timing is recorded. CLI replay remains independently tested.
- **Rationale:** A subprocess-per-fixture readiness implementation grew enough to trigger test-timeout false reds. The replay matrix is deterministic and does not need process startup overhead for every case.
- **Consequence:** Release readiness preserves all target-shadow cases, including the new exact-service audio-runtime failure fixture, while staying within a bounded host gate budget.

### D43-07 — Explicit evidence output directories must pre-exist

- **Decision:** `--output-dir` is accepted only for an existing real directory. The evidence tools never create an explicit operator-selected directory while running under `sudo`; only the documented root fallback directory may be created by the root process.
- **Rationale:** A verification review found that creating a new explicit directory as root could strand an otherwise correctly chowned ZIP under a root-owned `0700` parent. Requiring the operator to create the directory first preserves ownership intent and prevents a false "operator-accessible" result.
- **Consequence:** `/tmp` and existing home/project directories work directly; a custom directory must be created by the operator before collection. Regression tests assert that missing explicit directories are rejected and remain absent.

### D43-08 — Readiness identity includes release profile and Linux process start identity

- **Decision:** Voice READY/WAITING records bind not only release commit, boot ID and PID, but also the immutable release dependency profile and `/proc/<pid>/stat` process-start ticks.
- **Rationale:** PID existence alone does not distinguish a long-stale readiness record from PID reuse. A release commit also does not by itself encode the dependency profile under which that release is expected to operate.
- **Consequence:** `appliance_manager.py` rejects profile drift and PID-reuse/stale-process fixtures. Physical readiness still requires the exact Raspberry Pi campaign.

### D43-09 — Target runbooks must not hard-code a site-specific Bluetooth identity

- **Decision:** Checkpoint-43 operator documentation uses an explicit operator-supplied Bluetooth selector placeholder rather than embedding the device address observed on the current lab target.
- **Rationale:** The repair must generalize by capability and governed configuration, not encode the current hardware instance as universal product identity.
- **Consequence:** The exact target may reuse its configured selector during its own campaign, while the distributed package remains portable to another supported audio device/target.

## 2026-09-18 — Checkpoint 44 V04 foundation decisions

### D44-01 — Immutable package location, not resolved venv interpreter, owns runtime release identity
- **Decision:** Semantic readiness derives release identity from the installed `gonken_agent` package anchor. A venv Python symlink that resolves to `/usr/bin/python*` cannot downgrade an immutable target runtime to `development`.
- **Reason:** Fresh Checkpoint-43 target evidence showed `VOICE_RUNTIME_READY` under the correct immutable process but readiness recorded `development/development`, producing a false installer timeout.

### D44-02 — Current component state is independent from historical event counts
- **Decision:** Historical/recovered errors may be retained as provenance but do not override a fresh READY state bound to the current boot/process/release/profile.
- **Consequence:** Readiness checks are level-triggered from current state rather than waiting for a new connection/event merely because the checker started later.

### D44-03 — Environment commissioning is an explicit bootstrap/source-record choice
- **Decision:** `--environment-profile` defaults to `none`; the canonical profile names are `full-simulation`, `real-sensor-simulated-actuator`, `sensor-deferred-relay`, and `full-real`. `--sensor-address` is limited to 0x44/0x45.
- **Reason:** “Installed” and “commissioned/expected to run” were previously conflated.

### D44-04 — Real-sensor/simulated-actuator is the next target default for environment convergence testing
- **Decision:** The next Pi campaign should select `real-sensor-simulated-actuator`, proving SHT31, daemon, IPC, configuration and permissions before the package is allowed to control the real relay.
- **Consequence:** Generic installation of a real-relay profile pauses with exit 78 for supervised commissioning.

### D44-05 — Diagnostic checks do not create daemon-owned state
- **Decision:** `env serve --check` validates a prospective default policy in memory when policy state is absent. Persistent default initialization is reserved for the real daemon/service identity or an explicit governed initialization path.
- **Reason:** The Checkpoint-43 sudo diagnostic path could create root-owned `policy.json` and subsequently prevent `gonken-env` from starting.

### D44-06 — Safe permission drift is reconciled; ambiguous administrator state fails closed
- **Decision:** Known environment state/policy metadata is normalized only after path/type/JSON safety checks. The exact known temporary Checkpoint-43 test drop-in may be removed automatically; other drop-ins remain untouched and block commissioning.
- **Reason:** Reliability requires repairing known package-owned drift without silently overwriting administrator intent.

### D44-07 — systemd active is not environment semantic readiness
- **Decision:** Safe commissioned profiles must pass daemon-owned `env health` semantics and exact backend checks before downstream model provisioning.
- **Consequence:** A live but sensor-unready environment fails early and specifically rather than surfacing after expensive later steps.

### D44-08 — Checkpoint 44 reports incomplete V04 tool integration explicitly
- **Decision:** Installation output independently reports subsystem states. The LLM/environment tool broker is `NOT_COMMISSIONED` in this checkpoint rather than being implied READY by successful voice or Ollama operation.
- **Consequence:** Checkpoint 44 is a foundation package, not completion of V04 multi-model/tool integration or physical acceptance.

### D44-09 — Environment ownership is a postcondition, not merely a repair action
- **Decision:** Managed environment reconciliation applies service/control ownership before the final governed mode and `commissioned-status` verifies owner, group, and mode for state, cache, runtime and policy paths.
- **Reason:** Checkpoint-43 target recovery proved that a root-owned `policy.json` can block the daemon even when content and mode look otherwise valid. Verification also identified a false-green path where reconciliation changed ownership but the postcondition checked only modes.
- **Consequence:** A later ownership drift cannot satisfy the installer step merely because the service is currently alive, and the setgid runtime-directory mode is re-applied after ownership changes.


## Checkpoint 45 V04 multi-model/tool convergence decisions

### D45-01 — Three admitted small models, one normally loaded
- **Decision:** Govern exactly `qwen3:0.6b`, `lfm2.5-thinking:1.2b`, and `qwen3.5:0.8b`; first commissioning selects `qwen3:0.6b`, while an admitted operator selection persists across installer reruns.
- **Reason:** The Checkpoint-44 Pi still used the 1.9 GB legacy 2B model and interaction remained slow.
- **Boundary:** Host tests establish lifecycle logic only; the exact Pi must still prove runtime compatibility and performance.

### D45-02 — The model proposes typed tools; the broker owns authority
- **Decision:** Ollama may propose only a fixed typed schema. The broker validates schema and explicit user mutation authorization and is the only layer allowed to call environment IPC.
- **Consequence:** No model output can directly run shell/systemctl, access raw GPIO/I2C, files or the network.

### D45-03 — Deterministic fast paths remain preferred
- **Decision:** Local date/time and common environment/fan intents bypass the LLM. Typed model tools are a semantic fallback, not the default for simple deterministic operations.
- **Reason:** This reduces latency and the action surface while retaining flexible paraphrase handling.

### D45-04 — Real-sensor/simulated-actuator remains the next package default
- **Decision:** The next Pi campaign continues with the real SHT31 and simulated room-fan actuator. Natural-language fan mutation is therefore safe to test without touching GPIO23.
- **Consequence:** Real room-fan actuation remains WP-45C and cannot be inferred from simulated fan state.

### D45-05 — Diagnostic probe context is first-class evidence
- **Decision:** A direct operator-process audio probe that fails while the service has current semantic READY remains DEGRADED diagnostic evidence but does not overwrite service-runtime truth.
- **Reason:** The Checkpoint-44 target produced exactly this state.

### D45-06 — Evidence precedence is current state, same-boot history, then install history
- **Decision:** Support evidence binds the current boot/release/readiness and latest install run ID; repeated journal reason codes are bounded aggregates without raw content.
- **Consequence:** Historical recovered failures remain visible but cannot masquerade as the current cause.
