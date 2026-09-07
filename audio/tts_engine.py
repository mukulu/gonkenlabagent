"""Piper TTS wrapper using repository-relative model paths."""

import os
import tempfile
import wave
from pathlib import Path
from typing import Optional

try:
    from piper import PiperVoice
    from piper.voice import SynthesisConfig
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = (
    PROJECT_ROOT / "piper" / "voices" / "en_GB-semaine-medium.onnx"
)


class PiperTTS:
    """Piper TTS engine wrapper using the piper-tts Python package."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        speaking_rate: float = 1.0,
        speaker_id: int = 0,
    ):
        resolved_model = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self.model_path = str(resolved_model)
        self.speaking_rate = speaking_rate
        self.speaker_id = speaker_id
        self._voice = None

        if not resolved_model.exists():
            raise FileNotFoundError(f"Voice model not found at {resolved_model}")

        if PIPER_AVAILABLE:
            self._voice = PiperVoice.load(str(resolved_model))
        else:
            raise RuntimeError(
                "piper-tts is not installed in the project environment. Run ./setup.sh"
            )

    def synthesize(self, text: str, output_path: Optional[str] = None) -> str:
        """Synthesize text to a WAV file and return the WAV path."""
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

        syn_config = SynthesisConfig(speaker_id=self.speaker_id)
        with wave.open(output_path, "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file, syn_config=syn_config)

        return output_path

    def synthesize_to_audio(self, text: str):
        """Synthesize text directly to raw PCM bytes and sample rate."""
        audio_parts = []
        syn_config = SynthesisConfig(speaker_id=self.speaker_id)
        for chunk in self._voice.synthesize(text, syn_config=syn_config):
            audio_parts.append(chunk.audio_int16_bytes)

        audio_bytes = b"".join(audio_parts)
        sample_rate = self._voice.config.sample_rate
        return audio_bytes, sample_rate
