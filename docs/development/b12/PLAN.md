# B12 responsive room appliance: current execution contract

Baseline: Library archive gonken-b11i-runtime-tool-admission.tar.bz2, SHA256
264c19bc43e49153bd390cd7ef32cf15e479d02c3f5a830459edb352fe67e428,
commit 2fabc0985db44a3660b5af3be01a4b0e3af80f1b. Clean Git and strict fsck
were checked before branching. The B11 finalization report did not enumerate
this recoverable archive. B10 has not been substituted.

Current user changes (22 September 2026): explicitly select qwen3:0.6b, the
smallest admitted roster tag; disable thinking; preserve other models as
optional; set thermostat ON=28 C and OFF=26 C on this explicit deployment;
reduce deterministic command and wake-acknowledgement latency; add bounded
local scheduled fan/sensor interactions and confirmed reboot/poweroff;
put supported command examples in README and document architecture using SVG.
"Temperature increases by two minutes" is treated as an ambiguous request for
change notifications, implemented using explicitly stated degrees Celsius.
The command parser must reject minutes as a temperature-change unit.

Implementation batches: (1) performance/default/policy alignment, (2) typed
scheduler and notification contracts in the sole environment daemon, (3) voice
and CLI integration, (4) confirmed power action and narrow authorization,
(5) current README/architecture, (6) complete affected/current regression,
clean-archive and installed-entrypoint checks. Each batch is committed and
exported before costly checks. WIP commits are not release qualification.

Invariants: no model-selected shell, no new GPIO owner, no simulated fallback
in full-real deployment, sensor-fault safe OFF, bounded scheduled work, no
persistent private transcripts, no unconfirmed host power action, no hidden
execution on this development host. Existing real fan cycle evidence remains
attributable to its logged B9 runtime and the user's observation, not this build.

Current Attempt03 registry remains authoritative for older work. New B12
requirements are tracked here and in B12_REQUIREMENTS.json without relabeling
unimplemented display/physical/lifecycle gates PASS. Missing physical evidence
does not prevent delivery of a host-tested installation candidate.

Batch 1: 85 preset/config/policy/model + 26 voice + 19 installer tests PASS.
One broader test command was terminated after 45s: an old __new__ readiness
fixture lacked the now-required cached-cue dependency and retried. Fixture was
corrected with an explicit fake cue cache; isolated voice tests complete in
0.104s. Production retry deadlines were not increased. The incomplete grouped
run is not counted as a completed suite. Default factory stop threshold changed
intentionally; custom policies still change only via the explicit preset/IPC.

Batch 2: daemon-owned monotonic automation, numeric spoken-acknowledgement receipts,
32-job/32-notification limits, finite recurring leases, no catch-up bursts,
manual-override and sensor-fault cancellation, dwell-respecting fan writes, and
bounded power safe-OFF holds. 61 affected controller/IPC/lifecycle/automation
cases PASS. Voice/CLI surfaces and power privilege adapter remain next work.
An initial test-selection typo named two nonexistent modules; it was corrected
by inspecting actual test filenames. No missing module was counted as PASS.

## B12-03 operational voice and power boundary
Implemented shared deterministic scheduler/voice/CLI routing, action-specific power confirmation,
voice acknowledgement before fixed logind calls, daemon safe-OFF preparation, bounded power audit,
and exact root-owned PolicyKit rule. Timers clear on daemon restart; no delayed power actions.
The small-model preset also bypasses the *legacy-only* model provisioning gate and delegates
model availability/qualification to the canonical roster; it does not skip required qualification.
Found and fixed a hypothetical threshold-command authorization defect with a negative regression.
New narrow command/power tests: 33; combined directly affected campaign: 105 PASS.
Power is not executed on this host. User must apply the updated installer on the target.
A real downstream defect was found before delivery: changing the effective model to
qwen3:0.6b caused the legacy 2B-only provisioning helper to reject it. Governed
models now defer that legacy-only step to the existing canonical roster step;
required model/tool qualification still runs. Explicit legacy rollback remains.
Power provisioning includes polkitd/dbus prerequisites, uses the existing writable
runtime state directory, and is ordered after environment convergence and before
voice startup. Direct voice/model and new command/power cascade: 79 tests PASS.

## B12-04 speech and safety refinement

Question capture uses conservative PCM speech endpointing: 160 ms sustained
energy and 900 ms trailing silence, with a 1.2-second minimum. Wake/probe/PTT
windows are unchanged; no-speech and continuous noise retain the bounded max.
Operational responses are compact without converting relay-command truth into
physical motion. Number-word thresholds/timers are deterministic. Hypothetical,
quoted and ambiguous fan actions are rejected. Power execution rechecks the
prepared real actuator identity and refuses root to avoid logind root semantics.

122 affected tests pass in the current source, including 14 endpoint/latency
tests and 12 spoken-number/safety cases. An earlier command selected a nonexistent
voice test module; the actual test_voice_appliance module replaced that selection.
The older policy-update wording expectation was preserved in the concise reply.
No Raspberry Pi latency or physical acceptance is inferred from host checks.

## B12-05 boundary closure

Real AF_UNIX and subprocess integration checks traverse command parsing, daemon
scheduling, sensor reports, cancellation, and power-safe-OFF preparation. Hardware
and final logind execution are injected; no physical claims result. 64 focused
tests pass, including eight real IPC/CLI process cases.

Voice readiness now binds the full effective typed configuration fingerprint.
The installed appliance manager obtains that fingerprint using the exact installed
CLI, making a same-release config change invalidate old READY and trigger restart.
Power diagnostics export only a bounded allow-listed action record. Cue caches
accept only governed canned phrases and verify WAV content against its digest.

An inline wake transcript is not automatically a complete utterance: acoustic
trailing-silence evidence is required to skip follow-up capture. A truncated
"turn fan on" cannot become immediate actuation if "after two minutes" was cut
from the window. This closes a timing false-green introduced by fast-path work.
