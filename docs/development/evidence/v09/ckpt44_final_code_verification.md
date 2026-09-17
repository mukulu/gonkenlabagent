# Checkpoint 44 final code-change verification

## Scope and governing instructions

- Governing implementation prompt: `docs/development/V09_CKPT43_TO_FULL_COMPONENT_CONVERGENCE_BLUEPRINT_PROMPT_V4_GOLD.md`, SHA-256 `4e7597baaa8410d988f6f452adb9672969a734ec32f729c788055ce060d19ba8`.
- Baseline: checkpoint 43 commit `14c0438e84e7ba61f57290d3facaa05e8fd91cac`, tag `checkpoint/v09-43-semantic-convergence`.
- Fresh target failure regression source: `gonken-install-failure-20260917T181316Z-605043.zip`, SHA-256 `f38d15318afddc952c5f766efa39eb8af227c7d1fdc937974648881ee6969f51`.
- Repository `AGENTS.md` governs checkpoint controls, host/physical evidence separation, immutable releases, anti-hang execution and archive integrity.

## Risk classification

High-risk target-facing changes: installer dependency graph, environment commissioning/systemd convergence, service-user filesystem permissions, readiness identity, and immutable release payload. Medium-risk changes: target-shadow replay, failure evidence provenance and component status output. Documentation/control changes are low risk but acceptance-critical. No real GPIO/I2C/audio actuation was performed in this host verification.

## Defects converted to regression protection

1. **Checkpoint-43 readiness false red:** immutable service published `development/development`. Runtime release identity now derives from the installed package anchor, not a resolved venv Python symlink.
2. **Environment diagnostic side effect:** `env serve --check` no longer creates missing persistent policy state.
3. **Root-owned policy failure:** known environment state is reconciled only after path/content safety checks; owner/group/mode are now explicit postconditions.
4. **Verification-discovered permission false green:** initial Checkpoint-44 implementation rechecked only modes after repairing ownership. Verification changed the invariant so state/cache/run/policy owner, group and mode must all match, and final modes are applied after ownership changes.
5. **Installed-but-disabled environment:** bootstrap/source-record/install now carry an explicit canonical environment profile; safe non-actuating profiles are enabled, reset from failed state, restarted and then semantically probed.
6. **Temporary target drop-in residue:** only the exact known Checkpoint-43 temporary drop-in is auto-removed; unknown/admin drop-ins fail closed.
7. **Historical error counts poisoning current truth:** component/readiness foundation and level-triggered checks keep current READY separate from bounded historical/recovered error provenance.

## Executed verification

- Identity + voice/appliance focused slice: **36/36 PASS**.
- Environment policy/non-mutation slice: **19/19 PASS**.
- Main affected Checkpoint-44 slices: **114/114 PASS** and **119/119 PASS**.
- Initial broad unit aggregate: **INTERRUPTED** late in `test_support_export` by the bounded execution limit; not reported as PASS.
- Bounded continuation of uncertain suffix: support export **16/16 PASS**; architecture/archive/docs **30/30 PASS**; environment **127/127 PASS**; target/voice/Bluetooth **142/142 PASS**.
- Process regressions: support/bootstrap **10/10 PASS**; install-engine/uninstall **12/12 PASS**. The first process aggregate had one wrong test-module invocation; corrected runs are preserved separately.
- Verification-found permission repair: focused service-manager **9/9 PASS**; affected post-fix cascade **41/41 PASS**.
- Final post-fix focused verification: **14/14 PASS**.
- `python3 -m compileall -q src scripts tests`: PASS.
- shell syntax for bootstrap/install/support launcher paths: PASS.
- `scripts/validate_v09_docs.py --json`: PASS.
- `scripts/milestone_status.py --check`: PASS.
- `git diff --check`: PASS.
- distributed-runbook Bluetooth identity portability scan: PASS.
- `scripts/release_readiness.py --check --allow-dirty`: `READY_FOR_HOST_TARGET_SHADOW_GATE`, host-required **63/63**, target-shadow **24/24**, target gates remaining **26**.
- `./scripts/ci.sh --phase t0`: PASS.

## False-green / non-regression review

- A live systemd unit alone cannot satisfy environment semantic readiness.
- A mode-correct but wrong-owner policy/runtime directory cannot satisfy commissioned status.
- A real-relay profile cannot be automatically started by generic installation; it exits through the supervised commissioning boundary.
- SHT31 success in the next safe profile does not imply room-fan physical acceptance.
- Room-fan commanded power is not fan blade motion/RPM; Raspberry Pi Active Cooler hwmon data remains unrelated.
- Checkpoint 44 deliberately reports the future LLM/environment tool broker as `NOT_COMMISSIONED`; successful Ollama/voice does not imply V04 tool integration.
- Historical wake/audio errors do not override a freshness-bound current readiness record.

## Residual risk / required target evidence

Physical Raspberry Pi execution remains required for real service-account ownership/group behavior, SHT31 through the daemon after reboot/no-login, audio/wake transaction, and later supervised GPIO23 relay/fan actuation. Multi-model provisioning/benchmarking and typed LLM tool integration are V04 work after this foundation checkpoint.

## Source readiness verdict

**PASS for Checkpoint-44 source packaging as a host/target-shadow verified V04 foundation.** This is not M10.24 physical acceptance and not completion of all V04 work. Exact tagged archive qualification and fresh-extraction reruns are delivery-time evidence external to this self-referential source report.
