# V09 Simulation, Hybrid-HIL, Wake and Documentation Extension Plan

**Plan checkpoint:** V09 Checkpoint 16 — blueprint/control-plane expansion only  
**Date:** 2026-09-15  
**Input package:** `gonkenlabagent-v09-ci-phase-checkpoint-15.zip`  
**Input package SHA-256:** `70f5a7ccf97efef32efc36d3c7e07bab292ab7974c5552d078acf1eefc2e1906`  
**Governing expansion prompt:** `GonKenAgent_V09_CKPT15_to_Simulation_HIL_Blueprint_Expansion_Master_Prompt_V2_GOLD.md`  
**Governing expansion prompt SHA-256:** `a536954376e7834c398b772f60a749d521edc7b6df31de58a2506c414292aa63`  
**Current checkpoint commit:** `4171170a8b68cedbc52a4c651b0970fff481dcd4`  
**Execution mode:** blueprint expansion only; no simulation runtime, wake-runtime, GPIO, I2C, or CLI mutation is implemented by this checkpoint.

## 1. Current implementation truth at Checkpoint 15

### Already implemented and host-verified

- V09 static environment configuration schema 2 exists, with `[extensions.environment]` disabled by default.
- The current supported production environment backends are `sensor_backend = "sht31"` and `relay_backend = "libgpiod"`.
- The deterministic environment domain, mutable fan policy, controller, AF_UNIX IPC, operator CLI, deterministic voice environment intents, diagnostics, support-bundle fields, dashboard status fields, installer/systemd structural wiring, SHT31 adapter, libgpiod relay adapter, daemon activation scaffold, daemon polling loop, M10.7 evidence runner, bounded CI runner, release-lifecycle decomposition, and CI phase selection exist with host evidence.
- `gonken-agent env watch` exists and currently obtains repeated IPC sensor reads.
- Immediate wake acknowledgement `Yes?` exists after a wake match.
- Broad host evidence is phase-selectable through `./scripts/ci.sh --phase t0|unit|integration|release-lifecycle|all`.

### Planned but not implemented

- Runtime-supported simulated sensor backend.
- Runtime-supported simulated actuator backend.
- Mixed/hybrid HIL operation using independent sensor and actuator backend axes.
- Operator `gonken-agent env simulate ...` CLI family.
- Passive snapshot-style `env watch` that cannot affect controller timing or recovery sample counts.
- Simulation-aware voice responses that explicitly say simulated/measured/provenance-appropriate wording.
- Autonomous fan-transition announcements owned by the voice runtime.
- Mandatory shipped/default `GonKen` wake phrase.
- Continuous/overlapping high-recall wake capture path.
- Governed `GonKen` alias/fuzzy matcher corpus and wake diagnostics.
- Post-question progress cues such as `Just a second.` and `I'm still working on that.` using locally generated Piper cue assets.
- Beginner-safe hardware setup, simulation, environment control and troubleshooting documentation set.
- Documentation command verification for new simulation/wake docs.

### Target-gated and not run

- Physical SHT31 detection and repeated CRC-valid readings.
- Real Pi 5 gpiochip/line mapping for the room-fan relay.
- Relay active-high/polarity verification.
- PENGLIN USB VBUS/GND continuity and no-back-power evidence.
- ELUTENG physical fan ON/OFF cycles and blade-motion observation.
- Real target `gonken-environment.service` systemd/no-login convergence.
- Real microphone/speaker `GonKen` wake behavior, wake-to-`Yes?` latency, progress-cue timing, and no-overlap audio behavior.

## 2. Architectural decisions for the simulation extension

### 2.1 Independent backend axes

The next implementation must model sensor and actuator simulation as independent backend axes:

```toml
[extensions.environment]
sensor_backend = "sht31"      # sht31 | simulated
relay_backend = "libgpiod"    # libgpiod | simulated
```

This supports four evidence modes:

