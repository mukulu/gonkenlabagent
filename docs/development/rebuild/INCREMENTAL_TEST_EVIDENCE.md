# B8: preserve verification progress during interruption

## Observed failure mode

`bounded_unittest.py` wrote the structured result only after the whole selected
run. During this campaign an outer time budget stopped a grouped integration run
while earlier modules had already passed. Their text logs survived but the
machine-readable result did not. An unfinished run must never inherit a PASS
manifest from a previous invocation or erase completed module results.

## Change

The runner now atomically writes a planned-scope manifest before execution,
before each selected module/case and after each completed result. While any
selected work remains, result is INCOMPLETE, not PASS. It records planned count,
completed results, pending IDs and the active test. A final PASS requires full
selected-scope completion. Duplicate explicit selections and non-finite timeout
budgets are rejected before execution.

SIGTERM/SIGINT terminate and reap the active child and preserve INTERRUPTED state
with prior completed results. An uncatchable SIGKILL/container loss can leave the
last RUNNING/INCOMPLETE record; the next session must inspect the runner/process
and logs, mark that invocation INTERRUPTED, and rerun only uncertain work. It
must not interpret that record as a completed campaign. The files are local
execution evidence, not a guarantee of remote persistence.

## Evidence

Twelve runner tests pass (`b8-runner-tests.log`), including a real subprocess
interruption after one passing case: the prior result survives, one case stays
pending, the manifest is non-green and the child is reaped. Existing positive,
failure, internal timeout, per-case, exclusion and CI phase tests still pass.
The product runtime and hardware paths are unchanged.

## Remaining

Resume-by-manifest selection is a documented procedure, not an automatic skip
feature. Results must be invalidated for affected source/test changes. Target
Pi verification is not represented by these host runner tests. Other currentness,
reachability, authority and mutation-checker work remains separately open.
