# GonKenLab Agent onboarding draft

**State:** M3.1 preflight only; not an installation guide

This draft records the intended clean-device path while provisioning is built.
At the current checkpoint, `bootstrap.sh` validates prerequisites and writes a
private source manifest. It deliberately does not install packages, clone code,
run `setup.sh`, configure services, or claim that the assistant is ready.

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

If `--preflight-only` is omitted at M3.1, successful preflight ends with
`M3_2_UNAVAILABLE`. This is deliberate: the repository refuses to route a clean
installation through the retained, unaccepted `setup.sh` prototype. M3.2 must
provide the resumable installer before this document can become a user-facing
installation guide.
