from __future__ import annotations

import importlib.util
import io
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

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
            '"speech-artifacts.toml"',
            '"gonken-agent.service"',
            '"packaging" / "tmpfiles" / "gonken-agent.conf"',
            '"piper-pi-trixie-py313.lock"',
        ):
            self.assertIn(expected, manager)
        self.assertIn("gonken_speech_manager", installer)
        self.assertIn("gonken_service_manager", installer)
        self.assertIn("--speech-only", installer)
        self.assertIn("M3_5_SPEECH_COMPLETE", installer)
        self.assertIn("M3_6_INSTALL_SUMMARY", installer)
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


if __name__ == "__main__":
    unittest.main()
