from __future__ import annotations

import os
import platform
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "scripts" / "install.sh"
HARNESS = ROOT / "tests" / "fixtures" / "install_engine_harness.sh"


def git(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )


class InstallProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.source = self.root / "source"
        self.source.mkdir()
        git("init", "-q", "--initial-branch=main", cwd=self.source)
        git("config", "user.name", "Test User", cwd=self.source)
        git("config", "user.email", "test@example.invalid", cwd=self.source)
        (self.source / "README.md").write_text("source\n", encoding="utf-8")
        git("add", "README.md", cwd=self.source)
        git("commit", "-q", "-m", "source", cwd=self.source)
        self.commit = git("rev-parse", "HEAD", cwd=self.source).stdout.strip()
        self.checkout = self.root / "empty-checkout"
        self.checkout.mkdir()
        self.record = self.root / "source.record"
        self.state = self.root / "state"
        self.logs = self.root / "logs"
        self.write_record()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def record_lines(self) -> list[str]:
        return [
            "format=gonken-bootstrap-source-v1",
            f"source_url={self.source.as_uri()}",
            "requested_ref=main",
            f"resolved_commit={self.commit}",
            "platform_mode=development",
            "invoking_user=root",
            f"kernel_name={platform.system()}",
            f"architecture={platform.machine()}",
            "userspace_bits=64",
            f"python_version={sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "os_id=development",
            "os_version_id=not-applicable",
            "os_codename=not-applicable",
            "os_build_id=not-applicable",
            "os_release_sha256=not-applicable",
            "pi_issue_sha256=not-applicable",
            "rpi_image_reference=not-applicable",
            "pi_model=development-host",
            "pid1=not-required",
            "systemd_version=not-required",
            "free_kib=9000000",
            "memory_kib=4000000",
            f"observed_epoch={int(time.time())}",
            f"existing_checkout={self.checkout}",
        ]

    def write_record(self, extra: list[str] | None = None) -> None:
        lines = self.record_lines()
        if extra:
            lines.extend(extra)
        self.record.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.record.chmod(0o600)

    def run_install(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(INSTALL),
                "--source-record",
                str(self.record),
                "--state-dir",
                str(self.state),
                "--log-dir",
                str(self.logs),
                *extra,
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def stable_snapshot(self) -> dict[str, bytes]:
        files = list((self.state / "steps").glob("*.record"))
        files.extend((self.state / "artifacts").glob("*.record"))
        return {str(path.relative_to(self.state)): path.read_bytes() for path in files}

    def test_successful_engine_run_is_private_and_repeatable(self) -> None:
        first = self.run_install("--engine-only")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("code=M3_2_ENGINE_COMPLETE", first.stdout)
        before = self.stable_snapshot()
        first_events = {
            path.name: path.read_bytes()
            for path in (self.logs / "events").glob("*.event")
        }
        second = self.run_install("--engine-only")
        after = self.stable_snapshot()
        second_events = {
            path.name: path.read_bytes()
            for path in (self.logs / "events").glob("*.event")
        }
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(before, after)
        self.assertLess(len(first_events), len(second_events))
        self.assertEqual(
            first_events,
            {name: second_events[name] for name in first_events},
        )
        self.assertEqual(second.stdout.count("INSTALL_STEP_SATISFIED"), 2)
        for path in [self.state, self.logs, self.state / "steps", self.logs / "events"]:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        for path in self.state.rglob("*.record"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        for path in (self.logs / "events").glob("*.event"):
            self.assertTrue(
                path.read_text(encoding="utf-8").startswith(
                    "format=gonken-install-event-v1\n"
                )
            )

    def test_engine_only_stops_before_release_provisioning(self) -> None:
        result = self.run_install("--engine-only")
        self.assertEqual(result.returncode, 0)
        self.assertIn("code=M3_2_ENGINE_COMPLETE", result.stdout)
        self.assertFalse((self.root / "development-root").exists())

    def test_false_complete_state_is_repaired_from_probe_truth(self) -> None:
        self.assertEqual(self.run_install("--engine-only").returncode, 0)
        marker = self.state / "artifacts" / "source-validation.record"
        marker.write_text("format=corrupt\n", encoding="utf-8")
        state_record = self.state / "steps" / "source_record_validation.record"
        self.assertIn("status=complete", state_record.read_text(encoding="utf-8"))
        result = self.run_install("--engine-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("step=source_record_validation", result.stdout)
        self.assertIn("format=gonken-source-validation-v1", marker.read_text(encoding="utf-8"))

    def test_good_probe_repairs_missing_advisory_state_without_action(self) -> None:
        self.assertEqual(self.run_install("--engine-only").returncode, 0)
        marker = self.state / "artifacts" / "engine-contract.record"
        marker_before = marker.read_bytes()
        (self.state / "steps" / "engine_contract.record").unlink()
        result = self.run_install("--engine-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("INSTALL_STEP_SATISFIED step=engine_contract", result.stdout)
        self.assertEqual(marker.read_bytes(), marker_before)

    def test_record_is_data_and_never_shell_executed(self) -> None:
        payload = self.root / "executed"
        lines = self.record_lines()
        index = lines.index("os_build_id=not-applicable")
        lines[index] = f"os_build_id=$(touch {payload})"
        self.record.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.record.chmod(0o600)
        result = self.run_install("--engine-only")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(payload.exists())

    def test_duplicate_or_permissive_record_fails_before_state_mutation(self) -> None:
        self.write_record(["source_url=https://example.invalid/duplicate.git"])
        duplicate = self.run_install("--engine-only")
        self.assertEqual(duplicate.returncode, 65)
        self.assertIn("duplicate field", duplicate.stderr)
        self.assertFalse(self.state.exists())

        self.write_record()
        self.record.chmod(0o644)
        permissive = self.run_install("--engine-only")
        self.assertEqual(permissive.returncode, 65)
        self.assertIn("INSTALL_RECORD_PERMISSIONS", permissive.stderr)
        self.assertFalse(self.state.exists())

    def test_moved_remote_ref_fails_before_state_mutation(self) -> None:
        (self.source / "README.md").write_text("moved\n", encoding="utf-8")
        git("add", "README.md", cwd=self.source)
        git("commit", "-q", "-m", "move ref", cwd=self.source)
        result = self.run_install("--engine-only")
        self.assertEqual(result.returncode, 69)
        self.assertIn("code=INSTALL_SOURCE_CHANGED", result.stderr)
        self.assertFalse(self.state.exists())


class InterruptionProcessTests(unittest.TestCase):
    def run_harness(
        self,
        root: Path,
        *,
        interrupt: str | None = None,
        mode: str = "term",
    ) -> subprocess.CompletedProcess[str]:
        state = root / "state"
        logs = root / "logs"
        work = root / "work"
        work.mkdir(exist_ok=True)
        work.chmod(0o700)
        environment = os.environ.copy()
        if interrupt:
            environment["GONKEN_ENABLE_TEST_FAILURES"] = "1"
            environment["GONKEN_INSTALL_TEST_INTERRUPT"] = interrupt
            environment["GONKEN_INSTALL_TEST_INTERRUPT_MODE"] = mode
        return subprocess.run(
            [str(HARNESS), str(state), str(logs), str(work)],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def assert_converged(self, root: Path) -> None:
        result = self.run_harness(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        for step_id in ("alpha", "beta"):
            self.assertEqual(
                (root / "work" / f"{step_id}.marker").read_text(encoding="utf-8"),
                f"complete={step_id}\n",
            )
            state = (root / "state" / "steps" / f"{step_id}.record").read_text(
                encoding="utf-8"
            )
            self.assertIn("status=complete", state)
        self.assertFalse((root / "state" / "engine.lock").exists())
        self.assertEqual(list(root.rglob(".gonken-tmp.*")), [])
        self.assertEqual(list(root.rglob("*.partial")), [])

    def test_term_interrupt_before_during_after_every_fake_step_then_converges(self) -> None:
        for step_id in ("alpha", "beta"):
            for boundary in ("before", "during", "after"):
                with self.subTest(step=step_id, boundary=boundary), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    root.chmod(0o700)
                    interrupted = self.run_harness(root, interrupt=f"{step_id}:{boundary}")
                    self.assertEqual(interrupted.returncode, 75, interrupted.stderr)
                    self.assertIn("code=INSTALL_INTERRUPTED", interrupted.stderr)
                    interrupted_state = (
                        root / "state" / "steps" / f"{step_id}.record"
                    ).read_text(encoding="utf-8")
                    self.assertIn("status=interrupted", interrupted_state)
                    self.assertFalse((root / "state" / "engine.lock").exists())
                    self.assert_converged(root)

    def test_abrupt_kill_leaves_recoverable_stale_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            interrupted = self.run_harness(
                root, interrupt="alpha:during", mode="kill"
            )
            self.assertEqual(interrupted.returncode, -9)
            self.assertTrue((root / "state" / "engine.lock").exists())
            self.assertTrue((root / "work" / "alpha.partial").exists())
            running_state = (
                root / "state" / "steps" / "alpha.record"
            ).read_text(encoding="utf-8")
            self.assertIn("status=running", running_state)
            self.assert_converged(root)

    def test_advisory_complete_state_never_overrides_failed_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            self.assert_converged(root)
            marker = root / "work" / "alpha.marker"
            marker.write_text("wrong\n", encoding="utf-8")
            result = self.run_harness(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("INSTALL_STEP_COMPLETE step=alpha", result.stdout)
            self.assertEqual(marker.read_text(encoding="utf-8"), "complete=alpha\n")


if __name__ == "__main__":
    unittest.main()
