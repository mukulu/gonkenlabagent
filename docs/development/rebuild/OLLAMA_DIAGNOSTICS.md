# Ollama diagnostic reconstruction

## Observed defect and repair

The inspected CKPT45 runtime raised a generic HTTP code without retaining the
status/body class. The installer wrapped HTTPError into a generic exception.
Both now preserve content-free HTTP status, API path, configured model and request
shape with a bounded server-error classification. No raw message/body/prompt or
hash of private content is retained. HTTP 200 containing an `error` object is not
accepted as API success by the runtime.

A category such as EOF or OUT_OF_MEMORY is a diagnostic hint, not a proven cause.
The exact Pi failure remains a target experiment. No runtime pin, model pin or
inference budget is silently changed by this repair.

Narrow verification: `tests.unit.test_attempt03_ollama_errors`, existing Ollama
manager and multimodel tool suites: 28 tests passed. See `evidence/b2-errors.log`.

## Primary API reference rechecked 2026-09-21

- `https://docs.ollama.com/api/errors`: JSON `error` responses and HTTP status codes.
- `https://docs.ollama.com/api/chat`: tools, format, think, keep_alive, completion.

These are interface references, not evidence of the user's runtime version or
hardware behavior.

## Per-model stage repair

The v2 roster record invalidates an old READY before starting a new attempt and
atomically saves INVENTORY, PREREQUISITES, pull, identity, inference, tools,
unload and admission progress. A failed later model preserves prior results.
Cleanup has a separate outcome and cannot replace the first causal failure.
Unload requires a completed transaction and an empty loaded-model inventory.
Tool success requires the exact tool, empty arguments, completion and model.

Status no longer promotes model presence or a legacy minimal READY record to
qualification. It checks full model digests and completed required stages;
runtime admin additionally rejects context drift. An explicitly selected model
must have qualified tools. This retains the previous policy for conversation-only
alternate models but reports their tool limitations. It does not silently change
which model is selected or lower its required capabilities.

Record migration is deliberate: v1 records trigger a fresh qualification pass
without deleting model files. The install-summary consumer was migrated to v2.
44 focused and affected tests passed; see `evidence/b2b-qualification-final.log`.

## B2c: bounded maintenance experiment

The installer local API now normalizes localhost to numeric loopback, excludes
proxy environment variables and redirects, bounds response bytes, and rejects
HTTP-200 error objects. Service readiness uses one 60-second total deadline and
at most two seconds per version request, rather than 60 calls of 120 seconds.
The online pull stream bounds individual metadata lines; it never prints raw
server error messages. No production runtime/model pins or inference settings
were changed based on an unsupported diagnosis.

`scripts/ollama_qualification_matrix.py` runs exactly one admitted model/case.
It is not a normal health probe: first stop voice and other inference consumers
in a controlled maintenance window. The explicit `--maintenance-confirmed`
flag is an operator assertion, not independent proof of exclusive access. The
harness also refuses a nonempty `/api/ps` before starting. Do not run it alongside
production inference. It does not execute returned tools, alter model selection,
install models, or make hardware claims. Cases are synthetic comparisons, not
proof of the unknown target HTTP-500 root cause.

Example from the source checkout, during that maintenance window:

```sh
PYTHONPATH=src python3 scripts/ollama_qualification_matrix.py \
  --model qwen3:0.6b --case schema --context 2048 --output-tokens 128 \
  --timeout 60 --maintenance-confirmed --output "$HOME/ollama-schema-case.json"
```

Use a new output path per case; existing files are refused. `plain`, `json`,
`schema`, `tools`, and `schema-tools` are separate runs. Change only one setting
between comparisons. Token/context variants do not require a runtime upgrade.
API version, admitted full digest, source hash, request shape, result metadata,
per-stage timings and separate cleanup failure are retained; generated content
and prompts are not. Target/version rollback is still a separately governed
experiment, not automatically performed by this tool.
