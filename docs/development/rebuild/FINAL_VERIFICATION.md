# Attempt03 CP46R-B9: application continuation and verification checkpoint

## Verdict

**Development checkpoint; current host regression corpus passed. Not a final
Raspberry Pi release, not all Attempt03 features implemented, no physical
acceptance claimed. Main/dev-stable were not advanced.**

This is actual application source continued from the saved B3 reconstruction,
not the earlier report-only delivery and not the standalone RG1 recovery toolkit.

## Source and lineage

The delivered predecessor's index said `application_present=false`. Listing the
private Library recovery directory instead of relying on semantic text search
found `Application_Rebuild/B3-62eafcff0365.tar.bz2`. That archive was retrieved and
cold-restored at commit `62eafcff036592bebcc10da20d20bce21c1fc52a` with tree
`9cd3235db5426f7245b177b0aa1c2eb612b4cc4a`. Its SHA-256 is
`8b76bf75ff43038a24aaa9ca351a7d98f5cf86455f75520e84103150e0be87e6`.

The recovered branch is `dev-unstable/attempt03-rebuild`. Corrected authorship
and prior history were preserved. The missing original CP46.7R1/R11A objects
were not recreated or claimed recovered. Source truth is the saved reconstruction
plus the commits below, not a previous response's description of unavailable code.

## Completed changes

| Checkpoint | Implemented scope | Commit |
|---|---|---|
| Audit | Verify B3, record provenance and baseline | `ac6f95b` |
| B4 | Canonical boot/process/release/profile-bound runtime readiness; component, doctor, model-switch and support consumers; model digest/qualification coupling | `d3b3ef0df74c` |
| B5 | Shared bounded verified `.tar.bz2` support/failure engine, destination/ownership policy, thin support wrapper and current commands | `dcf4a1818465` |
| B6 | Full 179-slot Attempt03 registry coverage, current gate authority, separate development validation versus strict candidate promotion | `9a6119d2d114` |
| B6R1 | Replace doctor test's empty READY fixture with valid producer identity and a negative empty-record test | `62414832b3b3` |
| B7 | Fresh final installer summary and selected-component gate; prevent INSTALLATION_COMPLETE after degradation; shared late failure collection | `f1b8b9460f6d` |
| B7R1 | Verify Bluetooth retry schedule without real unit-test sleeps; unchanged product retry behavior | `0f0057cd3975` |
| B8 | Incremental atomic CI manifests, partial-result retention, explicit interrupted state and child termination; reject duplicate selections/non-finite budgets | `0355d2388a49` |

B9 records verification and the resumable handoff. It does not add or claim a
power-action implementation, presentation broker, console or LCD driver.

## Verified evidence

**763 unit tests across all 68 discovered unit modules passed; zero skipped.**
The entire unit suite was rerun at frozen source commit
`0355d2388a49bb676072c15e100fcd27df30f7ec` in 12 bounded shards. Each module has a
log, duration and completion result. The summed module time was 131.278 seconds;
this is not the total session duration.

**75 integration tests across all 12 integration modules passed; zero skipped.**
Coverage includes bootstrap and launcher, CLI, install-engine interruption,
local model lifecycle, speech lifecycle, immutable release build/activation,
same-commit reruns, rollback, uninstall, offline text runtime, canonical support,
environment voice transactions and host simulation. The 12 release, 12 speech
and five model lifecycle cases were individually accounted for. Their application
source is identical between B7 and B8; B8 changes the runner and its tests, not the
application runtime/installer implementations consumed by those cases.

Total selected current-corpus coverage is **838 tests**, not a sum of repeated
narrow runs. All complete unit/integration results are indexed in
`verification/VERIFICATION.json`. Its `code_sha256` map binds non-documentation
tracked source and tests. Recompute that map before reusing the results after
future changes. Logs are repository-relative and included in this checkpoint.

T0, dependency rendering (five existing profiles), generated current-state,
repository contract, compilation/syntax and diff-whitespace checks passed.
Exact final archive checks and extracted smoke results are in the separate
package qualification receipt delivered beside the archive; no pre-build archive
success is asserted inside this commit.

## Failure and interruption accounting

Earlier failing tests exposed and protected actual stale-readiness/final-success
faults. Historical doctor, transport and static installer expectations were
migrated to the current contracts; acceptance requirements were not weakened.
New negative fixture field names were corrected to the actual readiness schema.

