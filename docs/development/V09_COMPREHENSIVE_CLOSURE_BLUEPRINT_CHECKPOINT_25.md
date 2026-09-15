# GonKenLab Agent V09 — Comprehensive Closure Blueprint, Checkpoint 25

## 1. Authority, scope, and evidence boundary

This checkpoint reconstructs the remaining V09 work from checkpoint 24 using the Sensor-Ready V2 GOLD master prompt and the target evidence obtained on Raspberry Pi 5. It does not invalidate earlier verified host work. It makes the remaining dependencies explicit so later checkpoints can converge rather than expose one predictable prerequisite at a time.

Authority order for this continuation is:

1. current repository instructions and verified current code/tests;
2. this focused blueprint and the matching M10.16-M10.24 sections in `MASTER_BLUEPRINT.md`;
3. verified Raspberry Pi target evidence recorded in the checkpoint-24/25 reports;
4. current authoritative vendor/platform documentation;
5. older V09 blueprint text where it does not conflict with later verified evidence.

Evidence classes remain separate:

- **host** — code/static/unit/integration/package evidence without target hardware;
- **target-simulation** — Raspberry Pi runtime using only simulated environment backends;
- **hybrid-HIL** — one real environment backend and one simulated backend;
- **target-physical** — Raspberry Pi evidence from the actual SHT31/relay/fan/audio devices;
- **release-lifecycle** — clean install/update/rollback/reboot/no-login evidence on the target.

No host result may close a physical gate. Existing physical GPIO23/relay/fan observations are preserved as evidence but do not imply that GonKen service/voice control, SHT31, boot-safe state, or full acceptance has passed.

## 2. Preserved verified strengths

The following existing architecture is retained unless a reproduced defect requires change:

- one authoritative `gonken-environment.service` owner for physical sensor/relay state;
- local Unix-socket environment control with `gonken-envctl` operator authorization rather than raw hardware privileges;
- deterministic environment controller with MANUAL, SEMI_AUTOMATIC, AUTOMATIC and DISABLED modes;
- simulated sensor and actuator backends plus hybrid evidence semantics;
- libgpiod relay adapter resolving logical BCM GPIO23 from the unique kernel line name `GPIO23` rather than assuming a gpiochip offset;
- physical fan capability limited to ON/OFF power control; the ELUTENG physical speed selector remains manual;
- SHT31 frame decoding, CRC-8 validation, temperature/humidity conversion and explicit unavailable/error readings;
- content-minimizing diagnostics/support bundles;
- immutable releases, systemd supervision, rollback and bounded CI decomposition;
- exact-package/local-checkpoint acceptance support and portable Git history.

Changes must extend these strengths rather than create parallel owners, duplicate drivers, alternate safety rules, or incompatible profile/config paths.

## 3. Verified current target facts to preserve

The current Raspberry Pi 5 target has directly demonstrated:

- RP1 GPIO controller visible as `gpiochip0 [pinctrl-rp1]`;
- logical `GPIO23` resolves to `gpiochip0` line 23 on this target;
- Raspberry Pi physical header pin 16 controls GPIO23;
- `GPIO23=0` physically releases the KKHMF relay and stops the ELUTENG fan;
- `GPIO23=1` physically energizes the relay and starts the fan;
- relay polarity is therefore active-high on the tested board;
- COM/NO and the tested USB breakout/fan load path are operational;
- process termination of `gpioset` does not prove safe OFF on this target; explicit OFF is required during raw diagnostics.

These facts are target-specific physical evidence and must be recorded in later private evidence, but normal GonKen operation must use the environment service rather than raw `gpioset`.

## 4. Known checkpoint-23/24 failures that become permanent regression requirements

### 4.1 Runtime binding false green

Checkpoint 23 installed `python3-libgpiod` and `python3-smbus` with APT while the immutable application venv could not import them. System-Python import success is therefore never sufficient evidence for a service interpreter.

### 4.2 Checkpoint-24 target dependency contamination

