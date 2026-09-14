from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANAGER = ROOT / "scripts/environment_service_manager.py"
UNIT = ROOT / "packaging/systemd/gonken-environment.service"
TMPFILES = ROOT / "packaging/tmpfiles/gonken-environment.conf"
AGENT_UNIT = ROOT / "packaging/systemd/gonken-agent.service"


class EnvironmentServiceFixture:
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


class EnvironmentServiceManagerTests(unittest.TestCase):
    def fixture(self) -> EnvironmentServiceFixture:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return EnvironmentServiceFixture(Path(temporary.name))

    def test_environment_unit_is_local_only_least_privilege_and_independent(self) -> None:
        text = UNIT.read_text(encoding="utf-8")
        for required in (
            "Type=exec",
            "User=gonken-env",
            "Group=gonken-env",
            "ExecStart=/usr/local/lib/gonken-agent/current/.venv/bin/gonken-agent env serve",
            "RestrictAddressFamilies=AF_UNIX",
            "NoNewPrivileges=true",
            "CapabilityBoundingSet=",
            "PrivateDevices=false",
            "ReadWritePaths=/var/lib/gonken-environment /var/cache/gonken-environment /run/gonken-environment",
        ):
            self.assertIn(required, text)
        lowered = text.lower()
        for forbidden in ("sudo", "sudoers", "polkit", "poweroff", "reboot", "af_inet"):
            self.assertNotIn(forbidden, lowered)
        self.assertNotIn("Requires=gonken-agent.service", text)
        self.assertNotIn("Requires=ollama.service", text)

    def test_voice_service_has_soft_environment_dependency_only(self) -> None:
        text = AGENT_UNIT.read_text(encoding="utf-8")
        self.assertIn("Wants=ollama.service gonken-environment.service", text)
        self.assertIn("After=network-online.target ollama.service gonken-environment.service", text)
        self.assertNotIn("Requires=gonken-environment.service", text)

    def test_tmpfiles_contract_uses_separate_state_and_socket_client_group(self) -> None:
        lines = set(TMPFILES.read_text(encoding="utf-8").splitlines())
        self.assertEqual(
            lines,
            {
                "d /var/lib/gonken-environment 0750 gonken-env gonken-env -",
                "d /var/cache/gonken-environment 0750 gonken-env gonken-env -",
                "d /run/gonken-environment 2770 gonken-env gonken-envctl -",
            },
        )

    def test_install_status_remove_are_structural_and_do_not_enable_or_start(self) -> None:
        fixture = self.fixture()
        installed = fixture.run("install")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertIn("ENV_SERVICE_INSTALLED", installed.stdout)
        unit = fixture.system_root / "etc/systemd/system/gonken-environment.service"
        tmpfiles = fixture.system_root / "etc/tmpfiles.d/gonken-environment.conf"
        self.assertEqual(unit.read_bytes(), UNIT.read_bytes())
        self.assertEqual(tmpfiles.read_bytes(), TMPFILES.read_bytes())
        self.assertEqual(stat.S_IMODE(unit.stat().st_mode), 0o644)

        repeat = fixture.run("install")
        self.assertEqual(repeat.returncode, 0, repeat.stderr)
        status_result = fixture.run("installed-status")
        self.assertEqual(status_result.returncode, 0, status_result.stderr)
        self.assertIn("autostart=disabled", status_result.stdout)

        log = fixture.systemctl_log.read_text(encoding="utf-8")
        self.assertIn("daemon-reload", log)
        self.assertNotIn("enable gonken-environment.service", log)
        self.assertNotIn("start gonken-environment.service", log)

        removed = fixture.run("remove")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse(unit.exists())
        self.assertFalse(tmpfiles.exists())
        remove_log = fixture.systemctl_log.read_text(encoding="utf-8")
        self.assertIn("stop gonken-environment.service", remove_log)
        self.assertIn("disable gonken-environment.service", remove_log)

    def test_conflicting_environment_unit_fails_closed(self) -> None:
        fixture = self.fixture()
        unit = fixture.system_root / "etc/systemd/system/gonken-environment.service"
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text("[Unit]\nDescription=local override\n", encoding="utf-8")
        conflict = fixture.run("install")
        self.assertEqual(conflict.returncode, 75)
        self.assertIn("code=ENV_SERVICE_CONFLICT", conflict.stderr)


if __name__ == "__main__":
    unittest.main()
