# B5 - canonical support and installer-failure evidence transport

## Scope and root-cause correction

The restored application still produced ZIP evidence even though Attempt03 requires
`.tar.bz2`. The shell wrapper independently chose destinations/ownership and emitted
a second path; the merge reader did not require exact index-to-member agreement.
The canonical stdlib engine now owns naming, indexing, bounded archive reads,
verification and atomic no-overwrite publication. Both collectors call it. The
wrapper only gathers a bounded non-actuating target manifest and delegates.

Normal support defaults to the invoking administrator's home when validated;
`--output`, `--output-dir`, `/tmp`, explicit `--json`, and owner-only permissions
are shared with installer-failure collection. Combined failure evidence merges
verified common members rather than publishing two archives. Missing collectors
remain explicit omissions. Current readiness is filtered through B4's canonical
freshness reader, not raw JSON from an old process.

## Narrow and integration evidence

`PYTHONPATH=src:. python -m unittest tests.unit.test_attempt03_evidence_transport
 tests.unit.test_support_export tests.unit.test_v09_installer_failure_bundle
 tests.integration.test_support_collection_process -q`

The log is `evidence/continuation/b5-cascade.log`. It includes real compressed
archive readback, exact indexed member agreement, malformed/traversing/link/
duplicate/corrupt input rejection, size limits, no-overwrite races, failed-write
cleanup, private-content exclusion, sudo/output policy, staged failure collection,
and thin-wrapper subprocess behavior. Synthetic fixtures do not prove Pi execution.

## Limits and continuation

The new transport does not certify every producer's hardware claims. The member
index deliberately continues to say physical acceptance is false. Legacy
checkpoint ZIP readers may remain for historical source ingestion; newly generated
support/failure archives have only one canonical `.tar.bz2` path. No physical
sensor/relay/audio/power operation was run. Continue with broader regression and
repair any affected consumer before promoting an installation candidate.
