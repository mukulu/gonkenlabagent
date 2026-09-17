# V09 Checkpoint 42 — Single-ZIP Target Evidence and Failure-Bundle Completeness

## Scope

Checkpoint 42 changes the reliability workflow from "host waits for live target access" to "target produces one complete evidence ZIP." The host development platform cannot directly run the Raspberry Pi hardware environment, so the package must make the real device export enough structured evidence for the next repair cycle.

## Implemented

- Expanded normal support export with:
  - `target_manifest.json` from non-actuating `target_probe.py` when available;
  - `platform_inventory.json` for resource, command, release, memory and disk context;
  - `evidence_index.json` describing bundle purpose, members, privacy exclusions and interpretation.
- Expanded installer-failure bundles with:
  - sanitized target manifest capture when `target_probe.py` is available;
  - platform/resource inventory;
  - bounded service journal code counts;
  - richer allow-listed bootstrap source facts;
  - evidence index metadata.
- Updated `collect-support.sh` to auto-run `target_probe.py --json --output ...` from the installed maintenance payload.
- Updated the Raspberry Pi runbook and operations guide so the first requested artifact is the single generated ZIP.

## Governing Principle

The absence of direct live hardware access in the host workspace should not block stable package construction. It should instead raise the evidence standard for target-generated ZIPs. Those ZIPs must carry hardware, runtime, installer, service and bounded log-code facts in a privacy-preserving form.

## Evidence Boundary

The expanded ZIP can support host-side diagnosis and next-package construction. It does not by itself prove physical fan blade motion, relay polarity, SHT31 placement, acoustic quality or wake recognition. Those remain target-collected observations, but they should be attached as concise notes rather than as a second machine-diagnostic package.

## Verification

- `PYTHONPATH=src:. python3 -m unittest tests.unit.test_support_export tests.unit.test_v09_installer_failure_bundle -v`
- `PYTHONPATH=src:. python3 -m unittest tests.integration.test_support_collection_process -v`

## Next Target Use

On the Raspberry Pi, run:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

If installation fails before the installed release is usable, upload the installer-owned failure ZIP printed by the installer instead. In either case, the single ZIP is the primary diagnostic artifact for the next build cycle.
