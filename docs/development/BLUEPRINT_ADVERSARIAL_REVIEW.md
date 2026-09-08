# GonKenLab Agent Blueprint Adversarial Review

**Review ID:** M1B

**Date:** 2026-09-08 UTC

**Reviewed draft:** `MASTER_BLUEPRINT.md` revision 1.0-draft at `checkpoint/blueprint-draft`

**Repository baseline:** `6682360786135136abeb0bd2a17a9d45c6f291e7`

**Review outcome:** accepted with mandatory revisions incorporated into blueprint revision 1.1-reviewed

**Implementation boundary:** this review authorizes M2.1 only; it does not establish Raspberry Pi runtime readiness

## 1. Review purpose and method

This review attacked the draft as an implementation contract, not as prose. It checked the 18 questions in the draft against:

- the complete repository and audit evidence;
- the supplied SOPHIA-Lab feasibility/build blueprint;
- current Raspberry Pi OS and Debian platform documentation;
- current Ollama installation, API, release, and local-only behavior;
- systemd service, managed-directory, device, and watchdog semantics;
- FHS placement rules;
- openWakeWord training/evaluation guidance and current maintenance signals;
- current Whisper and Piper release/package evidence;
- power-loss, compromise, privacy, licensing, and scope-failure scenarios.

The test was not whether a design could be implemented in principle. The test was whether another session could implement it without silently inventing scope, weakening a privacy claim, or promising rollback that Linux package managers cannot provide.

## 2. Executive judgment

The draft had a sound overall direction but combined a viable first release with three materially riskier extensions: continuous wake monitoring, LAN dashboard exposure, and voice-authorized host power. That combination obscured the project's strongest contribution: a bounded, source-grounded, observable, push-to-talk edge assistant.

The reviewed architecture therefore establishes two boundaries:

1. **Core release:** repeatable Trixie/Python 3.13 installation; USB audio; physical push-to-talk and recording LED; local Whisper, Ollama/Qwen, Piper, lexical retrieval, provenance, content-free telemetry, loopback dashboard, systemd startup, diagnostics, update, rollback, and uninstall.
2. **Governed extensions:** “Hey Gonken” wake word, direct LAN dashboard, voice power control, and Bluetooth audio. These remain repository requirements/experiments, but none may delay or weaken the core release.

No Critical M1B review issue remains unresolved. High-risk items are either resolved by a concrete blueprint change or assigned a blocking gate before the affected extension can be enabled.

## 3. Finding disposition

