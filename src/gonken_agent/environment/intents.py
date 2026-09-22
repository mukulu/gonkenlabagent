"""Deterministic voice intents for the V09 environment-control domain.

This parser is deliberately small, local and allow-listed.  It translates
common room-temperature, humidity, fan, mode and threshold phrases into the same
versioned daemon operations used by the CLI.  It never constructs shell
commands, raw GPIO/I2C operations or arbitrary tool calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping
from ..spoken_numbers import normalize_spoken_numbers


@dataclass(frozen=True, slots=True)
class EnvironmentIntent:
    """A typed environment operation that may be executed by the daemon client."""

    operation: str
    params: Mapping[str, Any]
    response_kind: str
    mutating: bool = False


@dataclass(frozen=True, slots=True)
class EnvironmentClarification:
    """A safe spoken clarification for an ambiguous environment request."""

    message: str


ModeOrPowerTerms = tuple[str, ...]

_NUMBER = r"(-?\d+(?:\.\d+)?)\s*(?:degrees?|degree|°\s*c|°c|celsius|c)?"
_START_PATTERNS = (
    rf"(?:come|comes|turn|turns|switch|switches|start|starts)\s+(?:it\s+|the\s+)?(?:room\s+)?(?:fan\s+)?on\s+(?:at|above|when|if|from)?\s*{_NUMBER}",
    rf"(?:come|comes|turn|turns|switch|switches|start|starts)\s+on\s+(?:at|above|when|if|from)?\s*{_NUMBER}",
    rf"(?:on|start)\s+threshold\s+(?:at|to|=)?\s*{_NUMBER}",
    rf"start\s+(?:at|above)\s*{_NUMBER}",
    rf"on\s+(?:at|above)\s*{_NUMBER}",
)
_STOP_PATTERNS = (
    rf"(?:turn|turns|switch|switches|stop|stops)\s+(?:it\s+|the\s+)?(?:room\s+)?(?:fan\s+)?off\s+(?:at|below|when|if)?\s*{_NUMBER}",
    rf"(?:turn|turns|switch|switches)\s+off\s+(?:at|below|when|if)?\s*{_NUMBER}",
    rf"stop\s+(?:at|below)?\s*{_NUMBER}",
    rf"(?:off|stop)\s+threshold\s+(?:at|to|=)?\s*{_NUMBER}",
    rf"off\s+(?:at|below)\s*{_NUMBER}",
)


def parse_environment_intent(text: str) -> EnvironmentIntent | EnvironmentClarification | None:
    """Return a typed environment intent, a clarification, or ``None``.

    ``None`` means the utterance should continue through the ordinary local LLM
    conversation path.  A clarification means the utterance is environment
    related but unsafe or underspecified for actuation.
    """

    if not isinstance(text, str) or len(text) > 4096:
        return EnvironmentClarification("No setting was changed. The command is invalid or too long.")
    normalized = _normalize(text)
    if not normalized:
        return None

    # Quoted, negated and hypothetical control language is not authorization.
    if (_is_environment_related(normalized) and
            (re.search(r"\b(?:not|never|dont|don t|should|would|could|hypothetical|example|say|imagine)\b", normalized)
             or re.match(r"(?:what happens|what if |how |if |suppose |imagine )", normalized)
             or any(c in text for c in ('"', "'", "\u201c", "\u201d")))):
        if re.search(r"\b(?:turn|switch|set|start|stop|change|enable|disable)\b", normalized):
            return EnvironmentClarification("No setting was changed. Use a direct, unquoted command with explicit values.")

    start_c = _extract_number(normalized, _START_PATTERNS)
    stop_c = _extract_number(normalized, _STOP_PATTERNS)
    requested_mode = _requested_mode(normalized)
    if start_c is not None or stop_c is not None:
        direct = re.sub(r"^(?:(?:hey )?gonken |please )+", "", normalized)
        if not re.match(r"(?:use|set|change|update|turn|switch|start|stop|on threshold|off threshold)\b", direct):
            return EnvironmentClarification("No threshold was changed. Use a direct setting command, such as set fan on threshold to 28 and off threshold to 26.")
        params: dict[str, Any] = {}
        if requested_mode is not None:
            params["mode"] = requested_mode
        if start_c is not None:
            params["start_c"] = start_c
        if stop_c is not None:
            params["stop_c"] = stop_c
        return EnvironmentIntent("policy.update", params, "policy_update", mutating=True)

    if _ambiguous_temperature_setting(normalized):
        return EnvironmentClarification(
            "Do you want to change the fan start threshold, the fan stop threshold, or both?"
        )

    if requested_mode is not None and _looks_like_mode_command(normalized):
        return EnvironmentIntent(
            "mode.set",
            {"mode": requested_mode},
            "mode_set",
            mutating=True,
        )

    if _contains_any(normalized, ("fan",)) and re.search(r"\bon\b", normalized) and re.search(r"\boff\b", normalized) and re.search(r"\b(?:turn|switch|start|stop)\b", normalized):
        return EnvironmentClarification("No fan command was sent. Choose on or off, or specify a complete timed cycle.")
    fan_power = _requested_fan_power(normalized)
    if fan_power is not None:
        return EnvironmentIntent(
            "fan.set",
            {"power": fan_power},
            "fan_set",
            mutating=True,
        )

    if _asks_temperature(normalized) and _asks_humidity(normalized):
        return EnvironmentIntent("sensor.read", {}, "sensor_read", mutating=False)
    if _asks_temperature(normalized):
        return EnvironmentIntent("sensor.read", {}, "temperature", mutating=False)
    if _asks_humidity(normalized):
        return EnvironmentIntent("sensor.read", {}, "humidity", mutating=False)
    if _asks_policy(normalized):
        return EnvironmentIntent("policy.get", {}, "policy", mutating=False)
    if _asks_fan_status(normalized):
        return EnvironmentIntent("status.get", {}, "fan_status", mutating=False)
    if _asks_environment_status(normalized):
        return EnvironmentIntent("status.get", {}, "status", mutating=False)

    if _is_environment_related(normalized) and _has_unsafe_action_shape(normalized):
        return EnvironmentClarification(
            "I can report temperature or humidity, turn room-fan power on or off, set manual, semi-automatic, automatic or disabled mode, or change explicit start and stop thresholds."
        )
    return None


def _normalize(text: str) -> str:
    text = normalize_spoken_numbers(text.casefold())
    text = re.sub(r"[^a-z0-9.°%+-]+", " ", text)
    return " ".join(text.split())


def _extract_number(text: str, patterns: tuple[str, ...]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1))
            except (TypeError, ValueError):
                return None
    return None


def _requested_mode(text: str) -> str | None:
    if re.search(r"\b(semi\s*automatic|semi\s*auto|semi-auto|semiautomatic)\b", text):
        return "semi_automatic"
    if re.search(r"\b(automatic|auto)\b", text):
        return "automatic"
    if re.search(r"\bmanual\b", text):
        return "manual"
    if re.search(r"\b(disabled|disable|safe off)\b", text) and _contains_any(text, ("mode", "control", "environment", "fan")):
        return "disabled"
    return None


def _looks_like_mode_command(text: str) -> bool:
    return _contains_any(text, ("set", "use", "switch", "change", "mode", "control", "enable", "disable"))


def _requested_fan_power(text: str) -> str | None:
    if not _contains_any(text, ("fan", "room fan")):
        return None
    if _asks_fan_status(text):
        return None
    on_patterns = (
        r"\b(?:turn|switch|start|run|enable|power)\s+(?:the\s+)?(?:room\s+)?fan\s+on\b",
        r"\b(?:turn|switch|power)\s+on\s+(?:the\s+)?(?:room\s+)?fan\b",
        r"\b(?:start|run|enable)\s+(?:the\s+)?(?:room\s+)?fan\b",
        r"\bget\s+(?:the\s+)?(?:room\s+)?fan\s+(?:going|running)\b",
        r"\bstart\s+(?:some\s+)?air\s+(?:moving|circulating|circulation)\b",
        r"\b(?:room\s+)?fan\s+on\b",
    )
    off_patterns = (
        r"\b(?:turn|switch|shut|power|stop|disable)\s+(?:the\s+)?(?:room\s+)?fan\s+off\b",
        r"\b(?:turn|switch|shut|power)\s+off\s+(?:the\s+)?(?:room\s+)?fan\b",
        r"\b(?:stop|shut|disable)\s+(?:the\s+)?(?:room\s+)?fan\b",
        r"\bstop\s+(?:the\s+)?air\s+(?:movement|circulation|circulating)\b",
        r"\b(?:room\s+)?fan\s+off\b",
    )
    if any(re.search(pattern, text) for pattern in on_patterns):
        return "on"
    if any(re.search(pattern, text) for pattern in off_patterns):
        return "off"
    return None


def _asks_temperature(text: str) -> bool:
    return _contains_any(
        text,
        (
            "temperature", "temp", "how hot", "room heat", "how warm",
            "how cold", "how cool", "warm is the room", "degrees in the room",
            "degrees is the room", "room temperature",
        ),
    )


def _asks_humidity(text: str) -> bool:
    return _contains_any(text, ("humidity", "humid", "relative humidity"))


def _asks_fan_status(text: str) -> bool:
    if not _contains_any(text, ("fan", "room fan", "air circulation")):
        return False
    return _contains_any(text, ("status", "state", "on", "off", "running", "power")) and _contains_any(
        text,
        ("is", "what", "tell", "show", "report", "whether", "currently", "status"),
    )


def _asks_policy(text: str) -> bool:
    return _contains_any(text, ("fan", "environment", "room")) and _contains_any(
        text,
        ("policy", "threshold", "settings", "setting", "set up", "configured", "configuration"),
    ) and re.search(r"\b(set|change|update)\b", text) is None


def _asks_environment_status(text: str) -> bool:
    return _contains_any(text, ("environment", "room", "fan")) and _contains_any(
        text,
        ("status", "state", "health", "ready"),
    )


def _ambiguous_temperature_setting(text: str) -> bool:
    if not _contains_any(text, ("set", "change", "update")):
        return False
    if not _contains_any(text, ("temperature", "temp", "threshold")):
        return False
    if re.search(_NUMBER, text) is None:
        return False
    return not _contains_any(text, ("start", "stop", "on", "off", "come on", "turn on", "turn off"))


def _has_unsafe_action_shape(text: str) -> bool:
    return re.search(r"\b(set|change|update|make|configure|run|execute|gpio|shell)\b", text) is not None


def _is_environment_related(text: str) -> bool:
    return _contains_any(
        text,
        ("environment", "temperature", "humidity", "fan", "room fan", "relay", "air circulation"),
    )


def _contains_any(text: str, needles: ModeOrPowerTerms) -> bool:
    return any(needle in text for needle in needles)
