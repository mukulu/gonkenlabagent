# Ollama and selected-model lifecycle

**Implemented milestone:** M3.4  
**Implementation commit:** `980e09c153d4c3232c6bc8390bcbd4f1dcf0a1bd`  
**Evidence tier:** T0/T1 complete; T2/T3/T5/T6 target evidence blocked

This document defines the installed Ollama state accepted by GonKenLab Agent.
It is a provisioning contract, not a claim that a real Raspberry Pi has passed
the performance, thermal, reboot, or power-loss gates.

## Admitted artifacts

`packaging/ollama-artifacts.toml` is the closed-schema source authority. On
2026-09-09, the latest stable upstream release was recorded as Ollama `0.33.3`;
the newer `0.34.0` entry was a pre-release and was not selected. The admitted
ARM64 asset is:

- release: `v0.33.3`;
- asset: `ollama-linux-arm64.tar.zst`;
- SHA-256: `4425a112af999ae6572c1ce211fbabeaca7bab23ed5860972acdfc0cc2358420`;
- source: `https://github.com/ollama/ollama/releases/tag/v0.33.3`;
- license recorded in project provenance: MIT.

The selected model remains `qwen3.5:2b-q4_K_M`. Its official catalog entry
reported digest prefix `124a03c34777`, quantization `Q4_K_M`, parameter size
`2.27B`, and display size approximately `1.9GB`. The installer does not invent
or truncate a full digest. After pull it reads `/api/tags`, requires one exact
tag with a 64-character digest beginning with the admitted prefix, and records
that full local digest. A later change to that full digest fails as
`OLLAMA_MODEL_DRIFT` and requires an explicit repin.

## Installed paths and identities

| Path | Owner/purpose |
|---|---|
| `/usr/local/lib/ollama/releases/v0.33.3` | Root-owned, read-only extracted release with payload record |
| `/usr/local/lib/ollama/current` | Constrained relative link to the admitted release |
| `/usr/local/bin/ollama` | Stable relative link through `current` |
| `/var/cache/gonken-agent/downloads` | Resumable verified installer downloads |
| `/var/lib/ollama/models` | Mode `0750`, owned by the separate `ollama` account |
| `/etc/systemd/system/ollama.service` | Exact source-controlled system unit |
| `/etc/systemd/system/ollama.service.d/gonken-agent.conf` | Exact rendered resource/privacy settings |
| `/var/lib/gonken-agent/install/ollama.record` | Mode `0600` validation and full-digest evidence |

The `ollama` account is a distinct system identity with group `ollama`, home
`/var/lib/ollama`, and shell `/usr/sbin/nologin`. A mismatched existing account,
symlinked data path, non-directory conflict, or differing existing systemd file
fails closed. The installer does not adopt or overwrite those states.

## Acquisition and activation

Production acquisition requires root on Linux AArch64, an HTTPS URL, and the
published SHA-256. Downloads use a retained `.part` file and an HTTP Range
request on rerun. A checksum mismatch deletes only the untrusted partial file
and never constructs a release. Redirects must remain HTTPS.

The verified Zstandard payload is expanded to an identity-scoped candidate.
Absolute/traversing paths, duplicate members, devices, FIFOs, and escaping
links are rejected; set-user-ID/set-group-ID bits and archive ownership are not
preserved. The candidate records the asset, binary, and complete extracted
payload digests. Its final rename is same-filesystem and its final tree has no
write bits. A narrowly interrupted rename-to-top-mode interval is repaired
only when the record, payload digest, descendant modes, and ownership are exact.

The application immutable release contains the exact M3.4 manager, manifest,
unit, and drop-in used by installation. Target installation therefore does not
trust a mutable checkout after the M3.3 activation boundary.

## Service and resource policy

The unit runs `/usr/local/bin/ollama serve` as `ollama`, uses `Type=exec`, and
restarts on failure. The rendered drop-in enforces:

- `OLLAMA_HOST=127.0.0.1:11434` under defaults, with any override still required
  to be an explicit loopback HTTP origin;
- `OLLAMA_NO_CLOUD=1`;
- `OLLAMA_MODELS=/var/lib/ollama/models`;
- `OLLAMA_MAX_LOADED_MODELS=1`;
- `OLLAMA_NUM_PARALLEL=1`;
- `OLLAMA_CONTEXT_LENGTH=2048` under the authoritative default;
- `OLLAMA_MAX_QUEUE=4`.

The unit also removes capabilities and applies basic systemd filesystem/process
hardening. M3.4 does not claim kernel-enforced outbound-network denial: the
service needs installation-time network access for model acquisition, and the
normal-runtime network-denial acceptance test remains M5.2. Loopback binding
and Ollama's no-cloud switch are present now, but are not substitutes for that
later test.

Installation calls `daemon-reload`, `enable --now`, checks enabled/active state,
and requires `/api/version` to return exactly `0.33.3`. A different process or
version on the configured port cannot satisfy readiness.

## Model validation record

Provisioning pulls only the effective model obtained from the installed
`gonken-agent config show --effective --json` authority. It streams pull events,
then validates the exact tag, full digest/prefix, and quantization. The inference
smoke uses `/api/generate` with streaming disabled, temperature `0`, seed `0`,
the effective context length, eight maximum predicted tokens, and `keep_alive=0`.
It stores only timing/count metadata—never prompt or response content.

`ollama.record` binds the Ollama release/asset/checksum, binary/unit/drop-in
hashes, endpoint, model tag/full digest/prefix, model metadata, context and
parallelism policy, pull byte count, smoke metrics, time, and validation result.
The model postcondition requires this record, the live service, exact installed
files, and the local API to agree.

## Rerun and interruption behavior

Fixture tests terminate the manager before/during/after download, extraction,
binary finalization, service readiness, model pull, and inference smoke. A rerun
must converge to the exact postcondition. Partial downloads and Ollama blobs are
retained for their supported resumable behavior; unverified candidates never
become the stable executable; existing model blobs are not deleted on failure.

Development-root and failure controls require
`GONKEN_ENABLE_TEST_FAILURES=1`. Production refuses a redirected root, a local
`file://` artifact, non-AArch64 binary installation, and non-root mutations.

## Commands and current boundary

On a validated target, normal `bootstrap.sh` execution reaches M3.4, then
continues into M3.5 speech provisioning. The installer can return specifically
at this boundary with `--ollama-only` and prints `M3_4_OLLAMA_COMPLETE`.
Development hosts must use `--release-only`; they report
`M3_4_TARGET_REQUIRED` rather than contacting upstream or pretending a target
installation.

Useful target diagnostics after provisioning are:

```bash
systemctl is-enabled ollama.service
systemctl is-active ollama.service
journalctl -u ollama.service
curl http://127.0.0.1:11434/api/version
curl http://127.0.0.1:11434/api/tags
```

Do not edit managed unit files, links, immutable payloads, or the validation
record to force a pass. Resolve the reported conflict or create a reviewed
upgrade/migration decision.
