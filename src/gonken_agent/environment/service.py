"""Host-testable V09 environment service core.

The core translates versioned protocol operations into deterministic controller
and policy actions.  It deliberately does not import hardware drivers.  A later
adapter tranche may provide SHT31 and relay implementations behind this single
service boundary.
"""

from __future__ import annotations

import os
import secrets
import threading
from dataclasses import dataclass
from time import monotonic
from typing import Callable, Mapping, Any

from .automation import Automation, AutomationError, FAN_KINDS
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
    release_commit: str = "unknown"
    release_profile: str = "unknown"
    configuration_sha256: str = "unknown"

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
            "release_commit": self.release_commit,
            "release_profile": self.release_profile,
            "configuration_sha256": self.configuration_sha256,
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
        event_sink: Callable[[Mapping[str, object]], None] | None = None,
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
        self._transition_sequence = 0
        self._transition_events: list[dict[str, object]] = []
        self._last_transition_key: tuple[str, float] | None = (
            self.controller.state.last_transition_reason.value,
            self.controller.state.last_transition_monotonic,
        )
        self._closed = False
        self._event_sink = event_sink
        self._event_delivery_errors = 0
        self._actuator_command_count = 0
        self._actuator_write_errors = 0
        self._last_actuator_command: FanPower | None = None
        self._last_actuator_requested: FanPower | None = None
        self._last_actuator_command_reason: str | None = None
        self._last_actuator_command_monotonic: float | None = None
        self._last_actuator_write_result = "NOT_ATTEMPTED"
        self._last_actuator_error_event: float | None = None
        self.automation = Automation()
        self._power_hold: dict | None = None

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
            except (EnvironmentServiceError, ControllerError, PolicyError, SimulationStateError, AutomationError) as exc:
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
                self._expire_power_hold(now)
                reading = self._read_sensor_locked(now)
                state = self.controller.observe(reading, now_monotonic=now)
                self._apply_actuator_if_needed(now)
                self._record_controller_transition_if_changed(now, self.controller.state)
                self._tick_automation(now)
                state = self.controller.state
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
                self.automation.cancel(now=now, fan_only=True)
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
        if self._power_hold is not None and operation in {"fan.set", "mode.set", "policy.update", "automation.add"}:
            raise EnvironmentServiceError("BUSY", "power transition is pending")
        if operation.startswith(("automation.", "notifications.", "power.")):
            return self._automation_operation(operation, params, now)
        if operation == "status.get":
            _reject_unknown_params(params, set())
            return self._status_payload(now)
        if operation == "health.get":
            _reject_unknown_params(params, set())
            return self._health_payload(now)
        if operation == "sensor.read":
            _reject_unknown_params(params, set())
            reading = self._read_sensor_locked(now)
            state = self.controller.observe(reading, now_monotonic=now)
            self._apply_actuator_if_needed(now)
            self._record_controller_transition_if_changed(now, self.controller.state)
            return {
                "announcement_token": self.automation.reading_receipt(self._public_state(now), now=now),
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
            selected_power = FanPower.parse(power)
            self.automation.cancel(now=now, fan_only=True)
            state = self.controller.set_fan_power(selected_power, now_monotonic=now)
            self._apply_actuator_if_needed(now)
            self._record_controller_transition_if_changed(now, self.controller.state)
            self._save_policy_if_configured()
            return self._state_result(now, state=state)
        if operation == "mode.set":
            _reject_unknown_params(params, {"mode"})
            mode = _required_string(params, "mode")
            selected_mode = EnvironmentMode.parse(mode)
            self.automation.cancel(now=now, fan_only=True)
            state = self.controller.set_mode(selected_mode, now_monotonic=now)
            self._apply_actuator_if_needed(now)
            self._record_controller_transition_if_changed(now, self.controller.state)
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
            self.automation.cancel(now=now, fan_only=True)
            state = self.controller.update_policy(next_policy, now_monotonic=now)
            self._apply_actuator_if_needed(now)
            self._record_controller_transition_if_changed(now, self.controller.state)
            self._save_policy_if_configured()
            return self._state_result(now, state=state)
        if operation == "state.snapshot.get":
            _reject_unknown_params(params, set())
            return self._snapshot_payload(now)
        if operation == "events.get":
            _reject_unknown_params(params, {"limit"})
            limit = _optional_int(params, "limit")
            return {"events": self._events_payload(limit=limit), "provenance": self._provenance_payload(), "physical_evidence": False}
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

    def _scheduled_fan_write(self, power: str, reason: str) -> None:
        now = float(self.now())
        if self.fan_actuator is None:
            raise EnvironmentServiceError("ACTUATOR_UNAVAILABLE", "no actuator is configured")
        self.controller.scheduled_fan_power(FanPower.parse(power), now_monotonic=now,
                                            expired=reason == "TIMER_EXPIRED_SAFE_OFF")
        self._apply_actuator_if_needed(now)
        self._record_controller_transition_if_changed(now, self.controller.state)
        # Timer control mode is session-local, not a persisted policy rewrite.

    def _tick_automation(self, now: float) -> None:
        if self._power_hold is not None:
            return
        policy = self.controller.policy
        self.automation.tick(now=now, snapshot=self._public_state(now),
                             minimum_on=policy.minimum_on_seconds, minimum_off=policy.minimum_off_seconds,
                             fan_write=self._scheduled_fan_write)

    def _expire_power_hold(self, now: float) -> None:
        if self._power_hold is not None and now >= self._power_hold["expires"]:
            self._restore_power_hold(now)

    def _restore_power_hold(self, now: float) -> None:
        hold, self._power_hold = self._power_hold, None
        if hold is not None:
            policy = self.controller.policy.updated(bounds=self.bounds, mode=hold["previous_mode"])
            self.controller.update_policy(policy, now_monotonic=now)
            self._apply_actuator_if_needed(now)
            self._record_controller_transition_if_changed(now, self.controller.state)

    def _automation_operation(self, operation: str, params: Mapping[str, Any], now: float) -> dict:
        if operation == "automation.add":
            policy = self.controller.policy
            job = self.automation.add(params, now=now, snapshot=self._public_state(now),
                                      minimum_on=policy.minimum_on_seconds, minimum_off=policy.minimum_off_seconds)
            return {"job": job, "generation": self.automation.generation, "persistent": False}
        if operation == "automation.list":
            _reject_unknown_params(params, set())
            return self.automation.status(now=now)
        if operation == "automation.cancel":
            _reject_unknown_params(params, {"id"})
            job_id = _optional_string(params, "id")
            active = any(j.kind in FAN_KINDS and j.phase == "on" and (job_id is None or job_id == j.id)
                         for j in self.automation.jobs.values())
            cancelled = self.automation.cancel(now=now, job_id=job_id)
            if active:
                self._scheduled_fan_write("off", "TIMER_EXPIRED_SAFE_OFF")
            return {"cancelled": cancelled, "safe_off_requested": active, "persistent": False}
        if operation == "notifications.get":
            _reject_unknown_params(params, set())
            return self.automation.pending_notifications(now=now)
        if operation == "notifications.ack":
            _reject_unknown_params(params, {"id", "generation"})
            ok = self.automation.acknowledge(_required_string(params,"id"), _required_string(params,"generation"), now=now)
            return {"acknowledged": ok}
        if operation == "power.prepare":
            _reject_unknown_params(params, {"action"})
            action = _required_string(params, "action")
            if action not in {"REBOOT_DEVICE", "POWEROFF_DEVICE"}:
                raise EnvironmentServiceError("BAD_REQUEST", "invalid power action")
            if self._power_hold is not None:
                raise EnvironmentServiceError("BUSY", "power transition already pending")
            if self.fan_actuator is None:
                raise EnvironmentServiceError("ACTUATOR_UNAVAILABLE", "safe OFF cannot be acknowledged")
            token = secrets.token_hex(16)
            self._power_hold = {"token": token, "expires": now + 30, "previous_mode": self.controller.policy.mode.value}
            self.automation.cancel(now=now)
            self.controller.set_mode(EnvironmentMode.DISABLED, now_monotonic=now)
            self._apply_actuator_if_needed(now)
            self._record_controller_transition_if_changed(now, self.controller.state)
            if self._last_actuator_command != FanPower.OFF or self._last_actuator_write_result != "SUCCESS":
                raise EnvironmentServiceError("ACTUATOR_UNAVAILABLE", "safe OFF was not acknowledged")
            return {"token": token, "safe_off_acknowledged": True, "expires_in_seconds": 30,
                    "generation": self.automation.generation, "action": action, "physical_acceptance_claimed": False}
        if operation == "power.release":
            _reject_unknown_params(params, {"token"})
            token = _required_string(params, "token")
            if self._power_hold is None or not secrets.compare_digest(token, self._power_hold["token"]):
                raise EnvironmentServiceError("BAD_REQUEST", "unknown power transition")
            self._restore_power_hold(now)
            return {"released": True}
        raise EnvironmentServiceError("UNKNOWN_OPERATION", "unsupported operation")

    def _observed_sensor_quality(self, now: float) -> SensorQuality:
        quality = self.controller.state.sensor_quality
        reading = self.controller.state.last_reading
        if quality == SensorQuality.READY and reading is not None:
            return reading.quality(now_monotonic=now, stale_after_seconds=self.controller.stale_after_seconds)
        return quality

    def _public_state(self, now: float) -> dict[str, object]:
        payload = self.controller.state.as_dict(now_monotonic=now,
                                              stale_after_seconds=self.controller.stale_after_seconds)
        payload["sensor_quality"] = self._observed_sensor_quality(now).value
        return payload

    def _actuator_command_payload(self) -> dict[str, object]:
        transport = {}
        diagnostics = getattr(self.fan_actuator, "command_diagnostics", None)
        if callable(diagnostics):
            try:
                value = diagnostics()
                if isinstance(value, Mapping):
                    transport = dict(value)
            except Exception:
                transport = {"last_write_result": "DIAGNOSTICS_UNAVAILABLE", "relay_commanded": None}
        acknowledged = self._last_actuator_command.value if self._last_actuator_command is not None else None
        return {
            "controller_desired": self.controller.state.fan_power.value,
            "relay_commanded": transport.get("relay_commanded", acknowledged),
            "last_actuator_requested": self._last_actuator_requested.value if self._last_actuator_requested else None,
            "last_actuator_command": acknowledged,
            "last_actuator_command_reason": self._last_actuator_command_reason,
            "last_actuator_command_monotonic": self._last_actuator_command_monotonic,
            "actuator_command_count": self._actuator_command_count,
            "actuator_write_errors": self._actuator_write_errors,
            "last_command_result": self._last_actuator_write_result,
            "last_write_result": self._last_actuator_write_result,
            "event_delivery_errors": self._event_delivery_errors,
            "event_queue_drops": getattr(self._event_sink, "dropped_events", 0),
            "actuator_simulated": self.identity.actuator_is_simulated,
            **transport,
            "fan_motion_observed": False, "physical_evidence": False,
        }

    def _emit_actuator_event(self, now: float, code: str, previous: FanPower | None,
                             requested: FanPower, result: str, *, safe_off_result: str | None = None) -> None:
        if self._event_sink is None:
            return
        identity = self._actuator_runtime_identity()
        state, policy = self.controller.state, self.controller.policy
        event = {"code": code, "backend": self.identity.actuator_backend,
                 "release_commit": self.identity.release_commit,
                 "configuration_sha256": self.identity.configuration_sha256,
                 "process_id": os.getpid(),
                 "actuator_simulated": self.identity.actuator_is_simulated,
                 "gpio": identity.get("line_name"), "gpio_claimed": identity.get("gpio_claimed"),
                 "gpio_consumer": identity.get("gpio_consumer"),
                 "previous": previous.value if previous is not None else None,
                 "requested": requested.value,
                 "relay_commanded": self._actuator_command_payload()["relay_commanded"],
                 "reason": state.last_transition_reason.value, "mode": state.mode.value,
                 "monotonic": now, "control_temperature_c": state.control_temperature_c,
                 "start_c": policy.start_c, "stop_c": policy.stop_c,
                 "write_result": result, "safe_off_result": safe_off_result,
                 "actuator_write_errors": self._actuator_write_errors,
                 "fan_motion_observed": False, "physical_evidence": False}
        try:
            self._event_sink(event)
        except Exception:
            # Diagnostics may fail; they are never authority to interrupt control.
            self._event_delivery_errors += 1

    def _status_payload(self, now: float) -> dict[str, object]:
        return {
            "service": "READY",
            "environment": self._overall_environment_state(now),
            "state": self._public_state(now),
            "capabilities": self._capabilities_payload(),
            "actuator_runtime_identity": self._actuator_runtime_identity(),
            "actuator_commands": self._actuator_command_payload(),
            "physical_evidence": False,
            "provenance": self._provenance_payload(),
        }

    def _health_payload(self, now: float) -> dict[str, object]:
        sensor_quality = self._observed_sensor_quality(now)
        return {
            "process_alive": True,
            "ipc_ready": True,
            "policy_valid": True,
            "sensor": sensor_quality.value,
            "actuator": self._actuator_health(),
            "actuator_runtime_identity": self._actuator_runtime_identity(),
            "actuator_commands": self._actuator_command_payload(),
            "controller": "ACTIVE" if sensor_quality == SensorQuality.READY and self._actuator_error_code is None else "SUSPENDED_OR_STARTING",
            "overall": self._overall_environment_state(now),
            "automation": {"jobs": len(self.automation.jobs), "generation": self.automation.generation,
                           "notifications": len(self.automation.notices), "persistent": False,
                           "power_pending": self._power_hold is not None},
            "polling": self._polling_payload(),
            "state": self._public_state(now),
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

    def _overall_environment_state(self, now: float | None = None) -> str:
        if self._actuator_error_code is not None or self._closed:
            return "DEGRADED"
        quality = self._observed_sensor_quality(float(self.now()) if now is None else now)
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

    def _actuator_runtime_identity(self) -> dict[str, object]:
        """Return non-actuating runtime actuator identity for diagnostics.

        A simulated actuator has no physical GPIO identity.  A physical adapter
        may expose a resolver that inspects kernel line metadata, but this
        operation must not request or write the line.  Failure to resolve is
        reported as target evidence still required rather than hidden behind a
        guessed gpiochip/offset.
        """
        if self.identity.actuator_is_simulated:
            return {
                "status": "NOT_APPLICABLE",
                "backend": self.identity.actuator_backend,
                "physical_acceptance_claimed": False,
            }
        actuator = self.fan_actuator
        if actuator is None:
            return {
                "status": "UNAVAILABLE",
                "backend": self.identity.actuator_backend,
                "code": "ACTUATOR_RUNTIME_IDENTITY_UNAVAILABLE",
                "physical_acceptance_claimed": False,
            }
        resolver = getattr(actuator, "resolved_identity", None)
        if not callable(resolver):
            return {
                "status": "UNRESOLVED",
                "backend": self.identity.actuator_backend,
                "code": "ACTUATOR_RUNTIME_IDENTITY_UNSUPPORTED",
                "physical_acceptance_claimed": False,
            }
        try:
            resolved = resolver()
        except Exception as exc:  # diagnostics must remain available on mapping failure
            code = getattr(exc, "code", "ACTUATOR_RUNTIME_IDENTITY_UNRESOLVED")
            return {
                "status": "UNRESOLVED",
                "backend": self.identity.actuator_backend,
                "code": str(code),
                "physical_acceptance_claimed": False,
            }
        if not isinstance(resolved, Mapping):
            return {
                "status": "UNRESOLVED",
                "backend": self.identity.actuator_backend,
                "code": "ACTUATOR_RUNTIME_IDENTITY_INVALID",
                "physical_acceptance_claimed": False,
            }
        payload = dict(resolved)
        payload["status"] = "RESOLVED"
        payload.setdefault("backend", self.identity.actuator_backend)
        payload["physical_acceptance_claimed"] = False
        return payload

    def _snapshot_payload(self, now: float) -> dict[str, object]:
        return {
            "service": "READY",
            "environment": self._overall_environment_state(now),
            "state": self._public_state(now),
            "capabilities": self._capabilities_payload(),
            "polling": self._polling_payload(),
            "actuator_runtime_identity": self._actuator_runtime_identity(),
            "actuator_commands": self._actuator_command_payload(),
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
            "release_commit": self.identity.release_commit,
            "release_profile": self.identity.release_profile,
            "configuration_sha256": self.identity.configuration_sha256,
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
            "release_commit": self.identity.release_commit,
            "release_profile": self.identity.release_profile,
            "configuration_sha256": self.identity.configuration_sha256,
            "physical_evidence": False,
        })
        return payload

    def _events_payload(self, *, limit: int | None = None) -> list[dict[str, object]]:
        events = [*self._transition_events, *self._simulation_events(limit=None)]
        events.sort(key=lambda item: float(item.get("monotonic", 0.0)))
        if limit is not None:
            events = events[-max(0, int(limit)):]
        return events

    def _record_controller_transition_if_changed(self, now: float, state: Any) -> None:
        reason = getattr(getattr(state, "last_transition_reason", ""), "value", str(getattr(state, "last_transition_reason", "")))
        transitioned_at = float(getattr(state, "last_transition_monotonic", now))
        key = (str(reason), transitioned_at)
        if key == self._last_transition_key:
            return
        self._last_transition_key = key
        self._transition_sequence += 1
        self._transition_events.append({
            "sequence": self._transition_sequence,
            "source": "controller",
            "event_type": "controller.transition",
            "monotonic": float(now),
            "detail": {
                "reason": str(reason),
                "mode": getattr(getattr(state, "mode", ""), "value", str(getattr(state, "mode", ""))),
                "fan_power": getattr(getattr(state, "fan_power", ""), "value", str(getattr(state, "fan_power", ""))),
                "sensor_quality": getattr(getattr(state, "sensor_quality", ""), "value", str(getattr(state, "sensor_quality", ""))),
                "last_transition_monotonic": transitioned_at,
            },
            "provenance": self._provenance_payload(),
            "physical_evidence": False,
        })
        if len(self._transition_events) > 128:
            del self._transition_events[: len(self._transition_events) - 128]

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
        requested = self.controller.state.fan_power
        previous = self._last_actuator_command
        recovered = self._actuator_error_code is not None
        self._last_actuator_requested = requested
        try:
            self.fan_actuator.set_power(requested)
        except Exception as exc:
            self._actuator_error_code = "ACTUATOR_UNAVAILABLE"
            self._actuator_write_errors += 1
            self._last_actuator_command = None
            self._last_actuator_write_result = "FAILED"
            safe_result = "UNAVAILABLE"
            try:
                safe_off = getattr(self.fan_actuator, "safe_off", None)
                if callable(safe_off):
                    safe_off()
                    self._last_actuator_command = FanPower.OFF
                    safe_result = "SUCCESS"
            except Exception:
                self._actuator_write_errors += 1
                safe_result = "FAILED"
            self.controller.actuator_error_safe_off(now_monotonic=now)
            if safe_result == "SUCCESS":
                self._actuator_command_count += 1
                self._last_actuator_command_monotonic = now
                self._last_actuator_command_reason = self.controller.state.last_transition_reason.value
            if self._last_actuator_error_event is None or now - self._last_actuator_error_event >= 60:
                self._emit_actuator_event(now, "ENV_ACTUATOR_WRITE_FAILED", previous, requested, "FAILED", safe_off_result=safe_result)
                self._last_actuator_error_event = now
            raise EnvironmentServiceError("ACTUATOR_UNAVAILABLE", _public_message(exc)) from exc
        self._actuator_error_code = None
        self._last_actuator_error_event = None
        self._last_actuator_write_result = "SUCCESS"
        self._last_actuator_command = requested
        if previous != requested or recovered:
            self._actuator_command_count += 1
            self._last_actuator_command_monotonic = now
            self._last_actuator_command_reason = self.controller.state.last_transition_reason.value
            self._emit_actuator_event(now, "ENV_ACTUATOR_TRANSITION", previous, requested, "SUCCESS")

    def _save_policy_if_configured(self) -> None:
        if self.policy_store is not None:
            self.policy_store.save(self.controller.policy)

    def shutdown_safe_off(self) -> None:
        """Sole-owner OFF acknowledgement, then line release and sensor cleanup."""

        with self._lock:
            if self._closed:
                return
            now = float(self.now())
            self.automation.cancel(now=now)
            self._power_hold = None
            previous = self._last_actuator_command
            self.controller.shutdown(now_monotonic=now)
            if self.fan_actuator is not None:
                self._last_actuator_requested = FanPower.OFF
                try:
                    safe_off = getattr(self.fan_actuator, "safe_off", None)
                    if not callable(safe_off):
                        raise RuntimeError("ACTUATOR_SAFE_OFF_UNAVAILABLE")
                    safe_off()
                    self._last_actuator_command = FanPower.OFF
                    self._last_actuator_command_monotonic = now
                    self._last_actuator_command_reason = self.controller.state.last_transition_reason.value
                    self._last_actuator_write_result = "SUCCESS"
                    self._actuator_command_count += 1
                    self._emit_actuator_event(now, "ENV_ACTUATOR_TRANSITION", previous, FanPower.OFF, "SUCCESS")
                except Exception:
                    self._actuator_error_code = "ACTUATOR_UNAVAILABLE"
                    self._actuator_write_errors += 1
                    self._last_actuator_command = None
                    self._last_actuator_write_result = "FAILED"
                    self._emit_actuator_event(now, "ENV_ACTUATOR_WRITE_FAILED", previous, FanPower.OFF, "FAILED",
                                              safe_off_result="FAILED")
                try:
                    close = getattr(self.fan_actuator, "close", None)
                    if callable(close):
                        close()
                except Exception:
                    self._actuator_error_code = "ACTUATOR_UNAVAILABLE"
                    self._actuator_write_errors += 1
                    self._last_actuator_write_result = "RELEASE_FAILED"
                    self._last_actuator_command = None
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
