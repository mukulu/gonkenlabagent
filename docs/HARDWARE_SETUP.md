# V09 room-environment hardware setup

This document is a target-preparation guide for the V09 room-environment subsystem. It does not by itself prove that the physical Raspberry Pi, SHT31, relay, PENGLIN adapters, or ELUTENG fan have passed acceptance. The only valid physical evidence comes from the supervised M10.7 target campaign and the private evidence files described in [V09 room-environment acceptance evidence run](ENVIRONMENT_ACCEPTANCE_RUN.md).

## 1. Supported hardware boundary

V09 is designed for a low-voltage room-environment demonstrator:

| Part | Role | Evidence boundary |
|---|---|---|
| Raspberry Pi 5 with Active Cooler | Host appliance | The Active Cooler remains CPU cooling only. It is not the room fan. |
| SHT31-D pre-soldered breakout | Temperature and relative humidity sensor | Requires target I2C enablement, address confirmation, and repeated CRC-valid reads. |
| KKHMF 3V/3.3V high-level-drive one-channel relay | Fan power switch | Requires target polarity, boot-safe-off, and contact/current suitability evidence. |
| PENGLIN USB-A screw-terminal adapters | Expose USB fan conductors | Requires continuity/polarity inspection; only intended VBUS may be switched. |
| ELUTENG dual 120 mm 5V USB fan | Room-air actuator | V09 can switch power only. It cannot set Low/Medium/High software speed and cannot observe blade motion. |

The ELUTENG room fan is not the Raspberry Pi Active Cooler. With the current relay/PENGLIN/ELUTENG architecture, `software_speed_control=false` and `fan_motion_observed=false` remain the truthful capability values until additional accepted hardware exists.

## 2. Candidate pin and bus plan

The default static configuration uses:

```toml
[extensions.environment]
enabled = false
sensor_backend = "sht31"
i2c_bus = 1
i2c_address = 0x44
relay_backend = "libgpiod"
relay_bcm = 23
relay_active_high = true
safe_state = "off"
```

These are configuration defaults, not physical proof. The candidate relay line is logical BCM23 / physical header pin 16 because it does not collide with the current GPIO17 push-to-talk, GPIO27 recording LED, GPIO22 wake-monitoring LED, or I2C GPIO2/GPIO3 usage. On Raspberry Pi 5, the actual `gpiochip` and line mapping must still be recorded on the target. Do not assume `/dev/gpiochip0`.

### 2.1 Voice-control GPIOs

The voice appliance also reserves three logical GPIO identities. They are separate from the room-fan relay:

| Function | Logical BCM | Physical header pin | Candidate wiring |
|---|---:|---:|---|
| Push-to-talk button | GPIO17 | 11 | Momentary button from pin 11 to GND pin 9; software requests an internal pull-up and treats the grounded state as pressed. |
| Recording LED | GPIO27 | 13 | GPIO27 -> suitable series resistor (for example 330 ohm) -> LED -> GND. LED ON means microphone capture is active. |
| Wake-monitoring LED | GPIO22 | 15 | GPIO22 -> suitable series resistor -> distinct LED -> GND. LED ON means continuous wake standby capture is active. |

The production GPIO adapters resolve these identities from libgpiod line names such as `GPIO17`; they do not assume BCM17 is `/dev/gpiochip0` line 17. Before relying on either interaction mode, record the actual target mapping with `gpiodetect`, `gpioinfo`, and the service journal. If a configured line name is missing or ambiguous, the software fails closed rather than choosing an offset.

For the first target test, wire LEDs with the Pi powered off, verify polarity/resistor placement, then confirm: recording LED OFF at idle, ON only while PTT is physically held, OFF before processing; wake-monitoring LED ON only during wake standby and OFF while the assistant acknowledges, listens to the full question, or speaks. These observations are physical acceptance evidence and cannot be replaced by host tests.

### 2.2 Exact SHT31 four-wire connection

For the project SHT31 breakout, use the Raspberry Pi 5 3.3 V I2C header mapping below **only after confirming the actual breakout labels are VCC/VIN, SDA, SCL and GND (or documented equivalents)**. Do not infer a breakout pin order from a photograph or another vendor revision.

| Raspberry Pi physical pin | Function | SHT31 breakout |
|---:|---|---|
| 1 | 3.3 V | VCC / VIN |
| 3 | GPIO2 / SDA | SDA |
| 5 | GPIO3 / SCL | SCL |
| 6 | GND | GND |

```text
WIRE 1: Pi pin 1  (3.3 V)    -> SHT31 VCC/VIN
WIRE 2: Pi pin 3  (GPIO2/SDA)-> SHT31 SDA
WIRE 3: Pi pin 5  (GPIO3/SCL)-> SHT31 SCL
WIRE 4: Pi pin 6  (GND)      -> SHT31 GND
```

The project uses 3.3 V for this connection. Do not move the sensor to a Pi 5 V pin merely because an SHT31 IC or another breakout can tolerate a wider supply; breakout regulators, pull-ups and level shifting are board-specific and must be inspected/documented. Power the Pi off before changing these wires.

