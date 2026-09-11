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
Hey Gonken
```

Say the wake phrase, wait for the spoken `Yes?` acknowledgement, then ask the
question. Separating wake detection from the question avoids truncating a long
question inside the short phrase-spotting capture window.

Check the configured phrase with:

```bash
gonken-agent status
```

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

When diagnosing an installer failure, also preserve the exact terminal error;
the installer keeps structured state/events under the root-owned
`/var/lib/gonken-agent/install` tree.

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

The production runtime resolves capture and playback independently. For a managed
Bluetooth deployment it prefers the dedicated PipeWire/Pulse default source/sink.
If one direction is unavailable and exactly one direct USB audio path is usable,
that direction falls back to the USB device. This is intentional and allows a
USB microphone + Bluetooth speaker configuration.

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
