# Checkpoint 33 verification harness notes

- `integration_fast.log`: aggregate command exceeded its outer execution bound after 38 integration tests had completed PASS. The single unaccounted `test_v09_user_test_release_candidate` case was then run independently and PASS. The aggregate is recorded as INTERRUPTED, not PASS.
- `release_group1.log`: aggregate command exceeded its outer execution bound after the first two end-to-end release cases completed PASS. The two unaccounted cases were run independently and PASS. The aggregate is recorded as INTERRUPTED, not PASS.
- The first grouped speech-case command was reported interrupted by the external tool boundary even though the fourth case log completed PASS. Remaining speech cases were then run in bounded groups and all 12 cases are accounted PASS.
- A final targeted unittest command initially referenced a stale class name (`ReleaseBuildTests`) and was rejected by unittest discovery before product code ran. The command was corrected to `IntegrityAndPrivilegeTests`; the intended transient-cache and authoritative-tamper tests passed. This is classified as a verification-command error, not a product failure.
