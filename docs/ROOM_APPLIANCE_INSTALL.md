# Wired room-appliance installation (B10)

This is an explicit deployment path for the user's already-wired Raspberry Pi 5,
SHT31 on I2C1 at 0x44, and active-high GPIO23 relay switching ELUTENG USB fan power.
It does not depend on uploading a prior physical acceptance report. Actual device
results are evaluated when the candidate is run. Host tests do not prove fan motion.

From a clean extraction of this full-Git package, as the normal administrator:

```bash
./install-room-appliance.sh
```

The wrapper installs **this checkout's commit**, not remote `main`. It delegates
to `bootstrap.sh --local-checkpoint --environment-profile full-real
--environment-mode automatic`. SHT31 and libgpiod are real; runtime simulation
control is disabled. Explicit simulation profiles remain available only for
separate tests/development through the generic bootstrap.

The known managed `real-sensor-simulated-actuator` site configuration is migrated
atomically. Unrelated or conflicting administrator configuration is not destroyed.
The environment daemon is enabled and restarted if its release or static config
fingerprint is stale. Only that daemon opens SHT31/GPIO23; no installer probe
switches GPIO directly. Changing the mode uses its local IPC with a policy
version precondition. Existing valid start/stop temperatures and dwell times are
preserved. Invalid safety policy is not silently replaced or bypassed.

**Running the command authorizes real room-fan power control.** First startup is
safe-OFF. Automatic operation requires valid sensor samples and obeys minimum
ON/OFF dwell. Factory policy is ON at/above 28 C, OFF at/below 26.5 C, with 60-second
minimum ON and OFF dwell; the controller filters readings using its existing
median logic. An existing different valid policy remains authoritative. Therefore
an OFF fan below the start threshold or during dwell is expected, not simulation.
Sensor failure forces safe-OFF independently of normal dwell.

Do not connect/reseat the relay, sensor or GPIO HAT while the Pi is powered.
The external room fan is not the Pi Active Cooler. The ELUTENG's physical speed
switch stays manual; software controls power only, not RPM/speed.

After installation:

```bash
gonken-agent env health --json
gonken-agent env policy show
gonken-agent env watch --health
```

Expected provenance: `sensor_backend=sht31`, `actuator_backend=libgpiod`, both
simulation flags false; policy mode `automatic`. `physical_evidence=false` is
intentional evidence labeling, NOT simulation and NOT a runtime fan lock.

Manual `gonken-agent env fan on/off` commands intentionally switch an automatic
controller to manual mode. Restore temperature control with:

```bash
gonken-agent env mode automatic
```

The first installer run grants the administrator the existing `gonken-envctl`
group. Reconnect SSH if that group is not yet in the current login session. Do
not work around socket permissions by giving the operator raw GPIO privileges.

`--environment-mode preserve` retains the current mode on an intentional rerun;
`--environment-mode manual` is available when unattended automatic control is not
wanted. The plain room-appliance command explicitly reselects automatic mode.

A failing voice/model dependency must produce a failure, not a fabricated
`INSTALLATION_COMPLETE`. Model/speech prerequisites are prepared from the exact candidate before the
current-release switch. The independently supervised environment daemon may
already be operating correctly even if later voice-service readiness fails. Upload the
single `.tar.bz2` evidence bundle printed by the installer. Do not assume a failed
voice install means the thermostat is disabled; inspect the environment service.

No new display driver, touch action, or voice reboot/shutdown feature is claimed
by this room-appliance repair. Those Attempt03 feature families remain separately
tracked rather than being relabeled as implemented.
