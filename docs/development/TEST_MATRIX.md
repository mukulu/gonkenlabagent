# GonKenLab Agent Test Matrix

Current continuation evidence is recorded in the `continuation-*` sections below. Earlier next-only authorization statements are historical, superseded by D-060. See the generated implementation status for current gates.

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

- **T0:** M0 recorded 9 PASS and 4 baseline FAIL findings; M2.1–M3.3 static, package, configuration, dependency-policy, test-boundary, bootstrap, install-engine, and immutable-release checks pass without closing unrelated findings.
- **T1:** M3.3 expands the dependency-free entry point to 103 unit and 21 deterministic process-integration tests; source success uses local Git fixtures and no internet, live service, model, device, or privilege boundary.
- **T2:** exact Python 3.13/AArch64 pygame wheel metadata now passes, superseding the old pygame-availability observation; networked resolution and the physical target install remain BLOCKED.
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
| M2.1-T002 | T1 | Package, CLI, identity, boundary, and provenance unit suite | `PYTHONPATH=src python -m unittest discover -s tests/unit -v` | PASS | 16/16 deterministic tests pass on the recorded host. |
| M2.1-T003 | T1 | Core import without optional dependencies | Isolated `python -I` subprocess inside M2.1 suite; inspect `sys.modules` | PASS | Package import loads none of the declared audio/model/network/UI/GPIO/extension roots. |
| M2.1-T004 / V-C03 | T0 | Sole active product identity | M2.1 active-surface scan plus `rg`; exclude explicitly historical `PRD.md` and immutable development evidence | PASS | Inherited personal/product names and the old spoken activation phrase are absent from active surfaces; technical `hey_jarvis` identifiers remain only in compatibility provisioning/detector evidence. |
| M2.1-T005 | T0 | TOML, JSON, Bash, whitespace, and Python syntax | Parse both TOML files with `tomllib`; `python -m json.tool`; `bash -n`; `compileall`; `git diff --check` | PASS | New metadata/inventory and changed source parse cleanly on the host. |
| M2.1-T006 | T1 | CLI success paths | `PYTHONPATH=src python -m gonken_agent version`; `... status --json` | PASS | Version and honest machine-readable status return exit 0. |
| M2.1-T007 | T1 | CLI refuses nonexistent packaged runtime | `PYTHONPATH=src python -m gonken_agent run`; assert exit 3 | PASS | CLI does not turn package installation into a false runtime-readiness claim. |
| M2.1-T008 | T0 | Offline wheel contents | Copy working tree to `mktemp`; call installed `setuptools.build_meta.build_wheel`; inspect ZIP members | PASS | Wheel contains only six `gonken_agent` Python files plus metadata; no legacy modules or repository assets. |
| M2.1-T009 | T0 | Media provenance completeness/integrity | Compare every file below `assets/` with `packaging/provenance.toml`; recompute SHA-256 | PASS | All 14 media files are individually inventoried and hash-matched; all remain `NOASSERTION`/unknown and excluded from wheel. |
| M2.1-T010 | T0 | Dependency inventory coverage | Compare non-comment `requirements.txt` names plus separately installed openWakeWord against inventory | PASS | Every current legacy requirement is recorded; no dependency is declared in the new core package yet. |
| M2.1-T011 | T0 governance | Project/distribution disposition | Verify D-050, package metadata, CLI status, README, and provenance inventory agree | PASS | No license is granted and redistribution is explicitly prohibited; no source-ownership authority is implied. |
| M2.1-T012 | T0 governance | Unknown/noncommercial artifact disposition | Verify D-051 and inventory policy; rebuild/inspect wheel | PASS | Unknown media and noncommercial voice/wake artifacts are private legacy evidence excluded from packages, releases, and public exports. |
| M2.1-T013 | T2–T6 | Legacy runtime/hardware/install behavior | Existing installer, Ollama, audio, wake, Pi, service suites | NOT RUN | Outside M2.1; compatibility retention is not acceptance evidence. |

M2.1 is complete. All M2.1 implementation and governance checks pass under the
explicit no-redistribution policy. Public-release licensing/provenance remains
a later blocking gate; it does not authorize weakened package boundaries during
M2.2.

## 9. M2.2 configuration-authority and migration checks

**Starting checkpoint:** `checkpoint/m2.1` / resolve with `git rev-list -n 1 checkpoint/m2.1`

**Date:** 2026-09-08 UTC

**Environment:** Ubuntu 24.04.3 LTS, x86_64, Python 3.12.13; no Pi hardware,
Ollama, audio, GPIO, network request, or extension runtime used. The wheel
install used `--ignore-requires-python` only to verify packaging mechanics on
the audit host; it is not Python 3.13 target evidence.

