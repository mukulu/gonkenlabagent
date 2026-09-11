from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from brain.router import Router, ToolType
from tests.fixtures.router_fakes import (
    FakeChatClient,
    FakeChatResponse,
    FakeToolCall,
)


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "tests" / "fixtures" / "router_cases.json"


class RouterBoundaryTests(unittest.TestCase):
    def test_router_import_does_not_require_http_client_package(self) -> None:
        script = f"""
import importlib.util
import sys
sys.path.insert(0, {str(ROOT)!r})
from brain.router import Router
assert Router is not None
assert 'httpx' not in sys.modules
assert 'brain.ollama_client' not in sys.modules
"""
        result = subprocess.run(
            [sys.executable, "-I", "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_fixture_routes_are_deterministic(self) -> None:
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        for case in cases:
            with self.subTest(user_input=case["input"]):
                client = FakeChatClient(FakeChatResponse(case["model_content"]))
                result = Router(client).route(case["input"])
                self.assertEqual(result.tool.value, case["expected_tool"])
                self.assertEqual(result.arguments, case["expected_arguments"])
                self.assertEqual(len(client.calls), 1)

    def test_joke_request_matches_the_declared_joke_tool(self) -> None:
        router = Router(FakeChatClient(FakeChatResponse("local response")))
        result = router.route("Tell me a joke")
        self.assertEqual(result.tool, ToolType.JOKE)
        self.assertIsNone(result.response)

    def test_phrase_matching_does_not_match_substrings(self) -> None:
        router = Router(FakeChatClient(FakeChatResponse("model response")))
        result = router.route("This explanation needs detail")
        self.assertEqual(result.tool, ToolType.CLOUD)

        router = Router(FakeChatClient(FakeChatResponse("model response")))
        result = router.route("Describe international transport policy")
        self.assertEqual(
            result.arguments, {"query": "Describe international transport policy"}
        )

    def test_structured_tool_call_preserves_arguments(self) -> None:
        client = FakeChatClient(
            FakeChatResponse(
                tool_calls=(FakeToolCall("get_weather", {"location": "Tokyo"}),)
            )
        )
        result = Router(client).route("Weather please")
        self.assertEqual(result.tool, ToolType.WEATHER)
        self.assertEqual(result.arguments, {"location": "Tokyo"})
        self.assertIsNone(result.response)

    def test_local_response_is_added_to_bounded_history(self) -> None:
        responses = [FakeChatResponse(f"answer {index}") for index in range(6)]
        client = FakeChatClient(*responses)
        router = Router(client)
        for index in range(6):
            router.route(f"hello {index}")

        self.assertEqual(len(router.conversation_history), 12)
        final_messages = client.calls[-1]["messages"]
        self.assertLessEqual(len(final_messages), 10)
        self.assertEqual(final_messages[-1]["content"], "hello 5")

    def test_fake_boundary_does_not_load_network_or_hardware_modules(self) -> None:
        script = f"""
import sys
forbidden = {{"httpx", "sounddevice", "numpy", "openwakeword", "pygame"}}
before = forbidden.intersection(sys.modules)
sys.path.insert(0, {str(ROOT)!r})
from brain.router import Router
from tests.fixtures.router_fakes import FakeChatClient, FakeChatResponse
Router(FakeChatClient(FakeChatResponse("ok"))).route("hello")
loaded = sorted(forbidden.intersection(sys.modules) - before)
if loaded:
    raise SystemExit('optional dependencies imported by fake router boundary: ' + ', '.join(loaded))
"""
        result = subprocess.run(
            [sys.executable, "-I", "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