| Sensor backend | Actuator backend | Evidence mode | Physical gate status |
|---|---|---|---|
| simulated | simulated | `HOST_SIMULATION` or `TARGET_FULL_SIMULATION` | Does not close physical sensor/fan gates |
| simulated | libgpiod | `TARGET_HYBRID_SENSOR_SIMULATED` | Can test real relay/fan but not real sensor |
| sht31 | simulated | `TARGET_HYBRID_ACTUATOR_SIMULATED` | Can test real sensor but not real actuator/fan |
| sht31 | libgpiod | `TARGET_PHYSICAL` | Only this can close full physical environment acceptance |

Simulation is an adapter choice behind the same daemon/service boundary. It is not a bypass, not a second controller, and not a CLI-owned fake state file.

### 2.2 Static config, mutable policy and ephemeral simulation state

Keep three authorities separate:

| Authority | Owner | Examples | Persistence |
|---|---|---|---|
| Static/admin configuration | root/admin TOML | enabled, backend selection, I2C bus/address, GPIO chip/line, relay polarity, simulation runtime permission | persistent |
| Mutable operating policy | `gonken-environment.service` | mode, start/stop thresholds, dwell | persistent daemon JSON |
| Simulation state | `gonken-environment.service` | simulated temperature/humidity, sensor fault, actuator behavior | normally ephemeral |

Simulation state must not be written into the production policy file. Reset and service restart semantics must be explicit and default-safe.

### 2.3 Local protocol extension

Extend the existing bounded AF_UNIX JSON protocol with allow-listed operations only:

| Operation | Purpose | Mutating | Guardrail |
|---|---|---:|---|
| `simulation.status.get` | return simulation state/provenance | no | allowed when daemon supports simulation introspection |
| `simulation.reset` | reset sensor and actuator simulation state | yes | requires runtime simulation control enabled |
| `simulation.sensor.set` | set temperature/RH | yes | sensor backend must be simulated |
| `simulation.sensor.fault` | inject unavailable/read_error/crc_error/stale | yes | sensor backend must be simulated |
| `simulation.sensor.reset` | clear sensor simulation/fault | yes | sensor backend must be simulated |
| `simulation.actuator.behavior.set` | normal/unavailable/fail-next-write | yes | actuator backend must be simulated |
| `simulation.actuator.reset` | clear actuator simulation/fault | yes | actuator backend must be simulated |
| `state.snapshot.get` | passive current daemon state for watch/support | no | must not trigger sensor sampling or actuator writes |
| `events.get` | bounded recent transition/event records | no | must not replay old events as new truth |

Stable simulation errors should include `SIMULATION_DISABLED`, `SIMULATION_SENSOR_NOT_ACTIVE`, `SIMULATION_ACTUATOR_NOT_ACTIVE`, `SIMULATION_INPUT_INVALID` and `SIMULATION_FAULT_INVALID`.

### 2.4 Passive watch

`gonken-agent env watch` must become a passive snapshot observer of daemon-owned polling state. It must not call an operation that adds sensor samples, advances recovery count, changes median windows, changes dwell timing, or writes the actuator. If an explicit active read remains available, the docs must call it active sampling.

Suggested row:

```text
15:42:01  29.0 C  50.0 %RH  sensor=SIM  actuator=REAL  mode=automatic  fan=on  reason=AUTO_START_THRESHOLD  seq=17
```

### 2.5 Non-actuating check path

The current `env serve --check` path is not accepted as hardware-neutral until the implementation proves it cannot open/request a GPIO line or write safe-off merely to validate configuration. The next implementation must distinguish pure configuration construction from real daemon resource acquisition, or add a non-opening `close_if_open()`/safe-off contract. Unit tests must inject fake gpiod and prove no line request and no write during `--check`.

### 2.6 GPIO configuration clarification

The current seed `relay_bcm = 23` must not silently double as libgpiod chip line offset. The next config design should make operator identity and runtime identity explicit, for example:

