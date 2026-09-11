# Raspberry Pi acceptance run

This is the final real-target acceptance procedure. Passing host-side tests is
not enough; appliance readiness must be demonstrated on a freshly imaged Pi.

## 1. Fresh-image install

Prepare Raspberry Pi OS Lite 64-bit/Trixie in Raspberry Pi Imager. Configure
SSH and, if Wi-Fi is used, SSID/passphrase/WLAN country before first boot.

Core USB/default-audio installation:

```bash
curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | bash
```

Bluetooth installation when the intended device MAC is known:

```bash
curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | \
  bash -s -- --bluetooth-audio --bluetooth-device AA:BB:CC:DD:EE:FF
```

Do not manually preinstall Ollama, Whisper, Piper, Python packages, PipeWire or
project virtual environments. The acceptance test is intended to prove that the
launcher/bootstrap owns those prerequisites.

## 2. Installation-completion gate

Accept only a final `READY` boundary. Record the exact terminal output.
Expected shape:

```text
[READY] code=APPLIANCE_READY ... wake_phrase=Hey_Gonken reboot_required=false
[READY] code=INSTALLATION_COMPLETE ... autostart=enabled ...
```

The target should also audibly announce readiness when its output path is
available.

Run:

```bash
gonken-agent status --json
gonken-agent doctor --probe-ollama --probe-audio
systemctl status gonken-agent.service --no-pager -l
```

## 3. Live voice test

With the service running, say:

```text
Hey Gonken
```

Then ask a short question. Record whether:

1. wake phrase was recognized;
2. the question was understood;
3. an offline Qwen response was generated;
4. Piper played the response through the intended output;
5. the service returned to wake standby;
6. a second turn also succeeded.

Follow categorical runtime state if required:

```bash
journalctl -fu gonken-agent.service
```

No transcript should be persisted by the normal service.

## 4. Manual runtime test

Stop the daemon so it releases the microphone:

```bash
sudo systemctl stop gonken-agent.service
```

Test one explicit turn:

```bash
gonken-agent talk --seconds 8
```

For exact Bluetooth service-user testing, use the command in
[OPERATIONS.md](OPERATIONS.md). Restore automatic operation:

```bash
sudo systemctl start gonken-agent.service
```

## 5. Reboot/no-login test

```bash
sudo reboot
```

Do not log in immediately merely to start the application. Wait for normal boot
and the ready announcement. If Bluetooth is used, power on the trusted device
and verify it reconnects automatically.

Afterward, SSH in only for evidence collection:

```bash
systemctl is-enabled gonken-agent.service
systemctl is-active gonken-agent.service
gonken-agent status --json
journalctl -u gonken-agent.service -b --no-pager -n 100
```

Repeat a real `Hey Gonken` voice interaction.

## 6. Degraded/recovery tests

At minimum record these without deleting the installation:

- boot with Bluetooth device off, then turn it on and verify recovery;
- temporarily disconnect USB audio where applicable, restore it and verify
  readiness returns;
- restart `ollama.service` and verify voice runtime waits/recovers;
- stop/start/restart `gonken-agent.service`;
- rerun bootstrap and verify completed model/artifact stages are reused;
- if Wi-Fi is not used, verify Ethernet-only operation is unaffected by Wi-Fi
  rfkill state.

## 7. Lifecycle/recovery commands

After the primary voice/reboot evidence is captured, exercise the maintained
lifecycle helpers:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/update.sh
sudo /usr/local/lib/gonken-agent/current/maintenance/rollback.sh
```

For the dedicated uninstall/reinstall campaign, first preserve support evidence,
then run:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/uninstall.sh
```

The normal uninstall keeps project data unless its explicit purge contract is
used. Reinstall with the same one-command launcher and repeat the READY/wake
gates.

## 8. Support evidence

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

Preserve the printed ZIP and the exact bootstrap/service errors if any. Installer
state/events remain under the root-owned `/var/lib/gonken-agent/install` tree.

## 9. Acceptance decision

The build is appliance-ready only when all of these pass on the physical target:

- clean install reaches `READY`;
- live wake + spoken question + spoken answer succeeds;
- service starts without interactive login;
- reboot returns to wake standby;
- configured Bluetooth reconnects automatically where Bluetooth is in scope;
- manual start/stop/restart/talk/log procedures work;
- no Critical/High new defect remains unexplained.

A Pi 4 is not covered by this Pi 5 acceptance run. It requires a separate target
profile and physical performance evidence.
