#!/usr/bin/env python3
"""Classify the installed boundary after M3.5 without claiming appliance readiness."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_CODE_RE = re.compile(r"^[A-Z0-9_]{1,64}$")

RELEASE_FIELDS = (
    "format", "commit", "profile", "python_version", "package_version",
    "lock_sha256", "wheel_sha256", "build_backend", "maintenance_sha256",
    "payload_sha256", "owner_uid", "payload_size_kib", "built_epoch",
    "validation",
)
OLLAMA_FIELDS = (
    "format", "ollama_version", "ollama_asset", "ollama_sha256",
    "binary_sha256", "unit_sha256", "dropin_sha256", "endpoint", "model",
    "model_digest", "model_digest_prefix", "quantization", "parameter_size",
    "context_tokens", "max_loaded_models", "num_parallel", "no_cloud",
    "pull_total_bytes", "smoke_total_ns", "smoke_eval_count",
    "validated_epoch", "validation",
)
SPEECH_FIELDS = (
    "format", "whisper_version", "whisper_binary_sha256",
    "whisper_model_sha256", "piper_version", "piper_lock_sha256",
    "piper_voice", "piper_voice_sha256", "piper_config_sha256",
    "tts_sample_rate", "tts_frames", "stt_required_tokens",
    "validated_epoch", "validation",
)


class SummaryError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, status: int = 1):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.status = status


def fail(code: str, message: str, remediation: str, status: int = 1) -> None:
    raise SummaryError(code, message, remediation, status)


def emit_error(error: SummaryError) -> None:
    print(f"[ERROR] code={error.code} message={error} remediation={error.remediation}", file=sys.stderr)


def require_absolute(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or "\n" in value or "\r" in value:
        fail("SUMMARY_PATH", f"{label} must be an absolute normalized path", "supply a safe absolute path", 64)
    return path


def mapped(root: Path, absolute: str) -> Path:
    return Path(absolute) if root == Path("/") else root / absolute.lstrip("/")


def read_record(path: Path, fields: tuple[str, ...], expected_format: str) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        fail("SUMMARY_RECORD", "required install record is missing or unsafe", "rerun the failed provisioning stage", 1)
    output: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        fail("SUMMARY_RECORD", f"cannot read install record: {exc}", "inspect installed state manually", 1)
    allowed = set(fields)
    for line in lines:
        if "=" not in line or "\r" in line:
            fail("SUMMARY_RECORD", "record contains a malformed line", "restore a verified install record", 1)
        key, value = line.split("=", 1)
        if key not in allowed or key in output or not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            fail("SUMMARY_RECORD", "record contains an unknown or duplicate field", "restore a verified install record", 1)
        if "\n" in value or "\r" in value:
            fail("SUMMARY_RECORD", "record contains an unsafe value", "restore a verified install record", 1)
        output[key] = value
    if set(output) != allowed or output.get("format") != expected_format:
        fail("SUMMARY_RECORD", "record schema is incomplete or unsupported", "restore the matching verified record", 1)
    if output.get("validation") != "passed":
        fail("SUMMARY_RECORD", "record validation did not pass", "rerun the failed provisioning stage", 1)
    return output


def private_record(path: Path) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        fail("SUMMARY_RECORD_MODE", "install record is not private", "repair record permissions and rerun", 1)


def validate_release(root: Path, commit: str) -> dict[str, str]:
    release_root = mapped(root, "/usr/local/lib/gonken-agent")
    current = release_root / "current"
    if not current.is_symlink() or os.readlink(current) != f"releases/{commit}":
        fail("SUMMARY_RELEASE", "active release pointer does not match the verified commit", "rerun release activation", 1)
    record = read_record(release_root / "releases" / commit / "release.record", RELEASE_FIELDS, "gonken-release-v1")
    if record["commit"] != commit or not COMMIT_RE.fullmatch(record["commit"]):
        fail("SUMMARY_RELEASE", "release record commit differs from the active commit", "rerun release activation", 1)
    for field in ("lock_sha256", "wheel_sha256", "maintenance_sha256", "payload_sha256"):
        if not SHA256_RE.fullmatch(record[field]):
            fail("SUMMARY_RELEASE", "release digest field is invalid", "rebuild the release", 1)
    return record


def validate_ollama(root: Path) -> dict[str, str]:
    record = read_record(mapped(root, "/var/lib/gonken-agent/install/ollama.record"), OLLAMA_FIELDS, "gonken-ollama-install-v1")
    private_record(mapped(root, "/var/lib/gonken-agent/install/ollama.record"))
    for field in ("ollama_sha256", "binary_sha256", "unit_sha256", "dropin_sha256", "model_digest"):
        if not SHA256_RE.fullmatch(record[field]):
            fail("SUMMARY_OLLAMA", "Ollama digest field is invalid", "rerun Ollama provisioning", 1)
    if record["no_cloud"] != "1" or record["max_loaded_models"] != "1" or record["num_parallel"] != "1":
        fail("SUMMARY_OLLAMA", "Ollama policy record differs from the offline contract", "rerun Ollama provisioning", 1)
    return record


def validate_speech(root: Path) -> dict[str, str]:
    record_path = mapped(root, "/var/lib/gonken-agent/install/speech.record")
    record = read_record(record_path, SPEECH_FIELDS, "gonken-speech-install-v1")
    private_record(record_path)
    for field in ("whisper_binary_sha256", "whisper_model_sha256", "piper_lock_sha256", "piper_voice_sha256", "piper_config_sha256"):
        if not SHA256_RE.fullmatch(record[field]):
            fail("SUMMARY_SPEECH", "speech digest field is invalid", "rerun speech provisioning", 1)
    if record["piper_voice"] != "en_US-ljspeech-medium":
        fail("SUMMARY_SPEECH", "speech voice record differs from accepted policy", "rerun speech provisioning", 1)
    return record



def validate_service(root: Path, commit: str) -> bool:
    release_root = mapped(root, "/usr/local/lib/gonken-agent")
    expected = release_root / "releases" / commit / "maintenance" / "packaging" / "systemd" / "gonken-agent.service"
    installed = mapped(root, "/etc/systemd/system/gonken-agent.service")
    if (
        not expected.is_file()
        or expected.is_symlink()
        or not installed.is_file()
        or installed.is_symlink()
    ):
        return False
    try:
        if installed.read_bytes() != expected.read_bytes():
            return False
    except OSError:
        return False
    if root != Path("/"):
        return True
    for command in (
        ["/usr/bin/systemctl", "is-enabled", "--quiet", "gonken-agent.service"],
        ["/usr/bin/systemctl", "is-active", "--quiet", "gonken-agent.service"],
    ):
        try:
            result = subprocess.run(command, check=False, capture_output=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return False
        if result.returncode != 0:
            return False
    return True

def component(name: str, status: str, code: str) -> dict[str, str]:
    if status not in {"READY", "DEGRADED", "FAILED"} or not SAFE_CODE_RE.fullmatch(code):
        fail("SUMMARY_COMPONENT", "invalid summary component", "repair the summary implementation", 70)
    return {"component": name, "status": status, "code": code}


def build_summary(root: Path, commit: str) -> dict[str, object]:
    release = validate_release(root, commit)
    ollama = validate_ollama(root)
    speech = validate_speech(root)
    service_ready = validate_service(root, commit)
    milestones = ["M3.3", "M3.4", "M3.5"]
    if service_ready:
        milestones.append("M6.2")
    return {
        "status": "DEGRADED",
        "ready": False,
        "code": "M3_6_INSTALL_SUMMARY",
        "completed_milestones": milestones,
        "active_commit": release["commit"],
        "release_profile": release["profile"],
        "ollama_model": ollama["model"],
        "ollama_digest": ollama["model_digest"],
        "whisper_version": speech["whisper_version"],
        "piper_version": speech["piper_version"],
        "piper_voice": speech["piper_voice"],
        "components": [
            component("release", "READY", "ACTIVE_RELEASE_VALIDATED"),
            component("ollama", "READY", "LOCAL_MODEL_VALIDATED"),
            component("speech_artifacts", "READY", "PINNED_SPEECH_SMOKE_VALIDATED"),
            component("app_service", "READY" if service_ready else "DEGRADED", "HEADLESS_SERVICE_VALIDATED" if service_ready else "HEADLESS_SERVICE_NOT_READY"),
            component("input_audio", "DEGRADED", "PHYSICAL_ACCEPTANCE_NOT_RUN"),
            component("output_audio", "DEGRADED", "PHYSICAL_ACCEPTANCE_NOT_RUN"),
            component("gpio", "DEGRADED", "PHYSICAL_ACCEPTANCE_NOT_RUN"),
        ],
        "next_action": "Run target audio, GPIO, reboot, thermal, and end-to-end acceptance before claiming appliance readiness.",
        "limitations": [
            "No Raspberry Pi hardware acceptance is implied by this summary.",
            "No microphone, speaker, GPIO, reboot, thermal, or end-to-end voice behavior is accepted yet.",
        ],
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--system-root", default="/")
    result.add_argument("--commit", required=True)
    result.add_argument("--json", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = require_absolute(args.system_root, "system root")
        if root != Path("/") and os.environ.get("GONKEN_ENABLE_TEST_FAILURES") != "1":
            fail("SUMMARY_TEST_GATE", "redirected roots require the explicit test gate", "use only in isolated tests", 77)
        if not COMMIT_RE.fullmatch(args.commit):
            fail("SUMMARY_COMMIT", "commit must be a full lowercase Git SHA", "use the bootstrap resolved commit", 64)
        summary = build_summary(root, args.commit)
        if args.json:
            print(json.dumps(summary, sort_keys=True))
        else:
            print(f"[OK] code={summary['code']} status={summary['status']} ready=false next=TARGET_ACCEPTANCE")
    except SummaryError as error:
        emit_error(error)
        return error.status
    except (OSError, ValueError) as error:
        emit_error(SummaryError("SUMMARY_IO", str(error), "inspect installed state manually", 1))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