| ID | Severity | Draft question | Disposition | Binding change |
|---|---|---|---|---|
| AR-01 | High | Is Debian 13/Python 3.13 an incorrect or too-narrow target? | Confirmed with qualification | Trixie/AArch64/Python 3.13 is the single core target; the installer records exact image/package versions and fails safely elsewhere. No exact patch version is assumed. |
| AR-02 | High | Is `/opt` + `/etc/opt` + `/var/opt` unnecessarily complex? | Change accepted | Use local-software and service conventions: `/usr/local/lib/gonken-agent`, `/etc/gonken-agent`, `/var/lib/gonken-agent`, `/srv/gonken-agent/corpus`, `/var/cache/gonken-agent`, and `/run/gonken-agent`. |
| AR-03 | Medium | Are release-local virtual environments proportionate on 64GB microSD? | Retained with limits | Keep active plus one previous release only; measure actual release size; require storage headroom before staging; delete failed staging only after evidence capture. |
| AR-04 | High | Can Ollama binaries/models be pinned without brittle installation? | Retained and hardened | Download a named stable ARM64 release asset, verify the upstream-published SHA-256, and record version. Record source model tag plus local digest; a changed digest requires explicit update and model revalidation. Do not pipe an unverified installer into a privileged shell. |
| AR-05 | High | Is openWakeWord 0.6.0 maintainable enough to be a release dependency? | Change accepted | Remove openWakeWord from the core dependency set. Run a backend/licensing/Python 3.13/AArch64 spike before choosing it for extension X1; preserve a backend-neutral wake adapter. |
| AR-06 | High | Are wake-word data and thresholds attainable and defensible? | Change accepted | Treat current FAR/FRR numbers as research targets, not core release criteria. X1 requires a frozen evaluation protocol, lawful provenance, at least 200 held-out intended activations across at least 10 speakers, at least 24 hours of representative non-trigger audio, threshold sweep, and confidence intervals. |
| AR-07 | High | Does continuous wake monitoring need distinct privacy communication? | Change accepted | If X1 is enabled, a second physical indicator distinct from the red recording LED must show continuous wake monitoring; dashboard/documentation alone is insufficient. |
| AR-08 | Critical | Is voice-only power confirmation safe under STT error or service compromise? | Rejected | Core runtime receives no power privilege. X2 requires an independent physical confirmation and a narrowly reviewed root helper; two voice phrases do not mitigate a compromised service account. |
| AR-09 | High | Can service hardening coexist with ALSA/GPIO access? | Change accepted | Apply hardening incrementally. Do not use `PrivateDevices=true`; resolve target audio/GPIO groups or udev rules; allow only required writable paths; run unit verification, security scoring, and physical access tests after each hardening increment. |
| AR-10 | Medium | Is `Type=notify`/watchdog worth its complexity now? | Rejected for core | Use `Type=exec` plus internal health, bounded restart policy, and explicit doctor checks. Add notification/watchdog only if measured hang behavior or a dependent unit creates a demonstrated need. |
| AR-11 | High | Is loopback-only dashboard usable, and what protects LAN mode? | Resolved by scope | Core configuration rejects non-loopback dashboard binds. Secure SSH forwarding is the supported laptop path. X3 must add authentication and a transport/threat-model decision before phone/direct-LAN access. |
| AR-12 | High | Can offline behavior be tested without confusing LAN with internet? | Change accepted | Core permits Unix sockets and loopback only. Tests run with loopback available and external routes/DNS unavailable, instrument connection attempts, and distinguish provisioning from runtime. LAN is tested only under X3. |
| AR-13 | Critical | Are whole-installer transaction/rollback claims truthful around APT and model pulls? | Corrected | System package provisioning is convergent and repairable, not transactional. Atomic rollback applies only to project release activation/config/index writes. APT/dpkg and Ollama have explicit detection, repair, and rerun behavior. |
| AR-14 | Critical | What happens on power loss around writes, switch, restart, and migration? | Resolved by protocol | Use same-filesystem temporary writes, validation, file and parent-directory sync where durability matters, atomic rename/symlink replacement, and a root-owned phase journal. A reconciliation step resolves incomplete activation before the app service starts. |
| AR-15 | High | Can reinstall preserve data while rejecting incompatible schema? | Retained and hardened | Never migrate site data in place. Copy, migrate, validate, and atomically replace while retaining backup. A newer/unknown schema blocks activation without modifying data. Keep-data is the uninstall default. |
| AR-16 | High | Is BM25 sufficient, and how is answer quality tested? | Evidence-gated baseline | Retain deterministic BM25 first. Freeze a corpus-specific set with at least 40 answerable and 20 unanswerable questions; initially target hit@3 ≥85%, unsupported-answer abstention ≥90%, and valid-source-ID coverage 100%. Escalate retrieval only if measured failure warrants it. |
| AR-17 | Critical | Is the combined scope feasible? | Reduced | Core release excludes X1 wake, X2 voice power, X3 LAN dashboard, and X4 Bluetooth. First deferral is wake word, then LAN access, then voice power; none is allowed to compromise core completion. |
| AR-18 | High | Are audit findings mapped to tests rather than prose? | Change accepted | Section 15 now assigns a planned verification ID to every Critical/High audit finding and identifies whether it blocks core or an extension. |

## 4. Additional review findings

### AR-19 — Licensing is an implementation precondition, not end-stage paperwork

**Severity:** High

The repository lacks an adequate project/third-party licensing account, while current Piper is GPL-3.0-or-later, voice licenses vary, Qwen is separately licensed, and openWakeWord model/training resources have distinct terms. Choosing whether Piper is imported into the process or invoked as a separate program may affect distribution analysis.

**Disposition:** M2.1 must add a source/assets/dependencies inventory and a maintainer-approved project-license decision before a redistributable package is claimed. This is a release blocker, but not a reason to guess a license during M1B.

### AR-20 — Qwen 3.5 2B is a candidate, not yet a Pi acceptance result

**Severity:** High

The official Ollama entry confirms the selected 1.9GB Q4_K_M artifact, but no evidence in this repository proves acceptable Pi 5 4GB latency, memory, thermal behavior, or answer quality. The model remains the first candidate because the user selected it after comparison; M3 must benchmark it and record any fallback decision rather than silently changing models.

### AR-21 — Provenance display and content retention must be separated

**Severity:** Medium

The feasibility source expects a useful browser view of transcript, answer, and retrieved passages; the draft correctly prevents such content from entering default telemetry. These are not contradictory if the dashboard can show the current/last interaction from process memory without persisting it.

**Disposition:** Default persistent telemetry remains content-free. The loopback dashboard may display transient content and safely escaped excerpts when explicitly enabled; restart clears them. Persistent interaction records remain an opt-in research mode with retention/deletion controls.

### AR-22 — Filenames and health details can themselves disclose information

**Severity:** Medium

Absolute paths, usernames, hostnames, corpus titles, and support bundles can reveal sensitive institutional context even when transcripts are excluded.

**Disposition:** Runtime provenance uses corpus-relative stable IDs, never absolute paths. Support-bundle and dashboard tests must cover path, hostname, token, environment, and configuration redaction.

## 5. Power-loss and interrupted-install contract

