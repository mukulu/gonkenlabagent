"""Daemon-result-derived spoken responses for V09 environment voice actions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .client import EnvironmentClientError
from .intents import EnvironmentIntent


def environment_success_response(intent: EnvironmentIntent, result: Mapping[str, Any]) -> str:
    """Render a concise human response from the daemon-confirmed result only.

    Simulation/hybrid provenance is part of the spoken truth boundary.  Voice may
    execute the same daemon operation in full simulation, hybrid HIL, or physical
    modes, but it must not make a simulated sensor sound like a real room sensor
    or a simulated actuator sound like observed fan hardware.
    """

    kind = intent.response_kind
    if kind == "temperature":
        return _temperature_response(result)
    if kind == "humidity":
        return _humidity_response(result)
    if kind == "sensor_read":
        return _sensor_read_response(result)
    if kind == "fan_status":
        state = _state(result)
        fan_label = _fan_power_label(result)
        return (
            f"{fan_label} is {_value(state.get('fan_power'), 'unknown')}. "
            f"The control mode is {_mode(state)}. "
            f"{_capability_sentence(result)} {_evidence_boundary_sentence(result)}"
        )
    if kind == "status":
        state = _state(result)
        return (
            f"The room environment service is {_value(result.get('environment'), 'unknown')}. "
            f"{_fan_power_label(result)} is {_value(state.get('fan_power'), 'unknown')} in {_mode(state)} mode. "
            f"Sensor state is {_value(state.get('sensor_quality'), 'unknown')}. "
            f"{_evidence_boundary_sentence(result)}"
        )
    if kind == "policy":
        return _policy_response(result)
    if kind == "fan_set":
        state = _state(result)
        return (
            f"{_fan_power_label(result)} is {_value(state.get('fan_power'), 'unknown')}. "
            f"Control mode is {_mode(state)}. "
            f"{_capability_sentence(result)} {_evidence_boundary_sentence(result)}"
        )
    if kind == "mode_set":
        state = _state(result)
        return (
            f"Fan control mode is {_mode(state)}. "
            f"{_fan_power_label(result)} is {_value(state.get('fan_power'), 'unknown')}. "
            f"{_evidence_boundary_sentence(result)}"
        )
    if kind == "policy_update":
        policy = _policy(result)
        state = _state(result)
        if policy:
            return (
                f"Fan policy is updated: mode {_value(policy.get('mode'), 'unknown')}, "
                f"start at {_format_c(policy.get('start_c'))}, stop at {_format_c(policy.get('stop_c'))}. "
                f"{_fan_power_label(result)} is {_value(state.get('fan_power'), 'unknown')}. "
                f"{_evidence_boundary_sentence(result)}"
            )
        return f"The fan policy was updated by the environment daemon. {_evidence_boundary_sentence(result)}"
    return f"The environment command completed. {_evidence_boundary_sentence(result)}"


def environment_error_response(error: EnvironmentClientError) -> str:
    """Render daemon/client rejection without implying physical success."""

    if error.code in {"ENV_UNAVAILABLE", "TIMEOUT"}:
        return "The environment service is unavailable, so I cannot verify or change the room fan."
    if error.code == "ENV_DISABLED":
        return "Environment control is disabled, so I did not change the room fan."
    if error.code == "SENSOR_UNAVAILABLE":
        return "The environment sensor is unavailable, so I cannot report a current room reading."
    if error.code == "SENSOR_STALE":
        return "The environment sensor reading is stale, so I cannot use it as current room evidence."
    if error.code == "ACTUATOR_UNAVAILABLE":
        return "The fan actuator is unavailable, so I did not change room-fan power."
    if error.code == "POLICY_INVALID":
        return "That fan policy was rejected by the environment daemon, so I did not save it."
    if error.code == "POLICY_GENERATION_CONFLICT":
        return "The fan policy changed before this update was applied, so I did not overwrite it."
    if error.code == "SIMULATION_ACTIVE_PHYSICAL_ACCEPTANCE_BLOCKED":
        return "That physical-acceptance action is blocked because a simulated backend is active."
    return f"The environment command was rejected with code {error.code}."


def _temperature_response(result: Mapping[str, Any]) -> str:
    reading = _reading(result)
    value = reading.get("temperature_c")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if _sensor_is_simulated(result):
            return (
                f"In simulation, the sensor temperature is {_format_c(value)}. "
                f"Sensor state is {_quality(reading)}. This is simulated evidence, not a physical room reading."
            )
        return f"The room temperature is {_format_c(value)}. Sensor state is {_quality(reading)}. {_evidence_boundary_sentence(result)}"
    return "The environment sensor is not reporting a current room temperature."


def _humidity_response(result: Mapping[str, Any]) -> str:
    reading = _reading(result)
    value = reading.get("relative_humidity_pct")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if _sensor_is_simulated(result):
            return (
                f"In simulation, the relative humidity is {float(value):.1f} percent. "
                f"Sensor state is {_quality(reading)}. This is simulated evidence, not a physical room reading."
            )
        return f"The relative humidity is {float(value):.1f} percent. Sensor state is {_quality(reading)}. {_evidence_boundary_sentence(result)}"
    return "The environment sensor is not reporting a current humidity reading."


def _sensor_read_response(result: Mapping[str, Any]) -> str:
    reading = _reading(result)
    temp = reading.get("temperature_c")
    humidity = reading.get("relative_humidity_pct")
    if isinstance(temp, (int, float)) and not isinstance(temp, bool) and isinstance(humidity, (int, float)) and not isinstance(humidity, bool):
        if _sensor_is_simulated(result):
            return (
                f"In simulation, the sensor temperature is {_format_c(temp)} and relative humidity is {float(humidity):.1f} percent. "
                f"Sensor state is {_quality(reading)}. This is simulated evidence, not a physical room reading."
            )
        return (
            f"The room temperature is {_format_c(temp)} and relative humidity is {float(humidity):.1f} percent. "
            f"Sensor state is {_quality(reading)}. {_evidence_boundary_sentence(result)}"
        )
    return "The environment sensor is not reporting a current room reading."


def _policy_response(result: Mapping[str, Any]) -> str:
    policy = _policy(result)
    if not policy:
        return "The environment daemon did not return a fan policy."
    return (
        f"Fan policy: mode {_value(policy.get('mode'), 'unknown')}, "
        f"start at {_format_c(policy.get('start_c'))}, stop at {_format_c(policy.get('stop_c'))}, "
        f"minimum on {policy.get('minimum_on_seconds', 'unknown')} seconds and minimum off {policy.get('minimum_off_seconds', 'unknown')} seconds. "
        f"{_evidence_boundary_sentence(result)}"
    )


def _reading(result: Mapping[str, Any]) -> Mapping[str, Any]:
    value = result.get("reading")
    return value if isinstance(value, Mapping) else {}


def _state(result: Mapping[str, Any]) -> Mapping[str, Any]:
    value = result.get("state")
    return value if isinstance(value, Mapping) else {}


def _policy(result: Mapping[str, Any]) -> Mapping[str, Any]:
    value = result.get("policy")
    if isinstance(value, Mapping):
        return value
    state = _state(result)
    value = state.get("policy")
    return value if isinstance(value, Mapping) else {}


def _provenance(result: Mapping[str, Any]) -> Mapping[str, Any]:
    value = result.get("provenance")
    if isinstance(value, Mapping):
        return value
    value = result.get("simulation")
    if isinstance(value, Mapping):
        return value
    return {}


def _mode(state: Mapping[str, Any]) -> str:
    return str(state.get("mode", "unknown")).replace("_", "-")


def _quality(reading: Mapping[str, Any]) -> str:
    return str(reading.get("quality", reading.get("error_code", "unknown"))).replace("_", "-")


def _sensor_is_simulated(result: Mapping[str, Any]) -> bool:
    provenance = _provenance(result)
    if provenance.get("sensor_is_simulated") is True:
        return True
    simulation = result.get("simulation")
    if isinstance(simulation, Mapping) and simulation.get("sensor_is_simulated") is True:
        return True
    reading = _reading(result)
    return reading.get("source_backend") == "simulated"


def _actuator_is_simulated(result: Mapping[str, Any]) -> bool:
    provenance = _provenance(result)
    if provenance.get("actuator_is_simulated") is True:
        return True
    simulation = result.get("simulation")
    return isinstance(simulation, Mapping) and simulation.get("actuator_is_simulated") is True


def _fan_power_label(result: Mapping[str, Any]) -> str:
    if _actuator_is_simulated(result):
        return "Simulated fan actuator power"
    return "Room fan relay power"


def _capability_sentence(result: Mapping[str, Any]) -> str:
    if _actuator_is_simulated(result):
        return "This confirms simulated actuator state, not physical fan motion or software speed."
    return "This confirms the daemon's relay-power state, not physical blade rotation or software speed."


def _evidence_boundary_sentence(result: Mapping[str, Any]) -> str:
    provenance = _provenance(result)
    mode = str(provenance.get("evidence_mode", "")).replace("_", "-")
    sensor_sim = _sensor_is_simulated(result)
    actuator_sim = _actuator_is_simulated(result)
    if sensor_sim and actuator_sim:
        return "This is full simulation evidence, not physical Raspberry Pi acceptance."
    if sensor_sim:
        return "The sensor side is simulated; only a target run can provide physical sensor acceptance."
    if actuator_sim:
        return "The fan actuator side is simulated; this does not prove relay wiring or blade motion."
    if mode and mode != "TARGET-PHYSICAL":
        return f"Evidence mode is {mode}; physical acceptance remains separate."
    if result.get("physical_evidence") is True or provenance.get("physical_evidence") is True:
        return "This is daemon-reported target evidence; fan blade motion still requires physical observation."
    return "Physical Raspberry Pi acceptance is not established by this response."


def _format_c(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):.1f} degrees Celsius"
    return "unknown degrees Celsius"


def _value(value: object, default: str) -> str:
    if value is None or isinstance(value, bool):
        return default
    return str(value).replace("_", "-")
