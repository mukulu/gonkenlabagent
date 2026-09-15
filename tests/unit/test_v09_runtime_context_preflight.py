from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("runtime_context_preflight", ROOT / "scripts/runtime_context_preflight.py")
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class RuntimeContextPreflightTests(unittest.TestCase):
    def account(self):
        return SimpleNamespace(pw_uid=os.getuid(), pw_dir="/var/lib/gonken-agent")

    def fixture(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        runtime_env = root / "runtime-environment"
        uid = os.getuid()
        runtime_env.write_text(f"XDG_RUNTIME_DIR=/run/user/{uid}\nDBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus\n", encoding="utf-8")
        runtime_root = root / "run-user"; (runtime_root / str(uid)).mkdir(parents=True)
        linger = root / "linger"; linger.mkdir(); (linger / "gonken-agent").write_text("", encoding="utf-8")
        return runtime_env, runtime_root, linger

    def test_structural_context_can_be_ready_without_claiming_physical_audio(self) -> None:
        runtime_env, runtime_root, linger = self.fixture()
        runner=lambda _args: SimpleNamespace(returncode=0)
        with mock.patch.object(module.pwd, "getpwnam", return_value=self.account()):
            payload = module.inspect(audio_user="gonken-agent", require_pipewire=False, runtime_env=runtime_env, runtime_root=runtime_root, linger_dir=linger, runner=runner)
        self.assertTrue(payload["ready"])
        self.assertFalse(payload["physical_audio_claimed"])

    def test_pipewire_requirement_checks_user_manager_services_and_pulse(self) -> None:
        runtime_env, runtime_root, linger = self.fixture()
        runner=lambda _args: SimpleNamespace(returncode=0)
        user_runner=lambda *_args: SimpleNamespace(returncode=0)
        with mock.patch.object(module.pwd, "getpwnam", return_value=self.account()):
            payload = module.inspect(audio_user="gonken-agent", require_pipewire=True, runtime_env=runtime_env, runtime_root=runtime_root, linger_dir=linger, runner=runner, user_runner=user_runner)
        self.assertTrue(payload["ready"])
        self.assertTrue(payload["pipewire_active"])
        self.assertFalse(payload["physical_audio_claimed"])

    def test_missing_runtime_environment_fails_require_ready(self) -> None:
        with mock.patch.object(module, "inspect", return_value={"ready": False, "runtime_environment_exact": False, "runtime_dir_ready": False, "linger_enabled": False, "user_manager_active": False, "pipewire_required": False, "physical_audio_claimed": False}):
            rc = module.main(["status", "--require-ready"])
        self.assertEqual(rc, 75)

    def test_installer_gates_appliance_readiness_on_runtime_context(self) -> None:
        install = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
        release = (ROOT / "scripts/release_manager.py").read_text(encoding="utf-8")
        self.assertIn('"runtime_context" "1"', install)
        self.assertIn('"appliance_readiness" "4"', install)
        self.assertIn('"gonken_runtime_context_postcondition" "gonken_appliance_action"', install)
        self.assertIn('runtime_context_preflight.py', release)

    def test_service_unit_contract_preserves_environment_independence(self) -> None:
        app = (ROOT / "packaging/systemd/gonken-agent.service").read_text(encoding="utf-8")
        env = (ROOT / "packaging/systemd/gonken-environment.service").read_text(encoding="utf-8")
        self.assertIn("Wants=ollama.service gonken-environment.service", app)
        self.assertNotIn("Requires=gonken-environment.service", app)
        self.assertIn("EnvironmentFile=-/etc/gonken-agent/runtime-environment", app)
        self.assertIn("User=gonken-env", env)
        self.assertNotIn("PartOf=gonken-agent.service", env)


if __name__ == "__main__":
    unittest.main()
