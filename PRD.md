# GonKenLab Agent: current product requirements

**Current scope:** B12 responsive, local room appliance. This replaces the root
historical Pi-Genius concept as the current product overview. Earlier wording is
preserved in Git history, not an instruction to restore cloud fallback, an animated
800x480 face or an old wake phrase. [Current architecture](docs/ARCHITECTURE.md),
[command catalogue](README.md), and [task dispositions](docs/CURRENT_STATE.md)
provide implementation detail and explicitly open work.

## Operating contract

The wired Raspberry Pi 5 uses local wake-word voice interaction, Whisper recognition,
Piper speech and a qualified small Ollama model. Standard fan/sensor/time/policy/timer
commands bypass general inference. Normal operation requires no cloud service.
Installation may obtain pinned dependencies and models; an offline installation
requires those assets in advance. The supported wake phrase is **GonKen**.

The explicit real-room preset selects `qwen3:0.6b`, disables thinking and uses a
short answer/context budget. It migrates the requested thermostat to 28 C ON and
26 C OFF, retaining valid dwell. Older model variants can remain admitted alternatives
without blocking the default merely because optional tool capability fails.
Required default/selected qualification cannot be bypassed by a green process flag.

## Hardware and state authority

The environment daemon alone owns SHT31 I2C1/0x44 and the active-high GPIO23 relay.
CLI, voice, scheduler and future display clients use typed operations. Real-backend
failure never silently becomes simulated success. Sensor freshness, CRC, valid-sample
recovery, hysteresis and minimum dwell are enforced independently of the model.
Room-fan power is not Pi Active Cooler control, speed control, RPM or observed motion.

Timers are bounded, boot-scoped and enumerated, with finite recurrence leases,
manual intervention/cancellation semantics and no missed-event replay. Numeric
reading notifications are spoken by the voice owner when available. Model text
never creates arbitrary jobs, shell commands or raw GPIO actions.

## Privileged operations and privacy

Reboot and poweroff require direct user intent, short-lived same-session matching
confirmation, one-shot authorization, completed acknowledgement audio, environment
safe-OFF preparation and a fixed narrowly authorized logind request. Negation,
hypotheticals, quoted instructions, wrong confirmation and replay do not authorize
execution. Inhibitors remain effective. No remote network control endpoint is added.

Transient captured audio and arbitrary conversations are not persisted as logs.
Only governed canned cue audio can be cached. Support/failure collection shares one
`.tar.bz2` engine that retains necessary hardware/runtime facts but excludes private
conversation content and credentials. Code releases are immutable; mutable policy,
runtime state, cue cache and support output live outside the sealed release.

## Quality and release claims

Known failure paths become deterministic negative tests. Unit, process/IPC,
installer/lifecycle, package extraction and documentation checks are recorded
against exact source. No unrun physical gate is PASS. A host-tested installation
candidate may be delivered without waiting for an older physical acceptance report;
actual deployment must still validate present configuration, permissions, devices
and semantic capability readiness. No release is guaranteed error-free.

The completed implementation must be self-describing and resumable through full
Git history, immutable recovery exports, test evidence and a precise next action.
WIP commits preserve effort; only corresponding checks justify promotion. Broad
checks must be bounded and preserve completed results across interruption.

## Explicit remaining scope

The optional OSOYOO/HDMI/SSH live console, display driver/touch/physical acceptance,
remaining legacy reachability/removal and full mutable-dependency semantic rollback
remain in the Attempt03 registry. The current diagrams describe the shipped core,
not those future implementations. New capability claims require corresponding
code, tests, documentation and target evidence where inherently physical.