| ID | Tier | Check | Command/procedure | Result | Interpretation |
|---|---|---|---|---|---|
| M2.2-T001 | T0 | Clean accepted starting checkpoint | `git status --short --branch`; inspect HEAD/tag against `checkpoint/m2.1` | PASS | M2.2 began at the committed M2.1 boundary with a clean worktree. |
| M2.2-T002 | T1 | Full dependency-free host suite | `PYTHONPATH=src python -m unittest discover -s tests/unit -v` | PASS | 42/42 tests pass without live services, hardware, optional dependencies, or network. |
| M2.2-T003 / V-H01 | T1 | Every-field authority and precedence | Table-driven defaults/site/environment/CLI coverage in `test_m2_2_config.py` | PASS | Every schema leaf is typed and source-attributed at all four layers; differing model values prove the required order. |
| M2.2-T004 | T1 | Strict schema and value rejection | Invalid/unknown/type/enum/bounds/duration/model/path/GPIO/audio/privacy cases | PASS | Invalid configuration fails with `ConfigError`; unknown keys are not silently ignored. |
| M2.2-T005 | T1 | Offline and extension boundaries | Remote LLM, non-loopback dashboard, wake enablement, and voice-power enablement cases | PASS | Offline core cannot be configured onto remote endpoints or prematurely enable X1/X2. |
| M2.2-T006 | T1 | Redacted effective output and source attribution | Human and JSON CLI tests with one-shot override | PASS | Filesystem values and source file paths are not disclosed; source category/env/CLI identity remains visible. |
| M2.2-T007 | T1 | Legacy migration convergence | Migrate repository JSON plus `.env.example` twice; compare inputs/output/backups/modes | PASS | Inputs remain byte-identical; second run does not rewrite output or duplicate backups; output is `0600`, backup directory/files are `0700`/`0600`. |
| M2.2-T008 | T1 | Migration failure paths | Unknown keys, unsafe relative path, enabled UI, populated external credential, and differing destination | PASS | Invalid/unsupported input creates no output; an administrator-owned differing output remains byte-identical. |
| M2.2-T009 / V-H02 | T0/T1 | Consumer convergence | Source assertions plus compatibility-adapter test; inspect setup/doctor/client construction and `OLLAMA_HOST` export | PASS | Installer readiness/CLI, doctor, Ollama client, and Ollama CLI receive the same validated endpoint; runtime/test model values have no active fallback. |
| M2.2-T010 | T0 | Static syntax and whitespace | `bash -n bootstrap.sh setup.sh`; `compileall`; TOML/JSON parse; `git diff --check` | PASS | Changed shell, Python, TOML, JSON, and patch whitespace validate on the host. |
| M2.2-T011 | T0 | Offline wheel build and installed defaults | Build with local `setuptools.build_meta`; inspect wheel; install with `PIP_NO_INDEX=1 --no-deps --ignore-requires-python`; run installed CLI outside checkout | PASS | Wheel includes package code plus `share/gonken-agent/defaults.toml`; installed CLI locates the shipped Qwen 3.5 defaults without source checkout or network. |
| M2.2-T012 | T2–T6 | Pi/configuration integration | Target Python, installer, service, audio, GPIO, runtime, reboot, and failure injection | BLOCKED | M2.2 proves host configuration contracts only; target/hardware claims remain assigned to later milestones. |

M2.2 is complete. H-01 and H-02 are resolved for active configuration
consumers. The historical JSON retains its old value solely as tested migration
input; it is not a runtime layer. M2.3 followed as the only authorized work package.

## 10. M2.3 dependency-profile and lock checks

**Starting checkpoint:** `checkpoint/m2.2` / resolve with `git rev-list -n 1 checkpoint/m2.2`

**Date:** 2026-09-08 UTC

**Environment:** Ubuntu 24.04.3 LTS, x86_64, Python 3.12.13 and pip 26.2.1.
No Raspberry Pi, Python 3.13 interpreter, package-index network access, audio,
GPIO, model, Ollama, pygame, or governed extension was used. Target artifact
existence/hash evidence was read from the authoritative PyPI release page.

| ID | Tier | Check | Command/procedure | Result | Interpretation |
|---|---|---|---|---|---|
| M2.3-T001 | T0 | Clean accepted starting checkpoint | `git status --short --branch`; inspect HEAD/tag against `checkpoint/m2.2` | PASS | M2.3 began at committed M2.2 with a clean worktree. |
| M2.3-T002 / V-H06 | T0/T1 | Deterministic exact-lock policy | `python scripts/dependencies.py render --check`; profile unit tests | PASS | Four installable locks match the manifest byte-for-byte; all force hashes and binary wheels. Empty core/dev graphs are explicit. |
| M2.3-T003 | T1 | Full dependency-free host suite | `PYTHONPATH=src python -m unittest discover -s tests/unit -v` on host and isolated venv | PASS | 51/51 tests pass in both environments without a network, model, hardware, or optional dependency. |
| M2.3-T004 / V-H06 | T1 | Clean x86 development install | Build wheel with local backend; create fresh venv; install `dev-py312.lock` and wheel with `--no-index`; run `pip check`, import, status | PASS | Python 3.12 installs without bypassing `Requires-Python`; `pip check` reports no broken requirements and status remains not runtime-ready. |
| M2.3-T005 / V-H08 | T1 | Headless core excludes optional UI/wake | In isolated venv, import package and assert `find_spec('pygame')` and `find_spec('openwakeword')` are `None` | PASS | Mandatory pygame is removed and openWakeWord cannot leak into the maintained core. |
| M2.3-T006 / V-H07 | T2 metadata | Target UI wheel identity and hash | Inspect PyPI pygame 2.6.1 file details; compare CPython 3.13/AArch64 filename/SHA-256 with `profiles.toml` | PASS (LIMITED) | Exact compatible wheel metadata exists and matches `27eb17...510b`; this is not download, install, import, or Pi evidence. |
| M2.3-T007 / V-H07 | T2 | Networked AArch64 resolution/download | Documented binary-only `pip download` for `pi-trixie-py313.lock` and `ui-pi-trixie-py313.lock` | BLOCKED | Environment network policy rejected the resolver invocation before execution. No wheelhouse was created; metadata evidence is not promoted. |
| M2.3-T008 / V-H07 | T2/T3 | Physical Pi Python 3.13 venv install | Fresh supported Raspberry Pi OS Lite/Trixie image; install core and optional profiles; `pip check` and imports | BLOCKED | No Raspberry Pi target is available. H-07 remains open. |
| M2.3-T009 | T0 governance | License/profile report | `python scripts/dependencies.py report` and `report --json`; inspect provenance revision 1.2 | PASS | Selected pygame is exact and LGPL-2.1-or-later; wake/TTS candidates are reported blocked rather than silently accepted. |
| M2.3-T010 | T0 | Broad-input quarantine | Verify no root `requirements.txt`; inspect `legacy-prototype.in`, `setup.sh`, `doctor.py`, and pyproject extras | PASS | Broad ranges remain only in the explicitly unaccepted prototype; pygame is neither a mandatory legacy install nor required doctor import. |
| M2.3-T011 | T0 | Static syntax and whitespace | `bash -n`; `compileall`; TOML/JSON parse; `git diff --check` | PASS | Changed shell, Python, TOML, JSON, locks, and patch whitespace validate on the host. |
| M2.3-T012 | T1/T2 | Optional UI download/install/import | Install the appropriate exact UI lock from a fresh wheelhouse and import pygame | BLOCKED | Package-index access is unavailable. Both host/target filenames and hashes are recorded; execution evidence remains outstanding. |
| M2.3-T013 | T2–T4 | Voice/wake runtime dependency graph | Select package/voice/backend, create complete transitive locks, install and infer on Pi | BLOCKED | Maintained runtime is not packaged; Piper/voice licensing and X1 wake compatibility/model gates are unresolved. Placeholder locks are prohibited. |

