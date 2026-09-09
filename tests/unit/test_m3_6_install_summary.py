from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "install_summary", ROOT / "scripts" / "install_summary.py"
)
assert SPEC and SPEC.loader
install_summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install_summary)


COMMIT = "a" * 40
SHA = "b" * 64


def write_record(path: Path, fields: tuple[str, ...], values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for field in fields:
        payload.append(f"{field}={values[field]}")
    path.write_text("\n".join(payload) + "\n", encoding="utf-8")
    path.chmod(0o600)


class InstallSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.system = self.root / "system"
        self.system.mkdir()
        self.release = self.system / "usr/local/lib/gonken-agent/releases" / COMMIT
        self.release.mkdir(parents=True)
        (self.system / "usr/local/lib/gonken-agent/current").symlink_to(f"releases/{COMMIT}")
        write_record(
            self.release / "release.record",
            install_summary.RELEASE_FIELDS,
            {
                "format": "gonken-release-v1",
                "commit": COMMIT,
                "profile": "core-pi-trixie-py313",
                "python_version": "3.13.5",
                "package_version": "0.1.0.dev1",
                "lock_sha256": SHA,
                "wheel_sha256": SHA,
                "build_backend": "setuptools",
                "maintenance_sha256": SHA,
                "payload_sha256": SHA,
                "owner_uid": "0",
                "payload_size_kib": "100",
                "built_epoch": "1788963338",
                "validation": "passed",
            },
        )
        write_record(
            self.system / "var/lib/gonken-agent/install/ollama.record",
            install_summary.OLLAMA_FIELDS,
            {
                "format": "gonken-ollama-install-v1",
                "ollama_version": "0.33.3",
                "ollama_asset": "ollama-linux-arm64.tar.zst",
                "ollama_sha256": SHA,
                "binary_sha256": SHA,
                "unit_sha256": SHA,
                "dropin_sha256": SHA,
                "endpoint": "http://127.0.0.1:11434",
                "model": "qwen3.5:2b-q4_K_M",
                "model_digest": SHA,
                "model_digest_prefix": SHA[:12],
                "quantization": "Q4_K_M",
                "parameter_size": "2.27B",
                "context_tokens": "2048",
                "max_loaded_models": "1",
                "num_parallel": "1",
                "no_cloud": "1",
                "pull_total_bytes": "1900000000",
                "smoke_total_ns": "1234",
                "smoke_eval_count": "1",
                "validated_epoch": "1788963338",
                "validation": "passed",
            },
        )
        write_record(
            self.system / "var/lib/gonken-agent/install/speech.record",
            install_summary.SPEECH_FIELDS,
            {
                "format": "gonken-speech-install-v1",
                "whisper_version": "1.9.2",
                "whisper_binary_sha256": SHA,
                "whisper_model_sha256": SHA,
                "piper_version": "1.8.0",
                "piper_lock_sha256": SHA,
                "piper_voice": "en_US-ljspeech-medium",
                "piper_voice_sha256": SHA,
                "piper_config_sha256": SHA,
                "tts_sample_rate": "22050",
                "tts_frames": "4410",
                "stt_required_tokens": "speech,check",
                "validated_epoch": "1788963338",
                "validation": "passed",
            },
        )

    def test_summary_reports_degraded_not_ready_with_exact_next_action(self) -> None:
        data = install_summary.build_summary(self.system, COMMIT)
        self.assertEqual(data["status"], "DEGRADED")
        self.assertFalse(data["ready"])
        self.assertEqual(data["code"], "M3_6_INSTALL_SUMMARY")
        self.assertEqual(data["completed_milestones"], ["M3.3", "M3.4", "M3.5"])
        components = {row["component"]: row for row in data["components"]}
        self.assertEqual(components["speech_artifacts"]["status"], "READY")
        self.assertEqual(components["app_service"]["code"], "M6_SERVICE_NOT_IMPLEMENTED")
        self.assertIn("M6.1 application service", data["next_action"])
        self.assertNotIn(str(self.system), str(data))

    def test_records_are_closed_schema_private_and_policy_checked(self) -> None:
        record = self.system / "var/lib/gonken-agent/install/speech.record"
        record.chmod(0o644)
        with self.assertRaises(install_summary.SummaryError) as raised:
            install_summary.build_summary(self.system, COMMIT)
        self.assertEqual(raised.exception.code, "SUMMARY_RECORD_MODE")
        record.chmod(0o600)
        text = record.read_text(encoding="utf-8").replace(
            "piper_voice=en_US-ljspeech-medium",
            "piper_voice=en_GB-semaine-medium",
        )
        record.write_text(text, encoding="utf-8")
        with self.assertRaises(install_summary.SummaryError) as raised:
            install_summary.build_summary(self.system, COMMIT)
        self.assertEqual(raised.exception.code, "SUMMARY_SPEECH")

    def test_current_pointer_must_match_commit(self) -> None:
        current = self.system / "usr/local/lib/gonken-agent/current"
        current.unlink()
        current.symlink_to("releases/" + "c" * 40)
        with self.assertRaises(install_summary.SummaryError) as raised:
            install_summary.build_summary(self.system, COMMIT)
        self.assertEqual(raised.exception.code, "SUMMARY_RELEASE")


if __name__ == "__main__":
    unittest.main()
