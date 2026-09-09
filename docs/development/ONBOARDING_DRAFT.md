# GonKenLab Agent onboarding draft

**State:** M3.4 Ollama/model boundary; not a complete assistant installation guide

This draft records the intended clean-device path while provisioning is built.
At the current checkpoint, `bootstrap.sh` validates prerequisites, writes a
private source manifest, and routes a normal invocation through the M3.2 step
engine, M3.3 immutable-release lifecycle, and M3.4 Ollama/model lifecycle. It can install target bootstrap
prerequisites, create the `gonken-agent` non-login account, acquire the exact
recorded commit, build and validate a release-local virtual environment, and
activate it. On the supported target it can also create the separate `ollama`
identity, install the pinned verified Ollama payload and systemd unit, pull and
digest-bind Qwen, and run a deterministic API smoke. It deliberately does not
run `setup.sh`, install speech artifacts, configure the application service or
hardware, or claim that the assistant is ready.

## Supported target

- Raspberry Pi 5 with 4GB RAM;
- Raspberry Pi OS Lite 64-bit based on Debian 13 Trixie;
- AArch64 kernel and 64-bit userspace;
- distribution Python 3.13;
- systemd as PID 1;
- at least 8 GiB free on the selected staging filesystem.

Use Raspberry Pi Imager to configure hostname, an administrator account,
network, and SSH before first boot. The alternative official Network Install
path may be used with wired Ethernet, display, and keyboard. Neither
path requires automatic desktop login.

## Current preflight invocation

Run from a complete checkout only:

```bash
./bootstrap.sh --preflight-only \
  --source-url https://github.com/mukulu/gonkenlabagent.git \
  --ref main
```

The command validates the platform, disk, RAM, plausible system time, required
commands, administrator access, existing checkout state, network/TLS Git access,
and the requested advertised branch/tag. Only after all checks pass does it
create a mode-700 directory below `/var/tmp` containing a mode-600
`source.record` with the requested URL/ref, resolved commit, exact interpreter,
Raspberry Pi image reference and file fingerprints, systemd version, and
resource observations. The record is data and must never be sourced as shell
code.

For host-only verification, `--development-host` accepts 64-bit Linux x86_64 or
AArch64 with Python 3.12/3.13. Development-host success is T1 evidence only; it
does not establish Raspberry Pi compatibility.

## Failure and rerun interpretation

Errors have stable `code=...`, `message=...`, and `remediation=...` fields. A
failed preflight performs no package, service, checkout, configuration, or
installed-release mutation. Correct the reported condition and rerun.

If `--preflight-only` is omitted, the installer independently revalidates the
source record and remote commit, runs the release steps, and records either a
healthy post-verified activation or a structured failure. A rerun validates
actual artifacts rather than trusting advisory completion records. Failed
candidate construction never moves `current`; failed post-switch validation
restores the prior validated release when one exists.

Successful target provisioning prints `M3_3_RELEASE_COMPLETE` and
`M3_4_OLLAMA_COMPLETE`, then the normal bootstrap ends with
`M3_5_UNAVAILABLE`. This deliberate nonzero boundary means the core package,
Ollama service, and selected model are validated, but speech and the complete
assistant are not. Do not interpret it as `READY`. Use `--ollama-only` only to
return success at this explicit milestone boundary. A development host instead
reports `M3_4_TARGET_REQUIRED`; its M3.4 behavior is exercised with isolated
local fixtures rather than an unrepresentative host installation.

See `INSTALL_STATE_SCHEMA.md` for the step-engine contract and
`RELEASE_ACTIVATION_SCHEMA.md` for release paths, journal phases, reconciliation,
retention, failure codes, and the development-only temporary-root procedure.
See `OLLAMA_MODEL_LIFECYCLE.md` for the binary/model pins, paths, service
settings, digest record, and target diagnostics. The exact next implementation
is M3.5 Whisper and Piper artifact lifecycle—not the GonKen application service,
audio/GPIO policy, wake word, or a claim of unattended readiness.
