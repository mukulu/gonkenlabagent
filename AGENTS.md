# GonKenLab Agent development workflow

Read `docs/development/IMPLEMENTATION_STATUS.md`, `MASTER_BLUEPRINT.md`,
`TEST_MATRIX.md`, `MILESTONES.json` and relevant `DECISIONS.md` entries before changes.

- Continue through dependency-ready blueprint work in the same session. Completing
  one milestone or sub-item is never a reason to stop or request fresh permission.
- Implement a coherent item, verify its success/failure cases, update evidence and
  commit tested progress, then proceed. Group small coherent items when useful.
- A blocked requirement blocks its actual dependants. Record the missing evidence
  and continue independent work. Never weaken acceptance to increase completed counts.
- Maintain separate software/host evidence and physical target/release acceptance.
  Mocked GPIO/audio/systemd/network tests do not establish Pi readiness.
- `MILESTONES.json` must contain every core blueprint item. Regenerate status with
  `python scripts/milestone_status.py`; CI rejects omissions and status drift.
- Run proportionate tests during implementation; run `./scripts/ci.sh` at checkpoint
  close. Additional broad runs need a concrete defect, remaining risk or required gate.
- End a work session at a committed, resumable boundary. Record partial work and exact
  next actions. Use descriptive checkpoint names if earlier requirements remain open.
- Preserve Git history and private-development license/provenance restrictions. Do not
  push, publish, activate services or claim physical acceptance without applicable
  authorization and evidence. No shell/tool execution may be selected by model output.
- Portable checkpoints contain committed tracked files and `.git`, preserve executable
  modes, and must pass archive integrity, extracted Git cleanliness and object checks.
