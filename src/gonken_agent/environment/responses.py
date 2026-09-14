"""Daemon-result-derived spoken responses for V09 environment voice actions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .client import EnvironmentClientError
from .intents import EnvironmentIntent


def environment_success_response(intent: EnvironmentIntent, result: Mapping[str, Any]) -> str:
    """Render a concise human response from the daemon-confirmed result only."""

    kind = intent.response_kind
    if kind == "temperature":
        return _temperature_response(result)
    if kind == "humidity":
        return _humidity_response(result)
    if kind == "sensor_read":
        return _sensor_read_response(result)
    if kind == "fan_status":
        state = _state(result)
        return (
            f"Room fan power is {_value(state.get('fan_power'), 'unknown')}. "
            f"The control mode is {_mode(state)}. "
            "I can report relay power only, not blade motion or software speed."
        )
    if kind == "status":
        state = _state(result)
        return (
            f"The room environment is {_value(result.get('environment'), 'unknown')}. "
            f"The fan power is {_value(state.get('fan_power'), 'unknown')} in {_mode(state)} mode. "
            f"Sensor state is {_value(state.get('sensor_quality'), 'unknown')}."
        )
    if kind == "policy":
        return _policy_response(result)
    if kind == "fan_set":
        state = _state(result)
        return (
            f"Room fan power is {_value(state.get('fan_power'), 'unknown')}. "
            f"Control mode is {_mode(state)}. "
            "This confirms the daemon's relay-power state, not physical blade rotation."
        )
    if kind == "mode_set":
        state = _state(result)
        return (
            f"Fan control mode is {_mode(state)}. "
            f"Room fan power is {_value(state.get('fan_power'), 'unknown')}."
        )
    if kind == "policy_update":
        policy = _policy(result)
        state = _state(result)
        if policy:
            return (
                f"Fan policy is updated: mode {_value(policy.get('mode'), 'unknown')}, "
                f"start at {_format_c(policy.get('start_c'))}, stop at {_format_c(policy.get('stop_c'))}. "
                f"Current fan power is {_value(state.get('fan_power'), 'unknown')}."
            )
        return "The fan policy was updated by the environment daemon."
    return "The environment command completed."


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
    return f"The environment command was rejected with code {error.code}."


def _temperature_response(result: Mapping[str, Any]) -> str:
    reading = _reading(result)
    value = reading.get("temperature_c")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"The room temperature is {_format_c(value)}. Sensor state is {_quality(reading)}."
    return "The environment sensor is not reporting a current room temperature."


def _humidity_response(result: Mapping[str, Any]) -> str:
    reading = _reading(result)
    value = reading.get("relative_humidity_pct")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"The relative humidity is {float(value):.1f} percent. Sensor state is {_quality(reading)}."
    return "The environment sensor is not reporting a current humidity reading."


def _sensor_read_response(result: Mapping[str, Any]) -> str:
    reading = _reading(result)
    temp = reading.get("temperature_c")
    humidity = reading.get("relative_humidity_pct")
    if isinstance(temp, (int, float)) and not isinstance(temp, bool) and isinstance(humidity, (int, float)) and not isinstance(humidity, bool):
        return (
            f"The room temperature is {_format_c(temp)} and relative humidity is {float(humidity):.1f} percent. "
            f"Sensor state is {_quality(reading)}."
        )
    return "The environment sensor is not reporting a current room reading."


def _policy_response(result: Mapping[str, Any]) -> str:
    policy = _policy(result)
    if not policy:
        return "The environment daemon did not return a fan policy."
    return (
        f"Fan policy: mode {_value(policy.get('mode'), 'unknown')}, "
        f"start at {_format_c(policy.get('start_c'))}, stop at {_format_c(policy.get('stop_c'))}, "
        f"minimum on {policy.get('minimum_on_seconds', 'unknown')} seconds and minimum off {policy.get('minimum_off_seconds', 'unknown')} seconds."
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


def _mode(state: Mapping[str, Any]) -> str:
    return str(state.get("mode", "unknown")).replace("_", "-")


def _quality(reading: Mapping[str, Any]) -> str:
    return str(reading.get("quality", reading.get("error_code", "unknown"))).replace("_", "-")


def _format_c(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):.1f} degrees Celsius"
    return "unknown degrees Celsius"


def _value(value: object, default: str) -> str:
    if value is None or isinstance(value, bool):
        return default
    return str(value).replace("_", "-")
