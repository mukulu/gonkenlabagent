"""Typed, allow-listed semantic tool broker for local GonKen conversations.

Model output may *propose* one of these semantic operations.  The broker owns
schema validation, mutation authorization, serialization, environment IPC and
truthful result rendering.  It never exposes shell, systemctl, raw GPIO, raw I2C,
files, networking or arbitrary Python execution to the model.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from .environment.client import EnvironmentClient, EnvironmentClientError
from .environment.intents import EnvironmentIntent
from .environment.responses import environment_error_response, environment_success_response


class ToolBrokerError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ToolProposal:
    name: str
    arguments: Mapping[str, Any]


TOOL_SCHEMAS: tuple[dict[str, object], ...] = (
    {
        "type": "function",
        "function": {
            "name": "system_get_local_datetime",
            "description": "Read the Raspberry Pi local date and time. This is read-only.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "environment_read_sensor",
            "description": "Read current room temperature and relative humidity from the environment service.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "environment_get_status",
            "description": "Read room-environment controller and room-fan commanded power state.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "environment_set_fan_power",
            "description": "Set governed room-fan relay power on or off through the environment service.",
            "parameters": {
                "type": "object",
                "properties": {"power": {"type": "string", "enum": ["on", "off"]}},
                "required": ["power"],
                "additionalProperties": False,
            },
        },
    },
)

TOOL_NAMES = {str(item["function"]["name"]) for item in TOOL_SCHEMAS}  # type: ignore[index]
_MUTATION_LOCK = threading.Lock()


def parse_tool_call(value: Mapping[str, Any]) -> ToolProposal:
    function = value.get("function")
    if not isinstance(function, Mapping):
        raise ToolBrokerError("TOOL_CALL_INVALID", "tool call omitted function")
    name = function.get("name")
    arguments = function.get("arguments", {})
    if not isinstance(name, str) or name not in TOOL_NAMES:
        raise ToolBrokerError("TOOL_NOT_ALLOWED", "tool is not in the allow-list")
    if not isinstance(arguments, Mapping) or len(arguments) > 8:
        raise ToolBrokerError("TOOL_ARGUMENTS_INVALID", "tool arguments must be a small object")
    if name != "environment_set_fan_power" and arguments:
        raise ToolBrokerError("TOOL_ARGUMENTS_INVALID", "read-only tool takes no arguments")
    if name == "environment_set_fan_power":
        if set(arguments) != {"power"} or arguments.get("power") not in {"on", "off"}:
            raise ToolBrokerError("TOOL_ARGUMENTS_INVALID", "fan power must be exactly on or off")
    return ToolProposal(name, dict(arguments))


def direct_clock_intent(text: str) -> str | None:
    normalized = " ".join(text.casefold().split())
    if re.search(r"\b(what|tell|give|show)\b.*\b(time|date|day)\b", normalized) or re.fullmatch(
        r"(?:current\s+)?(?:time|date|date and time|time and date)", normalized
    ):
        return render_local_datetime()
    return None


def render_local_datetime(now: datetime | None = None) -> str:
    moment = now or datetime.now().astimezone()
    return (
        f"It is {moment.strftime('%-I:%M %p')} on "
        f"{moment.strftime('%A, %B %-d, %Y')} local time."
    )


def _mutation_authorized(user_text: str, proposal: ToolProposal) -> bool:
    if proposal.name != "environment_set_fan_power":
        return True
    text = " ".join(user_text.casefold().split())
    # Reject quoted, hypothetical, instructional and negated forms.  A model may
    # understand them semantically but it still lacks mutation authority.
    unsafe_markers = (
        "don't ", "do not ", "not turn", "not switch", "not start", "not stop",
        "what if", "if i ", "if you ", "would you", "could you explain", "how would",
        "hypothetical", "pretend", "example", "quote", "quoted", "without turning",
    )
    if any(marker in text for marker in unsafe_markers):
        return False
    if any(mark in user_text for mark in ('"', "“", "”", "'")) and any(
        token in text for token in ("turn", "switch", "start", "stop", "fan")
    ):
        return False
    power = str(proposal.arguments["power"])
    on_patterns = (
        r"\b(?:please\s+)?(?:turn|switch|power|start|run|enable)\b.*\b(?:fan|air circulation)\b.*\b(?:on|going|running)\b",
        r"\b(?:please\s+)?(?:start|run|enable)\s+(?:the\s+)?(?:room\s+)?fan\b",
        r"\bget\s+(?:the\s+)?(?:room\s+)?fan\s+(?:going|running)\b",
        r"\bstart\s+(?:some\s+)?air\s+(?:moving|circulating|circulation)\b",
        r"\bi\s+(?:want|need|would like)\b.*\bfan\b.*\bon\b",
    )
    off_patterns = (
        r"\b(?:please\s+)?(?:turn|switch|power|shut|stop|disable)\b.*\b(?:fan|air circulation)\b.*\b(?:off|down|stopped)?\b",
        r"\b(?:please\s+)?(?:stop|disable|shut)\s+(?:the\s+)?(?:room\s+)?fan\b",
        r"\bstop\s+(?:the\s+)?air\s+(?:movement|circulation|circulating)\b",
        r"\bi\s+(?:want|need|would like)\b.*\bfan\b.*\boff\b",
    )
    patterns = on_patterns if power == "on" else off_patterns
    return any(re.search(pattern, text) for pattern in patterns)


class ToolBroker:
    def __init__(self, environment_client_factory) -> None:
        self.environment_client_factory = environment_client_factory

    @property
    def schemas(self) -> tuple[dict[str, object], ...]:
        return TOOL_SCHEMAS

    def execute(self, proposal: ToolProposal, *, user_text: str) -> dict[str, object]:
        if not _mutation_authorized(user_text, proposal):
            raise ToolBrokerError("TOOL_MUTATION_NOT_AUTHORIZED", "user text did not independently authorize this mutation")
        if proposal.name == "system_get_local_datetime":
            return {"status": "READY", "tool": proposal.name, "spoken": render_local_datetime(), "mutating": False}
        try:
            client: EnvironmentClient = self.environment_client_factory()
            if proposal.name == "environment_read_sensor":
                result = client.read_sensor()
                intent = EnvironmentIntent("sensor.read", {}, "sensor_read", mutating=False)
            elif proposal.name == "environment_get_status":
                result = client.status()
                intent = EnvironmentIntent("status.get", {}, "fan_status", mutating=False)
            elif proposal.name == "environment_set_fan_power":
                intent = EnvironmentIntent(
                    "fan.set", {"power": proposal.arguments["power"]}, "fan_set", mutating=True
                )
                with _MUTATION_LOCK:
                    result = client.fan_set(str(proposal.arguments["power"]))
            else:  # pragma: no cover - parse_tool_call prevents this
                raise ToolBrokerError("TOOL_NOT_ALLOWED", "unknown tool")
        except EnvironmentClientError as exc:
            return {
                "status": "FAILED",
                "tool": proposal.name,
                "code": exc.code,
                "spoken": environment_error_response(exc),
                "mutating": proposal.name == "environment_set_fan_power",
            }
        return {
            "status": "READY",
            "tool": proposal.name,
            "spoken": environment_success_response(intent, result),
            "mutating": intent.mutating,
            "result": dict(result),
        }

    def execute_calls(self, raw_calls: list[Mapping[str, Any]], *, user_text: str) -> str:
        if not raw_calls or len(raw_calls) > 2:
            raise ToolBrokerError("TOOL_CALL_COUNT_INVALID", "tool call count exceeds the bounded transaction")
        proposals = [parse_tool_call(item) for item in raw_calls]
        if sum(1 for item in proposals if item.name == "environment_set_fan_power") > 1:
            raise ToolBrokerError("TOOL_DUPLICATE_MUTATION", "multiple mutations in one turn are not allowed")
        spoken: list[str] = []
        for proposal in proposals:
            outcome = self.execute(proposal, user_text=user_text)
            text = outcome.get("spoken")
            if isinstance(text, str) and text.strip():
                spoken.append(text.strip())
        if not spoken:
            raise ToolBrokerError("TOOL_RESULT_INVALID", "tool transaction returned no spoken result")
        return " ".join(spoken)


def broker_health() -> dict[str, object]:
    return {
        "status": "READY",
        "schema": 1,
        "tool_count": len(TOOL_SCHEMAS),
        "tools": sorted(TOOL_NAMES),
        "raw_shell": False,
        "raw_gpio": False,
        "raw_i2c": False,
        "mutation_policy": "explicit-user-authorization-and-serialized",
        "max_tool_calls_per_turn": 2,
    }
