"""Configuration management for the GonKenLab agent."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent


def _project_path(*parts: str) -> str:
    """Return an absolute path inside the cloned repository."""
    return str(PROJECT_ROOT.joinpath(*parts))


@dataclass
class Config:
    """Application configuration with repository-relative defaults."""

    # Paths are derived from the actual clone location. This makes a clone at
    # /home/pi/gonkenlabagent work without embedding that path in source code.
    project_root: str = field(default_factory=lambda: str(PROJECT_ROOT))
    assets_path: str = field(default_factory=lambda: _project_path("assets", "face"))

    # Audio
    piper_voice: str = field(
        default_factory=lambda: _project_path(
            "piper", "voices", "en_GB-semaine-medium.onnx"
        )
    )
    mic_name: str = "AIRHUG"
    speaker_name: str = "AIRHUG"

    # Whisper.cpp
    whisper_path: str = field(
        default_factory=lambda: _project_path(
            "whisper.cpp", "build", "bin", "whisper-cli"
        )
    )
    whisper_model: str = field(
        default_factory=lambda: _project_path(
            "whisper.cpp", "models", "ggml-base.en-q5_0.bin"
        )
    )

    # Models
    chat_model: str = "qwen2.5:1.5b"

    # Wake word. No custom wake-word model is currently committed to this
    # repository, so WakeWordDetector falls back to openWakeWord's hey_jarvis.
    wake_word_model: str = ""
    wake_word_threshold: float = 0.5
    wake_phrase: str = "Hey Jarvis"

    # Microphone settings
    mic_sample_rate: int = 48000
    target_sample_rate: int = 16000

    # Local location default
    local_location: str = "Kingston, CA"

    # API Keys (loaded from environment)
    openweather_api_key: str = ""
    moonshot_api_key: str = ""
    newsapi_key: str = ""

    # Soul/personality files
    local_soul_path: str = field(
        default_factory=lambda: _project_path("config", "local_soul.md")
    )
    cloud_soul_path: str = field(
        default_factory=lambda: _project_path("config", "cloud_soul.md")
    )

    # Display
    display_width: int = 800
    display_height: int = 480
    use_framebuffer: bool = True

    # Features
    enable_streaming_tts: bool = False
    enable_ui: bool = False

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """Load configuration from config/config.json and environment."""
        config = cls()

        if config_path is None:
            config_path = os.path.join(config.project_root, "config", "config.json")

        if Path(config_path).exists():
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)

        # The clone location is authoritative. Never allow an old config file
        # to reintroduce a stale /home/<user>/... project root.
        config.project_root = str(PROJECT_ROOT)

        # Resolve optional relative paths against the repository root.
        for attr in (
            "assets_path",
            "piper_voice",
            "whisper_model",
            "wake_word_model",
            "local_soul_path",
            "cloud_soul_path",
        ):
            value = getattr(config, attr, "")
            if value and not Path(value).is_absolute():
                setattr(config, attr, str(PROJECT_ROOT / value))

        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            config._load_env_file(str(env_path))

        config.openweather_api_key = os.getenv(
            "OPENWEATHER_API_KEY", config.openweather_api_key
        )
        config.moonshot_api_key = os.getenv(
            "MOONSHOT_API_KEY", config.moonshot_api_key
        )
        config.newsapi_key = os.getenv(
            "NEWSAPI_KEY", config.newsapi_key
        )

        # Optional runtime overrides are convenient when USB device names vary.
        config.mic_name = os.getenv("GONKEN_MIC_NAME", config.mic_name)
        config.speaker_name = os.getenv("GONKEN_SPEAKER_NAME", config.speaker_name)

        return config

    def _load_env_file(self, path: str):
        """Load KEY=value entries from a local .env file."""
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

    def save(self, config_path: Optional[str] = None):
        """Save non-secret configuration to JSON."""
        if config_path is None:
            config_path = os.path.join(self.project_root, "config", "config.json")

        Path(config_path).parent.mkdir(parents=True, exist_ok=True)

        data = {
            k: v for k, v in self.__dict__.items()
            if not k.endswith("_api_key") and not k.endswith("_key")
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
