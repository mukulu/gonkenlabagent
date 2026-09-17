# V09 Checkpoint 44 — V04 component/readiness and environment-convergence foundation

## Scope and authority

Checkpoint 44 starts the implementation cycle governed by `GonKenAgent_V09_CKPT43_to_Full_Component_Convergence_Blueprint_Prompt_V4_GOLD.md` (SHA-256 `4e7597baaa8410d988f6f452adb9672969a734ec32f729c788055ce060d19ba8`) from exact Checkpoint 43 commit `14c0438e84e7ba61f57290d3facaa05e8fd91cac` / tag `checkpoint/v09-43-semantic-convergence`.

The fresh Checkpoint-43 target failure bundle used as a regression source is `gonken-install-failure-20260917T181316Z-605043.zip` (SHA-256 `f38d15318afddc952c5f766efa39eb8af227c7d1fdc937974648881ee6969f51`). It showed a current `VOICE_RUNTIME_READY` record carrying `release_commit=development` / `release_profile=development` while the immutable active release was Checkpoint 43. It also preserved historical/recovered voice failures that must not override current component state.

This checkpoint deliberately does **not** implement the V04 multi-model/tool-broker tranche yet and does not claim physical Raspberry Pi acceptance.

## Evidence ledger

| Class | Finding | Checkpoint-44 response |
|---|---|---|
| FACT | Checkpoint 43 runtime readiness could lose immutable release identity through a symlinked venv interpreter path. | Runtime identity now derives from the installed `gonken_agent` package anchor; a production-shaped symlinked-venv regression is mandatory. |
| FACT | Current READY and historical event counts coexisted in target evidence. | Component readiness v2 separates current status, historical last failure, recovery state and evidence tier; target-shadow now contains an exact readiness-identity mismatch fixture. |
| FACT | The real SHT31 worked on target while environment commissioning remained disabled/partial. | Bootstrap/source record now carries one explicit canonical environment profile and SHT31 address. |
| FACT | `env serve --check` could initialize persistent policy state and create a permission failure when run through sudo. | `--check` now uses non-initializing construction; policy read/write/permission errors are separated and tested. |
| FACT | A root-owned `policy.json` and a temporary environment systemd drop-in occurred during target repair. | Managed environment reconciliation validates/repairs safe policy metadata, removes only the exact known temporary Checkpoint-43 drop-in and fails closed on unknown administrator drop-ins. |
| FACT | `gonken-environment.service` could be installed but disabled, and a repaired service could hit systemd restart-rate state. | Commissioned non-actuating profiles explicitly enable, reset-failed, restart and verify the service. Real-relay profiles pause with exit 78 for supervised commissioning. |
| FACT | systemd liveness alone is not environment readiness. | A passive semantic gate now requires daemon IPC health, `sensor=ready`, `actuator=READY`, and exact expected backends before model provisioning continues for safe commissioned profiles. |
| DECISION | Real GPIO23/fan actuation must not be introduced by a generic install. | `sensor-deferred-relay` and `full-real` are configuration-capable but installation pauses before real actuator commissioning. |
| DECISION | Package output must expose subsystem truth independently. | Final install terminal output reports voice, Ollama, environment controller, sensor, room-fan control and LLM/tool-broker state separately; tool-broker remains explicitly `NOT_COMMISSIONED` in Checkpoint 44. |
| BLOCKED TARGET GATE | SHT31 physical behavior, relay/fan integrated control, real wake/audio, reboot/no-login, and physical tool transactions require the Pi. | Remain open under M10.24 / later V04 target tranches. |

## Implemented source changes

