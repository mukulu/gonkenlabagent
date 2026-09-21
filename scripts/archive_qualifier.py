#!/usr/bin/env python3
"""Qualify an exact checkpoint archive before any Raspberry Pi candidate handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tarfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_IFMT((info.external_attr >> 16) & 0o777777) == stat.S_IFLNK


def _zip_mode(info: zipfile.ZipInfo) -> int | None:
    mode = (info.external_attr >> 16) & 0o777777
    return mode or None


def inspect_zip(path: Path) -> dict[str, object]:
    roots: set[str] = set()
    members: list[str] = []
    failures: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            for info in infos:
                name = info.filename
                members.append(name)
                posix = PurePosixPath(name)
                parts = posix.parts
                if not parts or name.startswith("/") or any(part in {"", ".", ".."} for part in parts):
                    failures.append(f"unsafe_path:{name}")
                    continue
                roots.add(parts[0])
                if _is_zip_symlink(info):
                    failures.append(f"symlink:{name}")
                if any(part == "__pycache__" for part in parts) or posix.suffix in {".pyc", ".pyo"}:
                    failures.append(f"python_cache:{name}")
    except (OSError, zipfile.BadZipFile) as exc:
        return {"status": "FAIL", "code": "ARCHIVE_UNREADABLE", "detail": type(exc).__name__}
    if not members:
        failures.append("empty_archive")
    if len(roots) != 1:
        failures.append("single_root_required")
    if failures:
        return {"status": "FAIL", "code": "ARCHIVE_STRUCTURE_INVALID", "detail": ";".join(failures)}
    return {
        "status": "PASS",
        "code": "ARCHIVE_STRUCTURE_VALID",
        "root": next(iter(roots)),
        "members": len(members),
    }


def extract_zip_preserving_permissions(path: Path, destination: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        inspection = inspect_zip(path)
        if inspection.get("status") != "PASS":
            raise ValueError(str(inspection.get("detail", "invalid archive")))
        for info in archive.infolist():
            parts = PurePosixPath(info.filename).parts
            target = destination.joinpath(*parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                mode = _zip_mode(info)
                if mode is not None:
                    target.chmod(mode & 0o777)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            mode = _zip_mode(info)
            if mode is not None:
                target.chmod(mode & 0o777)


def inspect_tar(path: Path) -> dict[str, object]:
    """Inspect new canonical tar.bz2 packages without trusting links or modes."""
    roots, seen, failures = set(), set(), []
    total = 0
    try:
        with tarfile.open(path, "r:bz2") as archive:
            for index, member in enumerate(archive):
                name = member.name.rstrip("/")
                parts = name.split("/")
                if (not name or name.startswith("/") or "\\" in name or
                        any(p in {"", ".", ".."} for p in parts) or name in seen):
                    failures.append("unsafe_or_duplicate_path"); continue
                seen.add(name); roots.add(parts[0])
                if not (member.isfile() or member.isdir()): failures.append("special_member")
                if member.mode & 0o7000: failures.append("privileged_mode")
                if "__pycache__" in parts or Path(name).suffix in {".pyc", ".pyo"}: failures.append("python_cache")
                total += member.size
                if index > 100000 or total > 512 * 1024 * 1024: failures.append("archive_size_limit"); break
    except (OSError, EOFError, tarfile.TarError):
        return {"status":"FAIL", "code":"ARCHIVE_UNREADABLE"}
    if not seen or len(roots) != 1: failures.append("single_nonempty_root_required")
    if failures: return {"status":"FAIL", "code":"ARCHIVE_STRUCTURE_INVALID", "detail":";".join(sorted(set(failures)))}
    return {"status":"PASS", "code":"ARCHIVE_STRUCTURE_VALID", "root":next(iter(roots)), "members":len(seen)}


def extract_tar_preserving_permissions(path: Path, destination: Path) -> None:
    inspection = inspect_tar(path)
    if inspection["status"] != "PASS": raise ValueError("invalid tar archive")
    # The qualification caller always supplies a fresh private directory.
    with tarfile.open(path, "r:bz2") as archive:
        for member in archive:
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(member.mode & 0o777)


def _run(command: list[str], cwd: Path, *, timeout: int = 60) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "FAIL", "command": command, "exit": None, "detail": type(exc).__name__}
    return {
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "command": command,
        "exit": completed.returncode,
        "stdout": completed.stdout.strip()[:2000],
        "stderr": completed.stderr.strip()[:2000],
    }


def _git_text(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()


def _append_command_check(checks: list[dict[str, object]], code: str, command: list[str], cwd: Path, *, timeout: int = 60) -> None:
    result = _run(command, cwd, timeout=timeout)
    checks.append({"code": code, **result})


def qualify_archive(
    archive_path: Path,
    *,
    expected_commit: str | None = None,
    expected_tag: str | None = None,
    run_t0: bool = True,
    purpose: str = "target-candidate",
) -> dict[str, object]:
    if purpose not in {"development", "target-candidate"}:
        raise ValueError("invalid archive qualification purpose")
    checks: list[dict[str, object]] = []
    archive_path = archive_path.resolve()
    is_tar = archive_path.name.endswith(".tar.bz2")
    structure = inspect_tar(archive_path) if is_tar else inspect_zip(archive_path)
    checks.append({"code": structure.get("code", "ARCHIVE_STRUCTURE_INVALID"), **structure})
    report: dict[str, object] = {
        "schema": 1,
        "archive": str(archive_path),
        "sha256": sha256_file(archive_path) if archive_path.is_file() else "",
        "status": "FAIL",
        "checks": checks,
        "physical_acceptance_claimed": False,
        "raspberry_pi_candidate": False,
        "purpose": purpose,
    }
    if purpose == 'target-candidate' and (not run_t0 or not isinstance(expected_commit, str) or not re.fullmatch(r'[0-9a-f]{40}', expected_commit)):
        checks.append({'status':'FAIL', 'code':'TARGET_QUALIFICATION_REQUIRES_PINNED_COMMIT_AND_T0'})
    if structure.get("status") != "PASS":
        return report
    with tempfile.TemporaryDirectory(prefix="gonken-archive-qualifier-") as temporary:
        extract_root = Path(temporary)
        (extract_tar_preserving_permissions if is_tar else extract_zip_preserving_permissions)(archive_path, extract_root)
        repo = extract_root / str(structure["root"])
        if not repo.is_dir():
            checks.append({"status": "FAIL", "code": "EXTRACTED_ROOT_MISSING", "path": str(repo)})
            return report
        _append_command_check(checks, "GIT_STATUS_CLEAN", ["git", "status", "--porcelain"], repo, timeout=30)
        if checks[-1].get("status") == "PASS" and checks[-1].get("stdout"):
            checks[-1]["status"] = "FAIL"
            checks[-1]["detail"] = "dirty_worktree"
        try:
            observed_commit = _git_text(repo, "rev-parse", "HEAD")
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            checks.append({"status": "FAIL", "code": "GIT_COMMIT_UNREADABLE", "detail": type(exc).__name__})
            observed_commit = ""
        commit_check: dict[str, object] = {
            "status": "PASS",
            "code": "GIT_COMMIT_MATCH",
            "observed": observed_commit,
            "expected": expected_commit or observed_commit,
        }
        if expected_commit and observed_commit != expected_commit:
            commit_check["status"] = "FAIL"
        checks.append(commit_check)
        if expected_tag:
            try:
                tags = _git_text(repo, "tag", "--points-at", "HEAD").splitlines()
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                tags = []
                checks.append({"status": "FAIL", "code": "GIT_TAG_UNREADABLE", "detail": type(exc).__name__})
            checks.append({
                "status": "PASS" if expected_tag in tags else "FAIL",
                "code": "GIT_TAG_MATCH",
                "expected": expected_tag,
                "observed": tags,
            })
        _append_command_check(checks, "GIT_FSCK_STRICT", ["git", "fsck", "--strict"], repo, timeout=60)
        _append_command_check(checks, "CURRENT_STATE_CHECK", [sys.executable, "scripts/current_state.py", "--check"], repo, timeout=60)
        _append_command_check(checks, "RELEASE_READINESS_CHECK", [sys.executable, "scripts/release_readiness.py", "--validate" if purpose == "development" else "--check"], repo, timeout=60)
        if run_t0:
            _append_command_check(checks, "CI_T0_CHECK", ["./scripts/ci.sh", "--phase", "t0"], repo, timeout=180)
    report["status"] = "PASS" if all(check.get("status") == "PASS" for check in checks) else "FAIL"
    report["raspberry_pi_candidate"] = report["status"] == "PASS" and purpose == "target-candidate"
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("archive", help="Canonical .tar.bz2 checkpoint (legacy ZIP read-only compatibility)")
    result.add_argument("--purpose", choices=("development", "target-candidate"), default="target-candidate")
    result.add_argument("--expected-commit", help="Expected Git commit for extracted archive")
    result.add_argument("--expected-tag", help="Expected Git tag pointing at the extracted archive commit")
    result.add_argument("--skip-t0", action="store_true", help="Skip T0 inside the extracted archive")
    result.add_argument("--json", action="store_true", dest="as_json")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = qualify_archive(
        Path(args.archive),
        expected_commit=args.expected_commit,
        expected_tag=args.expected_tag,
        run_t0=not args.skip_t0,
        purpose=args.purpose,
    )
    if args.as_json:
        print(json.dumps(report, sort_keys=True, indent=2))
    else:
        print(f"Status: {report['status']}")
        print(f"Archive: {report['archive']}")
        print(f"SHA256: {report['sha256']}")
        print("Physical acceptance claimed: false")
        for check in report["checks"]:
            print(f"- {check.get('code')}: {check.get('status')}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
