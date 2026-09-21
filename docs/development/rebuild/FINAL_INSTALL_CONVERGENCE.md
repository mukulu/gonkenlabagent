# B7: fresh final installation postconditions

## Defect and reproduction

The prior install-summary command returned zero for a DEGRADED summary. The
installer then printed hard-coded READY component lines and INSTALLATION_COMPLETE
outside the installer engine. A stale status record or a late failed component
could therefore be reported as success. The independent summary reader also did
not use the B4 boot/process/release validator or require model qualification stages.
The old graph tests inspected historical log tokens instead of exercising this
last branch, so they did not protect the semantic exit contract.

## Repair

- Final summary consumes the canonical boot/process/release/profile-bound reader,
  validates active model digest, and rejects newer same-process waiting evidence.
- Roster labels alone are insufficient: canonical qualification requires exact
  membership and identity/inference/tool/unload stages for the configured context.
- `install_summary.py --require-ready` returns 75 on a degraded final voice/service
  state. Plain inspection remains available without a completion claim.
- `gonken-agent components --require-ready` checks the required selected-profile
  components. Disabled environment is optional; enabled environment must be READY
  with the configured sensor/relay backends and matching simulation provenance.
- Installer final convergence invokes both bounded gates. A failed gate uses the
  existing canonical failure collector once and exits without INSTALLATION_COMPLETE.
- Bluetooth preference is no longer printed as proven pairing. Actual route/device
  details remain in diagnostic evidence. No new recording or GPIO probe is added.
- The immutable maintenance payload includes both canonical Python dependencies.

## Verification

107 tests passed in 4.432 seconds using the six modules below. New tests execute
only the actual final shell function/branch with explicit non-actuating fakes;
they never source/run the complete privileged installer. They cover summary
failure, component failure, timeout, successful completion, standalone maintenance
imports, stale identity/digest, malformed selection/roster, disabled environment,
required environment and refusal of simulation as a real-backend substitute.

```text
PYTHONPATH=src:. python -m unittest \
  tests.unit.test_attempt03_final_convergence \
  tests.unit.test_m3_6_install_summary \
  tests.unit.test_v09_install_dependency_graph \
  tests.unit.test_v09_llm_admin_components \
  tests.unit.test_attempt03_runtime_readiness \
  tests.unit.test_m3_3_release_manager -q
```

`b7-cascade.log` preserves the result. Two pre-existing structural tests were
updated to inspect the shared failure delegation and actual maintenance contract;
new executable negative cases replace reliance on static success-token presence.
Initial new negative fixtures used non-schema field names; these were corrected
to the production readiness schema, not accommodated by weakening validation.

## Scope and remaining gates

Host evidence only. This repairs the final success boundary, not all late release
activation/rollback ordering. CP46.5.2 remains WIP because activation ordering and
configuration-generation binding still require work. Pi install/no-login reboot,
audio, admitted model usability, sensor/fan and physical acceptance remain open.
No service was started, no device was actuated, and no stable branch was promoted.

## B7R1: bounded Bluetooth regression timing

The broad unit runner's 15-second module budget interrupted two pre-existing busy
Bluetooth tests. Each mocked every Bluetooth/device operation but still performed
20 real half-second sleeps: the pair consumed 20 seconds without hardware evidence.
The test-only repair mocks sleep and asserts the complete 20 x 0.5-second retry
schedule. Both USB fallback and no-fallback failure semantics remain tested. The
production retry loop, deadlines and acceptance criteria are unchanged. All 28
Bluetooth tests then passed in 0.014 seconds (`b7-bluetooth-timing.log`). The initial
TIMEOUT log remains in external campaign evidence, not recast as a product failure.
