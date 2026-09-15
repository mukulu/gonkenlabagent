# Raspberry Pi target acceptance campaign

This runbook is the authoritative **real-target** procedure for GonKenLab Agent
V09 checkpoint 24. Host CI, simulation, a clean ZIP, or a READY JSON file cannot
substitute for this campaign. Every result must remain classified as host,
simulation, hybrid HIL, or physical evidence.

The target is Raspberry Pi 5 (4 GB or greater) running Raspberry Pi OS Lite
64-bit based on Debian 13/Trixie. The room fan is the ELUTENG demonstration
actuator; it is **not** the Raspberry Pi Active Cooler. Current room-fan software
controls power only. It does not provide software fan-speed selection or
independent blade-motion/RPM feedback.

## 1. Verify the exact downloaded checkpoint before installation

For this campaign, do **not** install remote `main` with the public `curl`
launcher. Doing so would test whatever remote revision is current rather than
the checkpoint that passed host verification.

Copy these delivered files to the Pi:

```text
gonkenlabagent-v09-installer-runtime-repair-checkpoint-24.zip
SHA256SUMS_checkpoint24.txt
```

Verify the archive and extract it without discarding its `.git` directory:

```bash
sha256sum -c SHA256SUMS_checkpoint24.txt
mkdir -p ~/gonken-checkpoint24
python3 -m zipfile -e gonkenlabagent-v09-installer-runtime-repair-checkpoint-24.zip ~/gonken-checkpoint24
cd ~/gonken-checkpoint24/gonkenlabagent-v09-pi-target-campaign-checkpoint-23
# Python's standard-library ZIP extractor does not restore Unix execute bits.
# The archive includes its Git metadata, so restore the exact committed modes/content before validation.
git reset --hard HEAD
test -x ./bootstrap.sh
git rev-parse HEAD
git status --porcelain
git fsck --strict
python3 scripts/release_readiness.py --json --check
```

Acceptance conditions before installation:

- checksum verification passes;
- `git reset --hard HEAD` completes after checksum verification and restores the exact committed executable modes/content required by the standard-library ZIP extraction path;
- `./bootstrap.sh` is executable after that restoration;
- the Git commit matches the commit printed in the checkpoint-24 delivery summary;
- `git status --porcelain` is empty;
- `git fsck --strict` succeeds;
- `release_readiness.py --check` reports `READY_FOR_TARGET_ACCEPTANCE` while
  still listing target gates as not run.

If any identity/integrity check fails, **STOP** and return the terminal output.
The `git reset --hard HEAD` step above is the documented deterministic mode/content restoration required after the Python ZIP extractor; do not make any other in-place repair or edit to force the package to pass.

## 2. Install this exact checkpoint

Prepare a fresh Raspberry Pi OS Lite 64-bit/Trixie image. Configure an
administrator account, SSH if required, and the Wi-Fi country/credentials if
Wi-Fi will be used.

From the verified extracted checkpoint run:

```bash
./bootstrap.sh --local-checkpoint
```

For an intended Bluetooth audio device with a known MAC address:

```bash
./bootstrap.sh --local-checkpoint \
  --bluetooth-audio --bluetooth-device AA:BB:CC:DD:EE:FF
```

Checkpoint 24 repairs the first real-Pi installer failure. Do not work around a failed install with `PYTHONPATH`, ad-hoc `pip install`, copied modules, or edits inside the immutable release. The target release must validate `gpiod` and `smbus` using its own interpreter before appliance readiness can complete.

`--local-checkpoint` is deliberate: it binds the installation source record to
the clean checkout's exact full Git commit. Normal production installs may use
the official remote source later; this acceptance campaign must not silently
switch revisions.

Do not manually preinstall Ollama, Whisper, Piper, Python packages, PipeWire, or
project virtual environments merely to make the installer pass. Preserve the
exact installer error if a governed step fails.

## 3. Installation-completion and provenance gate

Accept only the governed final READY boundary. Expected shape:

