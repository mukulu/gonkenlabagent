# V09 Checkpoint 08 Change Verification Report

## Scope

Verify the M10.6 SHT31/libgpiod adapter foundation added after checkpoint 07. The change is limited to host-verifiable adapter code, service-boundary actuator synchronization, CLI fail-closed wording, tests and documentation ledgers.

## Changed files / risk class

High physical-control relevance, but host-only execution in this checkpoint:

- `src/gonken_agent/environment/sensors/base.py`
- `src/gonken_agent/environment/sensors/sht31.py`
- `src/gonken_agent/environment/sensors/__init__.py`
- `src/gonken_agent/environment/actuators/base.py`
- `src/gonken_agent/environment/actuators/gpiod_relay.py`
- `src/gonken_agent/environment/actuators/__init__.py`
- `src/gonken_agent/environment/service.py`
- `src/gonken_agent/environment/controller.py`
- `src/gonken_agent/environment/__init__.py`
- `src/gonken_agent/cli.py`
- `tests/unit/test_v09_environment_hardware_adapters.py`
- `tests/unit/test_v09_environment_cli.py`
- development ledgers and checkpoint reports.

## Planned versus executed checks

| Check | Executed | Result |
|---|---:|---|
| Affected adapter/controller/IPC/CLI/voice tests | Yes | PASS, 45/45 |
| Full host unit suite | Yes | PASS, 305/305 |
| Static gates | Yes | PASS |
| Broad CI | No unchanged repeat | Existing Ollama lifecycle interruption caveat remains open |
| Real Pi HIL | Not available | BLOCKED / NOT_RUN |

## Findings

1. SHT31 code imports `smbus` lazily and is host-testable through injected fake bus objects.
2. SHT31 tests validate the Sensirion CRC example, valid-frame conversion, bad-CRC rejection, command bytes and unavailable bus behavior.
3. Relay code imports libgpiod lazily and is host-testable through injected fake gpiod objects.
4. Relay tests validate inactive startup request, active-high/active-low configuration, logical ON/OFF writes, safe-off close and failure mapping.
5. Service tests validate that controller state is applied to injected actuators and that actuator write failure forces `ACTUATOR_ERROR_SAFE_OFF` without returning fake success.
6. The CLI `env serve` path still fails closed for enabled profiles because real target daemon activation has not yet been implemented or accepted.

## Regression protection

- Existing controller, IPC, CLI and deterministic voice tests were rerun with the new adapter tests.
- Full unit suite passed after the change.
- Static gates passed after the change.
- No eager import of `smbus` or `gpiod` is required by ordinary package imports.

## Residual risk

- No physical Raspberry Pi evidence exists for I2C enablement, SHT31 address, repeated CRC-valid readings, Pi 5 gpiochip mapping, relay polarity, boot safe-off, PENGLIN USB switching, ELUTENG fan cycles, service runtime under systemd or reboot/no-login convergence.
- `env serve` remains a fail-closed scaffold for enabled profiles until the next M10.6 daemon-activation batch.
- Broad CI still has the pre-existing Ollama lifecycle interruption caveat and is not claimed as a fresh PASS.

## Readiness verdict

**Host checkpoint verdict:** PASS for adapter-code foundation.  
**Physical acceptance verdict:** NOT_RUN / BLOCKED on target hardware.  
**Release verdict:** NOT_READY; M10.6 and M10.7 remain open.
