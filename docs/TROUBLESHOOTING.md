# V09 troubleshooting guide

This guide starts from observed symptoms and points to the least risky next diagnostic step. It preserves the same evidence boundary used by the V09 implementation: host output, simulation output, daemon JSON, and exit code 0 are not physical Raspberry Pi acceptance.

## 1. Basic state checks

Run these first:

```bash
gonken-agent status --json
gonken-agent wake status --json
gonken-agent env status --json
gonken-agent env health --json
gonken-agent env probe --json
```

If the environment service is disabled, enable it only through the static environment profile after reviewing hardware readiness. Do not bypass the daemon by writing GPIO/I2C directly.

## 2. “Environment commands fail”

Likely causes:

- `gonken-environment.service` is not running;
- the socket path does not match `extensions.environment.socket_path`;
- the service account or client group was not provisioned;
- the feature is disabled in static configuration;
- a policy file is corrupt.

Next checks:

```bash
gonken-agent env health --json
gonken-agent env status --json
sudo systemctl status gonken-environment.service --no-pager
sudo journalctl -u gonken-environment.service -b --no-pager -n 80
```

## 3. “Temperature or humidity is unavailable”

In physical mode, check I2C enablement, service permissions, SHT31 address, and CRC-valid reads. In simulation mode, check whether a simulated sensor fault was injected.

```bash
gonken-agent env read --json
gonken-agent env simulate status --json
```

A simulated value is not SHT31 evidence. If physical acceptance is being attempted and JSON reports `sensor_backend=simulated` or `TARGET_HYBRID_SENSOR_SIMULATED`, the physical SHT31 gate remains open.

## 4. “Fan command says OK but the blades did not move”

V09 cannot observe blade motion. It can report only daemon/relay-power command state. Check:

- ELUTENG inline physical speed switch;
- PENGLIN USB continuity/polarity;
- relay COM/NO wiring;
- relay active polarity;
- fan USB power path;
- whether actuator backend is simulated.

Do not interpret `fan_power=on` as measured blade motion. Use supervised M10.7 fan-cycle evidence.

## 5. “Automatic mode is not starting the fan”

Check the mode, thresholds, sensor quality, control temperature, dwell timers, and latest transition reason:

```bash
gonken-agent env status --json
gonken-agent env policy show --json
gonken-agent env watch --interval 2 --count 5
```

SEMI_AUTOMATIC never starts merely because temperature rises. MANUAL never changes fan state because of temperature. AUTOMATIC requires valid sensor recovery samples and dwell conditions.

## 6. “Physical acceptance runner reports BLOCKED”

If the runner reports:

```text
SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED
```

then a simulated backend appeared in JSON returned by a physical-evidence command. Preserve the files because they may be useful for diagnosis, but do not mark the physical gate PASS. Use a full physical profile and rerun the affected step only after confirming that both sensor and actuator backends are physical.

## 7. “Wake phrase is unreliable”

The packaged default wake phrase is `GonKen`, and `Hey GonKen` is retained as a backward-compatible alias. `gonken-agent wake status --json` should report `capture.mode=pipelined` and `capture_continues_during_transcription=true`. The production standby path uses a bounded newest-wins queue so synchronous Whisper work no longer intentionally stops microphone capture of the next wake window.

Check:

```bash
gonken-agent wake status --json
sudo journalctl -u gonken-agent.service -b --no-pager -n 160
gpiodetect
gpioinfo --strict GPIO22
```

If the journal reports dropped wake windows, record the count and recognition latency; do not increase the queue without measuring CPU/RAM/thermal effects. If the service reports a wake-monitoring GPIO error, correct permissions/mapping rather than bypassing the privacy indicator. Host matcher/pipeline tests are not real microphone evidence. For target evaluation, use the Raspberry Pi acceptance runbook, record intended detections, misses, benign false wakes, wake-to-`Yes?` latency, accent/distance/noise conditions, and preserve logs without retaining raw transcripts by default.

## 7A. “Push-to-talk does not record or the recording LED is wrong”