```toml
relay_bcm = 23
relay_physical_pin = 16
relay_chip_path = "/dev/gpiochip0"
relay_line_offset = 23
```

The exact field names may change, but target evidence must record the actual Pi 5 gpiochip label/path and line offset before physical actuation acceptance.

### 2.7 Voice and audio ownership

The environment daemon must never own Piper, ALSA, PipeWire, microphone capture or speaker playback. If automatic fan transitions are announced, the daemon records transition events and the voice runtime observes them through typed IPC. The voice runtime remains the one audio owner and must arbitrate direct answers, progress cues, wake acknowledgement, startup messages and autonomous transition announcements without overlap.

## 3. Simulated sensor contract

The simulated sensor backend is production-supported but explicitly test-oriented.

### Required CLI surface

```bash
gonken-agent env simulate sensor set --temperature-c 27 --humidity-pct 50
gonken-agent env simulate sensor unavailable
gonken-agent env simulate sensor read-error
gonken-agent env simulate sensor crc-error
gonken-agent env simulate sensor stale --age-seconds 30
gonken-agent env simulate sensor recover --temperature-c 27 --humidity-pct 50
gonken-agent env simulate sensor reset
```

### Semantics

- Valid simulated readings persist across daemon polls until changed, faulted, reset or service restart according to documented semantics.
- Recovery must still pass through `valid_samples_to_recover`; simulation must not bypass controller safety logic.
- Invalid operator input such as `NaN`, `Infinity`, humidity outside 0..100, nonnumeric values and unknown fault names must be rejected as command errors, not silently converted into sensor faults.
- Simulated sensor results must report `source_backend = "simulated"`, `sensor_address = null`, `physical_evidence = false`, and the current simulation generation/session identity.

## 4. Simulated actuator contract

The simulated actuator backend must:

- start OFF;
- accept controller ON/OFF requests through the same service core;
- record commanded state and modeled state;
- never import or require libgpiod;
- never touch `/dev/gpiochip*`;
- expose `software_speed_control=false` and `fan_motion_observed=false`;
- support `normal`, `unavailable`, and `fail-next-write` behavior first;
- treat `stuck_on`, `stuck_off`, and `silent_mismatch` as optional later adversarial faults unless implementation proves they are needed for the user-test release candidate.

Required CLI surface:

```bash
gonken-agent env simulate fan show
gonken-agent env simulate fan behavior normal
gonken-agent env simulate fan unavailable
gonken-agent env simulate fan fail-next-write
gonken-agent env simulate fan reset
```

## 5. Hybrid-HIL evidence classification

Every status, support bundle, dashboard environment payload, acceptance manifest and simulation runner output must identify:

```text
sensor_backend
actuator_backend
sensor_is_simulated
actuator_is_simulated
physical_evidence
simulation_session_id
simulation_generation
evidence_mode
```

Physical acceptance runners must block physical PASS while either backend is simulated, using an explicit result such as `SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED`. Hybrid target runs are useful evidence but must close only the physical side actually present.

## 6. Automatic and semi-automatic simulation demonstrations

The implementation must provide an end-to-end demonstration in full simulation and later in hybrid modes:

### Automatic

1. Set test policy with start 28 C, stop 26.5 C and shortened dwell only if static bounds allow it.
2. Set automatic mode.
3. Inject 27 C: fan remains OFF.
4. Inject 29 C: fan transitions ON after configured recovery/dwell rules.
5. Inject 27 C: fan remains ON due hysteresis.
6. Inject 26 C: fan transitions OFF after minimum-on dwell.
7. Assert transition reasons: `AUTO_START_THRESHOLD` and `AUTO_STOP_THRESHOLD`.

### Semi-automatic

1. Set semi-automatic mode.
2. Inject 30 C: fan stays OFF.
3. Explicit fan ON: fan ON and semi armed.
4. Inject 26 C: fan OFF and disarmed.
5. Inject 30 C again: fan remains OFF.