Before applying power, inspect and record the actual breakout markings, whether pull-up resistors or level shifting are visibly present/documented, and whether the address-select pad is in its default state. If labels differ from the table, STOP and identify the board rather than guessing.

### 2.3 I2C platform and SHT31 diagnostic ladder

The installer owns I2C platform convergence. It may enable I2C non-interactively and deliberately stop with `I2C_REBOOT_REQUIRED`; after reboot, rerun the **same exact checkpoint installer** so its persisted step engine resumes. The installer does not probe a sensor address or start the environment controller as part of this prerequisite step.

After installation reaches `INSTALLATION_COMPLETE` and the sensor is wired/powered, verify the platform without actuation:

```bash
ls -l /dev/i2c-1
sudo /usr/local/lib/gonken-agent/current/maintenance/i2c_manager.py status --user gonken-env --require-ready
```

`i2cdetect -y 1` may be used as a human diagnostic, but its table alone is not acceptance evidence. The governed production diagnostic uses the same raw Linux I2C transaction semantics as the GonKen SHT31 adapter and checks both supported addresses without accepting ambiguity:

```bash
sudo -u gonken-env /usr/local/lib/gonken-agent/current/.venv/bin/python \
  /usr/local/lib/gonken-agent/current/maintenance/sht31_diagnostic.py discover --bus 1
```

Exactly one supported address must answer as a valid SHT31 (`0x44` normally, `0x45` when the actual board is configured that way). Neither address is `SENSOR_NOT_FOUND`; two valid addresses are `SENSOR_ADDRESS_AMBIGUOUS`. Do not silently change static configuration merely because a scan displayed another device.

After discovery, run the bounded repeated-read campaign at the discovered address. The default is 100 reads and normal ambient operation verifies the SHT31 heater is off:

```bash
sudo -u gonken-env /usr/local/lib/gonken-agent/current/.venv/bin/python \
  /usr/local/lib/gonken-agent/current/maintenance/sht31_diagnostic.py campaign \
  --bus 1 --address 0x44 --reads 100
```

Use `0x45` only when discovery established that address. This campaign validates transport/CRC/plausibility at the adapter boundary but still does not, by itself, prove correct room placement or close full physical acceptance.

## 3. Power-off inspection before any actuation

Before running any command that can turn the relay/fan on:

1. Shut down and remove power from the Raspberry Pi and the fan power path.
2. Confirm the SHT31 is placed outside the hot Pi case, away from the Active Cooler exhaust and away from direct ELUTENG fan exhaust.
3. Confirm SDA/SCL wiring uses the intended Pi I2C pins and that power/ground match the SHT31 breakout requirements.
4. Confirm the relay input wiring uses the configured GPIO candidate, power, and ground expected by the relay module.
5. Confirm relay COM/NO wiring switches only the intended USB VBUS conductor through the PENGLIN adapters.
6. Confirm no USB short, back-power path, or exposed conductor is present.
7. Confirm the ELUTENG physical speed controller is deliberately set by the operator.
8. Record relay markings, SHT31 board markings/address, Pi model, OS/kernel, Python version, fan model, power supply, date, and operator.

Do not control mains voltage in this revision.

## 4. First target checks

Run these only after installation and before fan actuation:

```bash
gonken-agent status --json
gonken-agent wake status --json
gonken-agent env status --json
gonken-agent env health --json
gonken-agent env probe --json
```

These commands are non-destructive. They may report `physical_evidence=false` until the full target campaign records otherwise.

## 5. Sensor-only target evidence

Use `gonken-agent env read --json` and the M10.7 evidence collector to gather SHT31 evidence. A valid physical sensor gate requires repeated target reads with CRC validation and plausible placement. A JSON status alone does not prove that the reading represents room temperature.

```bash
gonken-agent env read --json
```

If the sensor backend is `simulated`, `simulation.sensor.*` output, host simulation output, or `TARGET_HYBRID_SENSOR_SIMULATED` evidence is useful for engineering but cannot close SHT31 physical acceptance.

## 6. Relay and fan target evidence

Actuation must remain supervised. Use the evidence runner with `--allow-actuation` only after power-off inspection.

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/environment_acceptance_runner.py \
  --output-dir /var/lib/gonken-environment/acceptance/manual-actuation \
  --allow-actuation
```

The runner issues fan OFF/ON/OFF through the daemon boundary. A human must record whether the relay clicked, whether the fan powered, whether the fan stopped, and whether boot/start/shutdown safe-off behavior is correct. JSON output cannot prove blade motion.

## 7. Stop conditions

Stop and preserve evidence if any of these occur:

- relay turns on during boot before the daemon permits it;
- relay polarity appears inverted;
- PENGLIN wiring becomes warm, loose, or uncertain;
- fan does not stop after OFF;
- `gonken-agent env health --json` reports actuator unavailable;
- SHT31 readings are stale, implausible, or CRC-invalid;
- support or acceptance output reports `SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED` during a physical gate.

Do not “fix” a physical wiring or polarity issue by weakening the software acceptance criteria. Correct the physical design or static configuration, rerun the affected target checks, and keep unrelated verified evidence only when its dependencies are unchanged.
