# Operating and troubleshooting GonKenLab Agent

This document is the operational reference after installation. Normal everyday
use does not require SSH or a shell login.

## Normal boot and wake-word operation

`gonken-agent.service` is a system service. It starts during boot independently
of interactive user login, so console auto-login/password bypass is neither
required nor recommended.

The expected boot path is:

```text
Linux/systemd
  -> Ollama
  -> optional Bluetooth radio + trusted-device reconnect
  -> dedicated headless PipeWire/WirePlumber session
  -> gonken-agent.service
  -> microphone/output/model readiness
  -> ready announcement
  -> wake-word standby
```

The default wake phrase is:

```text
GonKen
```

Say the wake phrase, wait for the spoken `Yes?` acknowledgement, then ask the
question. Separating wake detection from the question avoids truncating a long
question inside the short phrase-spotting capture window.

Check the configured phrase and host matcher boundary with:

```bash
gonken-agent status
gonken-agent wake status
gonken-agent wake status --json
```

The host matcher accepts the default `GonKen`, the backward-compatible `Hey GonKen` alias, split-token `Gon Ken`, punctuation/case variants and bounded one-character STT errors for the GonKen token.  This is host software evidence only; real microphone false-accept/false-reject and wake-to-acknowledgement latency evidence still belongs to the Raspberry Pi acceptance run.

Wake standby uses a bounded pipelined capture path: the microphone continues collecting the next short wake window while the previous window is transcribed. A two-window newest-wins queue prevents unbounded Whisper backlog; stale queued windows are dropped and reported categorically. The dedicated wake-monitoring indicator on logical GPIO22 is requested by line name and is ON only while standby capture is active. The software contract is host-tested, but the actual Raspberry Pi gpiochip mapping and visible LED behavior must still be verified on the target.

After a captured request begins processing, ordinary deterministic environment commands should normally answer without filler.  Slower general-model requests may receive `Just a second.` and, if still unresolved, at most one `I'm still working on that.` cue.  These cues are generated locally through Piper and cached under the voice cache directory; legacy unknown-provenance filler WAVs remain excluded.

Autonomous environment transition announcements are voice-owned.  The environment daemon records typed transition events, and the voice runtime may announce priority automatic/safety transitions without claiming fan blade motion or software speed control.  Simulated transitions are spoken as simulation.

## Service controls

Status:

```bash
systemctl status gonken-agent.service --no-pager -l
```

Start:

```bash
sudo systemctl start gonken-agent.service
```

Stop:

```bash
sudo systemctl stop gonken-agent.service
```

Restart:

```bash
sudo systemctl restart gonken-agent.service
```

Enable automatic startup now and on future boots:

```bash
sudo systemctl enable --now gonken-agent.service
```

The installer does this automatically. This command is mainly useful for
recovery/verification.

## Manual voice operation

Only one process should own the microphone at a time. Stop the system service
before starting a foreground voice runtime:

```bash
sudo systemctl stop gonken-agent.service
```

### Continuous foreground wake-word runtime

For USB audio, the normal administrator account can usually run:

```bash
gonken-agent run
```

Press `Ctrl+C` to stop it, then restore automatic operation:

```bash
sudo systemctl start gonken-agent.service
```

### Optional physical push-to-talk recovery mode

The packaged default remains wake-word operation, but `runtime.interaction_mode = "push_to_talk"` is supported as a physical privacy/recovery mode. In PTT mode the service discovers the configured button and recording-LED GPIOs by their libgpiod line names (`GPIO17` and `GPIO27` by default), rather than assuming the BCM number is the gpiochip offset. The button uses an internal pull-up and is active while held to ground. The recording LED means **microphone capture is active**; it is turned off before transcription, model inference, and speech playback.

Physical target wiring and line-name discovery must pass before this mode is accepted. See [HARDWARE_SETUP.md](HARDWARE_SETUP.md) and [RASPBERRY_PI_ACCEPTANCE_RUN.md](RASPBERRY_PI_ACCEPTANCE_RUN.md). To select PTT, change the root-owned site configuration rather than exposing GPIO through voice or a model action:

```toml
[runtime]
interaction_mode = "push_to_talk"
```

Restart the service after validating the site configuration. Hold the physical button while speaking and release it to process. A held button is bounded to 30 seconds; an overlong capture is discarded rather than automatically submitted.

### One microphone -> AI -> speaker turn

```bash
gonken-agent talk --seconds 8
```

Speak during the bounded capture window. The recognized question and answer are
printed only to the foreground terminal for this explicit manual diagnostic;
they are not persisted by the normal service.

### Exact service-user test (recommended for Bluetooth)

Bluetooth audio belongs to the dedicated headless `gonken-agent` PipeWire
session. To reproduce the system-service audio environment manually:

```bash
sudo systemctl stop gonken-agent.service
UID_GA="$(id -u gonken-agent)"
sudo runuser -u gonken-agent -- env \
  HOME=/var/lib/gonken-agent \
  XDG_RUNTIME_DIR="/run/user/$UID_GA" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$UID_GA/bus" \
  /usr/local/bin/gonken-agent run
```

