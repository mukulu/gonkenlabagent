from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "install-gonken.sh"
BOOTSTRAP = ROOT / "bootstrap.sh"
README = ROOT / "README.md"


class FirstInstallLauncherTests(unittest.TestCase):
    def test_launcher_help_is_non_mutating_and_documents_bootstrap_passthrough(self) -> None:
        result = subprocess.run(
            [str(LAUNCHER), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--bluetooth-audio", result.stdout)
        self.assertIn("--bluetooth-device", result.stdout)
        self.assertIn("~/gonkenlabagent", result.stdout)

    def test_standard_bootstrap_has_official_source_and_main_defaults(self) -> None:
        text = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn('SOURCE_URL="https://github.com/mukulu/gonkenlabagent.git"', text)
        self.assertIn('SOURCE_REF="main"', text)
        self.assertIn("Usage: ./bootstrap.sh [OPTIONS]", text)
        self.assertIn("--local-checkpoint", text)

    def test_readme_primary_install_is_one_command_and_manual_bootstrap_is_short(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn(
            "curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | bash",
            text,
        )
        self.assertIn("./bootstrap.sh", text)
        self.assertIn("--bluetooth-device AA:BB:CC:DD:EE:FF", text)

    def test_stream_launcher_prepares_checkout_and_forwards_bluetooth_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            stubs = root / "stubs"
            stubs.mkdir()
            log = root / "calls.log"
            bootstrap_log = root / "bootstrap.log"

            def executable(name: str, body: str) -> None:
                path = stubs / name
                path.write_text("#!/bin/bash\nset -Eeuo pipefail\n" + body, encoding="utf-8")
                path.chmod(path.stat().st_mode | stat.S_IXUSR)

            executable(
                "id",
                "if [[ \"${1:-}\" == '-u' ]]; then echo 1000; else /usr/bin/id \"$@\"; fi\n",
            )
            executable(
                "sudo",
                f"printf 'sudo %s\\n' \"$*\" >>{log!s}\n"
                "if [[ \"${1:-}\" == '-v' ]]; then exit 0; fi\n"
                "exec \"$@\"\n",
            )
            executable(
                "apt-get",
                f"printf 'apt-get %s\\n' \"$*\" >>{log!s}\nexit 0\n",
            )
            executable(
                "git",
                f"""
printf 'git %s\\n' "$*" >>{log!s}
if [[ "${{1:-}}" == 'clone' ]]; then
  dir="${{3}}"
  mkdir -p "$dir/.git"
  cat >"$dir/bootstrap.sh" <<'BOOT'
#!/bin/bash
printf '%s\n' "$@" >"$BOOTSTRAP_LOG"
exit 0
BOOT
  chmod +x "$dir/bootstrap.sh"
  exit 0
fi
if [[ "${{1:-}}" == '-C' && "${{3:-}}" == 'remote' && "${{4:-}}" == 'get-url' ]]; then
  printf '%s\\n' 'https://github.com/mukulu/gonkenlabagent.git'
  exit 0
fi
if [[ "${{1:-}}" == '-C' && "${{3:-}}" == 'status' ]]; then exit 0; fi
if [[ "${{1:-}}" == '-C' && "${{3:-}}" == 'fetch' ]]; then exit 0; fi
if [[ "${{1:-}}" == '-C' && "${{3:-}}" == 'rev-parse' ]]; then printf '%040d\\n' 1; exit 0; fi
if [[ "${{1:-}}" == 'ls-remote' ]]; then exit 0; fi
if [[ "${{1:-}}" == '-C' && "${{3:-}}" == 'checkout' ]]; then exit 0; fi
if [[ "${{1:-}}" == '-C' && "${{3:-}}" == 'branch' ]]; then exit 0; fi
exit 99
""",
            )

            environment = os.environ.copy()
            environment.update(
                {
                    "HOME": str(home),
                    "PATH": f"{stubs}:{environment['PATH']}",
                    "BOOTSTRAP_LOG": str(bootstrap_log),
                }
            )
            result = subprocess.run(
                [
                    str(LAUNCHER),
                    "--bluetooth-audio",
                    "--bluetooth-device",
                    "AA:BB:CC:DD:EE:FF",
                ],
                cwd=ROOT,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = log.read_text(encoding="utf-8")
            self.assertIn("apt-get update", calls)
            self.assertIn("apt-get install -y ca-certificates git python3", calls)
            self.assertIn("git clone https://github.com/mukulu/gonkenlabagent.git", calls)
            forwarded = bootstrap_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                forwarded,
                [
                    "--source-url",
                    "https://github.com/mukulu/gonkenlabagent.git",
                    "--ref",
                    "main",
                    "--bluetooth-audio",
                    "--bluetooth-device",
                    "AA:BB:CC:DD:EE:FF",
                ],
            )


if __name__ == "__main__":
    unittest.main()
