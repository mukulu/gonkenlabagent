# Attempt03 explicit reconstruction

This branch starts from the intact, user-supplied CKPT45 repository at
`6aa60fbc2bda3499400d7a0627a6f2a47840a4a2`. It does not contain or claim recovery of
missing CP46.7R1 commit `88d23bf3ebd67679db369c5c3e77f87a8d01b4a4`.
The user requested continued implementation rather than another blocked recovery
session. Changes are reconstructed from current inspected source and Attempt03;
old handoff test counts are historical, not fresh validation of this branch.

## Development / release distinction

Development commits may preserve unfinished work. Each such commit must be
marked WIP in the current record, with failing/unrun checks stated explicitly.
A clean committed tree is required for byte-complete export; it does NOT mean
software is stable. Only a checkpoint with all declared host gates passed can
be promoted to a host-verified branch. Pi/HIL gates require actual target evidence.
Never merge an untested work-in-progress into main or call it a stable release.

## Export and recovery

Use `python3 tools/recovery_guard.py create --help` for the explicit export
interface. The RG1 guard has been imported without behavioral changes from
checkpoint `bdd726e41e0d8ff10dff855c3fc88d0b943ec7b3`; its original tests are under
`tests/recovery`. It exports committed Git objects, not a dirty worktree.
A development commit remains non-release even after recovery verification.

After each coherent commit, create a unique .tar.bz2 outside the repository;
verify and restore to a fresh directory, save the actual archive in private
Library, retrieve the saved bytes and compare hashes. Record the actual storage
receipt outside the already sealed artifact. Do not confuse a local file path,
commit, or markdown manifest with an externally saved code-bearing artifact.

Final packages include committed tracked source and Git history, not private
credentials, caches, virtual environments or generated test data. No remote push,
service activation, real GPIO operation or physical acceptance is authorized by
an export or by a host test.
