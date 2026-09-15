"""Host-testable V09 environment service core.

The core translates versioned protocol operations into deterministic controller
and policy actions.  It deliberately does not import hardware drivers.  A later
adapter tranche may provide SHT31 and relay implementations behind this single
service boundary.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from time import monotonic
from typing import Callable, Mapping, Any

from .controller import ControllerError, EnvironmentController
from .domain import EnvironmentMode, FanPower, PolicyBounds, SensorQuality, SensorReading
from .policy import EnvironmentPolicy, PolicyError, PolicyStore
from .protocol import EnvironmentRequest
from .simulation import SimulationState, SimulationStateError


class EnvironmentServiceError(RuntimeError):
    """Service operation failed with a stable protocol error code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True, slots=True)
class ServiceIdentity:
    daemon_id: str = "gonken-environment"
    protocol_version: int = 1
    service_version: str = "0.2.0.dev0"
    hardware_backend: str = "host_fake"
    physical_evidence: bool = False
    sensor_backend: str = "host_fake"
    actuator_backend: str = "host_fake"
    sensor_is_simulated: bool = False
    actuator_is_simulated: bool = False
    evidence_mode: str = "HOST_FAKE"

    def as_dict(self) -> dict[str, object]:
        return {
            "daemon_id": self.daemon_id,
            "protocol_version": self.protocol_version,
            "service_version": self.service_version,
            "hardware_backend": self.hardware_backend,
            "physical_evidence": self.physical_evidence,
            "sensor_backend": self.sensor_backend,
            "actuator_backend": self.actuator_backend,
            "sensor_is_simulated": self.sensor_is_simulated,
            "actuator_is_simulated": self.actuator_is_simulated,
            "evidence_mode": self.evidence_mode,
        }


class ScriptedSensorSource:
    """Small deterministic sensor source for host tests and service smoke runs."""

    def __init__(self, readings: list[SensorReading] | tuple[SensorReading, ...]) -> None:
        self._readings = list(readings)
        self._index = 0
        self._lock = threading.Lock()

    def read(self, *, now_monotonic: float) -> SensorReading:
        with self._lock:
            if not self._readings:
                return SensorReading(
                    temperature_c=None,
                    relative_humidity_pct=None,
                    observed_monotonic=now_monotonic,
                    error_code="SENSOR_UNAVAILABLE",
                )
            if self._index < len(self._readings):
                reading = self._readings[self._index]
                self._index += 1
            else:
                reading = self._readings[-1]
        return SensorReading(
            temperature_c=reading.temperature_c,
            relative_humidity_pct=reading.relative_humidity_pct,
            observed_monotonic=now_monotonic,
            sensor_address=reading.sensor_address,
            source_backend=reading.source_backend,
            crc_valid=reading.crc_valid,
            error_code=reading.error_code,
        )


