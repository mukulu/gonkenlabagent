# Raspberry Pi target acceptance campaign

This runbook is the authoritative **real-target** procedure for GonKenLab Agent
the current V09 comprehensive-closure checkpoint. Host CI, simulation, a clean ZIP, or a READY JSON file cannot
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

Copy the delivered checkpoint ZIP and its SHA-256 manifest to the Pi. Use the **exact filenames from the delivery message**; do not substitute remote `main`.

Verify the archive, extract it without discarding `.git`, enter the single extracted repository directory, and restore tracked modes/content because Python's ZIP extractor does not preserve Unix executable bits:

```bash
sha256sum -c <delivered-sha256-manifest>
rm -rf ~/gonken-target-checkpoint
mkdir -p ~/gonken-target-checkpoint
python3 -m zipfile -e <delivered-checkpoint>.zip ~/gonken-target-checkpoint
cd ~/gonken-target-checkpoint/<extracted-repository-directory>
git reset --hard HEAD
test -x ./bootstrap.sh
git rev-parse HEAD
git status --porcelain
git fsck --strict
python3 scripts/release_readiness.py --json --check
```

Acceptance conditions before installation:

- checksum verification passes;
- `git reset --hard HEAD` restores the exact committed modes/content after extraction;
- `./bootstrap.sh` is executable;
- the Git commit equals the commit printed in the delivery summary;
- `git status --porcelain` is empty;
- `git fsck --strict` succeeds;
- `release_readiness.py --check` reports `READY_FOR_TARGET_ACCEPTANCE` while target-only gates remain open.

If any identity/integrity check fails, **STOP**. Do not make an unrecorded in-place edit to force the package through acceptance.

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

The comprehensive-closure installer must converge its own prerequisites. Do not work around a failed install with `PYTHONPATH`, ad-hoc `pip install`, copied modules, manual ownership/group changes, or edits inside the immutable release. The release venv remains isolated and its allow-listed hardware-binding bridge must validate the required `gpiod` API with the immutable interpreter. SHT31 transport uses the stdlib Linux `i2c-dev` path rather than a Python `smbus` dependency.

`--local-checkpoint` is deliberate: it binds the installation source record to
the clean checkout's exact full Git commit. Normal production installs may use
the official remote source later; this acceptance campaign must not silently
switch revisions.

Do not manually preinstall Ollama, Whisper, Piper, Python packages, PipeWire, or
project virtual environments merely to make the installer pass. Preserve the
exact installer error if a governed step fails.

The installer now treats Raspberry Pi I2C enablement as a resumable prerequisite. On a first run it may intentionally stop with `I2C_REBOOT_REQUIRED` after enabling I2C because `/dev/i2c-1` cannot exist in the already-running boot. That is not a reason to patch the machine. Reboot the Pi, return to this same clean checkout, and rerun the same `./bootstrap.sh --local-checkpoint ...` command. The persisted step engine must resume and revalidate prior work rather than restarting blindly.

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
/usr/local/lib/gonken-agent/current/.venv/bin/python -c 'import gpiod; from gpiod.line import Bias, Direction, Value; assert callable(gpiod.Chip); assert callable(gpiod.LineSettings); assert callable(gpiod.request_lines); assert callable(gpiod.Chip.get_info); assert callable(gpiod.Chip.get_line_info); print("gpio_binding=ready")'
sudo /usr/local/lib/gonken-agent/current/maintenance/i2c_manager.py status --user gonken-env --require-ready
```

The Python command must print `gpio_binding=ready`, and the I2C manager must report bus 1/device access ready for `gonken-env`. Record the installed release identity and compare it with the downloaded
checkpoint commit. A successful installation of a different commit is a FAIL
for this campaign.

## 3.1 Refresh the operator login and prove control-socket authorization

The installer adds the validated non-root installer operator to the local `gonken-envctl` control group only. It does **not** grant that human account raw GPIO/I2C ownership. Supplementary groups do not change inside an already-running SSH shell, so disconnect and reconnect after a successful installation before judging environment CLI permissions.

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


### Checkpoint-32 current-release rule

Normal installation and operation must converge on the exact checkpoint being installed. The installer must not execute or revalidate older releases to decide whether the current release is healthy. Older release identities are retained only for explicit update/rollback bookkeeping; an operator-requested rollback is the only operation that intentionally promotes the recorded previous release.

Checkpoint 31 exposed a different defect: the new release executed Python after its immutable digest had been recorded, so interpreter cache files could change the payload before activation. Checkpoint 32 moves all executable smoke before sealing, removes transient bytecode/cache files, and uses static non-mutating checks after sealing. A `RELEASE_INVALID ... payload digest differs` error on checkpoint 32 is therefore a real current-release integrity failure: **STOP**, preserve the installer failure bundle, and do not delete/rewrite releases by hand.

## 4. GPIO identity inventory before wiring or actuation

The production GPIO contract does not assume that a BCM number is the same thing as a
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

Host tests prove the bounded pipelined capture design, not real
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

Do not use GonKen for physical actuation until the current exact checkpoint has reached governed `INSTALLATION_COMPLETE` and all prerequisite gates below are true:

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

## 8.1 Real SHT31 sensor acceptance before full-real control

Wire the sensor only with Pi power removed and use this exact planned mapping after confirming the breakout labels:

```text
Pi physical pin 1 (3.3 V)     -> SHT31 VCC/VIN
Pi physical pin 3 (GPIO2/SDA) -> SHT31 SDA
Pi physical pin 5 (GPIO3/SCL) -> SHT31 SCL
Pi physical pin 6 (GND)       -> SHT31 GND
```

Do not substitute a 5 V header pin. Inspect the actual breakout board for labels, regulator/level-shifter/pull-up details and address-select state. If its labels do not match, stop rather than guess.

After `INSTALLATION_COMPLETE`, prove the platform first:

```bash
ls -l /dev/i2c-1
sudo /usr/local/lib/gonken-agent/current/maintenance/i2c_manager.py status --user gonken-env --require-ready
```

Then discover the SHT31 using the production transaction path while the real fan actuator is still simulated/off:

```bash
sudo -u gonken-env /usr/local/lib/gonken-agent/current/.venv/bin/python \
  /usr/local/lib/gonken-agent/current/maintenance/sht31_diagnostic.py discover --bus 1
