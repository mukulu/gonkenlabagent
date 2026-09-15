"""Client for the bounded local V09 environment IPC protocol."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any, Mapping

from .protocol import (
    MAX_RESPONSE_BYTES,
    EnvironmentResponse,
    ProtocolError,
    encode_request,
    make_request,
    parse_response_bytes,
)


class EnvironmentClientError(RuntimeError):
    """The local environment daemon could not be contacted or rejected a call."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class EnvironmentClient:
    def __init__(self, socket_path: str | Path, *, timeout_seconds: float = 2.0) -> None:
        self.socket_path = str(socket_path)
        self.timeout_seconds = float(timeout_seconds)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def call(self, operation: str, params: Mapping[str, Any] | None = None) -> EnvironmentResponse:
        request = make_request(operation, params)
        payload = encode_request(request) + b"\n"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout_seconds)
                sock.connect(self.socket_path)
                sock.sendall(payload)
                sock.shutdown(socket.SHUT_WR)
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES + 1:
                        raise ProtocolError("BAD_REQUEST", "response exceeds maximum size")
        except TimeoutError as exc:
            raise EnvironmentClientError("TIMEOUT", "environment service call timed out") from exc
        except OSError as exc:
            raise EnvironmentClientError("ENV_UNAVAILABLE", type(exc).__name__) from exc
        response = parse_response_bytes(b"".join(chunks).rstrip(b"\n"))
        if response.status == "error" and response.error is not None:
            raise EnvironmentClientError(response.error.code, response.error.message)
        return response

    def status(self) -> Mapping[str, Any]:
        return _result(self.call("status.get"))

    def health(self) -> Mapping[str, Any]:
        return _result(self.call("health.get"))

    def read_sensor(self) -> Mapping[str, Any]:
        return _result(self.call("sensor.read"))

    def fan_set(self, power: str) -> Mapping[str, Any]:
        return _result(self.call("fan.set", {"power": power}))

    def mode_set(self, mode: str) -> Mapping[str, Any]:
        return _result(self.call("mode.set", {"mode": mode}))

    def policy_get(self) -> Mapping[str, Any]:
        return _result(self.call("policy.get"))

    def policy_update(self, **params: Any) -> Mapping[str, Any]:
        return _result(self.call("policy.update", params))

    def snapshot(self) -> Mapping[str, Any]:
        return _result(self.call("state.snapshot.get"))

    def events(self, *, limit: int | None = None) -> Mapping[str, Any]:
        params = {} if limit is None else {"limit": limit}
        return _result(self.call("events.get", params))

    def simulation_status(self) -> Mapping[str, Any]:
        return _result(self.call("simulation.status.get"))

    def simulation_reset(self) -> Mapping[str, Any]:
        return _result(self.call("simulation.reset"))

    def simulation_sensor_set(self, *, temperature_c: float, relative_humidity_pct: float) -> Mapping[str, Any]:
        return _result(
            self.call(
                "simulation.sensor.set",
                {"temperature_c": temperature_c, "relative_humidity_pct": relative_humidity_pct},
            )
        )

    def simulation_sensor_fault(self, fault: str, *, age_seconds: float | None = None) -> Mapping[str, Any]:
        params: dict[str, Any] = {"fault": fault}
        if age_seconds is not None:
            params["age_seconds"] = age_seconds
        return _result(self.call("simulation.sensor.fault", params))

    def simulation_sensor_reset(self) -> Mapping[str, Any]:
        return _result(self.call("simulation.sensor.reset"))

    def simulation_actuator_behavior_set(self, behavior: str) -> Mapping[str, Any]:
        return _result(self.call("simulation.actuator.behavior.set", {"behavior": behavior}))

    def simulation_actuator_reset(self) -> Mapping[str, Any]:
        return _result(self.call("simulation.actuator.reset"))


def _result(response: EnvironmentResponse) -> Mapping[str, Any]:
    if response.result is None:
        raise EnvironmentClientError("INTERNAL_ERROR", "successful response omitted result")
    return response.result
