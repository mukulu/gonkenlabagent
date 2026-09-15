from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "bounded_unittest.py"
CI = ROOT / "scripts" / "ci.sh"


class BoundedUnittestRunnerTests(unittest.TestCase):
    def make_fixture(self, body: str) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        tests = root / "tests" / "unit"
        tests.mkdir(parents=True)
        (root / "tests" / "__init__.py").write_text("\n", encoding="utf-8")
        (tests / "__init__.py").write_text("\n", encoding="utf-8")
        (tests / "test_fixture.py").write_text(textwrap.dedent(body), encoding="utf-8")
        return temporary, root

    def add_fixture_module(self, root: Path, name: str, body: str) -> None:
        target = root / "tests" / "unit" / f"{name}.py"
        target.write_text(textwrap.dedent(body), encoding="utf-8")

    def run_runner(
        self,
        root: Path,
        *,
        timeout: str = "5",
        heartbeat: str = "0.1",
        extra: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(RUNNER),
            "--root",
            str(root),
            "--suite-dir",
            "tests/unit",
            "--label",
            "fixture",
            "--log-dir",
            str(root / "logs"),
            "--manifest",
            str(root / "manifest.json"),
            "--timeout-seconds",
            timeout,
            "--heartbeat-seconds",
            heartbeat,
        ]
        if extra:
            command.extend(extra)
        return subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_passing_module_writes_manifest_and_log(self) -> None:
        _temporary, root = self.make_fixture(
            """
            import unittest
            class FixtureTests(unittest.TestCase):
                def test_ok(self):
                    self.assertEqual(2 + 2, 4)
            """
        )
        result = self.run_runner(root)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["result"], "PASS")
        self.assertEqual(manifest["status_counts"], {"PASS": 1})
        self.assertTrue((root / "logs/tests_unit_test_fixture.log").is_file())

    def test_failing_module_returns_nonzero_but_preserves_manifest(self) -> None:
        _temporary, root = self.make_fixture(
            """
            import unittest
            class FixtureTests(unittest.TestCase):
                def test_fail(self):
                    self.fail('deliberate')
            """
        )
        result = self.run_runner(root)
        self.assertNotEqual(result.returncode, 0)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["result"], "FAIL")
        self.assertEqual(manifest["status_counts"], {"FAIL": 1})
        self.assertIn("test_fail", (root / "logs/tests_unit_test_fixture.log").read_text(encoding="utf-8"))

    def test_timeout_module_returns_nonzero_and_kills_child(self) -> None:
        _temporary, root = self.make_fixture(
            """
            import time
            import unittest
            class FixtureTests(unittest.TestCase):
                def test_hangs(self):
                    time.sleep(5)
            """
        )
        result = self.run_runner(root, timeout="0.3", heartbeat="0.1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("[WAIT] module=tests.unit.test_fixture", result.stdout)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status_counts"], {"TIMEOUT": 1})
        self.assertTrue(manifest["modules"][0]["timed_out"])

    def test_case_granularity_runs_each_unittest_method_with_separate_log(self) -> None:
        _temporary, root = self.make_fixture(
            """
            import unittest
            class FixtureTests(unittest.TestCase):
                def test_alpha(self):
                    self.assertTrue(True)
                def test_beta(self):
                    self.assertEqual('b'.upper(), 'B')
            """
        )
        result = self.run_runner(root, extra=["--granularity", "case"])
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["granularity"], "case")
        self.assertEqual(manifest["module_count"], 2)
        modules = {entry["module"] for entry in manifest["modules"]}
        self.assertIn("tests.unit.test_fixture.FixtureTests.test_alpha", modules)
        self.assertIn("tests.unit.test_fixture.FixtureTests.test_beta", modules)
        self.assertTrue((root / "logs/tests_unit_test_fixture_FixtureTests_test_alpha.log").is_file())
        self.assertTrue((root / "logs/tests_unit_test_fixture_FixtureTests_test_beta.log").is_file())

    def test_excluded_module_is_not_selected_during_discovery(self) -> None:
        _temporary, root = self.make_fixture(
            """
            import unittest
            class FixtureTests(unittest.TestCase):
                def test_ok(self):
                    self.assertTrue(True)
            """
        )
        self.add_fixture_module(
            root,
            "test_other",
            """
            import unittest
            class OtherTests(unittest.TestCase):
                def test_other_ok(self):
                    self.assertTrue(True)
            """,
        )
        result = self.run_runner(root, extra=["--exclude-module", "tests.unit.test_other"])
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        modules = [entry["module"] for entry in manifest["modules"]]
        self.assertEqual(modules, ["tests.unit.test_fixture"])

    def test_ci_uses_bounded_runner_for_unit_and_integration_suites(self) -> None:
        text = CI.read_text(encoding="utf-8")
        self.assertIn("bounded_unittest.py", text)
        self.assertIn("--suite-dir tests/unit", text)
        self.assertIn("--suite-dir tests/integration", text)
        self.assertIn("--exclude-module tests.integration.test_release_lifecycle_process", text)
        self.assertIn("--granularity case", text)
        self.assertIn("integration-release-lifecycle", text)
        self.assertIn("GONKEN_CI_UNIT_MODULE_TIMEOUT", text)
        self.assertIn("GONKEN_CI_INTEGRATION_MODULE_TIMEOUT", text)
        self.assertIn("GONKEN_CI_RELEASE_CASE_TIMEOUT", text)
        self.assertIn("--phase", text)
        self.assertIn("release-lifecycle", text)

    def test_ci_exposes_phase_selection_for_long_host_runs(self) -> None:
        help_result = subprocess.run(
            ["bash", str(CI), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("--phase PHASE", help_result.stdout)
        self.assertIn("release-lifecycle", help_result.stdout)

        list_result = subprocess.run(
            ["bash", str(CI), "--list-phases"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(list_result.returncode, 0, list_result.stderr)
        self.assertEqual(
            list_result.stdout.splitlines(),
            ["t0", "unit", "integration", "release-lifecycle", "all"],
        )

    def test_ci_rejects_unknown_phase_without_running_checks(self) -> None:
        result = subprocess.run(
            ["bash", str(CI), "--phase", "unknown"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown phase", result.stderr)


if __name__ == "__main__":
    unittest.main()
