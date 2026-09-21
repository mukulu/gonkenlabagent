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

Execution status: IN_PROGRESS. No application or physical acceptance implied.

## B10A outcome

Reproduced before repair: three installed helpers fail with the same missing
application import. Repair copies exact canonical standard-library error,
qualification and model-catalog modules into sealed maintenance, with explicit
installed/source import selection. No global site-packages exposure was added.
24 focused tests PASS; real release build/activation/immutability test PASS.
The release builder now performs bounded clean-environment maintenance import
smokes before activation. Model runtime behavior and real fan operation are not
established by these checks.
