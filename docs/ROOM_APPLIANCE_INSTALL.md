# Wired room-appliance installation: B12 responsive candidate

B12 continues the recovered B11 application, not an older source reconstruction.
It targets the existing SHT31/I2C1/0x44 and active-high GPIO23 room-fan wiring.
The current [README](../README.md) is the primary installation and command guide;
the [architecture](ARCHITECTURE.md) explains exact ownership and safety boundaries.

## Install the extracted commit

As the normal administrator in a clean, newly extracted `gonkenlabagent/`:

```bash
./install-room-appliance.sh
```

This selects `--local-checkpoint --environment-profile full-real
--environment-mode automatic --appliance-preset responsive-room`. It does not
fetch remote `main` instead of the package you are testing. The preset selects
`qwen3:0.6b`, no thinking, 2,048 context tokens, 96 output tokens and 10-minute
idle retention. It explicitly changes the thermostat to ON=28 C / OFF=26 C,
preserving valid existing minimum dwell (factory 60 seconds ON/OFF).

Running it authorizes real room-fan power control and the separately confirmed
power-command capability. First startup remains safe OFF. No previous HIL/PASS
file is a runtime prerequisite. Invalid config, missing permissions/devices,
unqualified required model or failed current semantic readiness still cannot
be represented as installation success. Simulation is not a fallback for failure.

A maintenance rerun with `--appliance-preset none --environment-mode preserve`
retains custom model/threshold/mode settings. It does not revoke an existing power
policy; uninstall removes the exact managed rule. `--preflight-only` does not
install or start hardware. `--model-provision-mode preseeded-offline` requires all
pinned dependencies and model files to be pre-provisioned; it is not a download bypass.

Do not reseat wiring while powered. Do not run `gpioset` alongside the daemon.
The Pi Active Cooler is separate; the ELUTENG fan has manually selected speed and
software-controlled power only. Existing real-fan observation is evidence for its
recorded earlier release, not automatic acceptance of this new candidate.

## Confirm selected configuration and runtime

```bash
gonken-agent llm status --json
gonken-agent config show --effective --json
gonken-agent env health --json
gonken-agent env policy show
gonken-agent components --json
gonken-agent env watch --changes-only --health
```

Expected: default `qwen3:0.6b`, real SHT31 and `libgpiod`, both simulated flags
false, automatic policy ON28/OFF26. `physical_evidence=false` is a truthful lack
of independent physical observation, not simulation and not a fan lock. Dwell,
filtered temperature and valid-sample recovery may delay a threshold transition.
Sensor failure commands safe OFF without waiting for ordinary dwell.

The installer adds the operator to `gonken-envctl`. Reconnect SSH if the current
session predates that group change; do not grant raw hardware access to work
around a stale login. Only the environment daemon owns SHT31 and GPIO23.

## Manual overrides, timers and power

Manual `env fan on/off` intentionally selects manual operation. Restore automatic
with `gonken-agent env mode set automatic`. Timers use the same owner and safety
checks; restart of that daemon clears timers. Pending old timer actions do not
replay after reboot. Repeating jobs have finite leases and bounded queue limits.

Voice power requests require a matching second utterance, successful acknowledgement
audio, a real relay safe-OFF handshake, and fixed logind authorization. They never
execute an arbitrary shell string or bypass inhibitors. Use the exact README
examples, including the designated service identity for administrative CLI power.
No actual host shutdown/reboot is executed during development verification.

## Failure and recovery behavior

An already-installed selected real thermostat is reconciled before later model
preparation. Model/speech dependencies are prepared from the candidate before
switching `current`. Optional alternate tool failure is reported as degraded;
the default/selected required capabilities remain mandatory. Post-activation
services must report the current release and effective configuration fingerprint.
This avoids accepting a stale simulated daemon or old model settings as current.

A later voice failure does not necessarily stop an independently healthy thermostat.
Inspect its actual state; do not rewrite a correct configuration again. Upload the
single `.tar.bz2` printed by installer failure collection. Ordinary support remains
`gonken-agent support --output-dir /tmp`. No raw speech, transcripts or model answers
are added to evidence. Power diagnostics contain only bounded event metadata.

Existing code-release rollback commands remain available in maintenance. Full
semantic rollback across every changed OS/model/config dependency is still an open
Attempt03 family; never assume a code-link rollback restores all mutable state.
Keep the previous exact archive and current config backups. The complete current
regression/extraction outcome belongs to the delivery receipt, not a generic
`systemd active` or `physical_evidence` flag.

B12 ships the README's real-room, timer, voice and confirmed-power functionality.
The optional display/live-console/touch programme and remaining whole-repository
cleanup are not silently relabeled complete. See [current state](CURRENT_STATE.md).