| Interruption point | State after interruption | Required next behavior |
|---|---|---|
| APT metadata/package download | APT/dpkg may be incomplete | Detect locks/processes; never kill package managers blindly; use status probes and documented `dpkg --configure -a`/APT repair only when indicated; rerun the step. |
| Python wheel download/install | Candidate venv may be incomplete | Candidate remains inactive; rebuild or resume from locked cache; active release is untouched. |
| Artifact download | `.partial` or checksum-mismatched file | Never treat as installed; resume only where supported and verified, otherwise quarantine/re-download. |
| Ollama model pull | Ollama content store may contain partial blobs | Query API/CLI postcondition; repeat pull; accept only matching name/digest plus inference smoke. |
| Config migration | Old config plus staged copy/backup | Validate staged copy before replacement; old file remains authoritative after failure; unknown schema blocks. |
| Index build | Old index plus incomplete staged index | Ignore/remove staged index; rebuild from corpus; activate only a validated index with matching hashes. |
| Release build | Incomplete candidate directory | `current` remains unchanged; candidate is not service-writable and may be rebuilt safely. |
| Atomic `current` switch | Pointer names either complete old or complete new release | Root-owned journal identifies candidate/previous and phase; never infer completion from the pointer alone. |
| Service restart/post-check | New release may be selected but not post-verified | Same invocation rolls back on failed health. After host power loss, pre-start reconciliation validates the pending candidate or restores the previous validated pointer before app start. |
| Journal/state write | Missing/stale/corrupt advisory state | Actual signed/root-owned files, checksums, pointers, and probes prevail; unsafe ambiguity becomes a visible failed-maintenance state. |

Whole-device power-loss tolerance does not mean APT is rolled back or that microSD corruption is impossible. The contract is: no partial project artifact is accepted, the prior application release is preserved whenever one exists, rerun converges from known package-manager states, and ambiguous integrity fails visibly rather than claiming readiness.

## 6. Service privilege conclusion

The core service account may read accepted models and corpus, and write only runtime, cache, index, and telemetry locations. It has no sudoers entry and no general Linux capabilities. USB audio and GPIO access are granted through the narrow target-platform mechanism proven on the Pi—normally supplementary groups and device permissions, with a scoped udev rule only if necessary.

The initial systemd unit uses `Type=exec`, `Restart=on-failure`, bounded start limits, `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectHome=true`, and a read-only system view with explicit writable locations. `PrivateDevices=true` is prohibited for this hardware-facing process. Additional hardening is accepted only after the same Pi test demonstrates input, output, GPIO, loopback Ollama, dashboard, stop cleanup, and hotplug recovery.

## 7. Core and extension acceptance boundary

| Capability | Core release | Later gate |
|---|---|---|
| USB audio | Required | G3 |
| Physical push-to-talk | Required | G3 |
| Dedicated red recording LED | Required | G3 |
| Local STT → retrieval → LLM → TTS | Required | G2/G3 |
| Source identifiers and insufficient-support response | Required | G2/G7 |
| Content-free telemetry | Required | G2/G7 |
| Loopback read-only dashboard over SSH forwarding | Required | G2/G7 |
| Headless systemd service | Required | G5 |
| Install/reinstall/update/rollback/uninstall | Required | G1/G5/G7 |
| “Hey Gonken” wake word | X1, not core | GX1 |
| Voice power control | X2, not core | GX2 |
| Direct LAN/phone dashboard | X3, not core | GX3 |
| Bluetooth audio | X4, not core | GX4 |

## 8. Review closure

All 18 mandatory questions have a concrete disposition. AR-08, AR-13, AR-14, and AR-17 were Critical at review entry and are resolved by removing unsafe privilege, correcting transaction claims, defining interruption recovery, and separating experimental scope. AR-19 remains a blocking M2/release governance gate with an explicit owner and does not require an ungrounded license choice in this review.

The next action after this review is M2.1 only: establish the package skeleton, sole GonKenLab identity, core-versus-extension boundaries, and licensing/provenance inventory with unit-testable compatibility wrappers. No installer/systemd/hardware mutation belongs in M2.1.

## 9. Primary evidence consulted

- [Raspberry Pi OS documentation](https://www.raspberrypi.com/documentation/computers/os.html)
- [Debian Trixie default Python package](https://packages.debian.org/trixie/python3)
- [Raspberry Pi remote-access documentation](https://www.raspberrypi.com/documentation/remote-access/)
- [Ollama Linux installation documentation](https://docs.ollama.com/linux)
- [Ollama local-only configuration](https://docs.ollama.com/faq)
- [Ollama model-list API and digest field](https://docs.ollama.com/api/tags)
- [Ollama release assets and published checksums](https://github.com/ollama/ollama/releases)
- [Qwen 3.5 2B Q4_K_M model entry](https://ollama.com/library/qwen3.5:2b-q4_K_M)
- [systemd execution-environment source documentation](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml)
- [systemd service source documentation](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml)
- [Filesystem Hierarchy Standard `/usr/local`](https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch04s09.html)
- [Filesystem Hierarchy Standard `/var/lib`](https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch05s08.html)
- [openWakeWord repository](https://github.com/dscripka/openWakeWord)
- [openWakeWord current issue tracker](https://github.com/dscripka/openWakeWord/issues)
- [whisper.cpp releases](https://github.com/ggml-org/whisper.cpp/releases)
- [Maintained Piper package/release evidence](https://pypi.org/project/piper-tts/)
