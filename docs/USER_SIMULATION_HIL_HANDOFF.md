# V09 user simulation and sensor-deferred HIL handoff

**Release-candidate label:** `READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL`

This label means the package has passed its host/software gate for supervised user simulation and sensor-deferred HIL. It is not Raspberry Pi physical acceptance. In particular, it does not prove SHT31 readings, Pi 5 GPIO mapping, relay polarity, PENGLIN continuity, ELUTENG blade motion, real `GonKen` wake performance, or real audio timing. M10.7 remains open until target evidence is collected and reviewed.

Use the stages below in order. Do not skip the safety prerequisites in [HARDWARE_SETUP.md](HARDWARE_SETUP.md).

## 1. Before target testing

After installing the exact checkpoint with `./bootstrap.sh --local-checkpoint`, do not begin room-relay testing until the installer prints governed `INSTALLATION_COMPLETE`. Confirm the active immutable interpreter can see the target bindings:

```bash
gonken-agent status --json
gonken-agent wake status --json
/usr/local/lib/gonken-agent/current/.venv/bin/python -c 'import gpiod, smbus; print("hardware_bindings=ready")'
```

After installation, disconnect and reconnect the non-root operator login so its new `gonken-envctl` membership is active, then run `id` and `getent group gonken-envctl`. The environment subsystem remains disabled by default; profile activation is a later supervised step.

## 2. Stage A — full simulation, no room hardware required

Use this static environment profile:

```toml
[extensions.environment]
enabled = true
sensor_backend = "simulated"
relay_backend = "simulated"
simulation_runtime_control_enabled = true
```

Restart the environment service, then verify provenance before injecting any value:

```bash
sudo systemctl restart gonken-environment.service
gonken-agent env simulate status --json
gonken-agent env status --json
```

Expected boundary:

```text
sensor_backend=simulated
actuator_backend=simulated
evidence_mode=HOST_SIMULATION
physical_evidence=false
```

`HOST_SIMULATION` is the daemon's current full-simulation backend token; it does not assert where the process is running. The target evidence collector records the Raspberry Pi platform identity separately. In every case, full simulation remains non-physical evidence.

Open a passive monitor in one terminal:

```bash
gonken-agent env watch --interval 1
```

In another terminal, exercise automatic control:

```bash
gonken-agent env policy set --mode automatic --start-c 28 --stop-c 26.5
gonken-agent env simulate sensor set --temperature-c 27 --humidity-pct 50
gonken-agent env simulate sensor set --temperature-c 29 --humidity-pct 50
gonken-agent env simulate sensor set --temperature-c 27 --humidity-pct 50
gonken-agent env simulate sensor set --temperature-c 26 --humidity-pct 50
```

The controller uses a median of recent valid samples, so a single low sample may not stop an already-running automatic cycle immediately. This is expected anti-chatter behavior.

Exercise semi-automatic behavior:

```bash
gonken-agent env mode set semi-automatic
gonken-agent env simulate sensor set --temperature-c 30 --humidity-pct 50
gonken-agent env fan on
gonken-agent env simulate sensor set --temperature-c 26 --humidity-pct 50
```

Semi-automatic mode may auto-stop an explicitly started run, but it must not auto-start again merely because the simulated temperature later rises.

Exercise a sensor fault and recovery:

```bash
gonken-agent env mode set automatic
gonken-agent env simulate sensor stale --age-seconds 30
gonken-agent env simulate sensor recover --temperature-c 27 --humidity-pct 50
```

No Stage-A output is physical acceptance.

## 3. Stage B — real relay/fan manual test, SHT31 still absent

Read [HARDWARE_SETUP.md](HARDWARE_SETUP.md) in full before this stage. Power-off inspection, relay logic verification, COM/NO wiring, PENGLIN continuity/polarity checks, an independent regulated 5 V fan supply, and an unloaded relay test come first.

The runtime uses logical BCM23 but no longer assumes that BCM23 is `/dev/gpiochip0` line offset `23`. The production libgpiod adapter scans the kernel gpiochip metadata for a **unique line named `GPIO23`** and fails closed if that identity is missing or ambiguous. Before any actuation, collect the target mapping evidence:

```bash
gpiodetect
gpioinfo --strict GPIO23
gonken-agent env status --json
gonken-agent env health --json
```

The environment status/health payload records `actuator_runtime_identity` with the logical BCM identity and the resolved gpiochip/offset when resolution succeeds. Preserve these outputs. If `GPIO23` is missing, ambiguous, reported as `UNRESOLVED`, or conflicts with the physical header/wiring plan, **STOP**. **Do not actuate.** Never substitute a guessed gpiochip offset.

