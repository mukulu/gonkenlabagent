from __future__ import annotations

import hashlib
import http.server
import json
import os
import shutil
import socketserver
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANAGER = ROOT / "scripts/ollama_manager.py"
UNIT = ROOT / "packaging/systemd/ollama.service"
DROPIN = ROOT / "packaging/systemd/ollama.service.d/gonken-agent.conf"
VERSION = "0.33.3"
MODEL = "qwen3.5:2b-q4_K_M"
PREFIX = "124a03c34777"
DIGEST = PREFIX + "a" * 52


class FakeState:
    installed = False
    digest = DIGEST


class ApiHandler(http.server.BaseHTTPRequestHandler):
    state: FakeState

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/version":
            self._json({"version": VERSION})
        elif self.path == "/api/tags":
            models = []
            if self.state.installed:
                models.append({
                    "name": MODEL,
                    "digest": self.state.digest,
                    "size": 1900000000,
                    "details": {"parameter_size": "2.27B", "quantization_level": "Q4_K_M"},
                })
            self._json({"models": models})
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/pull":
            assert request["model"] == MODEL
            assert request["stream"] is True
            self.state.installed = True
            lines = (
                json.dumps({"status": "downloading", "total": 1900000000}) + "\n"
                + json.dumps({"status": "success", "total": 1900000000}) + "\n"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Length", str(len(lines)))
            self.end_headers()
            self.wfile.write(lines)
        elif self.path == "/api/generate":
            assert request["stream"] is False
            assert request["options"]["temperature"] == 0
            assert request["options"]["num_ctx"] == 2048
            self._json({"response": "ready", "done": True, "total_duration": 1234, "eval_count": 1})
        else:
            self.send_error(404)


class ReusableServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class OllamaLifecycleFixture:
    def __init__(self, root: Path):
        self.root = root
        self.system_root = root / "system"
        self.system_root.mkdir()
        self.state = FakeState()
        handler = type("BoundApiHandler", (ApiHandler,), {"state": self.state})
        self.server = ReusableServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}"
        self.asset = root / "ollama-linux-arm64.tar.zst"
        payload = root / "payload"
        (payload / "bin").mkdir(parents=True)
        binary = payload / "bin/ollama"
        binary.write_text("#!/bin/sh\nprintf 'ollama version is 0.33.3\\n'\n", encoding="utf-8")
        binary.chmod(0o755)
        archive = root / "payload.tar"
        with tarfile.open(archive, "w") as bundle:
            bundle.add(payload / "bin", arcname="bin")
        subprocess.run(["/usr/bin/zstd", "-q", "-f", str(archive), "-o", str(self.asset)], check=True)
        self.manifest = root / "manifest.toml"
        self.write_manifest(hashlib.sha256(self.asset.read_bytes()).hexdigest())
        self.systemctl_log = root / "systemctl.log"
        self.systemctl = root / "systemctl"
        self.systemctl.write_text(
            "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$GONKEN_FAKE_SYSTEMCTL_LOG\"\nexit 0\n",
            encoding="utf-8",
        )
        self.systemctl.chmod(0o755)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def write_manifest(self, digest: str) -> None:
        self.manifest.write_text(
            "format = \"gonken-ollama-artifacts-v1\"\n"
            "verified_at = \"2026-09-09\"\n"
            "[ollama]\n"
            f"version = \"{VERSION}\"\nrelease_tag = \"v{VERSION}\"\n"
            "platform = \"linux-arm64\"\nasset = \"ollama-linux-arm64.tar.zst\"\n"
            f"url = \"{self.asset.as_uri()}\"\nsha256 = \"{digest}\"\n"
            "license = \"MIT\"\nsource = \"https://example.invalid/ollama\"\n"
            "[model]\n"
            f"tag = \"{MODEL}\"\ndigest_prefix = \"{PREFIX}\"\n"
            "quantization = \"Q4_K_M\"\nparameter_size = \"2.27B\"\n"
            "display_size = \"1.9GB\"\nlicense = \"Apache-2.0\"\n"
            "source = \"https://example.invalid/model\"\n",
            encoding="utf-8",
        )

    def command(self, action: str) -> list[str]:
        command = [
            sys.executable, str(MANAGER), action,
            "--manifest", str(self.manifest),
            "--system-root", str(self.system_root),
        ]
        if action == "install-binary":
            command += ["--zstd", "/usr/bin/zstd"]
        elif action not in {"binary-status"}:
            command += [
                "--endpoint", self.endpoint,
                "--context-tokens", "2048",
                "--unit-template", str(UNIT),
                "--dropin-template", str(DROPIN),
                "--systemctl", str(self.systemctl),
            ]
            if action in {"provision-model", "model-status"}:
                command += ["--model", MODEL]
        return command

    def run(self, action: str, *, interrupt: str | None = None) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update({
            "GONKEN_ENABLE_TEST_FAILURES": "1",
            "GONKEN_FAKE_SYSTEMCTL_LOG": str(self.systemctl_log),
        })
        if interrupt:
            environment["GONKEN_OLLAMA_TEST_INTERRUPT"] = interrupt
        if interrupt:
            quoted = " ".join(subprocess.list2cmdline([part]) for part in self.command(action))
            return subprocess.run(
                ["bash", "-c", f"{quoted}; result=$?; exit $result"],
                cwd=ROOT, env=environment, check=False, capture_output=True, text=True, timeout=20,
            )
        return subprocess.run(
            self.command(action), cwd=ROOT, env=environment, check=False,
            capture_output=True, text=True, timeout=20,
        )

    def binary(self) -> None:
        result = self.run("install-binary")
        if result.returncode != 0:
            raise AssertionError(result.stderr)

    def service(self) -> None:
        self.binary()
        result = self.run("install-service")
        if result.returncode != 0:
            raise AssertionError(result.stderr)


class OllamaLifecycleProcessTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        fixture = OllamaLifecycleFixture(Path(temporary.name))
        self.addCleanup(temporary.cleanup)
        self.addCleanup(fixture.close)
        return fixture

    def test_binary_service_model_repeat_and_status(self) -> None:
        fixture = self.fixture()
        fixture.service()
        first = fixture.run("provision-model")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn(f"digest={DIGEST}", first.stdout)
        record = fixture.system_root / "var/lib/gonken-agent/install/ollama.record"
        self.assertEqual(stat.S_IMODE(record.stat().st_mode), 0o600)
        before = record.read_text(encoding="utf-8")
        repeat = fixture.run("provision-model")
        self.assertEqual(repeat.returncode, 0, repeat.stderr)
        self.assertIn("pull_total_bytes=1900000000", before)
        self.assertEqual(fixture.run("binary-status").returncode, 0)
        self.assertEqual(fixture.run("service-status").returncode, 0)
        self.assertEqual(fixture.run("model-status").returncode, 0)
        self.assertIn("OLLAMA_NO_CLOUD=1", (fixture.system_root / "etc/systemd/system/ollama.service.d/gonken-agent.conf").read_text())
        self.assertIn("OLLAMA_NUM_PARALLEL=1", (fixture.system_root / "etc/systemd/system/ollama.service.d/gonken-agent.conf").read_text())

    def test_checksum_failure_never_creates_release(self) -> None:
        fixture = self.fixture()
        fixture.write_manifest("f" * 64)
        result = fixture.run("install-binary")
        self.assertEqual(result.returncode, 65, result.stderr)
        self.assertIn("code=OLLAMA_CHECKSUM", result.stderr)
        self.assertFalse((fixture.system_root / f"usr/local/lib/ollama/releases/v{VERSION}").exists())

    def test_service_file_conflict_is_not_overwritten(self) -> None:
        fixture = self.fixture()
        fixture.binary()
        unit = fixture.system_root / "etc/systemd/system/ollama.service"
        unit.parent.mkdir(parents=True)
        unit.write_text("administrator content\n", encoding="utf-8")
        result = fixture.run("install-service")
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertIn("code=OLLAMA_SERVICE_CONFLICT", result.stderr)
        self.assertEqual(unit.read_text(), "administrator content\n")

    def test_recorded_full_digest_drift_is_refused(self) -> None:
        fixture = self.fixture()
        fixture.service()
        self.assertEqual(fixture.run("provision-model").returncode, 0)
        fixture.state.digest = PREFIX + "b" * 52
        result = fixture.run("provision-model")
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertIn("code=OLLAMA_MODEL_DRIFT", result.stderr)

    def test_every_download_extract_readiness_pull_and_smoke_boundary_recovers(self) -> None:
        actions = {
            "binary_download": "install-binary",
            "binary_extract": "install-binary",
            "binary_finalize": "install-binary",
            "service_ready": "install-service",
            "model_pull": "provision-model",
            "model_smoke": "provision-model",
        }
        for operation, action in actions.items():
            for point in ("before", "during", "after"):
                with self.subTest(operation=operation, point=point):
                    fixture = self.fixture()
                    if operation == "service_ready":
                        fixture.binary()
                    elif operation in {"model_pull", "model_smoke"}:
                        fixture.service()
                    interrupted = fixture.run(action, interrupt=f"{operation}:{point}")
                    self.assertIn(interrupted.returncode, (-15, 143), interrupted.stderr)
                    resumed = fixture.run(action)
                    self.assertEqual(resumed.returncode, 0, resumed.stderr)
                    status = {
                        "install-binary": "binary-status",
                        "install-service": "service-status",
                        "provision-model": "model-status",
                    }[action]
                    self.assertEqual(fixture.run(status).returncode, 0)


if __name__ == "__main__":
    unittest.main()