PTT mode requires a unique libgpiod line named for the configured button and recording LED (GPIO17/GPIO27 by default). The button is active-low with an internal pull-up. Do not work around a mapping failure by hard-coding a guessed gpiochip offset.

Check:

```bash
gpiodetect
gpioinfo --strict GPIO17
gpioinfo --strict GPIO27
sudo journalctl -u gonken-agent.service -b --no-pager -n 160
```

Expected physical semantics: the recording LED is OFF at boot/idle, ON only while the button is held and microphone capture is active, then OFF before transcription/inference/TTS. A press longer than the 30-second bound is discarded. If the LED remains on after service stop/crash or the button reads inverted, stop target acceptance and return the mapping/wiring evidence; do not reinterpret the LED as a “thinking” indicator.

## 8. “Progress cue or transition announcement overlaps speech”

The host implementation has a single voice-runtime owner for progress cues and transition announcements. If target audio overlaps, preserve:

```bash
gonken-agent wake status --json
sudo journalctl -u gonken-agent.service -b --no-pager -n 120
```

Do not add ad hoc shell playback or multiple Piper/audio owners. Fix the voice arbitration layer.


## Installer reaches `WAKE_LED_GPIO_DEPENDENCY_MISSING`

**Symptom:** installation waits while `gonken-agent.service` repeatedly reports `code=WAKE_LED_GPIO_DEPENDENCY_MISSING` and `python3-libgpiod_is_not_importable`.

Run only diagnostic imports:

```bash
python3 -c 'import gpiod; print("system-gpiod=ready")'
/usr/local/lib/gonken-agent/current/.venv/bin/python -c 'import gpiod; print("release-gpiod=ready")'
sudo /usr/local/lib/gonken-agent/current/maintenance/i2c_manager.py status --user gonken-env --require-ready
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

On the comprehensive-closure checkpoints, release validation must fail closed before appliance readiness if the immutable interpreter cannot use the required APIs. If system Python succeeds but release Python fails, do **not** set `PYTHONPATH`, use `pip` workarounds, copy modules, or edit the immutable release. Preserve the support bundle and return it for diagnosis. Physical relay testing remains blocked.

## `gonken-agent env ...` reports `ENV_UNAVAILABLE: PermissionError`

Run:

```bash
id
getent group gonken-envctl
```

The installer adds the validated non-root invoking installer account to `gonken-envctl` only. Existing shells retain their old supplementary groups, so disconnect and reconnect SSH after successful installation. If a fresh login still lacks `gonken-envctl`, STOP and collect support evidence. Do not grant the human operator raw `gpio` or `i2c` as a workaround.

## SHT31/I2C installer or sensor diagnostic problems

If installation stops with `I2C_REBOOT_REQUIRED`, reboot and rerun the same exact-checkpoint installer. Do not hand-edit boot configuration or mark the step complete. The resumed installer must revalidate `/dev/i2c-1` and `gonken-env` access.

If the platform is ready but the sensor is unavailable, use the governed sequence rather than guessing from `i2cdetect` alone:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/i2c_manager.py status --user gonken-env --require-ready
sudo -u gonken-env /usr/local/lib/gonken-agent/current/.venv/bin/python \
  /usr/local/lib/gonken-agent/current/maintenance/sht31_diagnostic.py discover --bus 1
```

`SENSOR_NOT_FOUND` means neither supported SHT31 address produced a valid status/read transaction. `SENSOR_ADDRESS_AMBIGUOUS` means both `0x44` and `0x45` appeared valid and configuration must not guess. CRC/transport/heater-state failures must be fixed at wiring/bus/sensor/driver level before controller or voice acceptance.

## `RELEASE_BINDING_MANIFEST` during release activation

The release commit named in the error matters.

