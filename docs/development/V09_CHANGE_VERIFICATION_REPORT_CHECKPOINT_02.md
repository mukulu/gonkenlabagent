# V09 Change Verification Report — Checkpoint 02

## Scope

This report verifies the M10.4 deterministic controller-core change on branch `v09-environment-foundation`.  The change adds pure host-testable controller logic and tests only.  It does not implement hardware adapters, daemon ownership, AF_UNIX IPC, CLI, voice, installer, diagnostics, dashboard or physical acceptance.

## Governing instructions and sources

- `AGENTS.md` requires dependency-ready progress, proportionate checks, updated ledgers, committed resumable checkpoints and explicit separation of host/mock evidence from Raspberry Pi evidence.
- The V09 blueprint requires M10.4 to implement the MANUAL/SEMI_AUTOMATIC/AUTOMATIC/DISABLED state machine with hysteresis, dwell, median valid samples, stale-sensor safe-off, recovery, reason codes and threshold-change semantics.
- V09 Checkpoint 01 required inspection or classification of the existing Ollama lifecycle timeout before M10.4 implementation.

## Changed-file and risk classification

| Area | Files | Risk | Verification focus |
|---|---|---|---|
| Controller core | `src/gonken_agent/environment/controller.py`, `src/gonken_agent/environment/__init__.py` | Medium | State transitions, mode semantics, dwell/hysteresis, staleness/recovery, policy update effects, no hardware imports |
| Controller tests | `tests/unit/test_v09_environment_controller.py` | Medium | Positive, negative and boundary paths for MANUAL/SEMI/AUTO/DISABLED |
| Development ledgers | `docs/development/*`, `docs/development/evidence/v09/*` | Medium | Accurate M10.4 status, evidence, residual risk and next action |

## Checks executed

| Check | Result | Evidence |
|---|---:|---|
| Isolated Ollama lifecycle timeout recheck | TIMEOUT / INTERRUPTED | `docs/development/evidence/v09/wp_c_ollama_lifecycle_timeout_recheck.log` |
| M10.4 affected controller/config/domain/policy suite | PASS, 50/50 | `docs/development/evidence/v09/wp_c_controller_affected_tests.log` |
| Full host unit suite | PASS, 262/262 | `docs/development/evidence/v09/wp_c_full_unit.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_c_static_gates.log` |

## Regression protection added

- Manual mode test protects deliberate actuator state from temperature and sensor-failure side effects.
- Disabled mode test protects fail-closed ON rejection.
- Semi-automatic test protects the no-autostart invariant and auto-stop/disarm behavior.
- Automatic test protects recovery gating, hysteresis and dwell timing.
- Stale-sensor test protects safe-off and valid-sample recovery sequencing.
- AUTO direct-command test protects the MANUAL-override rule.
- Policy-update test protects stop-condition reconciliation and SEMI no-autostart behavior.
- Source-inspection test protects the controller from accidental `smbus` or `gpiod` imports at the pure-core layer.

## Residual risks

1. The full integration suite remains `NEEDS_MANUAL_REVIEW` because the existing Ollama lifecycle interruption/recovery test can exceed the bounded container run and leave a child process alive.
2. M10.4 has no physical effect until M10.5/M10.6 bind it to a single-owner daemon, local protocol, CLI/voice routes and installer/service configuration.
3. Host tests do not prove real SHT31 readings, relay polarity, line ownership, fan power switching, wake phrase behavior or reboot/no-login convergence.

## Readiness verdict

**M10.4 host controller checkpoint: PASS with integration-suite caveat.**  The deterministic controller core is host-verified.  M10.5 is now dependency-ready.  M10.7 physical acceptance remains not-run.
