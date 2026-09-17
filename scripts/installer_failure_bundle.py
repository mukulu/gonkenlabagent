#!/usr/bin/env python3
"""Create a private, content-free support bundle for installer failures.

This helper is source-package owned so it remains usable when a new immutable
candidate fails before activation.  It exports only allow-listed metadata and
structured installer/preflight records; raw stdout/stderr, credentials, user
content, audio, prompts and model data are never copied.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

SAFE_CODE = re.compile(r"^[A-Z0-9_]{1,64}$")
SAFE_STEP = re.compile(r"^(?:[a-z0-9_.-]{1,64}|none)$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
FORMAT = "gonken-installer-failure-bundle-v1"
TARGET_MANIFEST_FORMAT = "gonken-target-hardware-manifest-v1"
SERVICE_UNITS = (
    "gonken-agent.service",
    "gonken-environment.service",
    "ollama.service",
    "bluetooth.service",
    "gonken-bluetooth-autoconnect.service",
)


def clean(value: object, limit: int = 240) -> str:
    return " ".join(str(value).replace("\x00", "").replace("\r", " ").replace("\n", " ").split())[:limit]


def parse_kv(path: Path, *, max_bytes: int = 16384) -> dict[str, str] | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
            return None
        result: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if not sep or key in result or "\x00" in value:
                return None
            result[key] = value
        return result
    except (OSError, UnicodeError):
        return None


def safe_source(path: Path) -> dict[str, object]:
    fields = parse_kv(path) or {}
    commit = fields.get("resolved_commit", "")
    return {
        "format": fields.get("format") if fields.get("format") == "gonken-bootstrap-source-v1" else None,
        "resolved_commit": commit if COMMIT.fullmatch(commit) else None,
        "platform_mode": fields.get("platform_mode") if fields.get("platform_mode") in {"target", "development"} else None,
        "source_mode": fields.get("source_mode") if fields.get("source_mode") in {"remote", "local-checkpoint"} else None,
        "architecture": fields.get("architecture", "")[:64],
        "kernel_name": fields.get("kernel_name", "")[:64],
        "userspace_bits": fields.get("userspace_bits", "")[:16],
        "python_version": fields.get("python_version", "")[:64],
        "os_id": fields.get("os_id", "")[:64],
        "os_version_id": fields.get("os_version_id", "")[:64],
        "os_codename": fields.get("os_codename", "")[:64],
        "pid1": fields.get("pid1", "")[:64],
        "systemd_version": fields.get("systemd_version", "")[:64],
        "pi_model": fields.get("pi_model", "")[:160],
        "rpi_image_reference": fields.get("rpi_image_reference", "")[:160],
        "bluetooth_audio": fields.get("bluetooth_audio") if fields.get("bluetooth_audio") in {"disabled", "requested"} else None,
    }


def run_summary(command: list[str], *, timeout: float = 3.0, limit: int = 160) -> dict[str, object]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "UNAVAILABLE", "exit": None, "summary": type(exc).__name__}
    return {
        "status": "READY" if result.returncode == 0 else "DEGRADED",
        "exit": result.returncode,
        "summary": clean(result.stdout or result.stderr, limit),
    }


def memory_inventory() -> dict[str, int]:
    keys = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace").splitlines():
            key, _, remainder = line.partition(":")
            if key in keys:
                number = remainder.strip().split(" ", 1)[0]
                if number.isdigit():
                    values[f"{key.lower()}_kib"] = int(number)
    except OSError:
        pass
    return values


def command_inventory() -> dict[str, bool]:
    commands = (
        "arecord",
        "aplay",
        "bluetoothctl",
        "gpiodetect",
        "gpioinfo",
        "i2cdetect",
        "journalctl",
        "ollama",
        "systemctl",
        "vcgencmd",
    )
    return {name: shutil.which(name) is not None for name in commands}


def platform_inventory() -> dict[str, object]:
    root = shutil.disk_usage("/")
    var = shutil.disk_usage("/var") if Path("/var").exists() else root
    payload: dict[str, object] = {
        "schema": 1,
        "content_logging": False,
        "python": platform.python_version(),
        "system": platform.system(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "disk": {
            "root_total_kib": root.total // 1024,
            "root_free_kib": root.free // 1024,
            "var_total_kib": var.total // 1024,
            "var_free_kib": var.free // 1024,
        },
        "memory": memory_inventory(),
        "commands": command_inventory(),
        "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else [],
    }
    payload["throttled"] = (
        run_summary(["vcgencmd", "get_throttled"], timeout=3, limit=80)
        if shutil.which("vcgencmd")
        else {"status": "UNAVAILABLE", "exit": None, "summary": "vcgencmd_missing"}
    )
    return payload


def safe_events(directory: Path, limit: int = 80) -> list[dict[str, str]]:
    if directory.is_symlink() or not directory.is_dir():
        return []
    output: list[dict[str, str]] = []
    for path in sorted(directory.glob("*.event"))[-limit:]:
        fields = parse_kv(path, max_bytes=8192) or {}
        if fields.get("format") != "gonken-install-event-v1":
            continue
        code = fields.get("code", "")
        step = fields.get("step_id", "")
        level = fields.get("level", "")
        message = fields.get("message", "")
        if not SAFE_CODE.fullmatch(code) or not SAFE_STEP.fullmatch(step) or level not in {"info", "error"}:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", message):
            continue
        output.append({"level": level, "code": code, "step_id": step, "message": message})
    return output


def safe_preflight(path: Path) -> dict[str, object] | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 131072:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if payload.get("format") != "gonken-target-preflight-v1" or payload.get("phase") not in {"prerequisites", "identities"}:
        return None
    checks = []
    for item in payload.get("checks", []):
        if not isinstance(item, dict):
            continue
        check_id = str(item.get("id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", check_id):
            continue
        checks.append({
            "id": check_id,
            "required": bool(item.get("required")),
            "ok": bool(item.get("ok")),
            "detail": str(item.get("detail", ""))[:240],
            "remediation": str(item.get("remediation", ""))[:240],
        })
    return {
        "format": "gonken-target-preflight-v1",
        "phase": payload.get("phase"),
        "status": payload.get("status") if payload.get("status") in {"PASS", "WARN", "FAIL"} else "UNKNOWN",
        "required_failures": [str(v)[:96] for v in payload.get("required_failures", [])[:64]],
        "warnings": [str(v)[:96] for v in payload.get("warnings", [])[:64]],
        "checks": checks,
    }


def target_manifest(script_dir: Path) -> dict[str, object]:
    probe = script_dir / "target_probe.py"
    if not probe.is_file() or probe.is_symlink():
        return {
            "status": "UNAVAILABLE",
            "format": TARGET_MANIFEST_FORMAT,
            "detail": "target_probe_py_missing",
            "physical_acceptance_claimed": False,
        }
    try:
        result = subprocess.run(
            ["python3", str(probe), "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "UNAVAILABLE",
            "format": TARGET_MANIFEST_FORMAT,
            "detail": type(exc).__name__,
            "physical_acceptance_claimed": False,
        }
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "status": "INVALID",
            "format": TARGET_MANIFEST_FORMAT,
            "detail": "target_probe_json_unreadable",
            "physical_acceptance_claimed": False,
        }
    if not isinstance(payload, dict) or payload.get("format") != TARGET_MANIFEST_FORMAT:
        return {
            "status": "INVALID",
            "format": TARGET_MANIFEST_FORMAT,
            "detail": "target_probe_format_invalid",
            "physical_acceptance_claimed": False,
        }
    if payload.get("physical_acceptance_claimed") is not False:
        return {
            "status": "INVALID",
            "format": TARGET_MANIFEST_FORMAT,
            "detail": "target_probe_claims_physical_acceptance",
            "physical_acceptance_claimed": False,
        }
    privacy = payload.get("privacy")
    if not isinstance(privacy, dict) or any(
        privacy.get(key) is not False
        for key in ("raw_audio_included", "transcripts_included", "prompts_or_model_responses_included")
    ):
        return {
            "status": "INVALID",
            "format": TARGET_MANIFEST_FORMAT,
            "detail": "target_probe_privacy_invalid",
            "physical_acceptance_claimed": False,
        }
    payload["failure_bundle_member_status"] = "READY" if result.returncode == 0 else "DEGRADED"
    return payload


def service_event_codes(limit: int = 200) -> dict[str, object]:
    if not shutil.which("journalctl"):
        return {"status": "UNAVAILABLE", "units": {}}
    units: dict[str, object] = {}
    for unit in SERVICE_UNITS:
        try:
            result = subprocess.run(
                ["journalctl", "-u", unit, "-b", "--no-pager", "-n", str(limit), "-o", "cat"],
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
            )
        except (OSError, subprocess.TimeoutExpired):
            units[unit] = {"status": "UNAVAILABLE", "codes": {}}
            continue
        counts: dict[str, int] = {}
        for match in re.finditer(r"(?:^|\s)code=([A-Z0-9_]{1,64})(?:\s|$)", result.stdout):
            code = match.group(1)
            counts[code] = counts.get(code, 0) + 1
        units[unit] = {
            "status": "READY" if result.returncode == 0 else "DEGRADED",
            "codes": dict(sorted(counts.items())),
        }
    return {"status": "READY", "units": units}


def bundle_index(payloads: dict[str, object]) -> dict[str, object]:
    return {
        "schema": 1,
        "format": "gonken-install-failure-evidence-index-v1",
        "content_logging": False,
        "physical_acceptance_claimed": False,
        "diagnostic_package_role": (
            "single-upload installer failure evidence bundle for host-side troubleshooting and next-package construction"
        ),
        "members": sorted(payloads),
        "privacy_exclusions": [
            "raw audio",
            "conversation transcripts",
            "prompts or model responses",
            "credentials",
            "Wi-Fi passphrases",
            "source URLs",
            "Bluetooth device selectors",
            "arbitrary raw journal text",
        ],
        "interpretation": (
            "The bundle records target topology, installer provenance, preflight outcomes and bounded service codes. "
            "It does not by itself prove physical fan blade motion, acoustic quality or sensor placement."
        ),
    }


def create_bundle(*, state_dir: Path, log_dir: Path, source_record: Path, output_dir: Path, exit_code: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_dir.chmod(0o700)
    payloads: dict[str, object] = {
        "failure.json": {"format": FORMAT, "installer_exit_code": int(exit_code), "content_logging": False},
        "source.json": safe_source(source_record),
        "events.json": {"events": safe_events(log_dir / "events")},
        "platform_inventory.json": platform_inventory(),
        "target_manifest.json": target_manifest(Path(__file__).resolve().parent),
        "service_events.json": service_event_codes(),
    }
    artifacts = state_dir / "artifacts"
    for phase in ("prerequisites", "identities"):
        item = safe_preflight(artifacts / f"target-preflight-{phase}.json")
        if item is not None:
            payloads[f"preflight-{phase}.json"] = item
    payloads["evidence_index.json"] = bundle_index(payloads)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    final = output_dir / f"gonken-install-failure-{stamp}-{os.getpid()}.zip"
    fd, name = tempfile.mkstemp(prefix=".gonken-install-failure.", dir=output_dir)
    os.close(fd)
    temporary = Path(name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for member, payload in sorted(payloads.items()):
                archive.writestr(member, json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, final)
    finally:
        if temporary.exists():
            temporary.unlink()
    return final


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-dir", required=True)
    p.add_argument("--log-dir", required=True)
    p.add_argument("--source-record", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--exit-code", type=int, required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    bundle = create_bundle(
        state_dir=Path(args.state_dir), log_dir=Path(args.log_dir), source_record=Path(args.source_record),
        output_dir=Path(args.output_dir), exit_code=args.exit_code,
    )
    print(f"[OK] code=INSTALL_FAILURE_BUNDLE path={bundle} content_logging=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
