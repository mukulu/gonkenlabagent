from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
FORBIDDEN_AUTOMATED_IMPORTS = {
    "gpiozero",
    "httpx",
    "numpy",
    "onnxruntime",
    "openwakeword",
    "piper",
    "pygame",
    "requests",
    "scipy",
    "sklearn",
    "sounddevice",
}


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.partition(".")[0])
    return roots


class TestArchitectureTests(unittest.TestCase):
    def test_no_interactive_program_is_named_as_an_automated_test(self) -> None:
        self.assertEqual(list(TESTS.glob("test*.py")), [])
        manual_names = {
            path.name for path in TESTS.rglob("*_manual.py")
        }
        self.assertEqual(
            manual_names,
            {
                "audio_pipeline_manual.py",
                "router_live_manual.py",
                "wake_word_manual.py",
            },
        )

    def test_automated_suites_do_not_import_optional_boundaries(self) -> None:
        violations: dict[str, list[str]] = {}
        paths = list((TESTS / "unit").glob("test*.py"))
        paths.extend((TESTS / "integration").glob("test*.py"))
        for path in paths:
            forbidden = sorted(imported_roots(path) & FORBIDDEN_AUTOMATED_IMPORTS)
            if forbidden:
                violations[str(path.relative_to(ROOT))] = forbidden
        self.assertEqual(violations, {})

    def test_manual_programs_refuse_unintentional_execution(self) -> None:
        programs = [
            TESTS / "hardware" / "audio_pipeline_manual.py",
            TESTS / "hardware" / "wake_word_manual.py",
            TESTS / "integration" / "manual" / "router_live_manual.py",
        ]
        environment = os.environ.copy()
        environment.pop("GONKEN_RUN_HARDWARE_TESTS", None)
        environment.pop("GONKEN_RUN_LIVE_INTEGRATION", None)
        for program in programs:
            with self.subTest(program=program.name):
                result = subprocess.run(
                    [sys.executable, str(program)],
                    cwd=ROOT,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.assertEqual(result.returncode, 2, result.stderr or result.stdout)
                self.assertNotIn("Traceback", result.stderr)

    def test_ci_entry_point_has_no_install_or_network_step(self) -> None:
        script = (ROOT / "scripts" / "ci.sh").read_text(encoding="utf-8")
        self.assertIn("tests/unit", script)
        self.assertIn("tests/integration", script)
        self.assertIn("dependencies.py\" render --check", script)
        for forbidden in ("pip install", "curl ", "wget ", "apt "):
            self.assertNotIn(forbidden, script)

    def test_hardware_and_live_probe_boundaries_are_documented(self) -> None:
        hardware = (TESTS / "hardware" / "README.md").read_text(encoding="utf-8")
        integration = (TESTS / "integration" / "README.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("GONKEN_RUN_HARDWARE_TESTS=1", hardware)
        self.assertIn("advertises no", hardware)
        self.assertIn("GONKEN_RUN_LIVE_INTEGRATION=1", integration)
        self.assertIn("get_joke", integration)


if __name__ == "__main__":
    unittest.main()
