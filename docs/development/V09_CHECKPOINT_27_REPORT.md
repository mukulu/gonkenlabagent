# V09 Checkpoint 27 — Installer Convergence and Profile Parity

## Completed

- Added a release-independent target prerequisite preflight before expensive immutable release construction.
- Added private machine-readable prerequisite and identity evidence without opening GPIO/I2C devices.
- Added an installer-owned early-failure ZIP so candidate failures remain diagnosable before activation.
- Added identity revalidation after account convergence, including the invoking operator's `gonken-envctl` authorization.
- Expanded the environment profile manager to all four simulation/hybrid/full-real backend combinations with atomic managed-profile transitions and fail-closed administrator-config protection.
- Preserved generic installation as non-actuating and environment-disabled by default.

## Verification

- Focused M10.18/M10.19 slice: 47/47 PASS.
- Canonical T0: PASS.
- `git diff --check`: PASS before checkpoint commit.

## Evidence boundary

This is host verification. Raspberry Pi package state, `/dev/gpiochip*`, `/dev/i2c-1`, real supplementary-group/session behavior and hardware-service access remain target-run evidence. Profile creation does not imply service start or physical acceptance.

## Exact next action

Implement M10.20 systemd/service-context/audio closure and M10.21 SHT31/I2C transaction/readiness tranche. Do not redo already-proven GPIO23 relay/fan discovery.