class EnvironmentServiceCore:
    """Single-owner environment service semantics, independent of transport."""

    def __init__(
        self,
        *,
        controller: EnvironmentController,
        bounds: PolicyBounds,
        policy_store: PolicyStore | None = None,
        sensor_read: Callable[..., SensorReading] | None = None,
        sensor_adapter: Any | None = None,
        fan_actuator: Any | None = None,
        now: Callable[[], float] = monotonic,
        identity: ServiceIdentity | None = None,
        simulation_state: SimulationState | None = None,
        simulation_runtime_control_enabled: bool = False,
    ) -> None:
        self.controller = controller
        self.bounds = bounds
        self.policy_store = policy_store
        self.sensor_adapter = sensor_adapter
        if sensor_read is not None:
            self.sensor_read = sensor_read
        elif sensor_adapter is not None:
            self.sensor_read = getattr(sensor_adapter, "read", None)
        else:
            self.sensor_read = None
        self.fan_actuator = fan_actuator
        self.now = now
        self.identity = ServiceIdentity() if identity is None else identity
        self.simulation_state = simulation_state
        self.simulation_runtime_control_enabled = bool(simulation_runtime_control_enabled)
        self._lock = threading.RLock()
        self._request_count = 0
        self._error_count = 0
        self._actuator_error_code: str | None = None
        self._poll_count = 0
        self._poll_error_count = 0
        self._last_poll_monotonic: float | None = None
        self._last_poll_error_code: str | None = None
        self._closed = False

    @classmethod
    def with_defaults(
        cls,
        *,
        bounds: PolicyBounds | None = None,
        now: Callable[[], float] = monotonic,
        sensor_read: Callable[..., SensorReading] | None = None,
        sensor_adapter: Any | None = None,
        fan_actuator: Any | None = None,
    ) -> "EnvironmentServiceCore":
        selected_bounds = PolicyBounds() if bounds is None else bounds
        policy = EnvironmentPolicy.default().validated(bounds=selected_bounds)
        controller = EnvironmentController(policy=policy, bounds=selected_bounds, now_monotonic=now())
        return cls(
            controller=controller,
            bounds=selected_bounds,
            sensor_read=sensor_read,
            sensor_adapter=sensor_adapter,
            fan_actuator=fan_actuator,
            now=now,
        )

    def daemon_metadata(self) -> dict[str, object]:
        meta = self.identity.as_dict()
        meta.update(
            {
                "request_count": self._request_count,
                "error_count": self._error_count,
                "poll_count": self._poll_count,
                "poll_error_count": self._poll_error_count,
                "last_poll_monotonic": self._last_poll_monotonic,
                "last_poll_error_code": self._last_poll_error_code,
                "simulation": self._simulation_payload(),
            }
        )
        return meta

    def handle(self, request: EnvironmentRequest) -> dict[str, object]:
        with self._lock:
            self._request_count += 1
            try:
                return self._handle_locked(request.operation, request.params)
            except (EnvironmentServiceError, ControllerError, PolicyError, SimulationStateError) as exc:
                self._error_count += 1
                code = getattr(exc, "code", "INTERNAL_ERROR")
                raise EnvironmentServiceError(str(code), _public_message(exc)) from exc
            except Exception as exc:  # defensive boundary; no traceback leaks into protocol responses
                self._error_count += 1
                raise EnvironmentServiceError("INTERNAL_ERROR", type(exc).__name__) from exc

    def poll_once(self) -> dict[str, object]:
        """Run one bounded daemon sensor/control/actuator cycle.

        This method is the host-testable unit used by the background polling
        loop.  It never claims physical evidence.  Sensor transport failures are
        converted into structured unavailable readings so the controller can
        apply its fail-closed stale/failure policy.  Actuator failures are
        recorded as degraded poll results instead of terminating the daemon
        thread.
        """

        with self._lock:
            if self._closed:
                raise EnvironmentServiceError("ENV_CLOSED", "environment service core is closed")
            self._poll_count += 1
            now = float(self.now())
            self._last_poll_monotonic = now
            try:
                reading = self._read_sensor_locked(now)
                state = self.controller.observe(reading, now_monotonic=now)
                self._apply_actuator_if_needed(now)
                self._last_poll_error_code = None if reading.is_valid() else reading.error_code
                return {
                    "ok": True,
                    "reading": reading.as_dict(
                        now_monotonic=now,
                        stale_after_seconds=self.controller.stale_after_seconds,
                    ),
                    "state": state.as_dict(
                        now_monotonic=now,
                        stale_after_seconds=self.controller.stale_after_seconds,
                    ),
                    "physical_evidence": False,
                    "provenance": self._provenance_payload(),
                }
            except EnvironmentServiceError as exc:
                self._poll_error_count += 1
                self._last_poll_error_code = exc.code
                return {
                    "ok": False,
                    "error": {"code": exc.code, "message": _public_message(exc)},
                    "state": self.controller.state.as_dict(
                        now_monotonic=now,
                        stale_after_seconds=self.controller.stale_after_seconds,
                    ),
                    "physical_evidence": False,
                    "provenance": self._provenance_payload(),
                }

    def _handle_locked(self, operation: str, params: Mapping[str, Any]) -> dict[str, object]:
        now = float(self.now())
        if operation == "status.get":
            _reject_unknown_params(params, set())
            self.controller.tick(now_monotonic=now)
            return self._status_payload(now)
        if operation == "health.get":
            _reject_unknown_params(params, set())
            self.controller.tick(now_monotonic=now)
            return self._health_payload(now)
        if operation == "sensor.read":
            _reject_unknown_params(params, set())
            reading = self._read_sensor_locked(now)
            state = self.controller.observe(reading, now_monotonic=now)
            self._apply_actuator_if_needed(now)
            return {
                "reading": reading.as_dict(
                    now_monotonic=now,
                    stale_after_seconds=self.controller.stale_after_seconds,
                ),
                "state": state.as_dict(
                    now_monotonic=now,
                    stale_after_seconds=self.controller.stale_after_seconds,
                ),
                "physical_evidence": False,
                "provenance": self._provenance_payload(),
            }
        if operation == "fan.set":
            _reject_unknown_params(params, {"power"})
            power = _required_string(params, "power")
            state = self.controller.set_fan_power(FanPower.parse(power), now_monotonic=now)
            self._apply_actuator_if_needed(now)
            self._save_policy_if_configured()
            return self._state_result(now, state=state)
        if operation == "mode.set":
            _reject_unknown_params(params, {"mode"})
            mode = _required_string(params, "mode")
            state = self.controller.set_mode(EnvironmentMode.parse(mode), now_monotonic=now)
            self._apply_actuator_if_needed(now)
            self._save_policy_if_configured()
            return self._state_result(now, state=state)
        if operation == "policy.get":
            _reject_unknown_params(params, set())
            return {"policy": self.controller.policy.to_mapping(), "bounds": _bounds_mapping(self.bounds), "provenance": self._provenance_payload(), "physical_evidence": False}
        if operation == "policy.update":
            _reject_unknown_params(
                params,
                {
                    "expected_generation",
                    "mode",
                    "start_c",
                    "stop_c",
                    "minimum_on_seconds",
                    "minimum_off_seconds",
                },
            )
            next_policy = self.controller.policy.updated(
                bounds=self.bounds,
                expected_generation=_optional_int(params, "expected_generation"),
                mode=_optional_string(params, "mode"),
                start_c=_optional_float(params, "start_c"),
                stop_c=_optional_float(params, "stop_c"),
                minimum_on_seconds=_optional_int(params, "minimum_on_seconds"),
                minimum_off_seconds=_optional_int(params, "minimum_off_seconds"),
            )
            state = self.controller.update_policy(next_policy, now_monotonic=now)
            self._apply_actuator_if_needed(now)
            self._save_policy_if_configured()
            return self._state_result(now, state=state)
        if operation == "state.snapshot.get":
            _reject_unknown_params(params, set())
            return self._snapshot_payload(now)
        if operation == "events.get":
            _reject_unknown_params(params, {"limit"})
            limit = _optional_int(params, "limit")
            return {"events": self._simulation_events(limit=limit), "provenance": self._provenance_payload(), "physical_evidence": False}
        if operation == "simulation.status.get":
            _reject_unknown_params(params, set())
            return {"simulation": self._simulation_payload(), "provenance": self._provenance_payload(), "physical_evidence": False}
        if operation == "simulation.reset":
            _reject_unknown_params(params, set())
            self._require_simulation_control()
            self._simulation_state().reset_all()
            return {"simulation": self._simulation_payload(), "provenance": self._provenance_payload(), "physical_evidence": False}
        if operation == "simulation.sensor.set":
            _reject_unknown_params(params, {"temperature_c", "relative_humidity_pct"})
            self._require_simulation_control()
            self._require_simulated_sensor_active()
            self._simulation_state().set_sensor(
                temperature_c=_required_float(params, "temperature_c"),
                relative_humidity_pct=_required_float(params, "relative_humidity_pct"),
            )
            return {"simulation": self._simulation_payload(), "provenance": self._provenance_payload(), "physical_evidence": False}
        if operation == "simulation.sensor.fault":
            _reject_unknown_params(params, {"fault", "age_seconds"})
            self._require_simulation_control()
            self._require_simulated_sensor_active()
            self._simulation_state().fault_sensor(
                fault=_required_string(params, "fault"),
                stale_age_seconds=_optional_float(params, "age_seconds"),
            )
            return {"simulation": self._simulation_payload(), "provenance": self._provenance_payload(), "physical_evidence": False}
        if operation == "simulation.sensor.reset":
            _reject_unknown_params(params, set())
            self._require_simulation_control()
            self._require_simulated_sensor_active()
            self._simulation_state().reset_sensor()
            return {"simulation": self._simulation_payload(), "provenance": self._provenance_payload(), "physical_evidence": False}
        if operation == "simulation.actuator.behavior.set":
            _reject_unknown_params(params, {"behavior"})
            self._require_simulation_control()
            self._require_simulated_actuator_active()
            self._simulation_state().set_actuator_behavior(_required_string(params, "behavior"))
            return {"simulation": self._simulation_payload(), "provenance": self._provenance_payload(), "physical_evidence": False}
        if operation == "simulation.actuator.reset":
            _reject_unknown_params(params, set())
            self._require_simulation_control()
            self._require_simulated_actuator_active()
            self._simulation_state().reset_actuator()
            return {"simulation": self._simulation_payload(), "provenance": self._provenance_payload(), "physical_evidence": False}
        if operation == "probe.run":
            _reject_unknown_params(params, set())
            return {
                "probe": "bounded_host_only",
                "destructive": False,
                "hardware_toggled": False,
                "status": "not_implemented_for_physical_hardware",
                "provenance": self._provenance_payload(),
                "physical_evidence": False,
            }
        raise EnvironmentServiceError("UNKNOWN_OPERATION", f"unsupported operation: {operation}")

    def _status_payload(self, now: float) -> dict[str, object]:
        return {
            "service": "READY",
            "environment": self._overall_environment_state(),
            "state": self.controller.state.as_dict(
                now_monotonic=now,
                stale_after_seconds=self.controller.stale_after_seconds,
            ),
            "capabilities": self._capabilities_payload(),
            "physical_evidence": False,
            "provenance": self._provenance_payload(),
        }

    def _health_payload(self, now: float) -> dict[str, object]:
        sensor_quality = self.controller.state.sensor_quality
        return {
            "process_alive": True,
            "ipc_ready": True,
            "policy_valid": True,
            "sensor": sensor_quality.value,
            "actuator": self._actuator_health(),
            "controller": "ACTIVE" if sensor_quality == SensorQuality.READY else "SUSPENDED_OR_STARTING",
            "overall": self._overall_environment_state(),
            "polling": self._polling_payload(),
            "state": self.controller.state.as_dict(
                now_monotonic=now,
                stale_after_seconds=self.controller.stale_after_seconds,
            ),
            "physical_evidence": False,
            "provenance": self._provenance_payload(),
        }

    def _state_result(self, now: float, *, state) -> dict[str, object]:
        return {
            "state": state.as_dict(
                now_monotonic=now,
                stale_after_seconds=self.controller.stale_after_seconds,
            ),
            "policy": self.controller.policy.to_mapping(),
            "physical_evidence": False,
            "provenance": self._provenance_payload(),
        }

    def _overall_environment_state(self) -> str:
        quality = self.controller.state.sensor_quality
        if quality == SensorQuality.READY:
            return "READY"
        if quality in {SensorQuality.FAILED, SensorQuality.STALE, SensorQuality.UNAVAILABLE}:
            return "DEGRADED"
        return "STARTING"

    def _capabilities_payload(self) -> dict[str, bool]:
        if self.fan_actuator is not None:
            capabilities = getattr(self.fan_actuator, "capabilities", None)
            if callable(capabilities):
                return capabilities().as_dict()
        return self.controller.state.capability.as_dict()

    def _actuator_health(self) -> str:
        if self._actuator_error_code is not None:
            return "UNAVAILABLE"
        if self.fan_actuator is None:
            return "HOST_FAKE"
        return "READY"

    def _polling_payload(self) -> dict[str, object]:
        return {
            "poll_count": self._poll_count,
            "poll_error_count": self._poll_error_count,
            "last_poll_monotonic": self._last_poll_monotonic,
            "last_poll_error_code": self._last_poll_error_code,
        }

    def _snapshot_payload(self, now: float) -> dict[str, object]:
        return {
            "service": "READY",
            "environment": self._overall_environment_state(),
            "state": self.controller.state.as_dict(
                now_monotonic=now,
                stale_after_seconds=self.controller.stale_after_seconds,
            ),
            "capabilities": self._capabilities_payload(),
            "polling": self._polling_payload(),
            "physical_evidence": False,
            "provenance": self._provenance_payload(),
        }

    def _provenance_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "sensor_backend": self.identity.sensor_backend,
            "actuator_backend": self.identity.actuator_backend,
            "sensor_is_simulated": self.identity.sensor_is_simulated,
            "actuator_is_simulated": self.identity.actuator_is_simulated,
            "physical_evidence": self.identity.physical_evidence,
            "evidence_mode": self.identity.evidence_mode,
        }
        if self.simulation_state is not None:
            payload.update({
                "simulation_session_id": self.simulation_state.session_id,
                "simulation_generation": self.simulation_state.generation,
            })
        else:
            payload.update({
                "simulation_session_id": None,
                "simulation_generation": None,
            })
        return payload

    def _simulation_payload(self) -> dict[str, object]:
        if self.simulation_state is None:
            return {
                "active": False,
                "runtime_control_enabled": self.simulation_runtime_control_enabled,
                "sensor_is_simulated": self.identity.sensor_is_simulated,
                "actuator_is_simulated": self.identity.actuator_is_simulated,
                "physical_evidence": False,
            }
        payload = self.simulation_state.as_dict()
        payload.update({
            "active": True,
            "runtime_control_enabled": self.simulation_runtime_control_enabled,
            "sensor_is_simulated": self.identity.sensor_is_simulated,
            "actuator_is_simulated": self.identity.actuator_is_simulated,
            "evidence_mode": self.identity.evidence_mode,
            "physical_evidence": False,
        })
        return payload

    def _simulation_events(self, *, limit: int | None = None) -> list[dict[str, object]]:
        if self.simulation_state is None:
            return []
        return self.simulation_state.events(limit=limit)

    def _simulation_state(self) -> SimulationState:
        if self.simulation_state is None:
            raise EnvironmentServiceError("SIMULATION_DISABLED", "simulation is not active for this daemon")
        return self.simulation_state

    def _require_simulation_control(self) -> None:
        if not self.simulation_runtime_control_enabled:
            raise EnvironmentServiceError("SIMULATION_DISABLED", "simulation runtime control is disabled")
        self._simulation_state()

    def _require_simulated_sensor_active(self) -> None:
        if not self.identity.sensor_is_simulated:
            raise EnvironmentServiceError("SIMULATION_SENSOR_NOT_ACTIVE", "sensor backend is not simulated")

    def _require_simulated_actuator_active(self) -> None:
        if not self.identity.actuator_is_simulated:
            raise EnvironmentServiceError("SIMULATION_ACTUATOR_NOT_ACTIVE", "actuator backend is not simulated")

    def _read_sensor_locked(self, now: float) -> SensorReading:
        if self.sensor_read is None:
            return SensorReading(
                temperature_c=None,
                relative_humidity_pct=None,
                observed_monotonic=now,
                error_code="SENSOR_UNAVAILABLE",
            )
        try:
            reading = self.sensor_read(now_monotonic=now)
        except Exception as exc:
            code = str(getattr(exc, "code", "SENSOR_READ_FAILED"))
            if not code or code == "None":
                code = "SENSOR_READ_FAILED"
            return SensorReading(
                temperature_c=None,
                relative_humidity_pct=None,
                observed_monotonic=now,
                error_code=code,
            )
        if not isinstance(reading, SensorReading):
            return SensorReading(
                temperature_c=None,
                relative_humidity_pct=None,
                observed_monotonic=now,
                error_code="SENSOR_READ_FAILED",
            )
        return reading

    def _apply_actuator_if_needed(self, now: float) -> None:
        if self.fan_actuator is None:
            return
        try:
            self.fan_actuator.set_power(self.controller.state.fan_power)
        except Exception as exc:
            self._actuator_error_code = "ACTUATOR_UNAVAILABLE"
            try:
                safe_off = getattr(self.fan_actuator, "safe_off", None)
                if callable(safe_off):
                    safe_off()
            except Exception:
                pass
            self.controller.actuator_error_safe_off(now_monotonic=now)
            raise EnvironmentServiceError("ACTUATOR_UNAVAILABLE", _public_message(exc)) from exc
        self._actuator_error_code = None

    def _save_policy_if_configured(self) -> None:
        if self.policy_store is not None:
            self.policy_store.save(self.controller.policy)

    def shutdown_safe_off(self) -> None:
        """Best-effort safe OFF and adapter cleanup for daemon shutdown."""

        with self._lock:
            if self._closed:
                return
            now = float(self.now())
            self.controller.shutdown(now_monotonic=now)
            if self.fan_actuator is not None:
                try:
                    safe_off = getattr(self.fan_actuator, "safe_off", None)
                    if callable(safe_off):
                        safe_off()
                except Exception:
                    self._actuator_error_code = "ACTUATOR_UNAVAILABLE"
                try:
                    close = getattr(self.fan_actuator, "close", None)
                    if callable(close):
                        close()
                except Exception:
                    self._actuator_error_code = "ACTUATOR_UNAVAILABLE"
            if self.sensor_adapter is not None:
                try:
                    close = getattr(self.sensor_adapter, "close", None)
                    if callable(close):
                        close()
                except Exception:
                    pass
            self._closed = True



