from __future__ import annotations

import os
import shlex
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "scripts" / "lib" / "common.sh"
SOURCE_URL = "https://github.com/mukulu/gonkenlabagent.git"


def run_common(
    body: str,
    *,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    script = f"set -Eeuo pipefail\nsource {shlex.quote(str(COMMON))}\n{body}\n"
    return subprocess.run(
        ["/bin/bash", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=10,
    )


def write_stub(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(f"#!/bin/bash\nset -Eeuo pipefail\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def git(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )


class PrivilegePreflightTests(unittest.TestCase):
    def test_direct_root_does_not_require_sudo(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stubs = Path(temporary)
            write_stub(stubs, "id", "[[ \"$*\" == '-u' ]] && echo 0")
            environment = {"PATH": str(stubs)}
            result = run_common(
                "gonken_establish_privilege\n"
                "printf '%s|%s|%s\\n' \"$GONKEN_INVOKING_USER\" "
                "\"$GONKEN_PRIVILEGE_MODE\" \"${#GONKEN_PRIVILEGE_PREFIX[@]}\"",
                environment=environment,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "root|direct-root|0")

    def test_root_invoked_through_sudo_records_original_user(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stubs = Path(temporary)
            write_stub(
                stubs,
                "id",
                "case \"$*\" in '-u') echo 0 ;; '-u -- pi') echo 1000 ;; *) exit 1 ;; esac",
            )
            environment = {"PATH": str(stubs), "SUDO_USER": "pi"}
            result = run_common(
                "gonken_establish_privilege\n"
                "printf '%s|%s\\n' \"$GONKEN_INVOKING_USER\" \"$GONKEN_PRIVILEGE_MODE\"",
                environment=environment,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "pi|sudo-root")

    def test_non_root_validates_sudo_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stubs = Path(temporary)
            log = stubs / "sudo.log"
            write_stub(
                stubs,
                "id",
                "case \"$*\" in '-u') echo 1000 ;; '-un') echo alice ;; *) exit 1 ;; esac",
            )
            write_stub(stubs, "sudo", "printf '%s\\n' \"$*\" >>\"$SUDO_LOG\"")
            environment = {
                "PATH": str(stubs),
                "SUDO_LOG": str(log),
            }
            result = run_common(
                "gonken_establish_privilege\n"
                "printf '%s|%s|%s\\n' \"$GONKEN_INVOKING_USER\" "
                "\"$GONKEN_PRIVILEGE_MODE\" \"${GONKEN_PRIVILEGE_PREFIX[*]}\"",
                environment=environment,
            )
            calls = log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "alice|validated-sudo|sudo -n")
        self.assertEqual(calls, ["-v"])

    def test_non_root_without_sudo_fails_diagnostically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stubs = Path(temporary)
            write_stub(
                stubs,
                "id",
                "case \"$*\" in '-u') echo 1000 ;; '-un') echo alice ;; *) exit 1 ;; esac",
            )
            result = run_common(
                "gonken_establish_privilege", environment={"PATH": str(stubs)}
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code=PREFLIGHT_SUDO", result.stderr)
        self.assertIn("sudo is unavailable", result.stderr)

    def test_non_root_with_rejected_sudo_fails_diagnostically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stubs = Path(temporary)
            write_stub(
                stubs,
                "id",
                "case \"$*\" in '-u') echo 1000 ;; '-un') echo alice ;; *) exit 1 ;; esac",
            )
            write_stub(stubs, "sudo", "exit 1")
            result = run_common(
                "gonken_establish_privilege", environment={"PATH": str(stubs)}
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code=PREFLIGHT_SUDO", result.stderr)
        self.assertIn("validation failed", result.stderr)


class PlatformAndResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.os_release = self.root / "os-release"
        self.os_release.write_text(
            'ID=debian\nVERSION_ID="13"\nVERSION_CODENAME=trixie\n'
            'BUILD_ID="2026-06-18"\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def target_command(self, *overrides: str) -> str:
        values = [
            str(self.os_release),
            "Linux",
            "aarch64",
            "64",
            "3.13.5",
            "systemd",
            "Raspberry Pi 5 Model B Rev 1.0",
            "Raspberry Pi reference 2026-06-18",
        ]
        for index, value in enumerate(overrides):
            if value:
                values[index] = value
        return "gonken_validate_target_platform " + " ".join(
            shlex.quote(value) for value in values
        )

    def test_exact_target_contract_passes(self) -> None:
        result = run_common(self.target_command())
        self.assertEqual(result.returncode, 0, result.stderr)

        self.os_release.write_text(
            'ID=raspbian\nID_LIKE=debian\nVERSION_ID="13"\n'
            'VERSION_CODENAME=trixie\n',
            encoding="utf-8",
        )
        result = run_common(self.target_command())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unsupported_os_arch_python_init_and_board_fail(self) -> None:
        cases = {
            "architecture": ("", "x86_64"),
            "python": ("", "", "", "", "3.12"),
            "init": ("", "", "", "", "", "busybox"),
            "board": ("", "", "", "", "", "", "Raspberry Pi 4 Model B"),
            "image": ("", "", "", "", "", "", "", "plain Debian image"),
        }
        for name, overrides in cases.items():
            with self.subTest(name=name):
                result = run_common(self.target_command(*overrides))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("code=PREFLIGHT_", result.stderr)

        self.os_release.write_text(
            "ID=ubuntu\nVERSION_ID=24.04\nVERSION_CODENAME=noble\n",
            encoding="utf-8",
        )
        result = run_common(self.target_command())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code=PREFLIGHT_PLATFORM", result.stderr)

    def test_development_contract_is_explicit_and_bounded(self) -> None:
        for version in ("3.12", "3.13"):
            result = run_common(
                f"gonken_validate_development_platform Linux x86_64 64 {version}.1"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        result = run_common(
            "gonken_validate_development_platform Darwin arm64 64 3.13"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PREFLIGHT_DEV_PLATFORM", result.stderr)

    def test_disk_ram_and_clock_fail_independently(self) -> None:
        passing = "gonken_validate_resources 9000000 4000000 1800000000 target"
        self.assertEqual(run_common(passing).returncode, 0)
        cases = {
            "PREFLIGHT_DISK": "gonken_validate_resources 8000000 4000000 1800000000 target",
            "PREFLIGHT_RAM": "gonken_validate_resources 9000000 3000000 1800000000 target",
            "PREFLIGHT_TIME": "gonken_validate_resources 9000000 4000000 1600000000 target",
        }
        for code, body in cases.items():
            with self.subTest(code=code):
                result = run_common(body)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"code={code}", result.stderr)

    def test_missing_required_command_is_reported(self) -> None:
        result = run_common("gonken_require_commands gonken-command-does-not-exist")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code=PREFLIGHT_COMMAND", result.stderr)
        self.assertIn("gonken-command-does-not-exist", result.stderr)


class SourceAndCheckoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_repository(self, origin: str = SOURCE_URL) -> Path:
        repository = self.root / f"repository-{len(list(self.root.iterdir()))}"
        repository.mkdir()
        git("init", "-q", cwd=repository)
        git("config", "user.name", "Test User", cwd=repository)
        git("config", "user.email", "test@example.invalid", cwd=repository)
        (repository / "tracked.txt").write_text("baseline\n", encoding="utf-8")
        git("add", "tracked.txt", cwd=repository)
        git("commit", "-q", "-m", "baseline", cwd=repository)
        git("remote", "add", "origin", origin, cwd=repository)
        return repository

    def test_source_request_rejects_credentials_unsafe_ref_and_target_file_url(self) -> None:
        cases = [
            "gonken_validate_source_request 'https://token@example.com/repo.git' main target",
            "gonken_validate_source_request 'https://example.com/repo.git' '../main' target",
            "gonken_validate_source_request 'file:///tmp/repo.git' main target",
        ]
        for body in cases:
            with self.subTest(body=body):
                result = run_common(body)
                self.assertNotEqual(result.returncode, 0)

    def test_target_local_checkpoint_requires_explicit_mode_and_full_commit(self) -> None:
        commit = "a" * 40
        accepted = run_common(
            f"gonken_validate_source_request 'file:///tmp/repo' {commit} target local-checkpoint"
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        for body in (
            "gonken_validate_source_request 'file:///tmp/repo' main target local-checkpoint",
            f"gonken_validate_source_request 'https://example.com/repo.git' {commit} target local-checkpoint",
        ):
            with self.subTest(body=body):
                rejected = run_common(body)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn("code=PREFLIGHT_SOURCE", rejected.stderr)

    def test_local_checkpoint_checkout_and_resolver_bind_exact_clean_head(self) -> None:
        repository = self.make_repository(origin="https://example.invalid/other.git")
        commit = git("rev-parse", "HEAD", cwd=repository).stdout.strip()
        accepted = run_common(
            "gonken_validate_existing_checkout "
            f"{shlex.quote(str(repository))} {shlex.quote(repository.as_uri())} local-checkpoint\n"
            f"gonken_resolve_local_checkpoint {shlex.quote(str(repository))} {commit}\n"
            "printf '%s\n' \"$GONKEN_RESOLVED_COMMIT\""
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(accepted.stdout.strip(), commit)

        wrong = run_common(
            f"gonken_resolve_local_checkpoint {shlex.quote(str(repository))} {'b' * 40}"
        )
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn("code=PREFLIGHT_REF", wrong.stderr)

        bad_source = run_common(
            "gonken_validate_existing_checkout "
            f"{shlex.quote(str(repository))} file:///tmp/not-this-checkout local-checkpoint"
        )
        self.assertNotEqual(bad_source.returncode, 0)
        self.assertIn("code=PREFLIGHT_CHECKOUT_ORIGIN", bad_source.stderr)

    def test_network_or_missing_ref_failure_is_structured(self) -> None:
        stubs = self.root / "stubs"
        stubs.mkdir()
        write_stub(stubs, "git", "exit 1")
        result = run_common(
            "gonken_resolve_remote_ref https://example.invalid/repo.git main",
            environment={"PATH": str(stubs)},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code=PREFLIGHT_NETWORK", result.stderr)

    def test_advertised_local_ref_resolves_to_exact_commit(self) -> None:
        repository = self.make_repository(origin=SOURCE_URL)
        expected = git("rev-parse", "HEAD", cwd=repository).stdout.strip()
        body = (
            "gonken_resolve_remote_ref "
            f"{shlex.quote(repository.as_uri())} master\n"
            "printf '%s\\n' \"$GONKEN_RESOLVED_COMMIT\""
        )
        result = run_common(body)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), expected)

    def test_different_branch_and_tag_with_same_name_are_ambiguous(self) -> None:
        repository = self.make_repository(origin=SOURCE_URL)
        git("tag", "master", cwd=repository)
        (repository / "tracked.txt").write_text("second commit\n", encoding="utf-8")
        git("commit", "-q", "-am", "second", cwd=repository)
        result = run_common(
            "gonken_resolve_remote_ref "
            f"{shlex.quote(repository.as_uri())} master"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code=PREFLIGHT_REF", result.stderr)
        self.assertIn("ambiguous", result.stderr)

    def test_clean_checkout_and_empty_or_absent_paths_pass(self) -> None:
        repository = self.make_repository()
        empty = self.root / "empty"
        empty.mkdir()
        absent = self.root / "absent"
        for path in (repository, empty, absent):
            with self.subTest(path=path.name):
                result = run_common(
                    "gonken_validate_existing_checkout "
                    f"{shlex.quote(str(path))} {shlex.quote(SOURCE_URL)}"
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_tracked_staged_and_untracked_changes_are_rejected(self) -> None:
        cases = ("tracked", "staged", "untracked")
        for case in cases:
            with self.subTest(case=case):
                repository = self.make_repository()
                if case == "tracked":
                    (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")
                elif case == "staged":
                    (repository / "staged.txt").write_text("staged\n", encoding="utf-8")
                    git("add", "staged.txt", cwd=repository)
                else:
                    (repository / "untracked.txt").write_text("untracked\n", encoding="utf-8")
                result = run_common(
                    "gonken_validate_existing_checkout "
                    f"{shlex.quote(str(repository))} {shlex.quote(SOURCE_URL)}"
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("code=PREFLIGHT_CHECKOUT_DIRTY", result.stderr)

    def test_unexpected_origin_and_non_git_contents_are_rejected(self) -> None:
        repository = self.make_repository("https://example.invalid/other.git")
        result = run_common(
            "gonken_validate_existing_checkout "
            f"{shlex.quote(str(repository))} {shlex.quote(SOURCE_URL)}"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code=PREFLIGHT_CHECKOUT_ORIGIN", result.stderr)

        non_git = self.root / "non-git"
        non_git.mkdir()
        (non_git / "data.txt").write_text("preserve me\n", encoding="utf-8")
        result = run_common(
            "gonken_validate_existing_checkout "
            f"{shlex.quote(str(non_git))} {shlex.quote(SOURCE_URL)}"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code=PREFLIGHT_CHECKOUT", result.stderr)
        self.assertEqual((non_git / "data.txt").read_text(encoding="utf-8"), "preserve me\n")

    def test_private_staging_records_source_and_observed_facts(self) -> None:
        parent = self.root / "staging"
        parent.mkdir()
        commit = "1" * 40
        body = (
            "gonken_create_staging "
            f"{shlex.quote(str(parent))} "
            "'format=gonken-bootstrap-source-v1' "
            f"{shlex.quote(f'source_url={SOURCE_URL}')} 'requested_ref=main' "
            f"'resolved_commit={commit}' 'platform_mode=development' "
            "'invoking_user=alice' 'architecture=x86_64' 'python_version=3.12.13'\n"
            "printf '%s\\n' \"$GONKEN_STAGING_DIR\""
        )
        result = run_common(body)
        self.assertEqual(result.returncode, 0, result.stderr)
        staging = Path(result.stdout.strip())
        manifest = staging / "source.record"
        self.assertEqual(stat.S_IMODE(staging.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(manifest.stat().st_mode), 0o600)
        content = manifest.read_text(encoding="utf-8")
        self.assertIn(f"source_url={SOURCE_URL}", content)
        self.assertIn(f"resolved_commit={commit}", content)
        self.assertIn("platform_mode=development", content)

    def test_private_staging_does_not_leak_umask(self) -> None:
        parent = self.root / "staging-umask"
        parent.mkdir()
        result = run_common(
            "umask 0022; before=$(umask); "
            f"gonken_create_staging {shlex.quote(str(parent))} format=test-v1; "
            "after=$(umask); printf '%s|%s\\n' \"$before\" \"$after\""
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        before, after = result.stdout.strip().split("|")
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
