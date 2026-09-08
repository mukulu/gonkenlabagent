"""Whisper.cpp STT wrapper using repository-relative model paths."""

import os
import subprocess
import tempfile
from pathlib import Path


def _validate_whisper_executable(path: Path, timeout: int = 15) -> None:
    """Verify that whisper-cli can actually start, not merely that it exists."""
    if not path.is_file():
        raise FileNotFoundError(f"Whisper not found at {path}")
    if not os.access(path, os.X_OK):
        raise PermissionError(f"Whisper is not executable: {path}")

    try:
        process = subprocess.run(
            [str(path), "-h"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Whisper startup timed out after {timeout}s: {path}") from exc

    if process.returncode != 0:
        detail = (process.stderr or process.stdout).strip()
        raise RuntimeError(
            f"Whisper executable cannot start: {detail or f'exit {process.returncode}'}. "
            "Run ./setup.sh to repair the whisper.cpp build."
        )


class WhisperSTT:
    """Whisper.cpp speech-to-text engine."""

    def __init__(
        self,
        whisper_path: str,
        model_path: str,
        language: str,
        threads: int,
        timeout: int = 120,
    ):
        requested_whisper = Path(whisper_path)
        requested_model = Path(model_path)

        if not requested_whisper.exists():
            raise FileNotFoundError(f"Whisper not found at {requested_whisper}")

        if not requested_model.exists():
            raise FileNotFoundError(f"Model not found at {requested_model}")

        _validate_whisper_executable(requested_whisper)

        self.whisper_path = str(requested_whisper)
        self.model_path = str(requested_model)
        self.language = language
        self.threads = threads
        self.timeout = timeout

    def transcribe(self, audio_path: str) -> str:
        """Transcribe a 16 kHz mono WAV file to text."""
        try:
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
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Whisper transcription timed out after {self.timeout}s"
            ) from exc

        if process.returncode != 0:
            detail = (process.stderr or process.stdout).strip()
            raise RuntimeError(f"Whisper failed: {detail or f'exit {process.returncode}'}")

        return process.stdout.strip().replace("[BLANK_AUDIO]", "").strip()

    def transcribe_audio_array(self, audio, sample_rate: int) -> str:
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
