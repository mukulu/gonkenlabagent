# V09 Checkpoint 43 — Reliability-First Semantic Convergence Report

## Status at host-convergence boundary

- **Base package:** checkpoint 42, tag `checkpoint/v09-42-single-zip-target-evidence`, commit `3a0c78e`.
- **Governing prompt:** `GonKenAgent_V09_CKPT42_to_Single_Evidence_Architecture_Blueprint_Prompt_V2_GOLD.md`, SHA-256 `5ff8e6c141e7f1ef97ea40aaeb8b63acdf9e17f5d6be59651259ada00ff9fad5`.
- **Current implementation branch:** `dev/v09-43-convergence-v2`.
- **First persisted implementation commit:** `fa410670a8cb1825acb3111edfd67145c4f5e7ea` (`Implement checkpoint 43 convergence core`).
- **Physical Raspberry Pi acceptance:** **NOT RUN for checkpoint 43**. The supplied 2026-09-17 checkpoint-42 evidence is diagnostic input, not acceptance of this new package.

## Completed scope

1. Sanitized the fresh checkpoint-42 audio-runtime failure into target-shadow regression evidence.
2. Reworked PipeWire capture to bounded raw S16LE mono plus application-owned canonical WAV construction; added precise capture failure classes.
3. Added freshness-bound semantic readiness with current release/boot/PID/age binding and causal dependency reporting.
4. Prevented stale readiness reuse at systemd start and made installer readiness distinguish systemd liveness from application readiness.
5. Extracted a canonical evidence engine with v2 index, member hashes, safe ZIP publication, output placement and sudo-caller ownership return.
6. Converted installer failure into a combined one-ZIP orchestration of canonical support evidence plus namespaced installer facts.
7. Added metadata-only exact-service-user audio-session support evidence and protected it from interactive-user misattribution or unnecessary stable Bluetooth identifiers.
8. Added launcher/bootstrap/installer responsibility-boundary regression tests.
9. Expanded release readiness to 23 target-shadow fixtures and changed replay to one in-process probe load so the required matrix remains fast and observable.
10. Updated operator/troubleshooting/target-run documentation for one-ZIP failure handling, semantic readiness, service-user audio diagnostics and the environment commissioning ladder.

## Verified host evidence

- Repair tranche: **135/135 PASS**.
- Support privacy/exact-service-context slice: **16/16 PASS**.
- Responsibility boundary / launcher / bootstrap / installer graph: **23/23 PASS** after correcting new-test assumptions; failed intermediate runs are retained as diagnostic evidence.
- Downstream voice/speech/Ollama/Bluetooth/environment convergence: **249/249 PASS** in 157.808 s.
- Install/uninstall interruption and rerun lifecycle: **12/12 PASS**.
- Release lifecycle: the aggregate channel exceeded the execution-output boundary and was decomposed instead of repeated unchanged. All named release lifecycle cases were then accounted for by the preserved partial run plus focused reruns, including release build/repeat/cache, low-space, target-boundary, pre-bridge migration, prior-release non-execution, stale-history tolerance, activation interruptions/rollback/tamper protection and candidate-finalization recovery.
- Documentation validator: **PASS**.
- Target-shadow readiness: **23/23 expected outcomes PASS**; the optimized readiness run was about **0.75 s** during implementation versus roughly 15 s before in-process replay optimization.

## Defects encountered during this cycle

### D43-A — baseline Python path invocation

The first focused baseline command omitted the project `PYTHONPATH` and produced import errors. Re-running with the repository's expected `PYTHONPATH=src:.` produced the valid 41/41 baseline. This was an invocation defect, not a product failure.

### D43-B — target-shadow readiness timeout false-red

Adding the 23rd replay fixture while preserving one subprocess per fixture made the readiness unit run exceed its test budget. Root cause was checker startup overhead, not target-state failure. The checker now loads `target_probe.py` once and replays fixtures in-process; CLI behavior remains independently tested.

### D43-C — responsibility-boundary test assumptions

The first new structural test asserted invented textual names (`gonken_preflight`, an unquoted step token and `gonken_run_step`) that are not the repository's actual contracts. The test was corrected to assert real target/resource/privilege validation, quoted installer registration and `gonken_run_registered_steps`. No product source change was made to satisfy a false test assumption.

### D43-D — broad lifecycle aggregation exceeds the interactive execution boundary

