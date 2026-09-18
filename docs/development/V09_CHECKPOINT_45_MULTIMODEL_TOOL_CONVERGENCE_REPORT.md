# V09 Checkpoint 45 — V04 multi-model, typed-tool, causal-evidence convergence

## Scope and authority

Checkpoint 45 continues V04 from exact Checkpoint 44 commit `e04af9d9977a192fd58e53c50392c74b7dc8b85b`. It ingests the fresh Checkpoint-44 Raspberry Pi observation as evidence without promoting hybrid operation into full physical acceptance.

This checkpoint implements the dependency-ready host/package work for WP-44D/E/F/G/H/I/O/P/Q and packages those capabilities for the next Pi campaign. Real GPIO23/ELUTENG fan actuation remains explicitly blocked until supervised WP-45C.

## Fresh target evidence ingested

The Checkpoint-44 Pi installation reached `INSTALLATION_COMPLETE` with `real-sensor-simulated-actuator`. The environment daemon reported READY with a real SHT31 on bus 1/address `0x44`, approximately 27.5 C and 56.2–56.3% RH during the supplied observation, while the room-fan actuator remained simulated and commanded OFF. The only installed Ollama model was still the legacy `qwen3.5:2b-q4_K_M`. The direct operator-process doctor audio probe reported unavailable input/output even though the semantic voice runtime was already READY; Checkpoint 45 therefore makes that context difference explicit rather than allowing the probe to overwrite service-runtime truth.

The sanitized machine-readable observation is `docs/development/evidence/v09/checkpoint45/checkpoint44_target_hybrid_observation.json`. It is evidence of the observed target state, not a substitute for the later exact-package acceptance campaign.

## Implemented

- Exact governed three-model roster: `qwen3:0.6b` default, `lfm2.5-thinking:1.2b`, and `qwen3.5:0.8b`; legacy Checkpoint-44 model retained during rollback window.
- Online resumable and preseeded-offline provisioning modes, digest/quantization checks, disk headroom, inference/tool API smoke, and one-loaded-model policy.
- Atomic active-model selection, root-governed switching, service convergence verification, automatic rollback, and persistence of an operator-selected admitted model across installer reruns.
- `gonken-agent llm status/models/capabilities/benchmark/switch`, including all-model non-executing semantic tool qualification and optional thinking benchmarks.
- Typed Ollama tool-calling with thinking disabled by default and bounded tool-call structures.
- Governed tool broker for local date/time, SHT31/environment reading, environment/fan status and room-fan power through the environment daemon only. No shell, systemctl, raw GPIO, raw I2C, file or network execution is exposed to the model.
- Deterministic fast paths for clock and common environment/fan paraphrases; LLM tool selection is a fallback for semantic variation. Mutation still requires independent explicit present-tense user authorization.
- Read-only tool calls may run concurrently within the two-call bound; mutations remain serialized and duplicate mutations within one turn are rejected.
- Independent component status for voice, active Ollama model/roster, environment controller, real/simulated sensor provenance, fan backend/command state and tool broker.
- Richer passive `env watch` (`--once`, `--changes-only`, `--health`) without introducing a second SHT31 owner.
- Content-free per-turn route/latency metrics and content-free model benchmark resource snapshots.
- Phase-aware single-ZIP evidence: latest install run ID, boot/release/readiness identity, current component state, bounded same-boot reason-code summaries, permissions, effective systemd properties/drop-ins, config provenance, model roster/loaded state, tool policy, collection failures and causal findings.
- Doctor audio output now distinguishes an operator-process direct probe failure from an already-ready service runtime. Hybrid simulation status now directs the operator to `env read/watch` for a real sensor instead of printing misleading simulated `temp=unavailable`.

## Safety boundary

Checkpoint 45 does not automatically commission the real relay. With `real-sensor-simulated-actuator`, natural-language fan commands affect only the simulated actuator. Full-real GPIO23/ELUTENG operation remains a supervised target gate. Software continues to report commanded room-fan power only; physical blade motion and RPM are unavailable with the current room-fan hardware.

## Verification state

Implementation has been validated incrementally in committed batches. Final broad regression, release-readiness, T0, exact tagged archive qualification and fresh-extraction reruns are required before this report may be treated as checkpoint-close evidence. Their final results are appended during checkpoint close.

## Remaining target work

1. Exact-package Pi provisioning of the three-model roster and live compatibility smoke against the pinned Ollama runtime.
2. Per-model semantic tool-quality matrix and latency/memory/thermal benchmarks on the Pi.
3. Natural voice tests for local time/date, temperature/humidity, fan status and simulated fan ON/OFF.
4. Reboot/no-login and model-selection persistence.
5. Only after the above is stable: supervised WP-45C real GPIO23/ELUTENG actuation, followed by tool HIL and lifecycle/soak gates.
