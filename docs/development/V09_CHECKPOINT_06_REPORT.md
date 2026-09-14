# V09 Checkpoint 06 — Environment service installer/systemd wiring

**Date:** 2026-09-15
**Branch:** `v09-environment-foundation`
**Baseline checkpoint:** V09 Checkpoint 05 at commit `0dddb5d86996fe995a1de384a9a0fb482df3127c`
**Development version:** `0.2.0.dev0`
**Governing blueprint:** `GONKEN-V09-BP-GOLD-2026-09-15`

## Completed

1. Added `packaging/systemd/gonken-environment.service` as the structural unit for the separate room-environment controller.
2. Added `packaging/tmpfiles/gonken-environment.conf` for `/var/lib/gonken-environment`, `/var/cache/gonken-environment` and `/run/gonken-environment`.
3. Added `scripts/environment_service_manager.py` for exact install/status/remove validation of the environment unit and tmpfiles contract.
4. Updated `packaging/systemd/gonken-agent.service` and `scripts/service_manager.py` so the voice service has a soft `Wants`/`After` dependency on `gonken-environment.service`, never `Requires`.
5. Updated `scripts/install.sh` to install target I2C/GPIO OS dependencies, provision `gonken-env`, provision `gonken-envctl`, add `gonken-agent` to the control-socket client group, and install the environment service structurally without enabling or starting it.
6. Updated `scripts/release_manager.py` so immutable releases carry the environment service manager, unit and tmpfiles templates.
7. Updated `scripts/uninstall.sh` and `scripts/uninstall_manager.py` so managed environment service files are removed, environment state/cache are retained by default, and environment data is purged only under explicit purge confirmation.
8. Added hidden `gonken-agent env serve` behavior: disabled profiles exit safely with `ENVIRONMENT_DISABLED`; enabled profiles fail closed with `ENV_HARDWARE_BACKEND_NOT_IMPLEMENTED` until production hardware adapters exist.
9. Added and updated tests for environment service manager, CLI fail-closed behavior, release payload inclusion, service soft dependency and uninstall lifecycle.
10. Updated M10 ledgers, decisions, test matrix, evidence ledger and implementation status.

## Installer/systemd semantics now host-verified

- `gonken-environment.service` is a separate `Type=exec` service for `gonken-env`.
- The unit is local-only with `RestrictAddressFamilies=AF_UNIX`; it does not grant sudo, polkit, power, network or extra Linux capabilities.
- Generic installation writes structural service files and tmpfiles but does not enable or start the service.
- The voice service has a soft relationship with the environment service and can remain usable when environment control is disabled or degraded.
- `gonken-envctl` is the client-access group; `gonken-agent` receives client access rather than raw environment hardware privileges.
- Uninstall retains environment state/cache by default and removes them only under explicit purge confirmation.

## Verified evidence

| Evidence | Result | Boundary |
|---|---:|---|
| `docs/development/evidence/v09/wp_g_installer_systemd_affected_tests.log` | PASS, 41/41 | Host-only installer/systemd/release/uninstall/serve tests |
| `docs/development/evidence/v09/wp_g_full_unit.log` | PASS, 285/285 | Full host unit suite; no physical Pi evidence |
| `docs/development/evidence/v09/wp_g_static_gates.log` | PASS | Bash syntax, compileall, TOML/JSON parse, milestone check and diff-check gates |
| `docs/development/evidence/v09/wp_g_release_e2e_isolated.log` | PASS, 1/1 | Isolated release lifecycle integration; not a broad CI PASS |
| `docs/development/evidence/v09/wp_g_integration_subset.log` | INTERRUPTED | Targeted install/release subset reached the release E2E default-boundary test; isolated rerun passed |
| `docs/development/evidence/v09/wp_g_uninstall_integration.log` | PASS, 2/2 | Host fake-root uninstall lifecycle integration |
| `docs/development/evidence/v09/wp_g_broad_ci_attempt.log` | INTERRUPTED | Broad CI completed the unit phase and entered deterministic integration before interruption; not a PASS and not attributed to this tranche |

## Remaining

- M10.6 deterministic voice environment intents and result-derived spoken responses remain unimplemented.
- M10.6 watch-mode/operator documentation remains open.
- Production SHT31 and libgpiod relay adapters remain unimplemented.
- Real Raspberry Pi systemd convergence, I2C/GPIO permissions, relay safety and fan behavior remain untested.
- M10.7 real Raspberry Pi HIL/release acceptance remains not run and unavailable in this environment.
- Broad integration/CI remains under the existing Ollama lifecycle interruption timeout caveat; Checkpoint 06 broad CI was interrupted during deterministic integration and preserved as `wp_g_broad_ci_attempt.log`.

## Blocked items / risks

- No physical Raspberry Pi evidence exists for I2C enablement, SHT31 CRC reads, libgpiod line ownership, relay polarity, PENGLIN USB switching, ELUTENG fan behavior, wake phrase, reboot/no-login behavior or update/rollback with environment hardware.
- The environment service unit is structurally installed only; no target `systemctl enable/start/status` evidence exists.
- `env serve` deliberately fails closed for enabled profiles until production hardware adapters are implemented.
- Target dependency installation now includes `i2c-tools`, `python3-smbus` and `python3-libgpiod`, but package availability and group/device ownership still require target verification.

## Exact next action

Continue M10.6 with deterministic voice environment intents and result-derived spoken responses, or implement production SHT31/libgpiod adapters behind the existing service boundary.  Preserve the rule that voice and CLI are clients of the daemon and that no response claims physical actuation until the daemon and target evidence support it.

## Continuation instruction

Continue from this recorded checkpoint and execute the next dependency-ready batch.
