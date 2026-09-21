"""Process boundary: shell is an adapter, canonical CLI owns destination policy."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class SupportCollectionProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.maintenance = self.root/'current/maintenance'; self.maintenance.mkdir(parents=True)
        self.bin = self.root/'current/.venv/bin'; self.bin.mkdir(parents=True)
        self.wrapper = self.maintenance/'collect-support.sh'
        shutil.copy2(ROOT/'scripts/collect-support.sh', self.wrapper); self.wrapper.chmod(0o755)
        self.calls = self.root/'calls.json'
        self.env = dict(os.environ, GONKEN_FAKE_SUPPORT_LOG=str(self.calls))
        self.fake = self.bin/'gonken-agent'
        self.fake.write_text('#!'+sys.executable+'\n'+'''
import json,sys,os
from pathlib import Path
args=sys.argv[1:]
Path(os.environ['GONKEN_FAKE_SUPPORT_LOG']).write_text(json.dumps(args))
if '--output' in args:
 out=Path(args[args.index('--output')+1])
elif '--output-dir' in args:
 out=Path(args[args.index('--output-dir')+1])/'gonken-support-fixture.tar.bz2'
else:
 raise SystemExit(64)
out.write_text('{}')
print(out)
'''); self.fake.chmod(0o755)

    def run_wrapper(self, *args):
        return subprocess.run([str(self.wrapper), *args, '--site', str(self.root/'absent-site'),
                               '--telemetry', str(self.root/'absent-telemetry'),
                               '--startup-snapshot', str(self.root/'absent-snapshot')],
                              capture_output=True, text=True, env=self.env, timeout=10)

    def test_installed_wrapper_uses_release_local_entrypoint(self):
        output=self.root/'support.tar.bz2'
        result=self.run_wrapper('--output', str(output))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),str(output))
        args=json.loads(self.calls.read_text())
        self.assertEqual(args[:3], ['support','--output',str(output)])
        self.assertIn('--no-site',args)
        for option in ('--telemetry','--startup-snapshot','--target-manifest'):
            self.assertNotIn(option,args)

    def test_output_dir_forwarded_once_and_single_bundle_created(self):
        directory=self.root/'out'; directory.mkdir()
        result=self.run_wrapper('--output-dir',str(directory))
        self.assertEqual(result.returncode,0,result.stderr)
        args=json.loads(self.calls.read_text())
        self.assertIn('--output-dir',args); self.assertNotIn('--output',args)
        self.assertEqual(list(directory.iterdir()), [Path(result.stdout.strip())])

    def test_target_manifest_auto_embedded_and_temporary_file_removed(self):
        probe=self.maintenance/'target_probe.py'
        probe.write_text('#!'+sys.executable+'\nimport json,sys\nfrom pathlib import Path\n'
                         'Path(sys.argv[sys.argv.index("--output")+1]).write_text(json.dumps({"format":"gonken-target-hardware-manifest-v1"}))\n')
        probe.chmod(0o755)
        result=self.run_wrapper('--output',str(self.root/'support.tar.bz2'))
        self.assertEqual(result.returncode,0,result.stderr)
        args=json.loads(self.calls.read_text()); self.assertIn('--target-manifest',args)
        self.assertFalse(Path(args[args.index('--target-manifest')+1]).exists())

    def test_child_failure_is_preserved_no_destination_created(self):
        self.fake.write_text('#!/bin/sh\nexit 99\n')
        missing=self.root/'missing'
        result=self.run_wrapper('--output-dir',str(missing))
        self.assertEqual(result.returncode,99)
        self.assertFalse(missing.exists())

    def test_help_works_without_installed_command(self):
        self.fake.unlink()
        result=subprocess.run([str(self.wrapper),'--help'],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('.tar.bz2',result.stdout)

    def test_missing_flag_value_has_bounded_clear_error(self):
        result=subprocess.run([str(self.wrapper),'--output'],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,64)
        self.assertIn('requires a value',result.stderr)

if __name__=='__main__': unittest.main()
