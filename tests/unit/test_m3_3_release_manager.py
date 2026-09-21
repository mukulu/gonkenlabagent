from __future__ import annotations

import importlib.util
import contextlib
import io
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.fixtures.release_fakes import create_fake_release, current_user, point_current


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "release_manager", ROOT / "scripts" / "release_manager.py"
)
assert SPEC and SPEC.loader
release_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_manager)


class RecordAndPointerTests(unittest.TestCase):
    def test_durable_record_is_private_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = root / "activation.record"
            release_manager.durable_record(
                record,
                {"format": "test-v1", "phase": "prepared"},
                "unit_record",
            )
            self.assertEqual(record.read_text(), "format=test-v1\nphase=prepared\n")
            self.assertEqual(stat.S_IMODE(record.stat().st_mode), 0o600)
            self.assertEqual(list(root.glob(".journal.*")), [])

    def test_parser_rejects_unknown_duplicate_and_incomplete_records(self) -> None:
        contents = (
            "format=test-v1\nphase=prepared\nunknown=x\n",
            "format=test-v1\nphase=prepared\nphase=again\n",
            "format=test-v1\n",
        )
        for content in contents:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "record"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(release_manager.ReleaseError):
                    release_manager.read_record(path, ("format", "phase"), "test-v1")

    def test_current_pointer_cannot_escape_release_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "current").symlink_to("../../etc/passwd")
            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.current_commit(root)
            self.assertEqual(raised.exception.code, "ACTIVATION_POINTER")

    def test_layout_has_private_state_and_constant_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = root / "usr/local/lib/gonken-agent"
            state = root / "var/lib/gonken-agent/install"
            binary = root / "usr/local/bin"
            release_manager.init_layout(release, state, binary)
            self.assertEqual(stat.S_IMODE(state.parent.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
            entrypoint = binary / "gonken-agent"
            self.assertTrue(entrypoint.is_symlink())
            self.assertEqual(
                (binary / os.readlink(entrypoint)).resolve(strict=False),
                (release / "current/.venv/bin/gonken-agent").resolve(strict=False),
            )

    def test_candidate_finalization_is_atomic_and_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            releases = Path(temporary) / "releases"
            releases.mkdir()
            workspace = releases / f".candidate.{'a' * 40}.fixture"
            candidate = workspace / "release"
            candidate.mkdir(parents=True)
            marker = candidate / "marker"
            marker.write_text("complete\n", encoding="utf-8")
            final = releases / ("a" * 40)
            release_manager.finalize_candidate(candidate, final)
            self.assertFalse(candidate.exists())
            self.assertEqual(marker.name, "marker")
            self.assertEqual((final / "marker").read_text(), "complete\n")
            self.assertEqual(stat.S_IMODE((final / "marker").stat().st_mode) & 0o222, 0)

    def test_finalization_normalizes_restrictive_umask_modes_for_service_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            releases = Path(temporary) / "releases"
            releases.mkdir()
            workspace = releases / f".candidate.{'d' * 40}.fixture"
            candidate = workspace / "release"
            bin_dir = candidate / ".venv/bin"
            bin_dir.mkdir(parents=True)
            executable = bin_dir / "gonken-agent"
            data = candidate / "module.py"
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            data.write_text("VALUE = 1\n", encoding="utf-8")
            # Reproduce the real-Pi failure modes created under leaked umask 077.
            candidate.chmod(0o700)
            (candidate / ".venv").chmod(0o700)
            bin_dir.chmod(0o700)
            executable.chmod(0o700)
            data.chmod(0o600)
            final = releases / ("d" * 40)
            release_manager.finalize_candidate(candidate, final)
            self.assertEqual(stat.S_IMODE((final / ".venv").stat().st_mode), 0o555)
            self.assertEqual(stat.S_IMODE((final / ".venv/bin").stat().st_mode), 0o555)
            self.assertEqual(stat.S_IMODE((final / ".venv/bin/gonken-agent").stat().st_mode), 0o555)
            self.assertEqual(stat.S_IMODE((final / "module.py").stat().st_mode), 0o444)

    def test_source_archive_rejects_traversal_and_links(self) -> None:
        cases = (("../escape", b"payload", False), ("link", b"", True))
        for name, payload, is_link in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "source.tar"
                with tarfile.open(archive, "w") as bundle:
                    member = tarfile.TarInfo(name)
                    if is_link:
                        member.type = tarfile.SYMTYPE
                        member.linkname = "target"
                        bundle.addfile(member)
                    else:
                        member.size = len(payload)
                        bundle.addfile(member, io.BytesIO(payload))
                with self.assertRaises(release_manager.ReleaseError) as raised:
                    release_manager._safe_extract(archive, root / "destination")
                self.assertEqual(raised.exception.code, "RELEASE_SOURCE")


class IntegrityAndPrivilegeTests(unittest.TestCase):
    def test_payload_digest_rejects_post_build_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release_root = Path(temporary)
            release = create_fake_release(release_root, "a" * 40)
            cli = release / ".venv/bin/gonken-agent"
            cli.chmod(0o755)
            cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            cli.chmod(0o555)
            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.validate_release(
                    release,
                    commit="a" * 40,
                    profile="dev-py312",
                    service_user=current_user(),
                )
            self.assertEqual(raised.exception.code, "RELEASE_INVALID")

    def test_payload_manifest_localizes_changed_and_unexpected_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release = Path(temporary) / "release"
            (release / "pkg").mkdir(parents=True)
            target = release / "pkg" / "module.py"
            target.write_text("VALUE = 1\n", encoding="utf-8")
            release_manager.write_payload_manifest(release)
            target.write_text("VALUE = 2\n", encoding="utf-8")
            extra = release / "unexpected.txt"
            extra.write_text("x\n", encoding="utf-8")
            differences = release_manager.payload_manifest_differences(release)
            self.assertIn("changed:pkg/module.py", differences)
            self.assertIn("unexpected:unexpected.txt", differences)

    def test_transient_python_caches_are_removed_before_sealing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release = Path(temporary) / "release"
            cache = release / "pkg" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "module.cpython-test.pyc").write_bytes(b"cache")
            (release / "standalone.pyc").write_bytes(b"cache")
            release_manager.purge_release_transients(release)
            self.assertFalse(cache.exists())
            self.assertFalse((release / "standalone.pyc").exists())

    def test_active_same_commit_ignores_only_standard_post_seal_python_cache_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release_root = Path(temporary) / "release-root"
            commit = "c" * 40
            release = create_fake_release(release_root, commit)
            # Upgrade the fixture to the production payload-manifest contract.
            for item in [release, *release.rglob("*")]:
                if not item.is_symlink():
                    item.chmod(stat.S_IMODE(item.stat().st_mode) | 0o200)
            (release / "share" / "gonken-agent").mkdir(parents=True, exist_ok=True)
            release_manager.write_payload_manifest(release)
            record = release_manager.read_record(
                release / "release.record",
                release_manager.RELEASE_FIELDS,
                "gonken-release-v1",
            )
            record["payload_sha256"] = release_manager.payload_sha256(release)
            release_manager.durable_record(release / "release.record", record, "test_release")
            release_manager.freeze_tree(release)
            point_current(release_root, commit)

            cache = release / "maintenance" / "__pycache__"
            # Simulate a privileged interpreter creating cache content after
            # sealing without requiring the unit test itself to run as root.
            (release / "maintenance").chmod(0o755)
            cache.mkdir()
            (cache / "runtime.cpython-313.pyc").write_bytes(b"derived-cache")
            release_manager.freeze_tree(release)

            recovered = release_manager.build_release(
                "file:///unused",
                commit,
                commit,
                release_root,
                "dev-py312",
                current_user(),
            )
            self.assertEqual(recovered, release)
            self.assertTrue(cache.exists(), "runtime cache must be outside authority, not repaired in-place")
            release_manager.validate_release_static(release, commit=commit, profile="dev-py312")

    def test_active_same_commit_never_repairs_authoritative_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release_root = Path(temporary) / "release-root"
            commit = "d" * 40
            release = create_fake_release(release_root, commit)
            for item in [release, *release.rglob("*")]:
                if not item.is_symlink():
                    item.chmod(stat.S_IMODE(item.stat().st_mode) | 0o200)
            (release / "share" / "gonken-agent").mkdir(parents=True, exist_ok=True)
            release_manager.write_payload_manifest(release)
            record = release_manager.read_record(
                release / "release.record",
                release_manager.RELEASE_FIELDS,
                "gonken-release-v1",
            )
            record["payload_sha256"] = release_manager.payload_sha256(release)
            release_manager.durable_record(release / "release.record", record, "test_release")
            release_manager.freeze_tree(release)
            point_current(release_root, commit)

            cli = release / ".venv" / "bin" / "gonken-agent"
            (release / ".venv" / "bin").chmod(0o755)
            cli.chmod(0o755)
            cli.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
            cache = release / "maintenance" / "__pycache__"
            (release / "maintenance").chmod(0o755)
            cache.mkdir()
            (cache / "helper.cpython-313.pyc").write_bytes(b"derived-cache")
            release_manager.freeze_tree(release)

            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.build_release(
                    "file:///unused",
                    commit,
                    commit,
                    release_root,
                    "dev-py312",
                    current_user(),
                )
            self.assertEqual(raised.exception.code, "RELEASE_ACTIVE_INVALID")
            self.assertTrue(cache.exists(), "mixed authoritative tampering must not be auto-repaired")

    def test_many_runtime_caches_cannot_hide_authoritative_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release_root = Path(temporary) / "release-root"
            commit = "e" * 40
            release = create_fake_release(release_root, commit)
            for item in [release, *release.rglob("*")]:
                if not item.is_symlink():
                    item.chmod(stat.S_IMODE(item.stat().st_mode) | 0o200)
            (release / "share" / "gonken-agent").mkdir(parents=True, exist_ok=True)
            release_manager.write_payload_manifest(release)
            record = release_manager.read_record(
                release / "release.record",
                release_manager.RELEASE_FIELDS,
                "gonken-release-v1",
            )
            record["payload_sha256"] = release_manager.payload_sha256(release)
            release_manager.durable_record(release / "release.record", record, "test_release")
            release_manager.freeze_tree(release)
            point_current(release_root, commit)

            # More cache differences than the ordinary diagnostic display limit
            # must never hide one authoritative executable change.
            maintenance = release / "maintenance"
            maintenance.chmod(0o755)
            for index in range(300):
                cache = maintenance / f"pkg{index:03d}" / "__pycache__"
                cache.mkdir(parents=True)
                (cache / "module.cpython-313.pyc").write_bytes(b"cache")
            cli = release / ".venv" / "bin" / "gonken-agent"
            (release / ".venv" / "bin").chmod(0o755)
            cli.chmod(0o755)
            cli.write_text("#!/bin/sh\nexit 42\n", encoding="utf-8")
            release_manager.freeze_tree(release)

            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.build_release(
                    "file:///unused", commit, commit, release_root, "dev-py312", current_user()
                )
            self.assertEqual(raised.exception.code, "RELEASE_ACTIVE_INVALID")
            self.assertTrue((maintenance / "pkg299" / "__pycache__").exists())

    def test_top_level_sourceless_bytecode_is_not_treated_as_runtime_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release_root = Path(temporary) / "release-root"
            commit = "f" * 40
            release = create_fake_release(release_root, commit)
            for item in [release, *release.rglob("*")]:
                if not item.is_symlink():
                    item.chmod(stat.S_IMODE(item.stat().st_mode) | 0o200)
            (release / "share" / "gonken-agent").mkdir(parents=True, exist_ok=True)
            release_manager.write_payload_manifest(release)
            record = release_manager.read_record(release / "release.record", release_manager.RELEASE_FIELDS, "gonken-release-v1")
            record["payload_sha256"] = release_manager.payload_sha256(release)
            release_manager.durable_record(release / "release.record", record, "test_release")
            release_manager.freeze_tree(release)
            point_current(release_root, commit)
            release.chmod(0o755)
            injected = release / "evil.pyc"
            injected.write_bytes(b"not-derived-cache")
            release_manager.freeze_tree(release)
            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.build_release("file:///unused", commit, commit, release_root, "dev-py312", current_user())
            self.assertEqual(raised.exception.code, "RELEASE_ACTIVE_INVALID")

    def test_pycache_symlink_is_authoritative_and_cannot_bypass_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release_root = Path(temporary) / "release-root"
            commit = "1" * 40
            release = create_fake_release(release_root, commit)
            for item in [release, *release.rglob("*")]:
                if not item.is_symlink():
                    item.chmod(stat.S_IMODE(item.stat().st_mode) | 0o200)
            (release / "share" / "gonken-agent").mkdir(parents=True, exist_ok=True)
            release_manager.write_payload_manifest(release)
            record = release_manager.read_record(release / "release.record", release_manager.RELEASE_FIELDS, "gonken-release-v1")
            record["payload_sha256"] = release_manager.payload_sha256(release)
            release_manager.durable_record(release / "release.record", record, "test_release")
            release_manager.freeze_tree(release)
            point_current(release_root, commit)
            maintenance = release / "maintenance"
            maintenance.chmod(0o755)
            (maintenance / "__pycache__").symlink_to("../share")
            release_manager.freeze_tree(release)
            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.build_release("file:///unused", commit, commit, release_root, "dev-py312", current_user())
            self.assertEqual(raised.exception.code, "RELEASE_ACTIVE_INVALID")

    def test_non_bytecode_file_inside_pycache_remains_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release_root = Path(temporary) / "release-root"
            commit = "2" * 40
            release = create_fake_release(release_root, commit)
            for item in [release, *release.rglob("*")]:
                if not item.is_symlink():
                    item.chmod(stat.S_IMODE(item.stat().st_mode) | 0o200)
            (release / "share" / "gonken-agent").mkdir(parents=True, exist_ok=True)
            release_manager.write_payload_manifest(release)
            record = release_manager.read_record(release / "release.record", release_manager.RELEASE_FIELDS, "gonken-release-v1")
            record["payload_sha256"] = release_manager.payload_sha256(release)
            release_manager.durable_record(release / "release.record", record, "test_release")
            release_manager.freeze_tree(release)
            point_current(release_root, commit)
            maintenance = release / "maintenance"
            maintenance.chmod(0o755)
            cache = maintenance / "__pycache__"
            cache.mkdir()
            (cache / "payload.txt").write_text("unexpected", encoding="utf-8")
            release_manager.freeze_tree(release)
            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.build_release("file:///unused", commit, commit, release_root, "dev-py312", current_user())
            self.assertEqual(raised.exception.code, "RELEASE_ACTIVE_INVALID")

    def test_post_verified_journal_cannot_override_pointer_disagreement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release"
            state_root = root / "state"
            state_root.mkdir()
            create_fake_release(release_root, "a" * 40)
            create_fake_release(release_root, "b" * 40)
            point_current(release_root, "a" * 40)
            release_manager.write_journal(
                state_root,
                "b" * 40,
                "a" * 40,
                "post_verified",
                "fixture",
            )
            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.reconcile(release_root, state_root, current_user())
            self.assertEqual(raised.exception.code, "ACTIVATION_AMBIGUOUS")
            self.assertEqual(release_manager.current_commit(release_root), "a" * 40)

    def test_target_privilege_and_nonlogin_account_contract_is_explicit(self) -> None:
        bootstrap = (ROOT / "bootstrap.sh").read_text(encoding="utf-8")
        installer = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
        self.assertIn('exec "${GONKEN_PRIVILEGE_PREFIX[@]}" --', bootstrap)
        self.assertIn('"$(id -u)" != "0"', installer)
        self.assertIn("groupadd --system gonken-agent", installer)
        self.assertIn("--shell /usr/sbin/nologin --no-create-home gonken-agent", installer)
        self.assertNotIn("sudoers", installer.lower())

    def test_speech_and_service_maintenance_inputs_are_release_payload_contract(self) -> None:
        manager = (ROOT / "scripts/release_manager.py").read_text(encoding="utf-8")
        installer = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
        for expected in (
            '"speech_manager.py"',
            '"install_summary.py"',
            '"service_manager.py"',
            '"environment_service_manager.py"',
            '"environment_profile_manager.py"',
            '"environment_readiness.py"',
            '"archive_qualifier.py"',
            '"target_probe.py"',
            '"i2c_manager.py"',
            '"sht31_diagnostic.py"',
            '"update.sh"',
            '"update_manager.py"',
            '"collect-support.sh"',
            '"gonken_agent" / "evidence.py"',
            '"rollback.sh"',
            '"uninstall.sh"',
            '"uninstall_manager.py"',
            '"speech-artifacts.toml"',
            '"gonken-agent.service"',
            '"gonken-environment.service"',
            '"packaging" / "tmpfiles" / "gonken-agent.conf"',
            '"packaging" / "tmpfiles" / "gonken-environment.conf"',
            '"piper-pi-trixie-py313.lock"',
        ):
            self.assertIn(expected, manager)
        self.assertIn("gonken_speech_manager", installer)
        self.assertIn("gonken_service_manager", installer)
        self.assertIn("gonken_environment_service_manager", installer)
        self.assertIn("target_i2c_platform", installer)
        self.assertIn("gonken_i2c_platform_postcondition", installer)
        self.assertIn("I2C_REBOOT_REQUIRED", installer)
        self.assertIn("environment_service", installer)
        self.assertIn("--speech-only", installer)
        self.assertIn("M3_5_SPEECH_COMPLETE", installer)
        self.assertIn("gonken_final_convergence", installer)
        self.assertIn("--require-ready", installer)
        self.assertIn("runtime_readiness.py", manager)
        self.assertIn("model_qualification.py", manager)
        self.assertIn("M6_2_SERVICE_COMPLETE", installer)
        self.assertNotIn("M3_6_UNAVAILABLE", installer)

    def test_maintenance_lock_rejects_concurrent_state_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release"
            state_root = root / "state"
            release_root.mkdir()
            with release_manager.maintenance_lock(state_root):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts/release_manager.py"),
                        "reconcile",
                        "--release-root",
                        str(release_root),
                        "--state-root",
                        str(state_root),
                        "--service-user",
                        current_user(),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            self.assertEqual(result.returncode, 75)
            self.assertIn("code=ACTIVATION_BUSY", result.stderr)

    def test_pruning_keeps_only_active_and_previous_validated_releases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release"
            state_root = root / "state"
            state_root.mkdir()
            oldest, previous, active = ("a" * 40, "b" * 40, "c" * 40)
            for commit in (oldest, previous, active):
                create_fake_release(release_root, commit)
            point_current(release_root, active)
            release_manager.write_journal(
                state_root,
                active,
                previous,
                "post_verified",
                "fixture",
            )
            release_manager.prune_releases(
                release_root,
                state_root,
                current_user(),
            )
            self.assertEqual(
                {path.name for path in (release_root / "releases").iterdir()},
                {active, previous},
            )


    def test_pruning_ignores_obsolete_runtime_contract_for_stale_pre_bridge_release(self) -> None:
        """Exact Pi shape: legacy stale + legacy previous + strict active must converge."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release"
            state_root = root / "state"
            state_root.mkdir()
            stale, previous, active = ("3" * 40, "8" * 40, "9" * 40)
            create_fake_release(release_root, stale, profile="core-pi-trixie-py313", binding_bridge=False)
            create_fake_release(release_root, previous, profile="core-pi-trixie-py313", binding_bridge=False)
            create_fake_release(release_root, active, profile="core-pi-trixie-py313", binding_bridge=True)
            point_current(release_root, active)
            release_manager.write_journal(state_root, active, previous, "post_verified", "fixture")

            release_manager.prune_releases(release_root, state_root, current_user())

            self.assertEqual(
                {path.name for path in (release_root / "releases").iterdir()},
                {active, previous},
            )

    def test_pruning_corrupt_stale_release_does_not_revalidate_historical_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release"
            state_root = root / "state"
            state_root.mkdir()
            stale, previous, active = ("2" * 40, "8" * 40, "9" * 40)
            for commit in (stale, previous, active):
                create_fake_release(release_root, commit)
            stale_record = release_root / "releases" / stale / "release.record"
            stale_record.chmod(0o644)
            stale_record.write_text(stale_record.read_text(encoding="utf-8") + "junk=1\n", encoding="utf-8")
            stale_record.chmod(0o444)
            point_current(release_root, active)
            release_manager.write_journal(state_root, active, previous, "post_verified", "fixture")

            release_manager.prune_releases(release_root, state_root, current_user())

            self.assertFalse((release_root / "releases" / stale).exists())
            self.assertEqual(release_manager.current_commit(release_root), active)

    def test_pruning_filesystem_error_is_nonblocking_after_successful_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release"
            state_root = root / "state"
            state_root.mkdir()
            stale, previous, active = ("4" * 40, "8" * 40, "9" * 40)
            for commit in (stale, previous, active):
                create_fake_release(release_root, commit)
            point_current(release_root, active)
            release_manager.write_journal(state_root, active, previous, "post_verified", "fixture")

            output = io.StringIO()
            original_remove = release_manager._remove_validated_release

            def fail_one(path, releases):
                if path.name == stale:
                    raise OSError("fixture")
                return original_remove(path, releases)

            with patch.object(release_manager, "_remove_validated_release", side_effect=fail_one), \
                 contextlib.redirect_stderr(output):
                release_manager.prune_releases(release_root, state_root, current_user())

            self.assertTrue((release_root / "releases" / stale).exists())
            self.assertIn("reason=FILESYSTEM_ERROR", output.getvalue())
            self.assertEqual(release_manager.current_commit(release_root), active)

    def test_explicit_rollback_returns_to_previous_validated_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release"
            state_root = root / "state"
            state_root.mkdir()
            previous, active = ("b" * 40, "c" * 40)
            for commit in (previous, active):
                create_fake_release(release_root, commit)
            point_current(release_root, active)
            release_manager.write_journal(
                state_root,
                active,
                previous,
                "post_verified",
                "fixture",
            )
            release_manager.rollback_previous(release_root, state_root, current_user())
            self.assertEqual(release_manager.current_commit(release_root), previous)
            journal = release_manager.read_journal(state_root)
            self.assertEqual(journal["phase"], "post_verified")
            self.assertEqual(journal["candidate_commit"], previous)
            self.assertEqual(journal["previous_commit"], active)
            # Status is also a state-bound operation and must remain usable after
            # a governed rollback to a genuine pre-bridge release.
            release_manager.status(
                release_root,
                state_root,
                previous,
                current_user(),
            )

    def test_explicit_rollback_fails_without_previous_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release"
            state_root = root / "state"
            state_root.mkdir()
            active = "c" * 40
            create_fake_release(release_root, active)
            point_current(release_root, active)
            release_manager.write_journal(
                state_root,
                active,
                "none",
                "post_verified",
                "fixture",
            )
            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.rollback_previous(release_root, state_root, current_user())
            self.assertEqual(raised.exception.code, "ROLLBACK_UNAVAILABLE")
            self.assertEqual(release_manager.current_commit(release_root), active)


class TargetRuntimeBindingTests(unittest.TestCase):
    def _release_with_fake_python(self, root: Path, *, system_site: bool, exit_code: int = 0, manifest: bool = True) -> Path:
        release = root / "release"
        binary = release / ".venv" / "bin"
        binary.mkdir(parents=True)
        (release / ".venv" / "pyvenv.cfg").write_text(
            f"include-system-site-packages = {'true' if system_site else 'false'}\n",
            encoding="utf-8",
        )
        site = release_manager._venv_site_packages(release)
        (site / "gpiod").mkdir(parents=True)
        gpiod = site / "gpiod" / "__init__.py"
        gpiod.write_text("# fixture\n", encoding="utf-8")
        if manifest:
            path = release / release_manager.BINDING_MANIFEST_RELATIVE
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "format": "gonken-hardware-binding-bridge-v1",
                "profile": "core-pi-trixie-py313",
                "source_root": "/usr/lib/python3/dist-packages",
                "system_site_packages": False,
                "packages": [
                    {
                        "package": "python3-libgpiod",
                        "version": "2.2.1-test",
                        "files": [{"path": "gpiod/__init__.py", "sha256": release_manager.sha256_file(gpiod)}],
                    },
                ],
            }
            path.write_text(__import__("json").dumps(payload), encoding="utf-8")
        python = binary / "python"
        python.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
        python.chmod(0o755)
        return release

    def test_target_profile_uses_allowlisted_distro_binding_bridge_only_for_pi_core(self) -> None:
        self.assertTrue(release_manager.profile_uses_distro_bindings("core-pi-trixie-py313"))
        self.assertFalse(release_manager.profile_uses_distro_bindings("dev-py312"))
        self.assertFalse(release_manager.profile_uses_distro_bindings("ui-dev-py312"))

    def test_target_binding_validation_rejects_broad_system_site_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release = self._release_with_fake_python(Path(temporary), system_site=True)
            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.validate_runtime_hardware_bindings(
                    release, "core-pi-trixie-py313", current_user()
                )
        self.assertEqual(raised.exception.code, "RELEASE_VENV_POLICY")

    def test_target_binding_validation_rejects_missing_bridge_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release = self._release_with_fake_python(Path(temporary), system_site=False, manifest=False)
            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.validate_runtime_hardware_bindings(
                    release, "core-pi-trixie-py313", current_user()
                )
        self.assertEqual(raised.exception.code, "RELEASE_BINDING_MANIFEST")

    def test_target_binding_validation_rejects_release_python_import_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release = self._release_with_fake_python(Path(temporary), system_site=False, exit_code=1)
            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.validate_runtime_hardware_bindings(
                    release, "core-pi-trixie-py313", current_user()
                )
        self.assertEqual(raised.exception.code, "RELEASE_HARDWARE_BINDINGS")

    def test_target_binding_validation_accepts_isolated_release_python_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release = self._release_with_fake_python(Path(temporary), system_site=False, exit_code=0)
            release_manager.validate_runtime_hardware_bindings(
                release, "core-pi-trixie-py313", current_user()
            )

    def test_binding_allowlist_excludes_distribution_metadata_and_unrelated_packages(self) -> None:
        self.assertTrue(release_manager._binding_relative_allowed("python3-libgpiod", Path("gpiod/__init__.py")))
        for package, path in (
            ("python3-libgpiod", Path("gpiod-2.2.0.dist-info/METADATA")),
            ("python3-libgpiod", Path("types_tensorflow-2.18.dist-info/METADATA")),
        ):
            with self.subTest(package=package, path=path):
                self.assertFalse(release_manager._binding_relative_allowed(package, path))

    def test_bridge_copies_only_allowlisted_import_payloads_and_records_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = root / "release"
            site = release_manager._venv_site_packages(release)
            site.mkdir(parents=True)
            (release / ".venv" / "pyvenv.cfg").write_text(
                "include-system-site-packages = false\n", encoding="utf-8"
            )
            distro = root / "dist-packages"
            gpiod_init = distro / "gpiod" / "__init__.py"
            gpiod_ext = distro / "gpiod" / "_ext.cpython-313-test.so"
            unrelated = distro / "types_tensorflow-2.18.dist-info" / "METADATA"
            for path, payload in (
                (gpiod_init, b"# gpiod fixture\n"),
                (gpiod_ext, b"gpiod-so"),
                (unrelated, b"Requires-Dist: numpy\n"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)

            def files(package: str, *, source_root: Path = distro):
                self.assertEqual(source_root, distro)
                return {
                    "python3-libgpiod": [gpiod_init, gpiod_ext],
                }[package]

            with patch.object(release_manager, "_distro_binding_files", side_effect=files), patch.object(
                release_manager, "_distro_package_version", side_effect=lambda package: {
                    "python3-libgpiod": "2.2.1-test",
                }[package]
            ):
                manifest = release_manager.install_target_distro_bindings(
                    release, "core-pi-trixie-py313", source_root=distro
                )

            self.assertIsNotNone(manifest)
            self.assertTrue((site / "gpiod" / "__init__.py").is_file())
            self.assertTrue((site / gpiod_ext.name.replace(gpiod_ext.name, "gpiod/_ext.cpython-313-test.so")).is_file())
            self.assertFalse((site / "types_tensorflow-2.18.dist-info" / "METADATA").exists())
            self.assertTrue(release_manager._binding_manifest_valid(release, "core-pi-trixie-py313"))

    def test_isolated_bridge_keeps_unrelated_broken_system_metadata_out_of_pip_check(self) -> None:
        import venv
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = root / "release"
            venv.EnvBuilder(with_pip=True, system_site_packages=False).create(release / ".venv")
            fake_system = root / "dist-packages"
            broken = fake_system / "types_tensorflow-2.18.dist-info"
            broken.mkdir(parents=True)
            (broken / "METADATA").write_text(
                "Metadata-Version: 2.1\nName: types-tensorflow\nVersion: 2.18.0\nRequires-Dist: numpy\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(release / ".venv/bin/python"), "-m", "pip", "check"],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("types-tensorflow", result.stdout + result.stderr)

    def test_binding_probe_covers_exact_runtime_apis(self) -> None:
        probe = release_manager.HARDWARE_BINDING_CHECK
        for required in (
            "gpiod", "gpiod.line", "Chip", "LineSettings",
            "request_lines", "get_info", "get_line_info",
            "Bias", "Direction", "Value",
        ):
            self.assertIn(required, probe)
        self.assertNotIn("smbus", probe)

    def test_installer_authorizes_invoking_operator_only_for_control_socket(self) -> None:
        installer = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
        self.assertIn('operator="${GONKEN_SOURCE_RECORD[invoking_user]}"', installer)
        self.assertIn('usermod -a -G gonken-envctl "$operator"', installer)
        self.assertNotIn('usermod -a -G gpio "$operator"', installer)
        self.assertNotIn('usermod -a -G i2c "$operator"', installer)
        self.assertIn('code=ENV_OPERATOR_SESSION_REFRESH', installer)
        self.assertIn('"target_runtime_bindings" "1"', installer)

    def test_upgrade_activation_accepts_only_state_bound_pre_bridge_current_release(self) -> None:
        """Reproduce the checkpoint-29 Pi failure and prove the migration fix."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release"
            state_root = root / "state"
            state_root.mkdir()
            previous = "8" * 40
            candidate = "9" * 40
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
            release_manager.write_journal(
                state_root,
                previous,
                "none",
                "post_verified",
                "pre-bridge-active-fixture",
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                release_manager.activate(
                    release_root,
                    state_root,
                    candidate,
                    current_user(),
                )

            self.assertEqual(release_manager.current_commit(release_root), candidate)
            journal = release_manager.read_journal(state_root)
            self.assertIsNotNone(journal)
            self.assertEqual(journal["phase"], "post_verified")
            self.assertEqual(journal["candidate_commit"], candidate)
            self.assertEqual(journal["previous_commit"], previous)
            self.assertIn("policy=structural_current_only", output.getvalue())
            self.assertNotIn("RELEASE_LEGACY_TRANSITION_SOURCE", output.getvalue())

    def test_normal_activation_still_rejects_unjournaled_pre_bridge_target_candidate(self) -> None:
        """Compatibility must not become a bypass for arbitrary legacy candidates."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release"
            state_root = root / "state"
            state_root.mkdir()
            candidate = "7" * 40
            create_fake_release(
                release_root,
                candidate,
                profile="core-pi-trixie-py313",
                binding_bridge=False,
            )
            with self.assertRaises(release_manager.ReleaseError) as raised:
                release_manager.activate(
                    release_root,
                    state_root,
                    candidate,
                    current_user(),
                )
            self.assertEqual(raised.exception.code, "RELEASE_BINDING_MANIFEST")
            self.assertIsNone(release_manager.current_commit(release_root))

    def test_operator_rollback_can_return_to_state_bound_pre_bridge_previous_release(self) -> None:
        """The same migration boundary must preserve governed rollback semantics."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_root = root / "release"
            state_root = root / "state"
            state_root.mkdir()
            previous = "6" * 40
            active = "5" * 40
            create_fake_release(
                release_root,
                previous,
                profile="core-pi-trixie-py313",
                binding_bridge=False,
            )
            create_fake_release(
                release_root,
                active,
                profile="core-pi-trixie-py313",
                binding_bridge=True,
            )
            point_current(release_root, active)
            release_manager.write_journal(
                state_root,
                active,
                previous,
                "post_verified",
                "bridge-active-with-legacy-previous",
            )

            release_manager.rollback_previous(release_root, state_root, current_user())

            self.assertEqual(release_manager.current_commit(release_root), previous)
            journal = release_manager.read_journal(state_root)
            self.assertIsNotNone(journal)
            self.assertEqual(journal["phase"], "post_verified")
            self.assertEqual(journal["candidate_commit"], previous)
            self.assertEqual(journal["previous_commit"], active)


if __name__ == "__main__":
    unittest.main()
