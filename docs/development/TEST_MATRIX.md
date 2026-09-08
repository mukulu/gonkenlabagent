# GonKenLab Agent Test Matrix

## 1. Test evidence rules

- `PASS` means the stated check passed in the recorded environment; it does not imply a higher test tier passed.
- `FAIL` means the test ran and an unmet requirement or unavailable prerequisite was observed.
- `BLOCKED` means required target conditions were unavailable.
- `NOT RUN` means the action was deliberately outside the milestone scope.
- Hardware results must record Pi model/RAM, OS image/version, kernel, architecture, Python, connected devices, power supply, cooling, commit, and test date.
- A later success does not erase earlier evidence; append a new result or explicitly supersede it.

## 2. Test tiers

| Tier | Name | Scope |
|---|---|---|
| T0 | Repository/static | syntax, formatting, config parse, inventory, Git integrity, secret/static scans |
| T1 | Host unit | deterministic tests with no live models, network, service, or hardware |
| T2 | Architecture install | dependency/install checks on target ARM64 OS or faithful clean image |
| T3 | Pi software | provisioned Pi without requiring external peripherals |
| T4 | Pi hardware | configured USB audio/GPIO/cooling and end-to-end physical behavior |
| T5 | Boot/recovery | reboot, service order, crash restart, hotplug, late network, upgrade, uninstall |
| T6 | Failure injection/security | interrupted steps, corrupted artifacts, low disk, permission failures, adversarial commands/privacy |

## 3. M0 baseline results

**Baseline commit:** `6682360786135136abeb0bd2a17a9d45c6f291e7`

**Date:** 2026-09-08 UTC

**Environment:** Ubuntu 24.04.3 LTS, x86_64, kernel 6.18.35, Python 3.12.13

| ID | Tier | Check | Command/procedure | Result | Interpretation |
|---|---|---|---|---|---|
| M0-T001 | T0 | Bootstrap/setup Bash parse | `bash -n bootstrap.sh setup.sh` | PASS | Shell grammar parses on Bash 5.2. |
| M0-T002 | T0 | Python byte compilation | `python3 -m compileall -q .` | PASS | Tracked Python contains no syntax error under Python 3.12. |
| M0-T003 | T0 | Runtime JSON parse | `jq empty config/config.json` | PASS | JSON syntax is valid. |
| M0-T004 | T0 | Whitespace/conflict check | `git diff --check` | PASS | Baseline has no diff error; rerun after documentation changes. |
| M0-T005 | T0 | Git object integrity | `git fsck --full --strict` | PASS | Reachable local Git object database is internally valid. |
| M0-T006 | T0 | Tracked inventory | `git ls-files` plus type/line inventory | PASS | 50 files: 26 Python, 2 shell, 14 media, 8 other text/config. |
| M0-T007 | T0 | PNG integrity | Parse all chunks and validate CRC/signature/IEND | PASS | All 9 face assets structurally valid. |
| M0-T008 | T0 | WAV integrity | Python `wave` open/header inspection | PASS | All 5 fillers are valid mono PCM, 16-bit, 22,050 Hz. |
| M0-T009 | T0 | Targeted secret history scan | Scan every reachable blob for major token/private-key patterns | PASS | No credible committed secret identified. This is not a guarantee against every secret format. |
| M0-T010 | T0 | systemd unit inventory | `git ls-files '*.service'` | FAIL | Zero service units; C-01 confirmed. |
| M0-T011 | T0 | CI workflow inventory | `git ls-files '.github/workflows/*'` | FAIL | Zero CI workflows. |
| M0-T012 | T0 | dependency lock inventory | `git ls-files '*lock*'` | FAIL | No dependency lock/constraints artifact. |
| M0-T013 | T0 | license inventory | `git ls-files 'LICENSE*' 'COPYING*'` | FAIL | README says MIT, but no license file is tracked. |
| M0-T014 | T2 probe | CPython 3.13/AArch64 binary resolution | `pip download` with `manylinux_2_28_aarch64`, CPython 3.13, binary-only | FAIL | Resolution reached pygame and found no matching binary wheel. Source-build viability remains untested; H-07, not proof of impossibility. |
| M0-T015 | T3-equivalent attempt on wrong host | Doctor without provisioning | `python3 scripts/doctor.py` | FAIL | Expected: wrong interpreter, missing deps/artifacts/Ollama. Confirms doctor fails rather than claiming ready. Not a target test. |
| M0-T016 | T3-equivalent attempt on wrong host | Router script without provisioning | `python3 tests/test_router.py` | FAIL | `httpx` unavailable on audit host. Not a product regression result. |
| M0-T017 | T4-equivalent attempt on wrong host | Wake script without provisioning | `python3 tests/test_wake_word.py` | FAIL | `sounddevice` unavailable. Not a target/hardware result. |
| M0-T018 | T4-equivalent attempt on wrong host | Smoke script without provisioning | `python3 scripts/smoke_test.py` | FAIL | `sounddevice` unavailable. Not a target/hardware result. |
| M0-T019 | T2 | Full bootstrap/setup on clean Pi image | privileged installer | NOT RUN | Deliberately outside documentation-only audit. |
| M0-T020 | T3 | Ollama + selected model inference on Pi | provision and run model tests | BLOCKED | No target Pi/Ollama/model. |
| M0-T021 | T4 | USB microphone/speaker pipeline | physical end-to-end test | BLOCKED | No target hardware. |
| M0-T022 | T4 | Wake-word accuracy | positive/negative/noise corpus | BLOCKED | No Gonken model or target hardware. |
| M0-T023 | T4 | GPIO push-to-talk/LED | physical test | BLOCKED | Not implemented; no hardware. |
| M0-T024 | T5 | Service enable/start/reboot | clean Pi reboot sequence | BLOCKED | App service not implemented. |
| M0-T025 | T5 | Audio renumber/hotplug recovery | reboot/replug/multiple-device scenarios | BLOCKED | Recovery not implemented; no hardware. |
| M0-T026 | T5 | Second installer run | complete → rerun → compare | BLOCKED | Requires target provisioning. |
| M0-T027 | T6 | Interrupted install recovery | interrupt each network/build stage and rerun | BLOCKED | State/recovery architecture not implemented. |
| M0-T028 | T6 | Voice shutdown safety | adversarial and false-trigger suite | BLOCKED | Feature not implemented. |
| M0-T029 | T6 | Offline boundary | disconnect network and monitor outbound attempts | BLOCKED | Default routing currently conflicts with requirement. |

