# V09 Checkpoint 41 — Lifecycle, Runtime, Resource and Model-Finalization Target-Shadow Replay

## Scope

Checkpoint 41 executes a broader reliability batch after checkpoint 40. It expands sanitized replay from hardware/profile readiness into the target states that determine whether the next delivered package is likely to converge: installer state, current-release state, managed systemd state, service restart health, operator authorization, disk headroom and model finalization.

## Implemented

- Added opt-in replay requirements for `operator_identity`, `systemd_runtime`, `release_lifecycle`, `resource_capacity` and `model_finalization`.
- Added state fixtures for ready lifecycle, partial installer state, stale temp artifacts, noncurrent corrupt history, current runtime drift, wrong-release support collection, old systemd units, restart failure, missing operator control group, low disk and interrupted model finalization.
- Expanded release readiness to 22 required target-shadow fixtures.
- Preserved the non-actuating live target-probe boundary. The live collector records resource headroom but does not mutate services, pull models, scan I2C addresses or actuate GPIO.

## Governing Principle

The checkpoint blocks delivery only for states that undermine the current release, installation convergence, service runtime, operator control, model readiness or evidence provenance. Historical release corruption is not treated as a blocker when the current release is exact and the corrupt history is not selected for rollback/update.

## Blueprint Status Summary

| Work package | Status after checkpoint 41 | Notes |
|---|---|---|
| WP-A control-plane reconstruction | Mostly complete | Reliability-first documents, milestones and readiness status are synchronized. |
| WP-B current-release/read-only hardening | Substantially complete | Runtime cache and authoritative drift are host-tested and now replay-gated. |
| WP-C hardware identity and target-probe replay | Substantially complete | GPIO alias/deduplication, target probe and replay fixtures are active. |
| WP-D audio capability abstraction | Substantially complete | USB/direct duplex and ambiguous-audio fixtures are replay-gated. |
| WP-E installer state taxonomy | Substantially complete | Partial installer, stale temp and planned I2C pause states are replay-gated. |
| WP-F service/identity/config/runtime closure | Substantially complete | Service identity, operator control group, managed unit status and restart state are replay-gated. |
| WP-G SHT31/environment commissioning | Host-shadow complete; target evidence open | SHT31 and environment profiles are replay-gated; real target reads remain M10.24. |
| WP-H fan/relay safety | Partially complete | GPIO23/profile evidence is replay-gated; physical fan/relay behavior remains target-run work. |
| WP-I wake/STT/TTS/environment transaction closure | Partially complete | Host and synthetic lifecycle evidence exists; real wake/audio remains target-run work. |
| WP-J dirty-state/fault-injection campaign | Substantially expanded | Low disk, model partials, restart failure and runtime drift now have replay fixtures. |
| WP-K exact archive qualification | Complete as a host/package gate | Archive qualifier is part of the package workflow. |
| WP-L real Raspberry Pi campaign | Open | Requires exact package installation and supervised M10.24 evidence. |
| WP-M stable release | Blocked by WP-L | Stable status requires real target campaign evidence. |

## Remaining Work

- Capture and review real sanitized Raspberry Pi manifests for the exact hardware/service/release state.
- Add any final real-manifest-derived fixtures exposed by that target evidence.
- Qualify the exact candidate archive.
- Run the real Raspberry Pi campaign through `INSTALLATION_COMPLETE`, physical SHT31, relay/fan, audio, wake/voice, reboot/no-login, update, rollback, uninstall/reinstall and support-export evidence.

## Evidence Boundary

Checkpoint 41 does not produce a Raspberry Pi release candidate and does not claim physical acceptance. It improves the internal gate so that the next candidate is less likely to fail from known state/restart/resource/model problems.
