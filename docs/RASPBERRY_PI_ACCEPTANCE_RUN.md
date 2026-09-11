# Raspberry Pi Acceptance Run

This runbook is for the first real Raspberry Pi validation of GonKenLab Agent.
It assumes Raspberry Pi OS Lite 64-bit, SSH access, and the intended USB
microphone/speaker connected when available.

## 1. Install From a Clean Pi

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/mukulu/gonkenlabagent.git
cd gonkenlabagent
./bootstrap.sh --source-url https://github.com/mukulu/gonkenlabagent.git --ref main
```

If the run is interrupted by networking, power, or a recoverable package error,
fix the immediate condition and rerun the same bootstrap command once. Do not
delete project state before collecting diagnostics.

## 2. Check Service State

```bash
systemctl status gonken-agent.service --no-pager
journalctl -u gonken-agent.service -n 100 --no-pager
systemctl status ollama.service --no-pager
```

The service may report `DEGRADED` until real audio, GPIO, model, and speech
conditions are confirmed. `DEGRADED` is acceptable for diagnostic collection;
`FAILED` should be captured before attempting manual repair.

## 3. Reboot and Recheck

```bash
sudo reboot
```

After reconnecting by SSH:

```bash
systemctl is-enabled gonken-agent.service
systemctl is-active gonken-agent.service
journalctl -u gonken-agent.service -n 100 --no-pager
```

## 4. Collect the Support ZIP

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

Upload the printed ZIP path for review. The bundle is designed to contain
redacted configuration, categorical health, content-free telemetry, and the
latest startup hardware/software snapshot. It does not include transcripts,
answers, raw audio, corpus files, Git history, shell profiles, or arbitrary
system logs.

Useful raw files to inspect locally before upload are:

```text
/var/lib/gonken-agent/runtime/startup/latest.json
/var/lib/gonken-agent/runtime/startup/startup-*.json
/var/lib/gonken-agent/runtime/telemetry.jsonl
```

## 5. Exercise Lifecycle Commands

Run these only after the initial install and support ZIP have been captured.

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/update.sh
sudo /usr/local/lib/gonken-agent/current/maintenance/rollback.sh
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

For uninstall/reinstall validation:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/uninstall.sh
cd ~/gonkenlabagent
./bootstrap.sh --source-url https://github.com/mukulu/gonkenlabagent.git --ref main
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

## 6. Hardware Notes to Record

Record these observations alongside the support ZIP:

- Raspberry Pi model and RAM size.
- Raspberry Pi OS image date if known.
- MicroSD size and whether a cooler/fan is installed.
- Microphone/speaker model and whether it was connected at boot.
- Button and LED wiring pins.
- Whether the service returned after reboot without logging in.
- Whether audio appeared, disappeared, or changed after replug/reboot.
- Any exact command that produced a failure.

## 7. Acceptance Boundary

A successful cloud test run means the repository is ready to be tested on the
Pi. It does not prove physical readiness. Physical acceptance requires the
uploaded support ZIP and operator notes from this run.
