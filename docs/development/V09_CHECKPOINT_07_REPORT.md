# V09 Checkpoint 07 — Deterministic voice intents and env watch

**Date:** 2026-09-15
**Branch:** `v09-environment-foundation`
**Baseline checkpoint:** V09 Checkpoint 06 at commit `3ad094ac9a04a888ffbf55cdd839f8b115fc4b4b`
**Development version:** `0.2.0.dev0`
**Governing blueprint:** `GONKEN-V09-BP-GOLD-2026-09-15`

## Completed

1. Added `src/gonken_agent/environment/intents.py`, a deterministic allow-listed parser for temperature, humidity, fan status, fan on/off, mode and explicit threshold voice requests.
2. Added `src/gonken_agent/environment/responses.py`, which renders spoken environment answers from daemon results or daemon rejections rather than from model invention.
3. Integrated deterministic environment handling into `ConversationBrain.reply()` before the ordinary local LLM path.
4. Preserved general local LLM conversation for non-environment questions.
5. Ensured ambiguous environment commands such as “set the temperature to 25” ask for clarification and do not call the daemon or LLM.
6. Added `gonken-agent env watch` with human output, JSON output, configurable interval and bounded `--count` for tests/scripts.
7. Updated `docs/OPERATIONS.md` with the V09 environment operator and voice boundary.
8. Added unit tests for parser behavior, result-derived responses, daemon rejection handling, no LLM history for environment actions and watch-mode read-only behavior.
9. Updated M10 ledgers, decisions, evidence ledger and test matrix.

## Host-verified behavior

- Clear voice phrases are translated into typed daemon operations: `sensor.read`, `status.get`, `policy.get`, `fan.set`, `mode.set` and `policy.update`.
- Voice does not expose shell, GPIO, I2C, raw file mutation or model-selected arbitrary tool execution.
- Environment actions do not enter ordinary chat history.
- Daemon/client errors produce spoken failure text without claiming success.
- `env watch` reads through the same `EnvironmentClient` boundary as the CLI and reports `physical_evidence=false`.
- Responses distinguish relay/fan-power state from physical blade motion and software speed control.

## Verified evidence

| Evidence | Result | Boundary |
|---|---:|---|
| `docs/development/evidence/v09/wp_h_voice_watch_affected_tests.log` | PASS, 43/43 | Host-only parser/response/voice/CLI-watch/IPC tests |
| `docs/development/evidence/v09/wp_h_full_unit.log` | PASS, 295/295 | Full host unit suite; no physical Pi evidence |
| `docs/development/evidence/v09/wp_h_integration_subset.log` | PASS, 14/14 | Targeted CLI/text/dashboard integration subset; not broad CI |
| `docs/development/evidence/v09/wp_h_static_gates.log` | PASS | Static repository/package gates; no physical Pi evidence |

## Remaining

- M10.6 production SHT31 sensor adapter remains unimplemented.
- M10.6 production libgpiod relay adapter remains unimplemented.
- The hidden `env serve` entry point still fails closed when the environment profile is enabled because production hardware adapters do not yet exist.
- M10.7 physical HIL remains not run and unavailable in this environment.
- Broad CI remains under the existing Ollama lifecycle interruption timeout caveat from earlier checkpoints.

## Blocked items / risks

- No physical Raspberry Pi evidence exists for I2C enablement, SHT31 CRC reads, libgpiod line ownership, relay polarity, PENGLIN USB switching, ELUTENG fan cycles, fan blade motion, wake phrase, reboot/no-login behavior or update/rollback with environment hardware.
- Voice can now construct typed environment operations, but real spoken control still requires an installed/running environment daemon and physical target acceptance.
- `env watch` is host-verified as a read-only daemon-client loop; it is not a microSD logging feature and it does not prove real sensor values.

## Exact next action

Continue M10.6 with production SHT31 and libgpiod relay adapters behind the existing service boundary, using host tests and fakes first. Preserve `env serve` fail-closed behavior until the adapters are implemented and keep physical acceptance under M10.7.

## Continuation instruction

Continue from this recorded checkpoint and execute the next dependency-ready batch.
