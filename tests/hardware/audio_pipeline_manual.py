#!/usr/bin/env python3
"""Explicit microphone -> Whisper -> Piper -> speaker compatibility probe."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require_opt_in() -> bool:
    if os.environ.get("GONKEN_RUN_HARDWARE_TESTS") == "1":
        return True
    print(
        "Hardware audio probe disabled. Read tests/hardware/README.md and set "
        "GONKEN_RUN_HARDWARE_TESTS=1 only with intentional physical supervision."
    )
    return False


def require_project_venv() -> None:
    expected = (ROOT / ".venv").resolve()
    active = Path(sys.prefix).resolve()
    if active != expected:
        raise RuntimeError(f"Wrong Python environment: {active}. Use .venv/bin/python")


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
    return audio, stt, PiperTTS(model_path=config.piper_voice)


def exercise_tts(audio, tts) -> bool:
    print("Testing TTS and speaker...")
    path = None
    try:
        path = tts.synthesize("GonKenLab Agent audio output is working.")
        audio.play_wav(path)
        return True
    except Exception as exc:
        print(f"TTS and speaker failed: {exc}", file=sys.stderr)
        return False
    finally:
        if path:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


def exercise_stt(audio, stt) -> bool:
    print("Speak now; recording stops after silence or ten seconds.")
    try:
        recording = audio.record_until_silence(max_duration=10.0)
        if recording is None or len(recording) == 0:
            raise RuntimeError("no audio recorded")
        text = stt.transcribe_audio_array(
            recording, sample_rate=audio.sample_rate
        ).strip()
        if not text:
            raise RuntimeError("Whisper returned an empty transcription")
        print(f"Transcribed: {text}")
        return True
    except Exception as exc:
        print(f"Microphone and STT failed: {exc}", file=sys.stderr)
        return False


def exercise_round_trip(audio, stt, tts) -> bool:
    print("Say something; the compatibility runtime will repeat it.")
    path = None
    try:
        recording = audio.record_until_silence(max_duration=10.0)
        if recording is None or len(recording) == 0:
            raise RuntimeError("no audio recorded")
        text = stt.transcribe_audio_array(
            recording, sample_rate=audio.sample_rate
        ).strip()
        if not text:
            raise RuntimeError("Whisper returned an empty transcription")
        path = tts.synthesize(f"You said: {text}")
        audio.play_wav(path)
        return True
    except Exception as exc:
        print(f"Round trip failed: {exc}", file=sys.stderr)
        return False
    finally:
        if path:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


def main() -> int:
    if not require_opt_in():
        return 2
    require_project_venv()
    sys.path.insert(0, str(ROOT))
    from config import Config

    try:
        components = make_components(Config.load())
    except Exception as exc:
        print(f"Component initialization failed: {exc}", file=sys.stderr)
        return 1
    audio, stt, tts = components
    results = [
        ("TTS and speaker", exercise_tts(audio, tts)),
        ("Microphone and STT", exercise_stt(audio, stt)),
        ("Round trip", exercise_round_trip(audio, stt, tts)),
    ]
    for name, passed in results:
        print(f"{'PASS' if passed else 'FAIL'}: {name}")
    return 0 if all(passed for _, passed in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
