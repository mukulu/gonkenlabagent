from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "requirements"
SCRIPT = ROOT / "scripts" / "dependencies.py"


def load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


class DependencyProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_toml(REQUIREMENTS / "profiles.toml")
        cls.profiles = {item["id"]: item for item in cls.manifest["profiles"]}
        cls.blocked = {
            item["id"]: item for item in cls.manifest["blocked_profiles"]
        }

    def test_project_core_is_empty_and_ui_is_optional(self) -> None:
        project = load_toml(ROOT / "pyproject.toml")["project"]
        self.assertEqual(project["dependencies"], [])
        self.assertEqual(project["optional-dependencies"], {"ui": ["pygame==2.6.1"]})
        self.assertEqual(project["requires-python"], ">=3.12,<3.14")

    def test_required_profile_boundaries_exist(self) -> None:
        self.assertEqual(
            set(self.profiles),
            {
                "core-pi-trixie-py313",
                "dev-py312",
                "speech-piper-pi-trixie-py313",
                "ui-pi-trixie-py313",
                "ui-dev-py312",
            },
        )
        core = self.profiles["core-pi-trixie-py313"]
        self.assertEqual(core["dependencies"], [])
        self.assertEqual(core["python"], "3.13")
        self.assertEqual(self.manifest["target_arch"], "aarch64")

    def test_generated_locks_are_current(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "render", "--check"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("verified 5", result.stdout)

    def test_every_accepted_requirement_is_exact_hashed_and_binary_only(self) -> None:
        requirement_re = re.compile(r"^[A-Za-z0-9_.+-]+==[^ ]+ --hash=sha256:[0-9a-f]{64}$")
        for profile in self.profiles.values():
            lock = ROOT / profile["lock"]
            text = lock.read_text(encoding="utf-8")
            self.assertIn("--require-hashes", text)
            self.assertIn("--only-binary=:all:", text)
            for line in text.splitlines():
                if not line or line.startswith("#") or line.startswith("--"):
                    continue
                self.assertRegex(line, requirement_re)

    def test_artifacts_match_declared_interpreter_and_platform(self) -> None:
        for profile in self.profiles.values():
            python_tag = "cp" + profile["python"].replace(".", "")
            architecture = profile["platform"].rsplit("_", 1)[-1]
            for dependency in profile.get("dependencies", []):
                for artifact in dependency["artifacts"]:
                    filename = artifact["filename"]
                    pure_python = re.search(r"-py[23](?:\.py3)?-none-any\.whl$", filename) is not None
                    abi3_python = "-abi3-" in filename and re.search(r"-cp3[0-9]-abi3-", filename)
                    self.assertTrue(pure_python or python_tag in filename or abi3_python, filename)
                    if not pure_python:
                        self.assertIn(architecture, filename)

    def test_ui_and_wake_dependencies_cannot_leak_into_core(self) -> None:
        core_lock = (
            ROOT / self.profiles["core-pi-trixie-py313"]["lock"]
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("pygame", core_lock)
        self.assertNotIn("openwakeword", core_lock)
        self.assertIn("pygame==2.6.1", (REQUIREMENTS / "ui-pi-trixie-py313.lock").read_text())

    def test_blocked_profiles_have_reasons_and_no_locks(self) -> None:
        self.assertEqual(
            set(self.blocked),
            {"x1-wake-pi-trixie-py313"},
        )
        for profile in self.blocked.values():
            self.assertEqual(profile["status"], "blocked")
            self.assertGreaterEqual(len(profile["blockers"]), 3)
            self.assertNotIn("lock", profile)
        self.assertIn("tflite-runtime", " ".join(self.blocked["x1-wake-pi-trixie-py313"]["blockers"]))

    def test_legacy_ranges_are_quarantined_from_accepted_paths(self) -> None:
        self.assertFalse((ROOT / "requirements.txt").exists())
        legacy = REQUIREMENTS / "legacy-prototype.in"
        self.assertTrue(legacy.is_file())
        self.assertNotIn("pygame", "\n".join(
            line for line in legacy.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ))
        setup = (ROOT / "setup.sh").read_text(encoding="utf-8")
        self.assertIn("requirements/legacy-prototype.in", setup)
        self.assertIn("unaccepted legacy compatibility runtime", setup)
        self.assertNotIn("libsdl2", setup)

    def test_license_report_is_machine_readable_and_fail_closed(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "report", "--json"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        states = {row["profile"]: row["status"] for row in report}
        self.assertEqual(states["core-pi-trixie-py313"], "installable")
        self.assertEqual(states["speech-piper-pi-trixie-py313"], "installable")
        self.assertEqual(states["x1-wake-pi-trixie-py313"], "blocked")
        self.assertFalse(any(row["license"].startswith("UNVERIFIED") for row in report))


if __name__ == "__main__":
    unittest.main()
