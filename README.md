# GonKenLab Agent

GonKenLab Agent turns a supported Raspberry Pi into a privacy-oriented, fully
local voice assistant. Qwen, speech recognition, speech synthesis, and the voice
runtime operate on the Pi; normal conversation does not require a cloud AI
service.

The current production target is **Raspberry Pi 5 (4 GB or greater) running
Raspberry Pi OS Lite 64-bit based on Debian 13/Trixie**.

## 1. Prepare the Raspberry Pi

The easiest path is Raspberry Pi Imager. Before writing the card, configure:

- a username and password;
- SSH, if you want remote administration;
- Wi-Fi SSID/password **and WLAN country**, if Wi-Fi will be used;
- or use Ethernet for the first installation.

The WLAN country matters: Raspberry Pi OS may keep Wi-Fi radio-disabled until a
regulatory country has been configured. See
[Installation and fresh-Pi preparation](docs/INSTALLATION.md) if Wi-Fi is
blocked or the Pi is not yet reachable.

## 2. Install

SSH into the Pi as your normal administrator account and run:

```bash
curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | bash
```

The launcher installs the small checkout prerequisites, clones/updates the
repository, and hands control to the resumable bootstrap. The bootstrap installs
and validates the local model, Whisper, Piper, the system service, physical
audio, and the always-on voice runtime.

### Optional Bluetooth speaker/headset

If you know the device's Bluetooth MAC address, this is the most deterministic
headless setup:

```bash
curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | \
  bash -s -- --bluetooth-audio --bluetooth-device AA:BB:CC:DD:EE:FF
```

Put a new device into pairing mode when the installer asks. The MAC above is an
example only; no device identity is hard-coded in GonKenLab Agent.

A unique name can also be used, or omit `--bluetooth-device` for guided
discovery. See [Headless Bluetooth audio](docs/BLUETOOTH_AUDIO.md).

Already cloned? The standard command is simply:

```bash
cd ~/gonkenlabagent
./bootstrap.sh
```

The official repository and `main` branch are defaults.

## 3. Wait for READY

A successful appliance installation ends with output similar to:

```text
[READY] code=APPLIANCE_READY service=gonken-agent.service wake_phrase=Hey_Gonken reboot_required=false
[READY] code=INSTALLATION_COMPLETE service=gonken-agent.service autostart=enabled reboot_required=false wake_phrase=Hey_Gonken
```

When audio is available, the assistant also announces that it is ready.

No shell login is required for normal operation. `gonken-agent.service` is
enabled under systemd and starts automatically whenever the Pi boots.

## 4. Use the assistant

Power on the configured speaker/headset (if any), power the Raspberry Pi, and
wait for the ready announcement. Then say:

> **Hey Gonken**

Wait for the spoken **“Yes?”** acknowledgement, then ask your question. The
assistant processes it locally, speaks the answer, and returns to wake-word
standby.

To check readiness from SSH:

```bash
gonken-agent status
```

For manual foreground operation, one-turn testing, service start/stop/restart,
logs, `doctor`, and support collection, see
[Operating and troubleshooting GonKenLab Agent](docs/OPERATIONS.md).

## Documentation

- [Installation and fresh-Pi preparation](docs/INSTALLATION.md)
- [Operating, starting/stopping, logs and diagnostics](docs/OPERATIONS.md)
- [Headless Bluetooth audio](docs/BLUETOOTH_AUDIO.md)
- [Raspberry Pi acceptance runbook](docs/RASPBERRY_PI_ACCEPTANCE_RUN.md)
- [Dependency profiles](requirements/README.md)

Engineering/project-maintenance material is kept under
[`docs/development/`](docs/development/) rather than in this user-facing README.

## Important

Use the packaged `gonken-agent` commands and `gonken-agent.service`. Do **not**
run the retained `orchestrator.py`/legacy source runtime or install Python
packages globally with `pip`; those files exist only for compatibility and
project provenance, not as the supported appliance entry point.

Project policy currently prohibits redistribution unless that policy is
explicitly changed by the project owner.
