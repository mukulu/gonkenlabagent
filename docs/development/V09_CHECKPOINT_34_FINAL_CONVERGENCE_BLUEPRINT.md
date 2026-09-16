# V09 Checkpoint 34 Final-Convergence Blueprint

## 1. Purpose

This blueprint is the corrective continuation contract after the real Raspberry Pi 5 checkpoint-33 run. It does not reopen architecture that already has evidence. It exists to prevent another one-error-at-a-time installation cycle and to carry the package from host verification to a complete physical M10.24 campaign.

The governing target is simple: a clean or previously used supported Pi must be able to install/reinstall the same GonKen checkpoint through either supported entry path, reach `INSTALLATION_COMPLETE`, boot the current service without a login session, use any deterministic usable audio route, resolve the real Pi5 header GPIOs without numeric-chip assumptions, and then operate the existing fan/sensor/voice stack under the recorded safety boundaries.

## 2. Authoritative evidence and chronology

### 2.1 Physical facts already established

Preserve these facts; do not rediscover them merely because software changes:

- Pi 5 header GPIO23 is observed as `GPIO23` on the RP1 header controller.
- Manual logical low/high/low produced physical fan OFF/ON/OFF through the installed relay/PENGLIN/ELUTENG path.
- `/dev/i2c-1` exists.
- the installed SHT31 responds at `0x44`.
- AIRHUG USB capture and playback routes have been observed.
- Raspberry Pi 5 exposes multiple gpiochip devices; product logic may not assume the header is always a particular numeric `/dev/gpiochipN`.

These are component-level target facts. They are not evidence that checkpoint 34 has completed integrated acceptance.

### 2.2 Checkpoint-33 target result

Checkpoint 33 (`e5d05d105228d4cb8cf81201435d122a89435e6f`) advanced through:

1. source validation;
2. dependency/platform preflight;
3. runtime/release layout;
4. immutable candidate build;
5. activation;
6. environment account and target identity;
7. I2C platform;
8. runtime hardware bindings;
9. environment service installation;
10. Ollama account/binary/service/model;
11. Whisper/Piper/models/speech smoke;
12. application service;
13. Bluetooth steps;
14. runtime context.

The final appliance-readiness step failed because the running voice service repeatedly reported `WAKE_LED_GPIO_LINE_AMBIGUOUS` for GPIO22. Therefore this target run does **not** support reopening release activation as the current blocker. It supports fixing runtime GPIO identity and moving that validation earlier.

### 2.3 Real target GPIO topology evidence

The prior support snapshot records one 54-line gpiochip containing the coherent set:

```text
GPIO2
GPIO3
GPIO17
GPIO22
GPIO23
GPIO27
```

That topology corresponds to the project I2C/header/control pins. The package may use this coherent topology as a disambiguation signal, but must not encode the observed numeric chip name as a permanent product assumption.

## 3. Non-negotiable invariants

### 3.1 Current release is the runtime authority

Normal installation and runtime operate on the requested/current release only.

Previous releases:

- are not executed to prove current readiness;
- are not revalidated against current runtime contracts;
- are not allowed to block a healthy current release;
- may be retained for explicit rollback/update bookkeeping.

Explicit rollback is a separate governed operation and may validate the selected rollback target before switching.

### 3.2 Immutable authority is precise, not overbroad

Authoritative release payload includes source, config, executable/native payload, manifests, installed package metadata needed by the release, maintenance assets and all other sealed release content.

Interpreter-derived cache is not authoritative only when all of these hold:

- the cache ancestor is a real directory named `__pycache__`;
- the cache ancestor is not a symlink;
- the descendant is a regular `.pyc` or `.pyo` file;
- no arbitrary non-bytecode file is hidden under the cache tree.

The same authority definition must be used by:

- digest generation;
- payload manifest generation/comparison;
- ownership validation;
- immutable-mode validation.

Never let one validator ignore a cache while another validator rejects the same cache.

### 3.3 Do not mutate the current release to make validation green

