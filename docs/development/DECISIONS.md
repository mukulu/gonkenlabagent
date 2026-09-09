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
- **Consequence:** `--speech-only` is a tested milestone return point. Normal
  target bootstrap now stops at `M3_6_UNAVAILABLE`; this is still not `READY`.
