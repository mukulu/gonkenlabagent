"""Activation scaffold for ``gonken-environment.service``.

This module assembles the daemon-owned V09 environment controller from the
validated static configuration, daemon policy storage, SHT31 sensor adapter and
libgpiod relay actuator.  It is intentionally still evidence-conservative:
``physical_evidence`` remains ``False`` until a supervised Raspberry Pi HIL
campaign proves the actual sensor, GPIO line, relay polarity and fan behavior.
"""

from __future__ import annotations

from pathlib import Path
from time import monotonic
from typing import Any, Callable

from .actuators import GpiodRelayFanActuator, SimulatedFanActuator
from .controller import EnvironmentController
from .domain import PolicyBounds
from .policy import EnvironmentPolicy, PolicyError, PolicyStore
from .sensors import SHT31Sensor, SimulatedEnvironmentSensor
from .server import EnvironmentUnixServer
from .service import EnvironmentPollingLoop, EnvironmentServiceCore, ServiceIdentity
from .simulation import SimulationState, classify_evidence_mode


class EnvironmentDaemonError(RuntimeError):
    """Environment daemon activation failed before accepting requests."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


SensorFactory = Callable[[Any], Any]
ActuatorFactory = Callable[[Any], Any]
PolicyStoreFactory = Callable[..., PolicyStore]


def build_simulation_state_from_config(env_config: Any, *, now: Callable[[], float] = monotonic) -> SimulationState | None:
    sensor_backend = str(getattr(env_config, "sensor_backend", "")).strip().lower()
    actuator_backend = str(getattr(env_config, "relay_backend", "")).strip().lower()
    if sensor_backend != "simulated" and actuator_backend != "simulated":
        return None
    return SimulationState(
        event_history_limit=int(getattr(env_config, "simulation_event_history_limit", 128)),
        now=now,
    )


def build_sensor_adapter(env_config: Any, *, simulation_state: SimulationState | None = None) -> Any:
    backend = str(getattr(env_config, "sensor_backend", "")).strip().lower()
    if backend == "sht31":
        return SHT31Sensor.from_config(env_config)
    if backend == "simulated":
        if simulation_state is None:
            raise EnvironmentDaemonError("SIMULATION_DISABLED", "simulated sensor requires daemon simulation state")
        return SimulatedEnvironmentSensor(simulation_state)
    raise EnvironmentDaemonError("ENV_CONFIG_INVALID", f"unsupported sensor_backend: {backend}")


def build_actuator_adapter(env_config: Any, *, simulation_state: SimulationState | None = None) -> Any:
    backend = str(getattr(env_config, "relay_backend", "")).strip().lower()
    if backend == "libgpiod":
        return GpiodRelayFanActuator.from_config(env_config)
    if backend == "simulated":
        if simulation_state is None:
            raise EnvironmentDaemonError("SIMULATION_DISABLED", "simulated actuator requires daemon simulation state")
        return SimulatedFanActuator(simulation_state)
    raise EnvironmentDaemonError("ENV_CONFIG_INVALID", f"unsupported relay_backend: {backend}")


def policy_bounds_from_config(env_config: Any) -> PolicyBounds:
    """Translate static/admin configuration into mutable-policy bounds."""

    try:
        return PolicyBounds(
            temperature_min_c=float(env_config.temperature_policy_min_c),
            temperature_max_c=float(env_config.temperature_policy_max_c),
            minimum_hysteresis_c=float(env_config.minimum_hysteresis_c),
            maximum_hysteresis_c=float(env_config.maximum_hysteresis_c),
            minimum_dwell_seconds=int(env_config.minimum_dwell_seconds),
            maximum_dwell_seconds=int(env_config.maximum_dwell_seconds),
        )
    except Exception as exc:
        raise EnvironmentDaemonError("ENV_CONFIG_INVALID", "invalid environment policy bounds") from exc


def build_environment_service_core(
    env_config: Any,
    *,
    now: Callable[[], float] = monotonic,
    sensor_factory: SensorFactory | None = None,
    actuator_factory: ActuatorFactory | None = None,
    policy_store_factory: PolicyStoreFactory | None = None,
) -> EnvironmentServiceCore:
    """Build the daemon core from static config and daemon-owned policy.

    The function opens no I2C bus and requests no GPIO line during construction.
    SHT31 transport and relay line acquisition remain lazy adapter operations;
    this permits the daemon to start in a degraded/readable state while hardware
    target acceptance is still pending.  A missing policy is created with the
    governed default MANUAL/OFF policy; a corrupt policy fails closed and is not
    silently replaced.
    """

    if not bool(getattr(env_config, "enabled", False)):
        raise EnvironmentDaemonError("ENVIRONMENT_DISABLED", "environment subsystem is disabled")
    _validate_static_backend_contract(env_config)
    bounds = policy_bounds_from_config(env_config)
    simulation_state = build_simulation_state_from_config(env_config, now=now)
    store_factory = PolicyStore if policy_store_factory is None else policy_store_factory
    store = store_factory(Path(str(env_config.policy_path)), bounds=bounds)
    try:
        policy = store.load_or_create_default()
    except PolicyError as exc:
        raise EnvironmentDaemonError(exc.code, _public_message(exc)) from exc
    if not isinstance(policy, EnvironmentPolicy):
        raise EnvironmentDaemonError("POLICY_INVALID", "policy store returned an invalid policy object")

    sensor_maker = (lambda cfg: build_sensor_adapter(cfg, simulation_state=simulation_state)) if sensor_factory is None else sensor_factory
    actuator_maker = (lambda cfg: build_actuator_adapter(cfg, simulation_state=simulation_state)) if actuator_factory is None else actuator_factory
    try:
        sensor = sensor_maker(env_config)
        actuator = actuator_maker(env_config)
    except Exception as exc:
        code = getattr(exc, "code", "ENV_ADAPTER_CONFIG_FAILED")
        raise EnvironmentDaemonError(str(code), _public_message(exc)) from exc

    controller = EnvironmentController(
        policy=policy,
        bounds=bounds,
        now_monotonic=float(now()),
        stale_after_seconds=float(env_config.stale_after_seconds),
        valid_samples_to_recover=int(env_config.valid_samples_to_recover),
    )
    sensor_backend = str(env_config.sensor_backend).strip().lower()
    actuator_backend = str(env_config.relay_backend).strip().lower()
    identity = ServiceIdentity(
        hardware_backend=f"{sensor_backend}+{actuator_backend}",
        physical_evidence=False,
        sensor_backend=sensor_backend,
        actuator_backend=actuator_backend,
        sensor_is_simulated=sensor_backend == "simulated",
        actuator_is_simulated=actuator_backend == "simulated",
        evidence_mode=classify_evidence_mode(sensor_backend=sensor_backend, actuator_backend=actuator_backend),
    )
    return EnvironmentServiceCore(
        controller=controller,
        bounds=bounds,
        policy_store=store,
        sensor_adapter=sensor,
        fan_actuator=actuator,
        now=now,
        identity=identity,
        simulation_state=simulation_state,
        simulation_runtime_control_enabled=bool(getattr(env_config, "simulation_runtime_control_enabled", False)),
    )


def build_environment_unix_server(
    env_config: Any,
    *,
    now: Callable[[], float] = monotonic,
    sensor_factory: SensorFactory | None = None,
    actuator_factory: ActuatorFactory | None = None,
    policy_store_factory: PolicyStoreFactory | None = None,
    socket_mode: int = 0o660,
) -> EnvironmentUnixServer:
    """Create the AF_UNIX server for the configured environment daemon."""

    core = build_environment_service_core(
        env_config,
        now=now,
        sensor_factory=sensor_factory,
        actuator_factory=actuator_factory,
        policy_store_factory=policy_store_factory,
    )
    return EnvironmentUnixServer(Path(str(env_config.socket_path)), core, socket_mode=socket_mode)


class EnvironmentDaemon:
    """Lifecycle wrapper used by CLI/systemd entry points and tests."""

    def __init__(self, server: EnvironmentUnixServer, *, polling_loop: EnvironmentPollingLoop | None = None) -> None:
        self.server = server
        self.polling_loop = polling_loop

    @classmethod
    def from_config(cls, env_config: Any, **kwargs: Any) -> "EnvironmentDaemon":
        server = build_environment_unix_server(env_config, **kwargs)
        polling_loop = EnvironmentPollingLoop(
            server.core,
            interval_seconds=float(env_config.poll_interval_seconds),
        )
        return cls(server, polling_loop=polling_loop)

    def start_polling(self) -> None:
        if self.polling_loop is not None:
            self.polling_loop.start()

    def poll_once(self) -> dict[str, object]:
        if self.polling_loop is not None:
            return self.polling_loop.run_once()
        return self.server.core.poll_once()

    def serve_forever(self) -> None:
        self.start_polling()
        try:
            self.server.serve_forever()
        finally:
            self.close()

    def shutdown(self) -> None:
        if self.polling_loop is not None:
            self.polling_loop.stop()
        self.server.shutdown()
        self.close()

    def close(self) -> None:
        if self.polling_loop is not None:
            self.polling_loop.stop()
        self.server.server_close()

    def __enter__(self) -> "EnvironmentDaemon":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def _validate_static_backend_contract(env_config: Any) -> None:
    if str(getattr(env_config, "sensor_backend", "")).strip().lower() not in {"sht31", "simulated"}:
        raise EnvironmentDaemonError("ENV_CONFIG_INVALID", "sensor_backend must be sht31 or simulated")
    if str(getattr(env_config, "relay_backend", "")).strip().lower() not in {"libgpiod", "simulated"}:
        raise EnvironmentDaemonError("ENV_CONFIG_INVALID", "relay_backend must be libgpiod or simulated")
    if str(getattr(env_config, "safe_state", "")).strip().lower() != "off":
        raise EnvironmentDaemonError("ENV_CONFIG_INVALID", "safe_state must be off")
    socket_path = Path(str(getattr(env_config, "socket_path", "")))
    policy_path = Path(str(getattr(env_config, "policy_path", "")))
    if not socket_path.is_absolute():
        raise EnvironmentDaemonError("ENV_CONFIG_INVALID", "socket_path must be absolute")
    if not policy_path.is_absolute():
        raise EnvironmentDaemonError("ENV_CONFIG_INVALID", "policy_path must be absolute")


def _public_message(exc: BaseException) -> str:
    text = str(exc)
    if ": " in text:
        return text.split(": ", 1)[1]
    return text or type(exc).__name__
