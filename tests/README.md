# Test architecture

`scripts/ci.sh` is the single default repository test entry point. It runs T0
static checks, dependency-lock drift validation, the dependency-free unit
suite, and deterministic subprocess/filesystem integration tests. It performs
no package installation and makes no network, Ollama, model, audio, GPIO,
pygame, or privileged request.

```bash
./scripts/ci.sh
```

The current runner is Python's standard-library `unittest`, which is available
in both exact empty M2.3 core/dev profiles. Tests use class/method conventions
that remain discoverable by pytest, but pytest is not claimed or added without
a complete hash-locked dependency graph and a clean offline install. The tier
and isolation contract matters more than a runner brand.

| Location | Default execution | Evidence meaning |
|---|---|---|
| `tests/unit/` | Yes | Pure deterministic logic with fakes/mocks; no external boundary |
| `tests/integration/` | Yes, direct files only | Local process/filesystem contracts; no live service or hardware |
| `tests/integration/manual/` | No; explicit opt-in | Nondeterministic live-service observation |
| `tests/hardware/` | No; explicit opt-in | Physically supervised peripheral/model observation |
| `tests/fixtures/` | Data/helpers only | Deterministic shared inputs and test doubles |

Manual results do not become regression evidence merely because a script exits
zero. Record the environment and relevant tier in the test matrix. Raspberry
Pi, reboot/recovery, and failure-injection suites will be added by the
milestones that implement those boundaries.

M3.2 adds deterministic process failure injection through the tracked install
engine harness. `GONKEN_ENABLE_TEST_FAILURES=1` is required before its
before/during/after TERM or KILL controls become active; production installer
steps never set that gate. These tests establish host control-flow recovery,
not Raspberry Pi storage durability or physical power-loss behavior.