M2.3 is complete for the maintained package foundation. H-08 is resolved and
H-06 is controlled for the current exact graph; both must be rechecked whenever
runtime dependencies are added. H-07 remains open pending networked AArch64
resolution and a real Pi venv. M2.4 followed as the only authorized work package.

## 11. M2.4 automated-test foundation checks

**Starting checkpoint:** `checkpoint/m2.3` / resolve with `git rev-list -n 1 checkpoint/m2.3`

**Date:** 2026-09-08 UTC

**Environment:** Ubuntu 24.04.3 LTS, x86_64, Python 3.12.13. No pytest,
package-index request, Ollama, model, audio device, GPIO, pygame, openWakeWord,
or elevated privilege was used by the automated entry point.

| ID | Tier | Check | Command/procedure | Result | Interpretation |
|---|---|---|---|---|---|
| M2.4-T001 | T0 | Clean accepted starting checkpoint | `git status --short --branch`; inspect HEAD/tag against `checkpoint/m2.3` | PASS | M2.4 began at committed M2.3 with a clean worktree. |
| M2.4-T002 | T0 | Legacy probe classification | Inspect removed top-level test paths and replacement locations/names | PASS | Live Ollama belongs to `tests/integration/manual`; microphone/speaker and wake detection belong to `tests/hardware`; none uses a discoverable `test_*.py` name. |
| M2.4-T003 | T0/T1 | Single default entry point | `./scripts/ci.sh` | PASS | Lock rendering, syntax/data parsing, 63 unit tests, and three deterministic integration tests pass without installing dependencies. |
| M2.4-T004 | T1 | Optional-boundary isolation | Architecture tests scan automated suites and inspect imports loaded by the fake router path | PASS | Automated tests import no declared external optional module and load no HTTP/Ollama client on the deterministic router path. |
| M2.4-T005 | T1 | Router fake and fixtures | `tests/unit/test_legacy_router.py` with `tests/fixtures/router_cases.json` and `router_fakes.py` | PASS | Structured tool calls, history bounds, fallback categories, and all fixture routes execute without a service or network. |
| M2.4-T006 | T1 | Contradiction regression | Joke and word-boundary unit cases | PASS | A joke request maps to `get_joke`; category/phrase fragments inside unrelated words do not trigger tools. |
| M2.4-T007 | T0 | Wake-phrase claim | Inspect `tests/hardware/wake_word_manual.py` | PASS | The retained legacy model probe explicitly advertises no accepted spoken phrase; X1 “Hey Gonken” remains disabled. |
| M2.4-T008 | T1 | Manual/live opt-in guard | Run each manual program without its opt-in environment variable | PASS | Each returns exit 2 before external optional imports or device/service access. |
| M2.4-T009 | T0/T1 | Repository-root independence | Invoke absolute `scripts/ci.sh` path while the caller is outside the checkout | PASS | The entry point resolves and changes to its own repository root before checking or running suites. |
| M2.4-T010 | T0/T1 | Clean-checkout repeatability | Local no-hardlink full-history clone of `d79ac48515db7d613c0ba5a020981a3953fa0b87`; create fresh stdlib-only venv; run `PYTHON_BIN=<fresh-venv>/bin/python ./scripts/ci.sh`; compare worktree before/after | PASS | All 66 tests and T0 checks pass from committed files; the cloned worktree remains clean. |
| M2.4-T011 | T1 | Third-party runner | Inspect exact dev lock and D-055 | NOT RUN | Pytest is absent and was not downloaded. The suites remain pytest-discoverable, but M2.4 makes no pytest-execution claim. |
| M2.4-T012 | T2–T4 | Live router/audio/wake behavior | Opt in with documented variables on a recorded service/hardware environment | NOT RUN | Audit host lacks accepted runtime dependencies, Ollama/model readiness, and Raspberry Pi audio/wake hardware; manual observations cannot count as automated evidence. |

M2.4 is complete. Its T0/T1 boundary is deterministic and dependency-free; no
result establishes Pi, service, model, or physical audio readiness. M3.1 is the
only next authorized work package.

## 12. M3.1 bootstrap-preflight checks

**Starting checkpoint:** `checkpoint/m2.4` / `7ecb420ccde1bd4a0d177ea49421d8e7266aedb4`

**Date:** 2026-09-08 UTC