### Faults

- Sensor unavailable in AUTO/SEMI forces safe OFF.
- Sensor recovery requires configured valid-sample sequence.
- Simulated actuator fail-next-write produces actuator-unavailable/degraded state and safe-off behavior.

## 7. Mandatory `GonKen` wake and interaction plan

V2 product decision: the shipped/default wake phrase must become `GonKen`. Real Pi testing tunes recall and latency later; it is not an adoption gate.

### Implementation requirements

- Update default config, typed config tests, installer/readiness expectations, README, operations docs, troubleshooting docs and acceptance runbooks to say `GonKen`.
- Preserve `Hey GonKen`/`Hey Gonken` as a backward-compatible recognition alias unless collision tests show unacceptable false wakes.
- Do not implement only a string replacement. The wake architecture must reduce capture/transcription blind gaps.
- Implement a bounded rolling/overlapping standby capture design or a demonstrably equivalent pipelined design.
- Use a recall-first transcript matcher with Unicode/case/punctuation normalization, adjacent-token joining, governed aliases and bounded one-edit matching for GonKen-like tokens.
- Build a host fixture corpus with intended variants, split variants, aliases, one-character STT errors and deliberate collision/non-wake phrases.
- Add wake diagnostics: `gonken-agent wake status`, JSON status, and a supervised test/calibration path if feasible.

### Post-question progress cues

After a captured request begins processing:

- deterministic fast environment responses should return without filler;
- if the final answer is not ready around 0.8--1.0 s, play one cue: `Just a second.`;
- if still unresolved around 4 s, play at most one longer cue: `I'm still working on that.`;
- cancel cues not yet started when final answer is ready;
- allow an already-started short cue to finish before final answer;
- generate cue WAVs locally with Piper and a manifest; do not reuse legacy unknown-provenance filler WAVs.

## 8. Autonomous environment announcements

Planned optional announcements must be observed and spoken by the voice runtime, not the environment daemon. Prioritize:

- `AUTO_START_THRESHOLD`
- `AUTO_STOP_THRESHOLD`
- `SEMI_AUTO_STOP`
- `SENSOR_STALE_SAFE_OFF`
- `ACTUATOR_ERROR_SAFE_OFF`

Rules:

- Do not duplicate manual voice command confirmations.
- Drop or coalesce stale announcements.
- Never say the fan blades are spinning unless independent physical evidence exists.
- Simulated announcements must begin with or otherwise include simulation provenance.
- No announcement may overlap a direct user answer, wake acknowledgement, progress cue, or startup readiness message.

## 9. Documentation architecture to implement later

Create or revise these docs at the matching implementation checkpoint, without documenting unimplemented commands as available:

| File | Ownership |
|---|---|
| `README.md` | five-minute orientation and documentation map |
| `docs/INSTALLATION.md` | OS baseline, install, update, rollback, uninstall |
| `docs/HARDWARE_SETUP.md` | wiring, safety, pins, relay/PENGLIN/fan, first power-on |
| `docs/ENVIRONMENT_CONTROL.md` | modes, thresholds, CLI/voice examples, status interpretation |
| `docs/SIMULATION.md` | simulation backend matrix, CLI, two-terminal labs, fault injection, provenance |
| `docs/OPERATIONS.md` | service/log/watch/support operations |
| `docs/TROUBLESHOOTING.md` | decision trees with symptoms, safe checks, expected results and stop conditions |
| `docs/RASPBERRY_PI_ACCEPTANCE_RUN.md` | physical target acceptance only |
| `docs/ENVIRONMENT_ACCEPTANCE_RUN.md` | evidence export and target environment campaign |

Documentation checks must verify referenced files, commands, options, service names, config keys, wake phrase, simulation/physical separation and cross-links. A Markdown-rendering PASS alone is insufficient.

## 10. Hardware setup requirements

The future hardware document must be beginner-safe and exact.

### Safety rules

