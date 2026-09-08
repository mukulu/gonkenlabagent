# GonKenLab Agent License and Provenance Inventory

**Inventory revision:** 1.2

**Date checked:** 2026-09-08 UTC

**Machine-readable authority:** `packaging/provenance.toml`

## Decision status

The current policy is deliberately **no redistribution**. No project license is
granted, no `LICENSE` file exists, and package metadata contains no license
claim. The project may continue as a private engineering workstream, but no
source package, wheel, public repository export, or full-history ZIP is an
approved release. A future license requires a new explicit maintainer decision.

Ownership/contributor authority for project source has not been attested, and
all 14 tracked PNG/WAV assets have unknown origin and license. An earlier README
ended with an unsupported “MIT” label; that label was removed and is not a
license grant.

M2.1 therefore closes under an intentionally unlicensed, no-redistribution
policy. M2.3 keeps `pyproject.toml`'s core dependency list empty, exposes pygame
only as an optional extra, and keeps the wheel policy excluding the legacy
runtime and every tracked media asset. A local build is validation evidence
only.

## Repository-owned material

| Material | Repository state | Package state | License/provenance state | Required disposition |
|---|---|---|---|---|
| `src/gonken_agent/**` | Tracked development source | Included in local wheel | Ownership not attested; `NOASSERTION` | Private development only; no redistribution |
| Legacy Python/shell/config | Tracked source | Excluded | Ownership not attested; `NOASSERTION` | Private compatibility evidence only |
| Development/current docs | Tracked text | Excluded from wheel | Ownership not attested; supplied-source boundaries need confirmation | Private development only; no redistribution |
| Nine face PNGs | Tracked assets | Excluded | Origin and license unknown; hashes recorded individually | Quarantined internal compatibility evidence; never package/release/public-export content |
| Five filler WAVs | Tracked assets | Excluded | Origin, speaker/TTS source, and license unknown; hashes recorded individually | Quarantined internal compatibility evidence; never package/release/public-export content |

Excluding unknown media from a wheel does **not** make a ZIP containing the
entire Git repository redistributable. The Git history still contains those
objects. Portable checkpoints may be created only as private engineering
handoffs. Any future public export must prove rights, remove/replace the assets,
and use a separately reviewed history-filtered release process where necessary.

## Third-party facts verified from primary sources

| Component | Verified upstream terms | Current policy |
|---|---|---|
| Maintained `piper-tts` | GPL-3.0-or-later | Internal evaluation only; not a declared/bundled dependency; future release requires compatibility review |
| `en_GB-semaine-medium` voice | Model card identifies a CC BY-NC-SA 4.0 dataset | Legacy internal evaluation only; excluded from packages, releases, and public exports |
| `whisper.cpp` | MIT | Pin source/release and retain notices in M3 |
| OpenAI Whisper weights | MIT | Download separately with checksum and notices |
| Ollama CLI/server repository | MIT | Download a pinned Linux release; review binary notices in M3 |
| Qwen 3.5 2B / Ollama quantization | Apache-2.0 | Download separately; record tag, digest, license, and Pi acceptance |
| openWakeWord code | Apache-2.0 | Extension X1 only; absent from core dependencies |
| openWakeWord bundled pretrained models | CC BY-NC-SA 4.0 | Legacy internal evaluation only; excluded from core and release provisioning |
| `pygame` 2.6.1 | LGPL-2.1-or-later; PyPI publishes exact CPython 3.12/x86_64 and CPython 3.13/AArch64 wheels | Optional UI profile only; absent from headless core and no tracked media is bundled through it |

Primary evidence:

- <https://github.com/OHF-voice/piper1-gpl>
- <https://pypi.org/project/piper-tts/>
- <https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_GB/semaine/medium/MODEL_CARD>
- <https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE>
- <https://github.com/openai/whisper>
- <https://github.com/ollama/ollama/blob/main/LICENSE>
- <https://ollama.com/library/qwen3.5:2b-q4_K_M>
- <https://github.com/dscripka/openWakeWord>
- <https://pypi.org/project/pygame/2.6.1/>

This is an engineering inventory, not legal advice. M2.3 records the exact
version, wheel filenames, PyPI SHA-256 values, and license expression for its
only selected third-party package, optional pygame. Core and development locks
are exactly empty because the maintained runtime is not implemented. Future
dependency selection must still verify notice obligations, transitive metadata,
ARM/Python compatibility, versions, and hashes rather than relying on package
names or repository-level labels alone.

The blocked wake profile has no lock: openWakeWord 0.6.0 asks pip to install
both ONNX Runtime and `tflite-runtime` on Linux, while the legacy installer
bypasses dependency metadata with `--no-deps`. That workaround is explicitly
unaccepted. The future TTS profile likewise has no lock until the GPL package
integration and a release-compatible voice are selected and tested.

## M2.1 disposition and future release gate

M2.1 is complete under the conservative no-redistribution policy recorded in
`DECISIONS.md`. The following remain release blockers rather than M2.2 blockers:

1. authority to license the project source and documentation;
2. approved project-source and documentation license(s);
3. whether the maintained GPL Piper integration is distributed as part of a
   combined work, isolated behind a separately reviewed process boundary, or
   replaced;
4. removal, replacement, or documented rights for each PNG/WAV asset;
5. removal or explicit policy for noncommercial voice/wake artifacts.

Until all five are resolved, redistribution remains prohibited and no README,
package metadata, tag, wheel, repository export, or ZIP may be called a public
release. This restriction does not authorize later milestones to weaken or
silently remove the gate.
