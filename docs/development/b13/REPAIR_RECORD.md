# B13 installer probe and entry-path repair

## Scope

B13 is intentionally limited to the Raspberry Pi installation failure observed on
B12 and to making the two normal remote-main entry paths converge on the same
room-appliance bootstrap policy. It does not redesign fan, voice, timer, model,
power, display, or hardware behavior.

## Target evidence

The 2026-09-22 Raspberry Pi run built B12 commit
`aeb5cc80046f3d4c7aa5c17beb6a41a8b82d6d9a`, satisfied `environment_profile`,
and then stopped with:

```
[ERROR] code=INSTALL_PROBE message=postcondition probe errored for step responsive_configuration
```

The canonical failure bundle records `INSTALL_PROBE`,
`postcondition_probe_error_before_action`, step `responsive_configuration`, exit
65. The same target evidence shows the real SHT31/libgpiod environment service is
already operating; B13 therefore does not reopen the hardware-control design.

## Root cause

`scripts/install.sh` uses `python -m gonken_agent.deployment llm --check` as the
postcondition for `responsive_configuration`. A not-yet-applied preset is a normal
installer state: the postcondition must return 1 so the install engine runs the
step action. `gonken_agent.deployment` instead converted `PRESET_NOT_APPLIED` to
exit 65. The install engine correctly treats any pre-action postcondition result
other than 0 or 1 as a probe error, so it stopped before applying the preset.

## Repair

- `deployment --check` maps only `PRESET_NOT_APPLIED` to exit 1 and emits
  `ROOM_PRESET_PENDING`.
- Malformed, unsafe, unreadable, or invalid configuration still fails closed with
  exit 65.
- On a Raspberry Pi target, `./bootstrap.sh` with no environment/mode/preset
  override now defaults to `full-real`, `automatic`, `responsive-room`.
- Explicit environment/mode/preset arguments retain precedence over that default.
- `install-gonken.sh` continues to be a checkout/bootstrap launcher; it injects no
  competing environment policy, so the curl path and `./bootstrap.sh` converge on
  the same target defaults.
- The README and installation guide make `main -> git pull --ff-only ->
  ./bootstrap.sh` the primary existing-checkout workflow. The exact-checkpoint
  room wrapper remains supported but is no longer required for the ordinary
  remote-main workflow.

## Verification

Focused regression checks:

- 54 affected unit/integration/documentation tests: PASS.
- 25 installer/launcher integration tests: PASS. Ten are reruns from the focused
  set; the five B10 candidate-ordering and ten install-engine process tests extend
  the affected-path coverage.
- Installed-wheel reproduction: pending `deployment llm --check` exits 1 without
  mutation; applying the preset succeeds; subsequent check exits 0: PASS.
- `bash -n` on bootstrap, launcher, room wrapper, and installer: PASS.
- `current_state.py --check`: PASS.
- `release_readiness.py --validate`: PASS (whole Attempt03 remains truthfully
  `NOT_READY`; this does not invalidate the bounded B13 installer repair).
- `validate_v09_docs.py`: PASS.
- `scripts/ci.sh --phase t0`: PASS.
- `compileall` and `git diff --check`: PASS.

A broad unit run was started in the bounded runner. Twenty modules completed PASS
before the execution envelope interrupted while entering the next module; that
active module was rerun directly and passed 10 tests. A subsequent resumed batch
completed another 12 modules PASS before the external command envelope interrupted.
No product failure occurred in those broad runs; they are retained as partial
non-regression evidence rather than misreported as a complete unit-suite pass.

## Installation workflow after merge to main

Existing checkout:

```bash
cd "$HOME/gonkenlabagent"
git checkout main
git pull --ff-only origin main
./bootstrap.sh
```

Fresh/managed checkout:

```bash
curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | bash
```

Both end at the same governed `bootstrap.sh` target defaults unless the operator
explicitly supplies an environment/mode/preset override.
