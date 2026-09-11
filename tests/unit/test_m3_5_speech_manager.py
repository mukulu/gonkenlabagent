from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("speech_manager", ROOT / "scripts/speech_manager.py")
speech_manager = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(speech_manager)


class SpeechManagerUnitTests(unittest.TestCase):
    def test_test_controls_cannot_target_real_root(self) -> None:
        with mock.patch.dict(os.environ, {"GONKEN_ENABLE_TEST_FAILURES": "1"}):
            with self.assertRaises(speech_manager.SpeechError) as raised:
                speech_manager.test_mode(Path("/"))
        self.assertEqual(raised.exception.code, "SPEECH_TEST_GATE")

    def test_elf_machine_parses_aarch64_and_rejects_wrong_architecture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "binary"
            header = bytearray(20)
            header[:6] = b"\x7fELF\x02\x01"
            header[18:20] = (183).to_bytes(2, "little")
            path.write_bytes(header)
            self.assertEqual(speech_manager.elf_machine(path), 183)
            header[18:20] = (62).to_bytes(2, "little")
            path.write_bytes(header)
            with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(speech_manager.SpeechError) as raised:
                speech_manager.validate_aarch64(path, Path("/"))
            self.assertEqual(raised.exception.code, "SPEECH_ARCH")

    def test_valid_wav_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.wav"
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(22050)
                output.writeframes(b"\0\0" * 4410)
            self.assertEqual(speech_manager.validate_wav(path, 22050, 2205, 20), (22050, 4410))

    def test_download_rejects_bad_checksum_and_removes_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.write_bytes(b"payload")
            destination = root / "out/artifact"
            with self.assertRaises(speech_manager.SpeechError) as raised:
                speech_manager._download(source.as_uri(), destination, "0" * 64, 7, "fixture")
            self.assertEqual(raised.exception.code, "SPEECH_CHECKSUM")
            self.assertFalse((destination.parent / ".artifact.part").exists())

    def test_freeze_tree_normalizes_runtime_for_unprivileged_service(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "release"
            executable = root / ".venv/bin/python"
            executable.parent.mkdir(parents=True)
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            data = root / "model.bin"
            data.write_bytes(b"model")
            root.chmod(0o700)
            (root / ".venv").chmod(0o700)
            executable.parent.chmod(0o700)
            executable.chmod(0o700)
            data.chmod(0o600)
            speech_manager.freeze_tree(root)
            self.assertEqual(stat.S_IMODE((root / ".venv").stat().st_mode), 0o555)
            self.assertEqual(stat.S_IMODE(executable.parent.stat().st_mode), 0o555)
            self.assertEqual(stat.S_IMODE(executable.stat().st_mode), 0o555)
            self.assertEqual(stat.S_IMODE(data.stat().st_mode), 0o444)

    def test_manifest_rejects_unknown_field(self) -> None:
        source = ROOT / "packaging/speech-artifacts.toml"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.toml"
            path.write_bytes(source.read_bytes() + b"\nunknown = true\n")
            with self.assertRaises(speech_manager.SpeechError) as raised:
                speech_manager.read_manifest(path, Path(temporary))
            self.assertEqual(raised.exception.code, "SPEECH_MANIFEST")

    def test_authoritative_manifest_hashes_and_voice_policy(self) -> None:
        manifest = speech_manager.read_manifest(ROOT / "packaging/speech-artifacts.toml", Path("/"))
        self.assertEqual(manifest["whisper"]["commit"], "306c88f4d1286aec1bf96e544632897886af5501")
        self.assertEqual(manifest["piper"]["version"], "1.8.0")
        self.assertEqual(manifest["piper_voice"]["id"], "en_US-ljspeech-medium")
        self.assertNotIn("noncommercial", manifest["piper_voice"]["license"].lower())
        self.assertEqual(
            hashlib.sha256((ROOT / manifest["piper"]["lock"]).read_bytes()).hexdigest(),
            manifest["piper"]["lock_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
