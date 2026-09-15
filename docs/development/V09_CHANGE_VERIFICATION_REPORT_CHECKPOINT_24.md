# V09 Checkpoint 24 — Code-Change Verification Report

## Scope

Verify the checkpoint-24 repair tranche derived from real checkpoint-23 Raspberry Pi installation evidence. The intended change is to make the immutable target runtime consume the distro hardware bindings that the installer provisions, close the operator control-socket authorization gap, strengthen target/runtime support evidence, and prevent physical relay testing from resuming before a repaired installation reaches the governed target gate.

**Base commit:** `82a9c9b4223aa1036f37a2298bef0d8b3188dd4d`
**Risk classification:** high for target installation/runtime compatibility and physical-I/O readiness; medium for permissions/support/export; low for host-only documentation.
**Explicit exclusion:** no physical GPIO/relay/fan/SHT31 action was run in this checkpoint implementation environment.

## Governing instructions inspected

- repository `AGENTS.md`;
- checkpoint-23 development control files and target runbooks;
- checkpoint-23 support bundle and installer failure logs;
- checkpoint-24 target failure audit/addendum supplied from the prior evidence review.

## Original defect reproduced from evidence

The Pi installer installed OS packages successfully, but the production service used the immutable venv interpreter and repeatedly emitted `python3-libgpiod_is_not_importable`. The old package validated hardware bindings only through system Python and could therefore appear provisioned while the actual service interpreter was unusable. The interactive operator also lacked `gonken-envctl`, explaining `ENV_UNAVAILABLE: PermissionError`.

## Correct fix layer

The repair was applied to the release/installer contracts rather than to the live target:

- Pi target release construction and validation: `scripts/release_manager.py`;
- installer account/runtime gates: `scripts/install.sh`;
- safe sensor-deferred site-profile generation: `scripts/environment_profile_manager.py`;
- diagnostic/support evidence: `src/gonken_agent/diagnostics.py`, `src/gonken_agent/support.py`;
- regression tests and target/readiness documentation.

No manual `PYTHONPATH` target workaround is promoted as the production solution.

## Verification performed

### Static and focused

- Python/shell syntax and `git diff --check` during implementation;
- focused checkpoint-24 regression: 39/39 PASS;
- affected-unit regression: 106/106 PASS;
- support/release regression: 31/31 PASS;
- release-record format negative regression added and passed.

### Final suite accounting

- unit: 40 modules / 394 tests PASS by preserved decomposed accounting;
- deterministic integration excluding release lifecycle: 10 modules / 46 tests PASS;
- release lifecycle: 8/8 cases PASS;
- readiness/documentation closure: 13/13 PASS;
- canonical T0: PASS.

The aggregate long-running attempts that hit the external execution boundary are explicitly recorded as interrupted, not passed. Their uncertain modules/cases were isolated and rerun; the accounting manifests list the passing evidence per module/case.

## Regression protection added

1. A target release with an isolated venv policy is rejected even when system Python could import the distro package.
2. Binding validation checks the actual `gpiod`/`smbus` API surface used by GonKen, not only module import names.
3. The invoking operator receives only environment-control socket membership, not raw hardware privilege.
4. The sensor-deferred profile manager is tested as non-actuating and refuses unsafe/divergent site configuration.
5. Support output includes immutable runtime/provenance evidence and preserves diagnostic reason codes without exporting raw journals or probe output.
6. Unknown release-record formats are rejected by support identity extraction.
7. Target runbooks refuse relay actuation until repaired installation/runtime/operator gates pass.

## Non-regression review

Protected behaviors include:

- non-target venv isolation;
- offline/local runtime;
- immutable release and rollback semantics;
- environment hardware single-owner boundary;
- privacy/content-minimizing support bundles;
- simulation/physical evidence separation;
- voice/environment soft dependency;
- safe default `environment.enabled=false`;
- no software fan-speed claim.

No acceptance criterion was weakened to obtain PASS.

## False-green review

Checkpoint 24 specifically prevents the following checkpoint-23 false-green pattern:

```text
APT hardware package installed
+ system Python import succeeds
+ immutable service venv cannot import package
= installer incorrectly reaches/attempts readiness with unusable service runtime
```

The repaired installer/release validation binds the check to the immutable interpreter/service context. The support bundle also records that boundary so future diagnosis does not have to infer it from generic package state.

## Residual risk / unavailable validation

The repaired archive has not yet been installed on the real Pi. Therefore:

- `INSTALLATION_COMPLETE` on checkpoint 24 is not yet evidence;
- distro hardware imports in the real immutable venv remain a target gate;
- operator group refresh remains a target gate;
- physical relay/fan/SHT31/wake/audio/reboot acceptance remains open.

These are **BLOCKED TARGET GATES**, not host failures.

## Readiness verdict

**HOST CHANGE VERIFICATION: PASS**
**TARGET INSTALLATION VERIFICATION: NOT RUN**
**PHYSICAL HARDWARE ACCEPTANCE: BLOCKED / NOT RUN**

The code is ready to package as checkpoint 24 for the next target-install campaign, but it is not a physical-release PASS.