Ordinary same-commit operation must not depend on deleting or editing authoritative current-release files. Python bytecode generation is suppressed at managed entry points. If a standard cache exists anyway, it is outside the authority boundary and can remain without invalidating the release.

Actual source/config/executable/manifest drift remains a hard integrity failure. Do not suppress `RELEASE_ACTIVE_INVALID` for real authoritative changes.

### 3.4 Bluetooth is preference, audio is requirement

When `--bluetooth-audio` is supplied:

- attempt to provision/use the requested Bluetooth route;
- if unavailable, check deterministic direct audio;
- if exactly one supported direct capture route and exactly one supported non-HDMI playback route exist, continue base installation with explicit warnings;
- keep optional Bluetooth reconnection retryable;
- never claim Bluetooth is connected when direct audio is being used;
- refuse zero/ambiguous direct routes rather than guessing.

A transport preference must never become a stronger requirement than the actual voice appliance.

### 3.5 One shared GPIO resolver

PTT, wake indication, recording LED and room-fan relay must use the same resolver.

Resolution precedence:

1. globally unique exact kernel line name `GPIO<n>`;
2. unique target line whose controller metadata identifies RP1;
3. unique controller containing the coherent project header signature;
4. otherwise fail closed.

Do not:

- hard-code `gpiochip0`;
- assume BCM number equals line offset;
- special-case only GPIO22;
- silently pick the first line-name match;
- acquire or write a line during identity discovery.

### 3.6 Installer preflight must predict runtime

A non-actuating target GPIO identity step must run before environment/application readiness and use the same production resolver.

It proves:

- GPIO17 resolves;
- GPIO22 resolves;
- GPIO23 resolves;
- GPIO27 resolves;
- all resolve to one coherent header controller;
- the service account can inspect required metadata;
- no line request/write occurs.

A future runtime `WAKE_LED_GPIO_LINE_AMBIGUOUS` after this step would be a checker/runtime consistency defect and must be treated as such.

## 4. Installation dependency graph

The target installer order is:

```text
source record
  -> engine contract
  -> release prerequisites
  -> target platform preflight
  -> gonken-agent account
  -> release layout
  -> immutable current candidate
  -> current activation
  -> environment account/control group
  -> target identity/groups
  -> I2C platform/reboot convergence
  -> current-release hardware binding APIs
  -> Pi5 header GPIO identity (non-actuating)
  -> environment service structure (disabled, non-actuating)
  -> Ollama account/store
  -> Ollama binary
  -> Ollama service
  -> selected model
  -> Whisper
  -> Piper
  -> speech models
  -> speech smoke
  -> application service
  -> optional Bluetooth stack
  -> optional Bluetooth pair/fallback
  -> optional Bluetooth autoconnect
  -> transport-neutral runtime context
  -> physical appliance readiness
  -> INSTALLATION_COMPLETE
```

No step may declare success from stale persisted state when its postcondition is false. Every rerun rechecks the postcondition before using the completion record.

## 5. Entry-path equivalence

### 5.1 Local exact checkpoint

```bash
./bootstrap.sh --local-checkpoint ...
```

Authority: exact checked-out commit.

### 5.2 Remote launcher

```bash
curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | bash -s -- ...
```

Authority: commit resolved from the fetched remote ref during launcher/bootstrap source recording.

After source resolution, both paths must use the same:

- install engine;
- release manager;
- accounts/groups;
- service templates;
- runtime checks;
- failure semantics.

Tests must prove launcher arguments are forwarded and source-mode differences do not select a different convergence policy.

## 6. Repeated-run matrix

Checkpoint acceptance must cover:

1. first install on empty target state;
2. exact same command rerun before service start;
3. rerun after current service executed Python;
4. rerun with a legitimate `__pycache__` present;
5. rerun after reboot;
6. local checkpoint -> local checkpoint;
7. remote curl -> remote curl;
8. local checkpoint -> remote curl for the same remote/current commit;
9. remote curl -> local checkpoint for the same commit;
10. preferred Bluetooth online;
11. preferred Bluetooth busy/offline + deterministic USB duplex;
12. no Bluetooth + deterministic USB duplex;
13. missing/ambiguous physical audio: fail early and specifically;
14. authoritative current-release tamper: fail closed;
15. stale historical-release corruption: must not block current runtime unless explicitly selected for rollback.

