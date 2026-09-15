from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

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
                "bluetooth_audio=requested\nbluetooth_device=SECRET-DEVICE\nsource_url=https://secret.invalid/repo\n",
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
            output = root / "failures"
            path = bundle.create_bundle(state_dir=state, log_dir=logs, source_record=source, output_dir=output, exit_code=74)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
                text = "\n".join(zf.read(name).decode() for name in names)
            self.assertIn("failure.json", names)
            self.assertIn("preflight-prerequisites.json", names)
            self.assertIn("INSTALL_ACTION", text)
            self.assertIn("device:i2c-1", text)
            self.assertNotIn("SECRET-DEVICE", text)
            self.assertNotIn("secret.invalid", text)
            self.assertNotIn("do-not-copy", text)


if __name__ == "__main__":
    unittest.main()