**Environment:** Ubuntu 24.04.3 LTS, x86_64, Python 3.12.13. Production-target
facts are deterministic fixtures; source success uses local `file://` Git only
under explicit development mode. No package/service/configuration/install-tree
mutation, internet request, Raspberry Pi, model, audio, or GPIO was used.

| ID | Tier | Check | Command/procedure | Result | Interpretation |
|---|---|---|---|---|---|
| M3.1-T001 | T0 | Clean accepted starting checkpoint | Compare clean HEAD with `checkpoint/m2.4` before edits | PASS | M3.1 began at the committed/tagged M2.4 boundary. |
| M3.1-T002 | T0/T1 | Full deterministic repository entry point | `./scripts/ci.sh` | PASS | Bash/data/source checks, 81 unit tests, and six deterministic integration tests pass without network or optional dependencies. |
| M3.1-T003 / V-H03 | T1 | Root and sudo-user matrix | PATH-stub `id`/`sudo` tests for direct root, root reached through sudo, non-root, missing sudo, and rejected credentials | PASS | Direct root does not require sudo; sudo-root records the non-root invoker; non-root validates once; unavailable/rejected sudo fails diagnostically. |
| M3.1-T004 / V-H04 | T1 | Privilege lifetime and ordering | Count stubbed `sudo -v`; inspect process failure ordering | PASS | Exactly one interactive credential validation occurs before remote access; subsequent planned privilege prefix is `sudo -n`; rejected hosts create no staging or installed mutation. |
| M3.1-T005 | T1 | Production platform contract | Fixture matrix for Debian 13/Trixie, AArch64, 64-bit userspace, Python 3.13 patch, systemd PID 1, Pi 5 model, and Raspberry Pi image reference | PASS | Exact supported facts pass; each unsupported OS/arch/Python/init/board/image variant fails with a structured code. This is not physical-Pi evidence. |
| M3.1-T006 | T1 | Development-host separation | Validate Linux x86_64/AArch64, 64-bit, Python 3.12/3.13; reject other host contract | PASS | Host mode is explicit and cannot be mistaken for the production target. |
| M3.1-T007 | T1 | Disk, RAM, and clock gates | Boundary values through `gonken_validate_resources` | PASS | Less than 8 GiB staging space, insufficient mode-specific RAM, and pre-2025 clock each fail independently before remote access/staging. Thresholds remain provisional pending Pi measurement. |
| M3.1-T008 | T1 | Required commands | Invoke command inventory with a deliberately missing command | PASS | Missing tools produce `PREFLIGHT_COMMAND` and remediation rather than a late shell failure. |
| M3.1-T009 | T1 | Source request safety | Reject credential-bearing/invalid HTTPS, traversal ref, production `file://`, and divergent same-name branch/tag; resolve an advertised local development ref | PASS | Target source is credential-free HTTPS; branch/tag names are validated and unambiguous; successful resolution records exactly one full commit. |
| M3.1-T010 | T1 | Network/ref failure | Stub `git ls-remote` failure | PASS | Unreachable source or absent ref produces `PREFLIGHT_NETWORK` without staging or a false success. |
| M3.1-T011 | T1 | Existing checkout preservation | Temporary Git/file fixtures for clean, tracked dirty, staged dirty, untracked, wrong origin, empty, absent, and non-Git content | PASS | Only clean expected-origin or empty/absent states pass; rejected content remains byte-identical. |
| M3.1-T012 | T1 | Private facts record | Create temporary staging and inspect contents/modes | PASS | Staging is mode 700; `source.record` is mode 600 and contains source commit and observed facts. It is line data, never shell-sourced. |
| M3.1-T013 | T1 | End-to-end development preflight | Run `bootstrap.sh --development-host --preflight-only` against a temporary local Git repository | PASS | Process resolves the exact commit and writes the private record without calling network, sudo, setup, or an installer. |
| M3.1-T014 | T1 | Unsupported-host ordering | Run target mode on the x86 audit host with a logging Git stub | PASS | Exit 78 reports `PREFLIGHT_PLATFORM`; no `ls-remote` call and no staging entry occur. |
| M3.1-T015 | T1 | M3.2 boundary | Run valid development preflight without `--preflight-only` | PASS | Exit 69 reports `M3_2_UNAVAILABLE` after recording evidence and never invokes `setup.sh` or a nonexistent installer. |
| M3.1-T016 | T0/T1 | Clean-checkout repeatability | Clone implementation commit `29b5143febfea299454f56f05a75be06bffd790c` without hardlinks; create a fresh stdlib-only venv; run `PYTHON_BIN=<venv>/bin/python ./scripts/ci.sh`; compare worktree and run `git fsck --full --strict` | PASS | All 87 tests and T0 checks pass from committed files; the cloned worktree remains clean and Git object validation succeeds. |
| M3.1-T017 | T2/T3 | Physical target and real HTTPS source | Supported freshly imaged Pi 5; target preflight against intended GitHub ref | BLOCKED | No Raspberry Pi target is available. Fixture/host evidence cannot close the target gate. |

M3.1 is complete, including post-commit clean-checkout verification.
H-03/H-04 are resolved for the preflight boundary. M3.2 was the next authorized
package at that checkpoint; D-057 subsequently kept it control-only and moved
the first real source/release mutation to M3.3. The M3.1 state was deliberately
not install-ready.

## 13. M3.2 step-engine and install-state checks

**Starting checkpoint:** `checkpoint/m3.1` / `2ed709fb7bc423d0a0b9c48661df3a152049dbf7`

**Date:** 2026-09-08 UTC

**Environment:** Ubuntu 24.04.3 LTS, x86_64, Python 3.12.13. Source-ref
success uses local `file://` Git only under development mode. No package,
release, virtual environment, service, model, network request, Raspberry Pi,
audio device, or GPIO was used.