## 4. Required future suites

The master blueprint must allocate stable IDs and concrete procedures for at least:

### Installation

- pristine supported Raspberry Pi OS Lite image;
- supported Python version matrix;
- non-root sudo user and explicit-root invocation;
- missing sudo, no network, DNS failure, clock skew, proxy, low disk, low memory;
- second/third identical invocation;
- interruption during APT, pip, Ollama install, model pull, Whisper clone/build/model download, Piper download;
- corrupted/zero-byte/wrong-checksum artifacts;
- existing dirty/untracked checkout and unexpected origin;
- upgrade from the inspected baseline and rollback.

### Runtime and service

- enable/start/stop/restart/status and clean journal output;
- boot with Ollama ready, delayed, failed, and missing model;
- boot with audio present, absent, late, renamed, duplicated, or disconnected mid-use;
- signal handling during idle, recording, inference, and speech;
- crash-loop prevention/watchdog behavior;
- correct service user/groups/filesystem permissions;
- no requirement for interactive autologin.

### Models and configuration

- installer/runtime/doctor/service/test model agreement;
- exact tag/digest presence and real inference;
- model pull recovery and insufficient-space handling;
- explicit endpoint consistency;
- environment/config precedence and invalid-value rejection;
- reasonable context/RAM/thermal limits for Pi 5 4GB.

### Audio and interaction

- microphone/speaker selection with multiple devices;
- supported sample rates and resampling quality;
- silence/no-speech/long-speech/noise behavior;
- TTS artifact cleanup;
- feedback-loop prevention;
- custom Gonken wake-word true/false-positive tests across speakers and noise;
- physical/manual recovery path;
- recording indicator consistency.

### Privacy, tools, and grounding

- no outbound request in offline mode;
- no raw-audio persistence by default;
- no transcript in telemetry-only mode;
- allow-listed read-only tools;
- shutdown/reboot exact phrase + confirmation + cancel/timeout;
- prompt/tool injection cannot execute arbitrary commands;
- retrieval hit@k, provenance coverage, unsupported-answer behavior;
- logs/support bundles redact secrets and sensitive content.

## 5. Latest test summary

- **T0:** M0 recorded 9 PASS and 4 baseline FAIL findings; M2.1 adds passing package/identity/inventory checks without closing unrelated findings.
- **T1:** M2.1 adds 15 passing dependency-free host tests; full M2.4 framework remains not started.
- **T2:** one limited dependency probe FAIL/risk; full target install NOT RUN.
- **T3–T6:** BLOCKED or NOT RUN as detailed above.
- **Production readiness:** not established.

