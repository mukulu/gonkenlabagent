"""Bounded local JSON protocol for the V09 environment daemon.

This module contains only serialization and validation logic.  It does not open
sockets, files, I2C, GPIO, network or model resources.  The protocol is scoped
to typed room-environment operations; it intentionally exposes no raw GPIO,
I2C, shell, file-path or model-tool execution surface.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 16 * 1024
MAX_RESPONSE_BYTES = 64 * 1024
MAX_REQUEST_ID_LENGTH = 64

REQUEST_FIELDS = frozenset({"protocol_version", "request_id", "operation", "params"})
RESPONSE_FIELDS = frozenset(
    {
        "protocol_version",
        "request_id",
        "operation",
        "status",
        "result",
        "error",
        "daemon",
    }
)

OPERATIONS = frozenset(
    {
        "automation.add", "automation.list", "automation.cancel",
        "notifications.get", "notifications.ack", "power.prepare", "power.release",
        "status.get",
        "sensor.read",
        "health.get",
        "fan.set",
        "mode.set",
        "policy.get",
        "policy.update",
        "probe.run",
        "state.snapshot.get",
        "events.get",
        "simulation.status.get",
        "simulation.reset",
        "simulation.sensor.set",
        "simulation.sensor.fault",
        "simulation.sensor.reset",
        "simulation.actuator.behavior.set",
        "simulation.actuator.reset",
    }
)

ERROR_CODES = frozenset(
    {
        "BAD_REQUEST",
        "UNSUPPORTED_PROTOCOL",
        "UNKNOWN_OPERATION",
        "PERMISSION_DENIED",
        "ENV_DISABLED",
        "SENSOR_UNAVAILABLE",
        "SENSOR_STALE",
        "ACTUATOR_UNAVAILABLE",
        "POLICY_INVALID",
        "POLICY_GENERATION_CONFLICT",
        "BUSY",
        "TIMEOUT",
        "INTERNAL_ERROR",
        "SIMULATION_DISABLED",
        "SIMULATION_SENSOR_NOT_ACTIVE",
        "SIMULATION_ACTUATOR_NOT_ACTIVE",
        "SIMULATION_INPUT_INVALID",
        "SIMULATION_FAULT_INVALID",
    }
)


class ProtocolError(ValueError):
    """A request or response violates the local environment protocol."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code if code in ERROR_CODES else "BAD_REQUEST"
        super().__init__(f"{self.code}: {message}")


def new_request_id() -> str:
    """Return an opaque bounded request identifier."""

    return uuid.uuid4().hex


@dataclass(frozen=True, slots=True)
class EnvironmentRequest:
    protocol_version: int
    request_id: str
    operation: str
    params: Mapping[str, Any]

    def to_mapping(self) -> dict[str, object]:
        return {
            "protocol_version": self.protocol_version,
            "request_id": self.request_id,
            "operation": self.operation,
            "params": dict(self.params),
        }


@dataclass(frozen=True, slots=True)
class EnvironmentError:
    code: str
    message: str

    def to_mapping(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True, slots=True)
class EnvironmentResponse:
    protocol_version: int
    request_id: str | None
    operation: str | None
    status: str
    result: Mapping[str, Any] | None
    error: EnvironmentError | None
    daemon: Mapping[str, Any]

    def to_mapping(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "protocol_version": self.protocol_version,
            "request_id": self.request_id,
            "operation": self.operation,
            "status": self.status,
            "daemon": dict(self.daemon),
        }
        if self.result is not None:
            payload["result"] = dict(self.result)
        if self.error is not None:
            payload["error"] = self.error.to_mapping()
        return payload



def make_request(operation: str, params: Mapping[str, Any] | None = None, *, request_id: str | None = None) -> EnvironmentRequest:
    if not isinstance(operation, str) or not operation:
        raise ProtocolError("BAD_REQUEST", "operation must be a non-empty string")
    if operation not in OPERATIONS:
        raise ProtocolError("UNKNOWN_OPERATION", f"unsupported operation: {operation}")
    selected_id = new_request_id() if request_id is None else request_id
    _validate_request_id(selected_id)
    if params is None:
        selected_params: Mapping[str, Any] = {}
    elif isinstance(params, Mapping):
        selected_params = params
    else:
        raise ProtocolError("BAD_REQUEST", "params must be an object")
    return EnvironmentRequest(
        protocol_version=PROTOCOL_VERSION,
        request_id=selected_id,
        operation=operation,
        params=selected_params,
    )


