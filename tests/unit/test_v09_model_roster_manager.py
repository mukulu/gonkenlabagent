from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("model_roster_manager", ROOT / "scripts" / "model_roster_manager.py")
assert SPEC and SPEC.loader
manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manager)


class ModelRosterManagerTests(unittest.TestCase):
    def setUp(self):
        self.roster = manager.read_roster(ROOT / "packaging" / "ollama-model-roster.toml")

    def _models(self):
        return [
            {
                "name": spec["tag"],
                "digest": spec["digest_prefix"] + "a" * 52,
                "details": {"quantization_level": spec["quantization"]},
            }
            for spec in self.roster["models"]
        ]

    def test_manifest_has_exact_roster_and_default(self):
        self.assertEqual(self.roster["default_model"], "qwen3:0.6b")
        self.assertEqual([m["tag"] for m in self.roster["models"]], [
            "qwen3:0.6b", "lfm2.5-thinking:1.2b", "qwen3.5:0.8b"
        ])

    def test_preseeded_offline_fails_if_any_model_missing_without_pull(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = self._models()[:-1]
            with mock.patch.object(manager.om, "_api", return_value={"models": models}), \
                 mock.patch.object(manager.om, "pull_model") as pull:
                with self.assertRaises(manager.RosterError) as raised:
                    manager.provision(root, self.roster, "http://127.0.0.1:11434", 2048, "preseeded-offline")
            self.assertEqual(raised.exception.code, "MODEL_ROSTER_OFFLINE_MISSING")
            pull.assert_not_called()

    def test_online_provision_validates_all_models_and_selects_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = {"models": []}

            def api(_endpoint, path, payload=None, *, stream=False):
                if path == "/api/tags":
                    return {"models": list(state["models"])}
                if path == "/api/chat":
                    return {
                        "model": payload["model"], "done": True, "total_duration": 123,
                        "message": {"role": "assistant", "content": "", "tool_calls": [
                            {"function": {"name": "readiness_probe", "arguments": {}}}
                        ]},
                    }
                raise AssertionError(path)

            def pull(_endpoint, tag):
                spec = next(item for item in self.roster["models"] if item["tag"] == tag)
                state["models"].append({
                    "name": tag,
                    "digest": spec["digest_prefix"] + "b" * 52,
                    "details": {"quantization_level": spec["quantization"]},
                })
                return 100

            with mock.patch.object(manager.om, "_api", side_effect=api), \
                 mock.patch.object(manager.om, "pull_model", side_effect=pull), \
                 mock.patch.object(manager.om, "smoke_model", return_value={"total_ns": 50, "eval_count": 1}):
                record = manager.provision(root, self.roster, "http://127.0.0.1:11434", 2048, "online")
                checked = manager.status(root, self.roster, "http://127.0.0.1:11434")
            self.assertEqual(record["status"], "READY")
            self.assertEqual(len(record["models"]), 3)
            self.assertTrue(all(row["tool_call_smoke"] == "PASS" for row in record["models"]))
            self.assertEqual(checked["selection"]["model"], "qwen3:0.6b")
            selection = json.loads((root / "var/lib/gonken-agent/ollama/active-model.json").read_text())
            self.assertEqual(selection["previous_model"], "qwen3.5:2b-q4_K_M")

    def test_provision_preserves_admitted_operator_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = self._models()
            manager._write_selection(root, "qwen3.5:0.8b", "qwen3:0.6b")

            def api(_endpoint, path, payload=None, *, stream=False):
                if path == "/api/tags":
                    return {"models": models}
                if path == "/api/chat":
                    return {
                        "model": payload["model"], "done": True, "total_duration": 123,
                        "message": {"role": "assistant", "content": "", "tool_calls": [
                            {"function": {"name": "readiness_probe", "arguments": {}}}
                        ]},
                    }
                raise AssertionError(path)

            with mock.patch.object(manager.om, "_api", side_effect=api), \
                 mock.patch.object(manager.om, "smoke_model", return_value={"total_ns": 50, "eval_count": 1}):
                record = manager.provision(root, self.roster, "http://127.0.0.1:11434", 2048, "online")
                checked = manager.status(root, self.roster, "http://127.0.0.1:11434")
            self.assertEqual(checked["selection"]["model"], "qwen3.5:0.8b")
            self.assertEqual(record["active_model"], "qwen3.5:0.8b")

    def test_status_accepts_admitted_nondefault_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = self._models()
            manager._write_selection(root, "lfm2.5-thinking:1.2b", "qwen3:0.6b")
            manager._atomic_json(manager._record_path(root), {"format": manager.RECORD_FORMAT, "status": "READY"}, 0o644)
            with mock.patch.object(manager.om, "_api", return_value={"models": models}):
                checked = manager.status(root, self.roster, "http://127.0.0.1:11434")
            self.assertEqual(checked["selection"]["model"], "lfm2.5-thinking:1.2b")

    def test_default_tool_smoke_failure_blocks_default_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = self._models()

            def api(_endpoint, path, payload=None, *, stream=False):
                if path == "/api/tags":
                    return {"models": models}
                if path == "/api/chat":
                    return {"model": payload["model"], "done": True, "message": {"role": "assistant", "content": "text"}}
                raise AssertionError(path)

            with mock.patch.object(manager.om, "_api", side_effect=api), \
                 mock.patch.object(manager.om, "smoke_model", return_value={"total_ns": 50, "eval_count": 1}):
                with self.assertRaises(manager.RosterError) as raised:
                    manager.provision(root, self.roster, "http://127.0.0.1:11434", 2048, "online")
            self.assertEqual(raised.exception.code, "MODEL_DEFAULT_TOOL_SMOKE")
            self.assertFalse((root / "var/lib/gonken-agent/ollama/active-model.json").exists())


if __name__ == "__main__":
    unittest.main()
