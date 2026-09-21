# B6 - current-state authority and promotion-gate repair

## Reproduction and root cause

On the recovered rebuild, `release_readiness.py` read historical MILESTONES
software labels and reported READY_FOR_TARGET_CAMPAIGN despite the current
Attempt03 registry listing unfinished core slots. The `--allow-dirty` branch
could restore READY without consulting current work. This was a false-green
release predicate, not a physical-target limitation. The prior unit test
incorrectly required that behavior.

The authoritative requirement inventory is now `ATTEMPT03_PLAN.json`, bound to
the supplied Attempt03 prompt identity. `CURRENT_GATES.json` supplies current
dispositions and evidence references. The validator rejects missing/extra/
duplicate slots, scope-title drift, invalid requirement classification, absent
evidence, and unsafe evidence references. Historical MILESTONES remains a
compatibility document checked for consistency, not a release-promotion source.

## Gate semantics

`release_readiness.py --validate` checks current-state/replay/source consistency
for development. Its report can validly say validation PASS and status NOT_READY.
`--check` additionally requires every pre-package core Attempt03 requirement to
be complete with evidence references. `--allow-dirty` only changes the worktree
cleanliness predicate; it cannot suppress unfinished requirements.

T0 uses development validation. The archive qualifier defaults to strict target
candidate purpose; `--purpose development` is a distinct non-promoting mode.
Target qualification requires an expected full commit and T0; skip-T0 is not a
way to manufacture a candidate. Optional display tasks do not become hidden
core requirements. Neither mode grants physical acceptance.

The old simulation/HIL adapter now consumes the current registry. A successful
host simulation while the core program is unfinished is explicitly
DEVELOPMENT_HOST_SIMULATION_VERIFIED, not HIL readiness. Its strict promotion
check remains nonzero. No simulation fallback or physical actuation was added.

## Verification

49 tests PASS across current-state, promotion-negative tests, archive-purpose
checks, readiness report, simulation validation and actual simulation subprocess
integration. See `evidence/continuation/b6-cascade.log`. Negative cases include
old milestone data, missing/removed requirements, completion without evidence,
symlink evidence, disabled requirement flags, bad replay, unfinished clean or
dirty trees, and skipped candidate verification. Synthetic complete-state
fixtures exercise the positive gate without claiming real completion.

The previously failing runbook test was updated to require the actual tar
commands and reject forced reset/ZIP extraction. Current GPIO instructions use
selected configuration, not unconditional PTT GPIO17/GPIO27. GPIO22 remains the
separate wake/privacy indicator. All target and display physical work is open.

## Limits

The registry is an auditable declaration plus evidence references, not an
independent re-execution of every recorded test each time it is read. Candidate
closure still requires fresh full affected tests, exact archive qualification,
manual source/evidence review and, separately, target evidence. This repair does
not certify old PASS records or close unimplemented power/display work.
