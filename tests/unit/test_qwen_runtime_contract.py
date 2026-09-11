from __future__ import annotations

import json
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

from gonken_agent.llm.ollama import OllamaClient


class _FakeResponse:
    status = 200

    def __init__(self, payload: dict[str, object]):
        self._payload = json.dumps(payload).encode()

    def read(self, size: int) -> bytes:
        return self._payload

    def close(self) -> None:
        pass


class _FakeConnection:
    def __init__(self, response: _FakeResponse):
        self.response = response
        self.request_payload = None

    def request(self, method, path, body=None, headers=None):
        self.request_payload = json.loads(body)

    def getresponse(self):
        return self.response

    def close(self) -> None:
        pass


class QwenRuntimeContractTests(unittest.TestCase):
    def test_chat_disables_thinking_for_structured_json_contract(self) -> None:
        config = SimpleNamespace(
            base_url="http://127.0.0.1:11434",
            model="qwen3.5:2b-q4_K_M",
            keep_alive="5m",
            context_tokens=2048,
            max_output_tokens=128,
        )
        client = OllamaClient(config)
        response = _FakeResponse({
            "model": config.model,
            "done": True,
            "message": {"content": "{\"answer\": \"ok\"}"},
        })
        connection = _FakeConnection(response)
        with mock.patch.object(client, "_connection", return_value=connection):
            content = client.chat([{"role": "user", "content": "test"}], threading.Event())
        self.assertEqual(content, '{"answer": "ok"}')
        self.assertIs(connection.request_payload["think"], False)
        self.assertEqual(connection.request_payload["format"], "json")


if __name__ == "__main__":
    unittest.main()
