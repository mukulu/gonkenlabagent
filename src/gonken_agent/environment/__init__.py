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
from .policy import EnvironmentPolicy, PolicyError, PolicyStore

__all__ = [
    "ControllerError",
    "ControllerState",
    "EnvironmentController",
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