The broad release lifecycle campaign is intentionally expensive. Rather than repeating it unchanged, the run preserved completed cases and the remaining uncertain cases were isolated and executed independently. This follows the project's anti-hang/anti-loss policy and avoids converting tool/session boundaries into false product failures.

## Final host/static gate before archive qualification

- clean release readiness: **READY_FOR_HOST_TARGET_SHADOW_GATE**, host-required **61/61**, target-shadow **23/23**, tree clean;
- `./scripts/ci.sh --phase t0`: **PASS**;
- `compileall`, `git diff --check`, milestone synchronization and V09 documentation validator: **PASS**.

The first readiness attempt in this closeout wrote its log inside the repository before running, making the tree dirty by construction. That false-red is retained as evidence; the gate was rerun from the unchanged commit with output outside the tree and passed.

## Archive-qualification evidence

A clean tagged RC1 archive was built from commit `d0c40d000699b7e6ec174df4cf569281cd77bd4e` at tag `checkpoint/v09-43-semantic-convergence-rc1`. Archive SHA-256 was `ff6f9699d064dbbd6351fa5f261dcdb35edabb72090ad7b790d3065669170b53`. `archive_qualifier.py` passed archive structure, clean extracted Git status, exact commit, exact tag, `git fsck --strict`, milestone synchronization, release readiness and T0 from the extracted archive. This closes the host/package evidence needed to mark M10.38 host-verified.

## Source-checkpoint closeout and packaging boundary

Checkpoint 43 source implementation is **host-verified and closed for source-level work**. The authoritative handoff source is the exact Git tag `checkpoint/v09-43-semantic-convergence`; consumers must verify the tag/commit from the extracted repository rather than relying on a copied commit string in prose. Repository-internal gates are complete: milestone synchronization, documentation validation, release readiness, T0, focused regression portfolios and the post-verification repair campaign all pass.

The immutable distribution ZIP is necessarily created **after** the source tag exists. Therefore its ZIP SHA-256 and the archive-qualifier result are external handoff evidence and are intentionally not embedded in this source report: embedding the final archive hash inside the archive would change the archive itself. Before user handoff, the operator/automation MUST build from a fresh clone of the exact tag, run `scripts/archive_qualifier.py` against that exact ZIP, extract it afresh, rerun the focused evidence/readiness portfolio, verify ZIP integrity, and record the resulting SHA-256 in the accompanying handoff artifact.

The next dependency-ready work after a qualified archive is the real Raspberry Pi campaign described in `docs/RASPBERRY_PI_ACCEPTANCE_RUN.md`. No further host refactoring is required merely to proceed to that campaign.

## Target boundary

The next package may be called a qualified **Raspberry Pi release-candidate checkpoint**, not a stable or physically accepted release. The exact Pi campaign must still prove the service-account microphone/speaker path, `GonKen` wake transaction, real SHT31 behavior/placement, relay/fan electrical and motion behavior, reboot/no-login convergence and lifecycle operations. A failed target install should now return one combined evidence ZIP as the primary next-cycle input.

## Final code-verification repair pass

The mandatory final code-change verification reviewed the complete checkpoint-42-to-43 diff and found three issues worth repairing before final delivery rather than listing as residual risk:

1. an explicit new `--output-dir` could have been created by a root/sudo collector, making the parent directory inaccessible even after the ZIP itself was returned to the invoking user;
2. the new checkpoint-43 acceptance section repeated the current lab Bluetooth device address as a copy/paste example, contrary to the hardware-instance-agnostic design rule;
3. readiness identity rejected stale boot/release/PID records but did not yet distinguish PID reuse or dependency-profile drift.

The repair now requires explicit output directories to pre-exist, removes the target-specific Bluetooth identity from the new runbook, and binds readiness to release profile plus Linux process start ticks. New regression tests cover missing output-directory rejection, profile drift and process-start drift.

Post-repair evidence:

- focused evidence/readiness/voice/target-shadow/responsibility portfolio: **102/102 PASS**;
- speech lifecycle: aggregate execution exceeded the interactive boundary, so already completed cases were preserved and unfinished cases were run independently; all **12/12 PASS**;
- install-summary/Bluetooth remainder: **34/34 PASS**;
- environment controller/profile/simulation/CLI/voice/acceptance remainder: **124/124 PASS**;
- installer/uninstaller interruption/recovery: **12/12 PASS**;
- `git diff --check`: **PASS**.

This verification pass does not change the target boundary. The repaired exact package must still be rebuilt, qualified, extracted and rerun before handoff, and real Raspberry Pi evidence remains required for physical acceptance.
