# V09 Post-Checkpoint-34 Reliability-First Blueprint

**Status:** internal reliability checkpoint; not a Raspberry Pi release candidate.

**Authority:** this document supersedes the checkpoint-34 "final convergence" handoff boundary. Checkpoint 34 remains valuable host evidence, but the next user-facing Pi candidate is blocked until the host/target-shadow gate below is complete.

## 1. Forensic Chronology

| Checkpoint | Evidence class | What changed | Quality lesson |
|---|---|---|---|
| 23 | Target dependency and identity | `python3-libgpiod` was present for system Python but not for the consuming venv; operator group membership also blocked environment CLI. | Test each prerequisite in the exact interpreter, user, service and IPC context that consumes it. |
| 24 | Dirty Python environment | Broad `system_site_packages` exposed unrelated system package contamination. | Dependency-boundary repairs need dirty-target fixtures, not only clean host fixtures. |
| 29-30 | Historical-release coupling | New release validation and cleanup interacted with stale historical releases after current activation. | Normal runtime is current-release authoritative; stale history is update/rollback evidence only. |
| 30 | Planned reboot semantics | I2C enablement looked too much like fatal failure when reboot/resume was intended. | `PAUSED_REBOOT_REQUIRED` is a state, not an error. |
| 31-32 | Immutable release mutation | Post-seal Python execution created runtime cache/digest failures and same-commit rerun dead ends. | Executable checks occur before sealing; runtime writes belong outside authoritative release payload. |
| 32-33 | Transport preference as blocker | Bluetooth failure stopped progress despite deterministic AIRHUG USB capture/playback evidence. | Gate on usable audio capability, not preferred transport. |
| 33 | Late GPIO discovery | Wake GPIO ambiguity appeared only after final service readiness waited. | Deterministic non-actuating hardware identity must be checked before long readiness waits. |
| 34 target evidence | GPIO alias ambiguity | `/dev/gpiochip0` and `/dev/gpiochip4` both reported the same RP1 identity for GPIO17/22/23/27 and were treated as separate ambiguity. | Canonical hardware identity must deduplicate true device-node aliases before line ambiguity decisions. |

## 2. Multidisciplinary Council Matrix

| Role | Risk focus | Required gate |
|---|---|---|
| Raspberry Pi 5 platform / kernel GPIO / libgpiod / udev engineers | gpiochip numbering, duplicate line names, aliases, permissions and API drift | canonical gpiochip manifest, alias fixture, distinct-duplicate fail-closed fixture |
| Debian / Python packaging / venv engineers | package visibility, dirty system packages, source-tree-only imports | installed-style interpreter tests, dirty-host matrix, service-venv prerequisite checks |
| Python runtime / filesystem engineers | bytecode/cache writes, symlink cache deception, source/config drift | read-only release execution and adversarial payload tests |
| systemd / Unix identity engineers | wrong user/groups, user-session dependencies, stale service files | no-login service context, group convergence, managed predecessor hashes |
| PipeWire / WirePlumber / ALSA / BlueZ engineers | interactive audio works while headless service audio fails; transport preference over capability | service-user audio route smoke, USB/Bluetooth fallback matrix |
| Speech / Ollama engineers | binaries and models present but not executable in runtime context | service-user Whisper/Piper/Ollama transaction checks |
| Sensirion / I2C / metrology engineers | sensor visibility confused with valid repeated measurements | CRC, 100-read commissioning, range/stale/error statistics |
| Relay / control-safety engineers | unsafe fan state, wrong owner, speed-control overclaim | environment-service-only GPIO23 ownership, safe-OFF restart/reboot/fault tests |
| Installer / release / rollback engineers | current success invalidated by stale history or cleanup | model-based same-commit/update/rollback/reinstall campaign |
| QA / SRE / chaos / false-green reviewers | large green suites hiding unrun target states | bounded case accounting, support-bundle replay, false-green checklist before handoff |
| Security / privacy engineers | least-privilege erosion, secret/content leakage | content-minimized support scans, no raw audio/transcript evidence by default |
| Human-factors / operator-runbook engineers | misleading READY states and unclear recovery | actionable error taxonomy and explicit profile criticality |

## 3. Capability Criticality Matrix

| Capability | Default criticality | Blocks generic core install | Blocks feature commission | Degraded behavior |
|---|---|---:|---:|---|
| Current release integrity | Required | yes | yes | fail closed |
| Core service and current readiness | Required | yes | yes | fail closed |
| Ollama/model | Required for conversational mode | yes | yes | truthful unavailable if optionalized later |
| STT capture and TTS playback | Required for voice-ready install | yes | yes | terminal/text mode only if explicitly supported |
| USB/wired audio | Route option | no if another deterministic route works | no | use selected working route |
| Bluetooth audio | Preferred optional route | no unless `--require-bluetooth` exists and is selected | yes for Bluetooth feature | warn and use USB/wired route if healthy |
| Wake word | Required for requested wake-word product | yes | yes | explicit manual/text fallback only if configured |
| Wake LED GPIO22 | Optional indicator | no | no | degraded warning, fail-safe OFF |
| Recording LED GPIO27 | Optional indicator | no | no | degraded warning, fail-safe OFF |
| PTT GPIO17 | Optional alternate input when wake word is primary | no | PTT only | wake/text remains usable |
| Relay GPIO23 | Required only for real-fan/full-real profile | no | real-fan profile | environment disabled/simulated safely |
| SHT31 on `/dev/i2c-1` | Required only for real-sensor/full-real profile | no | real-sensor profile | simulated sensor or environment disabled |
| Environment service | Required for environment control | no for ordinary voice | yes | environment intents refuse truthfully |
| Dashboard | Optional | no | no | CLI/support remain available |

