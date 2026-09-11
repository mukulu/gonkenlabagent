# GonKenLab Agent

GonKenLab Agent is a privacy-oriented Raspberry Pi assistant for local,
source-grounded AI-lab use. It is designed to run without cloud services: local
speech recognition, local retrieval, Qwen 3.5 2B through loopback-only Ollama,
local speech synthesis, and a physical push-to-talk control.

## Quick Raspberry Pi Setup

Use a Raspberry Pi 5 with Raspberry Pi OS Lite 64-bit, a microSD card, network
for installation, and the intended USB microphone/speaker connected before the
first run if available. The assistant is installed as a headless system service,
so automatic desktop login is not required.

1. Flash Raspberry Pi OS Lite 64-bit to the microSD card with Raspberry Pi
   Imager.
2. In Raspberry Pi Imager, set hostname, Wi-Fi or Ethernet, username/password,
   locale, and enable SSH.
3. Boot the Pi and connect by SSH.
4. Install Git if the image does not already have it:

```bash
sudo apt update
sudo apt install -y git
```

5. Clone the repository and start the bootstrap:

```bash
git clone https://github.com/mukulu/gonkenlabagent.git
cd gonkenlabagent
./bootstrap.sh --source-url https://github.com/mukulu/gonkenlabagent.git --ref main
```

The bootstrap performs the supported platform checks, installs the application
release, provisions Ollama and the selected model, provisions speech artifacts,
installs the headless service, and records structured diagnostics. It is designed
to be rerun after a recoverable failure such as interrupted networking or a
reboot during installation.

## After Installation

Check the service:

```bash
systemctl status gonken-agent.service
```

View recent service logs:

```bash
journalctl -u gonken-agent.service -n 100 --no-pager
```

Create a private diagnostic ZIP to upload for troubleshooting:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/collect-support.sh
```

The command prints the support ZIP path. By default, service startup also writes
a content-free hardware/software snapshot at:

```text
/var/lib/gonken-agent/runtime/startup/latest.json
```

In the current default debug mode, the service keeps a bounded history of recent
startup snapshots in the same directory. This helps compare cases where USB
audio, GPIO, services, memory, or thermal state differs between reboots. For
production-style operation, the service can be started with
`--diagnostic-mode production`, which keeps only the latest startup snapshot
unless a retention value is explicitly supplied.

Update, rollback, and uninstall are explicit administrator actions:

```bash
sudo /usr/local/lib/gonken-agent/current/maintenance/update.sh
sudo /usr/local/lib/gonken-agent/current/maintenance/rollback.sh
sudo /usr/local/lib/gonken-agent/current/maintenance/uninstall.sh
```

Uninstall keeps project data by default. Data purge requires a separate explicit
confirmation flag documented by `uninstall.sh --help`.

## Configuration

The main site configuration file is:

```text
/etc/gonken-agent/config.toml
```

Most users should not need to edit it during first installation. The important
defaults are:

- local Ollama model: `qwen3.5:2b-q4_K_M`;
- microphone and speaker match text: `AIRHUG`;
- push-to-talk GPIO: `17`;
- recording LED GPIO: `27`;
- dashboard bind address: `127.0.0.1`.

To inspect the effective configuration without exposing absolute filesystem
paths:

```bash
gonken-agent config show --effective --json
```

## Current Release Boundary

This branch is still a private engineering workstream. The installer, immutable
release lifecycle, service installation, update, rollback, uninstall, diagnostic
snapshot, support export, and host-side automated tests are implemented. Physical
Raspberry Pi acceptance must still be established from logs and a real target
run, especially for USB audio behavior, GPIO wiring, reboot persistence, thermal
state, and live speech quality.

If the Pi run fails, rerun the bootstrap once after correcting obvious network or
power issues, then upload the support ZIP created by `collect-support.sh`.
Use [the Raspberry Pi acceptance runbook](docs/RASPBERRY_PI_ACCEPTANCE_RUN.md)
for the first clean install, reboot, update, rollback, uninstall and diagnostic
collection pass.

## Development authority

Repository state and Git history are the project handoff. Start with:

- `docs/development/MASTER_BLUEPRINT.md` — accepted engineering contract;
- `docs/development/IMPLEMENTATION_STATUS.md` — exact completed/current/next state;
- `docs/development/TEST_MATRIX.md` — commands, environments, and results;
- `docs/development/DECISIONS.md` — append-only architectural decisions;
- `docs/development/REPOSITORY_AUDIT.md` — frozen baseline evidence.

`PRD.md` is historical provenance only and is not implementation authority.

Development proceeds continuously across verified dependency-ready items. No milestone
imposes a conversation stop. `MILESTONES.json` generates the complete status table,
and CI rejects status drift. Host evidence and physical release acceptance remain distinct.

## Current package, configuration, and dependency boundary

The maintained package provides typed configuration, fail-closed dependency profiles,
grounded text diagnostics, and host-tested runtime/audio/PTT contracts. From a development checkout:

```bash
PYTHONPATH=src python -m gonken_agent version
PYTHONPATH=src python -m gonken_agent status --json
PYTHONPATH=src python -m gonken_agent config show --effective --no-site
```

The package imports without audio, model, GPIO, UI, network, or extension
dependencies. `gonken-agent run --text-only` provides an explicit diagnostic session;
plain `gonken-agent run` still refuses voice activation while speech/hardware gates remain open.
See [the text runtime guide](docs/development/TEXT_RUNTIME_GUIDE.md) for tested index,
question, dashboard and telemetry commands. For migration testing only, the historical source
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

## Bootstrap status

M3.4 adds pinned Ollama/model provisioning after verified immutable application
release activation. To validate
prerequisites only, run:

```bash
./bootstrap.sh --preflight-only \
  --source-url https://github.com/mukulu/gonkenlabagent.git \
  --ref main
