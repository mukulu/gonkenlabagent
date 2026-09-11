from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "gonken_agent", *arguments],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


class CliProcessTests(unittest.TestCase):
    def test_version_and_status_process_contracts(self) -> None:
        version = run_cli("version")
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(version.stdout.strip(), "0.1.0.dev1")

        status = run_cli("status", "--json")
        self.assertEqual(status.returncode, 0, status.stderr)
        payload = json.loads(status.stdout)
        self.assertIs(payload["core_runtime_ready"], False)
        self.assertEqual(set(payload["extensions"].values()), {"disabled"})

    def test_run_process_fails_closed_without_importing_legacy_runtime(self) -> None:
        result = run_cli("run")
        self.assertEqual(result.returncode, 3)
        self.assertIn("not implemented", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_effective_config_process_is_local_and_redacted(self) -> None:
        result = run_cli("config", "show", "--effective", "--no-site", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        serialized = json.dumps(payload)
        self.assertEqual(payload["config"]["llm"]["model"], "qwen3.5:2b-q4_K_M")
        self.assertNotIn(str(ROOT), serialized)

    def test_service_process_once_is_content_free_and_degraded(self) -> None:
        snapshot_dir = ROOT / ".pytest-cli-startup-snapshots"
        if snapshot_dir.exists():
            import shutil
            shutil.rmtree(snapshot_dir)
        result = run_cli("service", "--no-site", "--once", "--snapshot-dir", str(snapshot_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["service"], "gonken-agent")
        self.assertEqual(payload["mode"], "headless-supervisor")
        self.assertEqual(payload["status"], "DEGRADED")
        self.assertEqual(payload["startup_snapshot"]["status"], "RECORDED")
        self.assertTrue(payload["ready_for_systemd"])
        self.assertIn("service", json.dumps(payload))
        self.assertNotIn(str(ROOT), json.dumps(payload))
        self.assertTrue((snapshot_dir / "latest.json").is_file())
        import shutil
        shutil.rmtree(snapshot_dir)


if __name__ == "__main__":
    unittest.main()