- Low-voltage DC switching only.
- Do not use the relay for mains power.
- Never feed 5 V into a 3.3 V GPIO.
- Never power the room fan from a GPIO pin.
- Power off before changing wiring.
- Verify actual PCB labels; stop if relay terminals or JD-VCC/VCC arrangements differ.
- Stop if continuity, polarity, relay labeling, supply voltage or current path is uncertain.

### SHT31 candidate wiring

| Pi physical pin | BCM/function | SHT31 |
|---:|---|---|
| 1 | 3.3 V | VCC/VIN |
| 3 | GPIO2/SDA1 | SDA |
| 5 | GPIO3/SCL1 | SCL |
| 6 | GND | GND |

Expected common I2C address is `0x44`; alternate is `0x45`. Target evidence must determine the actual address.

### Relay logic candidate wiring

| Pi physical pin | Function | Relay logic terminal |
|---:|---|---|
| 17 | 3.3 V | VCC |
| 16 | GPIO23 | IN |
| 14 | GND | GND |

The actual relay PCB labels are authoritative. Unloaded relay test must precede any fan USB switching.

### PENGLIN/fan low-voltage path

Use independent regulated 5 V source VBUS through relay COM/NO to fan-side VBUS. Keep GND continuous. Do not use NC. Do not switch data lines. Verify VBUS/GND and absence of short with a meter before power. Set the ELUTENG physical speed controller to Low for the first supervised test.

## 11. Future checkpoint plan

| Checkpoint | Scope | Exit state |
|---|---|---|
| 16 | blueprint/control expansion only | `BLUEPRINT_READY_FOR_IMPLEMENTATION` |
| 17 | config, backend factories, simulated sensor/actuator, simulation protocol and unit tests | simulation foundations host-verified |
| 18 | `env simulate` CLI, passive watch, simulation faults, diagnostics/support visibility, full-sim tests | operator simulation experience host-verified |
| 19 | hybrid HIL integration, simulation-aware voice responses, hybrid evidence classification | hybrid-ready host evidence, physical actuation still gated |
| 20 | mandatory `GonKen` default, continuous/overlapping wake, progress cues, transition events/announcements | host-verified wake/interaction implementation |
| 21 | hardware/environment/simulation/troubleshooting docs, doc command checks, evidence runner hardening | documentation/evidence hardened |
| 22 | user-test package | `READY_FOR_USER_SIMULATION_AND_SENSOR_DEFERRED_HIL` if and only if all user-test gates pass |
| 23+ | evidence-driven fixes after user upload | repair smallest correct layer, rerun affected host/target checks |

## 12. Requirement traceability summary

Detailed traceability is in `docs/development/V09_SIMULATION_HIL_TRACEABILITY.csv`. No new requirement may proceed without a work package, tests, documentation and evidence tier.

## 13. Multi-pass review results

- **Completeness:** simulation sensor, actuator, hybrid, watch, voice truthfulness, announcements, wake, progress cues, hardware setup, evidence export and documentation requirements are specified or target-gated.
- **Architecture consistency:** one environment owner, one policy authority, one simulation state authority and one audio owner are preserved.
- **Dependency order:** simulation foundations precede CLI/operator experience; hybrid precedes user handoff; wake/progress has its own checkpoint; physical acceptance remains separate.
- **Non-regression:** existing V09 host behavior is preserved; no runtime changes are made in checkpoint 16.
- **False-green:** the plan explicitly blocks simulation from closing physical acceptance and calls out `env serve --check`, passive watch and gpiochip mapping risks.
- **Safety:** hardware instructions require low-voltage-only operation, unloaded relay testing, meter checks and explicit stop conditions.
- **Executability:** future work names actual modules, docs, tests, scripts and commands where possible.
- **Cold resume:** start with checkpoint 17 simulation foundations using this plan, `MASTER_BLUEPRINT.md`, `MILESTONES.json`, `TEST_MATRIX.md` and `DECISIONS.md`.
