from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('b10_plan', ROOT/'scripts/installer_plan.py')
plan=importlib.util.module_from_spec(spec);spec.loader.exec_module(plan)

class CandidatePlanTests(unittest.TestCase):
    def steps(self):
        return ['immutable_release','activate_release','environment_account','environment_profile',
            'target_gpio_identity','environment_service','environment_commissioning','environment_readiness',
            'environment_policy','ollama_model_roster','speech_smoke','application_service','appliance_readiness']
    def test_full_target_delays_switch_and_hardware_start_until_candidate_ready(self):
        initial=self.steps();final=plan.candidate_order(initial,platform='target')
        self.assertEqual(set(final),set(initial));self.assertEqual(initial,self.steps())
        self.assertLess(final.index('speech_smoke'),final.index('activate_release'))
        self.assertLess(final.index('activate_release'),final.index('environment_commissioning'))
        self.assertLess(final.index('environment_policy'),final.index('application_service'))
        self.assertEqual(plan.candidate_order(final,platform='target'),final)
    def test_target_ollama_only_uses_roster_anchor(self):
        initial=[s for s in self.steps() if s not in ('speech_smoke','application_service','appliance_readiness')]
        final=plan.candidate_order(initial,platform='target')
        self.assertLess(final.index('ollama_model_roster'),final.index('activate_release'))
    def test_disabled_environment_does_not_invent_feature_steps(self):
        initial=[s for s in self.steps() if not s.startswith('environment_')]
        final=plan.candidate_order(initial,platform='target')
        self.assertFalse(any(s.startswith('environment_') for s in final))
    def test_host_and_release_only_keep_explicit_narrow_boundary(self):
        for platform,flag in [('development',False),('target',True)]:
            self.assertEqual(plan.candidate_order(self.steps(),platform=platform,release_only=flag),self.steps())
    def test_invalid_or_incomplete_plan_rejected(self):
        for steps in [[],['a','a'],['bad;command'],['immutable_release','activate_release'],
                ['immutable_release','activate_release','ollama_model_roster','environment_policy']]:
            with self.assertRaises(ValueError):plan.candidate_order(steps,platform='target')
    def test_installer_uses_qualified_candidate_helpers_and_finalized_plan(self):
        text=(ROOT/'scripts/install.sh').read_text()
        self.assertIn('CANDIDATE_RELEASE="$RELEASE_ROOT/releases/${GONKEN_SOURCE_RECORD[resolved_commit]}"',text)
        self.assertIn('"$SCRIPT_DIR/installer_plan.py"',text)
        self.assertLess(text.index('mapfile -t GONKEN_STEP_ORDER'),text.index('if gonken_run_registered_steps; then'))
        for name in ['ollama_manager.py','speech_manager.py','environment_readiness.py']:
            self.assertIn('$CANDIDATE_RELEASE/maintenance/'+name,text)
        self.assertNotIn('$RELEASE_ROOT/current/maintenance/',text)
        self.assertNotIn('\"$BIN_ROOT/gonken-agent\" config show',text)

if __name__=='__main__':unittest.main()
