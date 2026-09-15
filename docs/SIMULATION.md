# V09 simulation and hybrid-HIL guide

Simulation is a daemon-owned test and training mode. It is useful for host development, operator practice, voice wording checks, and hybrid-HIL preparation. It is not physical Raspberry Pi acceptance.

## 1. Required static configuration

Simulation mutation is available only when both conditions are true:

1. the relevant backend is configured as simulated;
2. `simulation_runtime_control_enabled = true`.

Example full-simulation profile:

```toml
[extensions.environment]
enabled = true
sensor_backend = "simulated"
relay_backend = "simulated"
simulation_runtime_control_enabled = true
socket_path = "/run/gonken-environment/control.sock"
policy_path = "/var/lib/gonken-environment/policy.json"
```

Example hybrid profile with simulated sensor and physical relay actuator:

```toml
[extensions.environment]
enabled = true
sensor_backend = "simulated"
relay_backend = "libgpiod"
simulation_runtime_control_enabled = true
relay_bcm = 23
relay_active_high = true
```

Hybrid profiles are not full physical acceptance. They can support only the side that is actually physical and accepted.

## 2. Simulation commands

All simulation commands use the same AF_UNIX daemon boundary as the normal environment CLI.

```bash
gonken-agent env simulate status
gonken-agent env simulate reset
gonken-agent env simulate sensor set --temperature-c 27 --humidity-pct 50
gonken-agent env simulate sensor unavailable
gonken-agent env simulate sensor crc-error
gonken-agent env simulate sensor stale --age-seconds 30
gonken-agent env simulate sensor recover --temperature-c 27 --humidity-pct 50
gonken-agent env simulate sensor reset
gonken-agent env simulate fan show
gonken-agent env simulate fan behavior normal
gonken-agent env simulate fan unavailable
gonken-agent env simulate fan fail-next-write
gonken-agent env simulate fan reset
```

If the sensor backend is `sht31`, simulated-sensor mutations must be rejected. If the actuator backend is `libgpiod`, simulated-actuator mutations must be rejected. That is deliberate evidence protection.

## 3. Passive watch during simulation

```bash
gonken-agent env watch --interval 2 --count 3
gonken-agent env watch --interval 2 --count 3 --json
```

`env watch` reads the daemon snapshot. It does not perform extra sensor samples or actuator writes. Use `gonken-agent env read` only when an active read-now operation is intended.

## 4. Evidence modes

The daemon and evidence runner use explicit provenance terms:

| Evidence mode | Meaning | Physical acceptance boundary |
|---|---|---|
| `HOST_SIMULATION` | Sensor and actuator are simulated | Closes no physical M10.7 gate. |
| `TARGET_HYBRID_SENSOR_SIMULATED` | Sensor side is simulated; actuator side may be physical | Cannot close SHT31 physical acceptance. |
| `TARGET_HYBRID_ACTUATOR_SIMULATED` | Actuator side is simulated; sensor side may be physical | Cannot close relay/PENGLIN/fan acceptance. |
| `TARGET_PHYSICAL` | Intended full physical mode | Still requires target evidence and human observation. |

The physical acceptance runner blocks simulated or hybrid JSON from closing a physical gate with:

```text
SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED
```

## 5. Simulation-aware voice wording

When the daemon reports a simulated sensor, GonKen must say that the value is simulated rather than presenting it as the physical room temperature. When the actuator is simulated, GonKen must describe simulated actuator power rather than claiming that a physical relay/fan moved.

Simulation can verify that the voice route calls the correct daemon operation and speaks the correct boundary. It cannot prove real microphone wake behavior, real Piper timing, real relay polarity, or blade motion.