Checkpoint 24 enabled `system_site_packages` for the target venv. On the real Raspberry Pi this exposed unrelated system Python distributions to `pip check`; unrelated `types-*` package dependency defects then caused immutable-release validation to fail. The next design must not merely suppress this error. It must define the ownership boundary between GonKen-managed Python requirements and OS-managed hardware bindings and validate exactly that contract.

### 4.3 Operator authorization

A valid human operator was initially outside `gonken-envctl`, producing `ENV_UNAVAILABLE: PermissionError`. Installer/post-install convergence must ensure the selected operator receives control-socket authority, requires a new login when necessary, and never receives raw GPIO/I2C authority merely to make the CLI work.

### 4.4 Configuration/profile absence

The generic environment default is intentionally disabled, but supervised target testing needs governed profile creation and verification rather than ad-hoc TOML edits. Configuration creation, ownership, validation, conflict handling and profile transitions are installer/onboarding dependencies.

### 4.5 Failure evidence from the wrong release

A failed candidate can leave the previous release active. Installer failure evidence therefore must come from candidate/build/installer state independently of the active release, with enough provenance to identify source commit, profile, interpreter, packages and failing gate.

## 5. Dependency and resource graph

Every installer/runtime step must declare prerequisites, owned resources, postconditions, invalidation triggers, repair behavior, verification and rollback. At minimum the graph contains:

1. **platform identity** — Raspberry Pi model/OS/kernel/architecture/Python version/time/disk;
2. **package repositories** — APT health, package metadata and required OS packages;
3. **system Python** — exact ABI/version and distro hardware binding availability;
4. **immutable application runtime** — GonKen-owned dependencies and controlled access to required hardware bindings;
5. **users/groups** — `gonken-agent`, `gonken-env`, `gonken-envctl`, `audio`, `gpio`, `i2c`, invoking operator;
6. **filesystem ownership** — release root, state/config/runtime directories, sockets, model stores and private evidence;
7. **systemd units** — application, environment, Ollama and related runtime directories/order/restart contracts;
8. **audio stack** — PipeWire/Pulse/BlueZ/user-session/runtime-dir/device/profile dependencies;
9. **speech stack** — Whisper/Piper binaries, models, architecture and smoke tests;
10. **LLM/retrieval** — Ollama binary/service/model/local retrieval assets;
11. **GPIO** — logical GPIO17/22/23/27 discovery, group/device access and single-owner rules;
12. **I2C** — firmware enablement, reboot state, `/dev/i2c-1`, group ownership, service-user access and SHT31 address;
13. **environment profiles** — simulation, hybrid and full-real configuration with explicit evidence semantics;
14. **controller/voice** — environment socket, controller policy, deterministic voice intents and wake/audio arbitration;
15. **support/update/rollback** — active/candidate provenance, failure evidence and clean lifecycle behavior;
16. **Git/package handoff** — exact commit/tag/branch/origin/modes/checksums/extraction verification.

A downstream step may execute only after every dependency-ready prerequisite is verified or explicitly marked BLOCKED with independent work continuing elsewhere.

## 6. M10.17 — controlled Python dependency boundary

The design must compare and document at least:

- isolated venv plus an explicit, allow-listed bridge for distro hardware bindings;
- system-site-packages plus scoped GonKen dependency validation that ignores unrelated distributions without hiding GonKen dependency defects;
- another architecture only if it preserves OS ownership of hardware bindings and application reproducibility.

The selected design must satisfy all of these:

- GonKen runtime imports required `gpiod` v2 APIs and the selected I2C API under the actual service interpreter;
- unrelated system Python packages cannot cause GonKen dependency validation to fail;
- missing/incompatible required hardware bindings fail before service activation;
- missing GonKen Python dependencies still fail;
- development/host environments remain isolated unless explicitly required;
- validation reports provenance of every externally supplied binding;
- dirty-host tests reproduce the checkpoint-24 `types-*` contamination case;
- update/rollback and previously built release validation stay deterministic.

`pip check` must not be globally weakened without a replacement that proves the dependencies GonKen actually owns.

## 7. M10.18 — installer convergence engine

The installer is not a linear sequence that assumes a clean host. Each step must implement:

