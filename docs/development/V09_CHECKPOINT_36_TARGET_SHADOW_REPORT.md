# V09 Checkpoint 36 Report — Target Manifest And Target-Shadow Replay

## Purpose

Checkpoint 36 advances the reliability-first gate after checkpoint 35. It adds a sanitized non-actuating target manifest tool and permanent target-shadow replay fixtures so real Raspberry Pi topology can become host-verifiable regression evidence before another Pi candidate is produced.

## Implemented

- Added `scripts/target_probe.py`.
- The live probe emits `gonken-target-hardware-manifest-v1` JSON with platform, kernel, OS, Python/libgpiod, gpiochip stat/sysfs/chip/line metadata, I2C device inventory, non-content audio route inventory, Bluetooth inventory, systemd unit state, service identity groups, current release state and explicit privacy flags.
- The live probe does not request GPIO lines, toggle relay/LED/PTT hardware, scan arbitrary I2C addresses, capture audio, include transcripts/prompts/model responses, or claim physical acceptance.
- Added `target_probe.py --replay <manifest>` for target-shadow GPIO identity validation.
- Added a checkpoint-34 duplicate RP1 alias fixture that replays PASS.
- Added a distinct duplicate header-controller fixture that replays FAIL with `GPIO_HEADER_UNRESOLVED`.
- Included `target_probe.py` in immutable release maintenance payloads.

## Verification

| Check | Result | Evidence |
|---|---:|---|
| Target probe unit suite | PASS — 6 tests | `PYTHONPATH=src python3 -m unittest tests.unit.test_v09_target_probe -v` |
| Release maintenance inclusion | PASS — 1 focused test | `PYTHONPATH=src python3 -m unittest tests.unit.test_m3_3_release_manager.IntegrityAndPrivilegeTests.test_speech_and_service_maintenance_inputs_are_release_payload_contract -v` |
| CLI replay good/bad fixtures | PASS | good fixture exits 0; distinct duplicate fixture exits 75 |
| Live host smoke | PASS | `target_probe.py --json` emits valid content-free JSON with `physical_acceptance_claimed=false`; host only, not Pi evidence |
| Static syntax/control sync/T0 | PASS | compile, milestone status, whitespace and T0 checks at checkpoint close |

## Broader Check Boundary

The checkpoint does not rerun the full unit discovery suite because checkpoint 35 already established that this Work runtime blocks AF_UNIX socket creation and therefore several Unix-socket IPC tests error for environmental reasons. This checkpoint reruns only affected and uncertainty-reducing checks.

## Target Boundary

No Raspberry Pi release candidate is produced. No physical acceptance is claimed. A real target must still run `target_probe.py --json --output <private-path>`, the resulting manifest must be reviewed for privacy and committed as a sanitized target-shadow fixture, and replay must pass before any future Pi candidate package.

## Next Action

Continue with the next dependency-ready reliability batch: integrate target-shadow replay into release-readiness/CI gating, then expand target-shadow fixtures for audio fallback, service identity and dirty installer/release states.
