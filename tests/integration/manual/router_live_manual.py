#!/usr/bin/env python3
"""Explicit live-Ollama compatibility probe; never part of automated T0/T1."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    if os.environ.get("GONKEN_RUN_LIVE_INTEGRATION") != "1":
        print(
            "Live router probe disabled. Set GONKEN_RUN_LIVE_INTEGRATION=1 "
            "only with an intentional local Ollama test environment."
        )
        return 2

    sys.path.insert(0, str(ROOT))
    from brain.ollama_client import OllamaClient
    from brain.router import Router, ToolType
    from config import Config

    config = Config.load()
    client = OllamaClient(
        base_url=config.ollama_base_url,
        model=config.chat_model,
        max_output_tokens=config.max_output_tokens,
        keep_alive=config.keep_alive,
    )
    if not client.is_available():
        print(f"Ollama is unavailable at {config.ollama_base_url}", file=sys.stderr)
        return 1

    router = Router(client)
    cases = [
        ("Hello, how are you?", ToolType.NONE),
        ("What time is it?", ToolType.TIME),
        ("What's the weather in London?", ToolType.WEATHER),
        ("Write me a poem about stars", ToolType.CLOUD),
        ("Tell me a joke", ToolType.JOKE),
    ]
    failures = 0
    for user_input, expected in cases:
        result = router.route(user_input)
        passed = result.tool == expected
        failures += not passed
        print(
            f"{'PASS' if passed else 'FAIL'}: {user_input!r}: "
            f"expected={expected.value} actual={result.tool.value}"
        )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