```text
[READY] code=APPLIANCE_READY ... wake_phrase=GonKen reboot_required=false
[READY] code=INSTALLATION_COMPLETE ... autostart=enabled ...
```

Run:

```bash
gonken-agent status --json
gonken-agent wake status --json
gonken-agent doctor --probe-ollama --probe-audio
systemctl status gonken-agent.service --no-pager -l
readlink -f /usr/local/lib/gonken-agent/current
/usr/local/lib/gonken-agent/current/.venv/bin/python -c 'import gpiod, smbus; from gpiod.line import Bias, Direction, Value; assert callable(gpiod.Chip); assert callable(gpiod.LineSettings); assert callable(gpiod.request_lines); assert callable(gpiod.Chip.get_info); assert callable(gpiod.Chip.get_line_info); assert callable(smbus.SMBus); print("hardware_bindings=ready")'
```

The final Python command must print `hardware_bindings=ready`. Record the installed release identity and compare it with the downloaded
checkpoint commit. A successful installation of a different commit is a FAIL
for this campaign.

## 3.1 Refresh the operator login and prove control-socket authorization

Checkpoint 24 adds the validated non-root installer operator to the local `gonken-envctl` control group only. It does **not** grant that human account raw GPIO/I2C ownership. Supplementary groups do not change inside an already-running SSH shell, so disconnect and reconnect after a successful installation before judging environment CLI permissions.

```bash
exit
# reconnect from the administration workstation
ssh <operator>@<raspberry-pi>
```

Then run on the Pi:

```bash
id
getent group gonken-envctl
```

The fresh `id` output must include `gonken-envctl`. If it does not, **STOP** and collect installer/support evidence. Do not add the human operator to raw `gpio` or `i2c` as a workaround. The environment feature is still disabled by default at this point.

## 4. GPIO identity inventory before wiring or actuation

Checkpoint 24 preserves the checkpoint-23 rule and does not assume that a BCM number is the same thing as a
`/dev/gpiochip0` character-device line offset. Production adapters resolve
logical GPIOs by unique kernel line names and fail closed when the mapping is
missing or ambiguous.

Before connecting the room relay or PTT indicators, collect:

```bash
gpiodetect
gpioinfo --strict GPIO17
gpioinfo --strict GPIO22
gpioinfo --strict GPIO23
gpioinfo --strict GPIO27
gonken-agent wake status --json
gonken-agent env status --json
gonken-agent env health --json
```

Expected logical roles:

- GPIO17 — push-to-talk input;
- GPIO22 — wake-standby monitoring LED;
- GPIO23 — room-fan relay candidate;
- GPIO27 — recording LED.

**STOP and do not actuate** if a required GPIO line is absent, ambiguous, the
reported runtime identity is unresolved, or the physical header/wiring cannot be
matched confidently. Return the mapping output for diagnosis instead of
guessing a chip/offset.

## 5. Voice/audio and default `GonKen` wake campaign

First prove the ordinary wake path with the environment subsystem disabled if
necessary.

Run in one terminal:

```bash
journalctl -fu gonken-agent.service
```

Then perform repeated real voice trials:

1. Say `GonKen` and wait for `Yes?`.
2. Ask a short question.
3. Confirm local Qwen inference and audible Piper output.
4. Confirm the service returns to wake standby.
5. Repeat across representative distance/noise conditions and the speakers who
   will actually use the system.
6. Record missed intended wakes, benign false wakes, obvious self-triggering,
   wake-to-`Yes?` delay, and whether progress cues ever overlap the final answer.

Checkpoint 24 preserves checkpoint-23 host tests proving the bounded pipelined capture design, not real
microphone/STT recall. Real wake behavior is target evidence.

The GPIO22 monitoring LED, if wired per `HARDWARE_SETUP.md`, should be ON only
while continuous wake standby is active and OFF during the active turn. Its
visible physical behavior must be recorded separately from software state.

## 6. Manual foreground voice test

Stop the daemon so it releases the microphone:

```bash
sudo systemctl stop gonken-agent.service
gonken-agent talk --seconds 8
sudo systemctl start gonken-agent.service
```

