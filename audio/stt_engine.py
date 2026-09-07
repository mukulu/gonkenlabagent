"""Whisper.cpp STT wrapper using repository-relative model paths."""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WHISPER_PATH = (
    PROJECT_ROOT / "whisper.cpp" / "build" / "bin" / "whisper-cli"
)
DEFAULT_MODEL_PATH = (
    PROJECT_ROOT / "whisper.cpp" / "models" / "ggml-base.en-q5_1.bin"
)


class WhisperSTT:
    """Whisper.cpp speech-to-text engine."""

    def __init__(
        self,
        whisper_path: Optional[str] = None,
        model_path: Optional[str] = None,
        language: str = "en",
        threads: int = 4,
    ):
        requested_whisper = Path(whisper_path) if whisper_path else DEFAULT_WHISPER_PATH
        requested_model = Path(model_path) if model_path else DEFAULT_MODEL_PATH

        self.whisper_path = str(requested_whisper)
        self.model_path = str(requested_model)
        self.language = language
        self.threads = threads

        if not requested_whisper.exists():
            alt_paths = [
                Path("/usr/local/bin/whisper-cpp"),
                PROJECT_ROOT / "whisper.cpp" / "main",
            ]
            for alt in alt_paths:
                if alt.exists():
                    self.whisper_path = str(alt)
                    break
            else:
                raise FileNotFoundError(f"Whisper not found at {requested_whisper}")

        if not requested_model.exists():
            raise FileNotFoundError(f"Model not found at {requested_model}")

    def transcribe(self, audio_path: str) -> str:
        """Transcribe a 16 kHz mono WAV file to text."""
        process = subprocess.run(
            [
                self.whisper_path,
                "-m", self.model_path,
                "-f", audio_path,
                "-l", self.language,
                "-t", str(self.threads),
                "--no-timestamps",
                "-np",
            ],
            capture_output=True,
            text=True,
        )

        if process.returncode != 0:
            raise RuntimeError(f"Whisper failed: {process.stderr}")

        return process.stdout.strip().replace("[BLANK_AUDIO]", "").strip()

    def transcribe_audio_array(self, audio, sample_rate: int = 16000) -> str:
        """Transcribe a NumPy audio array."""
        import wave

        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        try:
            with wave.open(temp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio.tobytes())

            return self.transcribe(temp_path)
        finally:
            os.unlink(temp_path)