| ID | Tier | Check | Command/procedure | Result | Interpretation |
|---|---|---|---|---|---|
| M3.2-T001 | T0 | Clean accepted starting checkpoint | Compare clean HEAD with `checkpoint/m3.1` before edits | PASS | M3.2 began at the committed/tagged M3.1 boundary. |
| M3.2-T002 | T0/T1 | Full deterministic repository entry point | `./scripts/ci.sh` | PASS | Bash/data/source checks, 92 unit tests, and 16 deterministic integration tests pass without network or optional dependencies. |
| M3.2-T003 | T1 | Complete stable step definition | Register valid/invalid/duplicate step IDs, versions, functions, and metadata | PASS | A step cannot execute unless it declares all eight contract elements; malformed or duplicate definitions fail with exit 64. |
| M3.2-T004 | T0/T1 | Atomic private state and append-only events | Inspect directory/file modes, temporary cleanup, symlink rejection, byte snapshots, and consecutive event sets | PASS | Records use private same-directory rename; satisfied artifacts/current state remain byte-identical; later runs append collision-safe event evidence without changing earlier events. |
| M3.2-T005 | T1 | Source record is data | Supply malformed, unknown, duplicate, permissive, and command-substitution values | PASS | Input is parsed line by line and never evaluated; invalid input fails before installer-state creation. |
| M3.2-T006 | T1 | Independent source/host revalidation | Recheck recorded development facts and advance the advertised local ref | PASS | A moved ref returns `INSTALL_SOURCE_CHANGED` before state mutation; successful runs remain bound to the recorded commit. |
| M3.2-T007 / V-H10 | T1 | Probe authority over advisory state | Corrupt a real marker while retaining `complete`; remove state while retaining a valid marker | PASS | Failed postconditions trigger repair; passing postconditions reconstruct advisory state without replaying action. Generic state correctness is controlled, not the future activation boundary. |
| M3.2-T008 | T1 | Failure-code preservation | Force precondition, action, and post-action postcondition failures | PASS | Precondition/action codes are preserved and a missing postcondition after a successful action maps to stable exit 74. |
| M3.2-T009 | T1 | Exclusive invocation and PID reuse | Construct live, stale, and same-PID/different-start lock records | PASS | A true live owner is retained and rejected; dead/prior-identity ownership is recovered; corrupt ambiguity requires manual inspection. |
| M3.2-T010 | T1/T6 fixture | Cooperative interruption matrix | Inject TERM before/during/after each of fake steps `alpha` and `beta`, then rerun | PASS | All six cases record `interrupted`, remove tracked temporaries/owned locks, and converge to both verified postconditions on rerun. |
| M3.2-T011 | T1/T6 fixture | Abrupt-death recovery | Inject KILL during `alpha`, inspect `running`/partial/stale lock, then rerun | PASS | Untrappable death leaves observable partial state; identity-bound stale-lock recovery and idempotent action converge without a false completion. |
| M3.2-T012 | T1 | Bootstrap routing and milestone stop | Run valid development bootstrap normally and with `--preflight-only` | PASS | Preflight-only remains non-mutating; default invokes the engine, proves its two markers, exits `M3_3_UNAVAILABLE`, and never reaches legacy setup. |
| M3.2-T013 | T0/T1 | Clean-checkout repeatability | No-hardlink clone of `28ac3dac9ecf591c1845712036d97119377a9f37`; fresh stdlib-only venv; `PYTHON_BIN=<venv>/bin/python ./scripts/ci.sh`; cleanliness and `git fsck --full --strict` | PASS | All 108 tests and T0 checks pass from committed files; the cloned worktree remains clean and strict Git object validation succeeds. |
| M3.2-T014 | T2/T3/T6 | Physical target, real source, and power loss | Supported freshly imaged Pi 5; HTTPS source; controlled power interruption and storage inspection | BLOCKED | No Raspberry Pi target is available. Fake TERM/KILL coverage cannot establish filesystem durability, target behavior, or real power-loss recovery. |

M3.2 is complete at the host control-engine boundary. It performs no
privileged or installed-system mutation, so success is not installation
evidence. M3.3 is the only next authorized work package and must revalidate
H-03/H-04/H-10 at immutable candidate, journal, and atomic-switch boundaries.

## 14. M3.3 immutable-release and activation checks

**Starting checkpoint:** `checkpoint/m3.2` / `6af99b2ed0379ba1a976ee184bb32d2e74b0205f`

**Implementation commit:** `0ea9db1` (`feat: add immutable release activation lifecycle`)

**Date:** 2026-09-09 UTC

**Environment:** Linux x86_64, Python 3.12.14, setuptools 84.0.0. Exact-source
success uses a local `file://` Git repository and disposable FHS-shaped root.
The test venv installs the empty exact development lock and a locally built
wheel with `--no-index`. No internet, APT mutation, sudo transition, non-root
service account, Raspberry Pi, systemd service, Ollama, model, audio, or GPIO
was used.

