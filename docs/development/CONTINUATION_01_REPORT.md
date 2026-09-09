# GonKenLab Agent — Continuation 01

## Outcome

The supplied M3.4 checkpoint was continued through multiple independent work packages.
The one-item-per-session restriction is removed, status reporting is reconciled, and
the project now has an executable grounded text diagnostic path with a live read-only
dashboard and content-free telemetry. All work is committed on
`dev/bootstrap-rearchitecture`; the portable checkpoint tag is
`checkpoint/continuation-01`.

This is a private development checkpoint, not a completed M9 release candidate.
Earlier speech and physical deployment requirements remain open even though later
software components are implemented. The checkpoint name deliberately does not imply
that every milestone before M7 or M9 is complete.

## Diagnosis and workflow correction

The checkpoint's Git history, implementation and test matrix support M3.4 completion
at the host tier. The old implementation-status document was not wholly stuck at
M2.3: it contained later completions, but also listed completed items under “Not
Started” and repeatedly authorized only the next sub-item. The repository master
blueprint explicitly required one work package, a commit, and a stop per session.
The supplied feasibility blueprint instead recommends proving layers before integration;
it does not impose a conversation-sized stopping rule.

`MASTER_BLUEPRINT.md` revision 2.0 and `AGENTS.md` now require continuous progression:
implement and verify a coherent item, update evidence, commit, then continue to the
next dependency-ready item. A genuine failed gate blocks its dependants while independent
work can proceed. Final regression runs and committed portable handoffs remain required.

`MILESTONES.json` covers every core implementation sub-item. It generates the current
status table, and CI rejects missing items or drift. Software status, target acceptance,
evidence and remaining work appear separately. Previous detailed chronology remains
available in Git and the test matrix.

## Implemented and verified

| Area | New work | Remaining boundary |
|---|---|---|
| M4.1 | Sequential coordinator, explicit states, bounded activation queue, cancellation, signal cleanup, categorical health | Physical/service adapters and Pi evidence |
| M4.2 | Stable device selection, ambiguity/rate checks, re-enumeration/backoff, bounded PCM queue and frame accounting | Real ALSA capture/playback integration and hotplug tests |
| M4.3 | Anti-alias 16/32/48→16kHz PCM processing, bounded subprocesses, Whisper/Piper adapters, validated temporary WAV lifecycle | Accepted real speech artifacts, audible output and Pi performance |
| M5.1 | Debounced hold/release controller, indicator ordering, stuck-button cancellation and cleanup | GPIO adapter, permissions and physical/crash LED behavior |
| M5.2 | Numeric-loopback Ollama transport; no DNS, proxy, redirect, cloud or model-selected tool execution in core text mode | Kernel-observed Pi offline behavior and complete voice path |
| M7.1–M7.2 | Safe deterministic BM25 index, calibrated support threshold, stale/corrupt rejection, source IDs, no-support abstention, model-response validation | Real-lab calibration/evaluation; factual entailment and real-model adversarial tests |
| M7.3–M7.4 | Strict content-free rotating telemetry; integrated read-only dashboard; optional transient interaction text | Persistent research logging remains disabled; physical runtime integration |
| M7.5 | Frozen synthetic retrieval benchmark, reproducible JSON metrics and fixture hashes | Representative lab and grounded/ungrounded model/STT/RAM/thermal experiments |
| M8.1 | Categorical package doctor and allow-listed redacted support ZIP | Full target service, artifact, resource and hardware diagnostics |
| M9 documentation/handoff | Tested text guide, complete status, retained evidence and portable Git checkpoint procedure | Deployment onboarding, full physical release campaign and public licensing |

Available commands include `index build`, `index verify`, `ask`, `run --text-only`,
`dashboard`, `doctor`, and `support`. The text session can share its live metrics with
the dashboard. `--extractive` explicitly returns a retrieved excerpt without invoking
Ollama; omitting it uses the configured local model. Plain `run` still fails closed for
voice activation. Existing M3 provisioning behavior is preserved.