Confirm microphone capture, transcription, local answer generation and audible
speech. For exact Bluetooth service-user diagnostics, follow `OPERATIONS.md`.

## 7. Push-to-talk recovery/privacy path

Wire only after power is removed and after reviewing `HARDWARE_SETUP.md`.
Candidate Pi header mapping is:

| Function | BCM | Physical pin |
|---|---:|---:|
| Push-to-talk button to GND | GPIO17 | 11 |
| Wake monitoring LED via resistor | GPIO22 | 15 |
| Recording LED via resistor | GPIO27 | 13 |

The PTT input uses an internal pull-up and active-low press semantics. LEDs must
use appropriate current-limiting resistors. Never feed 5 V into a GPIO.

Edit the existing site configuration carefully:

```bash
sudoedit /etc/gonken-agent/config.toml
```

Set the existing runtime mode to:

```toml
[runtime]
interaction_mode = "push_to_talk"
```

Do not create a duplicate TOML table if `[runtime]` already exists. Validate the
merged configuration before restart:

```bash
gonken-agent config show --effective --json
sudo systemctl restart gonken-agent.service
journalctl -u gonken-agent.service -b --no-pager -n 120
```

Physically verify:

- service starts only if GPIO17/GPIO27 resolve uniquely;
- recording LED is OFF at acquisition/idle;
- holding the button starts capture and recording indication;
- release completes the turn and the LED returns OFF;
- an excessive hold is bounded/discarded rather than capturing indefinitely;
- stop/restart/cleanup leaves the recording LED OFF.

Restore `interaction_mode = "wake_word"`, validate, restart, and verify normal
`GonKen` operation again.

## 7.1 Checkpoint-24 hard gate before any GPIO23 relay ON command

The first checkpoint-23 target campaign failed before relay actuation. Therefore **do not run `gonken-agent env fan on`** until all of these are true on checkpoint 24:

- the exact archive was verified and installed with `./bootstrap.sh --local-checkpoint`;
- the installer printed governed `INSTALLATION_COMPLETE`;
- the active immutable release matches the delivered checkpoint commit;
- the application-venv hardware-binding probe prints `hardware_bindings=ready`;
- `gonken-agent.service` no longer loops on `WAKE_LED_GPIO_DEPENDENCY_MISSING`;
- after reconnecting, `id` includes `gonken-envctl`;
- environment CLI access no longer fails with `ENV_UNAVAILABLE: PermissionError`;
- `gpioinfo --strict GPIO23` and GonKen runtime identity agree on one unique GPIO23 line;
- relay `COM`, `NO`, and `NC` remain unloaded until the explicit Stage-B unloaded test.

If any item fails, STOP and collect a fresh support bundle. Do not repair the immutable release in place.

## 8. Environment campaign — safest to riskiest

Read these documents before enabling actuation:

- `docs/HARDWARE_SETUP.md`
- `docs/ENVIRONMENT_CONTROL.md`
- `docs/SIMULATION.md`
- `docs/USER_SIMULATION_HIL_HANDOFF.md`
- `docs/ENVIRONMENT_ACCEPTANCE_RUN.md`

Use the staged sequence; a later stage must not be used to erase a failure in an
earlier one.

### Stage A — full simulation

Prove CLI, passive watch, MANUAL, AUTO, SEMI, stale/recovery, simulation-aware
voice wording, diagnostics, and support export without touching GPIO/I2C.
Follow the exact profile and commands in `USER_SIMULATION_HIL_HANDOFF.md`.

### Stage B — real relay/fan, manual only

The SHT31 may remain unavailable. Verify GPIO23 mapping, relay labels/polarity,
unloaded OFF→ON→OFF behavior, PENGLIN VBUS/GND continuity and no back-power
path before connecting the fan. Use an independent regulated 5 V fan supply and
start with the fan's physical speed selector on Low.

A software ON result is only a relay-power command result. Record separately
whether the relay changed electrically and whether the blades physically moved.

### Stage C — simulated sensor + real relay/fan