## 6. M1A blueprint checks

**Draft base:** `checkpoint/audit` / commit `f71c371`

**Date:** 2026-09-08 UTC

| ID | Tier | Check | Command/procedure | Result | Interpretation |
|---|---|---|---|---|---|
| M1A-T001 | T0 | Blueprint exists and is non-placeholder | Inspect required sections and line count | PASS | Revision 1.0-draft contains architecture, contracts, milestones, gates, rollback, traceability, review checklist, and exact next action. |
| M1A-T002 | T0 | Critical finding traceability | Compare C-01–C-06 with Section 15 | PASS | 6 of 6 Critical findings mapped. |
| M1A-T003 | T0 | High finding traceability | Compare H-01–H-18 with Section 15 | PASS | 18 of 18 High findings mapped. |
| M1A-T004 | T0 | Deferred decision disposition | Compare audit/decision-log deferred list with blueprint Sections 2–13 | PASS | Each item is accepted/provisional or explicitly retained for M1B/M9. |
| M1A-T005 | T0 | Runtime code unchanged | Diff from `checkpoint/audit` excluding `docs/development/` | PASS | M1A changes development documentation only. |
| M1A-T006 | T0 | Primary-source alignment | Review Raspberry Pi, Ollama, systemd, FHS, openWakeWord, Whisper, and Piper primary references | PASS | Blueprint uses official/maintainer sources and preserves unverified target assumptions as gates. |
| M1A-T007 | T0 | Markdown/Git whitespace validation | `git diff --check` | PASS | Passed after all M1A control-document edits. |
| M1A-T008 | T0 | Adversarial architecture review | Execute Section 17 attack checklist | NOT RUN | Deliberately reserved for M1B; draft is not implementation-authorized. |
| M1A-T009 | T2–T6 | Target behavior | Hardware/install/runtime suites | BLOCKED | No runtime code changed; earlier blockers remain. |

## 7. M1B adversarial-review checks

**Reviewed draft:** `checkpoint/blueprint-draft`

**Accepted checkpoint:** `checkpoint/blueprint`

**Date:** 2026-09-08 UTC

| ID | Tier | Check | Command/procedure | Result | Interpretation |
|---|---|---|---|---|---|
| M1B-T001 | T0 | Review starts from exact clean draft | Compare HEAD/base tag and run `git diff --exit-code checkpoint/blueprint-draft --` before edits | PASS | M1B began at the committed/tagged M1A checkpoint with a clean worktree. |
| M1B-T002 | T0 | Mandatory review coverage | Compare draft Section 17 questions with `BLUEPRINT_ADVERSARIAL_REVIEW.md` AR-01–AR-18 | PASS | 18 of 18 mandatory questions have an explicit disposition and binding change. |
| M1B-T003 | T0 | Critical review closure | Inspect AR-08, AR-13, AR-14, and AR-17 plus revised blueprint contracts | PASS | All four Critical review findings are resolved; none is merely relabelled or silently deferred. |
| M1B-T004 | T0 | Blueprint accepted revision/state | Parse metadata and exact-next-action sections | PASS | Revision is `1.1-reviewed`, M1B is closed, and only M2.1 is authorized next. |
| M1B-T005 | T0 | Finding-to-test traceability | Compare C-01–C-06/H-01–H-18 with blueprint Section 15 and planned V-IDs | PASS | 24 of 24 audit findings map to work, a planned verification ID, and core/extension disposition. |
| M1B-T006 | T0 | Core/extension consistency | Search required capabilities, non-goals, gates, milestones, traceability, and status | PASS | Wake word, voice power, direct LAN dashboard, and Bluetooth are consistently X1–X4 rather than core gates. |
| M1B-T007 | T0 | Embedded configuration validity | Extract the first `toml` fence and parse with Python `tomllib` | PASS | Reviewed schema example is syntactically valid TOML. |
| M1B-T008 | T0 | Superseded architecture removed | Search active blueprint for old `/opt`/`/etc/opt`/`/var/opt`, core `Type=notify`, core wake dependency, and voice-only confirmation | PASS | Active contract uses reviewed paths, `Type=exec`, extension isolation, and independent physical power confirmation. Historical review/decision text remains intentionally. |
| M1B-T009 | T0 | Runtime code unchanged | Diff from `checkpoint/blueprint-draft` excluding `docs/development/` | PASS | M1B changes development documentation only. |
| M1B-T010 | T0 | Primary-source alignment | Review current Raspberry Pi OS/Debian, Ollama, systemd, FHS, openWakeWord, Whisper, and Piper primary evidence | PASS | Platform and implementation assumptions are either supported or retained as explicit target gates. |
| M1B-T011 | T0 | Markdown/Git whitespace validation | `git diff --check` and staged equivalent | PASS | Passed after all M1B control-document edits; staged check is repeated immediately before commit. |
| M1B-T012 | T2–T6 | Target behavior | Hardware/install/runtime suites | BLOCKED | M1B changes no runtime code; prior target blockers remain. |

