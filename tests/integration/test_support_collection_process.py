from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SupportCollectionProcessTests(unittest.TestCase):
    def test_installed_maintenance_wrapper_uses_release_local_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            maintenance = current / "maintenance"
            bin_dir = current / ".venv" / "bin"
            maintenance.mkdir(parents=True)
            bin_dir.mkdir(parents=True)
            shutil.copy2(ROOT / "scripts" / "collect-support.sh", maintenance / "collect-support.sh")
            (maintenance / "collect-support.sh").chmod(0o755)
            output = root / "support.zip"
            calls = root / "calls.log"
            fake = bin_dir / "gonken-agent"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$@\" > \"$GONKEN_FAKE_SUPPORT_LOG\"\n"
                "while [[ $# -gt 0 ]]; do\n"
                "  if [[ \"$1\" == \"--output\" ]]; then printf '{}' > \"$2\"; exit 0; fi\n"
                "  shift\n"
                "done\n"
                "exit 64\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = os.environ.copy()
            env["GONKEN_FAKE_SUPPORT_LOG"] = str(calls)
            result = subprocess.run(
                [
                    str(maintenance / "collect-support.sh"),
                    "--output",
                    str(output),
                    "--site",
                    str(root / "missing-site.toml"),
                    "--telemetry",
                    str(root / "missing-telemetry.jsonl"),
                    "--startup-snapshot",
                    str(root / "missing-startup.json"),
                ],
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip().splitlines()[-1], str(output))
            recorded = calls.read_text(encoding="utf-8")
            self.assertIn("support", recorded)
            self.assertIn("--no-site", recorded)
            self.assertNotIn("--telemetry", recorded)
            self.assertNotIn("--startup-snapshot", recorded)
            self.assertNotIn("--target-manifest", recorded)

    def test_output_dir_places_single_bundle_at_requested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            maintenance = current / "maintenance"
            bin_dir = current / ".venv" / "bin"
            maintenance.mkdir(parents=True)
            bin_dir.mkdir(parents=True)
            shutil.copy2(ROOT / "scripts" / "collect-support.sh", maintenance / "collect-support.sh")
            (maintenance / "collect-support.sh").chmod(0o755)
            outdir = root / "out"; outdir.mkdir()
            calls = root / "calls.log"
            fake = bin_dir / "gonken-agent"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$@\" > \"$GONKEN_FAKE_SUPPORT_LOG\"\n"
                "while [[ $# -gt 0 ]]; do\n"
                "  if [[ \"$1\" == \"--output\" ]]; then printf '{}' > \"$2\"; exit 0; fi\n"
                "  shift\n"
                "done\nexit 64\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = os.environ.copy(); env["GONKEN_FAKE_SUPPORT_LOG"] = str(calls)
            result = subprocess.run(
                [str(maintenance / "collect-support.sh"), "--output-dir", str(outdir),
                 "--site", str(root / "missing-site.toml")],
                check=False, capture_output=True, text=True, env=env, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = Path(result.stdout.strip().splitlines()[-1])
            self.assertEqual(output.parent, outdir)
            self.assertTrue(output.name.startswith("gonken-support-"))
            self.assertTrue(output.is_file())

    def test_installed_maintenance_wrapper_auto_embeds_target_probe_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            maintenance = current / "maintenance"
            bin_dir = current / ".venv" / "bin"
            maintenance.mkdir(parents=True)
            bin_dir.mkdir(parents=True)
            shutil.copy2(ROOT / "scripts" / "collect-support.sh", maintenance / "collect-support.sh")
            (maintenance / "collect-support.sh").chmod(0o755)
            (maintenance / "target_probe.py").write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "output = sys.argv[sys.argv.index('--output') + 1]\n"
                "payload = {\n"
                "  'format': 'gonken-target-hardware-manifest-v1',\n"
                "  'privacy': {'raw_audio_included': False, 'transcripts_included': False, 'prompts_or_model_responses_included': False},\n"
                "  'physical_acceptance_claimed': False,\n"
                "}\n"
                "open(output, 'w', encoding='utf-8').write(json.dumps(payload))\n"
                "print(json.dumps(payload))\n",
                encoding="utf-8",
            )
            (maintenance / "target_probe.py").chmod(0o755)
            output = root / "support.zip"
            calls = root / "calls.log"
            fake = bin_dir / "gonken-agent"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$@\" > \"$GONKEN_FAKE_SUPPORT_LOG\"\n"
                "while [[ $# -gt 0 ]]; do\n"
                "  if [[ \"$1\" == \"--output\" ]]; then printf '{}' > \"$2\"; exit 0; fi\n"
                "  shift\n"
                "done\n"
                "exit 64\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = os.environ.copy()
            env["GONKEN_FAKE_SUPPORT_LOG"] = str(calls)
            result = subprocess.run(
                [str(maintenance / "collect-support.sh"), "--output", str(output), "--site", str(root / "missing-site.toml")],
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            recorded = calls.read_text(encoding="utf-8")
            self.assertIn("--target-manifest", recorded)

    def test_output_dir_must_preexist_and_is_not_created_by_sudo_capable_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            maintenance = current / "maintenance"
            bin_dir = current / ".venv" / "bin"
            maintenance.mkdir(parents=True)
            bin_dir.mkdir(parents=True)
            shutil.copy2(ROOT / "scripts" / "collect-support.sh", maintenance / "collect-support.sh")
            (maintenance / "collect-support.sh").chmod(0o755)
            fake = bin_dir / "gonken-agent"
            fake.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
            fake.chmod(0o755)
            missing = root / "operator-created-destination"
            result = subprocess.run(
                [str(maintenance / "collect-support.sh"), "--output-dir", str(missing)],
                check=False, capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 64)
            self.assertIn("existing real directory", result.stderr)
            self.assertFalse(missing.exists())



if __name__ == "__main__":
    unittest.main()
