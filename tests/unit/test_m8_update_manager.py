from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "update_manager", ROOT / "scripts" / "update_manager.py"
)
assert SPEC and SPEC.loader
update_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(update_manager)


def git(*arguments: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class UpdateManagerTests(unittest.TestCase):
    def source_repo(self) -> tuple[tempfile.TemporaryDirectory[str], Path, str, str]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repo = Path(temporary.name) / "source"
        repo.mkdir()
        git("init", "-q", "--initial-branch=main", cwd=repo)
        git("config", "user.name", "M8 Update Test", cwd=repo)
        git("config", "user.email", "test@example.invalid", cwd=repo)
        (repo / "marker.txt").write_text("one\n", encoding="utf-8")
        git("add", ".", cwd=repo)
        git("commit", "-q", "-m", "one", cwd=repo)
        first = git("rev-parse", "HEAD", cwd=repo)
        (repo / "marker.txt").write_text("two\n", encoding="utf-8")
        git("commit", "-am", "two", "-q", cwd=repo)
        second = git("rev-parse", "HEAD", cwd=repo)
        return temporary, repo, first, second

    def fake_release_manager(self, current: str | None):
        events: list[tuple[str, str | None]] = []
        module = types.ModuleType("release_manager")

        @contextmanager
        def lock(_state_root: Path):
            events.append(("lock", None))
            yield

        def reconcile(_release_root: Path, _state_root: Path, _service_user: str) -> None:
            events.append(("reconcile", current))

        def current_commit(_release_root: Path) -> str | None:
            return current

        def status(_release_root: Path, _state_root: Path, expected: str | None, _service_user: str) -> None:
            events.append(("status", expected))

        def build_release(_source_url: str, _ref: str, commit: str, _release_root: Path, _profile: str, _service_user: str) -> None:
            events.append(("build", commit))

        def activate(_release_root: Path, _state_root: Path, commit: str, _service_user: str) -> None:
            nonlocal current
            current = commit
            events.append(("activate", commit))

        def prune_releases(_release_root: Path, _state_root: Path, _service_user: str) -> None:
            events.append(("prune", current))

        module.maintenance_lock = lock
        module.reconcile = reconcile
        module.current_commit = current_commit
        module.status = status
        module.build_release = build_release
        module.activate = activate
        module.prune_releases = prune_releases
        return module, events

    def systemctl(self, root: Path) -> tuple[Path, Path]:
        log = root / "systemctl.log"
        tool = root / "systemctl"
        tool.write_text(
            "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$GONKEN_FAKE_SYSTEMCTL_LOG\"\nexit 0\n",
            encoding="utf-8",
        )
        tool.chmod(0o755)
        return tool, log

    def test_resolve_ref_accepts_unambiguous_local_branch_under_test_gate(self) -> None:
        _temporary, repo, _first, second = self.source_repo()
        os.environ["GONKEN_ENABLE_TEST_FAILURES"] = "1"
        self.addCleanup(os.environ.pop, "GONKEN_ENABLE_TEST_FAILURES", None)
        self.assertEqual(update_manager.resolve_ref(repo.as_uri(), "main"), second)

    def test_source_and_ref_validation_fail_closed(self) -> None:
        with self.assertRaises(update_manager.UpdateError) as raised:
            update_manager.validate_source("file:///tmp/source", "main")
        self.assertEqual(raised.exception.code, "UPDATE_SOURCE")
        with self.assertRaises(update_manager.UpdateError) as raised:
            update_manager.validate_source("https://example.invalid/repo.git", "../main")
        self.assertEqual(raised.exception.code, "UPDATE_REF")

    def test_update_noop_does_not_restart_service(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _tmp, repo, _first, second = self.source_repo()
            fake, events = self.fake_release_manager(second)
            previous = sys.modules.get("release_manager")
            sys.modules["release_manager"] = fake
            os.environ["GONKEN_ENABLE_TEST_FAILURES"] = "1"
            systemctl, log = self.systemctl(root)
            os.environ["GONKEN_FAKE_SYSTEMCTL_LOG"] = str(log)
            self.addCleanup(os.environ.pop, "GONKEN_ENABLE_TEST_FAILURES", None)
            self.addCleanup(os.environ.pop, "GONKEN_FAKE_SYSTEMCTL_LOG", None)
            self.addCleanup(lambda: sys.modules.pop("release_manager", None))
            if previous is not None:
                self.addCleanup(lambda: sys.modules.__setitem__("release_manager", previous))
            update_manager.update(root / "release", root / "state", repo.as_uri(), "main", "dev-py312", "tester", systemctl, True)
            self.assertIn(("status", second), events)
            self.assertFalse(log.exists())

    def test_update_builds_activates_prunes_and_restarts_service(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _tmp, repo, first, second = self.source_repo()
            fake, events = self.fake_release_manager(first)
            previous = sys.modules.get("release_manager")
            sys.modules["release_manager"] = fake
            os.environ["GONKEN_ENABLE_TEST_FAILURES"] = "1"
            systemctl, log = self.systemctl(root)
            os.environ["GONKEN_FAKE_SYSTEMCTL_LOG"] = str(log)
            self.addCleanup(os.environ.pop, "GONKEN_ENABLE_TEST_FAILURES", None)
            self.addCleanup(os.environ.pop, "GONKEN_FAKE_SYSTEMCTL_LOG", None)
            self.addCleanup(lambda: sys.modules.pop("release_manager", None))
            if previous is not None:
                self.addCleanup(lambda: sys.modules.__setitem__("release_manager", previous))
            update_manager.update(root / "release", root / "state", repo.as_uri(), "main", "dev-py312", "tester", systemctl, True)
            self.assertIn(("build", second), events)
            self.assertIn(("activate", second), events)
            self.assertIn(("prune", second), events)
            self.assertEqual(log.read_text(encoding="utf-8").strip(), "restart gonken-agent.service")


if __name__ == "__main__":
    unittest.main()