class EnvironmentPollingLoop:
    """Bounded background polling scaffold for gonken-environment.service."""

    def __init__(
        self,
        core: EnvironmentServiceCore,
        *,
        interval_seconds: float,
        thread_name: str = "gonken-environment-poll",
    ) -> None:
        if not isinstance(interval_seconds, (int, float)) or isinstance(interval_seconds, bool):
            raise ValueError("interval_seconds must be a number")
        if float(interval_seconds) <= 0:
            raise ValueError("interval_seconds must be positive")
        self.core = core
        self.interval_seconds = float(interval_seconds)
        self.thread_name = thread_name
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.last_result: dict[str, object] | None = None

    @property
    def running(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def run_once(self) -> dict[str, object]:
        self.last_result = self.core.poll_once()
        return self.last_result

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name=self.thread_name, daemon=True)
            self._thread.start()

    def stop(self, *, timeout_seconds: float = 5.0) -> None:
        with self._lock:
            thread = self._thread
            self._stop_event.set()
        if thread is not None:
            thread.join(timeout=timeout_seconds)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            self._stop_event.wait(self.interval_seconds)



def _reject_unknown_params(params: Mapping[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise EnvironmentServiceError("BAD_REQUEST", f"unknown parameter: {unknown[0]}")


def _required_string(params: Mapping[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str):
        raise EnvironmentServiceError("BAD_REQUEST", f"{key} must be a string")
    if not value.strip():
        raise EnvironmentServiceError("BAD_REQUEST", f"{key} must not be empty")
    return value


def _optional_string(params: Mapping[str, Any], key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise EnvironmentServiceError("BAD_REQUEST", f"{key} must be a non-empty string")
    return value


def _required_float(params: Mapping[str, Any], key: str) -> float:
    value = params.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EnvironmentServiceError("BAD_REQUEST", f"{key} must be a number")
    return float(value)


def _optional_float(params: Mapping[str, Any], key: str) -> float | None:
    value = params.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EnvironmentServiceError("BAD_REQUEST", f"{key} must be a number")
    return float(value)


def _optional_int(params: Mapping[str, Any], key: str) -> int | None:
    value = params.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise EnvironmentServiceError("BAD_REQUEST", f"{key} must be an integer")
    return value


def _bounds_mapping(bounds: PolicyBounds) -> dict[str, object]:
    return {
        "temperature_min_c": bounds.temperature_min_c,
        "temperature_max_c": bounds.temperature_max_c,
        "minimum_hysteresis_c": bounds.minimum_hysteresis_c,
        "maximum_hysteresis_c": bounds.maximum_hysteresis_c,
        "minimum_dwell_seconds": bounds.minimum_dwell_seconds,
        "maximum_dwell_seconds": bounds.maximum_dwell_seconds,
    }


def _public_message(exc: BaseException) -> str:
    text = str(exc)
    if ": " in text:
        return text.split(": ", 1)[1]
    return text
