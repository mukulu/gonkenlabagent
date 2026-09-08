# GonKenLab Agent License and Provenance Inventory

**Inventory revision:** 1.0

**Date checked:** 2026-09-08 UTC

**Machine-readable authority:** `packaging/provenance.toml`

## Decision status

Redistribution is **not approved**. The repository has no `LICENSE` file, the
ownership/contributor authority for project source has not been attested, and
all 14 tracked PNG/WAV assets have unknown origin and license. An earlier README
ended with an unsupported “MIT” label; that label has been removed and is not a
license grant.

M2.1 therefore creates only a development package boundary. `pyproject.toml`
has no license declaration, its core dependency list is empty, and the wheel
policy excludes the legacy runtime and every tracked media asset. A local build
for validation is not an approved artifact for publication.

## Repository-owned material

| Material | Repository state | Package state | License/provenance state | Required disposition |
|---|---|---|---|---|
| `src/gonken_agent/**` | Tracked development source | Included in local wheel | Ownership not attested; `NOASSERTION` | Maintainer confirms authority and approves project license |
| Legacy Python/shell/config | Tracked source | Excluded | Ownership not attested; `NOASSERTION` | Same project-source decision before distribution |
| Development/current docs | Tracked text | Excluded from wheel | Ownership not attested; supplied-source boundaries need confirmation | Confirm author/permission and chosen documentation terms |
| Nine face PNGs | Tracked assets | Excluded | Origin and license unknown; hashes recorded individually | Prove rights or remove/replace before any portable public archive |
| Five filler WAVs | Tracked assets | Excluded | Origin, speaker/TTS source, and license unknown; hashes recorded individually | Prove rights or remove/replace before any portable public archive |

Excluding unknown media from a wheel does **not** make a ZIP containing the
entire Git repository redistributable. The Git history still contains those
objects. A public portable handoff must wait for asset disposition or use a
separately reviewed, history-filtered release process.

## Third-party facts verified from primary sources

| Component | Verified upstream terms | Current policy |
|---|---|---|
| Maintained `piper-tts` | GPL-3.0-or-later | Not a core package dependency until project-license/integration review |
| `en_GB-semaine-medium` voice | Model card identifies a CC BY-NC-SA 4.0 dataset | Not bundled; replacement or explicit noncommercial policy required |
| `whisper.cpp` | MIT | Pin source/release and retain notices in M3 |
| OpenAI Whisper weights | MIT | Download separately with checksum and notices |
| Ollama CLI/server repository | MIT | Download a pinned Linux release; review binary notices in M3 |
| Qwen 3.5 2B / Ollama quantization | Apache-2.0 | Download separately; record tag, digest, license, and Pi acceptance |
| openWakeWord code | Apache-2.0 | Extension X1 only; absent from core dependencies |
| openWakeWord bundled pretrained models | CC BY-NC-SA 4.0 | Legacy detector only; remove from release provisioning |

Primary evidence:

- <https://github.com/OHF-voice/piper1-gpl>
- <https://pypi.org/project/piper-tts/>
- <https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_GB/semaine/medium/MODEL_CARD>
- <https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE>
- <https://github.com/openai/whisper>
- <https://github.com/ollama/ollama/blob/main/LICENSE>
- <https://ollama.com/library/qwen3.5:2b-q4_K_M>
- <https://github.com/dscripka/openWakeWord>

This is an engineering inventory, not legal advice. M2.3 must verify the exact
license expression, notice obligations, ARM/Python compatibility, version, and
hash of every selected dependency and artifact rather than relying on package
names or repository-level labels alone.

## Maintainer decision required to close M2.1

The maintainer must record all of the following:

1. authority to license the project source and documentation;
2. the approved project-source and documentation license(s), or a decision not
   to redistribute;
3. whether the maintained GPL Piper integration is distributed as part of a
   combined work, isolated behind a separately reviewed process boundary, or
   replaced;
4. removal, replacement, or documented rights for each PNG/WAV asset;
5. removal or explicit policy for noncommercial voice/wake artifacts.

Until that decision is recorded in `DECISIONS.md`, M2.1 licensing acceptance is
blocked and no README, package metadata, tag, or ZIP may be called a release.
