#!/usr/bin/env python3
"""Post-install software and optional hardware smoke tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import sounddevice as sd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from audio.audio_manager import AudioManager  # noqa: E402
from audio.stt_engine import WhisperSTT  # noqa: E402
from audio.tts_engine import PiperTTS  # noqa: E402
from config import Config  # noqa: E402


def find_audio_matches(config: Config):
    try:
        devices = sd.query_devices()
    except Exception as exc:
        print(f"[WARN] Could not enumerate audio devices: {exc}")
        return [], [], []

    available = [
        (i, d["name"], int(d["max_input_channels"]), int(d["max_output_channels"]))
        for i, d in enumerate(devices)
    ]
    mic = [
        i for i, d in enumerate(devices)
        if config.mic_name.lower() in d["name"].lower() and d["max_input_channels"] > 0
    ]
    speaker = [
        i for i, d in enumerate(devices)
        if config.speaker_name.lower() in d["name"].lower() and d["max_output_channels"] > 0
    ]
    return mic, speaker, available


def check_whisper(config: Config) -> None:
    print("[TEST] Running deterministic Whisper transcription …")
    sample = PROJECT_ROOT / "whisper.cpp" / "samples" / "jfk.wav"
    if not sample.is_file():
        raise FileNotFoundError(f"Whisper sample is missing: {sample}")

    stt = WhisperSTT(
        whisper_path=config.whisper_path,
        model_path=config.whisper_model,
        language=config.language,
        threads=2,
        timeout=120,
    )
    text = stt.transcribe(str(sample)).strip()
    if not text:
        raise RuntimeError("Whisper completed but returned an empty transcription")
    print(f"[PASS] Whisper transcription: {text[:120]}")


def synthesize_confirmation(config: Config) -> str:
    print("[TEST] Synthesizing Piper confirmation …")
    tts = PiperTTS(model_path=config.piper_voice)
    wav_path = tts.synthesize(
        "GonKenLab Agent setup is complete. "
        "The local speech software is ready."
    )
    if not Path(wav_path).is_file() or Path(wav_path).stat().st_size == 0:
        raise RuntimeError("Piper returned an empty output file")
    print("[PASS] Piper synthesized a non-empty WAV file")
    return wav_path


def check_microphone(device_index: int, config: Config) -> None:
    print("[TEST] Opening microphone …")
    with sd.InputStream(
        device=device_index,
        samplerate=config.mic_sample_rate,
        channels=1,
        dtype="int16",
        blocksize=1024,
        latency="high",
    ) as stream:
        data, _overflowed = stream.read(1024)
    if data is None or len(data) == 0:
        raise RuntimeError("Microphone opened but returned no samples")
    print("[PASS] Microphone stream opened and returned audio samples")


def main() -> int:
    config = Config.load()
    print("GonKenLab Agent post-install smoke test")
    print(f"Repository: {PROJECT_ROOT}")

    # Software tests do not depend on USB audio being connected.
    check_whisper(config)
    wav_path = synthesize_confirmation(config)

    try:
        mic_matches, speaker_matches, available = find_audio_matches(config)
        if not mic_matches or not speaker_matches:
            print("[WARN] Required software passed, but configured audio hardware is incomplete.")
            print(f"[WARN] Available audio devices: {available}")
            print(
                "[WARN] Connect the USB audio device or set "
                "GONKEN_AUDIO_INPUT_MATCH and GONKEN_AUDIO_OUTPUT_MATCH, "
                "then rerun this test."
            )
            return 0

        check_microphone(mic_matches[0], config)
        audio = AudioManager(
            sample_rate=config.target_sample_rate,
            mic_sample_rate=config.mic_sample_rate,
            mic_name=config.mic_name,
            speaker_name=config.speaker_name,
        )
        print("[TEST] Playing Piper confirmation through configured speaker …")
        audio.play_wav(wav_path)
        print("[PASS] Speaker playback completed")
    finally:
        try:
            os.unlink(wav_path)
        except FileNotFoundError:
            pass

    print()
    print("All software and available-hardware smoke tests passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] Smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
