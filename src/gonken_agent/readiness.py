"""Profile-aware component readiness primitives.

This module deliberately contains no hardware access.  Runtime/installer layers
publish current component facts; this module only validates and aggregates them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

COMPONENT_STATUSES = frozenset({
    "STARTING", "READY", "DEGRADED", "FAILED", "WAITING", "DISABLED",
    "NOT_COMMISSIONED", "NOT_APPLICABLE", "NOT_TESTED", "BLOCKED", "UNKNOWN",
})

READY_STATUSES = frozenset({"READY", "NOT_APPLICABLE"})
COMMISSIONING_STATUSES = frozenset({"NOT_COMMISSIONED", "NOT_TESTED"})
FAILURE_STATUSES = frozenset({"FAILED", "BLOCKED", "UNKNOWN", "DISABLED", "WAITING", "STARTING", "DEGRADED"})


@dataclass(frozen=True, slots=True)
class ComponentReadiness:
    name: str
    status: str
    code: str
    required: bool
    recoverable: bool = False
    evidence_tier: str = "host"
    last_failure_code: str | None = None
    recovered: bool = False

    def __post_init__(self) -> None:
        if self.status not in COMPONENT_STATUSES:
            raise ValueError(f"unsupported component status: {self.status}")
        if not self.name or any(ch.isspace() for ch in self.name):
            raise ValueError("component name must be a non-empty token")
        if not self.code:
            raise ValueError("component code is required")

    def as_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "status": self.status,
            "code": self.code,
            "required": self.required,
            "recoverable": self.recoverable,
            "evidence_tier": self.evidence_tier,
            "recovered": self.recovered,
        }
        if self.last_failure_code:
            value["last_failure_code"] = self.last_failure_code
        return value


def aggregate_components(components: Mapping[str, ComponentReadiness]) -> dict[str, object]:
    """Aggregate current state only after every component has been classified."""
    blocking: list[str] = []
    commissioning: list[str] = []
    degraded_optional: list[str] = []
    for name, component in components.items():
        if component.required:
            if component.status in COMMISSIONING_STATUSES:
                commissioning.append(name)
            elif component.status not in READY_STATUSES:
                blocking.append(name)
        elif component.status not in READY_STATUSES:
            degraded_optional.append(name)
    if blocking:
        status = "INSTALLATION_FAILED_REQUIRED_COMPONENT"
        complete = False
    elif commissioning:
        status = "INSTALLATION_INCOMPLETE_COMMISSIONING_REQUIRED"
        complete = False
    elif degraded_optional:
        status = "INSTALLATION_COMPLETE_WITH_OPTIONAL_DEGRADATION"
        complete = True
    else:
        status = "INSTALLATION_COMPLETE_SELECTED_PROFILE_READY"
        complete = True
    return {
        "status": status,
        "complete": complete,
        "blocking": sorted(blocking),
        "commissioning_required": sorted(commissioning),
        "degraded_optional": sorted(degraded_optional),
    }


def readiness_document(
    *,
    selected_profile: str,
    components: Mapping[str, ComponentReadiness],
    release_commit: str,
    release_profile: str,
    observed_epoch: int,
    boot_id: str | None = None,
    service_pid: int | None = None,
    service_start_ticks: int | None = None,
) -> dict[str, object]:
    return {
        "format": "gonken-component-readiness-v2",
        "observed_epoch": int(observed_epoch),
        "release": {"commit": release_commit, "profile": release_profile},
        "boot_id": boot_id,
        "service": {"pid": service_pid, "start_ticks": service_start_ticks},
        "selected_profile": selected_profile,
        "components": {name: component.as_dict() for name, component in sorted(components.items())},
        "aggregate": aggregate_components(components),
        "physical_acceptance_claimed": False,
    }
