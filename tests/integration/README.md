# Integration test boundary

Automated files directly under this directory are deterministic subprocess or
filesystem tests. They may not require internet access, live Ollama, models,
audio, GPIO, pygame, or root privileges and are run by `scripts/ci.sh`.

`manual/` contains explicitly invoked live-service probes excluded from the
default suite. The legacy router probe requires both an intentional local
Ollama environment and this opt-in variable:

```bash
GONKEN_RUN_LIVE_INTEGRATION=1 .venv/bin/python \
  tests/integration/manual/router_live_manual.py
```

Its joke expectation is `get_joke`, matching the inspected router. It is still
a nondeterministic model-integration observation, never a unit regression test.
