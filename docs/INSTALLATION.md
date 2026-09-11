# GonKenLab Agent installation and recovery

This document contains the detailed path behind the short README setup.

## Standard fresh Raspberry Pi

Run as the normal Raspberry Pi administrator user, not as `sudo bash`:

```bash
curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | bash
```

The streamed launcher performs only the small outer bootstrap:

1. validates sudo when needed;
2. runs `apt-get update`;
3. installs `ca-certificates`, `git`, and `python3`;
4. creates or updates a clean `~/gonkenlabagent` checkout;
5. resolves the requested Git ref;
6. runs the repository's governed `bootstrap.sh`.

`bootstrap.sh` owns the real installation: platform/resource validation,
immutable application release, Ollama and Qwen, Whisper/Piper, speech models,
systemd service, structured installer state, and optional Bluetooth audio.

## Standard checkout command

The official source and main ref are defaults:

```bash
cd ~/gonkenlabagent
./bootstrap.sh
```

Advanced/custom source:

```bash
./bootstrap.sh \
  --source-url https://github.com/mukulu/gonkenlabagent.git \
  --ref main
```

## Bluetooth at first install

Known MAC (preferred in a busy lab):

```bash
curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | \
  bash -s -- --bluetooth-audio --bluetooth-device AA:BB:CC:DD:EE:FF
```

Known name substring:

```bash
./bootstrap.sh --bluetooth-audio --bluetooth-device 'My Headset'
```

Guided discovery:

```bash
./bootstrap.sh --bluetooth-audio
```

The device-specific selector is deployment input only. It is written to the
private bootstrap record and is never a source-controlled hardware constant.

## Resume after interruption or recoverable failure

Do not delete models/releases merely because one later step failed. Correct the
reported cause and rerun the same command:

```bash
cd ~/gonkenlabagent
./bootstrap.sh
```

The step engine probes completed boundaries and resumes from the first missing
postcondition. Long network/build phases emit `RUNNING` and `PROGRESS` output.

## Service verification

```bash
systemctl status gonken-agent.service --no-pager -l
journalctl -u gonken-agent.service -b --no-pager -n 100
```

Optional Bluetooth extension:

```bash
systemctl status gonken-bluetooth-autoconnect.service --no-pager -l
sudo /usr/local/bin/gonken-bluetooth status \
  --record /etc/gonken-agent/bluetooth-device.record \
  --audio-user gonken-agent
```

## Diagnostic support bundle

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

For installer-specific diagnosis also preserve `/var/lib/gonken-agent/install`
and the current boot's relevant systemd journal. The development blueprint tracks
expanding the normal support bundle to include those records automatically.

## Security note about the one-command launcher

Streaming a script to a shell is convenient but executes the current HTTPS-hosted
launcher immediately. Environments that require review/change control should use
the download-review-run form documented in the README or pin a reviewed commit.