- If the named release is the **new candidate**, treat it as a real candidate-construction/binding-provenance failure. Do not bypass the manifest, copy modules manually, edit the immutable release, or weaken validation.
- If upgrading from an older **pre-binding-bridge release**, checkpoint 30+ should recognize that release only when it is already bound to trusted activation state and should emit `RELEASE_LEGACY_TRANSITION_SOURCE` while migrating away from it. The new candidate remains strictly validated.
- A bridge-era release with a missing/corrupt manifest is never considered legacy simply because the file is absent.

On any failure, keep the active release/journal intact and collect the installer-owned failure bundle. Re-running an unchanged older checkpoint will not repair a deterministic contract mismatch.


## `RELEASE_PRUNE_SKIPPED` after a successful activation

Checkpoint 31 treats stale-release cleanup as best-effort maintenance. If the new release has already reached `ACTIVATION_COMPLETE` and an unrelated stale historical release is malformed or cannot be removed, the installer may emit `RELEASE_PRUNE_SKIPPED`. Do not edit the active release or fabricate a binding manifest for the stale release. Preserve the warning/support evidence; the current/previous journal releases remain protected.

## `I2C_REBOOT_REQUIRED` / `INSTALLATION_PAUSED`

Checkpoint 31 distinguishes an expected boot transition from a product error. After requesting Raspberry Pi I2C enablement it waits for `/dev/i2c-1`. If the device still requires a reboot, the expected terminal state is `PAUSED`, not `INSTALL_ACTION`. Reboot, reconnect, return to the same exact checkpoint directory and rerun the same installer command. A planned pause should not create an installer-failure bundle.

## `BLUETOOTH_INPUT_UNAVAILABLE` or `AUDIO_INPUT_AMBIGUOUS`

When `--bluetooth-audio` is requested, checkpoint 31 proves an input route before the final appliance-readiness wait. `BLUETOOTH_INPUT_UNAVAILABLE` means the connected headset exposes playback but no Bluetooth HFP/HSP capture source and the service user cannot enumerate one deterministic direct ALSA capture fallback. `AUDIO_INPUT_AMBIGUOUS` means more than one direct capture card could be chosen. Keep the requested headset powered and expose its headset microphone profile, or connect exactly one intended USB microphone; do not grant broad device permissions or bypass the check.

## Service appears ready immediately after an upgrade

Readiness is now tied to the exact immutable release commit. A previous release's `/run/gonken-agent/ready.json` is intentionally ignored. The new current release must restart and create a fresh readiness record. If the commit in the ready record does not match the current release, collect support evidence instead of copying or editing the file.


### `RELEASE_INVALID` / `release payload digest differs`

This is a current-release integrity failure, not evidence that an older release must be made compatible. Checkpoint 31 could create this condition itself by running Python from the immutable tree after recording its payload digest, allowing bytecode/cache files to appear. Checkpoint 32 completes executable smoke before sealing, purges transient caches, records a path-level payload manifest, and limits post-seal installation/activation checks to non-mutating static validation of the current candidate/current release.

Do not delete historical releases, fabricate manifests, thaw the active tree, or edit `/usr/local/lib/gonken-agent/current`. Preserve the installer failure bundle. Checkpoint-32 errors include bounded changed/missing/unexpected path hints when the payload manifest can localize the drift.

Older releases are not normal runtime dependencies. They remain only as release history / explicit rollback candidates.

## Checkpoint 34: installer or service reports `WAKE_LED_GPIO_LINE_AMBIGUOUS`

Checkpoint 33 demonstrated this failure on the real Raspberry Pi 5 after every earlier installer prerequisite had passed. Checkpoint 34 moves GPIO identity into an earlier non-actuating installer gate and uses the same shared resolver for PTT GPIO17, wake GPIO22, relay GPIO23 and recording LED GPIO27.

Safe diagnostics:

```bash
gpiodetect
gpioinfo --strict GPIO17
gpioinfo --strict GPIO22
gpioinfo --strict GPIO23
gpioinfo --strict GPIO27
```

Do not assume `/dev/gpiochip0` from documentation alone. The checkpoint-34 resolver first accepts a globally unique line name, then a unique RP1 metadata match, then a unique coherent header topology. If multiple coherent header-like chips remain, it fails closed. The installer should now stop at `target_gpio_identity` with bounded candidate details instead of waiting for `APPLIANCE_NOT_READY`.

