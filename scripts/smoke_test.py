#!/usr/bin/env python3
"""End-to-end post-install smoke test for GonKenLab Agent."""

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


def check_microphone(audio: AudioManager, config: Config) -> None:
    """Open the configured microphone and read a short frame."""
    print("[TEST] Opening microphone …")
    with sd.InputStream(
        device=audio.mic_device,
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


def check_whisper(config: Config) -> None:
    """Transcribe the small sample bundled with whisper.cpp."""
    print("[TEST] Running Whisper transcription …")
    sample = PROJECT_ROOT / "whisper.cpp" / "samples" / "jfk.wav"
    if not sample.is_file():
        raise FileNotFoundError(f"Whisper sample is missing: {sample}")

    stt = WhisperSTT(
        whisper_path=config.whisper_path,
        model_path=config.whisper_model,
        threads=2,
    )
    text = stt.transcribe(str(sample)).strip()
    if not text:
        raise RuntimeError("Whisper completed but returned an empty transcription")
    print(f"[PASS] Whisper transcription: {text[:120]}")


def check_tts_and_speaker(audio: AudioManager, config: Config) -> None:
    """Generate a local TTS message and play it through the configured speaker."""
    print("[TEST] Synthesizing and playing confirmation message …")
    tts = PiperTTS(model_path=config.piper_voice)
    wav_path = tts.synthesize(
        "GonKenLab Agent setup is complete. "
        "Your microphone and speaker are ready. "
        "Start the assistant and say Hey Jarvis."
    )
    try:
        audio.play_wav(wav_path)
    finally:
        try:
            os.unlink(wav_path)
        except FileNotFoundError:
            pass
    print("[PASS] Piper TTS and speaker playback completed")


def main() -> int:
    config = Config.load()
    print("GonKenLab Agent hardware/audio smoke test")
    print(f"Repository: {PROJECT_ROOT}")

    audio = AudioManager(
        sample_rate=config.target_sample_rate,
        mic_sample_rate=config.mic_sample_rate,
        mic_name=config.mic_name,
        speaker_name=config.speaker_name,
    )

    check_microphone(audio, config)
    check_whisper(config)
    check_tts_and_speaker(audio, config)

    print()
    print("All post-install smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
