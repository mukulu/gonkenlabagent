#!/usr/bin/env python3
"""Create a private, content-free support bundle for installer failures.

This helper is source-package owned so it remains usable when a new immutable
candidate fails before activation.  It exports only allow-listed metadata and
structured installer/preflight records; raw stdout/stderr, credentials, user
content, audio, prompts and model data are never copied.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

SAFE_CODE = re.compile(r"^[A-Z0-9_]{1,64}$")
SAFE_STEP = re.compile(r"^(?:[a-z0-9_.-]{1,64}|none)$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
FORMAT = "gonken-installer-failure-bundle-v2"
TARGET_MANIFEST_FORMAT = "gonken-target-hardware-manifest-v1"
SERVICE_UNITS = (
    "gonken-agent.service",
    "gonken-environment.service",
    "ollama.service",
    "bluetooth.service",
    "gonken-bluetooth-autoconnect.service",
)


def _load_evidence_module():
    candidates = [
        Path(__file__).resolve().with_name("evidence.py"),
        Path(__file__).resolve().parents[1] / "src" / "gonken_agent" / "evidence.py",
    ]
    for candidate in candidates:
        if candidate.is_file() and not candidate.is_symlink():
            spec = importlib.util.spec_from_file_location("gonken_canonical_evidence", candidate)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
    raise RuntimeError("canonical evidence engine unavailable")


EVIDENCE = _load_evidence_module()
CURRENT_MAINTENANCE = Path("/usr/local/lib/gonken-agent/current/maintenance")


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
        "environment_profile": fields.get("environment_profile") if fields.get("environment_profile") in {
            "none", "full-simulation", "real-sensor-simulated-actuator", "sensor-deferred-relay", "full-real"
        } else None,
        "environment_sensor_address": fields.get("environment_sensor_address") if fields.get("environment_sensor_address") in {"0x44", "0x45"} else None,
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


def _current_readiness() -> dict[str, object] | None:
    # Source and maintenance use the same content-free freshness validator.
    candidates = [Path(__file__).resolve().with_name("runtime_readiness.py"),
                  Path(__file__).resolve().parents[1] / "src/gonken_agent/runtime_readiness.py"]
    for path in candidates:
        if path.is_file() and not path.is_symlink():
            spec = importlib.util.spec_from_file_location("gonken_failure_readiness", path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module.read_pending()
    return None


def _collect_support_payloads(staging: Path) -> tuple[dict[str, object], list[dict[str, str]]]:
    collector = CURRENT_MAINTENANCE / "collect-support.sh"
    if not collector.is_file() or collector.is_symlink() or not os.access(collector, os.X_OK):
        return {}, [{"name": "canonical_support", "reason": "collect-support unavailable at current install stage"}]
    support_archive = staging / "canonical-support.tar.bz2"
    try:
        result = subprocess.run(
            [str(collector), "--output", str(support_archive)],
            check=False, capture_output=True, text=True, timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {}, [{"name": "canonical_support", "reason": f"collector {type(exc).__name__}"}]
    if result.returncode != 0 or not support_archive.is_file():
        return {}, [{"name": "canonical_support", "reason": f"collector exit {result.returncode}"}]
    try:
        return EVIDENCE.read_json_members(support_archive), []
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, [{"name": "canonical_support", "reason": f"collector archive {type(exc).__name__}"}]


def create_bundle(
    *, state_dir: Path, log_dir: Path, source_record: Path, exit_code: int,
    output: Path | None = None, output_dir: Path | None = None,
) -> Path:
    source = safe_source(source_record)
    events = safe_events(log_dir / "events")
    last_error = next((event for event in reversed(events) if event.get("level") == "error"), None)
    readiness = _current_readiness()
    commit = source.get("resolved_commit") if isinstance(source.get("resolved_commit"), str) else None
    final = EVIDENCE.resolve_output_path(
        prefix="gonken-install-failure", output=output, output_dir=output_dir,
        fallback_dir=Path("/var/lib/gonken-agent/install/failures"),
    )
    final.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payloads: dict[str, object] = {
        "installer/failure.json": {
            "format": FORMAT, "installer_exit_code": int(exit_code), "content_logging": False,
            "current_failure": {
                "installer_event": last_error,
                "runtime_readiness": readiness,
            },
        },
        "installer/source.json": source,
        "installer/events.json": {"status": "READY" if events else "UNAVAILABLE", "events": events},
    }
    producers = {name: "installer_failure_bundle.py" for name in payloads}
    artifacts = state_dir / "artifacts"
    for phase in ("prerequisites", "identities"):
        item = safe_preflight(artifacts / f"target-preflight-{phase}.json")
        if item is not None:
            name = f"installer/preflight-{phase}.json"
            payloads[name] = item
            producers[name] = "target_preflight.py"
    omitted: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="gonken-installer-evidence.") as temporary:
        staging = Path(temporary)
        common, support_omitted = _collect_support_payloads(staging)
        omitted.extend(support_omitted)
        if common:
            for name, value in common.items():
                if name.startswith("installer/") or name in payloads:
                    raise ValueError(f"canonical support member conflicts with installer evidence: {name}")
                payloads[name] = value
                producers[name] = "canonical-support-collector"
        else:
            # Preserve checkpoint-42 early-failure observability, but identify
            # these as explicit fallbacks rather than a second canonical schema.
            fallback = {
                "platform_inventory.json": platform_inventory(),
                "target_manifest.json": target_manifest(Path(__file__).resolve().parent),
                "service_events.json": service_event_codes(),
            }
            payloads.update(fallback)
            for name in fallback:
                producers[name] = "installer-early-fallback"
            omitted.append({
                "name": "installed_support_sections",
                "reason": "canonical installed collector unavailable; early-stage fallback members supplied",
            })
        EVIDENCE.write_bundle(
            final, payloads, bundle_kind="combined_installer_failure_support",
            producers=producers, omitted_sections=omitted, package_commit=commit,
        )
    EVIDENCE.return_ownership_to_invoking_user(final)
    return final


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-dir", required=True)
    p.add_argument("--log-dir", required=True)
    p.add_argument("--source-record", required=True)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--output")
    group.add_argument("--output-dir")
    p.add_argument("--exit-code", type=int, required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    bundle = create_bundle(
        state_dir=Path(args.state_dir), log_dir=Path(args.log_dir), source_record=Path(args.source_record),
        output=Path(args.output) if args.output else None,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        exit_code=args.exit_code,
    )
    print(f"[EVIDENCE] bundle: {bundle}")
    print("[EVIDENCE] kind: combined installer failure + support")
    print(f"[EVIDENCE] installer: exit={args.exit_code}")
    print("[EVIDENCE] upload this single .tar.bz2 archive for the next build cycle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
