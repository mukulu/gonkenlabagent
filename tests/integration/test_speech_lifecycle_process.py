from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANAGER = ROOT / "scripts/speech_manager.py"
WHISPER_PATH = "/var/lib/gonken-agent/models/whisper/base.en-q5_1.bin"
VOICE_PATH = "/var/lib/gonken-agent/models/piper/en_US-ljspeech-medium/en_US-ljspeech-medium.onnx"


class SpeechFixture:
    def __init__(self, root: Path):
        self.root = root
        self.system_root = root / "system"
        self.system_root.mkdir()
        self.bundle = root / "bundle"
        (self.bundle / "packaging").mkdir(parents=True)
        (self.bundle / "requirements").mkdir()
        self.artifacts = root / "artifacts"
        self.artifacts.mkdir()
        self.whisper_model = self.artifacts / "whisper.bin"
        self.voice = self.artifacts / "voice.onnx"
        self.voice_config = self.artifacts / "voice.json"
        self.card = self.artifacts / "MODEL_CARD"
        self.whisper_model.write_bytes(b"whisper-fixture-model")
        self.voice.write_bytes(b"piper-fixture-model")
        self.voice_config.write_text(json.dumps({"audio": {"sample_rate": 22050}}), encoding="utf-8")
        self.card.write_text("MIT fixture; public domain dataset\n", encoding="utf-8")
        self.lock = self.bundle / "requirements/piper.lock"
        self.lock.write_text("--require-hashes\n--only-binary=:all:\npiper-tts==1.8.0 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
        self.whisper = root / "fake-whisper"
        self.whisper.write_text(textwrap.dedent("""\
            #!/usr/bin/env python3
            import pathlib, sys
            if "--help" in sys.argv:
                print("fixture whisper")
                raise SystemExit(0)
            prefix = pathlib.Path(sys.argv[sys.argv.index("-of") + 1])
            pathlib.Path(str(prefix) + ".txt").write_text("This is a speech check.\\n", encoding="utf-8")
        """), encoding="utf-8")
        self.whisper.chmod(0o755)
        self.piper = root / "fake-piper-python"
        self.piper.write_text(textwrap.dedent("""\
            #!/usr/bin/env python3
            import pathlib, struct, sys, wave
            if "-c" in sys.argv:
                print("1.8.0")
                raise SystemExit(0)
            output = pathlib.Path(sys.argv[sys.argv.index("--output_file") + 1])
            with wave.open(str(output), "wb") as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(22050)
                wav.writeframes(struct.pack("<h", 500) * 4410)
        """), encoding="utf-8")
        self.piper.chmod(0o755)
        self.manifest = self.bundle / "packaging/speech.toml"
        self._write_manifest()

    @staticmethod
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_manifest(self) -> None:
        self.manifest.write_text(textwrap.dedent(f"""\
            format = "gonken-speech-artifacts-v1"
            verified_at = "2026-09-09"
            [whisper]
            version = "1.9.2"
            release_tag = "v1.9.2"
            commit = "{'1' * 40}"
            repository = "https://example.invalid/whisper.git"
            license = "MIT"
            source = "https://example.invalid/whisper"
            cmake_arguments = ["-DTEST=ON"]
            [whisper_model]
            id = "base.en-q5_1"
            filename = "base.en-q5_1.bin"
            upstream_filename = "fixture.bin"
            source_commit = "{'2' * 40}"
            url = "{self.whisper_model.as_uri()}"
            sha256 = "{self.digest(self.whisper_model)}"
            size = {self.whisper_model.stat().st_size}
            license = "MIT"
            source = "https://example.invalid/model"
            [piper]
            version = "1.8.0"
            release_tag = "v1.8.0"
            commit = "{'3' * 40}"
            platform = "manylinux_2_28_aarch64"
            profile = "fixture"
            lock = "requirements/piper.lock"
            lock_sha256 = "{self.digest(self.lock)}"
            wheel = "piper.whl"
            wheel_sha256 = "{'4' * 64}"
            license = "GPL-3.0-or-later"
            source = "https://example.invalid/piper"
            distribution = "test-only"
            [piper_voice]
            id = "en_US-ljspeech-medium"
            repository_commit = "{'5' * 40}"
            filename = "en_US-ljspeech-medium.onnx"
            url = "{self.voice.as_uri()}"
            sha256 = "{self.digest(self.voice)}"
            size = {self.voice.stat().st_size}
            config_filename = "en_US-ljspeech-medium.onnx.json"
            config_url = "{self.voice_config.as_uri()}"
            config_sha256 = "{self.digest(self.voice_config)}"
            config_size = {self.voice_config.stat().st_size}
            model_card_filename = "MODEL_CARD"
            model_card_url = "{self.card.as_uri()}"
            model_card_sha256 = "{self.digest(self.card)}"
            model_card_size = {self.card.stat().st_size}
            license = "MIT repository; public-domain source dataset"
            license_source = "https://example.invalid/card"
            source = "https://example.invalid/voice"
            [smoke]
            text = "This is a speech check."
            required_tokens = ["speech", "check"]
            minimum_wav_frames = 2205
            maximum_wav_seconds = 20
        """), encoding="utf-8")

    def command(self, action: str) -> list[str]:
        command = [sys.executable, str(MANAGER), action, "--manifest", str(self.manifest), "--system-root", str(self.system_root)]
        if action in {"models-status", "provision-models", "smoke-status", "run-smoke"}:
            command += ["--whisper-model-path", WHISPER_PATH, "--piper-voice-path", VOICE_PATH]
        if action == "run-smoke":
            command += ["--threads", "2"]
        return command

    def run(self, action: str, interrupt: str | None = None) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update({
            "GONKEN_ENABLE_TEST_FAILURES": "1",
            "GONKEN_SPEECH_TEST_WHISPER_BINARY": str(self.whisper),
            "GONKEN_SPEECH_TEST_PIPER_PYTHON": str(self.piper),
        })
        if interrupt:
            environment["GONKEN_SPEECH_TEST_INTERRUPT"] = interrupt
        return subprocess.run(self.command(action), cwd=ROOT, env=environment, check=False, capture_output=True, text=True, timeout=20)

    def provision(self) -> None:
        for action in ("install-whisper", "install-piper", "provision-models", "run-smoke"):
            result = self.run(action)
            if result.returncode != 0:
                raise AssertionError(result.stderr)


class SpeechLifecycleProcessTests(unittest.TestCase):
    def fixture(self) -> SpeechFixture:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return SpeechFixture(Path(temporary.name))

    def test_full_lifecycle_repeat_status_and_private_record(self) -> None:
        fixture = self.fixture()
        fixture.provision()
        for action in ("whisper-status", "piper-status", "models-status", "smoke-status"):
            result = fixture.run(action)
            self.assertEqual(result.returncode, 0, result.stderr)
        repeat = fixture.run("run-smoke")
        self.assertEqual(repeat.returncode, 0, repeat.stderr)
        record = fixture.system_root / "var/lib/gonken-agent/install/speech.record"
        self.assertEqual(stat.S_IMODE(record.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(record.stat().st_mode), 0o600)
        self.assertIn("validation=passed", record.read_text(encoding="utf-8"))

    def test_zero_byte_bad_checksum_and_missing_pair_repair(self) -> None:
        fixture = self.fixture()
        fixture.provision()
        whisper = fixture.system_root / WHISPER_PATH.lstrip("/")
        voice_dir = fixture.system_root / "var/lib/gonken-agent/models/piper/en_US-ljspeech-medium"
        whisper.chmod(0o644)
        whisper.write_bytes(b"")
        self.assertNotEqual(fixture.run("models-status").returncode, 0)
        self.assertEqual(fixture.run("provision-models").returncode, 0)
        config = voice_dir / "en_US-ljspeech-medium.onnx.json"
        voice_dir.chmod(0o755)
        config.chmod(0o644)
        config.unlink()
        self.assertEqual(fixture.run("provision-models").returncode, 0)
        model = voice_dir / "en_US-ljspeech-medium.onnx"
        voice_dir.chmod(0o755)
        model.chmod(0o644)
        model.write_bytes(b"corrupt")
        self.assertEqual(fixture.run("provision-models").returncode, 0)
        self.assertEqual(fixture.run("models-status").returncode, 0)

    def test_wrong_architecture_native_payload_is_rejected_and_repaired(self) -> None:
        fixture = self.fixture()
        self.assertEqual(fixture.run("install-piper").returncode, 0)
        native = fixture.system_root / "usr/local/lib/gonken-speech/piper/releases/v1.8.0/wrong.so"
        native.parent.chmod(0o755)
        header = bytearray(20)
        header[:6] = b"\x7fELF\x02\x01"
        header[18:20] = (62).to_bytes(2, "little")
        native.write_bytes(header)
        self.assertNotEqual(fixture.run("piper-status").returncode, 0)
        self.assertEqual(fixture.run("install-piper").returncode, 0)
        self.assertEqual(fixture.run("piper-status").returncode, 0)

    def _assert_interrupted_boundary_converges(self, action: str, boundary: str) -> None:
        fixture = self.fixture()
        if action == "provision-models":
            self.assertEqual(fixture.run("install-whisper").returncode, 0)
            self.assertEqual(fixture.run("install-piper").returncode, 0)
        interrupted = fixture.run(action, boundary)
        self.assertEqual(interrupted.returncode, 91, interrupted.stderr)
        rerun = fixture.run(action)
        self.assertEqual(rerun.returncode, 0, rerun.stderr)

    def test_interrupt_whisper_source_before_converges_on_rerun(self) -> None:
        self._assert_interrupted_boundary_converges("install-whisper", "whisper_source:before")

    def test_interrupt_whisper_source_during_converges_on_rerun(self) -> None:
        self._assert_interrupted_boundary_converges("install-whisper", "whisper_source:during")

    def test_interrupt_whisper_finalize_during_converges_on_rerun(self) -> None:
        self._assert_interrupted_boundary_converges("install-whisper", "whisper_finalize:during")

    def test_interrupt_piper_install_during_converges_on_rerun(self) -> None:
        self._assert_interrupted_boundary_converges("install-piper", "piper_install:during")

    def test_interrupt_piper_finalize_during_converges_on_rerun(self) -> None:
        self._assert_interrupted_boundary_converges("install-piper", "piper_finalize:during")

    def test_interrupt_whisper_model_download_during_converges_on_rerun(self) -> None:
        self._assert_interrupted_boundary_converges("provision-models", "whisper_model_download:during")

    def test_interrupt_piper_pair_download_during_converges_on_rerun(self) -> None:
        self._assert_interrupted_boundary_converges("provision-models", "piper_pair_download:during")

    def test_interrupt_piper_pair_finalize_during_converges_on_rerun(self) -> None:
        self._assert_interrupted_boundary_converges("provision-models", "piper_pair_finalize:during")

    def test_smoke_failure_does_not_create_success_record_and_reruns(self) -> None:
        fixture = self.fixture()
        for action in ("install-whisper", "install-piper", "provision-models"):
            self.assertEqual(fixture.run(action).returncode, 0)
        interrupted = fixture.run("run-smoke", "speech_smoke:during")
        self.assertEqual(interrupted.returncode, 91)
        record = fixture.system_root / "var/lib/gonken-agent/install/speech.record"
        self.assertFalse(record.exists())
        self.assertEqual(fixture.run("run-smoke").returncode, 0)


if __name__ == "__main__":
    unittest.main()
