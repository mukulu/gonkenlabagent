# GonKenLab Agent

GonKenLab Agent is a privacy-oriented Raspberry Pi 5 assistant stack designed
for local/offline AI-lab use. The maintained installation provisions local
Qwen 3.5 through loopback-only Ollama, local Whisper speech recognition, local
Piper speech synthesis, a governed headless service, diagnostics, and an
optional headless Bluetooth-audio extension.

## Install on Raspberry Pi

Use Raspberry Pi OS Lite 64-bit (Debian Trixie), enable SSH in Raspberry Pi
Imager, boot the Pi, then run this as the normal Pi user:

```bash
curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | bash
```

That one command refreshes package metadata, installs the small checkout
prerequisites, clones/updates `~/gonkenlabagent`, and runs the governed
bootstrap. Long downloads/builds report `RUNNING`/`PROGRESS` state and the
installer is resumable after recoverable interruption.

Already cloned? The official repository and `main` are defaults:

```bash
cd ~/gonkenlabagent
./bootstrap.sh
```

The explicit form remains available for forks or a non-default ref:

```bash
./bootstrap.sh \
  --source-url https://github.com/mukulu/gonkenlabagent.git \
  --ref main
```

## Optional headless Bluetooth audio

USB audio remains the fallback. Bluetooth is enabled only when requested.
If the intended device MAC is known, pass it at install time:

```bash
curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | \
  bash -s -- --bluetooth-audio --bluetooth-device AA:BB:CC:DD:EE:FF
```

You may supply a unique name substring instead of a MAC:

```bash
./bootstrap.sh --bluetooth-audio --bluetooth-device 'My Headset'
```

Or let setup pause at a bounded pairing checkpoint:

```bash
./bootstrap.sh --bluetooth-audio
```

An exact MAC is checked directly against known BlueZ state before scanning. The
installer never hard-codes a headset identity and never silently chooses among
multiple matching nearby devices. Successful setup pairs/trusts the device,
prepares a no-login PipeWire/WirePlumber session for `gonken-agent`, and enables
bounded reconnect on later boots.

See [Headless Bluetooth audio](docs/BLUETOOTH_AUDIO.md) for the detailed design
and troubleshooting path.

## After installation

Check the main service:

```bash
systemctl status gonken-agent.service --no-pager -l
```

Recent logs:

```bash
journalctl -u gonken-agent.service -b --no-pager -n 100
```

Optional Bluetooth status:

```bash
systemctl status gonken-bluetooth-autoconnect.service --no-pager -l
sudo /usr/local/bin/gonken-bluetooth status \
  --record /etc/gonken-agent/bluetooth-device.record \
  --audio-user gonken-agent
```

Local model sanity check:

```bash
curl -s http://127.0.0.1:11434/api/version
ollama list
```

Create a private diagnostic ZIP:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

The service also writes a content-free startup snapshot under:

```text
/var/lib/gonken-agent/runtime/startup/latest.json
```

## Update, rollback, uninstall

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/update.sh
sudo /usr/local/lib/gonken-agent/current/maintenance/rollback.sh
sudo /usr/local/lib/gonken-agent/current/maintenance/uninstall.sh
```

Uninstall keeps project data unless explicit purge confirmation is supplied.

## Configuration

Site configuration:

```text
/etc/gonken-agent/config.toml
```

Important defaults include:

- model: `qwen3.5:2b-q4_K_M`;
- USB input/output match: `AIRHUG`;
- push-to-talk GPIO: `17`;
- recording LED GPIO: `27`;
- Ollama: loopback only;
- cloud inference: disabled.

Inspect effective configuration with paths redacted:

```bash
gonken-agent config show --effective --json
```

## Current acceptance boundary

The installer/release lifecycle, Ollama/Qwen, Whisper/Piper artifact chain,
speech-file smoke, systemd service management, update/rollback/uninstall,
startup diagnostics, and host-side tests are implemented. Bluetooth is an
opt-in extension whose actual pairing/profile/reboot behavior must be proven on
the Raspberry Pi.

The governed packaged service is still a headless supervisor while the physical
capture/playback and push-to-talk/GPIO acceptance gates remain open. Plain
`gonken-agent run` therefore still refuses to claim production voice activation.
Do not interpret a successful installer as proof of microphone, speaker, GPIO,
or live conversational quality until the target acceptance run passes.

For the current physical campaign use:

- [Installation and recovery](docs/INSTALLATION.md)
- [Raspberry Pi acceptance runbook](docs/RASPBERRY_PI_ACCEPTANCE_RUN.md)
- [Headless Bluetooth audio](docs/BLUETOOTH_AUDIO.md)

## Development / project handoff

Engineering authority is kept outside the README:

- `docs/development/MASTER_BLUEPRINT.md`
- `docs/development/IMPLEMENTATION_STATUS.md`
- `docs/development/TEST_MATRIX.md`
- `docs/development/DECISIONS.md`
- `docs/development/REPOSITORY_AUDIT.md`
- `requirements/README.md`

`PRD.md` and the retained legacy runtime are provenance/compatibility material,
not release authority. Project policy prohibits redistribution unless that policy is
explicitly changed by the project owner.
