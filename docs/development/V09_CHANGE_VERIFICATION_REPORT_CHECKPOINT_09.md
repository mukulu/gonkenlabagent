# V09 Checkpoint 09 Change Verification Report

## Scope

Verify the M10.6 environment-daemon activation scaffold added after checkpoint 08. The change connects validated static config, daemon policy storage, production adapter classes and the AF_UNIX server while preserving disabled-by-default installation behavior and `physical_evidence=false`.

## Changed files / risk class

High physical-control relevance, but host-only execution in this checkpoint:

- `src/gonken_agent/environment/daemon.py`
- `src/gonken_agent/environment/service.py`
- `src/gonken_agent/environment/server.py`
- `src/gonken_agent/environment/__init__.py`
- `src/gonken_agent/cli.py`
- `tests/unit/test_v09_environment_daemon_activation.py`
- `tests/unit/test_v09_environment_cli.py`
- development ledgers and checkpoint reports.

## Planned versus executed checks

| Check | Executed | Result |
|---|---:|---|
| Affected daemon/CLI/IPC/adapter tests | Yes | PASS, 34/34 |
| Full host unit suite | Yes | PASS, 311/311 |
| Static gates | Yes | PASS |
| Targeted CLI/text integration subset | Yes | PASS, 14/14 |
| Broad CI | No unchanged repeat | Existing Ollama lifecycle interruption caveat remains open |
| Real Pi HIL | Not available | BLOCKED / NOT_RUN |

## Findings

1. `build_environment_service_core()` refuses disabled profiles, derives static policy bounds, creates a missing daemon policy, refuses corrupt policy without replacement, and wires the real adapter classes into `EnvironmentServiceCore`.
2. Adapter construction remains lazy with respect to physical resources: the SHT31 bus is opened on read and the relay line is requested on actuation, not during ordinary package import or check-mode construction.
3. `env serve --check` returns success for an enabled structurally valid profile without starting a socket loop, toggling hardware, or claiming physical evidence.
4. `EnvironmentUnixServer.server_close()` invokes best-effort safe-off and closes adapters before removing the AF_UNIX socket.
5. The package still defaults to `extensions.environment.enabled=false`, so generic upgrades do not start environment actuation.

## Regression protection

- Existing CLI, IPC and adapter tests were rerun with the new activation tests.
- Full unit discovery passed after the change.
- Static gates passed after the change.
- Targeted CLI/text integration subset passed after the change.

## Residual risk

- No physical Raspberry Pi evidence exists for I2C enablement, SHT31 address, repeated CRC-valid readings, Pi 5 gpiochip mapping, relay polarity, boot safe-off, PENGLIN USB switching, ELUTENG fan cycles, systemd runtime under target permissions or reboot/no-login convergence.
- The daemon still lacks a background polling/control-loop scaffold; automatic control currently advances when sensor reads are invoked by daemon operations.
- Broad CI still has the pre-existing Ollama lifecycle interruption caveat and is not claimed as a fresh PASS.

## Readiness verdict

**Host checkpoint verdict:** PASS for daemon activation scaffold.  
**Physical acceptance verdict:** NOT_RUN / BLOCKED on target hardware.  
**Release verdict:** NOT_READY; M10.6 and M10.7 remain open.
