# V09 Checkpoint 30 Change Verification Report

## Scope

Repair the checkpoint-29 Raspberry Pi activation failure without weakening the strict current release contract. Preserve the already-observed GPIO23/relay/fan evidence and leave integrated physical acceptance open.

## Risk classification

- **High:** immutable release activation/reconcile/rollback state machine.
- **High:** security/integrity risk if legacy compatibility could be abused to activate an arbitrary invalid candidate.
- **Medium:** upgrade/rollback compatibility from previously accepted releases.
- **Medium:** diagnostic provenance and target resumability.
- **No physical acceptance implied:** host/process tests cannot establish Pi service, SHT31, audio or voice behavior.

## Defect reproduction

Target checkpoint 29 built its candidate, then `activate_release` rejected the previously active pre-bridge release because the new binding-manifest policy was retroactively applied during reconciliation. Re-running reproduced the same deterministic failure.

## Change reviewed

The release manager now separates strict candidate validation from bounded state-bound legacy transition validation. Compatibility requires trusted activation-state linkage and a demonstrably pre-bridge embedded manager; new/bridge-era candidates remain strict. Rollback/status/reconcile use compatibility only where prior trusted state makes it necessary. Errors now name the release under validation.

## Regression protection

- exact process-level old-active → new-candidate migration;
- arbitrary pre-bridge candidate rejection;
- bridge-era missing-manifest rejection remains covered by target binding tests;
- state-bound rollback/status;
- activation interruption and failed post-switch rollback;
- finalization interruption recovery;
- installer false-complete/stale-state repair;
- adjacent environment/I2C/SHT31/support/voice affected suites.

## Verification evidence

- affected unit: 76 PASS;
- affected integration: 17 PASS;
- complete unit accounting: 45 modules / 438 PASS;
- deterministic integration: 11 modules / 49 PASS;
- release lifecycle: 9/9 PASS.

The broad aggregate wrappers that exceeded the session boundary are retained as INTERRUPTED and are not used as PASS evidence; their constituent uncertainty was decomposed into bounded passing evidence.

## Residual risk / verdict

**Host verdict:** repair is eligible for target retest after final control-plane/T0/package checks.  
**Target verdict:** NOT RUN for checkpoint 30. The next indispensable evidence is a real upgrade reaching `INSTALLATION_COMPLETE`; only after that may M10.24 integrated hardware/voice acceptance resume.
