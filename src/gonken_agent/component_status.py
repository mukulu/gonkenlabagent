"""Read-only independent component status for operators and support evidence."""
from __future__ import annotations

import json
from pathlib import Path

from .diagnostics import collect_environment_diagnostics
from .llm.models import active_model, selection_status
from .tool_broker import TOOL_NAMES

READY_FILE = Path("/run/gonken-agent/ready.json")


def _bounded_json(path: Path, limit: int = 8192) -> dict[str, object] | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def collect(config, *, ready_file: Path = READY_FILE, environment_client_factory=None) -> dict[str, object]:
    ready = _bounded_json(ready_file)
    voice_ready = bool(ready and ready.get("status") == "READY" and ready.get("code") == "VOICE_RUNTIME_READY")
    expected_model = active_model(config.llm.model)
    ready_model = ready.get("model") if isinstance(ready, dict) else None
    model_matches = ready_model == expected_model if voice_ready else False
    env = collect_environment_diagnostics(config, mode="production", client_factory=environment_client_factory)
    ipc = env.get("ipc") if isinstance(env.get("ipc"), dict) else {}
    snapshot = ipc.get("snapshot") if isinstance(ipc.get("snapshot"), dict) else {}
    simulation = ipc.get("simulation") if isinstance(ipc.get("simulation"), dict) else {}
    static = env.get("static") if isinstance(env.get("static"), dict) else {}
    sensor_ready = ipc.get("status") == "READY" and str(ipc.get("sensor", "")).lower() == "ready"
    environment_ready = ipc.get("status") == "READY" and ipc.get("overall") == "READY"
    actuator_ready = ipc.get("status") == "READY" and str(ipc.get("actuator", "")).upper() == "READY"
    fan_backend = snapshot.get("actuator_backend", static.get("relay_backend", "unknown"))
    sensor_backend = snapshot.get("sensor_backend", static.get("sensor_backend", "unknown"))
    components = {
        "voice_conversation": {
            "status": "READY" if voice_ready and model_matches else "DEGRADED",
            "code": "VOICE_RUNTIME_READY" if voice_ready and model_matches else "VOICE_RUNTIME_NOT_CURRENT",
            "model": ready_model,
            "wake_phrase": ready.get("wake_phrase") if ready else None,
            "evidence": "semantic_runtime_ready_file",
        },
        "ollama_inference": {
            "status": "READY" if voice_ready and model_matches else "DEGRADED",
            "code": "ACTIVE_MODEL_IN_USE" if voice_ready and model_matches else "ACTIVE_MODEL_NOT_PROVEN_IN_VOICE_RUNTIME",
            "active_model": expected_model,
            "selection": selection_status(config.llm.model),
        },
        "environment_controller": {
            "status": "READY" if environment_ready else "DEGRADED",
            "code": "ENVIRONMENT_READY" if environment_ready else str(ipc.get("code", "ENVIRONMENT_UNAVAILABLE")),
            "enabled": bool(env.get("enabled", False)),
            "controller": ipc.get("controller", "unknown"),
        },
        "temperature_humidity_sensor": {
            "status": "READY" if sensor_ready else "DEGRADED",
            "code": "SENSOR_READY" if sensor_ready else "SENSOR_NOT_READY",
            "backend": sensor_backend,
            "simulated": bool(simulation.get("sensor_is_simulated", False)),
            "quality": snapshot.get("sensor_quality", "unknown"),
            "physical_acceptance": False,
        },
        "room_fan_control": {
            "status": "READY" if actuator_ready else "DEGRADED",
            "code": "ACTUATOR_COMMAND_PATH_READY" if actuator_ready else "ACTUATOR_NOT_READY",
            "backend": fan_backend,
            "simulated": bool(simulation.get("actuator_is_simulated", False)),
            "commanded_power": snapshot.get("fan_power", "unknown"),
            "physical_motion_observed": False,
            "software_speed_control": False,
            "physical_acceptance": False,
        },
        "llm_environment_tool_broker": {
            "status": "READY",
            "code": "TYPED_TOOL_BROKER_READY",
            "tools": sorted(TOOL_NAMES),
            "raw_shell": False,
            "raw_gpio": False,
            "raw_i2c": False,
            "mutations_require_explicit_authorization": True,
        },
    }
    return {
        "format": "gonken-component-status-v1",
        "components": components,
        "environment_evidence_mode": simulation.get("evidence_mode", "UNKNOWN"),
        "physical_acceptance_claimed": False,
    }
