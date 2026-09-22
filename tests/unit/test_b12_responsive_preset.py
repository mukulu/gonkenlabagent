from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import threading
import tomllib
import unittest
from unittest.mock import Mock, patch

from gonken_agent.config import load_config, ConfigError
from gonken_agent.deployment import apply_preset, LLM_PRESET, main as deployment_main
from gonken_agent.environment.policy import EnvironmentPolicy
from gonken_agent.llm.models import DEFAULT_MODEL
from gonken_agent.voice_runtime import VoiceAppliance

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import environment_policy_manager as policy_manager
import environment_profile_manager as profile_manager
from tests.unit import test_b11_alternate_models as alternate_tests
manager = alternate_tests.manager

class ResponsivePresetTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'config.toml'
        self.path.write_text(profile_manager.profile_text('full-real'))
        self.path.chmod(0o640)

    def test_catalog_default_and_policy_are_aligned(self):
        cfg = load_config(site_path=None, environ={}).config
        self.assertEqual(cfg.llm.model, DEFAULT_MODEL)
        self.assertEqual(cfg.llm.max_output_tokens, 96)
        self.assertEqual(EnvironmentPolicy.default().stop_c, 26.0)

    def test_preset_preserves_hardware_and_backs_up_old_bytes(self):
        before = self.path.read_bytes()
        self.assertTrue(apply_preset(self.path))
        data = tomllib.loads(self.path.read_text())
        self.assertEqual(data['llm'], LLM_PRESET)
        self.assertEqual(data['extensions']['environment']['relay_bcm'], 23)
        backup = next(self.path.parent.glob('config.pre-room-preset.*.bak'))
        self.assertEqual(backup.read_bytes(), before)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
        self.assertFalse(apply_preset(self.path)); self.assertFalse(apply_preset(self.path, check=True))

    def test_check_is_nonmutating(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'NOT_APPLIED'): apply_preset(self.path, check=True)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(list(self.path.parent.iterdir())), 1)

    def test_cli_check_maps_pending_preset_to_normal_unsatisfied_status(self):
        before = self.path.read_bytes()
        self.assertEqual(deployment_main(["llm", "--config", str(self.path), "--check"]), 1)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(apply_preset(self.path))
        self.assertEqual(deployment_main(["llm", "--config", str(self.path), "--check"]), 0)

    def test_module_cli_pending_exit_is_install_engine_unsatisfied_status(self):
        before = self.path.read_bytes()
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-m", "gonken_agent.deployment", "llm", "--config", str(self.path), "--check"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("code=ROOM_PRESET_PENDING", result.stdout)
        self.assertEqual(self.path.read_bytes(), before)

    def test_cli_check_keeps_malformed_or_unsafe_configuration_fatal(self):
        self.path.write_text('[llm]\nmodel="one"\nmodel="two"\n')
        self.assertEqual(deployment_main(["llm", "--config", str(self.path), "--check"]), 65)
        link = self.path.with_name("unsafe-link")
        link.symlink_to(self.path)
        self.assertEqual(deployment_main(["llm", "--config", str(link), "--check"]), 65)

    def test_symlink_unknown_and_malformed_site_rejected(self):
        link = self.path.with_name('link'); link.symlink_to(self.path)
        with self.assertRaises(ValueError): apply_preset(link)
        for text in ('[llm]\nmodel="x"\nmodel="y"\n', '[invalid]\nunknown=true\n'):
            self.path.write_text(text)
            with self.assertRaises((ValueError, ConfigError)): apply_preset(self.path)
            self.assertEqual(self.path.read_text(), text)

    def test_profile_manager_rerun_keeps_other_settings(self):
        apply_preset(self.path)
        self.assertTrue(profile_manager.exact_profile(self.path, 'full-real'))
        self.assertEqual(profile_manager.ensure_profile(self.path, name='full-real', group='unused'), 'ALREADY_CONFIGURED')
        profile_manager.ensure_profile(self.path, name='real-sensor-simulated-actuator', group='unused')
        self.assertEqual(tomllib.loads(self.path.read_text())['llm'], LLM_PRESET)
        self.assertEqual(profile_manager.read_environment(self.path)['relay_backend'], 'simulated')

    def test_threshold_migration_keeps_dwell_and_uses_generation(self):
        before = EnvironmentPolicy.default().to_mapping(); before.update(generation=11, stop_c=25.0, minimum_on_seconds=80)
        after = dict(before, generation=12, stop_c=26.0, mode="automatic")
        with patch.object(policy_manager, 'read_agent', side_effect=[{'policy':before},{}, {'policy':after}]) as call:
            self.assertEqual(policy_manager.converge(Path('/agent'), 'automatic', start_c=28, stop_c=26)['stop_c'],26)
            request=call.call_args_list[1].args[1]
            self.assertIn('--expected-generation',request); self.assertIn('11',request)
            self.assertNotIn('--minimum-on-seconds',request)
        self.assertEqual(after['minimum_on_seconds'],80)

    def test_explicit_default_migration_does_not_require_failed_old_alternate(self):
        fixture=alternate_tests.AlternateModelTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        manager._write_selection(fixture.root, fixture.failed_tag, None)
        with patch.object(manager.om, '_api', side_effect=fixture.api), patch.object(manager.om, 'smoke_model', return_value={'total_ns':1}):
            result=manager.provision(fixture.root,fixture.roster,'http://127.0.0.1:11434',2048,'preseeded-offline',select_default=True)
        self.assertEqual(result['active_model'], DEFAULT_MODEL)
        self.assertEqual(result['roster_capabilities_status'],'DEGRADED')

    def test_complete_inline_command_never_requests_extra_capture(self):
        a=VoiceAppliance.__new__(VoiceAppliance)
        a.brain=Mock(spec=["is_fast_deterministic"]);a.brain.is_fast_deterministic.return_value=True;a.capture_text=Mock(side_effect=AssertionError('extra_capture'))
        self.assertEqual(a._question_after_wake('turn the fan on', utterance_complete=True),'turn the fan on')
        a.capture_text.assert_not_called()

    def test_partial_wake_window_keeps_followup_and_removes_overlap(self):
        a=VoiceAppliance.__new__(VoiceAppliance)
        a.brain=Mock(spec=["is_fast_deterministic"]);a.brain.is_fast_deterministic.return_value=False;a.capture_text=Mock(return_value='What is Python?')
        self.assertEqual(a._question_after_wake('what is'),'What is Python?')
        a.capture_text.assert_called_once_with(8)
        a.capture_text.return_value='capital of France?'
        self.assertEqual(a._question_after_wake('What is the capital'),'What is the capital of France?')

if __name__=='__main__': unittest.main()
