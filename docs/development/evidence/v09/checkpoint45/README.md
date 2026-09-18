# Checkpoint 45 host evidence notes

Authoritative compact outcome: `checkpoint45_host_verification_summary.json`.

The directory deliberately retains selected interrupted/failed diagnostic logs as well as final passing reruns. A log that contains `FAIL`, an incomplete last test line, or an older readiness label is **historical evidence**, not the final checkpoint verdict. This preserves the causal path instead of rewriting history after a repair.

Key final evidence:

- `focused_v04_convergence.log` — 85/85 focused tests PASS.
- `full_unit_phase.log` — bounded unit runner PASS for 57 modules; underlying unit logs account for 603 tests.
- `text_runtime_final.log` — final 9/9 text-runtime process PASS after adapting the harness to the strengthened non-empty message contract.
- `ollama_lifecycle_final_case.log` + `ollama_service_conflict_final.log` + the completed cases in `process_integration_b.log` — all five Ollama lifecycle cases accounted PASS.
- `release_lifecycle_remaining.log` plus the earlier partial/diagnostic release logs — all 12 release-lifecycle cases accounted PASS; the apparent repeat hang was slow validation, not deadlock.
- `speech_lifecycle_process.log` — 12/12 PASS.
- `final_source_close_gates.log` — final source static/control rerun PASS.
- `release_readiness_regression.log` — readiness transition regression PASS after removing the stale host/replay next-action message.

Important historical/diagnostic evidence:

- `process_integration_a.log` and `text_network_failures_isolated.log` capture the three harness failures caused by calling the strengthened client with an empty message list.
- `text_network_regression_fixed.log` and `text_runtime_final.log` prove the corrected harness without weakening the production validation.
- `process_integration_b.log`, `release_lifecycle_process.log`, and `release_lifecycle_repeat_case.log` end at bounded execution/streaming boundaries; later focused runs account for the unfinished cases.
- `release_repeat_diagnosis2.log` records direct process observation used to distinguish slow immutable-release validation from a deadlock.
- `release_readiness_preseal.json` predates the final readiness-label repair and is retained only as the reproduction of that stale continuation-state defect.

Post-tag exact archive qualification and independent fresh-extraction verification are delivery artifacts outside this immutable source checkpoint.
