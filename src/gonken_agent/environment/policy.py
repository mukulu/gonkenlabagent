"""Mutable environment policy validation and atomic persistence."""

from __future__ import annotations

import json
from math import isfinite
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .domain import EnvironmentMode, PolicyBounds

POLICY_SCHEMA_VERSION = 1
DEFAULT_START_C = 28.0
DEFAULT_STOP_C = 26.5
DEFAULT_DWELL_SECONDS = 60


class PolicyError(ValueError):
    """Mutable environment policy is invalid, stale, corrupt, or unsafe."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True, slots=True)
class EnvironmentPolicy:
    """Daemon-owned mutable policy constrained by static/admin bounds."""

    generation: int
    mode: EnvironmentMode
    start_c: float
    stop_c: float
    minimum_on_seconds: int
    minimum_off_seconds: int
    schema_version: int = POLICY_SCHEMA_VERSION

    @classmethod
    def default(cls) -> "EnvironmentPolicy":
        return cls(
            generation=1,
            mode=EnvironmentMode.MANUAL,
            start_c=DEFAULT_START_C,
            stop_c=DEFAULT_STOP_C,
            minimum_on_seconds=DEFAULT_DWELL_SECONDS,
            minimum_off_seconds=DEFAULT_DWELL_SECONDS,
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], *, bounds: PolicyBounds) -> "EnvironmentPolicy":
        allowed = {
            "schema_version",
            "generation",
            "mode",
            "start_c",
            "stop_c",
            "minimum_on_seconds",
            "minimum_off_seconds",
        }
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise PolicyError("POLICY_INVALID", f"unknown policy key: {unknown[0]}")
        for key in ("schema_version", "generation", "minimum_on_seconds", "minimum_off_seconds"):
            if key in data and type(data[key]) is not int:
                raise PolicyError("POLICY_INVALID", f"{key} must be an integer, not a coerced value")
        for key in ("start_c", "stop_c"):
            if key in data and (type(data[key]) not in (int, float) or not isfinite(data[key])):
                raise PolicyError("POLICY_INVALID", f"{key} must be a finite number")
        try:
            policy = cls(
                schema_version=int(data.get("schema_version", POLICY_SCHEMA_VERSION)),
                generation=int(data["generation"]),
                mode=EnvironmentMode.parse(str(data["mode"])),
                start_c=float(data["start_c"]),
                stop_c=float(data["stop_c"]),
                minimum_on_seconds=int(data["minimum_on_seconds"]),
                minimum_off_seconds=int(data["minimum_off_seconds"]),
            )
        except KeyError as exc:
            raise PolicyError("POLICY_INVALID", f"missing policy key: {exc.args[0]}") from exc
        except (TypeError, ValueError) as exc:
            raise PolicyError("POLICY_INVALID", "policy has an invalid value type") from exc
        return policy.validated(bounds=bounds)

    def validated(self, *, bounds: PolicyBounds) -> "EnvironmentPolicy":
        for key in ("schema_version", "generation", "minimum_on_seconds", "minimum_off_seconds"):
            if type(getattr(self, key)) is not int:
                raise PolicyError("POLICY_INVALID", f"{key} must be an integer")
        for key in ("start_c", "stop_c"):
            value = getattr(self, key)
            if type(value) not in (int, float) or not isfinite(value):
                raise PolicyError("POLICY_INVALID", f"{key} must be a finite number")
        if not isinstance(self.mode, EnvironmentMode):
            raise PolicyError("POLICY_INVALID", "mode must be an EnvironmentMode")
        if self.schema_version != POLICY_SCHEMA_VERSION:
            raise PolicyError(
                "POLICY_INVALID",
                f"unsupported policy schema_version {self.schema_version}",
            )
        if self.generation < 1:
            raise PolicyError("POLICY_INVALID", "generation must be positive")
        if self.start_c < bounds.temperature_min_c or self.start_c > bounds.temperature_max_c:
            raise PolicyError("POLICY_INVALID", "start_c is outside static temperature bounds")
        if self.stop_c < bounds.temperature_min_c or self.stop_c > bounds.temperature_max_c:
            raise PolicyError("POLICY_INVALID", "stop_c is outside static temperature bounds")
        hysteresis = self.start_c - self.stop_c
        if hysteresis < bounds.minimum_hysteresis_c:
            raise PolicyError("POLICY_INVALID", "stop_c plus minimum hysteresis must be <= start_c")
        if hysteresis > bounds.maximum_hysteresis_c:
            raise PolicyError("POLICY_INVALID", "temperature hysteresis exceeds static maximum")
        if not bounds.minimum_dwell_seconds <= self.minimum_on_seconds <= bounds.maximum_dwell_seconds:
            raise PolicyError("POLICY_INVALID", "minimum_on_seconds is outside static dwell bounds")
        if not bounds.minimum_dwell_seconds <= self.minimum_off_seconds <= bounds.maximum_dwell_seconds:
            raise PolicyError("POLICY_INVALID", "minimum_off_seconds is outside static dwell bounds")
        return self

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generation": self.generation,
            "mode": self.mode.value,
            "start_c": self.start_c,
            "stop_c": self.stop_c,
            "minimum_on_seconds": self.minimum_on_seconds,
            "minimum_off_seconds": self.minimum_off_seconds,
        }

    def updated(
        self,
        *,
        bounds: PolicyBounds,
        expected_generation: int | None = None,
        mode: str | EnvironmentMode | None = None,
        start_c: float | None = None,
        stop_c: float | None = None,
        minimum_on_seconds: int | None = None,
        minimum_off_seconds: int | None = None,
    ) -> "EnvironmentPolicy":
        for key, value in (("expected_generation", expected_generation),
                           ("minimum_on_seconds", minimum_on_seconds),
                           ("minimum_off_seconds", minimum_off_seconds)):
            if value is not None and type(value) is not int:
                raise PolicyError("POLICY_INVALID", f"{key} must be an integer")
        for key, value in (("start_c", start_c), ("stop_c", stop_c)):
            if value is not None and (type(value) not in (int, float) or not isfinite(value)):
                raise PolicyError("POLICY_INVALID", f"{key} must be a finite number")
        if expected_generation is not None and expected_generation != self.generation:
            raise PolicyError("POLICY_GENERATION_CONFLICT", "policy generation changed")
        next_policy = replace(
            self,
            generation=self.generation + 1,
            mode=self.mode if mode is None else EnvironmentMode.parse(mode),
            start_c=self.start_c if start_c is None else float(start_c),
            stop_c=self.stop_c if stop_c is None else float(stop_c),
            minimum_on_seconds=(
                self.minimum_on_seconds if minimum_on_seconds is None else int(minimum_on_seconds)
            ),
            minimum_off_seconds=(
                self.minimum_off_seconds if minimum_off_seconds is None else int(minimum_off_seconds)
            ),
        )
        return next_policy.validated(bounds=bounds)


class PolicyStore:
    """Small JSON policy store with same-directory atomic replacement."""

    def __init__(self, path: Path | str, *, bounds: PolicyBounds) -> None:
        self.path = Path(path)
        self.bounds = bounds

    def _permission_code(self) -> str:
        parent = self.path.parent
        while True:
            try:
                if parent.exists() and not os.access(parent, os.X_OK):
                    return "ENV_POLICY_PARENT_PERMISSION_DENIED"
            except OSError:
                pass
            if parent == parent.parent:
                break
            parent = parent.parent
        return "ENV_POLICY_PERMISSION_DENIED"

    def default_policy(self) -> EnvironmentPolicy:
        """Return the governed default in memory without mutating persistent state."""
        return EnvironmentPolicy.default().validated(bounds=self.bounds)

    def load(self) -> EnvironmentPolicy:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise PolicyError("ENV_POLICY_MISSING", f"policy file does not exist: {self.path}") from exc
        except PermissionError as exc:
            raise PolicyError(self._permission_code(), f"cannot access policy file: {self.path}") from exc
        except OSError as exc:
            raise PolicyError("ENV_POLICY_READ_FAILED", f"cannot read policy file: {self.path}") from exc
        try:
            raw = json.loads(text, object_pairs_hook=_unique_policy_object,
                             parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite policy")))
        except (ValueError, UnicodeError) as exc:
            raise PolicyError("ENV_POLICY_JSON_INVALID", f"policy JSON is invalid: {self.path}") from exc
        if not isinstance(raw, dict):
            raise PolicyError("ENV_POLICY_JSON_INVALID", "policy root must be an object")
        return EnvironmentPolicy.from_mapping(raw, bounds=self.bounds)

    def validate_access(self) -> None:
        """Validate existing policy readability without creating or rewriting state."""
        if not self.path.exists():
            return
        self.load()

    def initialize_default_if_missing(self) -> EnvironmentPolicy:
        if self.path.exists():
            return self.load()
        policy = self.default_policy()
        self.save(policy)
        return policy

    def load_or_create_default(self) -> EnvironmentPolicy:
        """Backward-compatible mutating startup operation."""
        return self.initialize_default_if_missing()

    def save(self, policy: EnvironmentPolicy) -> None:
        policy = policy.validated(bounds=self.bounds)
        payload = json.dumps(policy.to_mapping(), sort_keys=True, indent=2) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = -1
        temp_path: Path | None = None
        try:
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=str(self.path.parent),
                text=True,
            )
            temp_path = Path(temp_name)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                fd = -1
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_path, 0o640)
            os.replace(temp_path, self.path)
            temp_path = None
            _fsync_dir(self.path.parent)
        except PermissionError as exc:
            raise PolicyError("ENV_POLICY_WRITE_PERMISSION_DENIED", f"cannot write policy file: {self.path}") from exc
        except OSError as exc:
            raise PolicyError("ENV_POLICY_ATOMIC_REPLACE_FAILED", f"cannot write policy file: {self.path}") from exc
        finally:
            if fd >= 0:
                os.close(fd)
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except OSError:
                    pass


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _unique_policy_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate policy key")
        result[key] = value
    return result
