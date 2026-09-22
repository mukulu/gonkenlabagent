# B12 responsive room candidate: verification and handoff

## Verdict and evidence scope

The current implementation passes **972 unit tests in all 88 unit modules** and
**88 integration tests in all 14 integration modules**, with no skips, missing
cases, or duplicate selected cases. This is **1,060 distinct tests**, not a sum of
repeated narrow runs. The current discovered suite and observed case IDs match
bidirectionally in `verification/VERIFICATION.json`.

This is a deployable, host-tested **responsive room installation candidate**;
it is not a certification of an error-free system, completed 179-slot Attempt03
programme, or physical acceptance of this new commit. Check the adjacent final
archive receipt before relying on the distributed bytes. The whole-program
strict promotion gate remains intact and may correctly report NOT_READY.

## Source and provenance

Source was cold-restored from the actual Library archive
`gonken-b11i-runtime-tool-admission.tar.bz2`, not reconstructed from prose and not
silently replaced by B10. Its SHA-256 is
`264c19bc43e49153bd390cd7ef32cf15e479d02c3f5a830459edb352fe67e428`;
its commit is `2fabc0985db44a3660b5af3be01a4b0e3af80f1b`.

Product code was frozen at `06b205cfce29beb66328dcffcc5d5a44a5a3851f`.
The subsequently committed launcher-test correction
`f1fefa77e3d7cc760453f7f2fa87f04deb154d58` changes only the old README test
contract and its result log; product code is unchanged. The manifest records
source/test SHA-256 fingerprints, selectors, test identities, duration, log hashes
and relative evidence paths. Later qualification/control documents do not turn
unrun tests into PASS.

The development branch is `dev-unstable/attempt03-b12-responsive`. The original
main and existing history are not replaced, and no remote push occurred. Commits
use John Francis Mukulu <john.f.mukulu@gmail.com>. Seven intermediate full-Git
exports were cold-restored before final verification; those are recovery
checkpoints, not independent release-acceptance claims.

## Implemented current user requirements

| Requirement | Implementation and protection |
|---|---|
| Lightest admitted default | Responsive room preset selects qualified `qwen3:0.6b`, thinking false, context 2048, output 96, idle retention 10 minutes; canonical roster still qualifies it. |
| Faster wake and control | Fixed phrase cache; deterministic inline completed-command route; conservative question speech endpointing; operational intents never require model planning. |
| Real thermostat | Explicit full-real SHT31/I2C1/0x44 and active-high GPIO23, simulation disabled; requested policy migrates to ON 28 / OFF 26 while preserving valid dwell. |
| Existing thermostat repair | Early current-daemon reconciliation before model preparation, late candidate activation, configuration-bound restart, command-truth diagnostics and selected-model admission retained from B11. |
| Delayed and recurring actions | Environment-owner monotonic jobs for fan ON/OFF, finite runs/cycles, sensor reports and temperature-rise notices. No shell/cron/GPIO second owner. |
| Spoken delivery | Numeric sensor notices are spoken by the existing idle voice owner and acknowledged only on successful playback; stale notices expire rather than accumulating indefinitely. |
| Reboot / shutdown | Deterministic action-specific confirmation, expiry/session/replay protection, completed audio acknowledgement, same-daemon safe-OFF hold, fixed logind methods, narrow PolicyKit, bounded content-free audit. |
| Privilege lifecycle | Managed power rule is installed and removed by exact-content checks; altered administrator rules stop destructive uninstall. Installed sidecar works without source PYTHONPATH. |
| Accessible instructions | README contains 35 voice and 54 terminal examples; parser tests verify them. Current architecture/PRD and three native, accessible SVGs do not imply future display software exists. |

The request's temperature-rise example used a time unit where a temperature
change was intended. The implemented supported form is **two degrees Celsius**;
ambiguous timing or missing numbers ask for clarification, never silently act.

## Tests and reproducible commands

Host: Linux x86_64; Python 3.13.5 with an isolated locally provisioned build-test
venv. `host-toolchain.json` records installed tool versions. No model weights,
physical SHT31, GPIO relay, microphone, speaker, power action or display was used
on this host. Integration tests exercise real subprocess/AF_UNIX boundaries with
injected hardware, network/model and final logind adapters.

