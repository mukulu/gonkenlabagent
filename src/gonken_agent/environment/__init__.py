"""Deterministic room-environment control domain.

This package deliberately contains no hardware imports at the domain/policy layer.
Hardware access belongs to later adapter modules owned by gonken-environment.service.
"""

from .domain import (
    EnvironmentMode,
    FanCapability,
    FanPower,
    PolicyBounds,
    SensorQuality,
    SensorReading,
    TransitionReason,
)
from .controller import ControllerError, ControllerState, EnvironmentController
from .client import EnvironmentClient, EnvironmentClientError
from .intents import EnvironmentClarification, EnvironmentIntent, parse_environment_intent
from .responses import environment_error_response, environment_success_response
from .protocol import EnvironmentRequest, EnvironmentResponse, ProtocolError
from .server import EnvironmentUnixServer
from .service import EnvironmentPollingLoop, EnvironmentServiceCore, EnvironmentServiceError, ScriptedSensorSource, ServiceIdentity
from .daemon import EnvironmentDaemon, EnvironmentDaemonError, build_environment_service_core, build_environment_unix_server, policy_bounds_from_config
from .policy import EnvironmentPolicy, PolicyError, PolicyStore
from .sensors import EnvironmentSensor, SHT31Sensor, SensorAdapterError, crc8, decode_sht31_frame
from .actuators import ActuatorAdapterError, FanActuator, GpiodRelayFanActuator

__all__ = [
    "ControllerError",
    "ControllerState",
    "EnvironmentController",
    "EnvironmentClient",
    "EnvironmentClientError",
    "EnvironmentClarification",
    "EnvironmentIntent",
    "EnvironmentRequest",
    "EnvironmentResponse",
    "EnvironmentPollingLoop",
    "EnvironmentServiceCore",
    "EnvironmentServiceError",
    "EnvironmentDaemon",
    "EnvironmentDaemonError",
    "EnvironmentSensor",
    "EnvironmentUnixServer",
    "environment_error_response",
    "environment_success_response",
    "ProtocolError",
    "ScriptedSensorSource",
    "ServiceIdentity",
    "EnvironmentMode",
    "EnvironmentPolicy",
    "FanCapability",
    "FanPower",
    "FanActuator",
    "GpiodRelayFanActuator",
    "PolicyBounds",
    "build_environment_service_core",
    "build_environment_unix_server",
    "policy_bounds_from_config",
    "PolicyError",
    "PolicyStore",
    "SHT31Sensor",
    "SensorAdapterError",
    "SensorQuality",
    "SensorReading",
    "TransitionReason",
    "ActuatorAdapterError",
    "crc8",
    "decode_sht31_frame",
    "parse_environment_intent",
]