| ID | Tier | Check | Command/procedure | Result | Interpretation |
|---|---|---|---|---|---|
| M3.3-T001 | T0 | Clean accepted starting checkpoint | Compare clean HEAD with `checkpoint/m3.2` before edits | PASS | M3.3 began at the committed/tagged M3.2 boundary. |
| M3.3-T002 | T0/T1 | Full deterministic repository entry point | `./scripts/ci.sh` | PASS | Static/data checks, 103 unit tests, and 21 integrations pass without a live external boundary. |
| M3.3-T003 | T0/T1 / V-H04 | Exact verified source acquisition | End-to-end local Git fixture; source-record/ref and archive-rejection tests; inspect submodule guard | PASS | Installed payload is rebuilt from the exact recorded commit; ref movement and unsafe traversal/link/archive or submodule types fail closed. No mutable checkout tree is installed. |
| M3.3-T004 | T1 / V-H06 | Release-local environment and smoke | Build wheel; create venv; install applicable lock and local wheel with no index; run installed CLI version/status and `pip check` | PASS | The committed dependency-light core installs and executes outside its source checkout without inherited `PYTHONPATH`; backend version and lock/wheel hashes are recorded. |
| M3.3-T005 | T1 / V-H10 | Manifest, immutability, and integrity | Validate schema, path/commit/profile/digests/owner/modes/smoke; mutate fake payload | PASS | Final release has no write bits and post-build payload changes are rejected; malformed identity or pointer state cannot become activation truth. |
| M3.3-T006 | T1 | Conservative headroom | Override observed free KiB below the computed threshold | PASS | Exit 78 occurs before a final release or `current` pointer exists. The threshold is not model-space or Pi performance evidence. |
| M3.3-T007 | T1/T6 fixture / V-H10 | Candidate-finalization interruption | TERM before/during/after freeze-and-rename, inspect old/new state, rerun | PASS | All three boundaries leave either the complete candidate or final payload; rerun converges. A narrowly complete rename/top-mode interval is identity/digest/owner checked before repair. |
| M3.3-T008 | T1/T6 fixture / V-H10 | Journal, pointer, and postcheck interruption | TERM before/during/after each of journal replacement, `current` replacement, and post-switch validation; rerun activation | PASS | All nine boundaries converge to a post-verified candidate without stale journal/pointer temporaries. Host signals are not physical power-loss evidence. |
| M3.3-T009 | T1 / V-H10 | Failed post-switch validation rollback | Candidate fake passes prechecks then fails the post-switch smoke | PASS | Exit code is preserved, `current` returns to the prior validated release, and journal becomes `rolled_back`. |
| M3.3-T010 | T1 | Ambiguity fails closed | Disagree a `post_verified` journal and constrained `current` link | PASS | Reconciliation returns `ACTIVATION_AMBIGUOUS` and does not rewrite the pointer based on guesswork. |
| M3.3-T011 | T1 | Global activation mutual exclusion | Hold `maintenance.lock`; invoke concurrent reconciliation | PASS | Concurrent state mutation returns exit 75/`ACTIVATION_BUSY`; full installs also share the installed-state M3.2 engine lock. |
| M3.3-T012 | T1 | Validated two-release retention | Create three valid immutable releases; record active and previous; prune | PASS | Only active and previous remain. An inactive release is fully validated before controlled removal; corrupt evidence is not silently deleted. |
| M3.3-T013 | T0/T1 / V-H03 | Privilege/account/source-record boundary | Inspect sudo handoff and non-login account declarations; test root-readable invoking-user-owned private record and bootstrap routing | PASS (HOST-LIMITED) | The code performs one validated sudo transition, keeps root ownership of code/state, and reserves runtime smoke for the service user. Real `useradd`/`runuser`/APT execution remains untested on target. |
| M3.3-T014 | T1 | Stable entrypoint and reconciliation payload | Initialize temporary layout; inspect relative entrypoint; hash/copy exact-source maintenance helpers into release | PASS | Stable CLI path crosses only constrained `current`; release contains its exact reconciliation implementation for later M6 pre-start wiring. No service is installed. |
| M3.3-T015 | T1 | Repeatability and milestone stop | Repeat `--release-only`; compare manifest; invoke normal installer | PASS | Repeat leaves the release record byte-identical. Normal execution reports `M3_3_RELEASE_COMPLETE` then exits 69/`M3_4_UNAVAILABLE`, never legacy setup. |
| M3.3-T016 | T0/T1 | Clean-checkout repeatability | No-hardlink clone of `6c4c19e82be9cf47f5181a342f9f8638d754abe7`; fresh Python 3.12.14 venv; `PYTHON_BIN=<venv>/bin/python ./scripts/ci.sh`; inspect cleanliness and run `git fsck --full --strict` | PASS | All 124 tests and T0 checks pass from committed files; the cloned worktree remains clean and strict Git object validation succeeds. System setuptools 84.0.0 remains the recorded local build prerequisite. |
| M3.3-T017 | T2/T3/T6 | Real target, HTTPS, privilege, filesystem, and power loss | Fresh supported Pi 5; normal bootstrap; controlled interruptions/reboots; inspect ownership/journal/pointer | BLOCKED | No target is available. Host evidence cannot establish APT/account behavior, Python 3.13/AArch64 install, storage durability, or boot reconciliation. |

M3.3 is implementation-complete at T0/T1. The installed
artifact is only the dependency-light core package and release machinery; no
model, speech pipeline, application service, or hardware readiness exists.
At the M3.3 checkpoint, M3.4 was the only next authorized work package; the
following section records its completed host evidence.

## 15. M3.4 Ollama and selected-model lifecycle checks

**Starting checkpoint:** `checkpoint/m3.3` / `b7575cb44c04b7da90b1a73fec2e89a61a88dd76`

**Implementation commit:** `980e09c153d4c3232c6bc8390bcbd4f1dcf0a1bd`

**Date:** 2026-09-09 UTC

**Environment:** Linux x86_64, Python 3.12.14, system Zstandard CLI. The
end-to-end fixture builds a tiny local fake Ollama ARM64-shaped tar.zst, uses a
disposable FHS-shaped root, a fake systemctl executable, and a loopback HTTP
server implementing only the tested API contract. Automated tests perform no
internet access, APT/account mutation, real systemd operation, Ollama execution,
model download/inference, service-user transition, or Raspberry Pi operation.

