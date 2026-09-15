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
python3 -c 'import gpiod, smbus; print("system-bindings=ready")'
/usr/local/lib/gonken-agent/current/.venv/bin/python -c 'import gpiod, smbus; print("release-bindings=ready")'
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

On checkpoint 24, release validation must fail closed before appliance readiness if the immutable interpreter cannot use the required APIs. If system Python succeeds but release Python fails, do **not** set `PYTHONPATH`, use `pip` workarounds, copy modules, or edit the immutable release. Preserve the support bundle and return it for diagnosis. Physical relay testing remains blocked.

## `gonken-agent env ...` reports `ENV_UNAVAILABLE: PermissionError`

Run:

```bash
id
getent group gonken-envctl
```

Checkpoint 24 adds the validated non-root invoking installer account to `gonken-envctl` only. Existing shells retain their old supplementary groups, so disconnect and reconnect SSH after successful installation. If a fresh login still lacks `gonken-envctl`, STOP and collect support evidence. Do not grant the human operator raw `gpio` or `i2c` as a workaround.
