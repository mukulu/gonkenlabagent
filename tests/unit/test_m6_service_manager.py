from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANAGER = ROOT / "scripts/service_manager.py"
UNIT = ROOT / "packaging/systemd/gonken-agent.service"
TMPFILES = ROOT / "packaging/tmpfiles/gonken-agent.conf"
PREVIOUS_UNIT = ROOT / "tests/fixtures/systemd/gonken-agent-pre-fix3.service"
PRE_FIX7_UNIT = ROOT / "tests/fixtures/systemd/gonken-agent-pre-fix7.service"


class ServiceManagerFixture:
    def __init__(self, root: Path):
        self.root = root
        self.system_root = root / "system"
        self.system_root.mkdir()
        self.systemctl_log = root / "systemctl.log"
        self.tmpfiles_log = root / "tmpfiles.log"
        self.systemctl = self._fake("systemctl", self.systemctl_log)
        self.tmpfiles = self._fake("systemd-tmpfiles", self.tmpfiles_log)

    def _fake(self, name: str, log: Path) -> Path:
        path = self.root / name
        path.write_text(
            "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$GONKEN_FAKE_TOOL_LOG\"\nexit 0\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def command(self, action: str) -> list[str]:
        return [
            sys.executable,
            str(MANAGER),
            action,
            "--system-root",
            str(self.system_root),
            "--unit-template",
            str(UNIT),
            "--tmpfiles-template",
            str(TMPFILES),
            "--systemctl",
            str(self.systemctl),
            "--systemd-tmpfiles",
            str(self.tmpfiles),
            "--service-uid",
            "999",
        ]

    def run(self, action: str, *, tool_log: Path | None = None) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["GONKEN_ENABLE_TEST_FAILURES"] = "1"
        environment["GONKEN_FAKE_TOOL_LOG"] = str(tool_log or self.systemctl_log)
        return subprocess.run(
            self.command(action),
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )


class ServiceManagerTests(unittest.TestCase):
    def fixture(self) -> ServiceManagerFixture:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return ServiceManagerFixture(Path(temporary.name))

    def test_template_contract_rejects_power_and_privilege_grants(self) -> None:
        text = UNIT.read_text(encoding="utf-8")
        for required in (
            "Type=exec",
            "User=gonken-agent",
            "ExecStartPre=+/usr/local/lib/gonken-agent/current/maintenance/reconcile-release.sh",
            "ExecStart=/usr/local/lib/gonken-agent/current/.venv/bin/gonken-agent service",
            "EnvironmentFile=-/etc/gonken-agent/runtime-environment",
            "ReadWritePaths=/var/lib/gonken-agent/install /var/lib/gonken-agent/runtime /var/cache/gonken-agent /run/gonken-agent",
            "ReadOnlyPaths=-/srv/gonken-agent/corpus",
            "NoNewPrivileges=true",
            "CapabilityBoundingSet=",
            "PrivateDevices=false",
        ):
            self.assertIn(required, text)
        lowered = text.lower()
        for forbidden in ("sudo", "sudoers", "polkit", "poweroff", "reboot", "privateDevices=true".lower()):
            self.assertNotIn(forbidden, lowered)

    def test_optional_corpus_does_not_make_namespace_start_fatal(self) -> None:
        text = UNIT.read_text(encoding="utf-8")
        self.assertIn("ReadOnlyPaths=-/srv/gonken-agent/corpus", text)
        self.assertNotIn("ReadOnlyPaths=/srv/gonken-agent/corpus\n", text)
        self.assertIn("ExecStartPre=+", text)

    def test_install_status_remove_are_exact_and_reversible(self) -> None:
        fixture = self.fixture()
        installed = fixture.run("install")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertIn("SERVICE_INSTALLED", installed.stdout)
        unit = fixture.system_root / "etc/systemd/system/gonken-agent.service"
        tmpfiles = fixture.system_root / "etc/tmpfiles.d/gonken-agent.conf"
        self.assertEqual(unit.read_bytes(), UNIT.read_bytes())
        self.assertEqual(tmpfiles.read_bytes(), TMPFILES.read_bytes())
        runtime_env = fixture.system_root / "etc/gonken-agent/runtime-environment"
        self.assertEqual(
            runtime_env.read_text(encoding="utf-8"),
            "XDG_RUNTIME_DIR=/run/user/999\nDBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/999/bus\n",
        )
        self.assertEqual(stat.S_IMODE(runtime_env.stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE(unit.stat().st_mode), 0o644)

        repeat = fixture.run("install")
        self.assertEqual(repeat.returncode, 0, repeat.stderr)
        status_result = fixture.run("status")
        self.assertEqual(status_result.returncode, 0, status_result.stderr)
        self.assertIn("SERVICE_HEALTHY", status_result.stdout)

        removed = fixture.run("remove")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse(unit.exists())
        self.assertFalse(tmpfiles.exists())
        log = fixture.systemctl_log.read_text(encoding="utf-8")
        self.assertIn("daemon-reload", log)
        self.assertIn("enable gonken-agent.service", log)
        self.assertIn("reset-failed gonken-agent.service", log)
        self.assertIn("start gonken-agent.service", log)
        self.assertIn("stop gonken-agent.service", log)
        self.assertIn("disable gonken-agent.service", log)



    def test_installed_status_is_not_race_sensitive_to_runtime_activity(self) -> None:
        fixture = self.fixture()
        installed = fixture.run("install")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        fixture.systemctl.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >>\"$GONKEN_FAKE_TOOL_LOG\"\n"
            "case \"$1\" in is-active) exit 1;; *) exit 0;; esac\n",
            encoding="utf-8",
        )
        fixture.systemctl.chmod(0o755)
        structural = fixture.run("installed-status")
        self.assertEqual(structural.returncode, 0, structural.stderr)
        active = fixture.run("status")
        self.assertNotEqual(active.returncode, 0)
        self.assertIn("SERVICE_COMMAND", active.stderr)

    def test_system_unit_never_uses_manager_uid_specifier_for_audio(self) -> None:
        text = UNIT.read_text(encoding="utf-8")
        self.assertNotIn("%U", text)
        self.assertNotIn("/run/user/0", text)
        self.assertIn("EnvironmentFile=-/etc/gonken-agent/runtime-environment", text)

    def test_known_previous_managed_unit_is_upgraded_in_place(self) -> None:
        fixture = self.fixture()
        unit = fixture.system_root / "etc/systemd/system/gonken-agent.service"
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_bytes(PREVIOUS_UNIT.read_bytes())
        unit.chmod(0o644)
        installed = fixture.run("install")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertIn("SERVICE_MANAGED_UPGRADE", installed.stdout)
        self.assertEqual(unit.read_bytes(), UNIT.read_bytes())

    def test_fix6_managed_unit_is_upgraded_to_generated_runtime_environment(self) -> None:
        fixture = self.fixture()
        unit = fixture.system_root / "etc/systemd/system/gonken-agent.service"
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_bytes(PRE_FIX7_UNIT.read_bytes())
        unit.chmod(0o644)
        installed = fixture.run("install")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertIn("SERVICE_MANAGED_UPGRADE", installed.stdout)
        self.assertNotIn(b"%U", unit.read_bytes())
        runtime_env = fixture.system_root / "etc/gonken-agent/runtime-environment"
        self.assertIn(b"/run/user/999", runtime_env.read_bytes())

    def test_conflicting_installed_unit_fails_closed(self) -> None:
        fixture = self.fixture()
        first = fixture.run("install")
        self.assertEqual(first.returncode, 0, first.stderr)
        unit = fixture.system_root / "etc/systemd/system/gonken-agent.service"
        unit.write_text("[Unit]\nDescription=local override\n", encoding="utf-8")
        conflict = fixture.run("install")
        self.assertEqual(conflict.returncode, 75)
        self.assertIn("code=SERVICE_CONFLICT", conflict.stderr)
        remove = fixture.run("remove")
        self.assertEqual(remove.returncode, 74)
        self.assertIn("code=SERVICE_INSTALLED", remove.stderr)


if __name__ == "__main__":
    unittest.main()
