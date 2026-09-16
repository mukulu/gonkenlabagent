# V09 Checkpoint 34 Report — Final Convergence Hardening

## Purpose

Checkpoint 34 responds to the real checkpoint-33 Raspberry Pi result and a second adversarial review of checkpoint-33's host fixes. Checkpoint 33 proved that current-release construction/activation, I2C/runtime bindings, environment service, Ollama, Whisper, Piper, speech smoke, application service, Bluetooth/autoconnect and runtime context can all converge on the target. The remaining observed blocker was the live voice service repeatedly reporting `WAKE_LED_GPIO_LINE_AMBIGUOUS` for GPIO22 until appliance readiness timed out.

The checkpoint therefore closes three related quality boundaries together rather than patching the wake LED alone: immutable runtime authority, transport-neutral audio convergence, and shared Pi5 GPIO identity with an early non-actuating installer gate.

The prior target support snapshot also records one 54-line gpiochip containing GPIO2, GPIO3, GPIO17, GPIO22, GPIO23 and GPIO27 as a coherent set. Checkpoint 34 uses that topology as a fallback identity signal when libgpiod chip labels are incomplete; the observed device number itself is not hard-coded.

## Root-cause and architecture corrections

### 1. Immutable authority is defined once

Checkpoint 33 still used a repair-oriented cache model and could let different validators disagree about whether a root-created `__pycache__` tree was part of the sealed release. Checkpoint 34 uses one authoritative-payload iterator for digest, manifest, owner and mode validation. Only a real non-symlink `__pycache__` directory and `.pyc`/`.pyo` descendants are derived runtime cache. Symlink cache directories, top-level bytecode, arbitrary non-bytecode cache content, source/config/executable/manifest changes and mixed tampering remain fatal.

Normal same-commit convergence does not rewrite a current release to repair ordinary caches. Python entry points still suppress bytecode writes, and ordinary derived caches are outside immutable authority if they nevertheless exist.

### 2. Historical releases are not runtime prerequisites

Normal installation/service readiness evaluates only the requested/current release. Previous releases remain explicit rollback/update state and are never executed or revalidated as prerequisites of current operation. `RELEASE_ACTIVE_INVALID` continues to protect actual current-release authoritative drift; it is not a version-comparison blockade.

### 3. Audio readiness is transport-neutral

Bluetooth is a preferred optional route. The installer may continue if Bluetooth stack/pair/autoconnect work is unavailable but the service can prove exactly one deterministic direct USB/wired capture route and one direct non-HDMI playback route. Zero or ambiguous direct audio remains fail-closed. The runtime-context gate no longer requires PipeWire merely because `--bluetooth-audio` was requested.

### 4. GPIO identity is shared and proven early

PTT GPIO17, wake GPIO22, relay GPIO23 and recording LED GPIO27 now use `src/gonken_agent/gpio_resolver.py`. The resolver does not hard-code `gpiochip0` or assume BCM equals line offset. It uses global uniqueness, RP1 metadata/sysfs labels, or a unique coherent Pi-header topology. Genuine ambiguity still fails closed.

`scripts/gpio_identity_preflight.py` applies the same resolver before environment/application readiness. It opens only chip/line metadata; it never requests or writes a line. Installer PASS therefore cannot be based on a different mapping rule than runtime wake/PTT/relay behavior.

## Verification accounting

- Unit: **47 modules / 487 tests PASS** by bounded/decomposed accounting.
- Deterministic non-release/non-speech integration: **10 modules / 44 tests PASS**.
- Speech lifecycle: **12/12 PASS**.
- Release lifecycle: **12/12 PASS**, including same-commit runtime-cache rerun and previous-current non-execution.
- Ollama lifecycle: included in deterministic integration, **5/5 PASS**.
- Focused release/GPIO/Bluetooth/install/service regression: PASS.
- Aggregate wrappers stopped by an external execution boundary remain recorded as interrupted; only unaccounted modules/cases were rerun.

## Target evidence preserved

Existing target evidence is not discarded: manual GPIO23 relay/fan OFF/ON/OFF physically works; the SHT31 answers at `0x44` on `/dev/i2c-1`; AIRHUG USB input/output exists; checkpoint 33 reached the running voice service. None of this is converted into checkpoint-34 physical acceptance.

## Remaining target gate

M10.24 remains open. Exact checkpoint 34 must pass the early GPIO identity step and reach `INSTALLATION_COMPLETE` without live-tree patching. Then run GonKen CLI fan control, real SHT31 repeated reads, hybrid/full-real environment control, wake/STT/TTS, fault recovery, reboot/no-login, update/rollback/reinstall and final support evidence.