After Stage B passes, exercise AUTO/SEMI/hysteresis/dwell and simulated sensor
failure safe-OFF using the real relay/fan. The sensor evidence remains simulated.

### Stage D — real SHT31 + simulated actuator

When the SHT31 is available, first prove I2C address, CRC-valid readings,
staleness/recovery and plausible placement without switching the real fan.

### Stage E — full real

Only after Stages B and D pass independently, run real SHT31 + real actuator
MANUAL/SEMI/AUTO/DISABLED, unplug/replug sensor recovery, reboot/no-login and
combined voice controls.

The environment service may report relay logical state; it cannot prove fan
blade rotation because the current hardware has no tachometer/airflow/current
feedback.

## 9. M10.7 private environment evidence collector

First collect non-actuating evidence:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/environment_acceptance_runner.py \
  --output-dir /var/lib/gonken-environment/acceptance/$(date -u +%Y%m%dT%H%M%SZ)
```

After power-off wiring inspection, mapping verification, and physical
supervision, the explicit actuator campaign may use:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/environment_acceptance_runner.py \
  --output-dir /var/lib/gonken-environment/acceptance/$(date -u +%Y%m%dT%H%M%SZ)-actuation \
  --allow-actuation
```

Preserve:

```text
m10_7_evidence_manifest.json
m10_7_private_evidence_ledger.csv
private_evidence/
```

The runner is an evidence collector, not an acceptance oracle. Its manifest must keep `physical_acceptance_claimed=false` until the evidence is reviewed against the manual physical gates. `exit 0`, JSON READY, or a relay command cannot establish blade motion, relay polarity, PENGLIN correctness, SHT31 placement, or real wake/audio behavior.

## 10. Offline/network-boundary observation

Do not intentionally sever the only SSH path to a headless Pi. Perform this
only with local console access or a network arrangement that keeps
administrative LAN access while upstream Internet/DNS is unavailable.

Verify that loopback Ollama operation and normal already-provisioned voice use
continue without cloud access. Record:

```bash
ss -ltnp
ss -tpn
journalctl -u gonken-agent.service -b --no-pager -n 150
```

The goal is to confirm the expected local/loopback runtime boundary, not to
claim that the Pi can install/update without the network resources those
maintenance operations legitimately require.

## 11. Reboot, no-login, failure and recovery campaign

After primary voice/environment evidence is stable:

```bash
sudo reboot
```

Do not log in merely to start GonKen. After normal boot, collect:

```bash
systemctl is-enabled gonken-agent.service
systemctl is-active gonken-agent.service
systemctl is-enabled gonken-environment.service || true
systemctl is-active gonken-environment.service || true
gonken-agent status --json
gonken-agent wake status --json
journalctl -u gonken-agent.service -b --no-pager -n 150
```

Repeat a real `GonKen` interaction. Where the environment profile is enabled,
verify its documented boot SAFE-OFF and recovery behavior.

Also exercise only the failure cases that are safe for the current wiring:

- stop/start/restart `gonken-agent.service`;
- stop/start/restart `gonken-environment.service` when enabled;
- restart `ollama.service` and observe bounded recovery;
- disconnect/reconnect USB audio where applicable;
- Bluetooth-off-at-boot then reconnect where Bluetooth is in scope;
- sensor unplug/replug only after Stage D wiring has passed;
- preserve evidence before any destructive uninstall/reinstall campaign.

## 12. Update, rollback, uninstall and reinstall

Host tests cover update/rollback/uninstall logic, but target lifecycle evidence
must use real installed releases.

A first exact local-checkpoint installation may have **no previous validated
release** to roll back to. In that case, record rollback as
`BLOCKED_NO_PREVIOUS_VALIDATED_RELEASE`; do not manufacture a PASS. After a later
checkpoint/fix package is available, use the two real releases to exercise
forward update and rollback and then rerun only the affected target gates.