For one turn, replace the final `run` with:

```text
talk --seconds 8
```

After the foreground test:

```bash
sudo systemctl start gonken-agent.service
```

## Status and diagnostics

Compact runtime state:

```bash
gonken-agent status --json
```

Probe the local model:

```bash
gonken-agent doctor --probe-ollama
```

Probe the physical input and output devices as well:

```bash
gonken-agent doctor --probe-ollama --probe-audio
```

The physical audio probe briefly opens the microphone and speaker path. It does
not send content to a cloud service.

## Logs

Follow the voice service live:

```bash
journalctl -fu gonken-agent.service
```

Current boot:

```bash
journalctl -u gonken-agent.service -b --no-pager
```

Recent bounded output:

```bash
journalctl -u gonken-agent.service -b --no-pager -n 100
```

Ollama:

```bash
journalctl -u ollama.service -b --no-pager -n 100
```

Optional Bluetooth reconnect helper:

```bash
systemctl status gonken-bluetooth-autoconnect.service --no-pager -l
journalctl -u gonken-bluetooth-autoconnect.service -b --no-pager -n 100
```

## Bluetooth status

```bash
bluetoothctl show
bluetoothctl devices Paired
```

For an installed GonKen Bluetooth record:

```bash
sudo /usr/local/bin/gonken-bluetooth status \
  --record /etc/gonken-agent/bluetooth-device.record \
  --audio-user gonken-agent
```

See [BLUETOOTH_AUDIO.md](BLUETOOTH_AUDIO.md) for pairing and profile details.

## Support bundle

Create the project allow-listed support ZIP:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

The command prints the resulting ZIP path. When invoked through `sudo` without
`--output`, the maintenance wrapper now places the bundle in the invoking
administrator's home directory and returns ownership to that user, so a second
`sudo mv` step is unnecessary. Normal support export is designed to exclude
transcripts, prompts, answers, pairing secrets and raw audio. Debug snapshots
include bounded ALSA and PipeWire/Pulse route metadata so capture-routing failures
can be diagnosed without storing speech content.

The ZIP also includes a sanitized non-actuating target manifest, platform and
resource inventory, bounded service-event code counts and an evidence index when
the packaged maintenance helpers are present. When diagnosing an installer
failure, upload the installer-owned failure ZIP printed by the installer; it is
designed to carry the same one-upload evidence role even before activation.
Preserve the exact terminal error when convenient, but do not create a second
diagnostic package for information the ZIP already records.

## Updating

From the checkout:

```bash
cd ~/gonkenlabagent
git pull --ff-only origin main
./bootstrap.sh
```

Or use the managed update helper where appropriate:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/update.sh
```

The installer is postcondition-driven and should reuse valid downloaded models
and completed stages rather than reinstalling them unnecessarily.

## Rollback and uninstall

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/rollback.sh
sudo /usr/local/lib/gonken-agent/current/maintenance/uninstall.sh
```

Uninstall keeps project data by default unless the explicit purge contract is
used.

## What not to run

The source-tree `orchestrator.py`, `legacy_orchestrator.py`, `setup.sh`, and
`gonken-agent run --legacy-source` are not the supported production voice
runtime. Do not install `numpy` or other packages globally merely to make those
legacy paths run. Raspberry Pi OS Trixie intentionally protects the system
Python under PEP 668; the supported application uses its managed immutable
virtual environment.

## Audio readiness and fallback diagnostics

The production runtime resolves capture and playback independently and rechecks
routes while waiting for readiness. Its automatic policy is **wired first**: a
usable PipeWire/Pulse USB endpoint is preferred, then one unambiguous direct ALSA
USB endpoint, then the exact configured Bluetooth endpoint. Thus plugging the
AIRHUG (or another generic USB audio device) while Bluetooth is also connected
causes the usable wired route to win without deleting the Bluetooth bond. Mixed
USB/Bluetooth directions remain valid.

Inspect the service-user audio graph with:

```bash
UID_GA="$(id -u gonken-agent)"
sudo runuser -u gonken-agent -- env \
  HOME=/var/lib/gonken-agent \
  XDG_RUNTIME_DIR="/run/user/$UID_GA" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$UID_GA/bus" \
  sh -c 'pactl info; pactl get-default-source; pactl get-default-sink; pactl list sources short; pactl list sinks short'

arecord -l
aplay -l
```

`AUDIO_CAPTURE_FAILED` and `AUDIO_PLAYBACK_FAILED` journal events include only a
bounded command/device diagnostic, not captured speech. For a Bluetooth headset,
bootstrap attempts a microphone-capable profile but does not confuse pairing with
full appliance readiness: a playback-only Bluetooth route may coexist with an
accepted direct USB microphone, while the final readiness gate must prove that
some real capture path works.


## Service-user audio environment

The system service must talk to the `gonken-agent` user audio session rather than
the root system-manager session. Installation therefore generates
`/etc/gonken-agent/runtime-environment` from the actual numeric UID of the
`gonken-agent` account and loads it through the service unit. Do not replace this
with systemd `%U`: in a system unit that specifier refers to the system manager
(PID 1) and can resolve to UID 0 rather than the `User=gonken-agent` account.

