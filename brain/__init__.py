"""Legacy source-runtime reasoning modules for GonKenLab Agent.

Imports are lazy so deterministic router tests do not load the HTTP client.
"""

from __future__ import annotations

from typing import Any

__all__ = ["OllamaClient", "Router", "ToolType", "RouterResult", "TOOLS", "SYSTEM_PROMPT"]


def __getattr__(name: str) -> Any:
    if name == "OllamaClient":
        from .ollama_client import OllamaClient

        return OllamaClient
    if name in {"Router", "ToolType", "RouterResult"}:
        from .router import Router, RouterResult, ToolType

        return {"Router": Router, "ToolType": ToolType, "RouterResult": RouterResult}[name]
    if name in {"TOOLS", "SYSTEM_PROMPT"}:
        from .tool_definitions import SYSTEM_PROMPT, TOOLS

        return {"TOOLS": TOOLS, "SYSTEM_PROMPT": SYSTEM_PROMPT}[name]
    raise AttributeError(name)
