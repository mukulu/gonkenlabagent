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
import io
import stat
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

MAX_MEMBER_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
MAX_MEMBERS = 128

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
    if bundle_kind not in {"support", "combined_installer_failure_support"}:
        raise ValueError("unknown evidence bundle kind")
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
    if not output.name.endswith(".tar.bz2"):
        raise ValueError("evidence output must end in .tar.bz2")
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
        encoded = {member: json_bytes(payload) for member, payload in sorted(common.items())}
        if len(encoded) > MAX_MEMBERS or any(len(raw) > MAX_MEMBER_BYTES for raw in encoded.values()) or sum(map(len, encoded.values())) > MAX_TOTAL_BYTES:
            raise ValueError("evidence size limit")
        with tarfile.open(temporary, "w:bz2", format=tarfile.USTAR_FORMAT) as archive:
            for member, raw in encoded.items():
                entry = tarfile.TarInfo(member)
                entry.mode = 0o600
                entry.mtime = 0
                entry.size = len(raw)
                archive.addfile(entry, io.BytesIO(raw))
        # Validate the exact bytes before exposing the final path.
        verify_bundle(temporary)
        os.chmod(temporary, 0o600)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(temporary, output, follow_symlinks=False)
        os.chmod(output, 0o600)
        directory_fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "status": "CREATED",
        "archive": str(output),
        "archive_format": "tar.bz2",
        "verified": True,
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
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", prefix):
        raise ValueError("invalid evidence filename prefix")
    if output is not None and output_dir is not None:
        raise ValueError("use either --output or --output-dir, not both")
    if output is not None:
        result = Path(output).absolute()
        if not result.name.endswith(".tar.bz2"):
            raise ValueError("evidence --output must end in .tar.bz2")
        return result
    if output_dir is not None:
        # Explicit destinations are operator-owned policy.  Require the caller
        # to create them first so a sudo invocation cannot silently create a
        # root-only directory inside the caller's home and then strand an
        # otherwise correctly chowned archive beneath it.
        directory = Path(output_dir).absolute()
        if not directory.is_dir() or directory.is_symlink() or directory.resolve() != directory:
            raise ValueError("evidence --output-dir must be an existing real directory")
    else:
        identity = invoking_user_identity()
        if identity is not None:
            directory = identity[2]
        elif os.geteuid() != 0:
            directory = Path.home().absolute()
        else:
            directory = fallback_dir.absolute()
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not directory.is_dir() or directory.is_symlink() or directory.resolve() != directory:
            raise ValueError("evidence output directory must be an existing real directory")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return directory / f"{prefix}-{stamp}-{os.getpid()}.tar.bz2"


def return_ownership_to_invoking_user(path: Path) -> bool:
    identity = invoking_user_identity()
    if identity is None or os.geteuid() != 0:
        return False
    uid, gid, _home = identity
    os.chown(path, uid, gid)
    os.chmod(path, 0o600)
    return True


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate evidence JSON key")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError("non-finite evidence JSON")


def _read_archive(path: Path, max_total_bytes: int) -> tuple[dict[str, object], dict[str, bytes]]:
    payloads: dict[str, object] = {}
    raw_members: dict[str, bytes] = {}
    total = 0
    if type(max_total_bytes) is not int or not 1 <= max_total_bytes <= MAX_TOTAL_BYTES:
        raise ValueError("invalid evidence byte budget")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_TOTAL_BYTES * 2:
            raise ValueError("unsafe evidence archive input")
        source_file = os.fdopen(descriptor, 'rb')
        descriptor = None
        with source_file, tarfile.open(fileobj=source_file, mode="r:bz2") as archive:
            for info in archive:
                name = info.name
                if (name in payloads or not info.isfile() or not SAFE_MEMBER.fullmatch(name)
                        or ".." in Path(name).parts or info.mode & 0o7000):
                    raise ValueError("unsafe or duplicate evidence member")
                total += info.size
                if (info.size < 0 or info.size > MAX_MEMBER_BYTES or total > max_total_bytes
                        or len(payloads) >= MAX_MEMBERS):
                    raise ValueError("evidence member size limit")
                with archive.extractfile(info) as source:
                    raw = source.read(MAX_MEMBER_BYTES + 1)
                if len(raw) != info.size:
                    raise ValueError("truncated evidence member")
                value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
                payloads[name], raw_members[name] = value, raw
    except (tarfile.TarError, EOFError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid evidence archive") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return payloads, raw_members


def _validate_index(payloads: dict[str, object], raw_members: dict[str, bytes]) -> dict:
    index = payloads.get("evidence_index.json")
    if (not isinstance(index, dict) or index.get("format") != INDEX_FORMAT
            or type(index.get("schema")) is not int or index.get("schema") != 2
            or index.get("bundle_kind") not in {"support", "combined_installer_failure_support"}
            or index.get("content_logging") is not False or index.get("physical_acceptance_claimed") is not False
            or not isinstance(index.get("members"), list)):
        raise ValueError("invalid or missing evidence index")
    seen = set()
    for row in index['members']:
        if not isinstance(row, dict) or not isinstance(row.get('path'), str):
            raise ValueError("invalid evidence index row")
        name = row['path']
        if name in seen or name == 'evidence_index.json' or name not in raw_members:
            raise ValueError("evidence index membership mismatch")
        seen.add(name)
        raw = raw_members[name]
        if type(row.get('bytes')) is not int or row['bytes'] != len(raw) or row.get('sha256') != hashlib.sha256(raw).hexdigest():
            raise ValueError("evidence integrity mismatch")
    if seen != set(payloads) - {'evidence_index.json'}:
        raise ValueError("evidence index membership mismatch")
    return index


def verify_bundle(path: Path, *, max_total_bytes: int = MAX_TOTAL_BYTES) -> dict:
    payloads, raw_members = _read_archive(Path(path), max_total_bytes)
    return _validate_index(payloads, raw_members)


def read_json_members(path: Path, *, max_total_bytes: int = MAX_TOTAL_BYTES) -> dict[str, object]:
    payloads, raw_members = _read_archive(Path(path), max_total_bytes)
    _validate_index(payloads, raw_members)
    return {name: value for name, value in payloads.items() if name != 'evidence_index.json'}