## Verification evidence

Baseline `459f8da`: **109 unit + 26 integration tests = 135 passing**.
Final software commit `129aad0`: **154 unit + 35 integration tests = 189 passing**,
including all original tests and 54 additional tests. The full CI entrypoint passed
from a no-hardlink clean clone with a fresh Python 3.12.14 virtual environment on Linux
x86_64; no extra runtime/test dependencies were installed.

The suite includes local Git-to-wheel-to-venv release activation, interruption/rerun
fixtures, cancellation at each pipeline stage, concurrent activation rejection,
resampling spectral checks, temporary audio cleanup, corpus safety/corruption tests,
real loopback HTTP tests, dashboard access/privacy tests, subprocess CLI tests,
SIGINT/SIGTERM exit checks, telemetry rotation and support-export redaction.

Review and regression runs found and fixed four concrete issues in the new work:
product-name duplication; overflow frames not counting toward capture duration;
malformed calibration structures escaping categorical validation; and cancellation
of delayed HTTP/1.0 response bodies after connection detachment. Regression coverage
is retained. `git diff --check`, generated status validation and strict Git object
validation pass. A targeted new-code credential-pattern scan found no matching keys;
this is a limited scan, not a guarantee about all possible secret formats.

The synthetic retrieval smoke check achieved **40/40 hit@3, 20/20 unsupported-query
abstentions and 100% valid-source-ID coverage**. These are invented equipment documents,
templated positives and out-of-domain negatives in extractive mode. They establish
regression behavior, not real-lab accuracy, semantic entailment, model safety or research
generalization. Results and their limitations are recorded in
`evidence/grounding-smoke.json`.

## Open gates and efficient next work

1. **M3.5 speech chain:** resolve the already-blocked runtime/voice policy; verify
   immutable Whisper/Piper sources, artifacts, checksums, dependency closure and real
   STT/TTS smoke outputs. No placeholder pins or claimed speech results were introduced.
2. **Physical adapters and service:** connect the tested audio/PTT contracts to actual
   ALSA/GPIO, then complete M6 service installation/recovery and M3.6 installer readiness.
   Missing peripherals must remain diagnosable and recoverable.
3. **Real-lab evidence and operations:** replace synthetic acceptance substitutes with
   reviewed lab development/evaluation data, run real-model adversarial/quality checks,
   extend target diagnostics and complete update/uninstall workflows.
4. **Pi acceptance:** execute the full image/install/reboot/hotplug/offline/thermal/
   power-loss campaign. No Pi, audio or GPIO device was available here. Close M9 only
   from the required evidence and licensing decisions.

Proceed through as many ready items as practical in each session. Do not repeat the
completed baseline work or stop merely because one sub-item passes. Keep blockers and
partial states explicit. No approval is requested merely to cross milestone boundaries.

## Resume and Git handoff

Extract the private checkpoint and read `AGENTS.md`, the implementation status and
`TEXT_RUNTIME_GUIDE.md`. The guide contains tested local commands. Then inspect:

```bash
git status --short --branch
git log -8 --oneline
git show --no-patch checkpoint/continuation-01
python scripts/milestone_status.py --check
./scripts/ci.sh
```

The inherited Git `origin` points to an earlier temporary checkout. Do not push to that
path. The repository's onboarding/bootstrap documents identify the intended upstream
as `https://github.com/mukulu/gonkenlabagent.git`. If that remains the correct private
maintainer repository, set it explicitly and push the development branch and this tag:

```bash
git remote set-url origin https://github.com/mukulu/gonkenlabagent.git
git push -u origin dev/bootstrap-rearchitecture
git push origin checkpoint/continuation-01
```

No remote push, merge, public release, package redistribution or target service activation
was performed. Keep this branch for development; review the remaining gates before any
merge intended to represent a release candidate. No release-candidate or semantic-release
tag was created.
