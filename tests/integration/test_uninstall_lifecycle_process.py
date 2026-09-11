from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UNINSTALL = ROOT / "scripts/uninstall.sh"
UNIT = ROOT / "packaging/systemd/gonken-agent.service"
TMPFILES = ROOT / "packaging/tmpfiles/gonken-agent.conf"


class UninstallLifecycleProcessTests(unittest.TestCase):
    def test_wrapper_removes_project_owned_installation_and_keeps_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            system_root = root / "system"
            unit = system_root / "etc/systemd/system/gonken-agent.service"
            tmpfiles = system_root / "etc/tmpfiles.d/gonken-agent.conf"
            release = system_root / "usr/local/lib/gonken-agent"
            entrypoint = system_root / "usr/local/bin/gonken-agent"
            state = system_root / "var/lib/gonken-agent"
            cache = system_root / "var/cache/gonken-agent"
            for path in (unit.parent, tmpfiles.parent, release / "releases" / ("a" * 40), entrypoint.parent, state / "install", cache):
                path.mkdir(parents=True, exist_ok=True)
            unit.write_bytes(UNIT.read_bytes())
            tmpfiles.write_bytes(TMPFILES.read_bytes())
            entrypoint.symlink_to("../lib/gonken-agent/current/.venv/bin/gonken-agent")
            log = root / "systemctl.log"
            systemctl = root / "systemctl"
            systemctl.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$GONKEN_FAKE_SYSTEMCTL_LOG\"\nexit 0\n",
                encoding="utf-8",
            )
            systemctl.chmod(0o755)
            environment = os.environ.copy()
            environment["GONKEN_ENABLE_TEST_FAILURES"] = "1"
            environment["GONKEN_FAKE_SYSTEMCTL_LOG"] = str(log)
            result = subprocess.run(
                [str(UNINSTALL), "--system-root", str(system_root), "--systemctl", str(systemctl)],
                cwd=ROOT,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("UNINSTALL_COMPLETE", result.stdout)
            self.assertFalse(unit.exists())
            self.assertFalse(tmpfiles.exists())
            self.assertFalse(release.exists())
            self.assertFalse(entrypoint.exists())
            self.assertTrue(state.exists())
            self.assertTrue(cache.exists())

    def test_installed_maintenance_wrapper_uses_local_packaging_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            maintenance = root / "current/maintenance"
            (maintenance / "packaging/systemd").mkdir(parents=True)
            (maintenance / "packaging/tmpfiles").mkdir(parents=True)
            shutil.copy2(ROOT / "scripts/uninstall.sh", maintenance / "uninstall.sh")
            shutil.copy2(ROOT / "scripts/uninstall_manager.py", maintenance / "uninstall_manager.py")
            shutil.copy2(ROOT / "scripts/service_manager.py", maintenance / "service_manager.py")
            shutil.copy2(UNIT, maintenance / "packaging/systemd/gonken-agent.service")
            shutil.copy2(TMPFILES, maintenance / "packaging/tmpfiles/gonken-agent.conf")
            (maintenance / "uninstall.sh").chmod(0o755)
            system_root = root / "system"
            unit = system_root / "etc/systemd/system/gonken-agent.service"
            tmpfiles = system_root / "etc/tmpfiles.d/gonken-agent.conf"
            release = system_root / "usr/local/lib/gonken-agent"
            entrypoint = system_root / "usr/local/bin/gonken-agent"
            state = system_root / "var/lib/gonken-agent"
            for path in (unit.parent, tmpfiles.parent, release / "releases" / ("a" * 40), entrypoint.parent, state):
                path.mkdir(parents=True, exist_ok=True)
            unit.write_bytes(UNIT.read_bytes())
            tmpfiles.write_bytes(TMPFILES.read_bytes())
            entrypoint.symlink_to("../lib/gonken-agent/current/.venv/bin/gonken-agent")
            log = root / "systemctl.log"
            systemctl = root / "systemctl"
            systemctl.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$GONKEN_FAKE_SYSTEMCTL_LOG\"\nexit 0\n",
                encoding="utf-8",
            )
            systemctl.chmod(0o755)
            environment = os.environ.copy()
            environment["GONKEN_ENABLE_TEST_FAILURES"] = "1"
            environment["GONKEN_FAKE_SYSTEMCTL_LOG"] = str(log)
            result = subprocess.run(
                [str(maintenance / "uninstall.sh"), "--system-root", str(system_root), "--systemctl", str(systemctl)],
                cwd=ROOT,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("UNINSTALL_COMPLETE", result.stdout)
            self.assertFalse(unit.exists())
            self.assertFalse(tmpfiles.exists())


if __name__ == "__main__":
    unittest.main()
