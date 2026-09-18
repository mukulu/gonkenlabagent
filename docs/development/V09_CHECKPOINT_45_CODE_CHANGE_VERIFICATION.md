# Checkpoint 45 code-change verification

## Scope and acceptance criteria

Checkpoint 45 continues exact Checkpoint 44 commit `e04af9d9977a192fd58e53c50392c74b7dc8b85b` under the V04 blueprint. The verified change set covers dependency-ready host/package work for component observability, phase-aware causal evidence, the governed three-model Ollama lifecycle, typed LLM tool proposals, deterministic clock/environment fast paths, safe environment/fan mediation, and latency/resource instrumentation.

Acceptance requires preserving Checkpoint-44 release/environment behavior, keeping real GPIO23/ELUTENG actuation blocked, preventing model output from acquiring arbitrary execution authority, retaining privacy-minimizing evidence, passing focused and broad host regressions, and remaining explicit that exact-package Raspberry Pi acceptance is still open.

## Governing repository instructions

`AGENTS.md`, V04, `MASTER_BLUEPRINT.md`, `MILESTONES.json`, `TEST_MATRIX.md`, `DECISIONS.md`, and the project continuation/evidence rules govern this verification. Host/mock/replay success is not physical Raspberry Pi acceptance.

## Changed files and risk classification

Risk is **high but bounded** because the change set touches installer/model lifecycle, service restart behavior, runtime routing, model-mediated actuator requests, support evidence, and release readiness.

Major changed areas:

- model authority/lifecycle: `packaging/ollama-model-roster.toml`, `scripts/model_roster_manager.py`, `src/gonken_agent/llm/models.py`, `src/gonken_agent/llm/admin.py`, `src/gonken_agent/llm/ollama.py`;
- typed tool boundary: `src/gonken_agent/tool_broker.py`, `src/gonken_agent/voice_runtime.py`, `src/gonken_agent/environment/intents.py`;
- observability/evidence: `src/gonken_agent/component_status.py`, `src/gonken_agent/support.py`, CLI/operations and environment watch paths;
- installer/release: `bootstrap.sh`, `scripts/install.sh`, `scripts/install_summary.py`, `scripts/lib/install_engine.sh`, `scripts/release_manager.py`, `scripts/release_readiness.py`;
- tests/control/docs: Checkpoint-45 unit/integration tests and development ledgers.

Safety review confirms the model-facing broker exposes no shell, `systemctl`, raw GPIO, raw I2C, filesystem, or network execution primitive. Root-only `systemctl` usage exists only in the administrative model-switch path and is not a model-selected tool. Real room-fan actuation remains unavailable under the recommended `real-sensor-simulated-actuator` profile.

## Original defect reproduction

The predecessor Pi observation established the starting defects/limitations without promoting them to full acceptance:

- Checkpoint 44 still had only legacy `qwen3.5:2b-q4_K_M`, so the V04 three-small-model latency plan had not been commissioned.
- the environment controller and real SHT31 were READY, while the room-fan actuator was simulated;
- the LLM environment-tool broker was not commissioned, so flexible temperature/fan paraphrases could fall through to ordinary text inference without a governed sensor/fan action;
- direct operator-process audio probes could report unavailable even while the service runtime was semantically READY, requiring explicit probe-context evidence.

During Checkpoint-45 integration verification, three text-network harness tests initially failed because they called `chat([])` while the strengthened Ollama client now rejects empty message lists before network behavior is exercised. The production bounded-message validation was retained; the tests were corrected to use a minimal valid user message and all nine text-runtime integration tests pass.

Release repeat testing also appeared to hang at the tool execution boundary. Process inspection localized the delay to immutable-release static validation; the unmodified semantic test completed successfully (about 35.7 seconds). A temporary fixture-shortening experiment was reverted, so acceptance criteria/test semantics were not weakened.

## Checks executed

