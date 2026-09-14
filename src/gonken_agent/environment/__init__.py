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
from .protocol import EnvironmentRequest, EnvironmentResponse, ProtocolError
from .server import EnvironmentUnixServer
from .service import EnvironmentServiceCore, EnvironmentServiceError, ScriptedSensorSource, ServiceIdentity
from .policy import EnvironmentPolicy, PolicyError, PolicyStore

__all__ = [
    "ControllerError",
    "ControllerState",
    "EnvironmentController",
    "EnvironmentClient",
    "EnvironmentClientError",
    "EnvironmentRequest",
    "EnvironmentResponse",
    "EnvironmentServiceCore",
    "EnvironmentServiceError",
    "EnvironmentUnixServer",
    "ProtocolError",
    "ScriptedSensorSource",
    "ServiceIdentity",
    "EnvironmentMode",
    "EnvironmentPolicy",
    "FanCapability",
    "FanPower",
    "PolicyBounds",
    "PolicyError",
    "PolicyStore",
    "SensorQuality",
    "SensorReading",
    "TransitionReason",
]