- `src/gonken_agent/release_identity.py`: one package-anchor runtime release identity authority.
- `src/gonken_agent/readiness.py`: component-readiness v2 primitives and aggregation.
- `src/gonken_agent/voice_runtime.py`: semantic readiness uses the package release identity rather than resolved interpreter location.
- `src/gonken_agent/environment/policy.py`: explicit non-mutating/default/init/access operations and precise policy I/O error taxonomy.
- `src/gonken_agent/environment/daemon.py`, `src/gonken_agent/cli.py`: `env serve --check` no longer creates production policy state.
- `scripts/environment_profile_manager.py`: safely completes the exact Checkpoint-43 compatible partial environment config; exact status verification added.
- `scripts/environment_service_manager.py`: runtime ownership/mode reconciliation, known temporary-drop-in migration, safe profile convergence, restart-state recovery and real-actuator planned pause.
- `scripts/environment_readiness.py`: passive daemon semantic-readiness gate for `full-simulation` and `real-sensor-simulated-actuator`.
- `bootstrap.sh` / `scripts/lib/install_engine.sh`: governed `--environment-profile` and `--sensor-address` source-record contract.
- `scripts/install.sh`: explicit environment profile → commissioning → semantic readiness steps, with independent final component summary.
- `scripts/target_probe.py` / `scripts/release_readiness.py`: fresh Checkpoint-43 readiness-identity mismatch target-shadow regression.
- `scripts/installer_failure_bundle.py`: safe environment profile/address provenance in installer source evidence.

## Verification completed before checkpoint close

Focused/affected tests already passed during implementation:

- release-identity + voice/appliance: 36/36 PASS;
- environment policy/non-mutation: 19/19 PASS;
- environment service/profile convergence slices: PASS;
- focused component/environment/bootstrap/target-shadow portfolio: 114/114 PASS;
- environment/install/release-manager affected portfolio: 119/119 PASS;
- Checkpoint-43 readiness identity fixture: expected FAIL localized as `READINESS_IDENTITY_MISMATCH`;
- release readiness target-shadow corpus expanded from 23 to 24 required fixtures.

Final checkpoint-close gates and exact-archive qualification are recorded separately under `docs/development/evidence/v09/` after the final source commit/tag.

## Remaining V04 work

Dependency-ready work after this checkpoint includes the richer phase-aware causal support/journal tranche, enhanced `env watch`/probe/health operator UX, multi-model lifecycle and benchmarking, typed LLM tool broker, paraphrase/adversarial tool-routing corpus, model-switching UX, and then the supervised Raspberry Pi hardware/reboot/soak campaign.

## Exact next target intent

For the next real-Pi run, commission the already-observed SHT31 without automatically touching GPIO23:

```bash
./bootstrap.sh --local-checkpoint \
  --environment-profile real-sensor-simulated-actuator \
  --sensor-address 0x44
```

Add Bluetooth options only when intentionally required by that target. If I2C requires a reboot, rerun the exact same command afterward. If installation fails, upload the one combined evidence ZIP emitted by the installer. Do not manually repair ownership/drop-ins first; Checkpoint 44 needs to prove that its reconciler handles the known target state.

## Continuation

Continue from the recorded checkpoint and execute the next dependency-ready batch.

## Verification closeout update

- The initial broad unit aggregate was **INTERRUPTED** by the execution boundary late in `test_support_export`; it is preserved as `ckpt44_full_unit.log` and is not reported as a completed PASS.
- The smallest uncertain suffix was then decomposed and fully accounted: support export 16/16 PASS; architecture/archive/docs 30/30 PASS; environment 127/127 PASS; target/voice/Bluetooth 142/142 PASS.
- Process regressions pass: support/bootstrap 10/10 and install-engine/uninstall 12/12. The first process aggregate contained one test-module naming error; the corrected invocations are retained separately rather than hiding that invocation defect.
- Verification discovered a permission false-green: runtime metadata postconditions checked modes but not owner/group. The reconciler now verifies owner/group/mode and reapplies final directory modes after `chown`; the focused post-fix regression is 41/41 PASS.
- Release readiness now includes M10.38 and M10.39 as required host-verified milestones and reports 63/63 required host items with 24/24 target-shadow fixtures under `--allow-dirty`.
- Static close gates pass: compileall, shell syntax, documentation validator, milestone sync, `git diff --check`, and T0.
