"""Governed local-model roster and atomic active-model selection.

The conversational service reads one small selection record.  Model provisioning
is owned by maintenance/install tooling; runtime code never pulls or deletes
models.  Absence of a selection record preserves the prior configured model so
Checkpoint-44 installations remain rollback-compatible.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable


SELECTION_FORMAT = "gonken-active-model-v1"
DEFAULT_SELECTION_PATH = Path("/var/lib/gonken-agent/ollama/active-model.json")
DEFAULT_MODEL = "qwen3:0.6b"
LEGACY_MODEL = "qwen3.5:2b-q4_K_M"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    tag: str
    digest_prefix: str
    quantization: str
    parameter_size: str
    display_size_mib: int
    license: str
    source: str
    tools: bool
    thinking: bool
    role: str


MODEL_ROSTER: tuple[ModelSpec, ...] = (
    ModelSpec(
        tag="qwen3:0.6b",
        digest_prefix="7df6b6e09427",
        quantization="Q4_K_M",
        parameter_size="0.6B",
        display_size_mib=523,
        license="Apache-2.0",
        source="https://ollama.com/library/qwen3:0.6b",
        tools=True,
        thinking=True,
        role="default-low-latency",
    ),
    ModelSpec(
        tag="lfm2.5-thinking:1.2b",
        digest_prefix="95bd9d45385f",
        quantization="Q4_K_M",
        parameter_size="1.17B",
        display_size_mib=731,
        license="LFM-Open-License-1.0",
        source="https://ollama.com/library/lfm2.5-thinking:1.2b",
        tools=True,
        thinking=True,
        role="reasoning-alternate",
    ),
    ModelSpec(
        tag="qwen3.5:0.8b",
        digest_prefix="f3817196d142",
        quantization="Q8_0",
        parameter_size="0.8B",
        display_size_mib=1024,
        license="Apache-2.0",
        source="https://ollama.com/library/qwen3.5:0.8b",
        tools=True,
        thinking=True,
        role="modern-alternate",
    ),
)

_ROSTER_BY_TAG = {item.tag: item for item in MODEL_ROSTER}


def admitted_model(tag: str) -> ModelSpec:
    try:
        return _ROSTER_BY_TAG[tag]
    except KeyError as exc:
        raise ValueError("model is not in the governed V04 roster") from exc


def roster_tags() -> tuple[str, ...]:
    return tuple(item.tag for item in MODEL_ROSTER)


def required_model_bytes(*, reserve_mib: int = 512) -> int:
    if reserve_mib < 0:
        raise ValueError("reserve_mib must be non-negative")
    return (sum(item.display_size_mib for item in MODEL_ROSTER) + reserve_mib) * 1024 * 1024


def _read_selection(path: Path) -> dict[str, object] | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("format") != SELECTION_FORMAT:
        return None
    model = value.get("model")
    generation = value.get("generation")
    if model not in _ROSTER_BY_TAG or not isinstance(generation, int) or generation < 1:
        return None
    return value


def active_model(configured_model: str, *, path: Path = DEFAULT_SELECTION_PATH) -> str:
    value = _read_selection(Path(path))
    if value is not None:
        return str(value["model"])
    # Preserve the known-good Checkpoint-44 path until roster provisioning has
    # successfully written a governed selection record.
    return configured_model


def selection_status(configured_model: str, *, path: Path = DEFAULT_SELECTION_PATH) -> dict[str, object]:
    value = _read_selection(Path(path))
    if value is None:
        return {
            "status": "LEGACY_FALLBACK",
            "model": configured_model,
            "generation": 0,
            "selection_path": str(path),
            "governed_roster_active": False,
        }
    return {
        "status": "READY",
        "model": value["model"],
        "generation": value["generation"],
        "selection_path": str(path),
        "governed_roster_active": True,
    }


def write_selection(
    model: str,
    *,
    path: Path = DEFAULT_SELECTION_PATH,
    previous_model: str | None = None,
) -> dict[str, object]:
    admitted_model(model)
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("selection path must be an absolute non-symlink path")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    if path.parent.is_symlink():
        raise ValueError("selection parent must not be a symlink")
    current = _read_selection(path)
    generation = int(current.get("generation", 0)) + 1 if current else 1
    old_model = str(current["model"]) if current else previous_model
    payload = {
        "format": SELECTION_FORMAT,
        "model": model,
        "generation": generation,
        "previous_model": old_model,
    }
    fd, name = tempfile.mkstemp(prefix=".active-model.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o644)
        os.replace(temporary, path)
        path.chmod(0o644)
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def llm_config_for_model(llm_config, model: str):
    """Return a frozen LlmConfig copy with only the admitted model changed."""
    if model != LEGACY_MODEL:
        admitted_model(model)
    return replace(llm_config, model=model)


def roster_manifest() -> list[dict[str, object]]:
    return [
        {
            "tag": item.tag,
            "digest_prefix": item.digest_prefix,
            "quantization": item.quantization,
            "parameter_size": item.parameter_size,
            "display_size_mib": item.display_size_mib,
            "license": item.license,
            "source": item.source,
            "tools": item.tools,
            "thinking": item.thinking,
            "role": item.role,
        }
        for item in MODEL_ROSTER
    ]


def all_admitted(tags: Iterable[str]) -> bool:
    return all(tag in _ROSTER_BY_TAG for tag in tags)
