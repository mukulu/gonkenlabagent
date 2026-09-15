# V09 Checkpoint 26 — Target Python Dependency Boundary Redesign

## Completed

- Replaced checkpoint-24 target `system_site_packages` exposure with an isolated immutable venv.
- Added an allow-listed distro-binding bridge that copies only import payloads owned by `python3-libgpiod` and `python3-smbus`; distro metadata and unrelated site packages are excluded.
- Added `hardware-bindings.json` provenance with package versions and per-file hashes.
- Release validation requires broad system-site visibility to remain OFF, validates the bridge manifest/hash surface, and probes the exact gpiod/smbus APIs through the immutable interpreter/service identity.
- Support evidence reports the bridge separately from the venv policy.
- Converted the real checkpoint-24 `types-*` contamination failure into regression protection.

## Verification

- TargetRuntimeBindingTests: 10/10 PASS.
- Release-manager + support affected slice: 35/35 PASS before the additional dirty-host case; all later focused cases PASS.
- `./scripts/ci.sh --phase t0`: PASS.
- Release-lifecycle aggregate: INTERRUPTED/TIMEOUT after three activation cases PASS; active long case not claimed.

## Evidence boundary

This is host evidence. Actual Debian package discovery/copy and immutable-interpreter imports on Raspberry Pi remain target-run evidence.

## Exact next action

Implement M10.18 installer convergence/preflight/failure-evidence hardening, then M10.19 identities/config profiles.