```

It validates the supported Pi/OS/Python/systemd contract, resources, clock,
administrator access, checkout cleanliness, and the advertised source ref
before writing a private staging record. Without `--preflight-only`, it
revalidates the record and remote commit, creates the dedicated non-login
runtime account on the target, builds a release-local virtual environment from
the applicable exact lock, validates an immutable commit-named release, and
activates it through a durable journal and atomic `current` link. On the
validated Raspberry Pi target it then installs checksum-pinned Ollama `0.33.3`
under a separate `ollama` account, installs its exact loopback/no-cloud systemd
unit, pulls `qwen3.5:2b-q4_K_M`, records the full local digest, and runs an
inference smoke. It then provisions pinned Whisper/Piper speech artifacts and
runs a content-free real speech-chain smoke. It then prints a content-free `M3_6_INSTALL_SUMMARY` classified as
`DEGRADED`, because the application service and physical hardware integration
are not accepted yet. Use `--speech-only` to return success at the M3.5
boundary. It never invokes the retained `setup.sh`.

For an M3.3 development-host lifecycle test that returns after release
activation, use a disposable private root:

```bash
temporary_root="$(mktemp -d)"
mkdir "$temporary_root/empty-checkout"
./bootstrap.sh --development-host \
  --source-url "$(pwd | sed 's#^#file://#')" \
  --ref "$(git branch --show-current)" \
  --existing-checkout "$temporary_root/empty-checkout" \
  --staging-parent /tmp
```

The normal development bootstrap reports `M3_4_TARGET_REQUIRED`; use
`scripts/install.sh --release-only` for the development-host release lifecycle.
The automated M3.4 suite uses only local binary/systemd/API fixtures in
temporary roots. See `docs/development/ONBOARDING_DRAFT.md`,
`docs/development/RELEASE_ACTIVATION_SCHEMA.md`, and
`docs/development/OLLAMA_MODEL_LIFECYCLE.md` for the exact boundary.

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

M3.3 retains one default T0/T1 entry point. It requires no live model, internet,
Ollama, audio, GPIO, pygame, root access, or governed extension:

```bash
./scripts/ci.sh
```

Interactive audio/wake checks live under `tests/hardware/`; the live Ollama
router observation lives under `tests/integration/manual/`. Each requires a
specific opt-in variable and is excluded from automated discovery. Results are
meaningful only when the environment recorded in
`docs/development/TEST_MATRIX.md` matches the test tier. See `tests/README.md`.

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
