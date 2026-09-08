#!/usr/bin/env python3
"""Compatibility launcher for the pre-package source runtime.

New development and installed entry points use ``gonken-agent``. Running this
file without arguments preserves the historical source-checkout command, but
it does so through an explicit compatibility boundary.
"""

from __future__ import annotations

import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from gonken_agent.cli import main  # noqa: E402


if __name__ == "__main__":
    arguments = sys.argv[1:] or ["run", "--legacy-source"]
    raise SystemExit(main(arguments))
