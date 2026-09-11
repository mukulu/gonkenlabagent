from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "bootstrap.sh"
REAL_GIT = shutil.which("git")


def run(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )


class BootstrapProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.staging_parent = self.root / "staging"
        self.staging_parent.mkdir()
        self.empty_checkout = self.root / "empty-checkout"
        self.empty_checkout.mkdir()
        self.stubs = self.root / "stubs"
        self.stubs.mkdir()
        id_stub = self.stubs / "id"
        id_stub.write_text(
            "#!/bin/bash\nset -Eeuo pipefail\n"
            "case \"$*\" in\n"
            "  '-u'|'-u -- root') echo 0 ;;\n"
            "  '-un') echo root ;;\n"
            "  *) exit 1 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        id_stub.chmod(0o755)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_source(self) -> tuple[Path, str]:
        source = self.root / "source"
        source.mkdir()
        run("init", "-q", "--initial-branch=main", cwd=source)
        run("config", "user.name", "Test User", cwd=source)
        run("config", "user.email", "test@example.invalid", cwd=source)
        (source / "README.md").write_text("source\n", encoding="utf-8")
        run("add", "README.md", cwd=source)
        run("commit", "-q", "-m", "source", cwd=source)
        commit = run("rev-parse", "HEAD", cwd=source).stdout.strip()
        return source, commit

    def environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.pop("SUDO_USER", None)
        environment["PATH"] = f"{self.stubs}:{environment['PATH']}"
        return environment

    def command(self, source: Path, *extra: str) -> list[str]:
        return [
            str(BOOTSTRAP),
            "--development-host",
            "--source-url",
            source.as_uri(),
            "--ref",
            "main",
            "--existing-checkout",
            str(self.empty_checkout),
            "--staging-parent",
            str(self.staging_parent),
            *extra,
        ]

    def test_development_preflight_process_writes_exact_private_manifest(self) -> None:
        source, expected_commit = self.make_source()
        result = subprocess.run(
            self.command(source, "--preflight-only"),
            cwd=ROOT,
            env=self.environment(),
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        match = re.search(r"staging=([^\n]+)", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        staging = Path(match.group(1))
        manifest = staging / "source.record"
        self.assertEqual(stat.S_IMODE(staging.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(manifest.stat().st_mode), 0o600)
        content = manifest.read_text(encoding="utf-8")
        self.assertIn(f"resolved_commit={expected_commit}", content)
        self.assertIn("platform_mode=development", content)
        self.assertIn("rpi_image_reference=not-applicable", content)
        self.assertIn("bluetooth_audio=disabled", content)
        self.assertIn("bluetooth_device=", content)
        self.assertNotIn("M3_2_UNAVAILABLE", result.stderr)

    def test_bluetooth_audio_is_target_only_and_does_not_mutate_development_staging(self) -> None:
        source, _commit = self.make_source()
        result = subprocess.run(
            self.command(source, "--bluetooth-audio", "--preflight-only"),
            cwd=ROOT,
            env=self.environment(),
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 64)
        self.assertIn("code=PREFLIGHT_BLUETOOTH", result.stderr)
        self.assertEqual(list(self.staging_parent.iterdir()), [])

    def test_default_routes_to_release_manager_and_never_legacy_setup(self) -> None:
        source, expected_commit = self.make_source()
        result = subprocess.run(
            self.command(source),
            cwd=ROOT,
            env=self.environment(),
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code=RELEASE_", result.stderr)
        self.assertNotIn("M3_2_UNAVAILABLE", result.stderr)
        self.assertIn(f"source_commit={expected_commit}", result.stdout)
        self.assertNotIn("Starting full GonKenLab Agent setup", result.stdout)
        match = re.search(r"staging=([^\n]+)", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        state = (
            Path(match.group(1))
            / "development-root/var/lib/gonken-agent/install/engine"
        )
        self.assertTrue((state / "steps" / "engine_contract.record").is_file())
        self.assertFalse((state / "engine.lock").exists())

    def test_unsupported_target_fails_before_network_or_staging(self) -> None:
        self.assertIsNotNone(REAL_GIT)
        network_log = self.root / "network.log"
        git_stub = self.stubs / "git"
        git_stub.write_text(
            "#!/bin/bash\n"
            "set -Eeuo pipefail\n"
            "if [[ \"${1:-}\" == 'ls-remote' ]]; then\n"
            "  printf 'called\\n' >>\"$NETWORK_LOG\"\n"
            "  exit 99\n"
            "fi\n"
            f"exec {REAL_GIT} \"$@\"\n",
            encoding="utf-8",
        )
        git_stub.chmod(0o755)
        environment = self.environment()
        environment["NETWORK_LOG"] = str(network_log)
        result = subprocess.run(
            [
                str(BOOTSTRAP),
                "--preflight-only",
                "--source-url",
                "https://example.invalid/repository.git",
                "--ref",
                "main",
                "--existing-checkout",
                str(self.empty_checkout),
                "--staging-parent",
                str(self.staging_parent),
            ],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 78)
        self.assertRegex(
            result.stderr,
            r"code=PREFLIGHT_(?:PLATFORM|ARCH|HARDWARE|IMAGE|INIT)",
        )
        self.assertFalse(network_log.exists())
        self.assertEqual(list(self.staging_parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
