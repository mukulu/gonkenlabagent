#!/usr/bin/env python3
"""Provision and validate the pinned M3.5 Whisper/Piper speech chain."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import venv
import wave
from pathlib import Path
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")
INTERRUPT_ENV = "GONKEN_SPEECH_TEST_INTERRUPT"
TEST_ENV = "GONKEN_ENABLE_TEST_FAILURES"
RECORD_FIELDS = (
    "format", "whisper_version", "whisper_binary_sha256", "whisper_model_sha256",
    "piper_version", "piper_lock_sha256", "piper_voice", "piper_voice_sha256",
    "piper_config_sha256", "tts_sample_rate", "tts_frames", "stt_required_tokens",
    "validated_epoch", "validation",
)


class SpeechError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, status: int = 1):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.status = status


def fail(code: str, message: str, remediation: str, status: int = 1) -> None:
    raise SpeechError(code, message, remediation, status)


def emit_error(error: SpeechError) -> None:
    print(
        f"[ERROR] code={error.code} message={error} remediation={error.remediation}",
        file=sys.stderr,
    )


def require_absolute(value: str | Path, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        fail("SPEECH_PATH", f"{label} must be an absolute normalized path", "use an absolute path without '..'", 64)
    return path


def test_mode(root: Path) -> bool:
    enabled = os.environ.get(TEST_ENV) == "1"
    if enabled and root == Path("/"):
        fail("SPEECH_TEST_GATE", "test failure controls cannot target the real root", "use an isolated --system-root", 77)
    return enabled and root != Path("/")


def rooted(root: Path, canonical: Path) -> Path:
    canonical = require_absolute(canonical, "installed path")
    return canonical if root == Path("/") else root / canonical.relative_to("/")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(arguments: list[str], *, input_text: str | None = None, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            arguments, input=input_text, check=True, capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        stderr = getattr(exc, "stderr", "") or ""
        fail("SPEECH_COMMAND", f"command failed: {arguments[0]}: {stderr.strip() or exc}", "inspect the exact command and rerun", 69)


def maybe_interrupt(operation: str, point: str) -> None:
    if os.environ.get(INTERRUPT_ENV) == f"{operation}:{point}":
        fail("SPEECH_TEST_INTERRUPT", f"injected interruption at {operation}:{point}", "rerun without the test injection", 91)


def ensure_directory(path: Path, mode: int = 0o755) -> None:
    if path.exists() or path.is_symlink():
        if not path.is_dir() or path.is_symlink():
            fail("SPEECH_LAYOUT", f"unsafe path conflict: {path}", "move the conflict after administrator review", 75)
    else:
        path.mkdir(parents=True, mode=mode)
    path.chmod(mode)


def durable_bytes(path: Path, payload: bytes, mode: int = 0o644) -> None:
    ensure_directory(path.parent)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        fail("SPEECH_LAYOUT", f"unsafe file conflict: {path}", "move the conflict after administrator review", 75)
    temporary = path.parent / f".{path.name}.tmp.{os.getpid()}"
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(mode)
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def atomic_symlink(path: Path, target: str) -> None:
    ensure_directory(path.parent)
    if path.exists() and not path.is_symlink():
        fail("SPEECH_ENTRYPOINT_CONFLICT", f"refusing to overwrite non-symlink: {path}", "move or adopt the existing file explicitly", 75)
    temporary = path.parent / f".{path.name}.tmp.{os.getpid()}"
    with contextlib.suppress(FileNotFoundError):
        temporary.unlink()
    temporary.symlink_to(target)
    os.replace(temporary, path)


def remove_owned(path: Path, parent: Path) -> None:
    if path.parent != parent or path.is_symlink() or not path.is_dir():
        fail("SPEECH_REPAIR", f"refusing unsafe repair target: {path}", "inspect the path manually", 75)
    remove_tree(path)


def remove_tree(path: Path) -> None:
    for item in sorted(path.rglob("*"), key=lambda entry: len(entry.parts), reverse=True):
        if item.is_dir() and not item.is_symlink():
            item.chmod(stat.S_IMODE(item.stat().st_mode) | 0o700)
    path.chmod(stat.S_IMODE(path.stat().st_mode) | 0o700)
    shutil.rmtree(path)


def freeze_tree(path: Path, *, keep_root_writable: bool = False) -> None:
    """Freeze public runtime/model artifacts with explicit service-readable modes."""
    for item in sorted(path.rglob("*"), key=lambda entry: len(entry.parts), reverse=True):
        if item.is_symlink():
            continue
        mode = stat.S_IMODE(item.stat().st_mode)
        if item.is_dir():
            item.chmod(0o555)
        elif item.is_file():
            item.chmod(0o555 if mode & 0o111 else 0o444)
        else:
            fail("SPEECH_LAYOUT", f"unsupported immutable object: {item}", "rebuild the checked artifact", 74)
    path.chmod(0o755 if keep_root_writable else 0o555)


def read_manifest(path: Path, root: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        fail("SPEECH_MANIFEST", "artifact manifest is missing or unsafe", "restore it from the active release", 65)
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    expected_top = {"format", "verified_at", "whisper", "whisper_model", "piper", "piper_voice", "smoke"}
    expected = {
        "whisper": {"version", "release_tag", "commit", "repository", "license", "source", "cmake_arguments"},
        "whisper_model": {"id", "filename", "upstream_filename", "source_commit", "url", "sha256", "size", "license", "source"},
        "piper": {"version", "release_tag", "commit", "platform", "profile", "lock", "lock_sha256", "wheel", "wheel_sha256", "license", "source", "distribution"},
        "piper_voice": {"id", "repository_commit", "filename", "url", "sha256", "size", "config_filename", "config_url", "config_sha256", "config_size", "model_card_filename", "model_card_url", "model_card_sha256", "model_card_size", "license", "license_source", "source"},
        "smoke": {"text", "required_tokens", "minimum_wav_frames", "maximum_wav_seconds"},
    }
    if set(data) != expected_top or data.get("format") != "gonken-speech-artifacts-v1":
        fail("SPEECH_MANIFEST", "artifact manifest schema differs", "restore the accepted M3.5 manifest", 65)
    for section, fields in expected.items():
        if not isinstance(data.get(section), dict) or set(data[section]) != fields:
            fail("SPEECH_MANIFEST", f"manifest section differs: {section}", "restore the accepted M3.5 manifest", 65)
    for section, fields in (("whisper", ("commit",)), ("whisper_model", ("source_commit",)), ("piper", ("commit",)), ("piper_voice", ("repository_commit",))):
        for field in fields:
            if not COMMIT_RE.fullmatch(str(data[section][field])):
                fail("SPEECH_MANIFEST", f"invalid immutable commit: {section}.{field}", "repin from an official source", 65)
    for section, fields in (("whisper_model", ("sha256",)), ("piper", ("lock_sha256", "wheel_sha256")), ("piper_voice", ("sha256", "config_sha256", "model_card_sha256"))):
        for field in fields:
            if not SHA256_RE.fullmatch(str(data[section][field])):
                fail("SPEECH_MANIFEST", f"invalid SHA-256: {section}.{field}", "restore the checked digest", 65)
    for section in ("whisper_model", "piper_voice"):
        for field, value in data[section].items():
            if field.endswith("url"):
                scheme = urllib.parse.urlsplit(str(value)).scheme
                if scheme != "https" and not (test_mode(root) and scheme == "file"):
                    fail("SPEECH_MANIFEST", f"unsafe artifact URL: {section}.{field}", "use HTTPS or an isolated file fixture", 65)
    for section, field in (("whisper_model", "id"), ("piper_voice", "id"), ("piper", "version"), ("whisper", "version")):
        if not SAFE_ID_RE.fullmatch(str(data[section][field])):
            fail("SPEECH_MANIFEST", f"unsafe identifier: {section}.{field}", "use a simple pinned identifier", 65)
    return data


def layout(root: Path, manifest: dict[str, Any]) -> dict[str, Path]:
    whisper_version = manifest["whisper"]["version"]
    piper_version = manifest["piper"]["version"]
    voice = manifest["piper_voice"]["id"]
    speech = rooted(root, Path("/usr/local/lib/gonken-speech"))
    state = rooted(root, Path("/var/lib/gonken-agent/install"))
    return {
        "whisper_releases": speech / "whisper/releases",
        "whisper_release": speech / f"whisper/releases/v{whisper_version}",
        "whisper_binary": speech / f"whisper/releases/v{whisper_version}/bin/whisper-cli",
        "whisper_stable": rooted(root, Path("/usr/local/bin/whisper-cli")),
        "piper_releases": speech / "piper/releases",
        "piper_release": speech / f"piper/releases/v{piper_version}",
        "piper_python": speech / f"piper/releases/v{piper_version}/.venv/bin/python",
        "piper_stable": rooted(root, Path("/usr/local/bin/piper")),
        "whisper_model": rooted(root, Path("/var/lib/gonken-agent/models/whisper")) / manifest["whisper_model"]["filename"],
        "voice_parent": rooted(root, Path("/var/lib/gonken-agent/models/piper")),
        "voice_dir": rooted(root, Path("/var/lib/gonken-agent/models/piper")) / voice,
        "voice_model": rooted(root, Path("/var/lib/gonken-agent/models/piper")) / voice / manifest["piper_voice"]["filename"],
        "voice_config": rooted(root, Path("/var/lib/gonken-agent/models/piper")) / voice / manifest["piper_voice"]["config_filename"],
        "voice_card": rooted(root, Path("/var/lib/gonken-agent/models/piper")) / voice / manifest["piper_voice"]["model_card_filename"],
        "record": state / "speech.record",
        "cache": rooted(root, Path("/var/cache/gonken-agent/speech")),
    }


def elf_machine(path: Path) -> int:
    with path.open("rb") as handle:
        header = handle.read(20)
    if len(header) < 20 or header[:4] != b"\x7fELF" or header[4] != 2 or header[5] not in (1, 2):
        fail("SPEECH_ARCH", f"not a 64-bit ELF executable: {path}", "install the pinned AArch64 build", 65)
    return int.from_bytes(header[18:20], "little" if header[5] == 1 else "big")


def validate_aarch64(path: Path, root: Path) -> str:
    if test_mode(root) and path.read_bytes()[:2] == b"#!":
        return "test-fixture"
    if elf_machine(path) != 183:
        fail("SPEECH_ARCH", f"binary is not AArch64: {path}", "rebuild or reinstall on the supported target", 65)
    return "aarch64"


def write_kv_record(path: Path, values: dict[str, str], fields: tuple[str, ...]) -> None:
    durable_bytes(path, "".join(f"{key}={values[key]}\n" for key in fields).encode(), 0o600)


def read_kv_record(path: Path, fields: tuple[str, ...], format_value: str) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        fail("SPEECH_RECORD", f"record is missing or unsafe: {path}", "rerun speech provisioning", 1)
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            fail("SPEECH_RECORD", "record contains a malformed line", "rerun speech provisioning", 75)
        key, value = line.split("=", 1)
        if key not in fields or key in values or "\r" in value:
            fail("SPEECH_RECORD", "record contains an unknown or duplicate field", "rerun speech provisioning", 75)
        values[key] = value
    if set(values) != set(fields) or values["format"] != format_value:
        fail("SPEECH_RECORD", "record schema differs", "rerun speech provisioning", 75)
    return values


def _safe_extract(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:") as bundle:
        members = bundle.getmembers()
        for member in members:
            target = Path(member.name)
            if target.is_absolute() or ".." in target.parts or member.issym() or member.islnk() or member.isdev():
                fail("WHISPER_SOURCE", "source archive contains an unsafe member", "review the pinned upstream source", 65)
        bundle.extractall(destination, members=members, filter="data")


def validate_whisper(root: Path, manifest: dict[str, Any]) -> dict[str, str]:
    paths = layout(root, manifest)
    record = read_kv_record(paths["whisper_release"] / "artifact.record", ("format", "version", "commit", "binary_sha256", "architecture"), "gonken-whisper-runtime-v1")
    binary = paths["whisper_binary"]
    if not binary.is_file() or binary.is_symlink() or not os.access(binary, os.X_OK):
        fail("WHISPER_RUNTIME", "Whisper executable is missing or unsafe", "rerun Whisper provisioning", 1)
    if record["version"] != manifest["whisper"]["version"] or record["commit"] != manifest["whisper"]["commit"] or record["binary_sha256"] != sha256_file(binary):
        fail("WHISPER_RUNTIME", "Whisper runtime identity differs", "rebuild from the pinned source", 1)
    architecture = validate_aarch64(binary, root)
    if record["architecture"] != architecture:
        fail("WHISPER_RUNTIME", "Whisper architecture record differs", "rebuild the runtime", 1)
    expected_target = os.path.relpath(binary, paths["whisper_stable"].parent)
    if not paths["whisper_stable"].is_symlink() or os.readlink(paths["whisper_stable"]) != expected_target:
        fail("WHISPER_RUNTIME", "Whisper stable entrypoint differs", "rerun Whisper provisioning", 1)
    return record


def install_whisper(root: Path, manifest: dict[str, Any], git: Path, cmake: Path) -> None:
    paths = layout(root, manifest)
    ensure_directory(paths["whisper_releases"])
    if paths["whisper_release"].exists() or paths["whisper_release"].is_symlink():
        try:
            validate_whisper(root, manifest)
            print(f"[OK] code=WHISPER_ALREADY_VALID version={manifest['whisper']['version']}")
            return
        except SpeechError:
            if paths["whisper_release"].is_dir() and not paths["whisper_release"].is_symlink():
                paths["whisper_release"].chmod(0o755)
                remove_owned(paths["whisper_release"], paths["whisper_releases"])
            else:
                raise
    workspace = Path(tempfile.mkdtemp(prefix=".candidate.whisper.", dir=paths["whisper_releases"]))
    candidate = workspace / "release"
    (candidate / "bin").mkdir(parents=True)
    try:
        fixture = os.environ.get("GONKEN_SPEECH_TEST_WHISPER_BINARY") if test_mode(root) else None
        maybe_interrupt("whisper_source", "before")
        if fixture:
            fixture_path = require_absolute(fixture, "Whisper test fixture")
            if not fixture_path.is_file():
                fail("WHISPER_SOURCE", "test fixture is missing", "provide an executable fixture", 65)
            source_binary = fixture_path
            maybe_interrupt("whisper_source", "during")
        else:
            repository = str(manifest["whisper"]["repository"])
            if urllib.parse.urlsplit(repository).scheme != "https":
                fail("WHISPER_SOURCE", "production source repository must use HTTPS", "restore the official repository URL", 65)
            bare = workspace / "source.git"
            archive = workspace / "source.tar"
            source = workspace / "source"
            source.mkdir()
            print(f"[RUNNING] code=WHISPER_SOURCE_FETCH version={manifest['whisper']['version']}", flush=True)
            run([str(git), "init", "--bare", "--quiet", str(bare)])
            run([str(git), f"--git-dir={bare}", "fetch", "--quiet", "--depth=1", "--", repository, manifest["whisper"]["release_tag"]])
            fetched = run([str(git), f"--git-dir={bare}", "rev-parse", "FETCH_HEAD^{commit}"]).stdout.strip().lower()
            if fetched != manifest["whisper"]["commit"]:
                fail("WHISPER_SOURCE", "release tag no longer resolves to the pinned commit", "review upstream drift and repin deliberately", 75)
            tree = run([str(git), f"--git-dir={bare}", "ls-tree", "-r", fetched]).stdout
            if any(line.startswith("160000 ") for line in tree.splitlines()):
                fail("WHISPER_SOURCE", "source contains an unadmitted submodule", "pin all source inputs explicitly", 65)
            run([str(git), f"--git-dir={bare}", "archive", "--format=tar", f"--output={archive}", fetched])
            _safe_extract(archive, source)
            maybe_interrupt("whisper_source", "during")
            maybe_interrupt("whisper_build", "before")
            build = workspace / "build"
            arguments = [str(cmake), "-S", str(source), "-B", str(build), *manifest["whisper"]["cmake_arguments"]]
            print(f"[RUNNING] code=WHISPER_BUILD phase=configure version={manifest['whisper']['version']}", flush=True)
            run(arguments)
            print(f"[RUNNING] code=WHISPER_BUILD phase=compile jobs=2 target=whisper-cli", flush=True)
            run([str(cmake), "--build", str(build), "--config", "Release", "--parallel", "2", "--target", "whisper-cli"])
            source_binary = build / "bin/whisper-cli"
            maybe_interrupt("whisper_build", "during")
        if not source_binary.is_file() or not os.access(source_binary, os.X_OK):
            fail("WHISPER_BUILD", "build did not produce an executable whisper-cli", "inspect the pinned build", 74)
        shutil.copy2(source_binary, candidate / "bin/whisper-cli")
        binary = candidate / "bin/whisper-cli"
        binary.chmod(0o755)
        architecture = validate_aarch64(binary, root)
        run([str(binary), "--help"], timeout=30)
        record = {
            "format": "gonken-whisper-runtime-v1", "version": manifest["whisper"]["version"],
            "commit": manifest["whisper"]["commit"], "binary_sha256": sha256_file(binary),
            "architecture": architecture,
        }
        write_kv_record(candidate / "artifact.record", record, tuple(record))
        maybe_interrupt("whisper_build", "after")
        maybe_interrupt("whisper_finalize", "before")
        freeze_tree(candidate, keep_root_writable=True)
        os.replace(candidate, paths["whisper_release"])
        paths["whisper_release"].chmod(0o555)
        maybe_interrupt("whisper_finalize", "during")
        atomic_symlink(paths["whisper_stable"], os.path.relpath(paths["whisper_binary"], paths["whisper_stable"].parent))
        maybe_interrupt("whisper_finalize", "after")
    finally:
        if workspace.exists() and not workspace.is_symlink():
            remove_tree(workspace)
    validate_whisper(root, manifest)
    print(f"[OK] code=WHISPER_INSTALLED version={manifest['whisper']['version']}")


def piper_lock(manifest_path: Path, manifest: dict[str, Any]) -> Path:
    relative = Path(manifest["piper"]["lock"])
    if relative.is_absolute() or ".." in relative.parts:
        fail("PIPER_LOCK", "Piper lock path is unsafe", "restore the release-local lock", 65)
    lock = manifest_path.parent.parent / relative
    if not lock.is_file() or lock.is_symlink() or sha256_file(lock) != manifest["piper"]["lock_sha256"]:
        fail("PIPER_LOCK", "Piper lock is missing or differs", "restore the exact generated lock", 65)
    text = lock.read_text(encoding="utf-8")
    if "--require-hashes" not in text or "--only-binary=:all:" not in text or f"piper-tts=={manifest['piper']['version']}" not in text:
        fail("PIPER_LOCK", "Piper lock lacks required policy", "regenerate the accepted binary-only hash lock", 65)
    return lock


def _piper_version(python: Path) -> str:
    return run([str(python), "-c", "import importlib.metadata; print(importlib.metadata.version('piper-tts'))"], timeout=60).stdout.strip()


def validate_piper(root: Path, manifest_path: Path, manifest: dict[str, Any]) -> dict[str, str]:
    paths = layout(root, manifest)
    lock = piper_lock(manifest_path, manifest)
    record = read_kv_record(paths["piper_release"] / "artifact.record", ("format", "version", "commit", "lock_sha256", "python_sha256", "native_architecture"), "gonken-piper-runtime-v1")
    python = paths["piper_python"]
    if not python.is_file() or not os.access(python, os.X_OK):
        fail("PIPER_RUNTIME", "Piper interpreter is missing or unsafe", "rerun Piper provisioning", 1)
    if record["version"] != manifest["piper"]["version"] or record["commit"] != manifest["piper"]["commit"] or record["lock_sha256"] != sha256_file(lock) or record["python_sha256"] != sha256_file(python):
        fail("PIPER_RUNTIME", "Piper runtime identity differs", "reinstall from the exact lock", 1)
    if _piper_version(python) != manifest["piper"]["version"]:
        fail("PIPER_RUNTIME", "installed Piper package version differs", "reinstall from the exact lock", 1)
    native = [item for item in paths["piper_release"].rglob("*.so") if item.is_file() and not item.is_symlink()]
    if test_mode(root) and not native:
        architecture = "test-fixture"
    else:
        if not native:
            fail("PIPER_ARCH", "Piper runtime has no native payload", "reinstall the AArch64 wheel set", 65)
        for item in native:
            validate_aarch64(item, root)
        architecture = "aarch64"
    if record["native_architecture"] != architecture:
        fail("PIPER_ARCH", "Piper architecture record differs", "reinstall the runtime", 1)
    wrapper = f"#!/bin/sh\nexec '{python}' -m piper \"$@\"\n".encode()
    if not paths["piper_stable"].is_file() or paths["piper_stable"].is_symlink() or paths["piper_stable"].read_bytes() != wrapper or not os.access(paths["piper_stable"], os.X_OK):
        fail("PIPER_RUNTIME", "Piper stable entrypoint differs", "rerun Piper provisioning", 1)
    return record


def install_piper(root: Path, manifest_path: Path, manifest: dict[str, Any]) -> None:
    paths = layout(root, manifest)
    lock = piper_lock(manifest_path, manifest)
    ensure_directory(paths["piper_releases"])
    if paths["piper_release"].exists() or paths["piper_release"].is_symlink():
        try:
            validate_piper(root, manifest_path, manifest)
            print(f"[OK] code=PIPER_ALREADY_VALID version={manifest['piper']['version']}")
            return
        except SpeechError:
            if paths["piper_release"].is_dir() and not paths["piper_release"].is_symlink():
                paths["piper_release"].chmod(0o755)
                remove_owned(paths["piper_release"], paths["piper_releases"])
            else:
                raise
    workspace = Path(tempfile.mkdtemp(prefix=".candidate.piper.", dir=paths["piper_releases"]))
    candidate = workspace / "release"
    candidate.mkdir()
    try:
        maybe_interrupt("piper_install", "before")
        fixture = os.environ.get("GONKEN_SPEECH_TEST_PIPER_PYTHON") if test_mode(root) else None
        if fixture:
            python = candidate / ".venv/bin/python"
            python.parent.mkdir(parents=True)
            shutil.copy2(require_absolute(fixture, "Piper test fixture"), python)
            python.chmod(0o755)
        else:
            print(f"[RUNNING] code=PIPER_INSTALL phase=venv version={manifest['piper']['version']}", flush=True)
            venv.EnvBuilder(with_pip=True, symlinks=True).create(candidate / ".venv")
            python = candidate / ".venv/bin/python"
            print(f"[RUNNING] code=PIPER_INSTALL phase=packages lock={lock.name}", flush=True)
            run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "--require-hashes", "--only-binary=:all:", "--requirement", str(lock)])
            run([str(python), "-m", "pip", "check"])
        maybe_interrupt("piper_install", "during")
        if _piper_version(python) != manifest["piper"]["version"]:
            fail("PIPER_RUNTIME", "candidate package version differs", "review the exact lock", 65)
        native = [item for item in candidate.rglob("*.so") if item.is_file() and not item.is_symlink()]
        if test_mode(root) and not native:
            architecture = "test-fixture"
        else:
            if not native:
                fail("PIPER_ARCH", "candidate has no native payload", "review wheel selection", 65)
            for item in native:
                validate_aarch64(item, root)
            architecture = "aarch64"
        record = {
            "format": "gonken-piper-runtime-v1", "version": manifest["piper"]["version"],
            "commit": manifest["piper"]["commit"], "lock_sha256": sha256_file(lock),
            "python_sha256": sha256_file(python), "native_architecture": architecture,
        }
        write_kv_record(candidate / "artifact.record", record, tuple(record))
        maybe_interrupt("piper_install", "after")
        maybe_interrupt("piper_finalize", "before")
        freeze_tree(candidate, keep_root_writable=True)
        os.replace(candidate, paths["piper_release"])
        paths["piper_release"].chmod(0o555)
        maybe_interrupt("piper_finalize", "during")
        wrapper = f"#!/bin/sh\nexec '{paths['piper_python']}' -m piper \"$@\"\n".encode()
        durable_bytes(paths["piper_stable"], wrapper, 0o755)
        maybe_interrupt("piper_finalize", "after")
    finally:
        if workspace.exists() and not workspace.is_symlink():
            remove_tree(workspace)
    validate_piper(root, manifest_path, manifest)
    print(f"[OK] code=PIPER_INSTALLED version={manifest['piper']['version']}")


def _download(url: str, destination: Path, digest: str, size: int, operation: str) -> None:
    ensure_directory(destination.parent)
    if destination.exists() and not destination.is_symlink() and destination.is_file() and destination.stat().st_size == size and sha256_file(destination) == digest:
        return
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            fail("SPEECH_DOWNLOAD", f"unsafe download path: {destination}", "move the conflict after administrator review", 75)
        destination.unlink()
    part = destination.parent / f".{destination.name}.part"
    if part.is_symlink() or (part.exists() and not part.is_file()):
        fail("SPEECH_DOWNLOAD", f"unsafe partial path: {part}", "move the conflict after administrator review", 75)
    offset = part.stat().st_size if part.exists() else 0
    if offset > size:
        part.unlink()
        offset = 0
    print(f"[RUNNING] code=SPEECH_DOWNLOAD operation={operation} artifact={destination.name} resume_bytes={offset} total={size}", flush=True)
    maybe_interrupt(operation, "before")
    request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            append = offset > 0 and getattr(response, "status", None) == 206
            with part.open("ab" if append else "wb") as handle:
                first = True
                downloaded = offset if append else 0
                last_percent = -1
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    percent = min(100, int(downloaded * 100 / size)) if size else 0
                    if percent >= last_percent + 10 or percent == 100:
                        print(f"[PROGRESS] code=SPEECH_DOWNLOAD operation={operation} artifact={destination.name} percent={percent} downloaded={downloaded} total={size}", flush=True)
                        last_percent = percent
                    if first:
                        maybe_interrupt(operation, "during")
                        first = False
                handle.flush()
                os.fsync(handle.fileno())
    except (OSError, urllib.error.URLError) as exc:
        fail("SPEECH_DOWNLOAD", f"artifact download failed: {exc}", "restore connectivity and rerun; the partial download is retained", 69)
    if part.stat().st_size != size or sha256_file(part) != digest:
        part.unlink()
        fail("SPEECH_CHECKSUM", f"download identity differs: {destination.name}", "review the immutable source and manifest before retrying", 75)
    os.replace(part, destination)
    maybe_interrupt(operation, "after")
    print(f"[OK] code=SPEECH_DOWNLOAD_COMPLETE operation={operation} artifact={destination.name} bytes={size}", flush=True)


def validate_models(root: Path, manifest: dict[str, Any], whisper_model_path: Path, piper_voice_path: Path) -> dict[str, str]:
    paths = layout(root, manifest)
    expected_whisper = rooted(root, whisper_model_path)
    expected_voice = rooted(root, piper_voice_path)
    if expected_whisper != paths["whisper_model"] or expected_voice != paths["voice_model"]:
        fail("SPEECH_CONFIG", "effective speech paths differ from the pinned artifact layout", "restore the authoritative defaults or repin deliberately", 65)
    checks = (
        (paths["whisper_model"], manifest["whisper_model"]["size"], manifest["whisper_model"]["sha256"]),
        (paths["voice_model"], manifest["piper_voice"]["size"], manifest["piper_voice"]["sha256"]),
        (paths["voice_config"], manifest["piper_voice"]["config_size"], manifest["piper_voice"]["config_sha256"]),
        (paths["voice_card"], manifest["piper_voice"]["model_card_size"], manifest["piper_voice"]["model_card_sha256"]),
    )
    for path, size, digest in checks:
        if not path.is_file() or path.is_symlink() or path.stat().st_size != size or sha256_file(path) != digest:
            fail("SPEECH_MODEL", f"artifact is missing or differs: {path}", "rerun model provisioning", 1)
    try:
        config = json.loads(paths["voice_config"].read_text(encoding="utf-8"))
        sample_rate = config["audio"]["sample_rate"]
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        fail("PIPER_CONFIG", "voice configuration is malformed", "redownload the checked pair", 65)
    if not isinstance(sample_rate, int) or sample_rate < 8000 or sample_rate > 96000:
        fail("PIPER_CONFIG", "voice sample rate is invalid", "review the pinned voice configuration", 65)
    return {"sample_rate": str(sample_rate)}


def provision_models(root: Path, manifest: dict[str, Any], whisper_model_path: Path, piper_voice_path: Path) -> None:
    paths = layout(root, manifest)
    expected_whisper = rooted(root, whisper_model_path)
    expected_voice = rooted(root, piper_voice_path)
    if expected_whisper != paths["whisper_model"] or expected_voice != paths["voice_model"]:
        fail("SPEECH_CONFIG", "effective speech paths differ from the pinned artifact layout", "restore the authoritative defaults", 65)
    _download(manifest["whisper_model"]["url"], paths["whisper_model"], manifest["whisper_model"]["sha256"], manifest["whisper_model"]["size"], "whisper_model_download")
    ensure_directory(paths["voice_parent"])
    if paths["voice_dir"].exists() or paths["voice_dir"].is_symlink():
        try:
            validate_models(root, manifest, whisper_model_path, piper_voice_path)
            print(f"[OK] code=SPEECH_MODELS_ALREADY_VALID voice={manifest['piper_voice']['id']}")
            return
        except SpeechError:
            if paths["voice_dir"].is_dir() and not paths["voice_dir"].is_symlink():
                paths["voice_dir"].chmod(0o755)
                remove_owned(paths["voice_dir"], paths["voice_parent"])
            else:
                raise
    candidate = Path(tempfile.mkdtemp(prefix=f".candidate.{manifest['piper_voice']['id']}.", dir=paths["voice_parent"]))
    try:
        voice = manifest["piper_voice"]
        _download(voice["url"], candidate / voice["filename"], voice["sha256"], voice["size"], "piper_pair_download")
        _download(voice["config_url"], candidate / voice["config_filename"], voice["config_sha256"], voice["config_size"], "piper_pair_download")
        _download(voice["model_card_url"], candidate / voice["model_card_filename"], voice["model_card_sha256"], voice["model_card_size"], "piper_pair_download")
        config = json.loads((candidate / voice["config_filename"]).read_text(encoding="utf-8"))
        if not isinstance(config.get("audio", {}).get("sample_rate"), int):
            fail("PIPER_CONFIG", "candidate voice config lacks a sample rate", "review the pinned voice pair", 65)
        maybe_interrupt("piper_pair_finalize", "before")
        freeze_tree(candidate, keep_root_writable=True)
        os.replace(candidate, paths["voice_dir"])
        paths["voice_dir"].chmod(0o555)
        maybe_interrupt("piper_pair_finalize", "during")
        maybe_interrupt("piper_pair_finalize", "after")
    finally:
        if candidate.exists() and not candidate.is_symlink():
            remove_tree(candidate)
    validate_models(root, manifest, whisper_model_path, piper_voice_path)
    print(f"[OK] code=SPEECH_MODELS_INSTALLED voice={manifest['piper_voice']['id']}")


def validate_wav(path: Path, expected_rate: int, minimum_frames: int, maximum_seconds: int) -> tuple[int, int]:
    try:
        with wave.open(str(path), "rb") as audio:
            frames, rate = audio.getnframes(), audio.getframerate()
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or rate != expected_rate:
                fail("PIPER_SMOKE", "TTS WAV format differs", "inspect Piper and voice compatibility", 69)
    except (OSError, wave.Error, EOFError):
        fail("PIPER_SMOKE", "TTS output is not a valid WAV", "inspect Piper runtime output", 69)
    if frames < minimum_frames or frames > rate * maximum_seconds:
        fail("PIPER_SMOKE", "TTS WAV duration is outside the smoke bounds", "inspect synthesis output", 69)
    return rate, frames


def run_smoke(root: Path, manifest_path: Path, manifest: dict[str, Any], whisper_model_path: Path, piper_voice_path: Path, threads: int) -> None:
    whisper = validate_whisper(root, manifest)
    piper = validate_piper(root, manifest_path, manifest)
    model = validate_models(root, manifest, whisper_model_path, piper_voice_path)
    paths = layout(root, manifest)
    ensure_directory(paths["cache"], 0o700)
    maybe_interrupt("speech_smoke", "before")
    with tempfile.TemporaryDirectory(prefix="smoke.", dir=paths["cache"]) as temporary:
        work = Path(temporary)
        wav_path = work / "sample.wav"
        run([str(paths["piper_python"]), "-m", "piper", "--model", str(paths["voice_model"]), "--output_file", str(wav_path)], input_text=manifest["smoke"]["text"] + "\n", timeout=180)
        rate, frames = validate_wav(wav_path, int(model["sample_rate"]), manifest["smoke"]["minimum_wav_frames"], manifest["smoke"]["maximum_wav_seconds"])
        maybe_interrupt("speech_smoke", "during")
        output = work / "transcript"
        run([str(paths["whisper_binary"]), "-m", str(paths["whisper_model"]), "-f", str(wav_path), "-otxt", "-of", str(output), "-nt", "-np", "-t", str(threads)], timeout=300)
        transcript_path = Path(str(output) + ".txt")
        if not transcript_path.is_file():
            fail("WHISPER_SMOKE", "Whisper did not create its transcript", "inspect the pinned runtime/model", 69)
        words = set(re.findall(r"[a-z0-9]+", transcript_path.read_text(encoding="utf-8").lower()))
        required = [str(token).lower() for token in manifest["smoke"]["required_tokens"]]
        if not set(required).issubset(words):
            fail("WHISPER_SMOKE", "sample transcription omitted required tokens", "inspect STT accuracy and resource pressure", 69)
    values = {
        "format": "gonken-speech-install-v1",
        "whisper_version": manifest["whisper"]["version"],
        "whisper_binary_sha256": whisper["binary_sha256"],
        "whisper_model_sha256": manifest["whisper_model"]["sha256"],
        "piper_version": manifest["piper"]["version"],
        "piper_lock_sha256": piper["lock_sha256"],
        "piper_voice": manifest["piper_voice"]["id"],
        "piper_voice_sha256": manifest["piper_voice"]["sha256"],
        "piper_config_sha256": manifest["piper_voice"]["config_sha256"],
        "tts_sample_rate": str(rate), "tts_frames": str(frames),
        "stt_required_tokens": ",".join(required),
        "validated_epoch": str(int(time.time())), "validation": "passed",
    }
    write_kv_record(paths["record"], values, RECORD_FIELDS)
    maybe_interrupt("speech_smoke", "after")
    print(f"[OK] code=SPEECH_SMOKE_PASSED voice={manifest['piper_voice']['id']} rate={rate} frames={frames}")


def validate_smoke(root: Path, manifest_path: Path, manifest: dict[str, Any], whisper_model_path: Path, piper_voice_path: Path) -> dict[str, str]:
    whisper = validate_whisper(root, manifest)
    piper = validate_piper(root, manifest_path, manifest)
    model = validate_models(root, manifest, whisper_model_path, piper_voice_path)
    record = read_kv_record(layout(root, manifest)["record"], RECORD_FIELDS, "gonken-speech-install-v1")
    expected = {
        "whisper_version": manifest["whisper"]["version"], "whisper_binary_sha256": whisper["binary_sha256"],
        "whisper_model_sha256": manifest["whisper_model"]["sha256"], "piper_version": manifest["piper"]["version"],
        "piper_lock_sha256": piper["lock_sha256"], "piper_voice": manifest["piper_voice"]["id"],
        "piper_voice_sha256": manifest["piper_voice"]["sha256"], "piper_config_sha256": manifest["piper_voice"]["config_sha256"],
        "tts_sample_rate": model["sample_rate"], "stt_required_tokens": ",".join(str(token).lower() for token in manifest["smoke"]["required_tokens"]),
        "validation": "passed",
    }
    if any(record.get(key) != value for key, value in expected.items()) or not record["tts_frames"].isdigit() or not record["validated_epoch"].isdigit():
        fail("SPEECH_RECORD", "speech validation record differs from installed state", "rerun the speech smoke", 1)
    return record


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--manifest", required=True)
    common.add_argument("--system-root", default="/")
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("whisper-status", "install-whisper"):
        command = commands.add_parser(name, parents=[common])
        if name == "install-whisper":
            command.add_argument("--git", default="/usr/bin/git")
            command.add_argument("--cmake", default="/usr/bin/cmake")
    for name in ("piper-status", "install-piper"):
        commands.add_parser(name, parents=[common])
    for name in ("models-status", "provision-models", "smoke-status", "run-smoke"):
        command = commands.add_parser(name, parents=[common])
        command.add_argument("--whisper-model-path", required=True)
        command.add_argument("--piper-voice-path", required=True)
        if name == "run-smoke":
            command.add_argument("--threads", required=True, type=int)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = require_absolute(args.system_root, "system root")
        test_mode(root)
        if root == Path("/") and args.command.startswith(("install-", "provision-", "run-")) and os.geteuid() != 0:
            fail("SPEECH_PRIVILEGE", "production mutation requires root", "run through the validated bootstrap transition", 77)
        manifest_path = require_absolute(args.manifest, "artifact manifest")
        manifest = read_manifest(manifest_path, root)
        if args.command == "whisper-status":
            validate_whisper(root, manifest)
            print(f"[OK] code=WHISPER_HEALTHY version={manifest['whisper']['version']}")
        elif args.command == "install-whisper":
            install_whisper(root, manifest, require_absolute(args.git, "git executable"), require_absolute(args.cmake, "cmake executable"))
        elif args.command == "piper-status":
            validate_piper(root, manifest_path, manifest)
            print(f"[OK] code=PIPER_HEALTHY version={manifest['piper']['version']}")
        elif args.command == "install-piper":
            install_piper(root, manifest_path, manifest)
        else:
            whisper_model = require_absolute(args.whisper_model_path, "Whisper model path")
            piper_voice = require_absolute(args.piper_voice_path, "Piper voice path")
            if args.command == "models-status":
                validate_models(root, manifest, whisper_model, piper_voice)
                print(f"[OK] code=SPEECH_MODELS_HEALTHY voice={manifest['piper_voice']['id']}")
            elif args.command == "provision-models":
                provision_models(root, manifest, whisper_model, piper_voice)
            elif args.command == "run-smoke":
                if args.threads < 1 or args.threads > 16:
                    fail("SPEECH_CONFIG", "STT threads must be between 1 and 16", "use the resource-budgeted configuration", 65)
                run_smoke(root, manifest_path, manifest, whisper_model, piper_voice, args.threads)
            else:
                record = validate_smoke(root, manifest_path, manifest, whisper_model, piper_voice)
                print(f"[OK] code=SPEECH_HEALTHY voice={record['piper_voice']} validated_epoch={record['validated_epoch']}")
    except (SpeechError, KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as error:
        if not isinstance(error, SpeechError):
            error = SpeechError("SPEECH_MANIFEST", f"invalid manifest value: {error}", "restore the accepted manifest", 65)
        emit_error(error)
        return error.status
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