`PRECONDITION -> REPAIR/CREATE -> VERIFY POSTCONDITION -> RECORD EVIDENCE -> MARK SATISFIED`

and revalidate itself when inputs that invalidate its postcondition change.

Mandatory preflight covers platform, disk, DNS/repository access where required, APT health, package architecture, Python ABI, users/groups, filesystem safety, systemd, audio runtime capability, hardware-binding package/API availability, I2C enablement state, GPIO/I2C device permissions, existing GonKen partial state, candidate residue, active release and requested profile.

Required dirty-host scenarios include:

- clean target;
- checkpoint-23 partial install;
- checkpoint-24 failed candidate residue;
- unrelated broken system Python metadata/packages;
- missing required distro hardware binding;
- incompatible hardware binding API;
- pre-existing wrong ownership/modes;
- operator missing `gonken-envctl`;
- I2C disabled/reboot required;
- environment config absent, exact, divergent, malformed or unsafe symlink;
- services absent/disabled/failed/stale;
- interrupted install at every stateful boundary;
- reinstall after successful installation;
- update from previous checkpoint and rollback.

`INSTALLATION_COMPLETE` may be emitted only after all release/core appliance prerequisites are verified. Optional/physical environment activation remains a later explicit operation unless a selected target profile requests it.

## 8. M10.19 — identity, configuration and profile convergence

### Least privilege

- `gonken-agent`: application/audio needs only;
- `gonken-env`: authoritative physical environment owner; `gpio`/`i2c` only when present/required;
- `gonken-envctl`: environment control socket clients only;
- human operator: `gonken-envctl` after explicit installer selection; no raw GPIO/I2C by default.

Every service must be tested using its actual `User=`, `Group=`, supplementary groups, runtime directory, environment variables and device permissions.

### Governed environment profiles

A single profile manager must converge and verify at least:

1. `full-simulation`: simulated sensor + simulated actuator;
2. `sensor-deferred-relay`: simulated sensor + real libgpiod actuator;
3. `real-sensor-simulated-actuator`: SHT31 + simulated actuator;
4. `full-real`: SHT31 + real libgpiod actuator.

It must preserve administrator-owned unrelated configuration, refuse unsafe/conflicting files, support dry/status/verify semantics and never actuate hardware merely by writing configuration.

Evidence semantics must be exact:

- full simulation -> `HOST_SIMULATION` or target-simulation equivalent;
- simulated sensor + real actuator -> `TARGET_HYBRID_SENSOR_SIMULATED`;
- real sensor + simulated actuator -> `TARGET_HYBRID_ACTUATOR_SIMULATED`;
- real sensor + real actuator -> `TARGET_PHYSICAL` only after the physical acceptance gate, never merely from configured backend names.

## 9. M10.20 — systemd, runtime and audio closure

Before handoff, target-shadow and host tests must validate service definitions, ordering, restart behavior, runtime directories, supplementary groups, environment-file handling and independence between `gonken-agent.service` and `gonken-environment.service`.

Audio closure must explicitly explain and test the observed `/run/user/999` PipeWire/Pulse context, Bluetooth profile selection, capture/playback device visibility, reconnect/reboot behavior, USB/wired fallback and no-login operation. A service that is process-running but lacks capture/playback readiness is not appliance-ready.

## 10. M10.21 — SHT31/I2C and environment parity

### 10.1 Planned physical wiring

Power must be OFF while wiring. Planned Raspberry Pi 5 mapping:

| Raspberry Pi | SHT31 breakout |
|---|---|
| physical pin 1 — 3.3 V | VCC/VIN |
| physical pin 3 — GPIO2/SDA | SDA |
| physical pin 5 — GPIO3/SCL | SCL |
| physical pin 6 — GND | GND |

The exact breakout labels, onboard pull-ups/regulator/level shifting and voltage requirements must be inspected before power. Do not infer breakout-board electrical design from the bare sensor IC datasheet. The project default remains 3.3 V unless exact board documentation proves otherwise.

### 10.2 I2C platform convergence

