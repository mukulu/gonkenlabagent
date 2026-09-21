# B11 target-evidence convergence

Baseline: B10 `b275fa780890300af12828fce9d2ab295c034bcf`, unchanged history.
Current work branch: `dev-unstable/attempt03-b11-convergence`.

## Evidence and scope

FACT: the latest failure bundle identifies qwen3.5:0.8b TOOLS / HTTP 500.
UNLOAD was cleanup and succeeded; it is not the failing operation. Qwen3:0.6b
passed inference/tools; LFM inference passed but its tool result failed validation.
The underlying Ollama server cause remains unresolved; no runtime-pin guess is made.

FACT: B10 applied the real environment configuration before model prerequisites,
but deferred restarting the current environment until after global activation.
On the model error the old B9 daemon therefore continued its simulated actuator.

TARGET OBSERVATION: the supplied manual-recovery transcript identifies the running
B9 interpreter after restart, real SHT31/I2C1/0x44 and real libgpiod/GPIO23,
automatic mode, 28 C ON / 25 C OFF and 60-second dwell. It records automatic ON
18:09:33, OFF 18:10:33 and the `gonken-environment` GPIO consumer. The user confirms
physical motion/stopping. This is scoped evidence for that runtime/configuration,
not B10 installation completion or B11/reboot/voice/display acceptance.

## Decisions and dependency-ready batches

1. Enact Attempt03 section 11.5: require default/selected tools, mark an installed
   alternate TOOL_INCOMPATIBLE rather than aborting for its tool-only error.
   Keep identity, inference, unload and residency checks; deny unqualified tools.
2. Reconcile a compatible existing current environment independently before model
   provisioning, without moving global release activation early. On a fresh target
   without current runtime, defer this optional reconciliation to activation.
   Preserve the user's valid 28/25 policy; never terminate arbitrary GPIO owners.
3. Expose acknowledged relay commands, GPIO ownership and bounded transition/error
   events. Preserve controller/command/physical observation distinctions.
4. Make changes-only watch ignore raw sensor jitter while reporting control,
   quality, configuration and error changes; keep ordinary sample watch available.
5. Run affected and complete current tests, qualify the exact archive, save actual
   source and report remaining blueprint work without manufacturing acceptance.

Raw target bundles/transcripts remain outside Git. Only diagnostic metadata and
synthetic regression cases are exported. Host mocks are not physical evidence.

Execution: implementation in progress, no stable-release promotion.

## B11A outcome

Seven targeted cases replay alternate-tool HTTP/semantic errors, selected/default
failures, network/auth failures and unsuccessful unload. All pass, with the existing
roster progress/manager suites: 22 tests. Before repair, three of the original six
new cases failed. Optional tool rejection has a separate incident list and
TOOL_INCOMPATIBLE status, while selected/default qualification and residency remain
strict. No model binary/version was changed and the server-side cause is not claimed.

## B11B outcome

Added an explicitly scoped existing-thermostat reconciliation phase before model
provisioning. It checks current release integrity and installed service contract,
parses configuration without actuation, restarts the sole environment service,
checks real-backend health and converges mode through versioned IPC. It preserves
thresholds/dwell, records invocation/config/candidate identity and does not move
current. No-current/old-runtime failure is reported as deferred/degraded; final
candidate commissioning remains mandatory. No unrelated GPIO process is killed.

Before any restart, an atomic RUNNING record preserves interruption state and
unsafe destinations are rejected. Current identity/config changes invalidate the
receipt. 27 reconciliation/order/wrapper tests passed initially. After hardening,
13 reconciliation/installed-import tests and 13 real-profile/policy tests passed.
One larger grouped rerun was INTERRUPTED by its outer 30-second limit after 32
case markers; it is not counted as a complete suite. No child survived. Narrow
subsets were isolated, and the final complete-suite campaign will supersede it.

## B11C command truth and passive observation

GPIO diagnostics now report exclusive claim/consumer, last acknowledged command,
actual write/request error counters and no observed-motion fiction. Repeated equal
commands retain ownership without repeated GPIO writes. Failed writes and released
lines expose unknown current commanded state instead of synthesizing OFF success.
Polarity type is strictly validated at the adapter boundary as well as config.

Service snapshots distinguish controller desire, acknowledged relay command, last
request/result and command reason/time/counters. State changes and rate-bounded
write failures enter a content-free, allowlisted, bounded asynchronous journal
queue. A blocked journal cannot stall the controller; event loss is explicit.

Health/status reads no longer call controller.tick and hence cannot create an
unapplied control transition. They project staleness without mutating the filter,
dwell, state or GPIO. Changes-only watch ignores raw temperature/humidity jitter
and counters; it reports control/quality/error/backend/config transitions. Normal
watch still shows samples. The old test expecting the ambiguous `fan=off` display
was changed to assert desired/commanded/unobserved labels. 58 focused tests PASS.

## B11D downstream model-authority convergence

The final installer summary contained a second, unconditional all-alternate-tools
requirement. It now uses the same required default/selected capability predicate
as provisioning, preserves all three identity/inference/unload requirements, and
reports optional tool incompatibilities explicitly. No selected-model capability
is silently downgraded. The installation roster manifest must match the canonical
model catalog before any API call. Installed maintenance uses that same catalog
sidecar. 25 focused model/summary/installed-maintenance tests PASS; this closes the
newly reachable false-red gate rather than merely moving the original failure.

## B11E exclusive owner and service-stop safety

Source review found that default SIGTERM could bypass Python cleanup and a second
server could unlink a live authority socket. The main daemon now unwinds through
safe-OFF cleanup on SIGTERM/SIGINT (real subprocess signal tests, fake hardware).
Shutdown records the OFF acknowledgement or failure before releasing the line.
The socket server holds an exclusive lifetime lock, refuses live predecessor
sockets even without a lock, rejects symbolic/non-socket paths, recovers only
ECONNREFUSED stale sockets and never unlinks a replacement socket during cleanup.
Lock files remain to avoid inode replacement races. Bind failure releases the lock
without constructing a second hardware cleanup path. 46 lifecycle/adapter/
observability tests PASS, including actual process termination and restart.

## B11F canonical evidence closure

The canonical collector now recognizes allowlisted JSON relay journal events as
well as older code= records, retains at most 40 typed actuator transitions and
labels them current-boot history, not current readiness. Release/configuration
hashes and PID bind new events. Unknown keys, invalid enums/identities, duplicate
JSON keys and non-finite numbers are excluded. Passive environment diagnostics
retain acknowledged-command/unknown-state, ownership and error counters without
copying raw conversation or inventing physical observations. Existing thermostat
reconciliation is a separate historical phase member, never a live-ready claim.
35 focused evidence/journal/support tests PASS. The new member was added to the
exact-member regression expectation; privacy canaries remain excluded.