```

Exactly one of `0x44` or `0x45` must be validated. Run the default 100-read campaign at that exact address:

```bash
sudo -u gonken-env /usr/local/lib/gonken-agent/current/.venv/bin/python \
  /usr/local/lib/gonken-agent/current/maintenance/sht31_diagnostic.py campaign \
  --bus 1 --address 0x44 --reads 100
```

Substitute `0x45` only if discovery established `0x45`. The campaign must keep normal-use heater state off, validate every CRC frame, and report no transport/CRC/plausibility failures. Then select `real-sensor-simulated-actuator` with the proven address, start the environment service under supervision, and verify `gonken-agent env read --json`, stale/fault behavior and recovery before transitioning to `full-real`. A daemon reporting `TARGET_REAL_BACKENDS_UNVERIFIED` is correct before supervised full physical acceptance; backend names alone must never become `TARGET_PHYSICAL`.

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
current exact-package evidence campaign merely to change away from the tested package.
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

## 15. Single support/evidence ZIP to upload

Collect the standard support bundle. From checkpoint 42 onward this is the
primary target handoff artifact: it includes the ordinary support data plus a
sanitized non-actuating target manifest, platform/resource inventory, bounded
service-event code summaries and an evidence index.

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

If installation fails before the current release is usable, upload the
installer-owned failure ZIP printed by the installer instead. It carries the
same one-upload purpose for early failures: source/install provenance, target
preflight summaries, platform/resource inventory, bounded event summaries and
the target manifest when it can be collected.

Upload the ZIP without editing it to make results look cleaner. If a fact is
inherently manual, such as visible fan blade motion, relay indicator behavior,
sensor placement, wake recognition quality or reboot/no-login observation, add
short notes beside the ZIP. Do not create a second diagnostic package merely to
carry information that the collector now records automatically.

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

> Continue from the recorded comprehensive-closure checkpoint using the uploaded Raspberry Pi target evidence.
> Verify the exact delivered package/commit/config first; classify every
> result as host, simulation, hybrid, or physical evidence; repair only the
> smallest failed layer; rerun affected host regressions and only the uncertain
> target gates; do not restart architecture discovery or close M10.7 without
> real evidence.

## 7.2 Checkpoint-30 upgrade migration gate

Checkpoint 30 repairs a specific upgrade defect discovered while installing checkpoint 29 on a Pi that still had a valid pre-binding-bridge release active. The old release did not contain the later `hardware-bindings.json` contract, so checkpoint 29 incorrectly rejected that old release during reconciliation before switching to its already-valid new candidate.

For checkpoint 30 and later, **do not delete the old release, current symlink, activation journal, or create a binding manifest manually**. A legitimate upgrade from the recorded pre-bridge release should emit a bounded event such as:

```text
[OK] code=RELEASE_LEGACY_TRANSITION_SOURCE commit=<old-commit> ...
```

and continue to validate the new candidate under the full current binding-manifest/API contract. A new/bridge-era candidate with a missing or corrupt manifest must still fail closed.

If `RELEASE_BINDING_MANIFEST` occurs again, preserve the installer-owned failure bundle. The message now includes the release commit being validated; return that evidence rather than editing the immutable release. Do not proceed to GonKen relay/voice acceptance until the installer reaches governed `INSTALLATION_COMPLETE`.


## 7.3 Checkpoint-31 install-convergence gate

Checkpoint 30 established more target evidence than its final error implied. The Pi successfully emitted `ACTIVATION_COMPLETE` for commit `34aee184...`; the later `RELEASE_BINDING_MANIFEST` named unrelated historical commit `3b25b81...` and occurred during stale-release cleanup. A later local rerun correctly treated activation as satisfied, authorized `gonkenlab`, passed identity preflight and reached I2C enablement. The support bundle collected immediately afterward showed the checkpoint-30 binding bridge and `/dev/i2c-1` ready. These facts are preserved; do not restart hardware discovery.

Checkpoint 31 changes the required operator interpretation:

- `RELEASE_PRUNE_SKIPPED` for a stale non-current/non-previous release is a bounded cleanup warning, not evidence that a completed activation failed. Preserve it for maintenance review.
- I2C enablement waits for device convergence. If a reboot is still required, the installer must emit `I2C_REBOOT_REQUIRED` / `INSTALLATION_PAUSED` and exit with the planned pause state. Reboot and rerun the **same exact checkpoint**. No manual boot-config edit or step-state edit is permitted.
- Bluetooth pairing is not complete for a headset deployment until the exact service user can enumerate either a Bluetooth capture source or exactly one direct ALSA capture fallback. `BLUETOOTH_INPUT_UNAVAILABLE` and `AUDIO_INPUT_AMBIGUOUS` are early prerequisite failures, not reasons to wait for the final appliance timeout.
- Appliance readiness belongs to the exact immutable release. A stale `ready.json` from the previous release must not satisfy the current release.

The target gate remains `INSTALLATION_COMPLETE`. Only after that token is observed should the operator reconnect SSH for refreshed `gonken-envctl` membership and proceed to simulation, GonKen CLI fan OFF/ON/OFF, real SHT31 discovery/read campaign, full-real controller and voice/wake acceptance.

## Checkpoint 33 convergence note — same-commit rerun, optional Bluetooth and Pi5 GPIO identity

Checkpoint 33 supersedes checkpoint-32 target retry instructions for the next campaign. Normal installation/runtime health is scoped to the requested/current release; historical releases are not executed or revalidated except during an explicit operator rollback.

A requested Bluetooth headset is a preference, not a mandatory core dependency. If the headset is busy/offline but the `gonken-agent` service user can prove exactly one direct capture route and one direct non-HDMI playback route, installation may continue and should report `BLUETOOTH_OPTIONAL_UNAVAILABLE` plus `AUDIO_DIRECT_FALLBACK_READY`. Do not treat that warning as failure. If no deterministic fallback exists, or several plausible devices exist, stop and return the bounded audio error rather than selecting a device manually.

A repeated install of the same commit must not stop merely because Python generated cache files after activation. Checkpoint 33 suppresses such writes and can remove only recognized Python cache artifacts before revalidating the current release. `RELEASE_ACTIVE_INVALID` remains a real stop for authoritative payload drift and must not be bypassed manually.

On Raspberry Pi 5, GPIO17/GPIO22/GPIO23/GPIO27 line-name duplicates across unrelated gpiochips may be disambiguated only by a unique chip labelled `pinctrl-rp1`; do not hard-code a gpiochip number. A genuinely ambiguous or absent header mapping remains a STOP condition.

## Checkpoint 34 convergence note — early Pi5 GPIO identity and transport-neutral audio

Checkpoint 34 supersedes checkpoint-33 target retry instructions. The checkpoint-33 target run built and activated the current release and passed target identity, I2C, runtime bindings, environment service, Ollama, Whisper, Piper, speech smoke, application service, Bluetooth/autoconnect and runtime-context checks. It then spent the final readiness window reporting `WAKE_LED_GPIO_LINE_AMBIGUOUS` for GPIO22. The next package therefore proves the Pi5 header mapping **before** environment/application readiness.

After `target_runtime_bindings`, expect the non-actuating `target_gpio_identity` installer step. It inspects gpiochip metadata only and must resolve GPIO17, GPIO22, GPIO23 and GPIO27 to one coherent Pi header controller. It does not request a line and cannot toggle the fan, PTT button or LEDs. A valid result records `GPIO_HEADER_RESOLVED`; an unresolved/ambiguous result is a STOP condition and should name bounded candidate metadata. Do not work around it with `gpioset`, a hard-coded `/dev/gpiochip0`, or a manual line offset inside the GonKen configuration.

The resolver is shared by PTT, wake indication and the environment relay. It may use a globally unique line name, unique RP1 controller metadata, or a unique coherent header topology containing the project header GPIO signature. It never assumes BCM equals a character-device offset.

Requested Bluetooth remains a preference. If it is busy/offline but exactly one direct USB/wired capture route and one direct non-HDMI playback route are proven, installation may continue with warnings and later Bluetooth autoconnect. Zero or ambiguous fallback devices remain a STOP condition. Runtime-context validation is transport-neutral: it validates a usable audio runtime rather than requiring PipeWire solely because Bluetooth was requested.

Repeated installation of the same checkpoint must remain idempotent after service/runtime execution. Standard Python `__pycache__` bytecode derivatives are outside the authoritative immutable payload; source/config/executable/manifest changes are not. Do not manually delete or rewrite `/usr/local/lib/gonken-agent/current` if an authoritative integrity error occurs.

Only proceed to the integrated M10.24 hardware/voice campaign after the exact checkpoint reaches `INSTALLATION_COMPLETE`.

## Checkpoint 43 exact-package convergence campaign

Checkpoint 43 is the first package after the 2026-09-17 target attempt that reached final appliance readiness and then failed on service-context audio capture. It also consolidates installer-failure and normal support evidence. The package remains a **release candidate for target testing**, not a physical PASS.

### A. Install only the exact qualified archive

Extract the delivered checkpoint-43 ZIP including `.git`, enter its repository root, and verify the documented SHA-256 from the checkpoint report. Use the local-checkpoint route so the target source record is bound to the exact delivered commit:

If Bluetooth audio is intentionally selected, set the target's configured selector explicitly rather than copying a device identity from another installation:

```bash
export GONKEN_BLUETOOTH_DEVICE="<YOUR-BLUETOOTH-DEVICE-MAC>"
./bootstrap.sh --local-checkpoint --bluetooth-audio --bluetooth-device "$GONKEN_BLUETOOTH_DEVICE"
```

If Bluetooth is not part of the intended target profile, omit the Bluetooth options. Preserve the same resolved install command for reruns on that target.

If the installer intentionally reports `I2C_REBOOT_REQUIRED`, reboot once, return to the same extracted checkpoint and rerun the exact same command. Do not delete install state, immutable releases or model files merely to make the rerun look clean.

### B. Failure handling is one-ZIP-first

If any installer step fails, the terminal should print one operator-accessible evidence ZIP. Upload that ZIP first. Do not run `collect-support.sh` a second time unless `evidence_index.json` says canonical support collection was unavailable. The combined archive must identify the current installer failure separately from historical service-code counts.

A failure to create or return an operator-readable ZIP is itself a checkpoint-43 defect; record the terminal output and location/ownership observed.

### C. Required installation-success token

Do not begin integrated relay/fan/SHT31 acceptance until the installer prints:

```text
[READY] code=INSTALLATION_COMPLETE ... wake_phrase=GonKen
```

`systemctl is-active gonken-agent.service` alone is insufficient. While waiting, a fresh `APPLIANCE_DEPENDENCY_WAIT` line should identify the causal component/reason. The final READY must belong to the current release, current boot and current service PID.

### D. Immediate post-install convergence checks

After `INSTALLATION_COMPLETE`:

1. disconnect/reconnect SSH if instructed so `gonken-envctl` supplementary membership is refreshed;
2. confirm `gonken-agent.service` remains enabled and semantically ready without an interactive desktop login;
3. say `GonKen` and complete at least one wake -> capture -> Whisper -> local Ollama -> Piper -> speaker transaction;
4. repeat an immediate same-commit installer invocation and confirm it converges without mutating/rebuilding the active immutable release incorrectly;
5. reboot and repeat the no-login service/voice check before changing the environment profile;
6. collect a normal support ZIP and retain it as the successful-install target evidence artifact.

### E. Environment commissioning ladder

Proceed from lower-risk to higher-risk evidence and do not collapse the stages:

1. `full-simulation` — controller/IPC/CLI/voice semantics only;
2. `real-sensor-simulated-actuator` — SHT31 software/device/read quality without fan actuation;
3. `sensor-deferred-relay` only when supervised relay/fan testing is intended;
4. `full-real` only after SHT31 and relay wiring/polarity/GPIO identity prerequisites are separately satisfied.

For a real SHT31, run the governed targeted diagnostic and record the proven `0x44` or `0x45` address. For real relay/fan work, preserve the established GPIO23/header mapping evidence and repeat safe OFF -> ON -> OFF supervision. Never infer blade motion from `relay_logical_state=on`. Never claim software fan-speed control.

### F. Lifecycle acceptance sequence

For the exact checkpoint-43 archive, record separate results for: fresh/dirty-state install convergence; immediate same-commit rerun; reboot/no-login at least three times; USB capture/playback; configured Bluetooth preference plus deterministic direct fallback; wake/listen/STT/model/TTS transaction; SHT31 campaign; relay/fan cycles; MANUAL/SEMI/AUTOMATIC/DISABLED semantics; sensor unplug/recovery; service restart; audio hotplug/re-enumeration; update/rollback/reinstall when a suitable prior/newer governed release is available; and the final support/evidence ZIP privacy/integrity review.

Host, simulation and target-shadow PASS rows do not close these physical gates.

## Checkpoint 44 V04 foundation target campaign

Checkpoint 44 supersedes the Checkpoint-43 package for the next target run. It remains a **target-testing checkpoint**, not physical acceptance. Its primary goal is to prove that the package itself now converges the release-readiness identity and environment configuration/permission state that previously required manual intervention.

### A. Recommended first run: real SHT31, simulated room-fan actuator

Use the exact qualified Checkpoint-44 archive and verify its delivered commit/tag/SHA before running. From the clean extracted repository:

```bash
./bootstrap.sh --local-checkpoint \
  --environment-profile real-sensor-simulated-actuator \
  --sensor-address 0x44
