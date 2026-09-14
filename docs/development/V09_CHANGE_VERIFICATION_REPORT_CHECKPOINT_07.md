# V09 Change Verification Report — Checkpoint 07

## Scope

This report verifies the M10.6 deterministic voice-intent and operator-watch sub-batch. The change adds a local allow-listed voice parser, daemon-result-derived spoken responses, integration into `ConversationBrain.reply()`, and `gonken-agent env watch`. It does not implement production SHT31/libgpiod adapters, physical daemon startup, real Pi HIL, wake-phrase acceptance or software fan-speed control.

## Governing instructions and sources

- `AGENTS.md` requires dependency-ready progress, proportionate checks, updated ledgers, committed resumable checkpoints and explicit separation of host/mock evidence from Raspberry Pi evidence.
- The V09 blueprint requires deterministic environment intents before the LLM, result-derived confirmations, no arbitrary shell/GPIO/I2C/model tool execution, a shared CLI/voice daemon boundary, live watch behavior and truthful fan capability reporting.
- V09 Checkpoint 06 made this tranche dependency-ready by installing the structural environment service boundary while keeping production hardware adapters fail-closed.

## Changed-file and risk classification

| Area | Files | Risk | Verification focus |
|---|---|---|---|
| Deterministic voice parser | `src/gonken_agent/environment/intents.py` | High | allow-listed operations, ambiguity handling, no hardware/shell surface |
| Spoken responses | `src/gonken_agent/environment/responses.py` | High | daemon-result-derived claims, error handling, no fan-motion/speed fiction |
| Voice runtime integration | `src/gonken_agent/voice_runtime.py` | High | environment action before LLM, no chat-history pollution, normal LLM fallback |
| Operator watch | `src/gonken_agent/cli.py` | Medium | repeated IPC read, JSON/human output, bounded test mode, no direct sensor access |
| Exports | `src/gonken_agent/environment/__init__.py` | Low | stable module access for tests and later adapters |
| Tests | `tests/unit/test_v09_environment_voice_intents.py`, `tests/unit/test_v09_environment_cli.py` | Medium | parser/response/voice/watch regression protection |
| Documentation and ledgers | `docs/OPERATIONS.md`, `docs/development/*` | Medium | evidence state, remaining work and false-green prevention |

## Checks executed

| Check | Result | Evidence |
|---|---:|---|
| M10.6 voice/watch affected suite | PASS, 43/43 | `docs/development/evidence/v09/wp_h_voice_watch_affected_tests.log` |
| Full host unit suite | PASS, 295/295 | `docs/development/evidence/v09/wp_h_full_unit.log` |
| Targeted CLI/text integration subset | PASS, 14/14 | `docs/development/evidence/v09/wp_h_integration_subset.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_h_static_gates.log` |

## Regression protection added

- Parser tests cover temperature, humidity, fan status, policy query, fan on/off, mode set, combined automatic threshold update and ambiguous temperature clarification.
- Source-boundary tests verify the parser has no `subprocess`, `smbus`, `gpiod`, raw `set_gpio` or shell surface.
- Voice tests verify environment actions use the daemon client before the LLM, do not alter LLM chat history, pass typed policy parameters only, and speak daemon rejection without fake success.
- Response tests verify fan answers report relay/fan-power state and explicitly avoid physical blade-motion/software-speed claims.
- CLI tests verify `env watch` repeatedly uses `read_sensor`, supports JSON output and preserves `physical_evidence=false`.

## Residual risks

1. Broad CI remains under the known Ollama lifecycle interruption caveat from earlier checkpoints and was not re-run unchanged for this tranche.
2. Voice environment commands are host-tested with fake clients; real spoken action requires a running target daemon and physical acceptance.
3. `env serve` remains intentionally fail-closed for enabled profiles until production SHT31/libgpiod adapters are implemented.
4. `env watch` is a transient read loop, not a persistent data logger; long-running behavior on a real Pi remains a target observation.
5. All SHT31, relay, PENGLIN, ELUTENG, wake and reboot/update/rollback acceptance gates remain M10.7 target work.

## Readiness verdict

**M10.6 deterministic voice/watch sub-batch: PASS with scope limitation.** Clear environment voice commands and operator watch are host-verified through the daemon-client boundary. M10.6 remains partial because production hardware adapters are still absent, and M10.7 physical acceptance remains not-run.