## 7. Release-integrity adversarial matrix

Must remain valid:

| Condition | Expected |
|---|---|
| normal source/config/executable unchanged | PASS |
| standard `__pycache__/x.pyc` appears | PASS without current-release rewrite |
| hundreds of normal cache files appear | PASS without hiding other drift |
| source file changed + cache files | FAIL authoritative integrity |
| top-level sourceless `.pyc` added | FAIL |
| `__pycache__` symlink added | FAIL |
| non-bytecode payload hidden in cache tree | FAIL |
| release manifest changed | FAIL |
| binding manifest changed | FAIL |
| executable permission/owner changed authoritatively | fail or exact governed permission recovery only where pre-existing contract explicitly permits |

## 8. Pi5 GPIO adversarial matrix

| Target metadata shape | Expected |
|---|---|
| line name globally unique | resolve |
| duplicate line name, one controller labelled `pinctrl-rp1` | resolve RP1 |
| labels missing, one controller has full project header signature | resolve topology controller |
| two complete header-like controllers | fail ambiguous |
| GPIO22 absent | fail not-found |
| GPIO17/22/23/27 resolve across different chips | fail chip mismatch |
| numeric chip device changes across kernel/boot | still resolve by metadata/topology |

Target support evidence should record the selected chip path, offset, name/label and resolution basis for diagnosis, while making no physical-actuation claim.

## 9. Audio route matrix

| Bluetooth | Direct input/output | Installer |
|---|---|---|
| connected and usable | any | continue; Bluetooth route may be used |
| busy/offline | exactly one deterministic duplex path | warn + continue direct |
| stack installation fails | exactly one deterministic duplex path | warn + continue direct |
| no record/autoconnect unavailable | exactly one deterministic duplex path | warn + continue direct |
| unavailable | zero direct route | fail explicit audio prerequisite |
| unavailable | multiple plausible direct routes | fail ambiguity |
| available output only | one deterministic direct microphone | allowed only if actual capture/playback readiness is proven coherently |

HDMI/display-only playback must not be used as an implicit headset fallback.

## 10. Sensor/environment preservation

Checkpoint 34 must not regress the sensor/fan work already completed:

- I2C enable/reboot convergence;
- `/dev/i2c-1` permission/openability;
- SHT31 0x44/0x45 governed discovery;
- raw I2C transaction/CRC implementation;
- simulated/simulated profile;
- simulated sensor + real relay profile;
- real sensor + simulated actuator profile;
- full-real profile;
- one environment service owns sensor/relay;
- safe relay OFF and no software fan-speed claims;
- physical acceptance remains separate from configuration.

## 11. Failure taxonomy and action

### `RELEASE_ACTIVE_INVALID`
Use only for actual authoritative current-release invalidity. It is not a historical-version comparison failure. Preserve evidence; do not hand-edit current release.

### `INSTALL_ACTION`
Generic wrapper around a real failed installer action. Always inspect the preceding specific code. Do not remove this wrapper merely because prior root causes were benign; remove the benign root causes.

### `GPIO_HEADER_UNRESOLVED` / `GPIO_HEADER_CHIP_MISMATCH`
Early target mapping failure. Preserve candidate metadata. Do not start service or actuate GPIO.

### `WAKE_LED_GPIO_LINE_AMBIGUOUS`
Should not occur after a successful checkpoint-34 GPIO preflight. If it does, classify as installer/runtime resolver inconsistency and capture both preflight artifact and service log.

### Bluetooth warning codes
Warnings are allowed only when deterministic direct physical audio is proven. They must never be translated into Bluetooth success.

### `AUDIO_DIRECT_UNAVAILABLE` / ambiguity
Real prerequisite failure. Connect exactly one intended route or restore Bluetooth; no guessing.

## 12. Quality assurance requirements

Every material change requires:

