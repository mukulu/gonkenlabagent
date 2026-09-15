# GonKenLab Agent V09 — Checkpoint 24 Report

**Checkpoint:** 24 — installer/runtime dependency repair and target-evidence hardening
**Implementation base:** `82a9c9b4223aa1036f37a2298bef0d8b3188dd4d` (checkpoint 23)
**Checkpoint Git identity:** tag `checkpoint/v09-24` (resolve with `git rev-list -n 1 checkpoint/v09-24`)
**Host checkpoint state:** `M10.15 = host-verified`
**Real Raspberry Pi repaired-install state:** **NOT RUN**
**Physical relay/fan/SHT31 acceptance:** **NOT RUN / BLOCKED**

## 1. Completed

Checkpoint 24 converts the first checkpoint-23 Raspberry Pi installation failures into source-level repairs and regression protection instead of treating them as operator mistakes or patching only the live target.

Completed scope:

1. **Target release Python/runtime contract repaired.**
   - The Raspberry Pi production profile `core-pi-trixie-py313` now builds the immutable application venv with distro system-site visibility so Debian-provided `python3-libgpiod` and `python3-smbus` can be consumed by the actual service interpreter.
   - Non-target profiles remain isolated; this is not a global weakening of venv policy.
   - Release validation fails closed if the target venv policy is wrong or if the exact `gpiod`/`smbus` APIs GonKen uses are unavailable.
   - The immutable release is validated in the service-account context, and the installer adds a target-runtime binding gate before environment-service provisioning/use.

2. **Operator control-socket authorization repaired.**
   - The validated non-root invoking operator is added to `gonken-envctl` only.
   - The operator is not granted raw `gpio` or `i2c` ownership by this repair.
   - The installer emits an explicit session-refresh notice because supplementary group membership requires a fresh login/SSH session.

3. **Sensor-deferred real-relay profile made governed and non-actuating.**
   - Added `scripts/environment_profile_manager.py`.
   - The helper can create/verify the exact `simulated sensor + libgpiod relay` site override without starting services, requesting GPIO/I2C, or claiming hardware acceptance.
   - It refuses symlink/divergent/malformed configuration rather than silently overwriting it.

4. **Support/diagnostic false-green resistance strengthened.**
   - Support export now records bounded runtime-binding evidence, active immutable release identity, relevant Debian package versions, allow-listed installer event fields, and content-free service event code counts.
   - Health reason codes are preserved.
   - Legitimate systemd `inactive`/`disabled` states are preserved rather than collapsed to unknown merely because `systemctl is-active/is-enabled` returns nonzero.
   - Release identity rejects an unexpected release-record format.
   - Raw journal text, transcripts, stdout/stderr from probes, and other uncontrolled content are not added to the support bundle.

5. **Target runbooks and control plane updated.**
   - The target runbook now requires the exact checkpoint-24 local archive, governed `INSTALLATION_COMPLETE`, immutable-runtime binding validation, fresh `gonken-envctl` membership, environment CLI access, and GPIO23 identity agreement before any relay ON command.
   - The user HIL handoff uses the governed sensor-deferred profile helper rather than ad-hoc editing of a missing site config.
   - Troubleshooting documents the old venv binding failure and operator socket permission failure.
   - `MASTER_BLUEPRINT`, `MILESTONES`, `IMPLEMENTATION_STATUS`, `DECISIONS`, `TEST_MATRIX`, release-readiness logic, and documentation validator are synchronized around `M10.15`.

## 2. Verified evidence

### 2.1 Original target failure evidence

The checkpoint-23 Pi campaign established:

- Debian installed `python3-libgpiod` and `python3-smbus` successfully.
- The production GonKen service interpreter repeatedly reported `WAKE_LED_GPIO_DEPENDENCY_MISSING` / `python3-libgpiod_is_not_importable`.
- The same interpreter boundary affects GPIO17 PTT, GPIO22/27 indicators, GPIO23 room-relay actuation, and later SHT31 SMBus access.
- The human operator account was absent from `gonken-envctl`, producing `ENV_UNAVAILABLE: PermissionError`.
- `gonken-environment.service` safely exited with `ENVIRONMENT_DISABLED enabled=false`; this was expected default behavior rather than a service crash.
- The target reported `GPIO23` as `gpiochip0` line `23`; this remains target evidence for the same Pi but does not authorize actuation before checkpoint-24 installation closure.

Input fingerprints are preserved in `docs/development/evidence/v09/checkpoint24/target_failure_evidence_summary.json`, including the checkpoint-23 archive, Pi support bundle and audit/addendum SHA-256 values.

### 2.2 Checkpoint-24 host verification

The final evidence ledger is in `docs/development/TEST_MATRIX.md`. Key results:

- focused repair regression: **39/39 PASS**;
- broad affected unit regression: **106/106 PASS**;
- support/release focused regression: **31/31 PASS**, plus the final support startup-snapshot and release-format checks;
- final decomposed unit accounting: **40 modules / 394 tests PASS**;
- final deterministic integration accounting excluding release lifecycle: **10 modules / 46 tests PASS**;
- final release lifecycle accounting: **8/8 cases PASS**;
- deferred readiness/documentation closure: **13/13 PASS**;
- canonical `./scripts/ci.sh --phase t0`: **PASS**;
- user-test release-candidate integration after M10.15 closure: **PASS**.

