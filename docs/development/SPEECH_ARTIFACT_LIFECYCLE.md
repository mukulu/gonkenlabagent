# M3.5 Speech Artifact Lifecycle

**Implemented milestone:** M3.5  
**Date:** 2026-09-09 UTC  
**Scope:** host-verified artifact provisioning logic for Whisper and Piper; target Pi execution remains unrun.

## What M3.5 Builds

M3.5 turns the previous blocked speech dependency policy into an explicit, repeatable target provisioning contract:

- Whisper is built from the pinned `whisper.cpp` release `v1.9.2` at commit `306c88f4d1286aec1bf96e544632897886af5501`.
- The Whisper model is `ggml-base.en-q5_1.bin` from the official whisper.cpp model repository commit `5359861c739e955e79d9a303bcbc70fb988958b1`, SHA-256 `4baf70dd0d7c4247ba2b81fafd9c01005ac77c2f9ef064e00dcf195d0e2fdd2f`.
- Piper is installed as a separate root-managed CLI virtual environment from `requirements/piper-pi-trixie-py313.lock`, not into the application release venv.
- Piper package version is `piper-tts==1.8.0`; the selected AArch64 `abi3` wheel SHA-256 is `3f60c1917de6d8e8033f395878ad3f88f6dfee88a8b05f98971a275f76a38484`.
- The old noncommercial `en_GB-semaine-medium` voice is not provisioned. M3.5 selects `en_US-ljspeech-medium` from the Piper voices repository commit `1162a9173d0ce503555aed757976b7a9912eae4c`.
- The Piper voice model/config/card are downloaded and validated as a pair before acceptance.

All artifact authorities live in `packaging/speech-artifacts.toml`. The dependency graph authority lives in `requirements/profiles.toml` and renders to `requirements/piper-pi-trixie-py313.lock`.

## Installed Layout

| Path | Owner/role | Purpose |
|---|---|---|
| `/usr/local/lib/gonken-speech/whisper/releases/v1.9.2` | root-managed immutable tree | Pinned Whisper runtime |
| `/usr/local/bin/whisper-cli` | stable entrypoint | Relative symlink to active Whisper binary |
| `/usr/local/lib/gonken-speech/piper/releases/v1.8.0` | root-managed immutable tree | Separate Piper CLI venv |
| `/usr/local/bin/piper` | stable entrypoint | Wrapper invoking the separate Piper venv |
| `/var/lib/gonken-agent/models/whisper/base.en-q5_1.bin` | root-managed model | Checked Whisper model |
| `/var/lib/gonken-agent/models/piper/en_US-ljspeech-medium/` | root-managed immutable voice directory | Checked Piper model, config and model card |
| `/var/lib/gonken-agent/install/speech.record` | private record | Content-free successful speech-smoke evidence |

`config/defaults.toml` now points to these stable paths. The installer rejects effective config drift before provisioning models or writing a successful smoke record.

## Commands

The target installer consumes the speech manager from the activated immutable release:

```bash
python3 /usr/local/lib/gonken-agent/current/maintenance/speech_manager.py whisper-status   --manifest /usr/local/lib/gonken-agent/current/maintenance/packaging/speech-artifacts.toml   --system-root /
```

Normal target bootstrap now proceeds through M3.4 and M3.5, then stops at `M3_6_UNAVAILABLE`. Use `--speech-only` to return success immediately after `M3_5_SPEECH_COMPLETE`. Use `--ollama-only` to return success at the earlier M3.4 boundary.

## Recovery Contract

`scripts/speech_manager.py` is designed around real postconditions rather than trusting advisory state:

- checksum mismatch, zero-byte files and missing model/config/card pairs are repaired by redownloading checked artifacts;
- stale candidate directories are deleted only when they are owned by the expected parent namespace;
- stable entrypoints are not overwritten if they are non-symlink administrator files;
- test-only `file://` sources and fixture binaries require `GONKEN_ENABLE_TEST_FAILURES=1` and an isolated redirected root;
- production mutation against `/` requires root;
- non-AArch64 native binaries fail closed outside the isolated fixture mode;
- smoke samples live only in a temporary cache directory and are deleted before success is recorded.

The successful `speech.record` stores hashes, versions, sample rate, frame count and required token IDs only. It does not store speech text, model output, raw audio or transcripts.

## Host Evidence

Focused pre-regression command:

```bash
bash -n scripts/install.sh scripts/ci.sh && python scripts/dependencies.py render --check && python -m py_compile scripts/speech_manager.py scripts/dependencies.py scripts/release_manager.py && python -m unittest tests.unit.test_m3_3_release_manager   tests.unit.test_m2_3_dependencies   tests.unit.test_m3_5_speech_manager   tests.integration.test_speech_lifecycle_process -v
```

Result: 32 tests passed, including dependency policy, manifest schema, binary architecture checks, wrong-native-payload repair, zero-byte/missing/corrupt artifact repair, interrupted boundaries and smoke-record failure behavior.

## Remaining Target Evidence

M3.5 host verification does not establish:

- real HTTPS download behavior on Raspberry Pi OS;
- real `whisper.cpp` build success, runtime speed or memory pressure on Pi 5 4GB;
- real Piper wheel installation and native shared-library execution on Pi;
- microphone capture, speaker playback, ALSA hotplug or acoustic quality;
- end-to-end physical PTT-to-audio behavior;
- systemd application service startup, reboot recovery or power-loss durability;
- thermal throttling, long-run stability or classroom usability.

Those remain M4/M5/M6/M9 target acceptance work, not M3.5 host failures.

## Primary Source Evidence

- `whisper.cpp` release: <https://github.com/ggml-org/whisper.cpp/releases/tag/v1.9.2>
- Whisper model artifact: <https://huggingface.co/ggerganov/whisper.cpp/blob/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-base.en-q5_1.bin>
- Maintained Piper release: <https://github.com/OHF-Voice/piper1-gpl/releases/tag/v1.8.0>
- Piper package metadata: <https://pypi.org/project/piper-tts/>
- Selected Piper voice tree: <https://huggingface.co/rhasspy/piper-voices/tree/1162a9173d0ce503555aed757976b7a9912eae4c/en/en_US/ljspeech/medium>
- Selected voice model card: <https://huggingface.co/rhasspy/piper-voices/blob/1162a9173d0ce503555aed757976b7a9912eae4c/en/en_US/ljspeech/medium/MODEL_CARD>