A Bluetooth module exceeded a short test budget because two mocked-device cases
slept 20 x 0.5 seconds each. Production sleeps remain unchanged; the tests now
assert that full schedule without sleeping. A grouped simulation run and grouped
model lifecycle run exceeded their outer/module budgets; their completed results
were preserved and only uncertain work was isolated. The final selected
simulation result and every model lifecycle case pass. Two tool envelopes
reported timeout after complete child results were already written; the files
were inspected and the completed results preserved. No unexplained active run
remains at handoff. These observations do not identify the cause of older lost
sessions.

B8 prevents missing manifests for ordinary interruptions. SIGTERM/SIGINT record
INTERRUPTED and terminate the active test. SIGKILL or container loss cannot run
cleanup; a remaining RUNNING/INCOMPLETE record must be reconciled by the next
session, never interpreted as PASS.

## Mandatory review passes

- Completeness: every current Attempt03 slot has a disposition; unimplemented
  work is still explicit. Passing the existing corpus does not complete missing
  features or later acceptance campaigns.
- Consistency: current gate registry controls promotion; old milestones remain
  compatibility history. Semantic current-doc/legacy cleanup is still open.
- Non-regression: the complete current unit/integration corpus passed, with
  special checks for standalone maintenance dependencies and final shell flow.
- False-green: stale producer identity, wrong model/digest, incomplete model
  qualification, inactive/real-vs-simulated capability confusion, missing current
  gate rows, dirty override bypass, archive corruption and interrupted test runs
  are challenged by negative tests.
- Executability: canonical CLI flags, shell syntax, maintenance copying and
  private fresh-checkout command paths were tested. No target services started.
- Evidence: host processes/fakes/simulation are not Pi/HIL evidence. Exact archive
  identity and roundtrip checks remain external immutable receipts.
- Continuation: source, full Git history, current registry, code/test fingerprints,
  focused defect records and relative test logs travel together.

## Remaining scope and known risks

Current source is not ready for stable promotion. Major remaining families are:
repository/Git authority hardening; full Ollama failure causal qualification;
late candidate activation and semantic rollback; remaining audio/service-user
observability; legacy reachability/removal and PRD cleanup; full-real fan
commissioning; governed power actions; additional quality validators; final core
convergence and the display/live-console work. The 179-slot registry is the
specific inventory, not this summary.

The B4/B7 freshness contract binds boot, live PID/start ticks, release/profile and
model. It does not yet bind an effective-configuration generation or provide a
continuous semantic heartbeat. A static READY remains startup evidence, not a
continuous guarantee of healthy audio or inference. Physical privacy-indicator
policy and exact Pi behavior still require evidence.

Live upstream reconciliation remains unverified after a bounded DNS failure.
All Pi voice/audio/model, SHT31, GPIO23 room-fan, reboot/no-login, power, LCD/touch,
HDMI coexistence and physical soak gates remain open. No physical speed-control
or fan-motion claim is introduced. Neither core nor display stable acceptance is
inferred from host tests, source presence or archive qualification.

## Recovery and exact next action

Use the full-Git B9 development archive and its external qualification receipt.
Extract into a new directory as the normal user; do not overwrite another checkout,
run `git reset --hard`, or switch to remote main to conceal source divergence.
Read `AGENTS.md`, `docs/CURRENT_STATE.md`, this report and the governing Attempt03
prompt. Check HEAD/tag/tree against the receipt and keep the development branch.
Recovery archives are also provided for intermediate commits; their creation and
local cold-restore verification are not evidence of indefinite remote storage.
The B9 delivery has not been uploaded to Library by this session's tools.

**Next:** CP46.5.1 candidate/precondition state model, followed by the unfinished
activation-ordering portion of CP46.5.2. Preserve B7's final semantic success
gates. Complete one dependency-ready implementation slice, run its invalid/failure
and affected regression checks, commit (WIP is allowed when accurately labelled),
export and cold-verify its actual source before broader work. Do not resume an
unavailable R11A branch or an allegedly already implemented power subsystem.

> Continue from the B9 development source and recorded checkpoint. Execute the
> next dependency-ready batch, preserve verified behavior and corrected authorship,
> and promote only when current evidence satisfies the corresponding requirements.