def parse_request_bytes(data: bytes) -> EnvironmentRequest:
    if len(data) > MAX_REQUEST_BYTES:
        raise ProtocolError("BAD_REQUEST", "request exceeds maximum size")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError("BAD_REQUEST", "request must be UTF-8 JSON") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolError("BAD_REQUEST", "request must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("BAD_REQUEST", "request root must be an object")
    return parse_request_mapping(payload)


def parse_request_mapping(payload: Mapping[str, Any]) -> EnvironmentRequest:
    unknown = sorted(set(payload) - REQUEST_FIELDS)
    if unknown:
        raise ProtocolError("BAD_REQUEST", f"unknown request field: {unknown[0]}")
    version = payload.get("protocol_version")
    if version != PROTOCOL_VERSION:
        raise ProtocolError("UNSUPPORTED_PROTOCOL", "unsupported protocol_version")
    request_id = payload.get("request_id")
    if not isinstance(request_id, str):
        raise ProtocolError("BAD_REQUEST", "request_id must be a string")
    _validate_request_id(request_id)
    operation = payload.get("operation")
    if not isinstance(operation, str):
        raise ProtocolError("BAD_REQUEST", "operation must be a string")
    if operation not in OPERATIONS:
        raise ProtocolError("UNKNOWN_OPERATION", f"unsupported operation: {operation}")
    params = payload.get("params", {})
    if not isinstance(params, Mapping):
        raise ProtocolError("BAD_REQUEST", "params must be an object")
    return EnvironmentRequest(
        protocol_version=PROTOCOL_VERSION,
        request_id=request_id,
        operation=operation,
        params=params,
    )


def encode_request(request: EnvironmentRequest) -> bytes:
    return _encode_mapping(request.to_mapping(), limit=MAX_REQUEST_BYTES)


def make_success(
    request: EnvironmentRequest,
    result: Mapping[str, Any],
    *,
    daemon: Mapping[str, Any],
) -> EnvironmentResponse:
    return EnvironmentResponse(
        protocol_version=PROTOCOL_VERSION,
        request_id=request.request_id,
        operation=request.operation,
        status="ok",
        result=result,
        error=None,
        daemon=daemon,
    )


def make_error(
    code: str,
    message: str,
    *,
    request: EnvironmentRequest | None = None,
    daemon: Mapping[str, Any] | None = None,
) -> EnvironmentResponse:
    selected_code = code if code in ERROR_CODES else "INTERNAL_ERROR"
    return EnvironmentResponse(
        protocol_version=PROTOCOL_VERSION,
        request_id=None if request is None else request.request_id,
        operation=None if request is None else request.operation,
        status="error",
        result=None,
        error=EnvironmentError(selected_code, message),
        daemon={} if daemon is None else daemon,
    )


def parse_response_bytes(data: bytes) -> EnvironmentResponse:
    if len(data) > MAX_RESPONSE_BYTES:
        raise ProtocolError("BAD_REQUEST", "response exceeds maximum size")
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("BAD_REQUEST", "response must be valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("BAD_REQUEST", "response root must be an object")
    return parse_response_mapping(payload)


def parse_response_mapping(payload: Mapping[str, Any]) -> EnvironmentResponse:
    unknown = sorted(set(payload) - RESPONSE_FIELDS)
    if unknown:
        raise ProtocolError("BAD_REQUEST", f"unknown response field: {unknown[0]}")
    if payload.get("protocol_version") != PROTOCOL_VERSION:
        raise ProtocolError("UNSUPPORTED_PROTOCOL", "unsupported protocol_version")
    request_id = payload.get("request_id")
    if request_id is not None:
        if not isinstance(request_id, str):
            raise ProtocolError("BAD_REQUEST", "response request_id must be a string or null")
        _validate_request_id(request_id)
    operation = payload.get("operation")
    if operation is not None and not isinstance(operation, str):
        raise ProtocolError("BAD_REQUEST", "response operation must be a string or null")
    status = payload.get("status")
    if status not in {"ok", "error"}:
        raise ProtocolError("BAD_REQUEST", "response status must be ok or error")
    daemon = payload.get("daemon", {})
    if not isinstance(daemon, Mapping):
        raise ProtocolError("BAD_REQUEST", "response daemon must be an object")
    result = payload.get("result")
    error_payload = payload.get("error")
    if status == "ok":
        if not isinstance(result, Mapping):
            raise ProtocolError("BAD_REQUEST", "successful response requires object result")
        if error_payload is not None:
            raise ProtocolError("BAD_REQUEST", "successful response must not include error")
        error = None
    else:
        if result is not None:
            raise ProtocolError("BAD_REQUEST", "error response must not include result")
        if not isinstance(error_payload, Mapping):
            raise ProtocolError("BAD_REQUEST", "error response requires object error")
        code = error_payload.get("code")
        message = error_payload.get("message")
        if not isinstance(code, str) or code not in ERROR_CODES:
            raise ProtocolError("BAD_REQUEST", "error code is unsupported")
        if not isinstance(message, str):
            raise ProtocolError("BAD_REQUEST", "error message must be a string")
        error = EnvironmentError(code, message)
    return EnvironmentResponse(
        protocol_version=PROTOCOL_VERSION,
        request_id=request_id,
        operation=operation,
        status=status,
        result=None if result is None else result,
        error=error,
        daemon=daemon,
    )


def encode_response(response: EnvironmentResponse) -> bytes:
    return _encode_mapping(response.to_mapping(), limit=MAX_RESPONSE_BYTES)


def _encode_mapping(payload: Mapping[str, Any], *, limit: int) -> bytes:
    try:
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError("BAD_REQUEST", "payload is not JSON serializable") from exc
    if len(data) > limit:
        raise ProtocolError("BAD_REQUEST", "payload exceeds maximum size")
    return data


def _validate_request_id(value: str) -> None:
    if not value or len(value) > MAX_REQUEST_ID_LENGTH:
        raise ProtocolError("BAD_REQUEST", "request_id must be 1..64 characters")
    if any(ord(ch) < 32 for ch in value):
        raise ProtocolError("BAD_REQUEST", "request_id must not contain control characters")
