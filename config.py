"""Compatibility view over the packaged configuration authority.

The pre-package runtime imports this module. It does not read legacy JSON or
``.env``; those files are accepted only by ``gonken-agent config migrate``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gonken_agent.config import Config as PackageConfig
from gonken_agent.config import ConfigError, load_config


PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class Config:
    """Flattened adapter retained only for the source compatibility runtime."""

    effective: PackageConfig

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        if config_path and Path(config_path).suffix.lower() == ".json":
            raise ConfigError(
                "legacy JSON is a migration input; run `gonken-agent config migrate`"
            )
        load_arguments = {"site_path": Path(config_path)} if config_path else {}
        initial = load_config(**load_arguments)
        paths = initial.config.paths
        candidates = {
            "paths.assets_dir": PROJECT_ROOT / "assets" / Path(paths.assets_dir).name,
            "paths.whisper_binary": (
                PROJECT_ROOT / "whisper.cpp" / "build" / "bin"
                / Path(paths.whisper_binary).name
            ),
            "paths.whisper_model": (
                PROJECT_ROOT / "whisper.cpp" / "models" / Path(paths.whisper_model).name
            ),
            "paths.piper_voice": (
                PROJECT_ROOT / "piper" / "voices" / Path(paths.piper_voice).name
            ),
            "paths.local_prompt": PROJECT_ROOT / "config" / Path(paths.local_prompt).name,
        }
        checkout_paths = {
            dotted: str(candidate)
            for dotted, candidate in candidates.items()
            if initial.sources[dotted] == "defaults"
        }
        loaded = load_config(**load_arguments, cli_overrides=checkout_paths)
        return cls(loaded.config)

    @property
    def project_root(self) -> str:
        return str(PROJECT_ROOT)

    @property
    def assets_path(self) -> str:
        return self.effective.paths.assets_dir

    @property
    def piper_voice(self) -> str:
        return self.effective.paths.piper_voice

    @property
    def mic_name(self) -> str:
        return self.effective.audio.input_match

    @property
    def speaker_name(self) -> str:
        return self.effective.audio.output_match

    @property
    def whisper_path(self) -> str:
        return self.effective.paths.whisper_binary

    @property
    def whisper_model(self) -> str:
        return self.effective.paths.whisper_model

    @property
    def chat_model(self) -> str:
        return self.effective.llm.model

    @property
    def ollama_base_url(self) -> str:
        return self.effective.llm.base_url

    @property
    def max_output_tokens(self) -> int:
        return self.effective.llm.max_output_tokens

    @property
    def keep_alive(self) -> str:
        return self.effective.llm.keep_alive

    @property
    def wake_word_model(self) -> str:
        return self.effective.extensions.wake_word.model

    @property
    def wake_word_threshold(self) -> float:
        return self.effective.extensions.wake_word.threshold

    @property
    def wake_phrase(self) -> str:
        return self.effective.extensions.wake_word.phrase

    @property
    def mic_sample_rate(self) -> int:
        return self.effective.audio.capture_rate

    @property
    def target_sample_rate(self) -> int:
        return self.effective.audio.processing_rate

    @property
    def language(self) -> str:
        return self.effective.assistant.language

    @property
    def stt_threads(self) -> int:
        return self.effective.stt.threads

    @property
    def local_location(self) -> str:
        return ""

    @property
    def openweather_api_key(self) -> str:
        return ""

    @property
    def moonshot_api_key(self) -> str:
        return ""

    @property
    def newsapi_key(self) -> str:
        return ""

    @property
    def local_soul_path(self) -> str:
        return self.effective.paths.local_prompt

    @property
    def cloud_soul_path(self) -> str:
        return ""

    @property
    def display_width(self) -> int:
        return 0

    @property
    def display_height(self) -> int:
        return 0

    @property
    def use_framebuffer(self) -> bool:
        return False

    @property
    def enable_streaming_tts(self) -> bool:
        return False

    @property
    def enable_ui(self) -> bool:
        return False
