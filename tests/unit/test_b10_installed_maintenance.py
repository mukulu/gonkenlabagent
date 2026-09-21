"""Regression for B9 target failure: no checkout or application on system Python."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
# This staging inventory is also checked against the release builder below.
SCRIPTS = ("ollama_manager.py", "model_roster_manager.py", "ollama_qualification_matrix.py")
SIDECARS = {"ollama_errors.py": "src/gonken_agent/llm/errors.py",
            "model_qualification.py": "src/gonken_agent/llm/qualification.py",
            "model_catalog.py": "src/gonken_agent/llm/models.py"}

class InstalledMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.maintenance = self.root / "release" / "maintenance"
        self.maintenance.mkdir(parents=True)
        for name in SCRIPTS:
            shutil.copy2(ROOT / "scripts" / name, self.maintenance / name)
        for name, source in SIDECARS.items():
            shutil.copy2(ROOT / source, self.maintenance / name)
        self.env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "HOME": str(self.root), "LANG": "C.UTF-8",
                    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}

    def test_all_installed_ollama_helpers_run_without_checkout_pythonpath(self):
        for name in SCRIPTS:
            with self.subTest(helper=name):
                result = subprocess.run([sys.executable, "-s", str(self.maintenance / name), "--help"],
                    cwd=self.root, env=self.env, capture_output=True, text=True, timeout=8)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
        self.assertEqual(list(self.maintenance.rglob("*.pyc")), [])

    def test_sidecars_packaged_from_canonical_sources(self):
        text = (ROOT / "scripts/release_manager.py").read_text()
        for name in SIDECARS:
            self.assertTrue('maintenance / "' + name + '"' in text, name + " not packaged")

    def test_missing_installed_dependency_is_not_hidden(self):
        (self.maintenance / "ollama_errors.py").unlink()
        result = subprocess.run([sys.executable, "-s", str(self.maintenance / "ollama_manager.py"), "--help"],
            cwd=self.root, env=self.env, capture_output=True, text=True, timeout=8)
        self.assertNotEqual(result.returncode, 0)

if __name__ == "__main__": unittest.main()
