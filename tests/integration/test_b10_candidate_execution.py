"""Execute actual registered target step plans with non-mutating test actions.

This checks production shell registration + Python ordering + engine dispatch,
not physical provisioning. The only write is a temporary simulated current file.
"""
from __future__ import annotations
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

class RegisteredPlanTests(unittest.TestCase):
    def run_plan(self, fault='', profile='full-real', ollama_only=0):
        text=(ROOT/'scripts/install.sh').read_text()
        definitions=text[text.index('gonken_source_marker_content()'):text.index('gonken_engine_initialize "$STATE_DIR"')]
        registration=text[text.index('gonken_register_step \\\n  "source_record_validation"'):text.index('if gonken_run_registered_steps; then')]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);current=root/'current';current.write_text('predecessor')
            script='''set -Eeuo pipefail
source "$ROOT/scripts/lib/common.sh"
source "$ROOT/scripts/lib/install_engine.sh"
SCRIPT_DIR="$ROOT/scripts"
STATE_DIR="$WORK/state"
RELEASE_ROOT="$WORK/releases"
CANDIDATE_RELEASE="$RELEASE_ROOT/releases/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
INSTALL_STATE_ROOT="$WORK/install"
SERVICE_USER=test
ENGINE_ONLY=0 RELEASE_ONLY=0 OLLAMA_ONLY="$ONLY_OLLAMA" SPEECH_ONLY=0
SPEECH_STT_MODEL=test SPEECH_TTS_VOICE=test
TARGET_PREFLIGHT="$ROOT/scripts/target_preflight.py"
declare -A GONKEN_SOURCE_RECORD=([resolved_commit]=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa [platform_mode]=target [environment_profile]="$PROFILE" [environment_mode]=automatic [bluetooth_audio]=disabled)
'''+definitions+registration+'''
gonken_run_step() {
  printf 'STEP %s\\n' "$1"
  [[ "$1" != "$FAULT" ]] || return 75
  if [[ "$1" == activate_release ]]; then printf candidate > "$WORK/current"; fi
}
gonken_log_event() { :; }
gonken_release_engine_lock() { :; }
gonken_run_registered_steps
'''
            env={**os.environ,'ROOT':str(ROOT),'WORK':tmp,'PROFILE':profile,'FAULT':fault,'ONLY_OLLAMA':str(ollama_only)}
            result=subprocess.run(['bash','-c',script],env=env,capture_output=True,text=True,timeout=10)
            return result,current.read_text()
    def test_model_failure_never_switches_current(self):
        result,current=self.run_plan('ollama_model_roster')
        self.assertEqual(result.returncode,75,result.stderr);self.assertEqual(current,'predecessor')
        self.assertNotIn('STEP activate_release',result.stdout)
        self.assertNotIn('STEP environment_commissioning',result.stdout)
        self.assertIn('STEP environment_current_reconciliation',result.stdout)
        self.assertLess(result.stdout.index('STEP environment_current_reconciliation'),result.stdout.index('STEP ollama_model_roster'))
    def test_speech_failure_never_switches_current(self):
        result,current=self.run_plan('speech_smoke')
        self.assertEqual(result.returncode,75,result.stderr);self.assertEqual(current,'predecessor')
    def test_successful_prerequisites_precede_activation_and_real_environment(self):
        result,current=self.run_plan()
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(current,'candidate')
        steps=[line[5:] for line in result.stdout.splitlines() if line.startswith('STEP ')]
        for before,after in [('environment_profile','target_gpio_identity'),('speech_smoke','activate_release'),
                ('activate_release','environment_commissioning'),('environment_readiness','environment_policy'),
                ('environment_policy','application_service')]:
            self.assertLess(steps.index(before),steps.index(after))
    def test_no_environment_profile_does_not_start_environment(self):
        result,current=self.run_plan(profile='none')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('STEP environment_commissioning',result.stdout)
        self.assertNotIn('STEP environment_current_reconciliation',result.stdout)
    def test_ollama_only_plan_has_a_valid_late_activation_boundary(self):
        result,current=self.run_plan(ollama_only=1)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(current,'candidate')
        self.assertNotIn('STEP speech_smoke',result.stdout)
        self.assertLess(result.stdout.index('STEP ollama_model_roster'),result.stdout.index('STEP activate_release'))

if __name__=='__main__':unittest.main()
