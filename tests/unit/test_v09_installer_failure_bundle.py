from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("installer_failure_bundle", ROOT / "scripts" / "installer_failure_bundle.py")
assert SPEC and SPEC.loader
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class InstallerFailureBundleTests(unittest.TestCase):
    def test_bundle_is_private_allowlisted_and_works_without_active_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"; artifacts = state / "artifacts"; artifacts.mkdir(parents=True)
            logs = root / "logs"; events = logs / "events"; events.mkdir(parents=True)
            source = root / "source.record"
            source.write_text(
                "format=gonken-bootstrap-source-v1\nresolved_commit=" + "a"*40 + "\nplatform_mode=target\n"
                "source_mode=local-checkpoint\narchitecture=aarch64\nos_version_id=13\nos_codename=trixie\n"
                "bluetooth_audio=requested\nbluetooth_device=SECRET-DEVICE\n"
                "environment_profile=real-sensor-simulated-actuator\nenvironment_sensor_address=0x44\n"
                "source_url=https://secret.invalid/repo\n",
                encoding="utf-8",
            )
            (events / "1.event").write_text(
                "format=gonken-install-event-v1\nlevel=error\ncode=INSTALL_ACTION\nstep_id=immutable_release\nmessage=action_failed\nsecret=do-not-copy\n",
                encoding="utf-8",
            )
            (artifacts / "target-preflight-prerequisites.json").write_text(json.dumps({
                "format":"gonken-target-preflight-v1","phase":"prerequisites","status":"WARN",
                "required_failures":[],"warnings":["device:i2c-1"],"checks":[{"id":"device:i2c-1","required":False,"ok":False,"detail":"absent","remediation":"enable later"}],
            }), encoding="utf-8")
            output = root / "failures"; output.mkdir()
            with patch.object(bundle, "target_manifest", return_value={
                "format": "gonken-target-hardware-manifest-v1",
                "raspberry_pi": {"model": "Raspberry Pi 5 Model B"},
                "privacy": {
                    "raw_audio_included": False,
                    "transcripts_included": False,
                    "prompts_or_model_responses_included": False,
                },
                "physical_acceptance_claimed": False,
                "failure_bundle_member_status": "READY",
            }), patch.object(bundle, "platform_inventory", return_value={
                "schema": 1,
                "content_logging": False,
                "commands": {"gpioinfo": True, "i2cdetect": True},
            }), patch.object(bundle, "service_event_codes", return_value={
                "status": "READY",
                "units": {"gonken-agent.service": {"status": "DEGRADED", "codes": {"WAKE_LED_GPIO_LINE_AMBIGUOUS": 2}}},
            }):
                path = bundle.create_bundle(state_dir=state, log_dir=logs, source_record=source, output_dir=output, exit_code=74)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
                text = "\n".join(zf.read(name).decode() for name in names)
                index = json.loads(zf.read("evidence_index.json"))
                target = json.loads(zf.read("target_manifest.json"))
                service = json.loads(zf.read("service_events.json"))
            self.assertIn("installer/failure.json", names)
            self.assertIn("platform_inventory.json", names)
            self.assertIn("target_manifest.json", names)
            self.assertIn("service_events.json", names)
            self.assertIn("evidence_index.json", names)
            self.assertIn("installer/preflight-prerequisites.json", names)
            self.assertIn("INSTALL_ACTION", text)
            self.assertIn("device:i2c-1", text)
            self.assertIn("target_manifest.json", {item["path"] for item in index["members"]})
            self.assertEqual(index["format"], "gonken-evidence-bundle-index-v2")
            self.assertEqual(index["bundle_kind"], "combined_installer_failure_support")
            self.assertEqual(target["raspberry_pi"]["model"], "Raspberry Pi 5 Model B")
            self.assertEqual(service["units"]["gonken-agent.service"]["codes"]["WAKE_LED_GPIO_LINE_AMBIGUOUS"], 2)
            self.assertNotIn("SECRET-DEVICE", text)
            self.assertNotIn("secret.invalid", text)
            self.assertNotIn("do-not-copy", text)


    def test_bundle_merges_canonical_support_once_and_names_installer_members(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"; (state / "artifacts").mkdir(parents=True)
            logs = root / "logs"; (logs / "events").mkdir(parents=True)
            source = root / "source.record"
            source.write_text(
                "format=gonken-bootstrap-source-v1\nresolved_commit=" + "b"*40 + "\n"
                "platform_mode=target\nsource_mode=local-checkpoint\n", encoding="utf-8"
            )
            common = {
                "configuration.json": {"status": "READY", "config": {}},
                "runtime_bindings.json": {"status": "READY"},
                "target_manifest.json": {"status": "READY", "physical_acceptance_claimed": False},
            }
            (root / "out").mkdir()
            with patch.object(bundle, "_collect_support_payloads", return_value=(common, [])), \
                 patch.object(bundle, "_current_readiness", return_value={
                     "status": "WAITING", "code": "AUDIO_CAPTURE_FAILED",
                     "component": "audio_capture", "recoverable": True, "observed_epoch": 1,
                 }):
                path = bundle.create_bundle(
                    state_dir=state, log_dir=logs, source_record=source,
                    output_dir=root / "out", exit_code=75,
                )
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                index = json.loads(zf.read("evidence_index.json"))
                failure = json.loads(zf.read("installer/failure.json"))
                source_payload = json.loads(zf.read("installer/source.json"))
            self.assertEqual(names.count("target_manifest.json"), 1)
            self.assertIn("installer/source.json", names)
            self.assertIn("configuration.json", names)
            self.assertEqual(failure["current_failure"]["runtime_readiness"]["code"], "AUDIO_CAPTURE_FAILED")
            self.assertIsNone(source_payload.get("environment_profile"))
            self.assertEqual(index["omitted_sections"], [])


    def test_explicit_output_dir_must_preexist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"; (state / "artifacts").mkdir(parents=True)
            logs = root / "logs"; (logs / "events").mkdir(parents=True)
            source = root / "source.record"
            source.write_text(
                "format=gonken-bootstrap-source-v1\nresolved_commit=" + "c"*40 + "\n"
                "platform_mode=target\nsource_mode=local-checkpoint\n", encoding="utf-8"
            )
            missing = root / "operator-created-destination"
            with self.assertRaisesRegex(ValueError, "existing real directory"):
                bundle.create_bundle(
                    state_dir=state, log_dir=logs, source_record=source,
                    output_dir=missing, exit_code=75,
                )
            self.assertFalse(missing.exists())



if __name__ == "__main__":
    unittest.main()
