"""Canonical content-free evidence bundle primitives.

This module owns bundle indexing, integrity metadata, safe publication and
operator-accessible output policy.  Section producers remain domain-specific,
but every support/failure archive uses this exact envelope.
"""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

INDEX_FORMAT = "gonken-evidence-bundle-index-v2"
SAFE_MEMBER = re.compile(r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.json$")
PRIVACY_EXCLUSIONS = (
    "credentials and authentication secrets",
    "Wi-Fi passphrases",
    "private keys and tokens",
    "raw audio",
    "conversation transcripts",
    "prompts and model responses",
    "arbitrary raw journal text",
    "unrelated user files",
)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def payload_status(value: object) -> str:
    if isinstance(value, dict):
        status = str(value.get("status", "")).upper()
        if status in {"READY", "DEGRADED", "FAILED", "UNAVAILABLE", "INVALID", "PASS", "FAIL", "WAITING"}:
            return status
    return "READY"


def build_index(
    payloads: Mapping[str, object],
    *,
    bundle_kind: str,
    producers: Mapping[str, str] | None = None,
    omitted_sections: Sequence[Mapping[str, object]] = (),
    package_commit: str | None = None,
    created_at: str | None = None,
) -> dict[str, object]:
    members = []
    producer_map = producers or {}
    for name in sorted(payloads):
        if name == "evidence_index.json" or not SAFE_MEMBER.fullmatch(name) or ".." in Path(name).parts:
            raise ValueError(f"invalid evidence member: {name}")
        encoded = json_bytes(payloads[name])
        members.append({
            "path": name,
            "producer": str(producer_map.get(name, "canonical-evidence-engine"))[:96],
            "status": payload_status(payloads[name]),
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "bytes": len(encoded),
        })
    safe_omitted = []
    for item in omitted_sections:
        name = str(item.get("name", ""))[:96]
        reason = str(item.get("reason", ""))[:160]
        if name and reason:
            safe_omitted.append({"name": name, "reason": reason})
    return {
        "schema": 2,
        "format": INDEX_FORMAT,
        "bundle_kind": bundle_kind,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "package_commit": package_commit,
        "content_logging": False,
        "physical_acceptance_claimed": False,
        "members": members,
        "omitted_sections": safe_omitted,
        "privacy_exclusions": list(PRIVACY_EXCLUSIONS),
        "interpretation": (
            "Structured target/runtime evidence supports troubleshooting and target-shadow regression. "
            "It does not by itself prove physical fan motion, acoustic quality, sensor placement, or final HIL acceptance."
        ),
    }


def write_bundle(
    output: Path,
    payloads: Mapping[str, object],
    *,
    bundle_kind: str,
    producers: Mapping[str, str] | None = None,
    omitted_sections: Sequence[Mapping[str, object]] = (),
    package_commit: str | None = None,
) -> dict[str, object]:
    output = Path(output).absolute()
    if not output.parent.is_dir() or output.parent.is_symlink() or output.parent.resolve() != output.parent:
        raise ValueError("evidence output parent must be an existing real directory")
    if output.exists() or output.is_symlink():
        raise ValueError("evidence output must be a new file")
    common = dict(payloads)
    if "evidence_index.json" in common:
        raise ValueError("evidence index is canonical-engine owned")
    index = build_index(
        common,
        bundle_kind=bundle_kind,
        producers=producers,
        omitted_sections=omitted_sections,
        package_commit=package_commit,
    )
    common["evidence_index.json"] = index
    descriptor, name = tempfile.mkstemp(prefix=".gonken-evidence.", dir=output.parent)
    temporary = Path(name)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for member, payload in sorted(common.items()):
                entry = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
                entry.external_attr = 0o100600 << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, json_bytes(payload))
        os.chmod(temporary, 0o600)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(temporary, output, follow_symlinks=False)
        os.chmod(output, 0o600)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "status": "CREATED",
        "bundle_kind": bundle_kind,
        "members": sorted(common),
        "content_logging": False,
        "physical_acceptance_claimed": False,
        "index_format": INDEX_FORMAT,
    }


def invoking_user_identity() -> tuple[int, int, Path] | None:
    uid_text = os.environ.get("SUDO_UID", "")
    gid_text = os.environ.get("SUDO_GID", "")
    user = os.environ.get("SUDO_USER", "")
    try:
        uid = int(uid_text)
        gid = int(gid_text)
    except ValueError:
        return None
    if uid <= 0 or gid < 0 or user in {"", "root"}:
        return None
    try:
        account = pwd.getpwnam(user)
    except KeyError:
        return None
    if account.pw_uid != uid or account.pw_gid != gid:
        return None
    home = Path(account.pw_dir)
    if not home.is_absolute() or not home.is_dir() or home.is_symlink():
        return None
    return uid, gid, home


def resolve_output_path(
    *,
    prefix: str,
    output: Path | None = None,
    output_dir: Path | None = None,
    fallback_dir: Path = Path("/var/lib/gonken-agent/support"),
) -> Path:
    if output is not None and output_dir is not None:
        raise ValueError("use either --output or --output-dir, not both")
    if output is not None:
        result = Path(output).absolute()
        if result.suffix != ".zip":
            raise ValueError("evidence --output must end in .zip")
        return result
    if output_dir is not None:
        directory = Path(output_dir).absolute()
    else:
        identity = invoking_user_identity()
        if identity is not None:
            directory = identity[2]
        elif os.geteuid() != 0:
            directory = Path.home().absolute()
        else:
            directory = fallback_dir.absolute()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return directory / f"{prefix}-{stamp}-{os.getpid()}.zip"


def return_ownership_to_invoking_user(path: Path) -> bool:
    identity = invoking_user_identity()
    if identity is None or os.geteuid() != 0:
        return False
    uid, gid, _home = identity
    os.chown(path, uid, gid)
    os.chmod(path, 0o600)
    return True


def read_json_members(path: Path, *, max_total_bytes: int = 8 * 1024 * 1024) -> dict[str, object]:
    result: dict[str, object] = {}
    total = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            name = info.filename
            if name == "evidence_index.json":
                continue
            if not SAFE_MEMBER.fullmatch(name) or ".." in Path(name).parts:
                raise ValueError("unsafe evidence member")
            total += info.file_size
            if info.file_size > 2 * 1024 * 1024 or total > max_total_bytes:
                raise ValueError("evidence member size limit")
            value = json.loads(archive.read(info).decode("utf-8"))
            result[name] = value
    return result
