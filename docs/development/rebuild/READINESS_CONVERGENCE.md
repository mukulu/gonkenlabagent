# B4 - canonical runtime freshness and component evidence

## Repair and ownership

FACT (source): B3 component status and model-switch confirmation accepted READY
text without boot/process/release freshness. `doctor` accepted file existence.
Support copied entire readiness dictionaries, including unknown keys, and its
separate tool-broker member always reported READY. These were independent paths
around the more careful installer checks.

The canonical stdlib-only `runtime_readiness.py` now validates all these readers.
It requires a selected immutable release/profile, current boot, live non-zombie
PID and matching process-start ticks. Invalid/missing identity fails closed.
It rejects symlinks, FIFOs, oversized/ambiguous JSON, bool-as-integer identities,
future timestamps, and stale WAITING/READY races; it exports only named metadata.
READY is not a heartbeat: it is not expired merely because a healthy process
has been running a long time. The same module is copied into the sealed
maintenance payload, so installer Python does not depend on an accidental host
package installation.

Component reporting keeps daemon-owned environment status independent from
voice. Disabled environment is DISABLED, not READY. The model startup digest is
published in READY and compared with the qualification record/context before
claiming typed-model-tool readiness. Having the broker code available is not
model qualification. This does not disable existing deterministic voice intents.
Support uses the already collected component/environment snapshots rather than
calculating another broker status or taking a second environment snapshot.

## Verification

`PYTHONPATH=src:. python -m unittest tests.unit.test_attempt03_runtime_readiness
 tests.unit.test_fix5_appliance_manager tests.unit.test_voice_appliance
 tests.unit.test_v09_llm_admin_components tests.unit.test_support_export
 tests.unit.test_v09_model_roster_manager -q`

PASS: 88 tests, including 22 new freshness/component tests. Recorded output:
`evidence/continuation/b4-cascade-final.log`.

The first cascade found a B3 test-oracle defect: support already emitted
`resource_claims.json`, but its exact-member test still omitted that member.
The fixture now requires the member and its no-physical-acceptance flag; the
exact-member assertion was retained, not relaxed.

## Evidence boundaries and remaining work

This is E1 host evidence. It does not establish actual service-user audio, model
inference on the Pi, sensor/relay actuation, no-login reboot, or physical display.
Runtime READY still uses startup identity, not ongoing per-turn inference health.
Effective-config-generation binding remains a later freshness enhancement; this
batch does not claim config changes without service restart have been verified.
No model runtime pin, hardware mode, relay polarity or operational threshold was
changed. No service was started and no GPIO/I2C was opened by this batch.

Next: canonical support/failure archive migration, then fresh broader regression
and exact code-bearing package qualification. Main and dev-stable stay unchanged.