## 4. Installer State Model

Each step must persist: ID/version, consumer, read-only discovery probe, action, postcondition, mutable paths, forbidden release paths, side effects, retry rule, invalidation rule, reboot semantics, failure code, criticality, and support fields.

Allowed states are `UNASSESSED`, `PREFLIGHTED`, `ACTION_NEEDED`, `ACTION_APPLIED`, `VERIFIED`, `PAUSED_REBOOT_REQUIRED`, `DEGRADED_OPTIONAL`, `BLOCKED_REQUIRED`, `INTERRUPTED`, `NEEDS_MANUAL_REVIEW` and `COMPLETE`.

`INSTALLATION_COMPLETE` may only be derived from fresh current postconditions. A stale state record cannot satisfy a changed release, profile, kernel, service user, gpiochip manifest, audio route or environment profile.

## 5. Target Hardware Manifest Schema

The target-shadow fixture must be sanitized and non-actuating. Required top-level fields:

```json
{
  "format": "gonken-target-hardware-manifest-v1",
  "captured_at": "ISO-8601",
  "commit": "git-sha",
  "raspberry_pi": {"model": "", "revision": "", "kernel": "", "os_release": ""},
  "python": {"version": "", "libgpiod": ""},
  "gpiochips": [
    {
      "path": "/dev/gpiochipN",
      "stat": {"kind": "char", "major": 0, "minor": 0},
      "sysfs_realpath": "",
      "chip_info": {"name": "", "label": "", "num_lines": 0},
      "line_names": {"17": "GPIO17", "22": "GPIO22", "23": "GPIO23", "27": "GPIO27"},
      "canonical_chip_id": "",
      "alias_paths": []
    }
  ],
  "i2c": {"devices": [], "sht31_targeted_probe": {"bus": "/dev/i2c-1", "address": "0x44", "status": ""}},
  "audio": {"capture_routes": [], "playback_routes": [], "selected_route": null},
  "bluetooth": {"controller": "", "devices": []},
  "systemd": {"version": "", "units": {}},
  "identity": {"service_users": {}, "operator_groups": []},
  "release": {"current": "", "installer_state": ""}
}
```

## 6. Dirty-State And Target-Shadow Matrix

Before another Pi candidate, host/target-shadow tests must replay at least: clean install, old checkpoint active, partial installer state, stale symlink/journal temp state, corrupt historical releases, same commit after service runtime, same commit after support collection, old managed systemd units, operator missing group, I2C disabled then enabled with reboot pause, duplicate/alias gpiochips, true duplicate header controllers, USB-only audio, Bluetooth busy with USB available, audio hotplug/re-enumeration, SHT31 absent/present, disabled/simulated/full-real environment profiles, low disk, interrupted model finalization, and service restart failure.

## 7. Host/Target-Shadow Gate Before Any Pi Candidate

No user-facing `RELEASE_CANDIDATE` may be packaged until these host-verifiable gates pass: full unit accounting, deterministic integration accounting, release lifecycle case accounting, speech/Ollama lifecycle accounting, model-based installer properties, dirty-host matrix, target-shadow replay of checkpoint 23-34 defects, duplicate RP1 alias fixture, optional LED/PTT non-blocking core wake behavior, required GPIO23/SHT31 profile blocking, read-only release/write audit, installed-style import/execution, curl/local equivalence, service-unit upgrade compatibility, synchronized control docs, false-green review, and exact extracted-archive verification.

## 8. False-Green Review

Every checkpoint handoff must answer whether success could be false because system Python passed while the service venv failed; root passed while service user failed; interactive audio passed while no-login service audio failed; Bluetooth failed while USB was sufficient; optional LED/PTT blocked core service; gpiochip paths were aliases; kernel update changed numbering; runtime mutated current release; readiness came from an older commit; garbage collection failed after activation; state was stale; source-tree imports masked packaging; mocks hid native API differences; support came from the wrong release; aggregate timeout hid unrun cases; final ZIP differed from tested workspace; curl resolved a different commit; fan/sensor physical success was inferred from command success.

## 9. Work Packages

1. **WP-A:** this control-plane reconstruction plus synchronized status documents.
2. **WP-B:** current-release/write-audit/read-only execution hardening.
3. **WP-C:** canonical hardware identity and target-probe fixture replay.
4. **WP-D:** audio capability abstraction and no-login service-user route tests.
5. **WP-E:** installer DAG/state taxonomy and failure-code localization.
6. **WP-F:** service, identity, config/profile and runtime-dir closure.
7. **WP-G:** SHT31/environment commissioning.
8. **WP-H:** fan/relay safety.
9. **WP-I:** wake/STT/TTS/environment transaction closure.
10. **WP-J:** dirty-state/model-based/fault-injection campaign.
11. **WP-K:** exact archive qualification.
12. **WP-L:** real Raspberry Pi release-candidate campaign.
13. **WP-M:** stable release only after WP-L evidence passes.

## 10. Current Checkpoint

This checkpoint completes part of WP-A and starts WP-C by adding canonical gpiochip identity evidence and alias deduplication to the shared resolver/preflight. It remains host-only. Physical Raspberry Pi acceptance, `INSTALLATION_COMPLETE`, SHT31/fan/wake/voice and update/rollback/reinstall remain open target gates.

**Continuation instruction:** Continue from the recorded reliability checkpoint and execute the next dependency-ready batch. Preserve all verified evidence, rerun only uncertain/interrupted checks, and do not produce a user-facing Raspberry Pi candidate until the host/target-shadow release-candidate gate is completely satisfied.
