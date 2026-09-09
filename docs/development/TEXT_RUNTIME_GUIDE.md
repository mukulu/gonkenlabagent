# Text diagnostics and continued implementation

This checkpoint preserves M3.4 provisioning and adds executable local text diagnostics,
software runtime/audio/PTT contracts, retrieval and observability. It is not a deployed
voice appliance. Use `IMPLEMENTATION_STATUS.md` for item-by-item software and target gates.

## Run the synthetic demonstration

From the extracted repository on Linux with Python 3.12 or 3.13:

```bash
export PYTHONPATH="$PWD/src"
mkdir -m 700 -p /tmp/gonken-text-demo
python -m gonken_agent index build \
  --no-site --set "paths.corpus_dir=$PWD/tests/fixtures/grounding/corpus" \
  --index /tmp/gonken-text-demo/index.json \
  --calibration tests/fixtures/grounding/calibration.json
python -m gonken_agent ask 'What is the booking duration for the Atlas bench?' \
  --no-site --set "paths.corpus_dir=$PWD/tests/fixtures/grounding/corpus" \
  --index /tmp/gonken-text-demo/index.json --extractive
python -m gonken_agent ask 'Explain coral bleaching.' \
  --no-site --set "paths.corpus_dir=$PWD/tests/fixtures/grounding/corpus" \
  --index /tmp/gonken-text-demo/index.json --extractive
```

The first answer is a verbatim retrieval preview with its source identifier. The second
abstains. The corpus is invented test data, not Sophia University policy. Without
`--extractive`, `ask` uses the configured local Ollama model and validates its JSON
answer/citation format. An existing accepted model is required; no download is attempted.
Valid source IDs do not establish that every model claim is entailed by its sources.

For a continuous stdin session with a dashboard:

```bash
python -m gonken_agent run --text-only --extractive --with-dashboard \
  --no-site --set "paths.corpus_dir=$PWD/tests/fixtures/grounding/corpus" \
  --index /tmp/gonken-text-demo/index.json \
  --telemetry /tmp/gonken-text-demo/telemetry.jsonl
```

Type a question followed by Enter. Ctrl+D exits after submitted questions; Ctrl+C or
SIGTERM cancels and closes the session. Open `http://127.0.0.1:8080` locally. No audio is
captured. For remote viewing use SSH local forwarding. The dashboard requires its
numeric loopback Host header and exposes no mutation routes. If port 8080 is in use,
choose another validated `--set dashboard.port=...` value.

Persistent telemetry is content-free and rotates by size. By default, the dashboard
also omits interaction text. Explicit `--set privacy.dashboard_transient_content=true`
permits the current interaction in process memory, clears it on shutdown/restart and
still writes no content into telemetry. Persistent interaction logging remains rejected
until its research/retention governance is implemented and accepted.

`gonken-agent dashboard` is a separate diagnostic server and is deliberately marked
DEGRADED because it is not connected to a running assistant. Use the integrated
`run --text-only --with-dashboard` path for current interaction metrics.

## Use a real local corpus

Use a bounded directory containing UTF-8 `.md` and `.txt` files. Symlinks, unsafe names,
nonregular documents, files over 256 KiB, more than 256 documents, total document bytes
over 8 MiB and directory nesting beyond 12 levels are rejected. Corpus source hashes,
chunking settings, content-derived source IDs and the calibrated support threshold are
recorded in the index. Runtime checks the corpus before each query and refuses stale
or corrupt indexes; explicitly rebuild after approved corpus updates.

Calibration JSON is a list of objects with `query` and `expected_paths` (a list of
corpus-relative document names, empty for unanswerable questions). Include both types.
Keep separate evaluation cases and representative in-domain unsupported questions.
The supplied benchmark is a synthetic regression test with easy out-of-domain negatives;
its percentages are not release-quality or research-generalization evidence.

## Diagnostics and tests

```bash
python -m gonken_agent doctor --no-site
./scripts/ci.sh
python scripts/benchmark_grounding.py --output /tmp/gonken-text-demo/benchmark.json
```

Doctor returns 2 (DEGRADED) while physical and provisioning gates remain open. Its
optional `--probe-ollama` contacts only the configured numeric loopback endpoint. No
hardware, package installation or network download is performed by the CI entrypoint.

## Private support export

```bash
python -m gonken_agent support --no-site \
  --output /tmp/gonken-text-demo/support.zip
```

The output must not already exist. The archive contains only generated environment,
redacted configuration, categorical health and optional revalidated telemetry JSON.
Use `--telemetry PATH` to include at most 100 content-free events; pass `--index` and
the matching corpus override when events contain source IDs. Raw logs, corpus files,
audio, credentials, exception text and Git history are never bulk-copied. Hardware
readiness is still reported as unestablished. Retain the source checkpoint separately.

## What remains

M3.5 must settle the existing speech dependency/voice policy and verify immutable
Whisper/Piper artifacts, builds and real smoke samples. M4/M5 still need real ALSA and
GPIO adapters and physical acceptance. M6 service activation depends on that executable
voice path. M7 needs real-lab evaluation, model injection/contradiction evidence and Pi
performance/thermal measurements. M8 operational coverage and M9 physical release gates
remain open as specified in the complete ledger. Continue useful independent work while
recording those dependencies; do not reintroduce one-item-per-session stopping rules.
