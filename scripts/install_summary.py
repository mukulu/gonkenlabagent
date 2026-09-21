#!/usr/bin/env python3
"""Validate final installed release/runtime facts without claiming physical acceptance."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


_source = Path(__file__).resolve().parents[1] / 'src'
if _source.is_dir():
    sys.path.insert(0, str(_source))
try:
    from gonken_agent import runtime_readiness as rr
    from gonken_agent.llm.qualification import qualified_rows
except ModuleNotFoundError as exc:
    if not exc.name.startswith('gonken_agent'):
        raise
    import runtime_readiness as rr
    from model_qualification import qualified_rows


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

ROSTER_MODELS = ("qwen3:0.6b", "lfm2.5-thinking:1.2b", "qwen3.5:0.8b")
ROSTER_RECORD_FORMAT = "gonken-ollama-roster-record-v2"
SELECTION_FORMAT = "gonken-active-model-v1"


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

def read_bounded_json(path: Path, max_bytes: int = 256 * 1024) -> dict[str, object] | None:
    return rr.bounded_json(path, max_bytes)


def validate_model_roster(root: Path, legacy: dict[str, str]) -> dict[str, object]:
    selection_path = mapped(root, "/var/lib/gonken-agent/ollama/active-model.json")
    roster_path = mapped(root, "/var/lib/gonken-agent/ollama/roster.json")
    selection = read_bounded_json(selection_path, 4096)
    roster = read_bounded_json(roster_path)
    if selection is None and roster is None:
        return {
            "status": "LEGACY_FALLBACK", "active_model": legacy["model"],
            "active_digest": legacy["model_digest"], "models": [legacy["model"]],
            "generation": 0, "governed_roster_active": False,
        }
    if not selection or selection.get("format") != SELECTION_FORMAT:
        fail("SUMMARY_MODEL_SELECTION", "active model selection is missing or invalid", "rerun model roster provisioning", 1)
    model = selection.get("model")
    generation = selection.get("generation")
    if model not in ROSTER_MODELS or type(generation) is not int or generation < 1:
        fail("SUMMARY_MODEL_SELECTION", "active model selection is outside the governed roster", "rerun model roster provisioning", 1)
    if not roster or roster.get("format") != ROSTER_RECORD_FORMAT or roster.get("status") != "READY":
        fail("SUMMARY_MODEL_ROSTER", "validated roster record is missing or invalid", "rerun model roster provisioning", 1)
    rows = roster.get("models")
    if not isinstance(rows, list):
        fail("SUMMARY_MODEL_ROSTER", "roster record model list is invalid", "rerun model roster provisioning", 1)
    if len(rows) != len(ROSTER_MODELS) or any(not isinstance(row, dict) for row in rows):
        fail('SUMMARY_MODEL_ROSTER', 'roster membership is invalid', 'rerun model roster provisioning', 1)
    if any(not isinstance(row.get('tag'), str) for row in rows):
        fail('SUMMARY_MODEL_ROSTER', 'roster tags are invalid', 'rerun model roster provisioning', 1)
    by_tag = {row['tag']: row for row in rows}
    if set(by_tag) != set(ROSTER_MODELS):
        fail('SUMMARY_MODEL_ROSTER', 'roster must contain exactly the admitted models', 'rerun model roster provisioning', 1)
    inventory = [{'name': row['tag'], 'digest': row.get('digest')} for row in rows]
    verified = qualified_rows(roster, inventory, context_tokens=int(legacy['context_tokens']))
    if set(verified) != set(ROSTER_MODELS) or not all(row['tools'] for row in verified.values()):
        fail('SUMMARY_MODEL_QUALIFICATION', 'required roster stages are missing, stale or failed', 'rerun the bounded model qualification', 1)
    active_row = by_tag[model]
    digest = active_row.get("digest")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        fail("SUMMARY_MODEL_ROSTER", "active roster digest is invalid", "rerun model roster provisioning", 1)
    return {
        "status": "READY", "active_model": model, "active_digest": digest,
        "models": list(ROSTER_MODELS), "generation": generation,
        "governed_roster_active": True, "tool_call_smoke": active_row.get("tool_call_smoke"),
    }


def validate_appliance(root: Path, expected_commit: str | None = None,
                       expected_model: str | None = None, expected_digest: str | None = None) -> dict[str, object] | None:
    current = mapped(root, '/usr/local/lib/gonken-agent/current')
    commit, profile = rr.current_release_identity(current)
    if expected_commit is not None and commit != expected_commit:
        return None
    binding = rr.Binding(commit, profile, rr.current_boot_id(mapped(root, '/proc/sys/kernel/random/boot_id')))
    value = rr.read_ready(mapped(root, '/run/gonken-agent/ready.json'), binding=binding,
                          pending_path=mapped(root, '/run/gonken-agent/readiness.json'))
    if value is None or (expected_model is not None and value.get('model') != expected_model):
        return None
    if expected_digest is not None and value.get('model_digest') != expected_digest:
        return None
    return value


def component(name: str, status: str, code: str) -> dict[str, str]:
    if status not in {"READY", "DEGRADED", "FAILED"} or not SAFE_CODE_RE.fullmatch(code):
        fail("SUMMARY_COMPONENT", "invalid summary component", "repair the summary implementation", 70)
    return {"component": name, "status": status, "code": code}


def build_summary(root: Path, commit: str) -> dict[str, object]:
    release = validate_release(root, commit)
    ollama = validate_ollama(root)
    roster = validate_model_roster(root, ollama)
    speech = validate_speech(root)
    service_ready = validate_service(root, commit)
    appliance = validate_appliance(root, commit, str(roster["active_model"]), str(roster["active_digest"]))
    appliance_ready = service_ready and appliance is not None
    milestones = ["M3.3", "M3.4", "M3.5"]
    if service_ready:
        milestones.append("M6.2")
    return {
        "status": "READY" if appliance_ready else "DEGRADED",
        "ready": appliance_ready,
        "code": "M3_6_INSTALL_SUMMARY",
        "completed_milestones": milestones,
        "active_commit": release["commit"],
        "release_profile": release["profile"],
        "ollama_model": roster["active_model"],
        "ollama_digest": roster["active_digest"],
        "ollama_roster": roster,
        "whisper_version": speech["whisper_version"],
        "piper_version": speech["piper_version"],
        "piper_voice": speech["piper_voice"],
        "wake_phrase": appliance.get("wake_phrase") if appliance else None,
        "components": [
            component("release", "READY", "ACTIVE_RELEASE_VALIDATED"),
            component("ollama", "READY", "LOCAL_MODEL_VALIDATED"),
            component("ollama_roster", "READY" if roster["governed_roster_active"] else "DEGRADED", "THREE_MODEL_ROSTER_VALIDATED" if roster["governed_roster_active"] else "LEGACY_MODEL_FALLBACK"),
            component("llm_tool_broker", "READY" if appliance_ready and roster.get("tool_call_smoke") == "PASS" else "DEGRADED", "TYPED_TOOL_BROKER_READY" if appliance_ready and roster.get("tool_call_smoke") == "PASS" else "MODEL_TOOLS_NOT_QUALIFIED"),
            component("speech_artifacts", "READY", "PINNED_SPEECH_SMOKE_VALIDATED"),
            component("app_service", "READY" if service_ready else "DEGRADED", "HEADLESS_SERVICE_VALIDATED" if service_ready else "HEADLESS_SERVICE_NOT_READY"),
            component("input_audio", "READY" if appliance_ready else "DEGRADED", "PHYSICAL_INPUT_OPENED" if appliance_ready else "PHYSICAL_ACCEPTANCE_PENDING"),
            component("output_audio", "READY" if appliance_ready else "DEGRADED", "PHYSICAL_OUTPUT_OPENED" if appliance_ready else "PHYSICAL_ACCEPTANCE_PENDING"),
            component("wake_runtime", "READY" if appliance_ready else "DEGRADED", "WAKE_STANDBY_READY" if appliance_ready else "WAKE_RUNTIME_PENDING"),
            component("gpio", "READY", "OPTIONAL_NOT_REQUIRED_FOR_VOICE"),
        ],
        "next_action": "Say the configured wake phrase to begin." if appliance_ready else "Keep the configured audio device powered and rerun bootstrap.",
        "limitations": [
            "GPIO push-to-talk remains optional and requires separate physical acceptance.",
            "A READY state proves the service opened the configured audio path, warmed local inference, and played the ready announcement; a human-spoken wake turn and reboot cycle remain target acceptance evidence.",
            "Raspberry Pi 4 is not accepted by the Pi 5 production profile.",
        ],
    }



def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--system-root", default="/")
    result.add_argument("--commit", required=True)
    result.add_argument("--json", action="store_true")
    result.add_argument("--require-ready", action="store_true", help="nonzero unless fresh selected runtime and service facts are ready")
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
            label = "OK" if summary["ready"] else "DEGRADED"
            print(f"[{label}] code={summary['code']} status={summary['status']} ready={str(summary['ready']).lower()} next={'USE_ASSISTANT' if summary['ready'] else 'TARGET_ACCEPTANCE'}")
        if args.require_ready and not summary['ready']:
            return 75
    except SummaryError as error:
        emit_error(error)
        return error.status
    except (OSError, ValueError) as error:
        emit_error(SummaryError("SUMMARY_IO", str(error), "inspect installed state manually", 1))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
