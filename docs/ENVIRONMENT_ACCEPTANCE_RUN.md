# V09 room-environment acceptance evidence run

This runbook collects private evidence for the V09 SHT31/relay/ELUTENG room-fan subsystem on the physical Raspberry Pi. It complements, but does not replace, the main [Raspberry Pi acceptance runbook](RASPBERRY_PI_ACCEPTANCE_RUN.md).

The runner is an evidence collector. It does not decide final acceptance, and every generated manifest records `physical_acceptance_claimed=false`. A human reviewer must still inspect wiring, observe relay/fan behavior, verify reboot/no-login convergence, and confirm wake/voice behavior.

## 1. Preconditions

Before any fan actuation:

1. Power off the Pi and fan supply path.
2. Inspect SHT31 placement: outside the hot Pi case, away from the Active Cooler exhaust and away from direct ELUTENG fan exhaust.
3. Inspect relay input wiring and confirm the configured logical BCM line matches the physical header plan.
4. Inspect PENGLIN USB wiring: only intended USB VBUS is switched through relay COM/NO; no short or back-power path is present.
5. Confirm the ELUTENG physical speed controller is deliberately set by the operator. V09 can switch power only; it cannot select Low/Medium/High in software.
6. Record the Pi model, OS image, kernel, Python version, SHT31 board/address, relay markings, fan model, power supply and date.

Do not run `--allow-actuation` until these checks are complete.

## 2. Non-destructive evidence collection

Run this first. It collects platform identity, service state, daemon status/health, sensor read/probe output and recent journals. It must not toggle the relay.

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/environment_acceptance_runner.py \
  --output-dir /var/lib/gonken-environment/acceptance/$(date -u +%Y%m%dT%H%M%SZ)
```

Expected output shape:

```text
[OK] code=M10_7_EVIDENCE_COLLECTED status=... output=...
[INFO] physical_acceptance_claimed=false
```

Preserve these generated files:

```text
m10_7_evidence_manifest.json
m10_7_private_evidence_ledger.csv
private_evidence/*.json
```

A command-level PASS means only that the command completed and produced bounded output. It does not prove blade rotation, representative temperature placement, relay polarity or reboot safety.

## 3. Supervised fan actuation evidence

After wiring inspection and with a person observing the relay and fan, run:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/environment_acceptance_runner.py \
  --output-dir /var/lib/gonken-environment/acceptance/$(date -u +%Y%m%dT%H%M%SZ)-actuation \
  --allow-actuation
```

This mode issues exactly the environment CLI fan cycle commands through the daemon boundary:

```text
gonken-agent env fan off --json
gonken-agent env fan on --json
gonken-agent env fan off --json
```

The observer must separately record whether the relay/fan actually behaved as expected. JSON output can report the daemon's relay-power command boundary, not independent fan motion.

## 4. Manual target gates still required

The generated private ledger intentionally leaves these gates as `NEEDS_MANUAL_REVIEW` or `BLOCKED` until a human adds target evidence:

- power-off wiring inspection;
- reboot/no-login convergence;
- wake phrase and spoken environment commands;
- relay polarity and boot safe-off behavior;
- PENGLIN USB continuity/polarity;
- SHT31 placement and sanity comparison;
- fan blade motion and repeated power cycles.

These items remain M10.7 physical evidence gates. Do not change the ledger to PASS unless the supporting observation, command output, target identity and date are recorded.

## 5. Review boundary

The private evidence directory may contain local hostnames, device paths and journal excerpts. Treat it like a support bundle. Keep it private unless the project owner decides to share it.

The acceptance decision is valid only for the exact commit, configuration, policy, hardware wiring and target identity recorded in the manifest. A later hardware, config, policy or service change invalidates the affected and transitively dependent evidence.

## 6. Simulation and hybrid-HIL blocking rule

The physical acceptance runner now inspects JSON returned by the daemon-facing
commands. If a command reports any simulated backend, including hybrid modes such
as simulated sensor plus real actuator or real sensor plus simulated actuator,
the step is recorded as:

```text
status=BLOCKED
blocking_code=SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED
physical_evidence_claimed=false
```

The parsed JSON is still retained because hybrid evidence can be useful for
engineering diagnosis. It cannot close the full M10.7 physical gate. A later
review may use it only for the side that was actually physical and must leave the
simulated side open.

This rule applies even when the command returns exit code 0. Exit code 0 means
that the command completed; it does not mean that SHT31 hardware, relay wiring,
PENGLIN continuity, ELUTENG fan motion, wake behavior, or reboot/no-login
operation has been physically accepted.


## 7. Documentation-check command forms

These short forms are used by the repository documentation validator to confirm that the acceptance-runner command line still parses. They are examples only; use the target paths shown above during a real run.

```bash
environment_acceptance_runner.py --output-dir /tmp/gonken-m10-7-evidence --plan-only --json
environment_acceptance_runner.py --output-dir /tmp/gonken-m10-7-evidence --allow-actuation --json
```
