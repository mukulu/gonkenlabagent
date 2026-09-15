# GonKenLab Agent V09 — Checkpoint 30 Report

**Checkpoint:** 30 — target activation migration repair  
**Base:** checkpoint 29 (`6466f26a1a9cb97e4c24182505b37cefb766b3c3`)  
**Host state:** M10.25 = host-verified  
**Target state:** M10.24 remains NOT RUN as an integrated acceptance gate

## 1. Target evidence that triggered this checkpoint

The Raspberry Pi 5 physically demonstrated the actuator substrate independently of GonKen: GPIO23 resolves to `gpiochip0` line 23; LOW stopped the relay/fan load, HIGH started it, and LOW stopped it again. That evidence is preserved and does not need to be rediscovered unless contradicted.

Checkpoint 29 then reached target preflight and successfully built release `6466f26...`, but activation stopped with `RELEASE_BINDING_MANIFEST`. A second installer run reached the same boundary. The installer created source-owned failure bundles. `INSTALLATION_COMPLETE` was never reached, so no checkpoint-29 integrated software/voice acceptance is claimed.

## 2. Root cause

The checkpoint-29 candidate was not the failing release. Candidate construction performed strict final validation and emitted `RELEASE_BUILT`. `activate_release` then called activation reconciliation first. The previously active Pi release predates the checkpoint-29 allow-listed hardware-binding bridge and has no `hardware-bindings.json`. Reconciliation incorrectly applied the new contract retroactively to that old post-verified release and aborted before switching to the valid candidate.

## 3. Repair

- bounded legacy transition validation exists only for a release already bound to trusted activation state;
- immutable payload/record/ownership and service-user CLI identity/status smoke remain required;
- embedded immutable release-manager markers distinguish genuine pre-bridge releases from bridge-era releases whose manifest is missing/corrupt;
- normal candidate activation is always strict and cannot opt into legacy compatibility;
- state-bound rollback to a previous pre-bridge release remains available;
- status/reconcile can inspect the state-bound legacy current release without blocking migration;
- binding errors identify the release commit being validated;
- `RELEASE_LEGACY_TRANSITION_SOURCE` makes the compatibility path observable.

## 4. Verification

- affected unit slice: **76 PASS**;
- affected integration slice: **17 PASS**;
- complete unit accounting: **45 modules / 438 tests PASS**;
- deterministic non-release integration accounting: **11 modules / 49 tests PASS**;
- release lifecycle: **9/9 PASS**, including the exact pre-bridge-current → bridge-candidate process migration and interruption/finalization/rollback cases;
- final control unit slice: **41/41 PASS**;
- final control integration slice: **2/2 PASS**;
- documentation/readiness validation and canonical T0: **PASS**;
- aggregate runs that exceeded the execution boundary remain recorded as interrupted, not PASS.

Final control verification also passes: 41/41 focused control unit tests, 2/2 focused control integration tests, milestone/document/readiness validation and canonical T0. Clean-package verification remains the final checkpoint-close step.

## 5. Remaining

Install the exact checkpoint-30 package on the same Raspberry Pi without deleting or editing the old active release. Require the installer to migrate through the bounded legacy transition and reach `INSTALLATION_COMPLETE`. Then continue M10.24 with GonKen CLI fan control, SHT31/I2C, full-real controller, voice/wake/audio, faults, reboot/no-login and update/rollback/reinstall evidence.