| ID | Tier | Check | Command/procedure | Result | Interpretation |
|---|---|---|---|---|---|
| M3.4-T001 | T0 | Clean accepted starting checkpoint | Compare clean HEAD with `checkpoint/m3.3` before edits | PASS | M3.4 began at the committed/tagged M3.3 boundary. |
| M3.4-T002 | T0/T1 | Full deterministic repository entry point | `./scripts/ci.sh` | PASS | Static/data checks, 109 unit tests, and 26 integrations pass without a live external boundary. |
| M3.4-T003 | T0 / V-H04 | Closed upstream artifact authority | Parse `packaging/ollama-artifacts.toml`; inspect exact release, asset, SHA-256, model tag/prefix, sources, and licenses | PASS | Ollama `0.33.3` stable ARM64 and `qwen3.5:2b-q4_K_M` are explicit. Unknown fields, invalid identities, and non-HTTPS production URLs fail. Upstream observations are dated; this is not a real download. |
| M3.4-T004 | T1/T6 / V-H04 | Resumable verified acquisition and safe extraction | Local file fixture; checksum mismatch; traversal/device/FIFO/escaping-link/duplicate guards; redirect policy inspection | PASS | Only a matching SHA-256 payload can reach a candidate. Unsafe archive types and an HTTPS-to-non-HTTPS redirect are rejected. |
| M3.4-T005 | T1/T6 / V-H10 | Immutable Ollama release activation | Extract fixture; record asset/binary/complete-payload hashes; atomic versioned rename; validate links/modes; interrupt finalization | PASS | Stable entrypoint reaches only an exact read-only version. The narrow rename/top-mode interval is repaired only with exact digest, modes, and ownership. |
| M3.4-T006 | T0/T1 / V-H03, V-H02 | Account, unit, loopback, and resource contract | Inspect installer account/path steps and exact unit/drop-in; fake enabled/active systemctl and exact `/api/version` | PASS (HOST-LIMITED) | Separate non-login `ollama`, private model store, loopback/no-cloud, one loaded model, one parallel request, and exact version readiness are enforced by code. Real account/systemd behavior remains blocked. |
| M3.4-T007 | T0/T1 / V-H01, V-H02 | Configuration convergence | Inspect installed CLI JSON extraction and manager argument validation; run existing config convergence suite | PASS | Installer model, endpoint, and context come from the active release's effective configuration; remote/non-HTTP/credentialed/path-bearing origins fail. |
| M3.4-T008 | T1 / V-H01 | Authoritative model identity | Fake `/api/tags` exact tag/full digest/quantization; missing model triggers pull; wrong prefix/quantization and later full-digest drift | PASS | The source-pinned catalog prefix constrains the full local digest. Mutable tag drift never silently replaces recorded identity. |
| M3.4-T009 | T1 | Deterministic inference evidence | Fake `/api/generate`; require nonempty response and `done`; inspect request temperature/seed/context/predict/keep-alive and private record | PASS | Smoke completion and performance counts are stored without prompt/response content. This is contract evidence, not model-quality or speed evidence. |
| M3.4-T010 | T1/T6 / V-H10 | All lifecycle interruption boundaries | TERM before/during/after download, extraction, binary finalization, readiness, pull, and smoke; rerun then status | PASS | All 18 interruption points converge to their exact postcondition. Partial downloads/blobs are reusable; unverified candidates never activate. Host TERM is not physical power-loss evidence. |
| M3.4-T011 | T1/T6 | Conflicts and drift fail closed | Seed differing systemd unit; change API digest after recording; test unsafe redirected root without gate | PASS | Administrator files are not overwritten, recorded model identity is not rewritten, and test-only paths cannot be used accidentally. |
| M3.4-T012 | T1 | Repeatability and status | Repeat binary/service/model provisioning; run all three status commands; inspect record and links | PASS | Rerun validates live postconditions, retains original pull byte evidence, and does not repull an accepted model. |
| M3.4-T013 | T1 / V-H04 | Exact-source maintenance boundary | M3.3 end-to-end local Git build copies manager, manifest, unit, and drop-in into release payload and validates payload digest | PASS | Target provisioning consumes inputs from the activated immutable release, not the mutable checkout. |
| M3.4-T014 | T2/T3/T6 | Real Pi provisioning | Supported clean Pi 5; HTTPS asset/model download; account/unit install; API and inference; rerun and corrupt/interrupted cases | BLOCKED | No target is available. Host fixtures cannot establish ARM64 execution, real service ownership, storage behavior, or upstream transfer recovery. |
| M3.4-T015 | T3/T5 | Pi resource and reboot behavior | Record pull/inference RAM, latency, CPU, temperature/throttling; reboot; confirm enabled/active/readiness/digest | BLOCKED | The provisional 2K context and one-model/one-parallel limits require physical 4GB-Pi acceptance evidence. |
| M3.4-T016 | T6 / V-C02 | Normal-runtime outbound-network denial | Complete M5.2 runtime; deny/disconnect upstream; observe sockets/traffic while local inference remains functional | BLOCKED | Loopback binding and `OLLAMA_NO_CLOUD=1` are implemented, but kernel-observed no-outbound runtime enforcement is a later gate. |
| M3.4-T017 | T0/T1 | Clean-checkout repeatability | No-hardlink clone of `bc90a378f855b55d0a55f014c791f4d25a5e5967`; fresh Python 3.12.14 venv; `PYTHON_BIN=<venv>/bin/python ./scripts/ci.sh`; inspect cleanliness and run `git fsck --full --strict` | PASS | All 135 tests and T0 checks pass from committed files; the cloned worktree remains clean and strict Git object validation succeeds. No live Ollama/Pi boundary is inferred. |

