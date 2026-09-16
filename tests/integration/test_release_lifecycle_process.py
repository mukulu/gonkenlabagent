from __future__ import annotations

import hashlib
import os
import platform
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests.fixtures.release_fakes import create_fake_release, current_user, point_current


ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "scripts" / "install.sh"
MANAGER = ROOT / "scripts" / "release_manager.py"
ROLLBACK = ROOT / "scripts" / "rollback.sh"
PREVIOUS = "1" * 40
CANDIDATE = "2" * 40


def git(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True
    )


def activation_record(candidate: str, previous: str, phase: str) -> str:
    return (
        "format=gonken-activation-v1\n"
        f"candidate_commit={candidate}\n"
        f"previous_commit={previous}\n"
        f"phase={phase}\n"
        f"observed_epoch={int(time.time())}\n"
        "message=fixture\n"
    )


class EndToEndReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.root.chmod(0o700)
        cls.source = cls.root / "source"
        shutil.copytree(
            ROOT,
            cls.source,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".venv", "build", "*.egg-info"),
        )
        git("init", "-q", "--initial-branch=main", cwd=cls.source)
        git("config", "user.name", "M3.3 Test", cwd=cls.source)
        git("config", "user.email", "test@example.invalid", cwd=cls.source)
        git("add", ".", cwd=cls.source)
        git("commit", "-q", "-m", "fixture source", cwd=cls.source)
        cls.commit = git("rev-parse", "HEAD", cwd=cls.source).stdout.strip()
        cls.record = cls.root / "source.record"
        cls.checkout = cls.root / "empty-checkout"
        cls.checkout.mkdir()
        cls.write_record()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    @classmethod
    def write_record(cls) -> None:
        fields = [
            "format=gonken-bootstrap-source-v1",
            f"source_url={cls.source.as_uri()}",
            "requested_ref=main",
            f"resolved_commit={cls.commit}",
            "platform_mode=development",
            f"invoking_user={current_user()}",
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
            f"existing_checkout={cls.checkout}",
        ]
        cls.record.write_text("\n".join(fields) + "\n", encoding="utf-8")
        cls.record.chmod(0o600)

    def run_install(self, system_root: Path, *extra: str, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if environment:
            env.update(environment)
        return subprocess.run(
            [
                str(INSTALL),
                "--source-record", str(self.record),
                "--system-root", str(system_root),
                *extra,
            ],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )

    def assert_release_only_complete(self, system_root: Path) -> tuple[Path, Path]:
        first = self.run_install(system_root, "--release-only")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("code=M3_3_RELEASE_COMPLETE", first.stdout)
        release_root = system_root / "usr/local/lib/gonken-agent"
        release = release_root / "releases" / self.commit
        current = release_root / "current"
        self.assertEqual(os.readlink(current), f"releases/{self.commit}")
        self.assertTrue((release / ".venv/bin/gonken-agent").is_file())
        self.assertFalse((release / "assets").exists())
        self.assertFalse((release / "source").exists())
        self.assertEqual(
            subprocess.run(
                [str(system_root / "usr/local/bin/gonken-agent"), "version"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "0.2.0.dev0",
        )
        # Executing the sealed current release must not create bytecode/cache
        # artifacts inside the immutable tree or invalidate its recorded digest.
        static_check = subprocess.run(
            [
                sys.executable, str(MANAGER), "validate-static",
                "--release", str(release),
                "--commit", self.commit,
                "--profile", "dev-py312",
            ],
            cwd=ROOT, check=False, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(static_check.returncode, 0, static_check.stderr)
        self.assertEqual(list(release.rglob("__pycache__")), [])
        self.assertEqual(list(release.rglob("*.pyc")), [])
        journal = system_root / "var/lib/gonken-agent/install/activation.record"
        self.assertIn("phase=post_verified", journal.read_text(encoding="utf-8"))
        for item in [release, *release.rglob("*")]:
            if not item.is_symlink():
                self.assertEqual(stat.S_IMODE(item.stat().st_mode) & 0o222, 0)
        return release_root, release

    def test_release_only_builds_activates_and_freezes_release(self) -> None:
        self.assert_release_only_complete(self.root / "system-success-build")

    def test_release_only_repeat_is_idempotent(self) -> None:
        system_root = self.root / "system-success-repeat"
        _release_root, release = self.assert_release_only_complete(system_root)
        manifest_before = (release / "release.record").read_bytes()
        second = self.run_install(system_root, "--release-only")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((release / "release.record").read_bytes(), manifest_before)

    def test_same_commit_repeat_ignores_standard_runtime_cache_without_repairing_release(self) -> None:
        system_root = self.root / "system-success-runtime-cache-repeat"
        _release_root, release = self.assert_release_only_complete(system_root)
        maintenance = release / "maintenance"
        maintenance.chmod(0o755)
        cache = maintenance / "__pycache__"
        cache.mkdir()
        (cache / "release_manager.cpython-313.pyc").write_bytes(b"derived-cache")
        cache.chmod(0o755)
        (cache / "release_manager.cpython-313.pyc").chmod(0o644)
        maintenance.chmod(0o555)
        second = self.run_install(system_root, "--release-only")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("code=INSTALL_STEP_SATISFIED step=immutable_release", second.stdout)
        self.assertTrue(cache.exists(), "runtime cache is outside immutable authority and is not repaired in-place")
        static_check = subprocess.run(
            [sys.executable, str(MANAGER), "validate-static", "--release", str(release),
             "--commit", self.commit, "--profile", "dev-py312"],
            cwd=ROOT, check=False, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(static_check.returncode, 0, static_check.stderr)

    def test_default_install_after_release_boundary_stops_before_target_only_steps(self) -> None:
        system_root = self.root / "system-success-default-boundary"
        self.assert_release_only_complete(system_root)
        default = self.run_install(system_root)
        self.assertEqual(default.returncode, 69)
        self.assertIn("code=M3_4_TARGET_REQUIRED", default.stderr)

    def test_low_space_never_creates_or_switches_release(self) -> None:
        system_root = self.root / "system-low-space"
        result = self.run_install(
            system_root,
            "--release-only",
            environment={
                "GONKEN_ENABLE_TEST_FAILURES": "1",
                "GONKEN_RELEASE_TEST_FREE_KIB": "1",
            },
        )
        self.assertEqual(result.returncode, 78, result.stderr)
        release_root = system_root / "usr/local/lib/gonken-agent"
        self.assertFalse((release_root / "current").exists())
        self.assertEqual(list((release_root / "releases").glob("[0-9a-f]" * 40)), [])


class TargetBridgeUpgradeCompatibilityTests(unittest.TestCase):
    def test_process_activation_migrates_from_post_verified_pre_bridge_target_release(self) -> None:
        """Exact checkpoint-29 target failure: reconcile old active, then activate bridge release."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release-root"
            state_root = root / "state-root"
            state_root.mkdir()
            previous = "3" * 40
            candidate = "4" * 40
            create_fake_release(
                release_root,
                previous,
                profile="core-pi-trixie-py313",
                binding_bridge=False,
            )
            create_fake_release(
                release_root,
                candidate,
                profile="core-pi-trixie-py313",
                binding_bridge=True,
            )
            point_current(release_root, previous)
            (state_root / "activation.record").write_text(
                activation_record(previous, "none", "post_verified"),
                encoding="utf-8",
            )
            (state_root / "activation.record").chmod(0o600)

            result = subprocess.run(
                [
                    sys.executable,
                    str(MANAGER),
                    "activate",
                    "--release-root",
                    str(release_root),
                    "--state-root",
                    str(state_root),
                    "--service-user",
                    current_user(),
                    "--commit",
                    candidate,
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("policy=structural_current_only", result.stdout)
            self.assertNotIn("RELEASE_LEGACY_TRANSITION_SOURCE", result.stdout)
            self.assertIn("code=ACTIVATION_COMPLETE", result.stdout)
            self.assertEqual(os.readlink(release_root / "current"), f"releases/{candidate}")
            journal = (state_root / "activation.record").read_text(encoding="utf-8")
            self.assertIn("phase=post_verified", journal)
            self.assertIn(f"candidate_commit={candidate}", journal)
            self.assertIn(f"previous_commit={previous}", journal)

    def test_process_activation_does_not_execute_or_revalidate_previous_current_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release-root"
            state_root = root / "state-root"
            state_root.mkdir()
            previous = "5" * 40
            candidate = "6" * 40
            create_fake_release(release_root, previous)
            create_fake_release(release_root, candidate)
            # Corrupt the previous payload after it was historically accepted.
            previous_cli = release_root / "releases" / previous / ".venv/bin/gonken-agent"
            previous_cli.chmod(0o755)
            previous_cli.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
            previous_cli.chmod(0o555)
            point_current(release_root, previous)
            (state_root / "activation.record").write_text(
                activation_record(previous, "none", "post_verified"), encoding="utf-8"
            )
            (state_root / "activation.record").chmod(0o600)

            result = subprocess.run(
                [
                    sys.executable, str(MANAGER), "activate",
                    "--release-root", str(release_root),
                    "--state-root", str(state_root),
                    "--service-user", current_user(),
                    "--commit", candidate,
                ],
                cwd=ROOT, check=False, capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("policy=structural_current_only", result.stdout)
            self.assertIn("code=ACTIVATION_COMPLETE", result.stdout)
            self.assertEqual(os.readlink(release_root / "current"), f"releases/{candidate}")

    def test_process_activation_does_not_fail_after_success_when_older_stale_release_is_pre_bridge(self) -> None:
        """Reproduce checkpoint-30 Pi: stale legacy A, active legacy B, new strict C."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release-root"
            state_root = root / "state-root"
            state_root.mkdir()
            stale, previous, candidate = ("2" * 40, "3" * 40, "4" * 40)
            create_fake_release(release_root, stale, profile="core-pi-trixie-py313", binding_bridge=False)
            create_fake_release(release_root, previous, profile="core-pi-trixie-py313", binding_bridge=False)
            create_fake_release(release_root, candidate, profile="core-pi-trixie-py313", binding_bridge=True)
            point_current(release_root, previous)
            (state_root / "activation.record").write_text(
                activation_record(previous, stale, "post_verified"), encoding="utf-8"
            )
            (state_root / "activation.record").chmod(0o600)

            result = subprocess.run(
                [
                    sys.executable, str(MANAGER), "activate",
                    "--release-root", str(release_root),
                    "--state-root", str(state_root),
                    "--service-user", current_user(),
                    "--commit", candidate,
                ],
                cwd=ROOT, check=False, capture_output=True, text=True, timeout=20,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("code=ACTIVATION_COMPLETE", result.stdout)
            self.assertIn(f"code=RELEASE_PRUNED commit={stale}", result.stdout)
            self.assertEqual(os.readlink(release_root / "current"), f"releases/{candidate}")
            self.assertFalse((release_root / "releases" / stale).exists())
            self.assertTrue((release_root / "releases" / previous).exists())
            self.assertTrue((release_root / "releases" / candidate).exists())


class ActivationInterruptionTests(unittest.TestCase):
    def prepare(self, root: Path, *, failing_candidate: bool = False) -> tuple[Path, Path]:
        release_root = root / "release-root"
        state_root = root / "state-root"
        (release_root / "releases").mkdir(parents=True)
        state_root.mkdir()
        create_fake_release(release_root, PREVIOUS)
        create_fake_release(
            release_root,
            CANDIDATE,
            fail_after_calls=3 if failing_candidate else None,
        )
        point_current(release_root, PREVIOUS)
        (state_root / "activation.record").write_text(
            activation_record(PREVIOUS, "none", "post_verified"),
            encoding="utf-8",
        )
        (state_root / "activation.record").chmod(0o600)
        return release_root, state_root

    def run_activate(
        self,
        release_root: Path,
        state_root: Path,
        *,
        interrupt: str | None = None,
        mode: str = "term",
        extra_environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = (
            "python3 \"$MANAGER\" activate "
            "--release-root \"$RELEASE_ROOT\" --state-root \"$STATE_ROOT\" "
            "--service-user \"$SERVICE_USER\" --commit \"$COMMIT\"; "
            "result=$?; exit $result"
        )
        environment = os.environ.copy()
        environment.update(
            {
                "MANAGER": str(MANAGER),
                "RELEASE_ROOT": str(release_root),
                "STATE_ROOT": str(state_root),
                "SERVICE_USER": current_user(),
                "COMMIT": CANDIDATE,
            }
        )
        if interrupt:
            environment.update(
                {
                    "GONKEN_ENABLE_TEST_FAILURES": "1",
                    "GONKEN_RELEASE_TEST_INTERRUPT": interrupt,
                    "GONKEN_RELEASE_TEST_INTERRUPT_MODE": mode,
                }
            )
        if extra_environment:
            environment.update(extra_environment)
        return subprocess.run(
            ["bash", "-c", command],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def assert_activated(self, release_root: Path, state_root: Path) -> None:
        result = self.run_activate(release_root, state_root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(release_root / "current"), f"releases/{CANDIDATE}")
        journal = (state_root / "activation.record").read_text(encoding="utf-8")
        self.assertIn("phase=post_verified", journal)
        self.assertIn(f"candidate_commit={CANDIDATE}", journal)

    def test_every_journal_switch_and_postcheck_boundary_reconciles(self) -> None:
        operations = ("journal_replace", "current_switch")
        for operation in operations:
            for point in ("before", "during", "after"):
                with self.subTest(operation=operation, point=point), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    release_root, state_root = self.prepare(root)
                    interrupted = self.run_activate(
                        release_root,
                        state_root,
                        interrupt=f"{operation}:{point}",
                    )
                    self.assertIn(interrupted.returncode, (-15, 143))
                    self.assert_activated(release_root, state_root)
                    self.assertEqual(list(state_root.glob(".journal.*")), [])
                    self.assertEqual(list(release_root.glob(".current.*")), [])

    def test_tampered_candidate_is_rejected_before_switching_current(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root, state_root = self.prepare(root)
            candidate = release_root / "releases" / CANDIDATE
            cli = candidate / ".venv/bin/gonken-agent"
            cli.chmod(0o755)
            cli.write_text("#!/bin/sh\nexit 42\n", encoding="utf-8")
            cli.chmod(0o555)
            result = self.run_activate(release_root, state_root)
            self.assertEqual(result.returncode, 74, result.stderr)
            self.assertIn("RELEASE_INVALID", result.stderr)
            self.assertEqual(os.readlink(release_root / "current"), f"releases/{PREVIOUS}")
            journal = (state_root / "activation.record").read_text(encoding="utf-8")
            self.assertIn("phase=post_verified", journal)
            self.assertIn(f"candidate_commit={PREVIOUS}", journal)

    def test_operator_rollback_script_restarts_service_after_validated_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root, state_root = self.prepare(root)
            self.assert_activated(release_root, state_root)
            systemctl_log = root / "systemctl.log"
            systemctl = root / "systemctl"
            systemctl.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$GONKEN_FAKE_SYSTEMCTL_LOG\"\nexit 0\n",
                encoding="utf-8",
            )
            systemctl.chmod(0o755)
            environment = os.environ.copy()
            environment["GONKEN_FAKE_SYSTEMCTL_LOG"] = str(systemctl_log)
            result = subprocess.run(
                [
                    str(ROLLBACK),
                    "--release-root",
                    str(release_root),
                    "--state-root",
                    str(state_root),
                    "--service-user",
                    current_user(),
                    "--systemctl",
                    str(systemctl),
                ],
                cwd=ROOT,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("code=ROLLBACK_COMPLETE", result.stdout)
            self.assertEqual(os.readlink(release_root / "current"), f"releases/{PREVIOUS}")
            self.assertEqual(
                systemctl_log.read_text(encoding="utf-8").strip(),
                "restart gonken-agent.service",
            )


class FinalizationInterruptionTests(unittest.TestCase):
    def run_finalize(self, candidate: Path, final: Path, interrupt: str | None = None) -> subprocess.CompletedProcess[str]:
        script = (
            "import importlib.util, os; "
            "spec=importlib.util.spec_from_file_location('rm', os.environ['MANAGER']); "
            "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
            "m.finalize_candidate(__import__('pathlib').Path(os.environ['CANDIDATE']), __import__('pathlib').Path(os.environ['FINAL']))"
        )
        environment = os.environ.copy()
        environment.update({"MANAGER": str(MANAGER), "CANDIDATE": str(candidate), "FINAL": str(final)})
        if interrupt:
            environment.update(
                {
                    "GONKEN_ENABLE_TEST_FAILURES": "1",
                    "GONKEN_RELEASE_TEST_INTERRUPT": interrupt,
                    "GONKEN_RELEASE_TEST_INTERRUPT_MODE": "term",
                }
            )
        command = "python3 -c \"$SCRIPT\"; result=$?; exit $result"
        environment["SCRIPT"] = script
        return subprocess.run(
            ["bash", "-c", command], env=environment, check=False, capture_output=True, text=True, timeout=10
        )

    def test_candidate_finalize_boundaries_leave_recoverable_old_or_new_state(self) -> None:
        for point in ("before", "during", "after"):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as temporary:
                releases = Path(temporary) / "releases"
                workspace = releases / f".candidate.{'a' * 40}.fixture"
                candidate = workspace / "release"
                candidate.mkdir(parents=True)
                (candidate / "marker").write_text("complete\n", encoding="utf-8")
                final = releases / ("a" * 40)
                interrupted = self.run_finalize(candidate, final, f"candidate_finalize:{point}")
                self.assertIn(interrupted.returncode, (-15, 143))
                if not final.exists():
                    resumed = self.run_finalize(candidate, final)
                    self.assertEqual(resumed.returncode, 0, resumed.stderr)
                self.assertEqual((final / "marker").read_text(encoding="utf-8"), "complete\n")
                self.assertEqual(stat.S_IMODE((final / "marker").stat().st_mode) & 0o222, 0)


if __name__ == "__main__":
    unittest.main()
