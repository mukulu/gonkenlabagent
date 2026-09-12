# GonKenLab Agent installation and recovery

The README gives the shortest supported path. This document covers fresh-Pi
prerequisites, network recovery, installation options and resume behavior.

## Fresh Raspberry Pi preparation

The currently accepted production profile is Raspberry Pi 5 with at least 4 GB
RAM running Raspberry Pi OS Lite 64-bit based on Debian 13/Trixie.

Use Raspberry Pi Imager and configure the OS image before first boot:

1. choose a normal administrator username/password;
2. enable SSH if remote administration is desired;
3. if using Wi-Fi, set SSID, passphrase **and WLAN country**;
4. alternatively connect Ethernet for the initial installation.

A passwordless shell login is not required. GonKenLab runs as a systemd service
and starts before any interactive login.

### Wi-Fi is blocked after first boot

Raspberry Pi OS may block Wi-Fi until its regulatory country is configured. The
installer must not guess this legal/regulatory value.

Interactive recovery:

```bash
sudo raspi-config
```

Set the WLAN country, then enable the radio. A non-interactive equivalent is:

```bash
sudo raspi-config nonint do_wifi_country CC
sudo rfkill unblock wifi
nmcli radio wifi on
```

Replace `CC` with the correct two-letter country code for the Pi's actual
location. Then configure/connect the desired NetworkManager Wi-Fi connection.

If Ethernet is working, a blocked unused Wi-Fi radio does not block GonKenLab
installation.

## One-command installation

Run as the normal Raspberry Pi administrator account:

```bash
curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | bash
```

The launcher:

1. validates sudo when required;
2. refreshes package metadata;
3. installs Git, CA certificates and distribution Python;
4. clones/updates a clean `~/gonkenlabagent` checkout;
5. hands control to the repository bootstrap.

`bootstrap.sh` then validates and converges every governed boundary: platform,
resources, accounts, immutable release, Ollama/Qwen, Whisper/Piper, models,
systemd, optional Bluetooth, live physical audio and the voice runtime.

Long operations emit `RUNNING`/`PROGRESS`/`WAITING` state. Recoverable failures
can be corrected and the same command rerun.

## Installation with Bluetooth audio

Known MAC address (preferred):

```bash
curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | \
  bash -s -- --bluetooth-audio --bluetooth-device AA:BB:CC:DD:EE:FF
```

Known unique name:

```bash
cd ~/gonkenlabagent
./bootstrap.sh --bluetooth-audio --bluetooth-device 'My Headset'
```

Guided discovery:

```bash
./bootstrap.sh --bluetooth-audio
```

Bluetooth setup reconciles its own prerequisites: BlueZ service, software
rfkill state, controller power, the headless PipeWire/WirePlumber session,
pairing/trust, audio routing and persistent trusted-device reconnect. A hardware
rfkill block or missing controller fails with a specific diagnostic instead of
being silently bypassed.

Keep a new device in pairing mode when the installer prints the pairing action.
Device identities are deployment input only and are never hard-coded in source.

## Installation from an existing checkout

The official source and `main` are defaults:

```bash
cd ~/gonkenlabagent
./bootstrap.sh
```

Custom source/ref remains available for controlled forks/tests:

```bash
./bootstrap.sh \
  --source-url https://github.com/mukulu/gonkenlabagent.git \
  --ref main
```

## Successful completion

Installation is no longer considered complete merely because packages and
services exist. The final appliance gate requires:

- valid active release;
- local Qwen model reachable through loopback Ollama;
- Whisper and Piper artifacts validated;
- system service enabled and active;
- configured microphone path opens;
- configured speaker path opens;
- local voice runtime reaches wake-word standby.

The expected final boundary resembles:

```text
[READY] code=APPLIANCE_READY service=gonken-agent.service wake_phrase=Hey_Gonken reboot_required=false
[READY] code=INSTALLATION_COMPLETE service=gonken-agent.service autostart=enabled reboot_required=false wake_phrase=Hey_Gonken
```

No reboot is normally required. The service is already started. If the output
path is available the assistant announces readiness; say **Hey Gonken** to use
it.

## Resume after failure/interruption

Do not delete releases or downloaded models because a later stage failed.
Correct the reported prerequisite and rerun the same bootstrap command. Each
step verifies its postcondition and skips valid completed work.

For example:

```bash
cd ~/gonkenlabagent
./bootstrap.sh --bluetooth-audio --bluetooth-device AA:BB:CC:DD:EE:FF
```

## Reboot verification

After a successful install:

```bash
sudo reboot
```

No login should be required for the appliance itself. After boot, systemd starts
the service; if Bluetooth was configured, the trusted-device helper reconnects
it when available. The runtime waits/retries local dependencies and returns to
wake-word standby.

After reconnecting by SSH for verification:

```bash
systemctl is-enabled gonken-agent.service
systemctl is-active gonken-agent.service
gonken-agent status --json
```

For detailed manual controls/logs see [OPERATIONS.md](OPERATIONS.md).

## Locale warnings

The first-install launcher runs package management under `C.UTF-8` so incomplete
locale generation on a fresh image does not produce avoidable package-manager
noise. Site locale configuration remains an operating-system preference and is
not changed by GonKenLab Agent.

## Security note about streamed installation

`curl ... | bash` is deliberately provided for low-friction private deployment,
but it executes the current HTTPS-hosted launcher immediately. Environments
requiring change review should download/pin/review the launcher and source
commit before execution.

## Physical audio readiness

Bootstrap does not treat a Bluetooth bond or an ALSA device listing as proof that
voice capture works. The final readiness gate opens a real capture path and a real
playback path. Bluetooth setup revalidates the connected PipeWire output and
actively attempts an HFP/HSP capture profile for headset-capable devices; if that
Bluetooth capture route is unavailable, final readiness may still use one
unambiguous direct USB microphone.

The runtime is transport-adaptive and reuses what is already connected. For each
direction it prefers a usable **wired USB** route first (PipeWire/Pulse USB when
visible, otherwise an unambiguous direct ALSA USB path), then the exact configured
Bluetooth endpoint. Input and output are selected independently, so mixed routes
remain valid. This prevents a stale Bluetooth record from forcing a broken default
route and lets an already-connected wired device win without disabling Bluetooth.

If readiness still fails, collect the support bundle described in
[OPERATIONS.md](OPERATIONS.md); the debug snapshot now contains bounded ALSA and
PipeWire/Pulse route metadata.