If audio tools unexpectedly try `/run/user/0`, rerun the current bootstrap so the
governed service unit/runtime environment is repaired, then inspect:

```bash
systemctl cat gonken-agent.service
sudo cat /etc/gonken-agent/runtime-environment
id -u gonken-agent
```

## V09 room-environment operator and voice boundary

For hardware preparation, see [V09 room-environment hardware setup](HARDWARE_SETUP.md). For the full control reference, see [V09 environment control reference](ENVIRONMENT_CONTROL.md). For simulation and hybrid-HIL practice, see [V09 simulation and hybrid-HIL guide](SIMULATION.md). For fault diagnosis, see [V09 troubleshooting guide](TROUBLESHOOTING.md).

V09 adds a room-environment control boundary. Current code includes host-tested
SHT31 and libgpiod relay adapter modules, but real SHT31 reads, relay polarity,
PENGLIN USB switching and fan cycles are still target-gated. The direct operator
route is:

```bash
gonken-agent env status
gonken-agent env temperature
gonken-agent env humidity
gonken-agent env read
gonken-agent env fan on
gonken-agent env fan off
gonken-agent env mode set manual
gonken-agent env mode set semi-automatic
gonken-agent env mode set automatic
gonken-agent env policy show
gonken-agent env policy set --start-c 28 --stop-c 26.5
gonken-agent env watch --interval 2
gonken-agent env status --json
```

The `env` command is an IPC client. It must not be modified to read GPIO, I2C or
policy files directly. Human-readable output is for operators; `--json` is the
stable machine-readable form. `env watch` is now a passive observer: it reads the
daemon's latest `state.snapshot.get` result and must not create extra sensor
samples, accelerate simulated recovery, change dwell timing, write relay state,
or mutate policy. Use `gonken-agent env read` when an explicit read-now operation
is intended. All environment commands report `physical_evidence=false` until a
real Pi HIL run records otherwise.

Simulation is controlled through the same daemon and IPC boundary. It is intended
for host demonstration, user training and hybrid HIL preparation; it is not proof
of SHT31, relay, PENGLIN or ELUTENG behavior. Typical full-simulation commands
are:

```bash
gonken-agent env simulate status
gonken-agent env simulate sensor set --temperature-c 27 --humidity-pct 50
gonken-agent env simulate sensor unavailable
gonken-agent env simulate sensor crc-error
gonken-agent env simulate sensor stale --age-seconds 30
gonken-agent env simulate sensor recover --temperature-c 27 --humidity-pct 50
gonken-agent env simulate sensor reset
gonken-agent env simulate fan show
gonken-agent env simulate fan behavior normal
gonken-agent env simulate fan unavailable
gonken-agent env simulate fan fail-next-write
gonken-agent env simulate fan reset
gonken-agent env simulate reset
```

Simulation mutation requires `simulation_runtime_control_enabled = true` in the
static environment profile and the relevant backend must actually be
`simulated`. The daemon rejects a simulated-sensor mutation when the sensor
backend is `sht31`, and rejects a simulated-actuator mutation when the actuator
backend is `libgpiod`. This prevents the operator from silently substituting fake
values for a real hardware path.

The voice route now has a deterministic environment-intent parser before the
ordinary local model path. Clear phrases such as “what is the room temperature?”,
“what is the humidity?”, “is the room fan on?”, “turn the room fan on”, “turn the
room fan off”, “use automatic mode”, and “turn it on at 28 and off at 26.5” are
converted into typed environment-daemon operations. Ambiguous phrases such as
“set the temperature to 25” ask for clarification instead of changing policy.
General conversation still uses the local LLM.

Spoken environment answers are derived from the daemon result or daemon rejection.
They may report room-fan relay power, mode, policy and sensor state. They must not
claim physical blade rotation, software speed control, or real Raspberry Pi
acceptance with the current relay/PENGLIN/ELUTENG hardware. The adapter modules
are an implementation boundary, not acceptance evidence: only the M10.7 target
run can confirm the actual SHT31 address, Pi 5 gpiochip mapping, relay active
polarity, boot safe-off behavior and fan power cycles.

## Environment voice responses in simulation and hybrid-HIL

Voice environment commands use the same deterministic daemon client as the CLI.
When the daemon reports a simulated sensor or simulated actuator, the spoken
response must name that boundary. For example, a simulated temperature is spoken
as simulation evidence rather than as a physical room reading, and a simulated
fan actuator command is spoken as simulated actuator state rather than observed
fan motion.

This protects three separate truths:

- a simulated sensor value is useful for testing control logic but is not SHT31
  room-temperature evidence;
- a simulated actuator can validate command routing but does not prove relay
  polarity, PENGLIN wiring, or blade motion;
- hybrid-HIL evidence can support the physical side that was actually present,
  but the simulated side remains open.

Ordinary fan voice responses still avoid software-speed claims. With the
current ELUTENG inline controller and relay architecture, GonKen can report
relay/fan-power command state only; it cannot select Low/Medium/High speed or
observe blade RPM.
