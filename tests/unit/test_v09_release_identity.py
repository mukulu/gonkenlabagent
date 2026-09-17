from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gonken_agent import release_identity
from gonken_agent.voice_runtime import _runtime_release_commit, _runtime_release_profile


class RuntimeReleaseIdentityTests(unittest.TestCase):
    def make_release(self, root: Path, commit: str = "a" * 40, profile: str = "core-pi-trixie-py313") -> tuple[Path, Path]:
        release = root / "releases" / commit
        package = release / ".venv" / "lib" / "python3.13" / "site-packages" / "gonken_agent" / "release_identity.py"
        package.parent.mkdir(parents=True)
        package.write_text("# package anchor\n", encoding="utf-8")
        (release / "release.record").write_text(
            f"format=gonken-release-v1\ncommit={commit}\nprofile={profile}\n",
            encoding="utf-8",
        )
        return release, package

    def test_package_anchor_preserves_identity_when_venv_python_symlink_resolves_outside_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release, package = self.make_release(root)
            system_python = root / "usr" / "bin" / "python3.13"
            system_python.parent.mkdir(parents=True)
            system_python.write_text("fixture\n", encoding="utf-8")
            venv_python = release / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True)
            venv_python.symlink_to(system_python)
            self.assertNotIn(release.name, str(venv_python.resolve()))
            identity = release_identity.runtime_release_identity(package_anchor=package)
            self.assertEqual(identity.commit, release.name)
            self.assertEqual(identity.profile, "core-pi-trixie-py313")
            self.assertTrue(identity.immutable)

    def test_voice_runtime_wrappers_use_package_identity_not_sys_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release, package = self.make_release(root, commit="c" * 40)
            outside = root / "python3.13"
            outside.write_text("fixture\n", encoding="utf-8")
            with mock.patch.object(release_identity, "__file__", str(package)), \
                 mock.patch("gonken_agent.voice_runtime.sys.executable", str(outside)):
                self.assertEqual(_runtime_release_commit(), release.name)
                self.assertEqual(_runtime_release_profile(), "core-pi-trixie-py313")

    def test_source_tree_is_development(self) -> None:
        identity = release_identity.runtime_release_identity(package_anchor=Path(__file__))
        self.assertEqual(identity.commit, "development")
        self.assertEqual(identity.profile, "development")
        self.assertFalse(identity.immutable)

    def test_invalid_record_profile_is_unknown_not_development(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release, package = self.make_release(root)
            (release / "release.record").write_text(
                f"format=gonken-release-v1\ncommit={release.name}\nprofile=INVALID PROFILE\n",
                encoding="utf-8",
            )
            identity = release_identity.runtime_release_identity(package_anchor=package)
            self.assertEqual(identity.commit, release.name)
            self.assertEqual(identity.profile, "unknown")