The maintained installed helpers are:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/update.sh
sudo /usr/local/lib/gonken-agent/current/maintenance/rollback.sh
sudo /usr/local/lib/gonken-agent/current/maintenance/uninstall.sh
```

`update.sh` normally targets the governed remote source. Do not run it in the
checkpoint-23 evidence campaign merely to change away from the tested package.
Use it when a specifically intended successor source/ref exists. Before
uninstall, collect support evidence. Normal uninstall keeps project data unless
its explicit purge contract is deliberately selected.

## 13. Research/evaluation gates that remain distinct from appliance mechanics

M7.1, M7.2 and M7.5 intentionally remain partial because synthetic fixtures are
not a substitute for the approved real lab corpus, factual-support/adversarial
model evaluation, and real-device performance campaign. The existing synthetic
smoke benchmark may be rerun as regression evidence:

```bash
python3 /usr/local/lib/gonken-agent/current/maintenance/benchmark_grounding.py \
  --output /tmp/gonken-grounding-smoke.json
```

If the installed maintenance payload does not expose that helper, run it from
the exact checkpoint checkout instead:

```bash
python3 scripts/benchmark_grounding.py --output /tmp/gonken-grounding-smoke.json
```

Do not label this synthetic output as real-lab evidence. If the approved lab
corpus/evaluation set is not available in the campaign, mark those evaluation
gates `BLOCKED_INPUT_NOT_AVAILABLE` and continue independent hardware work.

## 14. Performance/thermal observations

During sustained real operation record, where available:

```bash
free -m
vcgencmd get_throttled || true
ps -eo pid,comm,%cpu,rss --sort=-%cpu | head -n 25
systemctl status gonken-agent.service --no-pager -l
systemctl status gonken-environment.service --no-pager -l || true
```

The V09 environment target is average environment-daemon CPU <=5% and RSS <=50
MiB over a representative 30-minute steady run. Wake, STT/TTS and LLM latency
must be measured on the real Pi rather than inferred from host tests. A threshold
miss triggers diagnosis; do not weaken the criterion merely to obtain PASS.

## 15. Support/evidence bundle to upload

Collect the standard support bundle:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

Upload the following after the campaign, without editing them to make results
look cleaner:

1. the support ZIP printed by the collector;
2. `m10_7_evidence_manifest.json`;
3. `m10_7_private_evidence_ledger.csv`;
4. the `private_evidence/` directory (ZIP it if convenient);
5. GPIO mapping output for GPIO17/22/23/27;
6. exact checkpoint commit and installed release path;
7. manual observation notes for wake/audio/PTT/LED/relay/fan/sensor/reboot;
8. exact error output for every FAIL/BLOCKED/NEEDS_MANUAL_REVIEW item.

Raw audio is not required by default. Do not upload credentials, Wi-Fi
passphrases, or unrelated personal data.

## 16. Acceptance decision and continuation rule

The package is **ready for the Raspberry Pi target campaign** when its host gate
passes. It is not physically accepted until all acceptance-critical target rows
have fresh evidence at the required tier.

A final target PASS requires, as applicable:

- exact-checkpoint clean install and provenance;
- real wake, STT, local model, TTS and audio recovery;
- no-login reboot convergence;
- PTT/recording/wake indicators where in scope;
- observed offline runtime boundary;
- safe GPIO mapping and relay polarity;
- real fan start/stop observation;
- real SHT31/I2C/CRC/stale-recovery evidence when the sensor is available;
- MANUAL/SEMI/AUTO/DISABLED semantics on the real controller;
- failure/recovery and lifecycle evidence;
- support/evidence bundle integrity;
- no unresolved acceptance-critical defect.

This is not a promise that the first physical campaign will be error-free. The
engineering objective is to detect target-only defects, repair the smallest
correct layer, rerun affected host regressions, and repeat only the uncertain
physical gates until no acceptance-critical issue remains.

**Continuation instruction after upload:**

> Continue from checkpoint 23 using the uploaded Raspberry Pi target evidence.
> Verify the exact checkpoint-23 package/commit/config first; classify every
> result as host, simulation, hybrid, or physical evidence; repair only the
> smallest failed layer; rerun affected host regressions and only the uncertain
> target gates; do not restart architecture discovery or close M10.7 without
> real evidence.