Do not disable the wake indicator, hard-code an offset, or manually edit the immutable release merely to get readiness. Preserve the installer failure bundle and support evidence.

## Checkpoint 34: same-commit reinstall after runtime activity

Checkpoint 34 defines one immutable-authority boundary for payload hashing, path manifests, ownership and mutability. A real non-symlink `__pycache__` tree containing only `.pyc`/`.pyo` derivatives is outside that authority; it must not make a valid current release fail on rerun. A symlink named `__pycache__`, top-level bytecode, non-bytecode files hidden in cache directories, and any source/config/executable/manifest difference remain authoritative and fail closed.

`RELEASE_ACTIVE_INVALID` therefore remains meaningful for actual current-release drift. It is not a comparison with historical releases. Historical releases are not executed or revalidated during normal install/runtime and matter only for explicit rollback/update bookkeeping.

## Checkpoint 34: requested Bluetooth is unavailable but USB audio works

`--bluetooth-audio` means “prefer/configure Bluetooth,” not “make Bluetooth mandatory.” If the requested headset is busy or offline and the service user can prove exactly one direct USB/wired capture device plus one direct non-HDMI playback device, the installer may continue and report bounded Bluetooth warnings with `AUDIO_DIRECT_FALLBACK_READY`.

If direct audio is missing or ambiguous, the installer still fails rather than guessing. Keep only the intended USB/wired audio devices connected or restore the preferred Bluetooth device, then rerun the same checkpoint.

## Checkpoint 43: service is active but installation reports audio/readiness failure

Treat this as a semantic-readiness problem, not as proof that systemd is broken. The voice process can be `active (running)` while waiting for an audio, GPIO, speech-model or local-model dependency.

1. Read the current installer line containing `APPLIANCE_DEPENDENCY_WAIT`. Record its `component`, `dependency_code` and `recoverable` value.
2. If installation has failed, use the **single evidence archive path printed by the installer**. Do not immediately run a second support command; the combined failure archive already attempts canonical support collection and records omitted sections with reasons.
3. Do not substitute the interactive login user's `wpctl`/PipeWire success for the `gonken-agent` service identity. Check `runtime_bindings.json -> audio_session` and `voice_readiness` in the evidence archive.
4. `AUDIO_CAPTURE_PERMISSION_DENIED` is treated as a configuration/authority error and should not be retried forever. Repair the service account/device/runtime permission contract.
5. `AUDIO_SERVER_UNAVAILABLE` means the service user's PipeWire/Pulse endpoint is unavailable; inspect the runtime-context evidence instead of switching to a desktop user's runtime directory.
6. `AUDIO_CAPTURE_DEVICE_UNAVAILABLE` means the selected physical capture route is absent. Restore the intended USB/wired microphone or the configured Bluetooth headset/profile; do not hard-code a transient ALSA card number.
7. `AUDIO_CAPTURE_DEVICE_BUSY` means another owner is holding the path. Remove the conflict rather than broadening privileges.
8. `AUDIO_CAPTURE_WAV_INVALID` means capture bytes did not produce a valid canonical WAV at the application boundary. Preserve the evidence archive; do not manually manufacture a WAV or mark READY.
9. A generic ALSA/backend failure remains a STOP condition if deterministic fallback cannot be proven.

Checkpoint 43's PipeWire capture path records bounded raw signed-16-bit mono PCM and then writes the canonical WAV container itself before validation. ALSA and Bluetooth/direct fallback semantics remain intact. The change is intended to remove dependence on an interrupted encoded-WAV finalization path, but only the exact Raspberry Pi campaign can prove the physical repair.

### Historical reason codes versus current causal failure

A support/failure archive may contain counts from earlier processes or attempts. Do not treat the most frequent or oldest code as the current cause. Check the current semantic readiness record and installer event first; historical failure codes are retained as chronology, not silently promoted to the present root cause.
