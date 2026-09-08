"""Narrow adapters for the pre-package source runtime.

This module intentionally imports no audio, model, UI, network, or extension
dependency until the compatibility runtime is explicitly requested.
"""

from __future__ import annotations

import importlib
import sys


class CompatibilityError(RuntimeError):
    """Raised when the legacy source runtime cannot be started safely."""


def run_legacy_source() -> int:
    """Run the pre-package orchestrator from a source checkout only."""

    print(
        "WARNING: starting the compatibility source runtime; this is not the "
        "accepted headless core runtime.",
        file=sys.stderr,
    )
    try:
        module = importlib.import_module("legacy_orchestrator")
    except ModuleNotFoundError as exc:
        if exc.name == "legacy_orchestrator":
            detail = "the source-checkout module is unavailable"
        else:
            detail = f"legacy dependency {exc.name!r} is unavailable"
        raise CompatibilityError(detail) from exc

    legacy_main = getattr(module, "main", None)
    if not callable(legacy_main):
        raise CompatibilityError("legacy_orchestrator.main is unavailable")
    legacy_main()
    return 0
