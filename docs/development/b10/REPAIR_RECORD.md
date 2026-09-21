# B10 target-run repair record

Source: exact B9 a732f0bb1ab0e752a395f5250fa5b792d65ac708. See INPUTS.json for actual input identities. Raw target diagnostics remain outside Git; only purpose-limited findings are retained.

## FACTS

- The 2026-09-21 target terminal run built and activated B9, then failed at `ollama_binary` with `ModuleNotFoundError: gonken_agent` in installed `maintenance/ollama_manager.py`.
- B9 creates a release with `.venv` and `maintenance`, not a `src` directory. Its new errors import assumes a checkout. The system Python invocation cannot see the isolated application's site-packages.
- The current support archive records real `sht31` at I2C1/0x44, simulated relay, GPIO23 active-high, manual policy, and a stale voice READY bound to the predecessor release.
- The current generic service/readiness helpers deliberately refuse real-relay profiles irrespective of observed hardware. That software gate is not a hardware failure.
- Current code default thresholds are 28 C ON / 26.5 C OFF with 60-second minimum ON/OFF dwell. Existing valid user policy must not be silently replaced.

## DECISIONS (current user authorization)

- Ship a real-room deployment entry point selecting full-real SHT31/GPIO23 and automatic control; no simulated fallback on a real profile. Preserve simulation as explicit development/test functionality only, not the selected deployment.
- Selecting real hardware is operator authorization to run that configured controller; an uploaded prior physical-acceptance report is not an installation prerequisite. Keep live identity/permission/config checks and fail-safe OFF. Do not claim observed fan motion from a command or successful host test.
- Test installed maintenance with checkout PYTHONPATH removed before packaging, including all newly reachable Ollama helper commands.
- Preserve off-state initialization, valid-sample recovery, hysteresis/dwell, one environment-daemon hardware owner, private evidence, immutable release payloads, and systemd supervision.

## Scope / sequence

B10A: reproduce/fix installed maintenance imports; B10B: real-profile service/readiness and safe policy convergence; B10C: candidate/precondition and restart lifecycle; B10D: downstream model/voice and evidence repairs found by tests; B10 close: complete affected and full current regression corpus, build/extract exact installation candidate, report unimplemented broader blueprint items separately.

Execution status: HOST_VERIFIED_REPAIR; target installation candidate prepared. Full Attempt03 completion and physical acceptance are not claimed.

## B10A outcome

Reproduced before repair: three installed helpers fail with the same missing
application import. Repair copies exact canonical standard-library error,
qualification and model-catalog modules into sealed maintenance, with explicit
installed/source import selection. No global site-packages exposure was added.
24 focused tests PASS; real release build/activation/immutability test PASS.
The release builder now performs bounded clean-environment maintenance import
smokes before activation. Model runtime behavior and real fan operation are not
established by these checks.

## B10B real room-appliance deployment

The persisted target profile used a real SHT31 and simulated relay; its mutable
policy was manual. Added an explicit exact-checkout room-appliance wrapper that
selects full-real and automatic, preserves thresholds/dwell, and routes changes
through the sole environment daemon. Full-real service convergence no longer
requires historical physical PASS artifacts. The selected profile is validated
before GPIO discovery, and live daemon commit/config fingerprints invalidate an
old running simulated process. Simulated-sensor/real-actuator HIL remains distinct.

Added strict finite/type validation of policy and duplicate-JSON rejection.
Environment/source-record/mode helper and installed dependency closure are tested.
B10B focused chain: 61 tests PASS (14.476 s); earlier two static-order expectations
failed because they encoded the old profile-after-GPIO order. They now require the
intentional profile-before-GPIO order and explicit full-real authorization contract.
Real backend controller tests inject host adapters: not physical acceptance.

## B10C candidate preparation before activation

Provisioning helpers and effective config readers now use the exact candidate
release instead of following `current` before the candidate is ready. The engine
finalizes its selected target phase order through a pure validated planner:
model/roster/speech prerequisites precede activation; environment restart/readiness
and policy occur after activation; voice service/readiness follows. Release-only
host tests retain their explicit narrower boundary. Existing mutable dependency
provisioning is still convergent, not a claim of atomic rollback of apt/models.

Actual release build + installer-engine tests: 11 PASS in 37.598 s. The tool
reported timeout after the child completed; its full result log was inspected and
no surviving child process remained. Actual shell registration/planner/engine
fault fixtures plus ordering tests: 24 PASS in 3.669 s. Model/speech failure fixtures
prove the simulated current pointer is unchanged and environment startup was not
called. These are host execution proofs, not real Pi provisioning.

## B10D broad verification and current deployment documentation

All 73 current unit modules (791 cases) and all 13 integration modules (80 cases)
passed at runtime/installer source commit cf737520be6f380c9779b0198faa2c2922aef671.
`VERIFICATION.json` binds every discovered test to its recorded log. Module/case
reruns are not counted twice. Interrupted outer commands preserve completed results;
only uncertain speech/unit work was rerun. No unexplained RUNNING test remains.

Current README/installation/operations/troubleshooting docs point to the explicit
real-room wrapper. Historical simulation-first campaign text is retained with an
explicit current-profile supersession. T0 now syntax-checks the wrapper as well.
Only supported host slots advance in CURRENT_GATES; physical and future feature
slots remain open. The B10 package may be run on the configured Pi without first
uploading historical HIL acceptance. It is not the full Attempt03 stable release.

Known remaining boundaries: no real Pi execution in this host run; no fresh
physical model/audio/wake/fan/soak proof; new display/touch/power-action features
are not implemented here. Late post-activation semantic rollback and transactional
rollback of mutable model/config dependencies remain separately tracked. A model
or voice failure is reported, not suppressed to manufacture installation success.

Final documentation/CI regression: 34 focused reruns PASS; T0/dependency rendering/current-state/docs/syntax PASS. These are reruns, not additional unique tests.
