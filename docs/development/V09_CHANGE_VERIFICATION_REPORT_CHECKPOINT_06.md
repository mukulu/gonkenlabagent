# V09 Change Verification Report — Checkpoint 06

## Scope

This report verifies the M10.6 installer/systemd sub-batch: structural provisioning for the separate `gonken-environment.service`, target account/group scaffolding, release payload inclusion, uninstall behavior and fail-closed daemon entry behavior.  The change does not implement deterministic voice environment intents, watch documentation, production SHT31/libgpiod adapters, real systemd target execution or physical Raspberry Pi acceptance.

## Governing instructions and sources

- `AGENTS.md` requires dependency-ready progress, proportionate checks, updated ledgers, committed resumable checkpoints and explicit separation of host/mock evidence from Raspberry Pi evidence.
- The V09 blueprint requires a separate `gonken-environment.service`, a dedicated non-login hardware owner, AF_UNIX client access, soft voice dependency, disabled-by-default generic upgrades and no false hardware acceptance.
- V09 Checkpoint 05 made this tranche dependency-ready by exposing CLI, IPC and observability surfaces that can refer to a structural environment service without direct GPIO/I2C access.

## Changed-file and risk classification

| Area | Files | Risk | Verification focus |
|---|---|---|---|
| Environment service unit/tmpfiles | `packaging/systemd/gonken-environment.service`, `packaging/tmpfiles/gonken-environment.conf` | Medium | local-only process boundary, state/cache/runtime ownership, no network/power/privilege grants |
| Environment service manager | `scripts/environment_service_manager.py` | Medium | exact file validation, conflict refusal, no enable/start by default, reversible removal |
| Installer/release payload | `scripts/install.sh`, `scripts/release_manager.py` | High | target dependencies, `gonken-env`, `gonken-envctl`, release maintenance inclusion, disabled-by-default generic upgrade behavior |
| Voice service dependency | `packaging/systemd/gonken-agent.service`, `scripts/service_manager.py` | Medium | soft `Wants`/`After`, no `Requires` coupling |
| Uninstall lifecycle | `scripts/uninstall.sh`, `scripts/uninstall_manager.py` | Medium | managed service-file removal, data retention by default, purge only with confirmation |
| CLI daemon entry | `src/gonken_agent/cli.py` | Medium | disabled profile harmless exit; enabled profile fails closed until production hardware adapters exist |
| Tests | `tests/unit/*`, `tests/integration/test_uninstall_lifecycle_process.py` | Medium | regression and false-green prevention |
| Evidence and ledgers | `docs/development/*`, `docs/development/evidence/v09/*` | Medium | M10.6 partial status, evidence, residual risk and next action |

## Checks executed

| Check | Result | Evidence |
|---|---:|---|
| M10.6 installer/systemd affected suite | PASS, 41/41 | `docs/development/evidence/v09/wp_g_installer_systemd_affected_tests.log` |
| Full host unit suite | PASS, 285/285 | `docs/development/evidence/v09/wp_g_full_unit.log` |
| Static gates | PASS | `docs/development/evidence/v09/wp_g_static_gates.log` |
| Isolated release lifecycle E2E | PASS, 1/1 | `docs/development/evidence/v09/wp_g_release_e2e_isolated.log` |
| Targeted install/release integration subset | INTERRUPTED | `docs/development/evidence/v09/wp_g_integration_subset.log` |
| Uninstall lifecycle integration | PASS, 2/2 | `docs/development/evidence/v09/wp_g_uninstall_integration.log` |
| Bounded broad CI attempt | INTERRUPTED | `docs/development/evidence/v09/wp_g_broad_ci_attempt.log` |

## Regression protection added

- Environment service manager tests verify required hardening lines, forbidden privilege/network/power strings, exact tmpfiles contract, conflict refusal, no enable/start on install and reversible removal.
- Service manager tests verify the voice service soft-depends on the environment service and rejects `Requires=gonken-environment.service`.
- Release-manager tests verify the immutable release maintenance payload includes the environment manager, service unit and tmpfiles template.
- Uninstall tests verify managed environment service files are removed, default uninstall retains environment state/cache and purge removes them only with explicit confirmation.
- CLI tests verify `env serve` does not run fake hardware when disabled and fails closed when enabled before production adapters exist.

## Residual risks

1. The broad CI attempt remains `INTERRUPTED`, not PASS. It completed the unit phase and entered deterministic integration before the watchdog/container interruption. The isolated release E2E and uninstall integration checks passed separately.
2. The new service and tmpfiles files are structurally host-tested, but there is no target `systemctl` evidence yet.
3. `gonken-env`/`gonken-envctl` provisioning is tested through script contracts, not through real Raspberry Pi users, groups or device ACLs.
4. `env serve` intentionally fails closed for enabled profiles until SHT31/libgpiod adapters are implemented; this is correct for this checkpoint but means the environment service is not production-operational yet.
5. Physical I2C, SHT31, relay, PENGLIN, ELUTENG, wake and reboot/update/rollback gates remain M10.7 target work.

## Readiness verdict

**M10.6 installer/systemd sub-batch: PASS with scope limitation.**  Structural environment service provisioning, release inclusion, uninstall behavior and fail-closed daemon entry behavior are host-verified.  M10.6 remains partial, and M10.7 physical acceptance remains not-run.
