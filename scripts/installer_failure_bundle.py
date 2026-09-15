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
import re
import tempfile
import time
import zipfile
from pathlib import Path

SAFE_CODE = re.compile(r"^[A-Z0-9_]{1,64}$")
SAFE_STEP = re.compile(r"^(?:[a-z0-9_.-]{1,64}|none)$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
FORMAT = "gonken-installer-failure-bundle-v1"


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
        "os_version_id": fields.get("os_version_id", "")[:64],
        "os_codename": fields.get("os_codename", "")[:64],
        "bluetooth_audio": fields.get("bluetooth_audio") if fields.get("bluetooth_audio") in {"disabled", "requested"} else None,
    }


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


def create_bundle(*, state_dir: Path, log_dir: Path, source_record: Path, output_dir: Path, exit_code: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_dir.chmod(0o700)
    payloads: dict[str, object] = {
        "failure.json": {"format": FORMAT, "installer_exit_code": int(exit_code), "content_logging": False},
        "source.json": safe_source(source_record),
        "events.json": {"events": safe_events(log_dir / "events")},
    }
    artifacts = state_dir / "artifacts"
    for phase in ("prerequisites", "identities"):
        item = safe_preflight(artifacts / f"target-preflight-{phase}.json")
        if item is not None:
            payloads[f"preflight-{phase}.json"] = item
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
