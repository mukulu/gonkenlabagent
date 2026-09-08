# GonKenLab Agent

GonKenLab Agent is being rebuilt as a headless Raspberry Pi 5 4GB appliance
for local, source-grounded spoken access to a bounded AI-lab corpus. The
release path will use local Whisper speech recognition, local retrieval,
Qwen 3.5 2B through loopback-only Ollama, local Piper speech synthesis, and a
physical push-to-talk control with an explicit recording indicator.

This branch is an implementation workstream, not an install-ready release.
The inspected prototype remains reachable through a compatibility launcher,
but its installer, runtime, cloud routing, continuous wake detector, and UI are
not accepted release behavior.

## Development authority

Repository state and Git history are the project handoff. Start with:

- `docs/development/MASTER_BLUEPRINT.md` — accepted engineering contract;
- `docs/development/IMPLEMENTATION_STATUS.md` — exact completed/current/next state;
- `docs/development/TEST_MATRIX.md` — commands, environments, and results;
- `docs/development/DECISIONS.md` — append-only architectural decisions;
- `docs/development/REPOSITORY_AUDIT.md` — frozen baseline evidence.

`PRD.md` is historical provenance only and is not implementation authority.

## Current package, configuration, and dependency boundary

M2.3 provides a dependency-light package/CLI, typed configuration authority,
and fail-closed dependency profiles. From a development checkout:

```bash
PYTHONPATH=src python -m gonken_agent version
PYTHONPATH=src python -m gonken_agent status --json
PYTHONPATH=src python -m gonken_agent config show --effective --no-site
```

The package imports without audio, model, GPIO, UI, network, or extension
dependencies. `gonken-agent run` intentionally refuses to imply that the new
core runtime exists yet. For migration testing only, the historical source
command remains:

```bash
.venv/bin/python orchestrator.py
```

That launcher crosses an explicit compatibility boundary and is not evidence
of release readiness.

`config/defaults.toml` is the only source-controlled default authority. Normal
precedence is packaged defaults, optional `/etc/gonken-agent/config.toml`,
explicit `GONKEN_<SECTION>_<FIELD>` environment variables, then one-shot CLI
`--set SECTION.FIELD=VALUE`. Unknown keys and unsafe/unsupported values fail
closed. Effective output reports each setting's source and redacts filesystem
paths.

Legacy `config/config.json` and checkout `.env` are never loaded normally. To
stage a validated, non-destructive migration to a chosen path:

```bash
PYTHONPATH=src python -m gonken_agent config migrate \
  --legacy-json config/config.json --legacy-env .env \
  --output /tmp/gonken-agent-config.toml
```

Migration refuses to overwrite different output, keeps restricted timestamped
backups, and produces the same output when repeated with unchanged inputs.

Accepted dependency locks and their machine-readable authority live under
`requirements/`. The maintained headless core and current test profile have
exactly zero third-party dependencies. Pygame is an exact/hash-locked optional
UI extra and is not installed by core. Wake-word and TTS profiles are blocked
until their Python 3.13/AArch64 and licensing gates pass; the old broad ranges
survive only as explicitly unaccepted compatibility input for `setup.sh`.

```bash
python scripts/dependencies.py render --check
python scripts/dependencies.py report
```

See `requirements/README.md` for clean-host installation, target resolution,
and dependency-change procedures.

## Accepted first-release boundary

Required core behavior includes:

- Raspberry Pi OS Lite 64-bit on Raspberry Pi 5 4GB;
- unattended systemd startup without automatic login;
- USB input/output audio with deterministic selection and degraded recovery;
- physical push-to-talk and visible recording state;
- local STT, retrieval, LLM, and TTS processing;
- source identifiers and explicit abstention for unsupported answers;
- content-free persistent telemetry and a loopback-only read-only dashboard;
- idempotent install, upgrade, rollback, recovery, doctor, and uninstall paths.

Wake word, voice power control, direct LAN dashboard access, and Bluetooth are
governed extensions. They do not block the core release and remain disabled
until their independent acceptance gates pass.

## Testing

M2.3 host tests require no model, network, audio, GPIO, or optional extension:

```bash
PYTHONPATH=src python -m unittest discover -s tests/unit -v
```

Hardware and installer scripts under `tests/` remain legacy/manual probes until
M2.4 classifies and restructures them. Results are meaningful only when the
environment recorded in `docs/development/TEST_MATRIX.md` matches the test tier.

## Licensing and redistribution

No project license is granted and no `LICENSE` file exists. The current
maintainer policy deliberately prohibits redistribution until a future explicit
license decision. Do not infer rights from earlier README text. The tracked face
PNGs and filler WAVs have unknown provenance and are quarantined as internal
compatibility evidence; they are excluded from package builds, releases, and
public exports.
See `docs/development/LICENSE_PROVENANCE.md` and
`packaging/provenance.toml` for the decision-ready inventory.

The package and any portable Git checkpoint created during development are
private engineering handoffs, not approved redistributable releases. Maintained
Piper and noncommercial voice/wake artifacts are likewise excluded from every
public release path until a compatible, explicitly approved policy replaces
this one.
