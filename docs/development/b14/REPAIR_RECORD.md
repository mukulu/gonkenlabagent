# B14 installer convergence repair

## Scope

This repair is intentionally limited to the Raspberry Pi installation failure
observed on B13 at `voice_power_configuration`.

## Target evidence

B13 reached the following downstream gates successfully before failing:

- responsive configuration applied;
- GPIO identity;
- current real-environment reconciliation;
- canonical model roster (`qwen3:0.6b` admitted as the active default; alternate
  tool incompatibilities degraded rather than fatal);
- speech prerequisites;
- candidate activation;
- real environment commissioning/readiness; and
- automatic environment policy.

The next step failed with `INSTALL_PROBE` before its action. The combined
failure evidence recorded `voice_power.enabled=false`, `rule_matches=false`,
`busctl_present=true`, and `confirmation_required=true`.

## Root cause

`python -m gonken_agent.power_install --check` classified two ordinary
not-yet-configured postconditions (`POWER_RULE_MISSING` and
`PRESET_NOT_APPLIED`) as fatal exit 65. The install engine therefore aborted
instead of running the registered voice-power configuration action.

## Repair

For `--check` only, those two safe pending states return 1 (postcondition
unsatisfied/action required). All unsafe/conflicting paths, dependency
failures, malformed configuration, permissions failures, and other exceptions
continue to return 65. Normal action execution still installs only the fixed
PolicyKit rule and enables the typed voice-power configuration; it never
executes reboot or poweroff.

## Regression protection

Tests cover:

- missing managed rule -> 1;
- managed rule present but preset disabled -> 1;
- action then check -> 0;
- missing `busctl` -> 65;
- administrator rule conflict -> 65; and
- target installer order retains environment policy -> voice power ->
  application service.

The standard no-argument target `bootstrap.sh` and curl launcher behavior from
B13 is intentionally unchanged: curl delegates to bootstrap and both use the
same target defaults.