M3.4 is implementation-complete at T0/T1. The Ollama service is the only
installed runtime service at this boundary; no speech artifacts, GonKen
application service, audio/GPIO behavior, wake word, or power action exists.
M3.5 is the only next authorized work package.

## Continuous-workflow reconciliation — 2026-09-09

The preceding milestone-specific next-only authorizations are historical and superseded by D-060 and blueprint revision 2.0. Baseline `459f8da` rerun: 109 unit + 26 integration tests PASS, T0 PASS, on Linux x86_64/Python 3.12. No Pi acceptance is claimed. ZIP extraction lost executable bits; restored exactly from the Git index before testing, without source changes. The new generated status check requires all blueprint item IDs exactly once.

## continuation-runtime — M4/M5.1 software, 2026-09-09

`PYTHONPATH=src:. python -m unittest tests.unit.test_runtime_audio -v`: **22 tests PASS** on Linux x86_64/Python 3.12.

| Scope | Evidence | Result / limit |
|---|---|---|
| M4.1 | Every pipeline stage cancellation/error, 12 concurrent activations, late dependency, stop before dispatch, text path, transition rejection | PASS at T1; no physical adapter claim |
| M4.2 | Missing/ambiguous/exact stable identity, rate mismatch, re-enumeration/backoff, bounded frame count/queue/overflow | PASS at T1; real ALSA backend pending |
| M4.3 | 48→16kHz deterministic tones, passband preservation, alias amplitude below 1%; stereo conversion and ratio rejection | PASS at T1; Pi timing unmeasured |
| M4.3 | Real subprocess success/error/timeout/cancel/output cap; fake speech executable outputs, valid/truncated WAV, cleanup on success/error/cancel/playback failure | PASS at T1; real pinned STT/TTS and audible target tests unrun |
| M5.1 | Bounce, hold/release, indicator-before-capture and off-before-submit ordering, stuck-button cancel/inhibit, missing device/start failure | PASS at T1; GPIO permission/crash/physical LED tests unrun |

Adapters are explicit injection points, not proof of deployment wiring. M3.5 stays blocked and installer activation is unchanged.

## continuation-grounding — M5.2/M7 and text diagnostics, 2026-09-09

`PYTHONPATH=src:. python -m unittest tests.unit.test_grounding_observability tests.integration.test_text_runtime_process -v`: **17 unit + 8 integration tests PASS**, Linux x86_64/Python 3.12. Rechecked after dashboard state preservation fix.

| Area | Executed evidence | Result / boundary |
|---|---|---|
| Retrieval | Deterministic rebuild; atomic replace failure preserves old index; changed/deleted/added sources; corrupt/tampered index; symlink/size/encoding/name rejection; heading/overlap; calibration | T1 PASS |
| Grounding | No-source abstention without client call; untrusted JSON source boundary; malformed/extra-field/invalid-citation responses abstain | T1 PASS; citation validation is not entailment; real-model adversarial evaluation open |
| HTTP inference | Numeric loopback sockets with DNS/proxies/external connections forbidden; cancellation; absolute timeout; concurrent request rejection; overload; redirect refusal; bounded malformed response | T1 PASS; no kernel/Pi network-observation claim |
| Telemetry | Unknown/content field rejection; finite metric checks; registered IDs; 120 concurrent-thread records; size rotation; torn final-record recovery; corrupt-middle/symlink refusal | T1 PASS; no persistent interaction mode enabled |
| Dashboard | Real loopback HTTP routes; Host/Origin refusal; mutation routes denied; CSP/no-store; textContent rendering; transient clearing; non-loopback bind refusal | T1 PASS; connected to text coordinator only |
| CLI lifecycle | Real index build/verify/ask/abstain/doctor subprocesses; multi-line stdin/EOF; SIGINT/SIGTERM exits; categorized errors and content-free telemetry | T1 PASS |
| Synthetic smoke | `python scripts/benchmark_grounding.py --output docs/development/evidence/grounding-smoke.json` | 40/40 answerable hit@3; 20/20 out-of-domain abstentions; valid ID coverage 100%. Synthetic templated extractive mode only; no model or real-lab quality claim. |

Target gates, deployment readiness, semantic answer validation and research generalization remain open.

## continuation-support and regression repairs — 2026-09-09

`PYTHONPATH=src:. python -m unittest tests.unit.test_support_export tests.unit.test_runtime_audio tests.unit.test_m2_1 tests.unit.test_grounding_observability -q`: **60 tests PASS**.

- Four support-export cases cover exact members, redaction, content refusal, private modes, symlinks, existing output, publication race and cleanup; arbitrary health detail is discarded.
- Broad regression discovered one identity-authority failure: dashboard duplicated the product-name literal. It now consumes `IDENTITY.product_name`; the existing invariant test passes unchanged.
- Review found dropped capture frames did not advance the recording-duration bound. Captured and accepted frame counters are now separate; a regression proves overflow still stops capture at the configured duration boundary (within one bounded callback block).
- Added AGENTS.md to make continuous progression and final committed checkpoint handling discoverable to future development sessions.

## continuation-01 full regression

After the support export and regression repairs, `./scripts/ci.sh` passes all T0
checks, **153 unit tests and 34 process/integration tests (187 total)** on Linux
x86_64 / Python 3.12.14. This retains every original M2/M3 test and adds 52 tests.
The run includes real local Git → wheel → venv → immutable release activation,
installer/Ollama interruption fixtures, text CLI and loopback HTTP boundaries.
`git diff --check` and `git fsck --full --strict` succeed. Unreachable historical
loose objects are informational; no Git history was pruned. Clean-clone/archive
verification is recorded separately below when executed.
