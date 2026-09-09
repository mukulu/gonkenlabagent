from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANAGER = ROOT / "scripts/uninstall_manager.py"
UNIT = ROOT / "packaging/systemd/gonken-agent.service"
TMPFILES = ROOT / "packaging/tmpfiles/gonken-agent.conf"


class UninstallFixture:
    def __init__(self, root: Path):
        self.root = root
        self.system_root = root / "system"
        self.system_root.mkdir()
        self.systemctl_log = root / "systemctl.log"
        self.systemctl = root / "systemctl"
        self.systemctl.write_text(
            "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$GONKEN_FAKE_SYSTEMCTL_LOG\"\nexit 0\n",
            encoding="utf-8",
        )
        self.systemctl.chmod(0o755)
        self.unit = self.system_root / "etc/systemd/system/gonken-agent.service"
        self.tmpfiles = self.system_root / "etc/tmpfiles.d/gonken-agent.conf"
        self.release = self.system_root / "usr/local/lib/gonken-agent"
        self.entrypoint = self.system_root / "usr/local/bin/gonken-agent"
        self.state = self.system_root / "var/lib/gonken-agent"
        self.cache = self.system_root / "var/cache/gonken-agent"
        self.corpus = self.system_root / "srv/gonken-agent"
        self.ollama_unit = self.system_root / "etc/systemd/system/ollama.service"

    def populate(self) -> None:
        self.unit.parent.mkdir(parents=True, exist_ok=True)
        self.unit.write_bytes(UNIT.read_bytes())
        self.tmpfiles.parent.mkdir(parents=True, exist_ok=True)
        self.tmpfiles.write_bytes(TMPFILES.read_bytes())
        (self.release / "releases" / ("a" * 40)).mkdir(parents=True)
        (self.system_root / "usr/local/bin").mkdir(parents=True, exist_ok=True)
        self.entrypoint.symlink_to("../lib/gonken-agent/current/.venv/bin/gonken-agent")
        (self.state / "install").mkdir(parents=True)
        (self.cache / "downloads").mkdir(parents=True)
        (self.corpus / "corpus").mkdir(parents=True)
        self.ollama_unit.parent.mkdir(parents=True, exist_ok=True)
        self.ollama_unit.write_text("[Unit]\nDescription=Ollama shared fixture\n", encoding="utf-8")

    def run(self, *extra: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["GONKEN_ENABLE_TEST_FAILURES"] = "1"
        environment["GONKEN_FAKE_SYSTEMCTL_LOG"] = str(self.systemctl_log)
        return subprocess.run(
            [
                sys.executable,
                str(MANAGER),
                "--system-root",
                str(self.system_root),
                "--unit-template",
                str(UNIT),
                "--tmpfiles-template",
                str(TMPFILES),
                "--systemctl",
                str(self.systemctl),
                *extra,
            ],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )


class UninstallManagerTests(unittest.TestCase):
    def fixture(self) -> UninstallFixture:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return UninstallFixture(Path(temporary.name))

    def test_keep_data_default_removes_code_and_service_but_retains_data(self) -> None:
        fixture = self.fixture()
        fixture.populate()
        result = fixture.run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("UNINSTALL_COMPLETE", result.stdout)
        self.assertFalse(fixture.unit.exists())
        self.assertFalse(fixture.tmpfiles.exists())
        self.assertFalse(fixture.entrypoint.exists())
        self.assertFalse(fixture.release.exists())
        self.assertTrue(fixture.state.exists())
        self.assertTrue(fixture.cache.exists())
        self.assertTrue(fixture.corpus.exists())
        self.assertTrue(fixture.ollama_unit.exists())
        log = fixture.systemctl_log.read_text(encoding="utf-8")
        self.assertIn("stop gonken-agent.service", log)
        self.assertIn("disable gonken-agent.service", log)
        self.assertIn("daemon-reload", log)

        repeat = fixture.run()
        self.assertEqual(repeat.returncode, 0, repeat.stderr)
        self.assertIn("removed=none", repeat.stdout)

    def test_purge_requires_confirmation_and_never_touches_ollama(self) -> None:
        fixture = self.fixture()
        fixture.populate()
        rejected = fixture.run("--purge-data")
        self.assertEqual(rejected.returncode, 64)
        self.assertIn("code=UNINSTALL_PURGE_CONFIRMATION", rejected.stderr)
        self.assertTrue(fixture.release.exists())

        purged = fixture.run("--purge-data", "--confirm-purge", "purge-gonken-agent-data")
        self.assertEqual(purged.returncode, 0, purged.stderr)
        self.assertFalse(fixture.state.exists())
        self.assertFalse(fixture.cache.exists())
        self.assertFalse(fixture.corpus.exists())
        self.assertTrue(fixture.ollama_unit.exists())

    def test_modified_service_or_entrypoint_fails_before_mutation(self) -> None:
        fixture = self.fixture()
        fixture.populate()
        fixture.unit.write_text("[Unit]\nDescription=local override\n", encoding="utf-8")
        conflict = fixture.run()
        self.assertEqual(conflict.returncode, 75)
        self.assertIn("code=UNINSTALL_CONFLICT", conflict.stderr)
        self.assertTrue(fixture.release.exists())

        fixture = self.fixture()
        fixture.populate()
        fixture.entrypoint.unlink()
        fixture.entrypoint.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        conflict = fixture.run()
        self.assertEqual(conflict.returncode, 75)
        self.assertIn("code=UNINSTALL_CONFLICT", conflict.stderr)
        self.assertTrue(fixture.release.exists())


if __name__ == "__main__":
    unittest.main()