1. narrow unit tests;
2. negative/adversarial tests;
3. affected integration tests;
4. cascade review of shared consumers;
5. complete bounded unit accounting;
6. deterministic integration accounting;
7. release/speech lifecycle accounting;
8. milestone/blueprint/status/test-matrix consistency;
9. false-green review;
10. package extraction and exact-artifact verification.

An aggregate timeout is neither PASS nor FAIL. Preserve completed sub-results and rerun only the uncertain module/case.

## 13. False-green questions required before handoff

Ask and test:

- Could a cache exclusion hide source tampering?
- Could a cache directory symlink escape the release tree?
- Could installer GPIO preflight use a different resolver than runtime?
- Could a host fixture with ideal RP1 label mask a real Pi metadata gap?
- Could Bluetooth requested make PipeWire mandatory despite working USB audio?
- Could stale install state mark Bluetooth/GPIO/runtime steps satisfied after their true postcondition changed?
- Could a prior ready file satisfy a new current release?
- Could current operation execute an old release accidentally?
- Could a generic install start/toggle the relay while merely validating configuration?
- Could a support bundle imply physical acceptance from configuration or mock state?

## 14. Checkpoint-34 host completion criteria

Do not package until all are true:

- all discovered unit modules accounted PASS;
- all deterministic integration modules accounted PASS;
- speech lifecycle all cases PASS;
- release lifecycle all cases PASS;
- same-commit cache rerun PASS;
- previous-current non-execution PASS;
- Pi5 topology + RP1 + ambiguity GPIO tests PASS;
- direct audio fallback positive/negative/ambiguity tests PASS;
- target GPIO preflight non-actuating tests PASS;
- install dependency order PASS;
- documentation validator PASS;
- milestone ledger PASS;
- release readiness PASS;
- T0 PASS;
- `git diff --check`, Python compile and shell syntax PASS;
- clean committed repository;
- tag created;
- delivered ZIP extracted and independently reverified.

## 15. Exact-package verification criteria

After packaging, the extracted archive must prove:

- expected commit;
- expected tag;
- active development branch;
- local `main` pinned to previous checkpoint merge base;
- `main` tracks `origin/main`;
- GitHub origin is correct;
- no credentials embedded;
- `git fsck --strict` PASS;
- clean worktree after `git reset --hard HEAD`;
- executable scripts retain mode;
- release readiness PASS;
- T0 PASS;
- critical release/audio/GPIO/install/service unit slice PASS;
- launcher equivalence PASS;
- same-commit repeated-release regression PASS;
- current-only release regression PASS.

## 16. Target campaign after `INSTALLATION_COMPLETE`

Do not repeat already-established wiring discovery unnecessarily. Execute in order:

1. inspect current service/readiness and support baseline;
2. GonKen CLI fan OFF -> ON -> OFF with physical observation;
3. real SHT31 discovery and bounded repeated-read campaign;
4. real sensor + simulated actuator;
5. simulated sensor + real actuator if useful for controlled threshold testing;
6. full-real environment profile;
7. temperature/humidity voice query;
8. voice fan ON/OFF;
9. automatic/semi/manual controller semantics;
10. sensor unplug/recovery and safe-off;
11. environment service restart/voice-service stop independence;
12. wake/PTT/LED physical behavior;
13. reboot/no-login operation;
14. offline/no-WAN operation;
15. update/rollback/reinstall;
16. final support/private acceptance evidence.

Do not call the release physically accepted until every acceptance-critical target row has actual observed evidence or an explicit documented block.

## 17. Continuation protocol

If target checkpoint 34 fails:

- do not patch the live immutable release;
- capture the specific terminal code and installer failure bundle;
- collect support from the current release where possible;
- classify the smallest failed dependency;
- convert it into a regression fixture/test;
- fix the authoritative package layer;
- verify cascade effects;
- create the next checkpoint only after host/package gates are green.

If checkpoint 34 reaches `INSTALLATION_COMPLETE`, stop treating installation as an open software blocker and continue directly through M10.24 hardware/voice acceptance.