The canonical long aggregate unit/integration attempts were externally interrupted after partial progress and remain labelled **INTERRUPTED / not PASS**. They are not used as false green evidence. The smallest uncertain modules/cases were resumed or decomposed, and the final accounting manifests bind every module/case to preserved passing evidence.

Evidence manifests:

- `docs/development/evidence/v09/checkpoint24/final_unit_accounting.json`
- `docs/development/evidence/v09/checkpoint24/final_integration_accounting.json`
- `docs/development/evidence/v09/checkpoint24/final_release_lifecycle_accounting.json`

## 3. Files changed

Primary implementation surfaces:

- `scripts/release_manager.py`
- `scripts/install.sh`
- `scripts/environment_profile_manager.py` **(new)**
- `src/gonken_agent/support.py`
- `src/gonken_agent/diagnostics.py`

Regression tests:

- `tests/unit/test_m3_3_release_manager.py`
- `tests/unit/test_v09_environment_profile_manager.py` **(new)**
- `tests/unit/test_support_export.py`
- `tests/unit/test_diagnostics_snapshot.py`
- `tests/unit/test_release_readiness.py`

Readiness/control/documentation:

- `scripts/release_readiness.py`
- `scripts/v09_user_test_readiness.py`
- `scripts/validate_v09_docs.py`
- `README.md`
- `docs/RASPBERRY_PI_ACCEPTANCE_RUN.md`
- `docs/USER_SIMULATION_HIL_HANDOFF.md`
- `docs/TROUBLESHOOTING.md`
- `docs/development/MASTER_BLUEPRINT.md`
- `docs/development/MILESTONES.json`
- `docs/development/IMPLEMENTATION_STATUS.md`
- `docs/development/DECISIONS.md`
- `docs/development/TEST_MATRIX.md`
- `requirements/README.md`
- `docs/development/evidence/v09/checkpoint24/*`

## 4. Current implementation truth

### Host/software

- `M10.15`: **host-verified**.
- Target production venv policy and hardware-binding validation are implemented.
- Operator authorization is implemented at installer source level.
- Sensor-deferred profile helper is implemented and host-verified as non-actuating.
- Support/runtime evidence strengthening is implemented and host-verified.

### Real target

The repaired checkpoint-24 installer has **not yet been run on the Raspberry Pi**. Therefore all of the following remain unverified on the repaired package:

- fresh local-checkpoint install reaches `INSTALLATION_COMPLETE`;
- active immutable venv can import/use `gpiod` and `smbus` under target service identities;
- fresh operator login receives `gonken-envctl`;
- environment CLI access succeeds without `PermissionError`;
- GPIO23 ownership/actuation through the repaired environment daemon;
- unloaded relay OFF → ON → OFF;
- relay polarity and boot/shutdown safety;
- PENGLIN/fan power path;
- SHT31 physical operation;
- real voice/wake/audio and reboot/no-login acceptance.

## 5. Blocked items / risks

1. **Target validation is mandatory.** Host tests cannot prove Debian/Python/systemd behavior on the actual Pi.
2. **System-site visibility is deliberately scoped to the Pi target profile.** It increases visibility of root-managed distro Python packages; compatibility is controlled by target-profile scope plus exact runtime API validation and support provenance.
3. **Operator group membership requires a fresh login.** The installer can update the account database but cannot retroactively change supplementary groups in an already-open SSH shell.
4. **Physical actuation remains blocked.** No relay ON command should be issued until the checkpoint-24 target install/preflight gate passes.
5. **No fan-motion claim exists.** Even after relay actuation, software can establish relay/power command state; physical blade motion still requires observation.

## 6. Exact next action

On the Raspberry Pi, use the exact delivered checkpoint-24 archive and checksum, not remote `main`:

```bash
sha256sum -c SHA256SUMS_checkpoint24.txt
python3 -m zipfile -e gonkenlabagent-v09-installer-runtime-repair-checkpoint-24.zip ~/gonken-checkpoint24
cd ~/gonken-checkpoint24/gonkenlabagent-v09-installer-runtime-repair-checkpoint-24
git reset --hard HEAD
./bootstrap.sh --local-checkpoint --bluetooth-audio --bluetooth-device 41:42:06:42:05:80
```

The install must end with governed `INSTALLATION_COMPLETE`. If it does not, stop and collect/upload the new support evidence; do not manually patch the immutable release and do not actuate the relay.

After successful installation, exit/reconnect SSH and follow `docs/RASPBERRY_PI_ACCEPTANCE_RUN.md` through the checkpoint-24 runtime/operator preflight. Only after that preflight passes may the unloaded relay Stage-2 OFF → ON → OFF procedure resume.

## 7. Continuation instruction

**Continue from checkpoint 24 target-install handoff. Install the exact checkpoint-24 archive locally on the Raspberry Pi, require governed `INSTALLATION_COMPLETE`, verify immutable-runtime `gpiod`/`smbus` bindings and fresh `gonken-envctl` operator authorization, and do not resume physical relay actuation until all checkpoint-24 preflight gates pass. If any gate fails, preserve and upload the resulting support evidence and fix only the smallest uncertain layer.**