| Check | Command/method | Result | Evidence |
|---|---|---|---|
| Focused V04 convergence | focused checkpoint-45 unit portfolio | PASS — 85/85 | `evidence/v09/checkpoint45/focused_v04_convergence.log` |
| Full unit phase | `./scripts/ci.sh --phase unit` bounded module runner | PASS — 57/57 modules, 603/603 tests | `full_unit_phase.log`; `build/ci-logs/unit_manifest.json` |
| CLI process | `tests.integration.test_cli_process` | PASS — 5/5 | initial integration log |
| Text runtime | `tests.integration.test_text_runtime_process` | PASS — 9/9 | `text_runtime_final.log` |
| Bootstrap preflight | process integration | PASS — 6/6 | `bootstrap_preflight_process.log` |
| Install engine | process integration | PASS — 10/10 | `process_integration_b.log` |
| Support collection | process integration | PASS — 4/4 | `process_integration_b.log` |
| Ollama lifecycle | bounded process runs | PASS — 5/5 | `process_integration_b.log`, `ollama_lifecycle_final_case.log`, `ollama_service_conflict_final.log` |
| First-install launcher | process integration | PASS — 4/4 | `process_integration_c.log` |
| Uninstall lifecycle | process integration | PASS — 2/2 | `process_integration_c.log` |
| Release lifecycle | bounded/polled process runs | PASS — 12/12 | release lifecycle logs |
| Speech lifecycle | bounded process run | PASS — 12/12 | `speech_lifecycle_process.log` |
| Static/control | `git diff --check`, compileall, shell syntax, milestone sync, T0 | PASS | `static_control_gates.log` plus final close rerun |
| Release readiness target-shadow | `scripts/release_readiness.py` | PASS — 24/24 replay fixtures; no physical acceptance claim | pre-seal/final readiness JSON |

## Generated artifacts and manual review

The source tree contains a sanitized Checkpoint-44 target observation and a machine-readable Checkpoint-45 host-verification ledger. Failure/timeout logs are retained where they contributed to diagnosis rather than being overwritten by later success. The final immutable package qualification and fresh-extraction verification are intentionally post-tag delivery artifacts and therefore live outside the source archive.

Manual diff review covered the model roster, tool authority boundary, mutating-fan authorization, release/install ordering, support privacy/evidence fields, model-switch rollback, and release-readiness state transition.

## Regression protection

- exact model roster/tag/digest/quantization admission tests;
- provisioning/repeat/offline/rollback tests;
- typed tool schema/bounds tests;
- deterministic clock/environment route tests;
- mutation authorization, negation/hypothetical/direction-mismatch/replay tests;
- support ZIP evidence/privacy tests;
- doctor service-runtime versus direct-probe context regression;
- environment watch passive-observer tests;
- install dependency/summary and release-readiness tests;
- existing release, speech, environment, target-shadow and archive regression suites remain in the broad unit portfolio.

## Skipped or unavailable checks

Not run in host verification because they require the exact Raspberry Pi package/hardware:

- downloads/runtime compatibility of all three admitted models on Pi;
- real Pi latency/RAM/thermal measurements and model-quality comparison;
- spoken local-time/date and real-SHT31/simulated-fan tool transactions;
- reboot/no-login and model-selection persistence;
- real GPIO23/KKHMF/PENGLIN/ELUTENG actuation;
- physical fan motion/RPM (unsupported by current room-fan hardware);
- full target update/rollback/reinstall/soak campaign.

## Residual risks and rollback

The three-model roster increases first-install disk/network work and has not yet been measured on the 4 GB Pi. Small-model semantic tool selection remains target/model-quality evidence, not a host-proven quality claim. The legacy Checkpoint-44 model remains available during the rollback window and administrative model switching is atomic with service-convergence rollback. The Checkpoint-44 package/tag remains an immutable fallback if target validation of Checkpoint 45 fails.

## Readiness verdict

**READY FOR EXACT TAG/ARCHIVE QUALIFICATION AND RASPBERRY PI TARGET CAMPAIGN; NOT PHYSICALLY ACCEPTED.**

Source verification supports sealing Checkpoint 45 after final clean-tree/T0/readiness checks. Exact archive qualification and independent fresh-extraction verification must pass before delivery. Real GPIO23/ELUTENG actuation remains blocked until supervised WP-45C.
