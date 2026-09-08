#!/usr/bin/env python3
"""Interactive microphone -> Whisper -> Piper -> speaker test."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

def require_project_venv() -> None:
    expected = (PROJECT_ROOT / ".venv").resolve()
    active = Path(sys.prefix).resolve()
    if active != expected:
        raise RuntimeError(
            f"Wrong Python environment: {active}. Use: "
            ".venv/bin/python tests/test_audio_pipeline.py"
        )


def make_components(config):
    from audio.audio_manager import AudioManager
    from audio.stt_engine import WhisperSTT
    from audio.tts_engine import PiperTTS

    audio = AudioManager(
        sample_rate=config.target_sample_rate,
        mic_sample_rate=config.mic_sample_rate,
        mic_name=config.mic_name,
        speaker_name=config.speaker_name,
    )
    stt = WhisperSTT(
        whisper_path=config.whisper_path,
        model_path=config.whisper_model,
        language=config.language,
        threads=config.stt_threads,
        timeout=120,
    )
    tts = PiperTTS(model_path=config.piper_voice)
    return audio, stt, tts


def test_tts(audio, tts) -> bool:
    print("Testing TTS + speaker...")
    audio_path = None
    try:
        audio_path = tts.synthesize("Hello. GonKenLab Agent audio output is working.")
        audio.play_wav(audio_path)
        print("✓ TTS + speaker working")
        return True
    except Exception as exc:
        print(f"✗ TTS + speaker failed: {exc}")
        return False
    finally:
        if audio_path:
            try:
                os.unlink(audio_path)
            except FileNotFoundError:
                pass


def test_stt(audio, stt) -> bool:
    print("\nTesting microphone + STT...")
    print("Speak now... (recording for at most 10 seconds)")
    try:
        recording = audio.record_until_silence(max_duration=10.0)
        if recording is None or len(recording) == 0:
            raise RuntimeError("No audio recorded")
        text = stt.transcribe_audio_array(recording, sample_rate=audio.sample_rate).strip()
        if not text:
            raise RuntimeError("Whisper returned an empty transcription")
        print(f"✓ Transcribed: {text}")
        return True
    except Exception as exc:
        print(f"✗ Microphone + STT failed: {exc}")
        return False


def test_round_trip(audio, stt, tts) -> bool:
    print("\nTesting round-trip...")
    print("Say something; it will be repeated back. Maximum recording time: 10 seconds.")
    audio_path = None
    try:
        recording = audio.record_until_silence(max_duration=10.0)
        if recording is None or len(recording) == 0:
            raise RuntimeError("No audio recorded")
        text = stt.transcribe_audio_array(recording, sample_rate=audio.sample_rate).strip()
        if not text:
            raise RuntimeError("Whisper returned an empty transcription")
        print(f"You said: {text}")
        audio_path = tts.synthesize(f"You said: {text}")
        audio.play_wav(audio_path)
        print("✓ Round-trip complete")
        return True
    except Exception as exc:
        print(f"✗ Round-trip failed: {exc}")
        return False
    finally:
        if audio_path:
            try:
                os.unlink(audio_path)
            except FileNotFoundError:
                pass


def main() -> int:
    require_project_venv()
    from config import Config

    config = Config.load()
    try:
        audio, stt, tts = make_components(config)
    except Exception as exc:
        print(f"Component initialization failed: {exc}")
        return 1

    results = [
        ("TTS + speaker", test_tts(audio, tts)),
        ("Microphone + STT", test_stt(audio, stt)),
        ("Round-trip", test_round_trip(audio, stt, tts)),
    ]

    print("\n" + "=" * 40)
    print("Results:")
    for name, passed in results:
        print(f"  {name}: {'✓ PASS' if passed else '✗ FAIL'}")
    return 0 if all(passed for _, passed in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