Planned V-C/V-H/V-X identifiers are defined in `MASTER_BLUEPRINT.md` Section 15. They become executable test-matrix rows when their implementing milestone creates the test; a planned identifier is not a passing result.

## 8. M2.1 package/identity/provenance checks

**Starting checkpoint:** `checkpoint/blueprint` / commit `f92f6a1`

**Date:** 2026-09-08 UTC

**Environment:** Ubuntu 24.04.3 LTS, x86_64, Python 3.12.13; no Pi hardware, Ollama, audio, GPIO, network request, or extension runtime used

| ID | Tier | Check | Command/procedure | Result | Interpretation |
|---|---|---|---|---|---|
| M2.1-T001 | T0 | Clean accepted starting checkpoint | `git status --short --branch`; `git log -1 --decorate --oneline`; compare `checkpoint/blueprint` | PASS | Work began at the reviewed M1B commit with a clean tree. |
| M2.1-T002 | T1 | Package, CLI, identity, boundary, and provenance unit suite | `PYTHONPATH=src python -m unittest discover -s tests/unit -v` | PASS | 15/15 deterministic tests pass on the recorded host. |
| M2.1-T003 | T1 | Core import without optional dependencies | Isolated `python -I` subprocess inside M2.1 suite; inspect `sys.modules` | PASS | Package import loads none of the declared audio/model/network/UI/GPIO/extension roots. |
| M2.1-T004 / V-C03 | T0 | Sole active product identity | M2.1 active-surface scan plus `rg`; exclude explicitly historical `PRD.md` and immutable development evidence | PASS | Inherited personal/product names and the old spoken activation phrase are absent from active surfaces; technical `hey_jarvis` identifiers remain only in compatibility provisioning/detector evidence. |
| M2.1-T005 | T0 | TOML, JSON, Bash, whitespace, and Python syntax | Parse both TOML files with `tomllib`; `python -m json.tool`; `bash -n`; `compileall`; `git diff --check` | PASS | New metadata/inventory and changed source parse cleanly on the host. |
| M2.1-T006 | T1 | CLI success paths | `PYTHONPATH=src python -m gonken_agent version`; `... status --json` | PASS | Version and honest machine-readable status return exit 0. |
| M2.1-T007 | T1 | CLI refuses nonexistent packaged runtime | `PYTHONPATH=src python -m gonken_agent run`; assert exit 3 | PASS | CLI does not turn package installation into a false runtime-readiness claim. |
| M2.1-T008 | T0 | Offline wheel contents | Copy working tree to `mktemp`; call installed `setuptools.build_meta.build_wheel`; inspect ZIP members | PASS | Wheel contains only six `gonken_agent` Python files plus metadata; no legacy modules or repository assets. |
| M2.1-T009 | T0 | Media provenance completeness/integrity | Compare every file below `assets/` with `packaging/provenance.toml`; recompute SHA-256 | PASS | All 14 media files are individually inventoried and hash-matched; all remain `NOASSERTION`/unknown and excluded from wheel. |
| M2.1-T010 | T0 | Dependency inventory coverage | Compare non-comment `requirements.txt` names plus separately installed openWakeWord against inventory | PASS | Every current legacy requirement is recorded; no dependency is declared in the new core package yet. |
| M2.1-T011 | T0 governance | Project/distribution license approval | Maintainer selection and authority attestation | BLOCKED | No selection was received; source remains `NOASSERTION` and redistribution remains false. |
| M2.1-T012 | T0 governance | Unknown media disposition | Provenance/license proof or removal/replacement for each PNG/WAV | BLOCKED | Hashing proves identity, not ownership or permission. Full Git ZIP/publication is not approved. |
| M2.1-T013 | T2–T6 | Legacy runtime/hardware/install behavior | Existing installer, Ollama, audio, wake, Pi, service suites | NOT RUN | Outside M2.1; compatibility retention is not acceptance evidence. |

M2.1 implementation validation is green, but the milestone is not closed because
M2.1-T011 and M2.1-T012 are governance acceptance blockers. M2.2 must not begin.
