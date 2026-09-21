from __future__ import annotations
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

class RoomInstallerTests(unittest.TestCase):
    def run_wrapper(self,args):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            shutil.copy2(ROOT/'install-room-appliance.sh',root/'install-room-appliance.sh')
            boot=root/'bootstrap.sh'
            boot.write_text('#!/usr/bin/env python3\nimport sys,json\nprint(json.dumps(sys.argv[1:]))\n');boot.chmod(0o755)
            return subprocess.run([str(root/'install-room-appliance.sh'),*args],capture_output=True,text=True,timeout=5)
    def test_default_exact_local_full_real_automatic(self):
        result=self.run_wrapper([])
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[-1]),['--local-checkpoint','--environment-profile','full-real','--environment-mode','automatic'])
    def test_safe_options_forward_without_shell_reinterpretation(self):
        result=self.run_wrapper(['--environment-mode','preserve','--bluetooth-device','speaker; echo nope','--sensor-address','0x45','--preflight-only'])
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('speaker; echo nope',json.loads(result.stdout.splitlines()[-1]))
    def test_no_simulation_or_remote_source_override(self):
        for args in [['--environment-profile','full-simulation'],['--development-host'],['--ref','main'],['--environment-mode']]:
            self.assertEqual(self.run_wrapper(args).returncode,64)
    def test_help_does_not_delegate_or_modify(self):
        result=self.run_wrapper(['--help'])
        self.assertEqual(result.returncode,0)
        self.assertIn('No simulated fallback',result.stdout)
        self.assertNotIn('[CONFIG]',result.stdout)
    def test_registration_profile_precedes_resource_validation(self):
        text=(ROOT/'scripts/install.sh').read_text()
        self.assertLess(text.index('"environment_profile" "1"'),text.index('"target_gpio_identity" "2"'))
        self.assertLess(text.index('"environment_readiness" "2"'),text.index('"environment_policy" "1"'))
        section=text[text.index('gonken_environment_commissioning_postcondition()'):text.index('gonken_environment_commissioning_action()')]
        self.assertIn('--binding-only',section);self.assertIn('--check-config',section);self.assertIn('--expect-commit',section)
    def test_bootstrap_rejects_invalid_or_unprofiled_mode_before_privilege(self):
        for args in [['--environment-mode','bogus'],['--environment-mode','automatic']]:
            result=subprocess.run(['bash',str(ROOT/'bootstrap.sh'),*args],cwd=ROOT,capture_output=True,text=True,timeout=8)
            self.assertEqual(result.returncode,64,result.stderr)
            self.assertIn('PREFLIGHT_ENVIRONMENT_MODE',result.stderr)

if __name__=='__main__':unittest.main()
