"""Dependency-free test doubles for the inspected legacy router boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FakeToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FakeChatResponse:
    content: str | None = ""
    tool_calls: tuple[FakeToolCall, ...] = ()

    @property
    def is_tool_call(self) -> bool:
        return bool(self.tool_calls)


class FakeChatClient:
    """Records requests and returns queued responses without network access."""

    def __init__(self, *responses: FakeChatResponse):
        if not responses:
            raise ValueError("at least one fake response is required")
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> FakeChatResponse:
        self.calls.append({"messages": messages, "tools": tools, "stream": stream})
        if not self._responses:
            raise AssertionError("fake chat response queue exhausted")
        return self._responses.pop(0)
