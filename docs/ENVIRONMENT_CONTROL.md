# V09 environment control reference

This reference describes the V09 room-environment control plane. The environment daemon is the only owner of SHT31 reads, relay writes, control-loop state, and mutable policy. The CLI and voice layers are clients of the daemon. They must not read GPIO, I2C, or policy files directly.

## 1. Evidence boundary

- Host tests and simulation can verify logic, protocol, CLI behavior, and voice wording.
- Physical M10.7 acceptance requires a real Raspberry Pi target, real SHT31, real relay wiring, PENGLIN wiring, ELUTENG fan cycles, and supervised observation.
- `physical_evidence=false` means the output is not physical acceptance.
- Current hardware supports power control only: `software_speed_control=false` and `fan_motion_observed=false` remain expected capability values.

## 2. Static environment configuration

Static environment configuration is root/admin-controlled TOML. It defines hardware, safety, permissions, hard bounds, and whether runtime simulation mutation is allowed. Ordinary CLI/voice policy mutation must not edit these fields.

Every current static key in `extensions.environment` is listed below so documentation checks can detect drift:

| Key | Purpose | Default boundary |
|---|---|---|
| `enabled` | Enables the environment service profile | Default false; generic upgrades do not actuate hardware. |
| `sensor_backend` | Sensor adapter: `sht31` or `simulated` | Physical SHT31 remains target-gated. |
| `i2c_bus` | Linux I2C bus number | Usually 1 on Pi; target must verify `/dev/i2c-*`. |
| `i2c_address` | SHT31 I2C address | 0x44 default; target must verify actual address. |
| `sensor_repeatability` | SHT31 repeatability profile | High repeatability in current driver. |
| `poll_interval_seconds` | Daemon polling interval | Must remain bounded; default 2.0. |
| `stale_after_seconds` | Sensor staleness threshold | Stale AUTO/SEMI control fails closed. |
| `valid_samples_to_recover` | Consecutive valid samples required for recovery | Default 3. |
| `relay_backend` | Relay adapter: `libgpiod` or `simulated` | Physical relay remains target-gated. |
| `relay_bcm` | Candidate logical BCM line | Default 23; Pi 5 gpiochip mapping must be recorded. |
| `relay_active_high` | Relay polarity assumption | Target must verify active polarity. |
| `safe_state` | Relay safe state | Must remain off. |
| `socket_path` | AF_UNIX control socket path | Default `/run/gonken-environment/control.sock`. |
| `policy_path` | Daemon-owned mutable policy path | Default `/var/lib/gonken-environment/policy.json`. |
| `temperature_policy_min_c` | Lower allowed temperature-policy bound | Default -10.0 C. |
| `temperature_policy_max_c` | Upper allowed temperature-policy bound | Default 60.0 C. |
| `minimum_hysteresis_c` | Minimum start/stop temperature gap | Default 0.5 C. |
| `maximum_hysteresis_c` | Maximum allowed hysteresis | Default 15.0 C. |
| `minimum_dwell_seconds` | Lower allowed dwell bound | Default 5 s. |
| `maximum_dwell_seconds` | Upper allowed dwell bound | Default 3600 s. |
| `simulation_runtime_control_enabled` | Allows simulation mutation through IPC | Default false. |
| `simulation_event_history_limit` | Bounded simulation/event history size | Default 128. |

## 3. Mutable policy

Mutable policy is stored by the daemon at `policy_path`. It contains operating mode, thresholds, dwell values, and generation. It does not change hardware backends, GPIO pins, relay polarity, I2C settings, or hard bounds.

Typical policy commands:

```bash
gonken-agent env policy show
gonken-agent env policy set --start-c 28 --stop-c 26
gonken-agent env policy set --mode automatic --minimum-on-seconds 60 --minimum-off-seconds 60
```

Invalid threshold combinations, stale generations, malformed JSON, or hard-bound violations must be rejected by the daemon.

## 4. Operator commands

Read-only or non-destructive commands:

```bash
gonken-agent env status
gonken-agent env status --json
gonken-agent env health
gonken-agent env read
gonken-agent env temperature
gonken-agent env humidity
gonken-agent env probe
gonken-agent env watch --interval 2 --count 3
```

Mutating commands:

```bash
gonken-agent env fan on
gonken-agent env fan off
gonken-agent env mode set manual
gonken-agent env mode set semi-automatic
gonken-agent env mode set automatic
gonken-agent env mode set disabled
```

`env watch` is passive. It observes `state.snapshot.get`; it must not create extra sensor reads, modify dwell timing, mutate policy, or write the relay.

## 5. Mode semantics

- `disabled`: rejects ON, keeps relay/fan power off, and is safe for transport or troubleshooting.
- `manual`: user commands determine relay power; temperature does not start or stop the fan.
- `semi-automatic`: explicit user start arms the run; low temperature may stop and disarm it; high temperature alone never auto-starts it.
- `automatic`: valid sensor readings and thresholds decide start/stop subject to hysteresis and dwell; sensor stale/failure forces safe-off and suspension.

Direct ON/OFF while in automatic mode intentionally switches to manual plus the requested state. This prevents a user from asking “turn it off” and having automatic mode immediately turn it back on without an explicit mode decision.

## 6. Voice command boundary

Voice commands use deterministic environment intents before the ordinary local model path. Clear environment commands become typed daemon calls. Spoken success must be derived from the daemon result. The voice layer must not fabricate physical state, claim blade motion, claim software speed control, or perform arbitrary shell/GPIO/I2C actions.

Example clear phrases:

```text
what is the room temperature?
what is the humidity?
is the room fan on?
turn the room fan on
turn the room fan off
use automatic mode
turn it on at 28 and off at 26
```

Ambiguous phrases such as “set the temperature to 25” require clarification.

## 7. Checkpoint 45 typed semantic tool boundary

Checkpoint 45 keeps the deterministic parser as the preferred fast path and adds a bounded semantic fallback for natural paraphrases. The admitted model may propose only these operations:

```text
system_get_local_datetime
environment_read_sensor
environment_get_status
environment_set_fan_power(power=on|off)
```

Temperature/humidity and fan status/results come from `gonken-environment.service`; the model never reads I2C or GPIO itself. Read-only proposals may share a bounded concurrent transaction. Fan mutation is serialized and requires an independently recognizable present-tense user instruction; negated, quoted, hypothetical and explanatory phrases cannot authorize a mutation.

Examples intended to work without exposing raw execution authority include:

```text
what time is it?
how warm is the room?
what's the humidity in here?
is the room fan powered on?
please start the room fan
turn the room fan off
```

When `relay_backend=simulated`, a successful fan command means only that simulated commanded power changed. It is not physical fan-motion evidence.

## B12 deterministic timers and command truth

Use the [README](../README.md#4-timers-modes-and-safety) for the canonical current timer/voice catalogue and 28 C / 26 C responsive preset. The scheduler is part of the same daemon, never a second GPIO owner. Numeric notifications are acknowledged only after successful voice playback. Timers do not survive daemon restart. Power preparation uses a bounded safe-OFF hold; it is not a persistent policy change. [Architecture](ARCHITECTURE.md).
