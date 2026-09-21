from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import archive_qualifier


class ArchiveQualifierTests(unittest.TestCase):
    def write_zip(self, entries: dict[str, str], *, symlink: str | None = None) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "package.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name, payload in entries.items():
                archive.writestr(name, payload)
            if symlink is not None:
                info = zipfile.ZipInfo(symlink)
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, "target")
        return path

    def test_inspect_zip_accepts_single_clean_root(self) -> None:
        path = self.write_zip({"package/README.md": "ok", "package/scripts/ci.sh": "#!/bin/sh\n"})
        report = archive_qualifier.inspect_zip(path)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["root"], "package")

    def test_inspect_zip_rejects_python_cache_artifacts(self) -> None:
        path = self.write_zip({"package/scripts/__pycache__/x.cpython-312.pyc": "cache"})
        report = archive_qualifier.inspect_zip(path)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("python_cache", report["detail"])

    def test_inspect_zip_rejects_unsafe_paths_and_multiple_roots(self) -> None:
        path = self.write_zip({"package/README.md": "ok", "../escape.txt": "no", "other/file.txt": "no"})
        report = archive_qualifier.inspect_zip(path)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("unsafe_path", report["detail"])
        self.assertIn("single_root_required", report["detail"])

    def test_inspect_zip_rejects_symlinks(self) -> None:
        path = self.write_zip({"package/README.md": "ok"}, symlink="package/link")
        report = archive_qualifier.inspect_zip(path)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("symlink", report["detail"])

    def test_extract_zip_preserves_executable_permissions(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "package.zip"
        info = zipfile.ZipInfo("package/scripts/run.sh")
        info.external_attr = (stat.S_IFREG | 0o755) << 16
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(info, "#!/bin/sh\n")
        output = Path(temporary.name) / "extract"
        archive_qualifier.extract_zip_preserving_permissions(path, output)
        mode = (output / "package" / "scripts" / "run.sh").stat().st_mode & 0o777
        self.assertEqual(mode, 0o755)

    def test_main_json_reports_no_physical_acceptance_for_invalid_archive(self) -> None:
        path = self.write_zip({"package/__pycache__/x.pyc": "cache"})
        with patch("sys.stdout") as stdout:
            code = archive_qualifier.main([str(path), "--json"])
        self.assertEqual(code, 1)
        payload = json.loads("".join(call.args[0] + "\n" for call in stdout.write.call_args_list if call.args))
        self.assertFalse(payload["physical_acceptance_claimed"])
        self.assertFalse(payload["raspberry_pi_candidate"])

    def test_qualify_archive_uses_expected_commit_and_tag_checks(self) -> None:
        path = self.write_zip({"package/.git/HEAD": "ref: refs/heads/main\n", "package/README.md": "ok"})
        commands: list[tuple[str, ...]] = []

        def fake_run(command, cwd, *, timeout=60):
            commands.append(tuple(command))
            if command[:3] == ["git", "status", "--porcelain"]:
                return {"status": "PASS", "command": command, "exit": 0, "stdout": "", "stderr": ""}
            return {"status": "PASS", "command": command, "exit": 0, "stdout": "", "stderr": ""}

        def fake_git_text(repo, *args):
            if args == ("rev-parse", "HEAD"):
                return "a" * 40
            if args == ("tag", "--points-at", "HEAD"):
                return "checkpoint/example"
            return ""

        with patch.object(archive_qualifier, "_run", side_effect=fake_run), \
             patch.object(archive_qualifier, "_git_text", side_effect=fake_git_text):
            report = archive_qualifier.qualify_archive(
                path,
                expected_commit="a" * 40,
                expected_tag="checkpoint/example",
                run_t0=True,
            )
        self.assertEqual(report["status"], "PASS")
        self.assertIn(("git", "fsck", "--strict"), commands)
        self.assertIn((os.sys.executable, "scripts/current_state.py", "--check"), commands)
        self.assertIn((os.sys.executable, "scripts/release_readiness.py", "--check"), commands)
        self.assertIn(("./scripts/ci.sh", "--phase", "t0"), commands)


if __name__ == "__main__":
    unittest.main()
