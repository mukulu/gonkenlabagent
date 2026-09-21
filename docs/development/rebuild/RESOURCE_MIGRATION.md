# Capability-derived resource migration

The actual profile uses wake word, not a required physical PTT button. Historical
PTT decisions remain historical. Dormant PTT17 and recording27 values remain
strictly typed/range-validated but do not reserve hardware. The actual wake
indicator on GPIO22 remains a separate active requirement. It is not silently
removed or replaced by a screen. No physical LED acceptance is inferred.

`gonken_agent.resources` is the pure authority for enabled-capability claims.
Config collision validation, GPIO preflight, target manifest/replay and support
use it or its explicit machine document. Metadata discovery never requests GPIO
lines. Real SHT31 on I2C1 and relay GPIO23 remain owned by the environment daemon;
simulated and disabled backends create no physical acquisition requirement.
Other I2C bus numbers retain explicit bus identity, but this module does not
invent header mappings for non-default buses. Those require target qualification.

The GPIO installer postcondition now checks fresh metadata as the voice service
account and compares the saved record's boot ID, exact claim fingerprint and
resolved metadata with the fresh result. A changed profile, old boot or changed
chip identity invalidates the prior record. Old four-pin artifacts cannot make
this new check green. No service, profile, policy or relay state is changed by
preflight or support collection.

All historical target fixtures now state their own old four-line requirements
explicitly; they do not define today's production requirements. A replay without
explicit requirements fails when GPIO readiness is required. Header topology
remains a resolver aid, not selected-profile policy.

The pure future OSOYOO profile permits touch GPIO17 only when PTT is inactive,
reserves SPI/control lines, preserves I2C1 and GPIO23, and conservatively reserves
uncertain GPIO18 while the board profile is selected. Managed backlight remains
refused without exact-board verification. This is not a driver implementation,
physical display acceptance, or authorization to mount the screen while powered.

## Verification and changed expectations

95 focused tests passed, including positive/negative active/inactive modes,
non-actuating preflight, stale boot/claims/chip rejection, config validation,
GPIO identity aliases and existing target replay. Older tests that treated a
DISABLED relay or dormant PTT fields as active reservations were migrated into
explicit enabled-profile collision tests. This intentional semantic change is
not removal of conflict protection: all selected physical owners still conflict.
