from __future__ import annotations

import importlib.util
import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "ollama_manager", ROOT / "scripts" / "ollama_manager.py"
)
assert SPEC and SPEC.loader
ollama_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ollama_manager)


class OllamaInputContractTests(unittest.TestCase):
    def test_only_loopback_http_origins_are_accepted(self) -> None:
        self.assertEqual(
            ollama_manager.validate_endpoint("http://127.0.0.1:11434"),
            "http://127.0.0.1:11434",
        )
        for endpoint in (
            "https://127.0.0.1:11434",
            "http://0.0.0.0:11434",
            "http://192.168.1.2:11434",
            "http://user:pass@localhost:11434",
            "http://localhost",
            "http://localhost:11434/api",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ollama_manager.OllamaError):
                ollama_manager.validate_endpoint(endpoint)

    def test_manifest_rejects_unknown_fields_and_non_https_production_url(self) -> None:
        source = (ROOT / "packaging/ollama-artifacts.toml").read_text(encoding="utf-8")
        cases = (
            source + "\nunknown = true\n",
            source.replace("https://github.com/", "file:///tmp/"),
        )
        for content in cases:
            with self.subTest(content=content[-40:]), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "manifest.toml"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ollama_manager.OllamaError) as raised:
                    ollama_manager.read_manifest(path, Path("/"))
                self.assertEqual(raised.exception.code, "OLLAMA_MANIFEST")

    def test_archive_rejects_traversal_devices_and_escaping_links(self) -> None:
        cases = (("../escape", "file"), ("device", "device"), ("lib/link", "link"))
        for name, kind in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "payload.tar"
                with tarfile.open(archive, "w") as bundle:
                    member = tarfile.TarInfo(name)
                    if kind == "file":
                        member.size = 1
                        bundle.addfile(member, io.BytesIO(b"x"))
                    elif kind == "device":
                        member.type = tarfile.CHRTYPE
                        bundle.addfile(member)
                    else:
                        member.type = tarfile.SYMTYPE
                        member.linkname = "../../outside"
                        bundle.addfile(member)
                with self.assertRaises(ollama_manager.OllamaError) as raised:
                    ollama_manager.safe_extract(archive, root / "out")
                self.assertEqual(raised.exception.code, "OLLAMA_ARCHIVE")

    def test_install_record_parser_is_closed_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ollama.record"
            path.write_text("format=gonken-ollama-install-v1\nunknown=value\n", encoding="utf-8")
            with self.assertRaises(ollama_manager.OllamaError) as raised:
                ollama_manager.read_install_record(path)
            self.assertEqual(raised.exception.code, "OLLAMA_RECORD")

    def test_model_digest_and_quantization_are_both_enforced(self) -> None:
        accepted = {
            "models": [{
                "name": "qwen3.5:2b-q4_K_M",
                "digest": "124a03c34777" + "a" * 52,
                "details": {"quantization_level": "Q4_K_M"},
            }]
        }
        with mock.patch.object(ollama_manager, "_api", return_value=accepted):
            item = ollama_manager.installed_model(
                "http://127.0.0.1:11434", "qwen3.5:2b-q4_K_M", "124a03c34777"
            )
        self.assertEqual(item["digest"], "124a03c34777" + "a" * 52)
        for field, value in (("digest", "f" * 64), ("quantization_level", "Q8_0")):
            rejected = {"models": [{**accepted["models"][0], "details": dict(accepted["models"][0]["details"])}]}
            if field == "digest":
                rejected["models"][0][field] = value
            else:
                rejected["models"][0]["details"][field] = value
            with self.subTest(field=field), mock.patch.object(ollama_manager, "_api", return_value=rejected):
                with self.assertRaises(ollama_manager.OllamaError):
                    ollama_manager.installed_model(
                        "http://127.0.0.1:11434", "qwen3.5:2b-q4_K_M", "124a03c34777"
                    )

    def test_redirected_root_requires_explicit_failure_test_gate(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ollama_manager.OllamaError) as raised:
                ollama_manager.test_mode(Path("/tmp/isolated"))
        self.assertEqual(raised.exception.code, "OLLAMA_TEST_GATE")


if __name__ == "__main__":
    unittest.main()