```

If Bluetooth is intentionally required, add only the target's own selector:

```bash
export GONKEN_BLUETOOTH_DEVICE="<YOUR-BLUETOOTH-DEVICE-MAC>"
./bootstrap.sh --local-checkpoint \
  --environment-profile real-sensor-simulated-actuator \
  --sensor-address 0x44 \
  --bluetooth-audio --bluetooth-device "$GONKEN_BLUETOOTH_DEVICE"
```

Do **not** pre-create `/etc/gonken-agent/config.toml`, run `chown`/`chmod` on the environment policy, delete the prior Checkpoint-43 test drop-in, run `systemctl reset-failed`, or manually enable/restart `gonken-environment.service` before this test. Those are now package responsibilities and the target run must prove that convergence.

If the installer reports `I2C_REBOOT_REQUIRED`, reboot once and rerun the exact same command from the exact same package. Preserve installer state.

### B. Expected independent component reporting

A successful safe-profile install should report voice and inference independently from environment/sensor/fan/tool status. For this profile, expected semantics are broadly:

```text
[COMPONENT] id=voice_conversation status=READY ...
[COMPONENT] id=ollama_inference status=READY ...
[COMPONENT] id=environment_controller status=READY profile=real-sensor-simulated-actuator ...
[COMPONENT] id=temperature_humidity_sensor status=READY backend=sht31 ... physical_acceptance=false
[COMPONENT] id=room_fan_control status=NOT_TESTED ... backend=simulated ...
[COMPONENT] id=llm_environment_tool_broker status=NOT_COMMISSIONED ...
[READY] code=INSTALLATION_COMPLETE ...
```

The room fan must remain untouched by this profile. `NOT_TESTED` for physical room-fan control is correct, not a failure.

### C. Post-install checks for this checkpoint

After `INSTALLATION_COMPLETE`, verify the independently commissioned sensor path:

```bash
systemctl is-enabled gonken-environment.service
gonken-agent env status
gonken-agent env health
gonken-agent env temperature
gonken-agent env humidity
gonken-agent env watch --interval 2 --count 10
```

The environment service should be enabled/active and the commands should return daemon-owned SHT31 state. This still does not establish sensor placement accuracy or physical room-fan acceptance.

### D. Real relay/fan remains a separate supervised gate

Do not change the first run to `full-real` merely to make the fan participate. If a real-relay profile is selected before supervised commissioning, Checkpoint 44 is expected to pause with `ENVIRONMENT_PHYSICAL_COMMISSION_REQUIRED`. Later V04 work must complete the typed tool broker and the supervised GPIO23/PENGLIN/ELUTENG acceptance sequence before physical fan control can be promoted.

### E. Failure evidence

If any step fails, upload the **single combined evidence ZIP** printed by the installer. Do not manually repair the target and then report only the post-repair state; the failure archive is needed to test whether Checkpoint 44 correctly localized the remaining dependency.