The installer/onboarding path must detect whether the ARM I2C interface is enabled. On supported Raspberry Pi OS, the governed noninteractive operation is based on `raspi-config nonint do_i2c 0`, followed by verification. If enablement changes boot configuration and a reboot is required, persist a `REBOOT_REQUIRED` checkpoint with exact reason and resume after reboot rather than continuing into a false failure.

After reboot/when already enabled, verify `/dev/i2c-1`, ownership/mode, `gonken-env` access and actual open/read ability in service context. `i2cdetect` is a diagnostic aid, not proof that production reads are correct.

### 10.3 Address policy

Default SHT3x address is `0x44`; `0x45` is the alternate. Detect and handle:

- exactly configured address present -> continue;
- other known SHT3x address present -> require explicit/selectable profile convergence, never silently rewrite administrator intent;
- neither present -> `SHT31_NOT_PRESENT` / sensor-deferred mode remains usable;
- both present -> ambiguous unless explicit multi-device support is designed; fail closed for the single-sensor product contract.

### 10.4 Wire-protocol correctness gate

The existing driver must not be accepted solely because a fake object recorded `write_i2c_block_data` and `read_i2c_block_data`. SHT3x single-shot acquisition requires exact I2C wire semantics: 16-bit measurement command, conversion wait, then a six-byte read containing temperature+CRC+humidity+CRC without an unintended register/command byte. The implementation must use an API capable of expressing the exact transaction (for example raw/combined I2C messages when appropriate) and tests must verify the actual byte/message sequence.

Required driver checks include:

- all supported repeatability/clock-stretching commands;
- correct conversion timing bounds;
- exact six-byte frame length;
- CRC for both words;
- conversion formula/range validation;
- transport vs CRC vs stale vs invalid-range taxonomy;
- bus open/close/recovery behavior;
- soft reset/status/heater policy where used;
- heater OFF during ordinary room monitoring;
- real sensor readings never manufacture a value after transport/CRC failure.

### 10.5 Sensor diagnostic ladder

A bounded diagnostic runner must localize failures through:

A. platform/I2C state;
B. targeted address presence;
C. one production-adapter read;
D. repeated read campaign (minimum configured acceptance count, default >=100) with CRC/transport/intermittent-error accounting;
E. environment daemon state/health;
F. controller integration with simulated actuator first;
G. voice temperature/humidity query and full-real operation later.

### 10.6 Measurement quality and interference

Physical acceptance must evaluate sensor placement away from Pi/relay/self-heating and direct fan airflow artifacts, plausible response to ambient change, comparison to a reasonable reference instrument without claiming calibration, and I2C/CRC behavior during relay switching/fan startup. Power/undervoltage and wiring issues must be distinguished from application defects.

## 11. M10.22 — environment/voice end-to-end transaction

Host and target-shadow tests must cover every deterministic environment voice command and response with simulation/hybrid evidence wording. On the physical target, after software gates pass:

- CLI OFF -> GPIO low -> relay released -> fan stopped;
- CLI ON -> GPIO high -> relay energized -> fan rotating;
- voice ON/OFF produces the same service transaction without bypassing the environment daemon;
- temperature/humidity queries report real values only when the real sensor backend is valid;
- simulated/hybrid modes explicitly say which side is simulated;
- actuator/sensor failure produces fail-closed/no-fake-success responses;
- wake, progress cues and transition announcements do not create concurrent audio/device conflicts.

Raw GPIO commands remain diagnostics only, never the product control path.

## 12. M10.23 — clean/dirty lifecycle, support, package and Git closure

Before another user-test package:

- clean target-shadow install passes;
- dirty/partial target-shadow scenarios pass or fail with deterministic remediation;
- interrupted installs resume from the smallest uncertain step;
- update/rollback/reinstall/uninstall boundaries are checked;
- support bundles identify source/candidate/active release, profile, binding provenance, environment profile, service states, I2C/GPIO identity summaries and allow-listed failure codes without raw transcripts;
- support collection works even when no valid active release exists;
- package is created from a committed clean tree and re-extracted for verification;
- executable modes, Git objects, tag/branch identity, checksums and referenced artifacts are checked.

Portable Git handoff contract:

- `origin` is `https://github.com/mukulu/gonkenlabagent.git`;
- local `main` tracks `origin/main`;
- development checkpoint branch is descriptive;
- no credentials/tokens are embedded;
- user receives exact merge/push instructions but automated external push is not performed without explicit authorization.

## 13. M10.24 — final target/release acceptance

Final target campaign order is:

1. exact package/commit/checksum identity;
2. installer reaches governed `INSTALLATION_COMPLETE` without manual repair;
3. reconnect/new-login group state verified;
4. service/runtime/audio readiness verified;
5. simulation profile smoke;
6. real relay/fan CLI and lifecycle safe-OFF;
7. real SHT31 + simulated actuator;
8. real sensor + real relay/fan controller modes;
9. deterministic voice and wake path;
10. sensor/actuator/audio fault injection and recovery;
11. reboot/no-login convergence;
12. update/rollback/reinstall campaign;
13. final support/evidence capture.

Physical acceptance remains OPEN until each applicable gate has target evidence. A later hardware defect blocks only dependent claims; it does not erase unrelated verified host evidence.

## 14. Mandatory change-impact review for every repair

For each material defect record: symptom, reproduction, expected/observed, root cause/confidence, affected components, downstream impact, correct fix layer, repair, narrow test, related/cascade tests, regression test, remaining risk and physical retest requirement.

At minimum, changing any of the following requires the corresponding cascade review:

- Python dependency policy -> release build/validate/update/rollback/services/SHT31/GPIO;
- group/user policy -> installer/systemd/socket/device access/uninstall/reinstall;
- config/profile schema -> defaults/profile manager/daemon/CLI/voice/support/docs/migration;
- systemd runtime context -> audio/GPIO/I2C/models/runtime dirs/reboot/no-login;
- SHT31 driver -> simulation parity/daemon/controller/health/support/voice/full-real acceptance;
- relay adapter -> controller/safe-off/service lifecycle/voice/physical acceptance;
- support schema -> privacy/tests/troubleshooting/target evidence workflows.

No fix is complete while a directly related consumer remains unreviewed.

## 15. Anti-hang/checkpoint execution model

Implementation checkpoints are dependency-aware, not one-item sessions. For every batch:

`LOAD STATE -> VERIFY INPUTS -> SELECT READY WORK -> IMPLEMENT -> NARROW TESTS -> PERSIST/COMMIT -> BROADER AFFECTED TESTS -> RECORD RESULT -> CONTINUE`

Long checks must use bounded runners/timeouts and persistent logs. A timeout is recorded as INTERRUPTED/TIMEOUT, never PASS. Decompose rather than repeat unchanged. Commit coherent verified work before disruptive clean-install/release-lifecycle simulations. Continue independent work when one target-only gate is blocked.

## 16. Completion gates

Before any package handoff run all of these reviews:

1. completeness against M10.16-M10.24;
2. dependency consistency;
3. configuration/profile consistency;
4. permission/ownership consistency;
5. runtime/service-context consistency;
6. dirty-host resilience;
7. non-regression;
8. cascade/change-impact review;
9. false-green review;
10. executability of commands/paths/IDs;
11. evidence/provenance accuracy;
12. continuation/resumability;
13. package/Git integrity.

The engineering target is to eliminate known and reasonably anticipatable defects through evidence. Never claim the software can be proven free of all future defects or that unrun physical acceptance passed.

## 17. Current authoritative external references

- Raspberry Pi Documentation, Configuration / hardware communication / I2C: https://www.raspberrypi.com/documentation/computers/configuration.html
- Raspberry Pi `raspi-config` noninteractive I2C operation: https://www.raspberrypi.com/documentation/configuration/config-txt/memory.md
- Sensirion, Datasheet SHT3x-DIS, version 7 (December 2022): https://sensirion.com/media/documents/213E6A3B/63A5A569/Datasheet_SHT3x_DIS.pdf
- Python `venv` documentation: https://docs.python.org/3/library/venv.html
- Debian `python3-libgpiod` package information for trixie and the target architecture family: https://packages.debian.org/trixie/python3-libgpiod

Re-verify current versions when a later checkpoint depends on version-sensitive details.
