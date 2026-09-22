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
