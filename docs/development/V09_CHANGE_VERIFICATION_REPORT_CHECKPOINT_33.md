# V09 Checkpoint 33 Change Verification Report

## Scope and risk

Verify correction of the checkpoint-32 same-current-release rerun dead-end, optional Bluetooth fallback, managed service-template upgrade compatibility, and Pi5 GPIO duplicate-name handling. Risk is high for release integrity and installer idempotence, medium-high for audio routing/service upgrades, and medium for GPIO identity resolution. No target actuation is performed by host verification.

## Changed implementation surfaces

- `scripts/release_manager.py` — narrow Python-cache transient classification/repair for an active same-commit release; authoritative tamper remains fatal.
- `scripts/install.sh` and systemd units — bytecode/no-user-site guards after release seal.
- `scripts/bluetooth_manager.py` — deterministic direct duplex fallback and optional preferred Bluetooth semantics.
- `scripts/service_manager.py`, `scripts/environment_service_manager.py` — known checkpoint-32 managed-unit predecessor hashes.
- `src/gonken_agent/interaction/gpiod_ptt.py` and relay adapter — Pi5 RP1 controller disambiguation without numeric chip assumption.
- tests/control documents — regressions, evidence and checkpoint accounting.

## Original defects reproduced from evidence

The target first activated checkpoint 32 and reached Bluetooth pairing. The requested address then failed connection. Subsequent same-commit local and curl invocations failed at `immutable_release` with `RELEASE_ACTIVE_INVALID`. Support evidence showed direct USB input/output and repeated wake LED GPIO ambiguity. Source analysis identified privileged post-seal Python cache creation as the benign payload drift that made same-commit rerun fail.

## Verification evidence

- Unit: **46 modules / 476 tests PASS**.
- Integration: **12 modules / 67 tests PASS**.
- Release lifecycle: **11/11 PASS**.
- Ollama lifecycle: **5/5 PASS**.
- Speech lifecycle: **12/12 PASS**.
- Static checks/document/readiness/T0 are required again after control-plane synchronization and before commit/package.

## False-green / non-regression checks

- Only recognized Python runtime-cache differences can be automatically purged; authoritative executable/source/config/manifest drift still fails.
- A Bluetooth failure cannot be hidden unless one deterministic input and output fallback are actually proven for the service user.
- HDMI-only playback is not accepted as the direct audio fallback.
- Ambiguous USB/direct devices fail closed.
- Pi5 GPIO disambiguation requires exactly one `pinctrl-rp1` match; it never selects `gpiochip0` by number.
- Existing administrator-modified systemd units are not overwritten; only exact known managed predecessor hashes upgrade.
- Environment hardware stays non-actuating during generic install.
- Previous releases are not normal runtime prerequisites; explicit rollback remains separately governed.

## Readiness verdict

**HOST IMPLEMENTATION VERIFIED; FINAL CONTROL/ARCHIVE GATES REQUIRED BEFORE DELIVERY.** Physical M10.24 remains open until the exact delivered checkpoint reaches `INSTALLATION_COMPLETE` and the target acceptance campaign is observed.