After the mapping and wiring preconditions are satisfied, create the sensor-deferred profile using the installed non-actuating helper:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/environment_profile_manager.py sensor-deferred-relay
sudo cat /etc/gonken-agent/config.toml
sudo systemctl restart gonken-environment.service
sudo systemctl status gonken-environment.service --no-pager -l
gonken-agent env status --json
gonken-agent env health --json
```

The helper creates only the governed simulated-sensor/real-libgpiod-relay safe-OFF profile, refuses to overwrite a divergent site configuration, and never starts the service or touches hardware itself. Verify `TARGET_HYBRID_SENSOR_SIMULATED`, no `PermissionError`, and the same unique GPIO23 runtime identity before the unloaded relay check.

When the unloaded relay behavior is correct and the low-voltage fan path has passed the checks in `HARDWARE_SETUP.md`, perform the supervised OFF → ON → OFF test:

```bash
gonken-agent env mode set manual
gonken-agent env fan off
gonken-agent env fan on
gonken-agent env fan off
```

A successful daemon command means the relay-power command was accepted. It does not by itself prove blade motion. Record what you physically observe.

## 4. Stage C — simulated sensor plus real relay/fan

Remain in the `sensor_backend="simulated"` and `relay_backend="libgpiod"` profile. Use the same full-simulation temperature commands while physically observing the relay/fan.

```bash
gonken-agent env policy set --mode automatic --start-c 28 --stop-c 26.5
gonken-agent env simulate sensor set --temperature-c 27 --humidity-pct 50
gonken-agent env simulate sensor set --temperature-c 29 --humidity-pct 50
gonken-agent env simulate sensor set --temperature-c 26 --humidity-pct 50
```

This stage may provide physical relay/fan evidence, but the temperature side remains simulated. It cannot close the SHT31 gate.

## 5. Voice checks

After the environment daemon is ready, say `GonKen`, wait for `Yes?`, then try:

```text
What is the room temperature?
Is the room fan on?
Turn the room fan on.
Turn the room fan off.
Use automatic mode.
```

With a simulated sensor, GonKen must identify the temperature as simulated. With a simulated actuator, it must identify simulated fan-power state. With a real relay, it may report the real relay-power command but must not claim blade motion unless you independently observed it.

Real wake recall, false wakes, wake-to-ack latency, Piper progress-cue timing, and audio overlap remain target evidence under M10.7.

## 6. Logs and live monitoring

Keep `env watch` open when useful:

```bash
gonken-agent env watch --interval 1
```

Watch the environment service journal in another terminal:

```bash
sudo journalctl -fu gonken-environment.service
```

For voice/audio diagnosis:

```bash
sudo journalctl -fu gonken-agent.service
```

`env watch` is passive. It must not create extra sensor samples or alter controller decisions.

## 7. Evidence export

Create a private M10.7 evidence directory. The collector is an evidence collector, not an acceptance oracle.

Without actuation:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/environment_acceptance_runner.py \
  --output-dir /var/lib/gonken-environment/acceptance/user-test \
  --json
```

For the supervised relay/fan OFF → ON → OFF evidence step only after all hardware preconditions pass:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/environment_acceptance_runner.py \
  --output-dir /var/lib/gonken-environment/acceptance/user-test-actuation \
  --allow-actuation \
  --json
```

When a simulated backend is active, physical-gate rows may be `BLOCKED` with `SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED`. That is correct evidence separation, not a software failure.

Also create the content-minimized support bundle:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

## 8. Upload after the target run

Return these artifacts from the exact tested checkpoint:

- the support ZIP printed by `collect-support.sh`;
- `m10_7_evidence_manifest.json`;
- `m10_7_private_evidence_ledger.csv`;
- the `private_evidence/` directory, preferably archived without editing its contents;
- saved `gpiodetect` / `gpioinfo --strict GPIO23` output plus `gonken-agent env status --json`/`health --json` showing the runtime-resolved actuator identity;
- a short manual observation note covering relay safe boot, OFF/ON polarity, fan start/stop, any brownout/reboot, voice ON/OFF behavior, automatic simulated-threshold behavior, semi-automatic stop/no-restart behavior, `GonKen` detection, progress cues, and speech overlap.

Do not edit evidence to turn `BLOCKED`, `NEEDS_MANUAL_REVIEW`, or `NOT_RUN` into `PASS`.

## 9. Stop conditions

Stop physical testing and preserve evidence if the GPIO mapping is uncertain, relay polarity is unexpected, the relay energizes during boot, the fan does not stop after OFF, VBUS/GND identification is uncertain, the Pi browns out or reboots during fan changes, wiring heats or smells abnormal, or any mains voltage is involved.

The continuation after upload is evidence-driven: verify the exact package/configuration, classify each run as simulation/hybrid/physical, fix the smallest correct layer, and rerun only the uncertain target checks.
