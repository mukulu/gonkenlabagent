from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import shutil
from unittest import mock
import importlib.util
import json
import os
import stat
import tempfile
import time
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
        boot = self.system / 'proc/sys/kernel/random/boot_id'
        boot.parent.mkdir(parents=True)
        boot.write_text(install_summary.rr.current_boot_id())
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

    def publish_ready(self, model='qwen3.5:2b-q4_K_M', digest=SHA, **overrides):
        ready = self.system / 'run/gonken-agent/ready.json'
        ready.parent.mkdir(parents=True, exist_ok=True)
        value = {'status':'READY','code':'VOICE_RUNTIME_READY','wake_phrase':'GonKen',
                 'model':model,'model_digest':digest,'release_commit':COMMIT,
                 'release_profile':'core-pi-trixie-py313',
                 'boot_id':install_summary.rr.current_boot_id(),'service_pid':os.getpid(),
                 'service_start_ticks':install_summary.rr.process_start_ticks(os.getpid()),
                 'observed_epoch':int(time.time())}
        value.update(overrides)
        ready.write_text(json.dumps(value))
        return ready

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
        self.publish_ready()
        data = install_summary.build_summary(self.system, COMMIT)
        self.assertEqual(data["status"], "READY")
        self.assertTrue(data["ready"])
        self.assertEqual(data["wake_phrase"], "GonKen")
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
            rows.append({"tag": tag, "digest": f"{index + 1:064x}", "tool_call_smoke": "PASS", "inference_status":"PASS",
                         "stages":[{"stage":s,"status":"PASS"} for s in ("IDENTITY","INFERENCE","TOOLS","UNLOAD")]})
        (state / "roster.json").write_text(json.dumps({
            "format": "gonken-ollama-roster-record-v2", "status": "READY", "models": rows, "context_tokens":2048,
        }) + "\n", encoding="utf-8")
        self.publish_ready('qwen3:0.6b', '1'.zfill(64))
        data = install_summary.build_summary(self.system, COMMIT)
        self.assertEqual(data["ollama_model"], "qwen3:0.6b")
        self.assertTrue(data["ollama_roster"]["governed_roster_active"])
        components = {row["component"]: row for row in data["components"]}
        self.assertEqual(components["ollama_roster"]["code"], "THREE_MODEL_ROSTER_VALIDATED")
        self.assertEqual(components["llm_tool_broker"]["status"], "READY")
        self.assertTrue(data["ready"])

    def test_optional_tool_failures_do_not_block_final_default_summary(self):
        self.test_summary_prefers_governed_roster_active_model_over_legacy_record()
        path = self.system / 'var/lib/gonken-agent/ollama/roster.json'
        payload = json.loads(path.read_text())
        for row in payload['models'][1:]:
            row['tool_call_smoke'] = 'FAILED'
            row['stages'][2]['status'] = 'FAIL'
        path.write_text(json.dumps(payload))
        result = install_summary.build_summary(self.system, COMMIT)
        self.assertTrue(result['ready'])
        self.assertEqual(result['ollama_roster']['roster_capabilities_status'], 'DEGRADED')
        self.assertEqual(len(result['ollama_roster']['tool_incompatible_models']), 2)
        selection = self.system / 'var/lib/gonken-agent/ollama/active-model.json'
        chosen = json.loads(selection.read_text()); chosen['model'] = install_summary.ROSTER_MODELS[-1]
        selection.write_text(json.dumps(chosen))
        with self.assertRaises(install_summary.SummaryError):install_summary.build_summary(self.system, COMMIT)

    def test_summary_rejects_ready_record_from_previous_release(self) -> None:
        self.publish_ready(release_commit='b'*40)
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

    def test_final_required_exit_rejects_degraded_and_accepts_fresh(self):
        args = ['--system-root', str(self.system), '--commit', COMMIT, '--require-ready', '--json']
        with mock.patch.dict(os.environ, {'GONKEN_ENABLE_TEST_FAILURES': '1'}):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(install_summary.main(args), 75)
            self.assertFalse(json.loads(output.getvalue())['ready'])
            self.publish_ready()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(install_summary.main(args), 0)
            # Inspection without a completion claim remains supported.
            (self.system / 'run/gonken-agent/ready.json').unlink()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(install_summary.main(args[:-2] + ['--json']), 0)

    def test_boot_process_and_digest_drift_reject_final_ready(self):
        for field, bad in [('boot_id','old-boot'), ('service_start_ticks',0), ('model_digest','c'*64), ('release_profile','wrong')]:
            with self.subTest(field=field):
                self.publish_ready(**{field:bad})
                self.assertFalse(install_summary.build_summary(self.system, COMMIT)['ready'])

    def test_newer_waiting_record_rejects_old_success(self):
        self.publish_ready()
        directory = self.system / 'run/gonken-agent'
        value = json.loads((directory / 'ready.json').read_text())
        value.update(status='WAITING', code='AUDIO_UNAVAILABLE', observed_epoch=int(time.time()),
                     format='gonken-voice-readiness-v1', component='capture', recoverable=True)
        (directory / 'readiness.json').write_text(json.dumps(value))
        self.assertFalse(install_summary.build_summary(self.system, COMMIT)['ready'])

    def test_roster_labels_without_stages_are_not_qualification(self):
        self.test_summary_prefers_governed_roster_active_model_over_legacy_record()
        path = self.system / 'var/lib/gonken-agent/ollama/roster.json'
        payload = json.loads(path.read_text())
        payload['models'][0]['stages'] = []
        path.write_text(json.dumps(payload))
        with self.assertRaises(install_summary.SummaryError) as raised:
            install_summary.build_summary(self.system, COMMIT)
        self.assertEqual(raised.exception.code, 'SUMMARY_MODEL_QUALIFICATION')

    def test_selection_boolean_generation_and_duplicate_roster_are_rejected(self):
        self.test_summary_prefers_governed_roster_active_model_over_legacy_record()
        path = self.system / 'var/lib/gonken-agent/ollama/active-model.json'
        value = json.loads(path.read_text()); value['generation'] = True
        path.write_text(json.dumps(value))
        with self.assertRaises(install_summary.SummaryError) as raised:
            install_summary.build_summary(self.system, COMMIT)
        self.assertEqual(raised.exception.code, 'SUMMARY_MODEL_SELECTION')
        value['generation'] = 1; path.write_text(json.dumps(value))
        path = self.system / 'var/lib/gonken-agent/ollama/roster.json'
        value = json.loads(path.read_text()); value['models'][-1] = value['models'][0]
        path.write_text(json.dumps(value))
        with self.assertRaises(install_summary.SummaryError) as raised:
            install_summary.build_summary(self.system, COMMIT)
        self.assertEqual(raised.exception.code, 'SUMMARY_MODEL_ROSTER')

    def test_standalone_maintenance_dependencies_are_sufficient(self):
        target = self.root / 'isolated-maintenance'; target.mkdir()
        for source, name in [
            (ROOT/'scripts/install_summary.py','install_summary.py'),
            (ROOT/'src/gonken_agent/runtime_readiness.py','runtime_readiness.py'),
            (ROOT/'src/gonken_agent/llm/qualification.py','model_qualification.py'),
            (ROOT/'src/gonken_agent/llm/models.py','model_catalog.py')]:
            shutil.copyfile(source, target/name)
        # Remove PYTHONPATH and run outside source to prove maintenance copying.
        result = subprocess.run([sys.executable, str(target/'install_summary.py'), '--help'],
                                capture_output=True, text=True, timeout=5, cwd=target,
                                env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--require-ready', result.stdout)

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
