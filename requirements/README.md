# Dependency profiles and exact locks

This directory is the M2.3 dependency authority. `profiles.toml` records the
accepted and blocked profiles, exact wheel identities, hashes, licenses, target
interpreters, and target platforms. The `*.lock` files are deterministic
generated views; do not edit them directly.

The maintained Python package profile has no third-party **pip/wheel** core or
test dependency. Raspberry Pi hardware bindings are a separate, explicit
target-OS contract: the installer provisions Debian `python3-libgpiod` and
`python3-smbus`, and only the `core-pi-trixie-py313` immutable venv is created
with system-site visibility so those root-managed distro bindings are visible
to the production interpreter. Development profiles remain isolated. The
release validator checks the exact hardware API surface before target
installation can proceed, so an APT-level install cannot be mistaken for a
usable application runtime.

## Profiles

| Profile | Purpose | State |
|---|---|---|
| `core-pi-trixie-py313` | Headless production target | Installable; zero pip/wheel dependencies; consumes validated Debian `python3-libgpiod` + `python3-smbus` through the target-only system-site policy |
| `dev-py312` | Current x86 host unit/static checks | Installable; zero third-party dependencies |
| `ui-pi-trixie-py313` | Optional Raspberry Pi UI evaluation | Installable separately; `pygame` exact/hash-locked |
| `ui-dev-py312` | Optional x86 UI import evaluation | Installable separately; `pygame` exact/hash-locked |
| `x1-wake-pi-trixie-py313` | Governed wake-word extension | Blocked; intentionally has no lock |
| `core-voice-runtime-pi-trixie-py313` | Future packaged voice runtime | Blocked pending TTS/package/voice decisions |

`requirements/legacy-prototype.in` is unpinned compatibility evidence for the
retained, explicitly unaccepted `setup.sh`. It is not a lock and is not an
accepted install path. The former root `requirements.txt` no longer exists.

## Regenerate and verify

The renderer uses only the Python standard library and canonicalizes package
ordering and lock headers:

```bash
python scripts/dependencies.py render
python scripts/dependencies.py render --check
python scripts/dependencies.py report
python scripts/dependencies.py report --json
python scripts/dependencies.py digest
```

Every installable lock forces hashes and wheels. A dependency without a wheel
for the declared interpreter/platform fails rather than silently building from
source.

## Clean host install

On the recorded x86_64/Python 3.12 development host:

```bash
python3.12 -m pip wheel --no-index --no-deps --no-build-isolation \
  --wheel-dir /tmp/gonken-m2.3-wheels .
python3.12 -m venv /tmp/gonken-m2.3-host
/tmp/gonken-m2.3-host/bin/python -m pip install \
  --no-index -r requirements/dev-py312.lock
/tmp/gonken-m2.3-host/bin/python -m pip install \
  --no-index --no-deps /tmp/gonken-m2.3-wheels/gonkenlab_agent-*.whl
/tmp/gonken-m2.3-host/bin/python -m pip check
PYTHON_BIN=/tmp/gonken-m2.3-host/bin/python ./scripts/ci.sh
```

The optional UI profile requires its wheel to be downloaded into a controlled
wheelhouse first; it is never installed by the headless command.

## Target resolution probe

Run from a network-enabled resolver host into a new temporary wheelhouse:

```bash
python -m pip download \
  --dest /tmp/gonken-core-wheelhouse \
  --platform manylinux_2_28_aarch64 \
  --python-version 3.13 --implementation cp --abi cp313 \
  -r requirements/pi-trixie-py313.lock

python -m pip download \
  --dest /tmp/gonken-ui-wheelhouse \
  --platform manylinux_2_17_aarch64 \
  --python-version 3.13 --implementation cp --abi cp313 \
  -r requirements/ui-pi-trixie-py313.lock
```

The M2.3 audit verified from PyPI metadata that the exact UI wheel exists for
CPython 3.13/AArch64 and recorded its PyPI SHA-256. That is a metadata-level
resolution result, not a download, import, Raspberry Pi venv, or hardware pass.
Those checks remain blocked until a network-enabled resolver and physical Pi
are available.

## Adding or changing a dependency

1. Prove the exact CPython/platform wheel exists; source builds are rejected.
2. Inspect transitive metadata and resolve the entire graph for every affected
   profile.
3. Record exact versions, artifact filenames, SHA-256 values, upstream source,
   and SPDX-style license expressions in `profiles.toml` and provenance docs.
4. Regenerate locks and review the diff.
5. Build a fresh wheelhouse using the target-resolution command.
6. Install from that wheelhouse with `--no-index`, run `pip check`, imports,
   unit/integration tests, and the license report.
7. On Raspberry Pi, repeat the clean venv install and record it in the test
   matrix before claiming target support.

Blocked profiles do not receive placeholder locks. Creating a wake lock before
the X1 spike—or bypassing metadata with `--no-deps`—would turn a known failure
into hidden dependency drift.
