# V09 Checkpoint 10 Change Verification Report

## Scope

Verify the M10.6 daemon polling/control-loop scaffold added after checkpoint 09. The change gives the environment daemon a bounded autonomous polling path while keeping physical hardware acceptance explicitly open.

## Changed files / risk class

High physical-control relevance, but host-only execution in this checkpoint:

- `src/gonken_agent/environment/service.py`
- `src/gonken_agent/environment/daemon.py`
- `src/gonken_agent/environment/__init__.py`
- `src/gonken_agent/cli.py`
- `tests/unit/test_v09_environment_polling_loop.py`
- development ledgers and checkpoint reports.

## Planned versus executed checks

| Check | Executed | Result |
|---|---:|---|
| Affected polling/daemon/IPC/CLI/adapter tests | Yes | PASS, 39/39 |
| Full host unit suite | Yes | PASS, 316/316 |
| Targeted CLI/text integration subset | Yes | PASS, 14/14 |
| Static gates | Yes | PASS |
| Broad CI | Yes, bounded | INTERRUPTED / not PASS; full unit phase passed and deterministic integration began before external timeout/process cleanup |
| Real Pi HIL | Not available | BLOCKED / NOT_RUN |

## Findings

1. `EnvironmentServiceCore.poll_once()` reads through the single daemon-owned sensor boundary, feeds the deterministic controller and reconciles the actuator state.
2. Sensor exceptions are converted into structured failed/unavailable readings; this lets the controller enforce AUTO/SEMI fail-closed behavior instead of crashing the polling thread.
3. Actuator write errors force `ACTUATOR_ERROR_SAFE_OFF`, call best-effort `safe_off`, record poll error metadata and return a degraded poll result.
4. `EnvironmentPollingLoop` is stoppable and bounded by the configured poll interval; it does not busy-loop.
5. `EnvironmentDaemon.from_config()` attaches the polling loop to normal daemon serving, while `env serve --check` still performs construction-only validation without starting the socket loop or polling thread.

## Regression protection

- Existing daemon activation, IPC, CLI and hardware-adapter tests were rerun with the new polling tests.
- Full unit discovery passed after the change.
- Targeted CLI/text integration passed after the change.
- Static gates passed after ledger updates.

## Residual risk

- No physical Raspberry Pi evidence exists for I2C enablement, SHT31 address, repeated CRC-valid readings, Pi 5 gpiochip mapping, relay polarity, boot safe-off, PENGLIN USB switching, ELUTENG fan cycles, target systemd execution or reboot/no-login convergence.
- Broad CI still has the pre-existing Ollama lifecycle interruption caveat and is not claimed as a fresh PASS.
- Background polling is host-verified with fakes; real resource use and timing must be measured on target.

## Readiness verdict

**Host checkpoint verdict:** PASS for daemon polling/control-loop scaffold.  
**Physical acceptance verdict:** NOT_RUN / BLOCKED on target hardware.  
**Release verdict:** NOT_READY; M10.6 target-grounded documentation and M10.7 remain open.
