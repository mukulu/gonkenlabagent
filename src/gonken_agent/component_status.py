"""Read-only independent component status for operators and support evidence."""
from __future__ import annotations

from pathlib import Path

from .diagnostics import collect_environment_diagnostics
from .llm.models import active_model, selection_status
from .tool_broker import TOOL_NAMES
from .runtime_readiness import read_ready, bounded_json
from .llm.qualification import qualified_rows

READY_FILE = Path("/run/gonken-agent/ready.json")


def collect(config, *, ready_file: Path = READY_FILE, environment_client_factory=None,
            roster_file: Path = Path("/var/lib/gonken-agent/ollama/roster.json"),
            environment_evidence: dict | None = None) -> dict[str, object]:
    ready = read_ready(ready_file)
    voice_ready = ready is not None
    expected_model = active_model(config.llm.model)
    ready_model = ready.get("model") if isinstance(ready, dict) else None
    model_matches = ready_model == expected_model if voice_ready else False
    roster = bounded_json(roster_file, 256 * 1024)
    inventory = [{"name": ready_model, "digest": ready.get("model_digest")}] if ready else []
    qualified = qualified_rows(roster, inventory, context_tokens=config.llm.context_tokens)
    tools_qualified = bool(model_matches and qualified.get(expected_model, {}).get("tools"))
    env = environment_evidence if environment_evidence is not None else collect_environment_diagnostics(
        config, mode="production", client_factory=environment_client_factory)
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
            "evidence": "boot_process_release_bound_runtime_record",
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
            "status": "READY" if tools_qualified else "DEGRADED",
            "code": "TYPED_TOOL_BROKER_READY" if tools_qualified else "ACTIVE_MODEL_TOOLS_NOT_QUALIFIED",
            "implementation_available": True,
            "active_model_qualified": tools_qualified,
            "tools": sorted(TOOL_NAMES),
            "raw_shell": False,
            "raw_gpio": False,
            "raw_i2c": False,
            "mutations_require_explicit_authorization": True,
        },
    }
    if not env.get("enabled"):
        for name in ("environment_controller", "temperature_humidity_sensor", "room_fan_control"):
            components[name]["status"] = "DISABLED"
            components[name]["code"] = "ENVIRONMENT_DISABLED"
    return {
        "format": "gonken-component-status-v1",
        "components": components,
        "environment_evidence_mode": simulation.get("evidence_mode", "UNKNOWN"),
        "physical_acceptance_claimed": False,
    }