From a suitable local test environment:

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=src:.
./scripts/ci.sh --phase t0
./scripts/ci.sh --phase unit
./scripts/ci.sh --phase integration
./scripts/ci.sh --phase speech-lifecycle
./scripts/ci.sh --phase release-lifecycle
python3 scripts/current_state.py --check
python3 scripts/release_readiness.py --validate
```

The current session used the same bounded test runner in smaller selections;
all exact selectors and logs are preserved. Release lifecycle cases were split
into bounded groups rather than repeating a previously timed-out whole module.
The selected module/case durations sum to **85.192 seconds**, not the duration of
this development session or a Raspberry Pi performance measurement.

The test fixtures challenge wrong model/qualification, legacy 2B-only gate,
old process/config readiness, invalid temperatures/timer bounds, booleans/NaN,
late/mismatched/replayed confirmation, quoted/negative/hypothetical actions,
failed actuator writes, sensor faults, stale numeric notices, slow/failed audio,
missing installed imports, permission denial, policy modification, timer
cancellation/expiry, immutable release mutations and false-success installer
summaries. No physical acceptance follows from their PASS results.

## Discovered defects and earlier failed runs

Original failure/timeout logs are retained outside the selected PASS accounting.
The source and README repairs were tested before counting replacements:

* Readiness cache test used an incomplete fake that retried indefinitely; give the
  fixture its actual required cache dependency. Production retry bounds were not
  increased. Only uncertain work was rerun.
* Legacy PTT fixture did not have a brain, support membership missed new power
  diagnostics, doctor mocks missed configuration, and sensor fixtures omitted
  validity. Adapter compatibility or fixtures now represent the actual contract.
* Legacy CLI default test still expected the old 2B model; the explicit B12 small
  model default is tested instead.
* An old README test required remote-main installation. B12 is an exact local
  candidate, not published main: its replacement verifies the correct archive,
  one-command wrapper, exact-commit wording and Bluetooth pass-through. The
  launcher process and source-default tests remain unchanged.
* Conceptual humidity questions were mistaken for live readings. General
  conceptual questions now route to conversation, after action-negation guards;
  direct room queries remain deterministic.
* An inline transcript could be truncated before its time qualifier. Acoustic
  trailing-silence evidence and syntax now jointly determine completion.
* A previously installed managed power policy would survive uninstall. Its exact
  payload now has a shared installed sidecar and explicit removal tests.
* The old 2B-only provisioning helper rejected the new lightweight model. Governed
  models now delegate availability and qualification to the canonical roster;
  required model qualification is not bypassed.

Mistyped test-selector names and a nonexistent example probe flag were caught,
corrected from actual parsers/files, and never counted as passing checks. The
selected final launcher failure has an explicit `superseded_by` link to the
passing corrected run; the original manifest remains FAIL.

## Mandatory review passes

**Completeness:** current requested lightweight, thermostat, timers, power,
README and SVG scope is implemented and host-tested. Broader unfinished Attempt03
items are preserved in CURRENT_GATES; none disappear behind the candidate label.

**Consistency:** real actuator identity is distinct from observed fan motion;
28/26 supersedes the prior valid 28/25 only through the explicit requested preset.
Default model and admission agree. Time uses the Pi clock; the installer does not
silently change its timezone. Model answers do not authorize power or raw GPIO.

**Non-regression:** the complete current unit/integration corpus passes, including
installed maintenance, release build/activation/reinstall, software rollback
switching, speech lifecycle, environment polling/voice and ordinary support.

**False-green:** case-by-case coverage, fingerprints and hashes prevent old logs,
missing tests, stale READY, optional alternate failure, unchecked write success,
or simulated hardware from satisfying unrelated claims. README tests validate
both exposed examples and unsupported-feature boundaries.

**Executability:** parser examples, installed sidecars, wheel/release builds,
permissions and shell/TOML/JSON/Python syntax are exercised. Native SVGs were
rendered and inspected, with no embedded scripts, remote assets or font files.

**Evidence/privacy:** target raw transcripts/credentials are not copied into this
release's new evidence. Private voice contents are not added to operational
journals/support. Fixed acknowledgement cache is limited to governed canned
phrases, not arbitrary answers. Historical tracked source retains its existing
private-development provenance; no redistribution permission is granted.

**Continuation/package:** commits and recovery archives contain the application,
not only reports. Final bytes must be independently extracted and checked by the
adjacent delivery receipt. Local sandbox storage is not an indefinite retention
guarantee; retain the actual code-bearing archive.

## Remaining programme scope and limitations

No physical B12 latency measurements are claimed. Wake still requires microphone,
speech recognition and audio routing. The smallest admitted model trades answer
quality/capability for size; 96 tokens deliberately limits response length. Typed
local actions remain independent of its factual reliability.

Schedules are memory-only, expire, and are discarded on daemon restart, reboot or
update. Notices wait for an idle voice path and expire if stale. This is not a
persistent alarm clock, general natural-language automation engine or arbitrary
scripting service. Fan schedules obey dwell and safe-sensor state; automatic
policy is restored explicitly after a manual override when needed.

Physical logind authorization/inhibitors, audio acknowledgement, restart/no-login,
actual fan motion, sensor quality and deployed latency must be observed on the
Pi. No old physical-PASS report is required by the installer; current readiness
and device checks still apply. The earlier observed fan cycle belongs to its
logged B9 runtime, not to B12 by inheritance.

Late whole-system semantic rollback (including mutable config, model stores and
OS dependencies), remaining legacy removal/currentness validators, and the
OSOYOO presentation/TUI/touch/driver implementation remain open. In particular,
this archive does not implement `gonken-agent console` or an on-screen keyboard.
The architecture SVGs describe this build, not nonexistent future components.

**Next action:** qualify and retain the adjacent exact B12 archive, run its
`./install-room-appliance.sh` on the already wired Pi, and continue dependency-ready
Attempt03 work from this full-Git source. The next core engineering tranche is
46.5.3 late semantic rollback; do not reconstruct from CKPT45 or discard B12.
