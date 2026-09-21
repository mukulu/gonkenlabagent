from __future__ import annotations

import importlib.util
import json
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
                "package_version": "0.2.0.dev0",
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
        service_template = self.release / "maintenance/packaging/systemd/gonken-agent.service"
        service_template.parent.mkdir(parents=True, exist_ok=True)
        service_template.write_text("[Unit]\nDescription=fixture\n", encoding="utf-8")
        installed_service = self.system / "etc/systemd/system/gonken-agent.service"
        installed_service.parent.mkdir(parents=True, exist_ok=True)
        installed_service.write_bytes(service_template.read_bytes())

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
        self.assertEqual(data["completed_milestones"], ["M3.3", "M3.4", "M3.5", "M6.2"])
        components = {row["component"]: row for row in data["components"]}
        self.assertEqual(components["speech_artifacts"]["status"], "READY")
        self.assertEqual(components["app_service"]["code"], "HEADLESS_SERVICE_VALIDATED")
        self.assertIn("audio device", data["next_action"])
        self.assertNotIn(str(self.system), str(data))

    def test_summary_reports_ready_when_voice_runtime_ready_file_exists(self) -> None:
        ready = self.system / "run/gonken-agent/ready.json"
        ready.parent.mkdir(parents=True, exist_ok=True)
        ready.write_text(
            '{"status":"READY","code":"VOICE_RUNTIME_READY","wake_phrase":"Hey Gonken",'
            '"model":"qwen3.5:2b-q4_K_M","release_commit":"' + COMMIT + '"}\n',
            encoding="utf-8",
        )
        data = install_summary.build_summary(self.system, COMMIT)
        self.assertEqual(data["status"], "READY")
        self.assertTrue(data["ready"])
        self.assertEqual(data["wake_phrase"], "Hey Gonken")
        components = {row["component"]: row for row in data["components"]}
        self.assertEqual(components["input_audio"]["status"], "READY")
        self.assertEqual(components["wake_runtime"]["code"], "WAKE_STANDBY_READY")

    def test_summary_prefers_governed_roster_active_model_over_legacy_record(self) -> None:
        state = self.system / "var/lib/gonken-agent/ollama"
        state.mkdir(parents=True, exist_ok=True)
        (state / "active-model.json").write_text(json.dumps({
            "format": "gonken-active-model-v1", "model": "qwen3:0.6b", "generation": 2,
            "previous_model": "qwen3.5:2b-q4_K_M",
        }) + "\n", encoding="utf-8")
        rows = []
        for index, tag in enumerate(install_summary.ROSTER_MODELS):
            rows.append({"tag": tag, "digest": f"{index + 1:064x}", "tool_call_smoke": "PASS"})
        (state / "roster.json").write_text(json.dumps({
            "format": "gonken-ollama-roster-record-v2", "status": "READY", "models": rows,
        }) + "\n", encoding="utf-8")
        ready = self.system / "run/gonken-agent/ready.json"
        ready.parent.mkdir(parents=True, exist_ok=True)
        ready.write_text(json.dumps({
            "status": "READY", "code": "VOICE_RUNTIME_READY", "wake_phrase": "GonKen",
            "model": "qwen3:0.6b", "release_commit": COMMIT,
        }) + "\n", encoding="utf-8")
        data = install_summary.build_summary(self.system, COMMIT)
        self.assertEqual(data["ollama_model"], "qwen3:0.6b")
        self.assertTrue(data["ollama_roster"]["governed_roster_active"])
        components = {row["component"]: row for row in data["components"]}
        self.assertEqual(components["ollama_roster"]["code"], "THREE_MODEL_ROSTER_VALIDATED")
        self.assertEqual(components["llm_tool_broker"]["status"], "READY")
        self.assertTrue(data["ready"])

    def test_summary_rejects_ready_record_from_previous_release(self) -> None:
        ready = self.system / "run/gonken-agent/ready.json"
        ready.parent.mkdir(parents=True, exist_ok=True)
        ready.write_text(
            '{"status":"READY","code":"VOICE_RUNTIME_READY","wake_phrase":"GonKen",'
            '"model":"qwen3.5:2b-q4_K_M","release_commit":"' + ("b" * 40) + '"}\n',
            encoding="utf-8",
        )
        data = install_summary.build_summary(self.system, COMMIT)
        self.assertEqual(data["status"], "DEGRADED")
        self.assertFalse(data["ready"])

    def test_summary_reports_service_degraded_when_unit_differs(self) -> None:
        installed = self.system / "etc/systemd/system/gonken-agent.service"
        installed.write_text("[Unit]\nDescription=drift\n", encoding="utf-8")
        data = install_summary.build_summary(self.system, COMMIT)
        components = {row["component"]: row for row in data["components"]}
        self.assertEqual(components["app_service"]["status"], "DEGRADED")
        self.assertEqual(components["app_service"]["code"], "HEADLESS_SERVICE_NOT_READY")
        self.assertNotIn("M6.2", data["completed_milestones"])

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
