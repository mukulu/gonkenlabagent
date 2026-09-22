"""Typed, dependency-free configuration authority.

Source-controlled defaults live only in ``config/defaults.toml``.  The loader
applies site TOML, explicit environment values, and one-shot CLI values in that
order while retaining source attribution for every effective field.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import shutil
import sysconfig
import tempfile
import tomllib
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path, PurePath
from typing import Any, Mapping, get_type_hints
from urllib.parse import urlsplit

from .identity import IDENTITY


SCHEMA_VERSION = 2
DEFAULT_SITE_PATH = Path("/etc/gonken-agent/config.toml")
SOURCE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DEFAULTS_PATH = SOURCE_ROOT / "config" / "defaults.toml"
INSTALLED_DEFAULTS_PATH = (
    Path(sysconfig.get_path("data")) / "share" / "gonken-agent" / "defaults.toml"
)
REDACTED = "<redacted>"


class ConfigError(ValueError):
    """Configuration is missing, malformed, unsafe, or unsupported."""


@dataclass(frozen=True, slots=True)
class AssistantConfig:
    name: str
    language: str


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    mode: str
    interaction_mode: str


@dataclass(frozen=True, slots=True)
class LlmConfig:
    provider: str
    base_url: str
    model: str
    context_tokens: int
    max_output_tokens: int
    keep_alive: str


@dataclass(frozen=True, slots=True)
class AudioConfig:
    input_match: str
    output_match: str
    capture_rate: int
    processing_rate: int
    speech_endpointing: bool
    speech_end_silence_ms: int
    speech_energy_threshold: int


@dataclass(frozen=True, slots=True)
class SttConfig:
    model: str
    threads: int


@dataclass(frozen=True, slots=True)
class TtsConfig:
    voice: str


@dataclass(frozen=True, slots=True)
class InteractionConfig:
    push_to_talk_gpio: int
    recording_led_gpio: int


@dataclass(frozen=True, slots=True)
class RetrievalConfig:
    enabled: bool
    top_k: int


@dataclass(frozen=True, slots=True)
class PrivacyConfig:
    raw_audio_retention: str
    interaction_logging: bool
    telemetry_content: bool
    dashboard_transient_content: bool


@dataclass(frozen=True, slots=True)
class DashboardConfig:
    enabled: bool
    bind: str
    port: int


@dataclass(frozen=True, slots=True)
class PathsConfig:
    assets_dir: str
    state_dir: str
    cache_dir: str
    runtime_dir: str
    corpus_dir: str
    whisper_binary: str
    whisper_model: str
    piper_voice: str
    local_prompt: str


@dataclass(frozen=True, slots=True)
class WakeWordConfig:
    enabled: bool
    phrase: str
    model: str
    threshold: float
    monitoring_led_gpio: int
    backend: str = "streaming"
    keyword_threshold: float = 1e-20


@dataclass(frozen=True, slots=True)
class VoicePowerConfig:
    enabled: bool


@dataclass(frozen=True, slots=True)
class EnvironmentConfig:
    enabled: bool
    sensor_backend: str
    i2c_bus: int
    i2c_address: int
    sensor_repeatability: str
    poll_interval_seconds: float
    stale_after_seconds: float
    valid_samples_to_recover: int
    relay_backend: str
    relay_bcm: int
    relay_active_high: bool
    safe_state: str
    socket_path: str
    policy_path: str
    temperature_policy_min_c: float
    temperature_policy_max_c: float
    minimum_hysteresis_c: float
    maximum_hysteresis_c: float
    minimum_dwell_seconds: int
    maximum_dwell_seconds: int
    simulation_runtime_control_enabled: bool
    simulation_event_history_limit: int


@dataclass(frozen=True, slots=True)
class ExtensionsConfig:
    wake_word: WakeWordConfig
    voice_power: VoicePowerConfig
    environment: EnvironmentConfig


@dataclass(frozen=True, slots=True)
class Config:
    schema_version: int
    assistant: AssistantConfig
    runtime: RuntimeConfig
    llm: LlmConfig
    audio: AudioConfig
    stt: SttConfig
    tts: TtsConfig
    interaction: InteractionConfig
    retrieval: RetrievalConfig
    privacy: PrivacyConfig
    dashboard: DashboardConfig
    paths: PathsConfig
    extensions: ExtensionsConfig


SECTION_TYPES = {
    "assistant": AssistantConfig,
    "runtime": RuntimeConfig,
    "llm": LlmConfig,
    "audio": AudioConfig,
    "stt": SttConfig,
    "tts": TtsConfig,
    "interaction": InteractionConfig,
    "retrieval": RetrievalConfig,
    "privacy": PrivacyConfig,
    "dashboard": DashboardConfig,
    "paths": PathsConfig,
}
EXTENSION_TYPES = {
    "wake_word": WakeWordConfig,
    "voice_power": VoicePowerConfig,
    "environment": EnvironmentConfig,
}
ENVIRONMENT_STATIC_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "sensor_backend": "sht31",
    "i2c_bus": 1,
    "i2c_address": 0x44,
    "sensor_repeatability": "high",
    "poll_interval_seconds": 2.0,
    "stale_after_seconds": 10.0,
    "valid_samples_to_recover": 3,
    "relay_backend": "libgpiod",
    "relay_bcm": 23,
    "relay_active_high": True,
    "safe_state": "off",
    "socket_path": "/run/gonken-environment/control.sock",
    "policy_path": "/var/lib/gonken-environment/policy.json",
    "temperature_policy_min_c": -10.0,
    "temperature_policy_max_c": 60.0,
    "minimum_hysteresis_c": 0.5,
    "maximum_hysteresis_c": 15.0,
    "minimum_dwell_seconds": 5,
    "maximum_dwell_seconds": 3600,
    "simulation_runtime_control_enabled": False,
    "simulation_event_history_limit": 128,
}
PATH_FIELDS = {f"paths.{field.name}" for field in fields(PathsConfig)} | {
    "extensions.wake_word.model",
    "extensions.environment.socket_path",
    "extensions.environment.policy_path",
}
ENV_FIELDS: dict[str, str] = {
    "GONKEN_" + dotted.upper().replace(".", "_"): dotted
    for dotted in (
        ["schema_version"]
        + [
            f"{section}.{field.name}"
            for section, section_type in SECTION_TYPES.items()
            for field in fields(section_type)
        ]
        + [
            f"extensions.{extension}.{field.name}"
            for extension, extension_type in EXTENSION_TYPES.items()
            for field in fields(extension_type)
        ]
    )
}


@dataclass(frozen=True, slots=True)
class EffectiveConfig:
    config: Config
    sources: Mapping[str, str]

    def as_dict(self, *, redact: bool = True) -> dict[str, Any]:
        payload = asdict(self.config)
        if redact:
            for dotted in PATH_FIELDS:
                if _get_dotted(payload, dotted):
                    _set_dotted(payload, dotted, REDACTED)
        return payload

    def source_dict(self) -> dict[str, Any]:
        nested: dict[str, Any] = {}
        for dotted, source in self.sources.items():
            _set_dotted(nested, dotted, source)
        return nested


@dataclass(frozen=True, slots=True)
class MigrationResult:
    output: Path
    backups: tuple[Path, ...]
    changed: bool
    ignored: tuple[str, ...]


def default_config_path() -> Path:
    """Find the single defaults artifact in a checkout or installed wheel."""

    if SOURCE_DEFAULTS_PATH.is_file():
        return SOURCE_DEFAULTS_PATH
    if INSTALLED_DEFAULTS_PATH.is_file():
        return INSTALLED_DEFAULTS_PATH
    raise ConfigError(
        "packaged defaults.toml not found at "
        f"{SOURCE_DEFAULTS_PATH} or {INSTALLED_DEFAULTS_PATH}"
    )


def load_config(
    *,
    defaults_path: Path | str | None = None,
    site_path: Path | str | None = DEFAULT_SITE_PATH,
    environ: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
) -> EffectiveConfig:
    """Load, merge, validate, and attribute effective configuration."""

    selected_defaults = Path(defaults_path) if defaults_path else default_config_path()
    raw = _upgrade_full_schema(_read_toml(selected_defaults, "defaults"), "defaults")
    _validate_shape(raw)
    sources = {dotted: "defaults" for dotted in _leaf_paths(raw)}

    if site_path is not None:
        selected_site = Path(site_path)
        if selected_site.exists():
            site = _upgrade_override_schema(_read_toml(selected_site, "site config"), "site config")
            _validate_override_shape(site)
            _merge(raw, site)
            for dotted in _leaf_paths(site):
                sources[dotted] = "site"

    environment = os.environ if environ is None else environ
    for variable, dotted in ENV_FIELDS.items():
        if variable in environment:
            value = _parse_scalar(environment[variable], _expected_type(dotted), variable)
            _set_dotted(raw, dotted, value)
            sources[dotted] = f"env:{variable}"

    for dotted, value in (cli_overrides or {}).items():
        expected = _expected_type(dotted)
        if isinstance(value, str):
            value = _parse_scalar(value, expected, f"CLI {dotted}")
        _require_type(dotted, value, expected)
        _set_dotted(raw, dotted, value)
        sources[dotted] = f"cli:{dotted}"

    config = _construct(raw)
    _validate_values(config)
    return EffectiveConfig(config=config, sources=dict(sorted(sources.items())))


def parse_cli_overrides(values: list[str]) -> dict[str, str]:
    """Parse repeated ``SECTION.FIELD=VALUE`` one-shot overrides."""

    result: dict[str, str] = {}
    for item in values:
        dotted, separator, value = item.partition("=")
        if not separator or not dotted:
            raise ConfigError(f"invalid --set value {item!r}; expected SECTION.FIELD=VALUE")
        _expected_type(dotted)
        result[dotted] = value
    return result


def migrate_legacy(
    *,
    legacy_json: Path | str | None,
    legacy_env: Path | str | None,
    output: Path | str,
    defaults_path: Path | str | None = None,
    backup_dir: Path | str | None = None,
) -> MigrationResult:
    """Stage and validate a non-destructive, repeatable legacy migration."""

    output_path = Path(output)
    defaults = Path(defaults_path) if defaults_path else default_config_path()
    overrides: dict[str, Any] = {}
    ignored: list[str] = []
    inputs: list[Path] = []

    if legacy_json is not None and Path(legacy_json).exists():
        json_path = Path(legacy_json)
        inputs.append(json_path)
        try:
            legacy = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"cannot read legacy JSON {json_path}: {exc}") from exc
        if not isinstance(legacy, dict):
            raise ConfigError("legacy JSON root must be an object")
        _migrate_json_values(legacy, json_path, overrides, ignored)

    if legacy_env is not None and Path(legacy_env).exists():
        env_path = Path(legacy_env)
        inputs.append(env_path)
        _migrate_env_values(_read_dotenv(env_path), overrides, ignored)

    if not inputs:
        raise ConfigError("no legacy JSON or .env input exists")

    effective = load_config(
        defaults_path=defaults,
        site_path=None,
        environ={},
        cli_overrides=overrides,
    )
    defaults_effective = load_config(
        defaults_path=defaults, site_path=None, environ={}, cli_overrides={}
    )
    output_data = _differences(
        asdict(defaults_effective.config), asdict(effective.config)
    )
    rendered = _dump_toml(output_data)

    changed = True
    if output_path.exists():
        current = output_path.read_text(encoding="utf-8")
        if current != rendered:
            raise ConfigError(
                f"migration output {output_path} already exists with different content"
            )
        changed = False
    selected_backup_dir = (
        Path(backup_dir) if backup_dir else output_path.parent / "legacy-backups"
    )
    backups = tuple(_backup_once(path, selected_backup_dir) for path in inputs)
    if not output_path.exists():
        _atomic_write(output_path, rendered)

    # Validate the on-disk result after atomic staging/reuse.
    load_config(defaults_path=defaults, site_path=output_path, environ={})
    return MigrationResult(
        output=output_path,
        backups=backups,
        changed=changed,
        ignored=tuple(sorted(ignored)),
    )


def _upgrade_full_schema(data: Mapping[str, Any], label: str) -> dict[str, Any]:
    """Return a schema-2 full static configuration, upgrading schema-1 input.

    Schema 1 has no room-environment section.  A schema-1 full defaults file is
    upgraded by inserting the disabled V09 environment defaults.
    """

    upgraded = json.loads(json.dumps(data))
    version = upgraded.get("schema_version")
    if version == 1:
        upgraded["schema_version"] = SCHEMA_VERSION
        extensions = upgraded.setdefault("extensions", {})
        extensions.setdefault("environment", dict(ENVIRONMENT_STATIC_DEFAULTS))
    elif version != SCHEMA_VERSION:
        raise ConfigError(
            f"unsupported {label} schema_version {version}; expected {SCHEMA_VERSION}"
        )
    return upgraded


def _upgrade_override_schema(data: Mapping[str, Any], label: str) -> dict[str, Any]:
    """Return a schema-2 site/override mapping without destructive mutation.

    Schema-1 site files remain valid migration inputs.  Their explicit
    schema_version=1 is treated as a migration marker rather than an instruction
    to downgrade the effective static configuration.
    """

    upgraded = json.loads(json.dumps(data))
    version = upgraded.get("schema_version")
    if version == 1:
        upgraded.pop("schema_version", None)
    elif version is not None and version != SCHEMA_VERSION:
        # Let normal value validation produce the public error path after merge.
        pass
    return upgraded


def _read_toml(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{label} root must be a table")
    return data


def _schema_template() -> dict[str, Any]:
    return {
        "schema_version": int,
        **{
            section: get_type_hints(section_type)
            for section, section_type in SECTION_TYPES.items()
        },
        "extensions": {
            name: get_type_hints(extension_type)
            for name, extension_type in EXTENSION_TYPES.items()
        },
    }


def _validate_shape(data: Mapping[str, Any]) -> None:
    _validate_mapping(data, _schema_template(), "", require_all=True)


def _validate_override_shape(data: Mapping[str, Any]) -> None:
    _validate_mapping(data, _schema_template(), "", require_all=False)


def _validate_mapping(
    data: Mapping[str, Any], schema: Mapping[str, Any], prefix: str, *, require_all: bool
) -> None:
    unknown = sorted(set(data) - set(schema))
    if unknown:
        raise ConfigError(f"unknown configuration key: {prefix + unknown[0]}")
    if require_all:
        missing = sorted(set(schema) - set(data))
        if missing:
            raise ConfigError(f"missing configuration key: {prefix + missing[0]}")
    for key, value in data.items():
        dotted = f"{prefix}{key}"
        expected = schema[key]
        if isinstance(expected, dict):
            if not isinstance(value, dict):
                raise ConfigError(f"{dotted} must be a table")
            _validate_mapping(value, expected, dotted + ".", require_all=require_all)
        else:
            _require_type(dotted, value, expected)


def _require_type(dotted: str, value: Any, expected: type) -> None:
    valid = isinstance(value, expected)
    if expected in (int, float) and isinstance(value, bool):
        valid = False
    if expected is float and isinstance(value, int) and not isinstance(value, bool):
        valid = True
    if not valid:
        raise ConfigError(f"{dotted} must be {expected.__name__}")


def _expected_type(dotted: str) -> type:
    node: Any = _schema_template()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise ConfigError(f"unknown configuration key: {dotted}")
        node = node[part]
    if isinstance(node, dict):
        raise ConfigError(f"configuration override must name a field: {dotted}")
    return node


def _parse_scalar(raw: str, expected: type, label: str) -> Any:
    if expected is str:
        return raw
    if expected is bool:
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ConfigError(f"{label} must be a boolean")
    try:
        return expected(raw)
    except ValueError as exc:
        raise ConfigError(f"{label} must be {expected.__name__}") from exc


def _construct(raw: Mapping[str, Any]) -> Config:
    sections = {
        section: section_type(**raw[section])
        for section, section_type in SECTION_TYPES.items()
    }
    extensions = ExtensionsConfig(
        **{
            name: extension_type(**raw["extensions"][name])
            for name, extension_type in EXTENSION_TYPES.items()
        }
    )
    return Config(
        schema_version=raw["schema_version"],
        **sections,
        extensions=extensions,
    )


def _validate_values(config: Config) -> None:
    if config.schema_version != SCHEMA_VERSION:
        raise ConfigError(
            f"unsupported schema_version {config.schema_version}; expected {SCHEMA_VERSION}"
        )
    if config.assistant.name != IDENTITY.product_name:
        raise ConfigError("assistant.name is fixed by the product identity")
    if config.assistant.language != "en":
        raise ConfigError("assistant.language supports only en in the initial schema")
    if config.runtime.mode != "offline":
        raise ConfigError("runtime.mode supports only offline")
    if config.runtime.interaction_mode not in {"push_to_talk", "wake_word"}:
        raise ConfigError("runtime.interaction_mode supports push_to_talk or wake_word")
    if config.llm.provider != "ollama":
        raise ConfigError("llm.provider supports only ollama")
    _validate_loopback_url(config.llm.base_url, "llm.base_url")
    if not config.llm.model.strip():
        raise ConfigError("llm.model must not be empty")
    if not 256 <= config.llm.context_tokens <= 131072:
        raise ConfigError("llm.context_tokens must be between 256 and 131072")
    if not 1 <= config.llm.max_output_tokens <= config.llm.context_tokens:
        raise ConfigError("llm.max_output_tokens must be within the context window")
    if not re.fullmatch(r"[1-9][0-9]*[smh]", config.llm.keep_alive):
        raise ConfigError("llm.keep_alive must use a positive s, m, or h duration")
    for dotted, value in (
        ("audio.input_match", config.audio.input_match),
        ("audio.output_match", config.audio.output_match),
        ("stt.model", config.stt.model),
        ("tts.voice", config.tts.voice),
    ):
        if not value.strip():
            raise ConfigError(f"{dotted} must not be empty")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", config.stt.model) or ".." in config.stt.model:
        raise ConfigError("stt.model must be a safe model identifier")
    if not re.fullmatch(
        r"[a-z]{2}_[A-Z]{2}-[A-Za-z0-9_]+-(?:low|medium|high)",
        config.tts.voice,
    ):
        raise ConfigError("tts.voice must be a safe Piper voice identifier")
    if not 500 <= config.audio.speech_end_silence_ms <= 2000:
        raise ConfigError("audio.speech_end_silence_ms must be 500..2000")
    if not 50 <= config.audio.speech_energy_threshold <= 2000:
        raise ConfigError("audio.speech_energy_threshold must be 50..2000")
    if not 8000 <= config.audio.processing_rate <= config.audio.capture_rate <= 192000:
        raise ConfigError("audio rates must satisfy 8000 <= processing <= capture <= 192000")
    if config.audio.capture_rate % config.audio.processing_rate:
        raise ConfigError("audio.capture_rate must be divisible by audio.processing_rate")
    if not 1 <= config.stt.threads <= 16:
        raise ConfigError("stt.threads must be between 1 and 16")
    _validate_gpio(config.interaction.push_to_talk_gpio, "interaction.push_to_talk_gpio")
    _validate_gpio(config.interaction.recording_led_gpio, "interaction.recording_led_gpio")
    if not 1 <= config.retrieval.top_k <= 20:
        raise ConfigError("retrieval.top_k must be between 1 and 20")
    if config.privacy.raw_audio_retention != "delete":
        raise ConfigError("privacy.raw_audio_retention supports only delete")
    if config.privacy.interaction_logging or config.privacy.telemetry_content:
        raise ConfigError("persistent interaction content logging is not supported in core")
    _validate_loopback_bind(config.dashboard.bind)
    if not 1 <= config.dashboard.port <= 65535:
        raise ConfigError("dashboard.port must be between 1 and 65535")
    for field in fields(PathsConfig):
        _validate_absolute_path(
            getattr(config.paths, field.name), f"paths.{field.name}", allow_empty=False
        )
    wake = config.extensions.wake_word
    if config.runtime.interaction_mode == "wake_word" and not wake.enabled:
        raise ConfigError("wake_word interaction_mode requires extensions.wake_word.enabled=true")
    if not wake.phrase.strip():
        raise ConfigError("extensions.wake_word.phrase must not be empty")
    if wake.model:
        _validate_absolute_path(wake.model, "extensions.wake_word.model", allow_empty=True)
    if not 0.0 < wake.threshold < 1.0:
        raise ConfigError("extensions.wake_word.threshold must be between 0 and 1")
    if wake.backend not in {"streaming", "whisper"}:
        raise ConfigError("extensions.wake_word.backend supports streaming or whisper")
    if not 1e-50 <= wake.keyword_threshold <= 1e-5:
        raise ConfigError("extensions.wake_word.keyword_threshold must be between 1e-50 and 1e-5")
    _validate_gpio(wake.monitoring_led_gpio, "extensions.wake_word.monitoring_led_gpio")
    _validate_environment_config(config)
    from .resources import claims_for_config, ResourceConflict
    try:
        claims_for_config(config)
    except ResourceConflict as exc:
        raise ConfigError(str(exc)) from exc


def _validate_environment_config(config: Config) -> None:
    env = config.extensions.environment
    if env.sensor_backend not in {"sht31", "simulated"}:
        raise ConfigError("extensions.environment.sensor_backend supports only sht31 or simulated")
    if not 0 <= env.i2c_bus <= 255:
        raise ConfigError("extensions.environment.i2c_bus must be between 0 and 255")
    if env.i2c_address not in {0x44, 0x45}:
        raise ConfigError("extensions.environment.i2c_address must be 0x44 or 0x45")
    if env.sensor_repeatability not in {"low", "medium", "high"}:
        raise ConfigError("extensions.environment.sensor_repeatability must be low, medium, or high")
    if not 0.5 <= env.poll_interval_seconds <= 60.0:
        raise ConfigError("extensions.environment.poll_interval_seconds must be between 0.5 and 60.0")
    if not env.poll_interval_seconds <= env.stale_after_seconds <= 3600.0:
        raise ConfigError("extensions.environment.stale_after_seconds must be between poll interval and 3600")
    if not 1 <= env.valid_samples_to_recover <= 10:
        raise ConfigError("extensions.environment.valid_samples_to_recover must be between 1 and 10")
    if env.relay_backend not in {"libgpiod", "simulated"}:
        raise ConfigError("extensions.environment.relay_backend supports only libgpiod or simulated")
    _validate_gpio(env.relay_bcm, "extensions.environment.relay_bcm")
    if env.safe_state != "off":
        raise ConfigError("extensions.environment.safe_state supports only off")
    _validate_absolute_path(env.socket_path, "extensions.environment.socket_path", allow_empty=False)
    _validate_absolute_path(env.policy_path, "extensions.environment.policy_path", allow_empty=False)
    if not -50.0 <= env.temperature_policy_min_c < env.temperature_policy_max_c <= 100.0:
        raise ConfigError("environment temperature policy bounds must satisfy -50 <= min < max <= 100")
    if not 0.1 <= env.minimum_hysteresis_c <= env.maximum_hysteresis_c <= 50.0:
        raise ConfigError("environment hysteresis bounds must satisfy 0.1 <= minimum <= maximum <= 50")
    if env.maximum_hysteresis_c > (env.temperature_policy_max_c - env.temperature_policy_min_c):
        raise ConfigError("environment maximum_hysteresis_c must fit within temperature policy bounds")
    if not 0 <= env.minimum_dwell_seconds <= env.maximum_dwell_seconds <= 86400:
        raise ConfigError("environment dwell bounds must satisfy 0 <= minimum <= maximum <= 86400")
    if not 1 <= env.simulation_event_history_limit <= 1000:
        raise ConfigError("extensions.environment.simulation_event_history_limit must be between 1 and 1000")


def _validate_loopback_url(value: str, dotted: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigError(f"{dotted} must be an HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigError(f"{dotted} must not contain credentials, query, or fragment")
    if parsed.path:
        raise ConfigError(f"{dotted} must not contain a path or trailing slash")
    _require_loopback_host(parsed.hostname, dotted)


def _validate_loopback_bind(value: str) -> None:
    _require_loopback_host(value, "dashboard.bind")


def _require_loopback_host(value: str, dotted: str) -> None:
    if value.lower() == "localhost":
        return
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ConfigError(f"{dotted} must be a literal loopback address or localhost") from exc
    if not address.is_loopback:
        raise ConfigError(f"{dotted} must be loopback-only")


def _validate_gpio(value: int, dotted: str) -> None:
    if not 0 <= value <= 27:
        raise ConfigError(f"{dotted} must be a BCM GPIO number from 0 through 27")


def _validate_absolute_path(value: str, dotted: str, *, allow_empty: bool) -> None:
    if not value and allow_empty:
        return
    path = PurePath(value)
    if not path.is_absolute() or ".." in path.parts or str(path) != value:
        raise ConfigError(f"{dotted} must be an absolute normalized path without '..'")


def _leaf_paths(data: Mapping[str, Any], prefix: str = "") -> list[str]:
    result: list[str] = []
    for key, value in data.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.extend(_leaf_paths(value, dotted))
        else:
            result.append(dotted)
    return result


def _get_dotted(data: Mapping[str, Any], dotted: str) -> Any:
    node: Any = data
    for part in dotted.split("."):
        node = node[part]
    return node


def _set_dotted(data: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        child = node.setdefault(part, {})
        if not isinstance(child, dict):
            raise ConfigError(f"configuration key conflicts with table: {dotted}")
        node = child
    node[parts[-1]] = value


def _merge(target: dict[str, Any], overrides: Mapping[str, Any]) -> None:
    for key, value in overrides.items():
        if isinstance(value, dict):
            _merge(target[key], value)
        else:
            target[key] = value


def _differences(base: Mapping[str, Any], effective: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in effective.items():
        if isinstance(value, dict):
            nested = _differences(base[key], value)
            if nested:
                result[key] = nested
        elif value != base[key]:
            result[key] = value
    return result


LEGACY_JSON_MAP = {
    "chat_model": "llm.model",
    "mic_name": "audio.input_match",
    "speaker_name": "audio.output_match",
    "wake_word_model": "extensions.wake_word.model",
    "wake_word_threshold": "extensions.wake_word.threshold",
    "wake_phrase": "extensions.wake_word.phrase",
    "mic_sample_rate": "audio.capture_rate",
    "target_sample_rate": "audio.processing_rate",
    "assets_path": "paths.assets_dir",
    "piper_voice": "paths.piper_voice",
    "whisper_path": "paths.whisper_binary",
    "whisper_model": "paths.whisper_model",
    "local_soul_path": "paths.local_prompt",
}
LEGACY_IGNORED_JSON = {
    "project_root",
    "local_location",
    "cloud_soul_path",
    "display_width",
    "display_height",
    "use_framebuffer",
}
LEGACY_UNSUPPORTED_JSON = {"enable_streaming_tts", "enable_ui"}
LEGACY_ENV_MAP = {
    "GONKEN_MIC_NAME": "audio.input_match",
    "GONKEN_SPEAKER_NAME": "audio.output_match",
}
LEGACY_EXTERNAL_KEYS = {
    "OPENWEATHER_API_KEY",
    "NEWSAPI_KEY",
    "MOONSHOT_API_KEY",
}


def _migrate_json_values(
    legacy: Mapping[str, Any], source: Path, overrides: dict[str, Any], ignored: list[str]
) -> None:
    unknown = sorted(
        set(legacy) - set(LEGACY_JSON_MAP) - LEGACY_IGNORED_JSON - LEGACY_UNSUPPORTED_JSON
    )
    if unknown:
        raise ConfigError(f"unknown legacy JSON key: {unknown[0]}")
    for key in sorted(LEGACY_UNSUPPORTED_JSON):
        if legacy.get(key) is True:
            raise ConfigError(f"legacy {key}=true is unsupported in core")
        if key in legacy:
            ignored.append(f"json:{key}")
    for key in sorted(LEGACY_IGNORED_JSON & set(legacy)):
        ignored.append(f"json:{key}")
    for key, dotted in LEGACY_JSON_MAP.items():
        if key not in legacy:
            continue
        value = legacy[key]
        if key in {"wake_word_model", "wake_phrase"} and value == "":
            continue
        if dotted in PATH_FIELDS and value and not PurePath(str(value)).is_absolute():
            # Legacy paths were checkout-relative; the JSON lives in <root>/config.
            legacy_root = source.parent.parent.resolve()
            candidate = (legacy_root / str(value)).resolve()
            try:
                candidate.relative_to(legacy_root)
            except ValueError as exc:
                raise ConfigError(f"legacy path escapes checkout: {key}") from exc
            value = str(candidate)
        overrides[dotted] = value


def _read_dotenv(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigError(f"cannot read legacy .env {path}: {exc}") from exc
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key.strip()):
            raise ConfigError(f"invalid .env entry at {path}:{number}")
        result[key.strip()] = _unquote_env(value.strip(), path, number)
    return result


def _unquote_env(value: str, path: Path, number: int) -> str:
    if not value or value[0] not in {'"', "'"}:
        return value
    if len(value) < 2 or value[-1] != value[0]:
        raise ConfigError(f"unterminated .env quote at {path}:{number}")
    return value[1:-1]


def _migrate_env_values(
    legacy: Mapping[str, str], overrides: dict[str, Any], ignored: list[str]
) -> None:
    unknown = sorted(set(legacy) - set(LEGACY_ENV_MAP) - LEGACY_EXTERNAL_KEYS)
    if unknown:
        raise ConfigError(f"unknown legacy .env key: {unknown[0]}")
    populated_external = sorted(key for key in LEGACY_EXTERNAL_KEYS if legacy.get(key))
    if populated_external:
        raise ConfigError(
            "legacy external-service credentials are unsupported in offline core: "
            + ", ".join(populated_external)
        )
    for key in sorted(LEGACY_EXTERNAL_KEYS & set(legacy)):
        ignored.append(f"env:{key}")
    for key, dotted in LEGACY_ENV_MAP.items():
        if key in legacy:
            overrides[dotted] = legacy[key]


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    raise ConfigError(f"cannot serialize configuration value {value!r}")


def _dump_toml(data: Mapping[str, Any]) -> str:
    lines: list[str] = []
    for key, value in data.items():
        if not isinstance(value, dict):
            lines.append(f"{key} = {_toml_scalar(value)}")

    def emit_tables(table: Mapping[str, Any], prefix: str = "") -> None:
        for key, value in table.items():
            if not isinstance(value, dict):
                continue
            dotted = f"{prefix}.{key}" if prefix else key
            scalars = [(name, item) for name, item in value.items() if not isinstance(item, dict)]
            if scalars:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.append(f"[{dotted}]")
                lines.extend(f"{name} = {_toml_scalar(item)}" for name, item in scalars)
            emit_tables(value, dotted)

    emit_tables(data)
    return "\n".join(lines).rstrip() + "\n"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _backup_once(source: Path, backup_dir: Path) -> Path:
    import hashlib

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    timestamp = datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    destination = backup_dir / f"{source.name}.{timestamp}.{digest[:12]}.bak"
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup_dir.chmod(0o700)
    if destination.exists():
        if destination.read_bytes() != source.read_bytes():
            raise ConfigError(f"backup collision at {destination}")
        destination.chmod(0o600)
        return destination
    shutil.copy2(source, destination)
    destination.chmod(0o600)
    return destination
