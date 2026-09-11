#!/usr/bin/env python3
"""Install and verify the pinned Ollama runtime and GonKen chat model.

Only Python's standard library is used. Production operations are restricted to
the real filesystem root; isolated roots and injected failures require an
explicit test gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
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
from pathlib import Path, PurePosixPath


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DIGEST_PREFIX_RE = re.compile(r"^[0-9a-f]{12}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
MODEL_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9_.-]+$")
RECORD_FIELDS = (
    "format", "ollama_version", "ollama_asset", "ollama_sha256",
    "binary_sha256", "unit_sha256", "dropin_sha256", "endpoint",
    "model", "model_digest", "model_digest_prefix", "quantization",
    "parameter_size", "context_tokens", "max_loaded_models",
    "num_parallel", "no_cloud", "pull_total_bytes", "smoke_total_ns",
    "smoke_eval_count", "validated_epoch", "validation",
)


class OllamaError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, exit_code: int = 74):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.exit_code = exit_code


def fail(code: str, message: str, remediation: str, exit_code: int = 74) -> None:
    raise OllamaError(code, message, remediation, exit_code)


def emit_error(error: OllamaError) -> None:
    print(f"[ERROR] code={error.code} message={error} remediation={error.remediation}", file=sys.stderr)


def require_absolute(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or "\n" in value or "\r" in value or ".." in path.parts:
        fail("OLLAMA_PATH", f"{label} must be an absolute normalized path", "supply a safe absolute path", 64)
    return path


def mapped(root: Path, absolute: str) -> Path:
    return Path(absolute) if root == Path("/") else root / absolute.lstrip("/")


def test_mode(root: Path) -> bool:
    enabled = os.environ.get("GONKEN_ENABLE_TEST_FAILURES") == "1"
    if root != Path("/") and not enabled:
        fail("OLLAMA_TEST_GATE", "redirected system roots require the explicit test gate", "set GONKEN_ENABLE_TEST_FAILURES=1 only in an isolated test", 77)
    return enabled


def maybe_interrupt(operation: str, point: str) -> None:
    if os.environ.get("GONKEN_ENABLE_TEST_FAILURES") != "1":
        return
    if os.environ.get("GONKEN_OLLAMA_TEST_INTERRUPT") != f"{operation}:{point}":
        return
    mode = os.environ.get("GONKEN_OLLAMA_TEST_INTERRUPT_MODE", "term")
    chosen = signal.SIGTERM if mode == "term" else signal.SIGKILL if mode == "kill" else None
    if chosen is None:
        fail("OLLAMA_TEST_CONTROL", "unknown interruption mode", "use term or kill", 64)
    os.kill(os.getppid(), chosen)
    os.kill(os.getpid(), chosen)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def binary_payload_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*"), key=lambda entry: entry.relative_to(path).as_posix()):
        relative = item.relative_to(path).as_posix()
        if relative == "artifact.record":
            continue
        if item.is_symlink():
            kind, payload = b"link", os.readlink(item).encode()
        elif item.is_dir():
            kind, payload = b"directory", b""
        elif item.is_file():
            kind, payload = b"file", item.read_bytes()
        else:
            fail("OLLAMA_BINARY", f"unsupported release object: {relative}", "rebuild the pinned release", 74)
        digest.update(kind + b"\0" + relative.encode() + b"\0" + payload + b"\0")
    return digest.hexdigest()


def durable_bytes(path: Path, payload: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        fail("OLLAMA_LAYOUT", f"destination is a symlink: {path}", "remove the unsafe path after inspection", 73)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def read_manifest(path: Path, root: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        fail("OLLAMA_MANIFEST", "artifact manifest is missing or unsafe", "restore it from the active immutable release", 65)
    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        fail("OLLAMA_MANIFEST", f"cannot parse artifact manifest: {exc}", "restore the exact release input", 65)
    expected_top = {"format", "verified_at", "ollama", "model"}
    expected_ollama = {"version", "release_tag", "platform", "asset", "url", "sha256", "license", "source"}
    expected_model = {"tag", "digest_prefix", "quantization", "parameter_size", "display_size", "license", "source"}
    if set(parsed) != expected_top or parsed.get("format") != "gonken-ollama-artifacts-v1":
        fail("OLLAMA_MANIFEST", "manifest top-level schema differs", "use the supported exact manifest", 65)
    if not isinstance(parsed.get("ollama"), dict) or set(parsed["ollama"]) != expected_ollama:
        fail("OLLAMA_MANIFEST", "Ollama artifact schema differs", "use the supported exact manifest", 65)
    if not isinstance(parsed.get("model"), dict) or set(parsed["model"]) != expected_model:
        fail("OLLAMA_MANIFEST", "model artifact schema differs", "use the supported exact manifest", 65)
    values = {**{f"ollama_{k}": str(v) for k, v in parsed["ollama"].items()}, **{f"model_{k}": str(v) for k, v in parsed["model"].items()}}
    if (
        not VERSION_RE.fullmatch(values["ollama_version"])
        or values["ollama_release_tag"] != f"v{values['ollama_version']}"
        or values["ollama_platform"] != "linux-arm64"
        or not SHA256_RE.fullmatch(values["ollama_sha256"])
        or not MODEL_RE.fullmatch(values["model_tag"])
        or not DIGEST_PREFIX_RE.fullmatch(values["model_digest_prefix"])
        or values["model_quantization"] != "Q4_K_M"
    ):
        fail("OLLAMA_MANIFEST", "manifest identity or digest fields are invalid", "review and repin official artifacts", 65)
    url = urllib.parse.urlparse(values["ollama_url"])
    if url.scheme != "https" and not (test_mode(root) and url.scheme == "file"):
        fail("OLLAMA_MANIFEST", "artifact URL is not approved HTTPS", "use an official HTTPS URL", 65)
    return values


def validate_endpoint(endpoint: str) -> str:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        fail("OLLAMA_ENDPOINT", "Ollama endpoint must be an unauthenticated loopback HTTP origin", "set the effective endpoint to http://127.0.0.1:11434", 65)
    if parsed.port is None:
        fail("OLLAMA_ENDPOINT", "Ollama endpoint must include an explicit port", "set the effective loopback port", 65)
    return endpoint.rstrip("/")


def layout(root: Path, version: str) -> dict[str, Path]:
    base = mapped(root, "/usr/local/lib/ollama")
    return {
        "base": base,
        "releases": base / "releases",
        "release": base / "releases" / f"v{version}",
        "current": base / "current",
        "stable": mapped(root, "/usr/local/bin/ollama"),
        "cache": mapped(root, "/var/cache/gonken-agent/downloads"),
        "record": mapped(root, "/var/lib/gonken-agent/install/ollama.record"),
        "unit": mapped(root, "/etc/systemd/system/ollama.service"),
        "dropin": mapped(root, "/etc/systemd/system/ollama.service.d/gonken-agent.conf"),
    }


def ensure_directory(path: Path, mode: int) -> None:
    if path.is_symlink():
        fail("OLLAMA_LAYOUT", f"unsafe directory symlink: {path}", "replace it with a real administrator-owned directory", 73)
    path.mkdir(parents=True, exist_ok=True, mode=mode)
    if not path.is_dir() or path.is_symlink():
        fail("OLLAMA_LAYOUT", f"not a real directory: {path}", "repair the installation layout", 73)
    path.chmod(mode)


def remove_candidate(path: Path, releases: Path) -> None:
    if path.parent != releases or not path.name.startswith(".candidate.v") or path.is_symlink():
        fail("OLLAMA_LAYOUT", f"refusing unsafe candidate cleanup: {path}", "inspect it manually", 75)
    if not path.exists():
        return
    for directory in [path, *[item for item in path.rglob("*") if item.is_dir() and not item.is_symlink()]]:
        directory.chmod(0o700)
    shutil.rmtree(path)


def run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(arguments, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")[:400]
        fail("OLLAMA_COMMAND", f"command failed ({result.returncode}): {detail or arguments[0]}", "inspect installer events and rerun", result.returncode if 1 <= result.returncode <= 125 else 74)
    return result


def binary_version(binary: Path) -> str:
    if not binary.is_file() or binary.is_symlink() or not os.access(binary, os.X_OK):
        fail("OLLAMA_BINARY", "Ollama binary is missing, linked, or not executable", "rerun verified binary installation", 74)
    result = run([str(binary), "--version"])
    output = result.stdout + result.stderr
    matches = re.findall(r"\b([0-9]+\.[0-9]+\.[0-9]+)\b", output)
    if len(set(matches)) != 1:
        fail("OLLAMA_BINARY", "cannot establish one Ollama binary version", "inspect the installed executable", 74)
    return matches[0]


def _check_link(member: tarfile.TarInfo) -> None:
    target = PurePosixPath(member.linkname)
    if target.is_absolute():
        fail("OLLAMA_ARCHIVE", f"absolute link target: {member.name}", "use the pinned official archive", 65)
    combined = (PurePosixPath(member.name).parent / target) if member.issym() else target
    depth = 0
    for part in combined.parts:
        if part == "..":
            depth -= 1
        elif part not in {"", "."}:
            depth += 1
        if depth < 0:
            fail("OLLAMA_ARCHIVE", f"escaping link target: {member.name}", "use the pinned official archive", 65)


def safe_extract(archive: Path, destination: Path) -> None:
    try:
        with tarfile.open(archive, "r:") as bundle:
            members = bundle.getmembers()
            seen: set[str] = set()
            for member in members:
                name = PurePosixPath(member.name)
                normalized = name.as_posix().rstrip("/")
                if normalized in seen:
                    fail("OLLAMA_ARCHIVE", f"duplicate archive member: {member.name}", "use the pinned official archive", 65)
                seen.add(normalized)
                if name.is_absolute() or ".." in name.parts or member.isdev() or member.isfifo():
                    fail("OLLAMA_ARCHIVE", f"unsafe archive member: {member.name}", "use the pinned official archive", 65)
                if member.issym() or member.islnk():
                    _check_link(member)
                member.mode &= 0o755 if member.isdir() or member.mode & 0o111 else 0o644
                member.uid = os.geteuid()
                member.gid = os.getegid()
                member.uname = ""
                member.gname = ""
            bundle.extractall(destination, members=members, filter="data")
    except (tarfile.TarError, OSError) as exc:
        fail("OLLAMA_ARCHIVE", f"archive extraction failed: {exc}", "clear the verified cache only after inspection and rerun", 65)


def freeze_runtime_tree(path: Path, *, keep_root_writable: bool = False) -> None:
    """Make an immutable runtime tree service-readable regardless of caller umask."""
    for item in sorted(path.rglob("*"), key=lambda entry: len(entry.parts), reverse=True):
        if item.is_symlink():
            continue
        mode = stat.S_IMODE(item.stat().st_mode)
        if item.is_dir():
            item.chmod(0o555)
        elif item.is_file():
            item.chmod(0o555 if mode & 0o111 else 0o444)
        else:
            fail("OLLAMA_BINARY", f"unsupported runtime filesystem object: {item}", "rebuild the pinned release", 74)
    path.chmod(0o755 if keep_root_writable else 0o555)


def _download(url: str, destination: Path, expected: str) -> None:
    if destination.is_symlink():
        fail("OLLAMA_DOWNLOAD", "download cache path is a symlink", "remove the unsafe path after inspection", 73)
    if destination.is_file() and sha256_file(destination) == expected:
        return
    partial = destination.with_suffix(destination.suffix + ".part")
    offset = partial.stat().st_size if partial.is_file() and not partial.is_symlink() else 0
    print(f"[RUNNING] code=OLLAMA_DOWNLOAD artifact={destination.name} resume_bytes={offset}", flush=True)
    maybe_interrupt("binary_download", "before")
    parsed = urllib.parse.urlparse(url)
    try:
        if parsed.scheme == "file":
            source = Path(urllib.request.url2pathname(parsed.path))
            handle = source.open("rb")
            handle.seek(offset)
            response = handle
        else:
            request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
            response = urllib.request.urlopen(request, timeout=60)
            if offset and getattr(response, "status", 200) != 206:
                response.close()
                offset = 0
                response = urllib.request.urlopen(url, timeout=60)
            if urllib.parse.urlparse(response.geturl()).scheme != "https":
                response.close()
                fail("OLLAMA_DOWNLOAD", "artifact redirect left HTTPS", "use an end-to-end HTTPS official artifact URL", 65)
        mode = "ab" if offset else "wb"
        with response, partial.open(mode) as output:
            interrupted = False
            downloaded = offset
            next_report = ((downloaded // (64 * 1024 * 1024)) + 1) * (64 * 1024 * 1024)
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                downloaded += len(block)
                output.flush()
                os.fsync(output.fileno())
                if downloaded >= next_report:
                    print(f"[PROGRESS] code=OLLAMA_DOWNLOAD artifact={destination.name} downloaded_mib={downloaded // (1024 * 1024)}", flush=True)
                    next_report += 64 * 1024 * 1024
                if not interrupted:
                    interrupted = True
                    maybe_interrupt("binary_download", "during")
        maybe_interrupt("binary_download", "after")
    except (OSError, urllib.error.URLError) as exc:
        fail("OLLAMA_DOWNLOAD", f"artifact download failed: {exc}", "restore networking and rerun; the partial download is retained", 69)
    if sha256_file(partial) != expected:
        partial.unlink(missing_ok=True)
        fail("OLLAMA_CHECKSUM", "downloaded artifact checksum differs", "do not install it; verify the official release and manifest", 65)
    os.replace(partial, destination)
    print(f"[OK] code=OLLAMA_DOWNLOAD_COMPLETE artifact={destination.name} bytes={destination.stat().st_size}", flush=True)


def _atomic_symlink(path: Path, target: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not path.is_symlink():
        fail("OLLAMA_LAYOUT", f"managed link conflicts with a real path: {path}", "move the administrator-owned conflict after review", 73)
    if path.is_symlink() and os.readlink(path) == target:
        return
    temporary = path.parent / f".{path.name}.{os.getpid()}"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    os.replace(temporary, path)


def validate_binary_payload(release: Path, manifest: dict[str, str]) -> dict[str, str]:
    release_binary = release / "bin/ollama"
    release_record = release / "artifact.record"
    payload_digest = binary_payload_sha256(release)
    expected = f"format=gonken-ollama-binary-v1\nversion={manifest['ollama_version']}\nasset_sha256={manifest['ollama_sha256']}\nbinary_sha256={sha256_file(release_binary)}\npayload_sha256={payload_digest}\n"
    if not release_record.is_file() or release_record.is_symlink() or release_record.read_text(encoding="utf-8") != expected:
        fail("OLLAMA_BINARY", "binary artifact record differs", "rebuild the pinned release", 74)
    if binary_version(release_binary) != manifest["ollama_version"]:
        fail("OLLAMA_BINARY", "installed binary version differs from the manifest", "quarantine the release and review the pin", 74)
    for item in [release, *release.rglob("*")]:
        if not item.is_symlink() and stat.S_IMODE(item.stat().st_mode) & 0o222:
            fail("OLLAMA_BINARY", "immutable Ollama release contains a writable path", "restore from the pinned artifact", 74)
    return {"binary_sha256": sha256_file(release_binary)}


def validate_binary(root: Path, manifest: dict[str, str]) -> dict[str, str]:
    paths = layout(root, manifest["ollama_version"])
    expected_current = f"releases/v{manifest['ollama_version']}"
    expected_stable = os.path.relpath(paths["current"] / "bin/ollama", paths["stable"].parent)
    if not paths["current"].is_symlink() or os.readlink(paths["current"]) != expected_current:
        fail("OLLAMA_BINARY", "current Ollama release pointer differs", "rerun verified binary installation", 74)
    if not paths["stable"].is_symlink() or os.readlink(paths["stable"]) != expected_stable:
        fail("OLLAMA_BINARY", "stable Ollama entrypoint differs", "remove conflicts and rerun", 74)
    return validate_binary_payload(paths["release"], manifest)


def install_binary(root: Path, manifest: dict[str, str], zstd: Path) -> None:
    if root == Path("/") and (os.geteuid() != 0 or platform.machine() != "aarch64" or platform.system() != "Linux"):
        fail("OLLAMA_PLATFORM", "production Ollama installation requires root on Linux aarch64", "run through bootstrap on the supported Raspberry Pi", 77)
    paths = layout(root, manifest["ollama_version"])
    try:
        validate_binary(root, manifest)
        print(f"[OK] code=OLLAMA_BINARY_ALREADY_VALID version={manifest['ollama_version']}")
        return
    except OllamaError as error:
        if paths["release"].exists() or paths["release"].is_symlink():
            if not paths["release"].is_dir() or paths["release"].is_symlink():
                raise error
            try:
                validate_binary_payload(paths["release"], manifest)
            except OllamaError as payload_error:
                # Recover only the narrow rename-to-top-chmod interval. All
                # descendants and the recorded payload must already be exact.
                release = paths["release"]
                descendants = [item for item in release.rglob("*") if not item.is_symlink()]
                if (
                    payload_error.code != "OLLAMA_BINARY"
                    or stat.S_IMODE(release.stat().st_mode) != 0o755
                    or any(stat.S_IMODE(item.stat().st_mode) & 0o222 for item in descendants)
                    or any(item.stat().st_uid != os.geteuid() for item in [release, *descendants])
                ):
                    raise payload_error
                release.chmod(0o555)
                validate_binary_payload(release, manifest)
            _atomic_symlink(paths["current"], f"releases/v{manifest['ollama_version']}")
            _atomic_symlink(paths["stable"], os.path.relpath(paths["current"] / "bin/ollama", paths["stable"].parent))
            validate_binary(root, manifest)
            print(f"[OK] code=OLLAMA_BINARY_RECOVERED version={manifest['ollama_version']}")
            return
    ensure_directory(paths["releases"], 0o755)
    ensure_directory(paths["stable"].parent, 0o755)
    ensure_directory(paths["cache"], 0o755)
    for stale in paths["releases"].glob(f".candidate.v{manifest['ollama_version']}.*"):
        if stale.is_dir() and not stale.is_symlink() and stale.parent == paths["releases"]:
            remove_candidate(stale, paths["releases"])
        else:
            fail("OLLAMA_LAYOUT", f"unsafe stale candidate: {stale}", "inspect it manually", 75)
    free_kib = shutil.disk_usage(paths["releases"]).free // 1024
    if test_mode(root) and os.environ.get("GONKEN_OLLAMA_TEST_FREE_KIB"):
        free_kib = int(os.environ["GONKEN_OLLAMA_TEST_FREE_KIB"])
    if free_kib < 4194304:
        fail("OLLAMA_SPACE", f"Ollama installation requires 4194304 KiB headroom; found {free_kib}", "free storage and rerun", 78)
    asset = paths["cache"] / manifest["ollama_asset"]
    _download(manifest["ollama_url"], asset, manifest["ollama_sha256"])
    workspace = Path(tempfile.mkdtemp(prefix=f".candidate.v{manifest['ollama_version']}.", dir=paths["releases"]))
    archive = workspace / "payload.tar"
    candidate = workspace / "release"
    candidate.mkdir()
    try:
        maybe_interrupt("binary_extract", "before")
        run([str(zstd), "-d", "-f", str(asset), "-o", str(archive)])
        safe_extract(archive, candidate)
        maybe_interrupt("binary_extract", "during")
        binary = candidate / "bin/ollama"
        if binary_version(binary) != manifest["ollama_version"]:
            fail("OLLAMA_BINARY", "candidate binary version differs", "review the pinned archive", 65)
        payload_digest = binary_payload_sha256(candidate)
        record = (
            "format=gonken-ollama-binary-v1\n"
            f"version={manifest['ollama_version']}\n"
            f"asset_sha256={manifest['ollama_sha256']}\n"
            f"binary_sha256={sha256_file(binary)}\n"
            f"payload_sha256={payload_digest}\n"
        )
        (candidate / "artifact.record").write_text(record, encoding="utf-8")
        # Normalize readability/traversal explicitly so a restrictive caller
        # umask can never produce a root-only runtime tree.
        freeze_runtime_tree(candidate, keep_root_writable=True)
        maybe_interrupt("binary_finalize", "before")
        os.replace(candidate, paths["release"])
        maybe_interrupt("binary_finalize", "during")
        paths["release"].chmod(0o555)
        maybe_interrupt("binary_finalize", "after")
        maybe_interrupt("binary_extract", "after")
    finally:
        if workspace.exists() and not workspace.is_symlink():
            remove_candidate(workspace, paths["releases"])
    _atomic_symlink(paths["current"], f"releases/v{manifest['ollama_version']}")
    _atomic_symlink(paths["stable"], os.path.relpath(paths["current"] / "bin/ollama", paths["stable"].parent))
    validate_binary(root, manifest)
    print(f"[OK] code=OLLAMA_BINARY_INSTALLED version={manifest['ollama_version']}")


def _api(endpoint: str, path: str, payload: dict[str, object] | None = None, *, stream: bool = False):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(endpoint + path, data=body, headers={"Content-Type": "application/json"} if body is not None else {}, method="POST" if body is not None else "GET")
    try:
        response = urllib.request.urlopen(request, timeout=120)
        if stream:
            return response
        with response:
            return json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        fail("OLLAMA_API", f"Ollama API request failed for {path}: {exc}", "inspect the loopback service and journal", 69)


def wait_ready(endpoint: str, version: str, attempts: int = 60) -> None:
    maybe_interrupt("service_ready", "before")
    last = "no response"
    for attempt in range(attempts):
        try:
            payload = _api(endpoint, "/api/version")
            if attempt == 0:
                maybe_interrupt("service_ready", "during")
            if isinstance(payload, dict) and payload.get("version") == version:
                maybe_interrupt("service_ready", "after")
                return
            last = f"unexpected version: {payload!r}"
        except OllamaError as error:
            last = str(error)
        time.sleep(0.1 if os.environ.get("GONKEN_ENABLE_TEST_FAILURES") == "1" else 1)
    fail("OLLAMA_READINESS", f"Ollama did not become ready: {last}", "inspect systemctl status and journalctl -u ollama.service", 69)


def _render_dropin(template: bytes, endpoint: str, context_tokens: int) -> bytes:
    host = urllib.parse.urlparse(endpoint).netloc
    text = template.decode("utf-8").replace("@OLLAMA_HOST@", host).replace("@CONTEXT_TOKENS@", str(context_tokens))
    if "@" in text or f'Environment="OLLAMA_HOST={host}"' not in text:
        fail("OLLAMA_SERVICE", "service drop-in template was not rendered exactly", "restore the active release template", 65)
    return text.encode()


def service_files(root: Path, endpoint: str, context_tokens: int, unit_template: Path, dropin_template: Path) -> tuple[bytes, bytes]:
    for path in (unit_template, dropin_template):
        if not path.is_file() or path.is_symlink():
            fail("OLLAMA_SERVICE", "service template is missing or unsafe", "restore the active immutable release", 65)
    return unit_template.read_bytes(), _render_dropin(dropin_template.read_bytes(), endpoint, context_tokens)


def _systemctl(systemctl: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    if not systemctl.is_absolute():
        fail("OLLAMA_SERVICE", "systemctl path must be absolute", "use /usr/bin/systemctl", 64)
    return run([str(systemctl), *arguments])


def install_service(root: Path, manifest: dict[str, str], endpoint: str, context_tokens: int, unit_template: Path, dropin_template: Path, systemctl: Path) -> None:
    validate_binary(root, manifest)
    paths = layout(root, manifest["ollama_version"])
    unit, dropin = service_files(root, endpoint, context_tokens, unit_template, dropin_template)
    for destination, payload in ((paths["unit"], unit), (paths["dropin"], dropin)):
        if destination.exists() and (not destination.is_file() or destination.is_symlink() or destination.read_bytes() != payload):
            fail("OLLAMA_SERVICE_CONFLICT", f"existing service file differs: {destination}", "review and remove or migrate it explicitly", 75)
        if not destination.exists():
            durable_bytes(destination, payload)
    _systemctl(systemctl, "daemon-reload")
    _systemctl(systemctl, "enable", "--now", "ollama.service")
    wait_ready(endpoint, manifest["ollama_version"])
    print(f"[OK] code=OLLAMA_SERVICE_READY endpoint={endpoint}")


def validate_service(root: Path, manifest: dict[str, str], endpoint: str, context_tokens: int, unit_template: Path, dropin_template: Path, systemctl: Path) -> dict[str, str]:
    paths = layout(root, manifest["ollama_version"])
    unit, dropin = service_files(root, endpoint, context_tokens, unit_template, dropin_template)
    if not paths["unit"].is_file() or paths["unit"].is_symlink() or paths["unit"].read_bytes() != unit:
        fail("OLLAMA_SERVICE", "installed system unit differs", "restore it from the active release", 74)
    if not paths["dropin"].is_file() or paths["dropin"].is_symlink() or paths["dropin"].read_bytes() != dropin:
        fail("OLLAMA_SERVICE", "installed system drop-in differs", "restore it from the active release", 74)
    _systemctl(systemctl, "is-enabled", "--quiet", "ollama.service")
    _systemctl(systemctl, "is-active", "--quiet", "ollama.service")
    wait_ready(endpoint, manifest["ollama_version"], attempts=2)
    return {"unit_sha256": hashlib.sha256(unit).hexdigest(), "dropin_sha256": hashlib.sha256(dropin).hexdigest()}


def installed_model(endpoint: str, model: str, prefix: str) -> dict[str, object] | None:
    payload = _api(endpoint, "/api/tags")
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        fail("OLLAMA_MODEL", "model list response is malformed", "inspect the local Ollama API", 69)
    matches = [item for item in models if isinstance(item, dict) and item.get("name") == model]
    if not matches:
        return None
    if len(matches) != 1:
        fail("OLLAMA_MODEL", "model tag is ambiguous in the local store", "inspect and repair the model store", 75)
    item = matches[0]
    digest = item.get("digest")
    details = item.get("details")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest) or not digest.startswith(prefix):
        fail("OLLAMA_MODEL_DIGEST", "local model digest does not match the admitted catalog prefix", "do not run it; review upstream tag drift and repin deliberately", 75)
    if not isinstance(details, dict) or details.get("quantization_level") != "Q4_K_M":
        fail("OLLAMA_MODEL", "local model quantization differs from Q4_K_M", "remove the unapproved variant and rerun", 75)
    return item


def pull_model(endpoint: str, model: str) -> int:
    print(f"[RUNNING] code=OLLAMA_MODEL_PULL model={model}", flush=True)
    maybe_interrupt("model_pull", "before")
    response = _api(endpoint, "/api/pull", {"model": model, "stream": True}, stream=True)
    total = 0
    completed = 0
    last_percent = -1
    seen_success = False
    try:
        for index, line in enumerate(response):
            if index == 0:
                maybe_interrupt("model_pull", "during")
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("non-object event")
            if isinstance(event.get("total"), int):
                total = max(total, event["total"])
            if isinstance(event.get("completed"), int):
                completed = max(completed, event["completed"])
            if total > 0 and completed >= 0:
                percent = min(100, int(completed * 100 / total))
                if percent >= last_percent + 5 or percent == 100:
                    print(f"[PROGRESS] code=OLLAMA_MODEL_PULL model={model} percent={percent} completed={completed} total={total}", flush=True)
                    last_percent = percent
            status = event.get("status")
            if isinstance(status, str) and status and total == 0:
                print(f"[RUNNING] code=OLLAMA_MODEL_PULL model={model} status={status.replace(' ', '_')}", flush=True)
            if status == "success":
                seen_success = True
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        fail("OLLAMA_PULL", f"model pull stream failed: {exc}", "restore connectivity and rerun; Ollama resumes blobs", 69)
    finally:
        response.close()
    if not seen_success:
        fail("OLLAMA_PULL", "model pull did not report success", "inspect the service journal and rerun", 69)
    maybe_interrupt("model_pull", "after")
    print(f"[OK] code=OLLAMA_MODEL_PULL_COMPLETE model={model} total={total}", flush=True)
    return total


def smoke_model(endpoint: str, model: str, context_tokens: int) -> dict[str, int]:
    print(f"[RUNNING] code=OLLAMA_MODEL_SMOKE model={model} think=false", flush=True)
    maybe_interrupt("model_smoke", "before")
    payload = _api(endpoint, "/api/chat", {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with the single word ready."}],
        "stream": False,
        "think": False,
        "keep_alive": 0,
        "options": {"temperature": 0, "num_ctx": context_tokens, "num_predict": 8, "seed": 0},
    })
    maybe_interrupt("model_smoke", "during")
    message = payload.get("message") if isinstance(payload, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("done") is not True
        or not isinstance(content, str)
        or not content.strip()
    ):
        reason = payload.get("done_reason") if isinstance(payload, dict) else "malformed"
        thinking = message.get("thinking") if isinstance(message, dict) else None
        fail(
            "OLLAMA_SMOKE",
            f"deterministic non-thinking inference smoke did not complete (done_reason={reason}, thinking_present={bool(thinking)})",
            "inspect memory pressure and the Ollama journal",
            69,
        )
    metrics = {"total_ns": int(payload.get("total_duration", 0)), "eval_count": int(payload.get("eval_count", 0))}
    maybe_interrupt("model_smoke", "after")
    print(f"[OK] code=OLLAMA_MODEL_SMOKE model={model} eval_count={metrics['eval_count']}", flush=True)
    return metrics


def read_install_record(path: Path) -> dict[str, str] | None:
    if not path.exists() and not path.is_symlink():
        return None
    if not path.is_file() or path.is_symlink():
        fail("OLLAMA_RECORD", "install record is missing or unsafe", "restore the private root-owned record", 75)
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            fail("OLLAMA_RECORD", "install record contains a malformed line", "restore it from a verified run", 75)
        key, value = line.split("=", 1)
        if key not in RECORD_FIELDS or key in result or "\r" in value:
            fail("OLLAMA_RECORD", "install record has an unknown or duplicate field", "restore it from a verified run", 75)
        result[key] = value
    if set(result) != set(RECORD_FIELDS) or result.get("format") != "gonken-ollama-install-v1":
        fail("OLLAMA_RECORD", "install record schema differs", "restore it from a verified run", 75)
    return result


def validate_install_record(
    record: dict[str, str], manifest: dict[str, str], endpoint: str,
    model: str, context_tokens: int, binary: dict[str, str], service: dict[str, str],
) -> None:
    expected = {
        "ollama_version": manifest["ollama_version"],
        "ollama_asset": manifest["ollama_asset"],
        "ollama_sha256": manifest["ollama_sha256"],
        "binary_sha256": binary["binary_sha256"],
        "unit_sha256": service["unit_sha256"],
        "dropin_sha256": service["dropin_sha256"],
        "endpoint": endpoint,
        "model": model,
        "model_digest_prefix": manifest["model_digest_prefix"],
        "quantization": manifest["model_quantization"],
        "parameter_size": manifest["model_parameter_size"],
        "context_tokens": str(context_tokens),
        "max_loaded_models": "1",
        "num_parallel": "1",
        "no_cloud": "1",
        "validation": "passed",
    }
    if any(record.get(key) != value for key, value in expected.items()):
        fail("OLLAMA_RECORD", "install record differs from the effective validated state", "rerun provisioning or investigate configuration drift", 75)
    for field in ("pull_total_bytes", "smoke_total_ns", "smoke_eval_count", "validated_epoch"):
        if not record[field].isdigit():
            fail("OLLAMA_RECORD", f"install record has invalid numeric field: {field}", "restore it from a verified run", 75)
    if not SHA256_RE.fullmatch(record["model_digest"]) or not record["model_digest"].startswith(manifest["model_digest_prefix"]):
        fail("OLLAMA_RECORD", "recorded full model digest is invalid", "restore it from a verified run", 75)


def write_install_record(path: Path, values: dict[str, str]) -> None:
    payload = "".join(f"{key}={values[key]}\n" for key in RECORD_FIELDS).encode()
    durable_bytes(path, payload, 0o600)


def provision_model(root: Path, manifest: dict[str, str], endpoint: str, model: str, context_tokens: int, unit_template: Path, dropin_template: Path, systemctl: Path) -> None:
    if model != manifest["model_tag"]:
        fail("OLLAMA_MODEL", "effective chat model differs from the authoritative artifact manifest", "set GONKEN_CHAT_MODEL to the admitted tag", 65)
    binary = validate_binary(root, manifest)
    service = validate_service(root, manifest, endpoint, context_tokens, unit_template, dropin_template, systemctl)
    paths = layout(root, manifest["ollama_version"])
    ensure_directory(paths["record"].parent, 0o700)
    record = read_install_record(paths["record"])
    item = installed_model(endpoint, model, manifest["model_digest_prefix"])
    pull_bytes = 0
    if item is None:
        if shutil.disk_usage(paths["record"].parent).free // 1024 < 4194304 and not test_mode(root):
            fail("OLLAMA_MODEL_SPACE", "model pull requires at least 4194304 KiB free", "free model storage and rerun", 78)
        pull_bytes = pull_model(endpoint, model)
        item = installed_model(endpoint, model, manifest["model_digest_prefix"])
        if item is None:
            fail("OLLAMA_MODEL", "model remains absent after a successful pull", "inspect the Ollama model store and journal", 69)
    digest = str(item["digest"])
    if record is not None and record["model_digest"] != digest:
        fail("OLLAMA_MODEL_DRIFT", "recorded full model digest changed for the same tag", "review upstream drift and repin in a new milestone", 75)
    metrics = smoke_model(endpoint, model, context_tokens)
    values = {
        "format": "gonken-ollama-install-v1",
        "ollama_version": manifest["ollama_version"],
        "ollama_asset": manifest["ollama_asset"],
        "ollama_sha256": manifest["ollama_sha256"],
        "binary_sha256": binary["binary_sha256"],
        "unit_sha256": service["unit_sha256"],
        "dropin_sha256": service["dropin_sha256"],
        "endpoint": endpoint,
        "model": model,
        "model_digest": digest,
        "model_digest_prefix": manifest["model_digest_prefix"],
        "quantization": manifest["model_quantization"],
        "parameter_size": manifest["model_parameter_size"],
        "context_tokens": str(context_tokens),
        "max_loaded_models": "1",
        "num_parallel": "1",
        "no_cloud": "1",
        "pull_total_bytes": str(pull_bytes if record is None else record["pull_total_bytes"]),
        "smoke_total_ns": str(metrics["total_ns"]),
        "smoke_eval_count": str(metrics["eval_count"]),
        "validated_epoch": str(int(time.time())),
        "validation": "passed",
    }
    write_install_record(paths["record"], values)
    print(f"[OK] code=OLLAMA_MODEL_READY model={model} digest={digest}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--manifest", required=True)
    common.add_argument("--system-root", default="/")
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("binary-status", "install-binary"):
        command = commands.add_parser(name, parents=[common])
        if name == "install-binary":
            command.add_argument("--zstd", default="/usr/bin/zstd")
    for name in ("service-status", "install-service", "model-status", "provision-model"):
        command = commands.add_parser(name, parents=[common])
        command.add_argument("--endpoint", required=True)
        command.add_argument("--context-tokens", required=True, type=int)
        command.add_argument("--unit-template", required=True)
        command.add_argument("--dropin-template", required=True)
        command.add_argument("--systemctl", default="/usr/bin/systemctl")
        if name in {"model-status", "provision-model"}:
            command.add_argument("--model", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = require_absolute(args.system_root, "system root")
        test_mode(root)
        if root == Path("/") and args.command in {"install-binary", "install-service", "provision-model"} and os.geteuid() != 0:
            fail("OLLAMA_PRIVILEGE", "production mutation requires root", "run through the validated bootstrap privilege transition", 77)
        manifest = read_manifest(require_absolute(args.manifest, "artifact manifest"), root)
        if args.command == "binary-status":
            validate_binary(root, manifest)
            print(f"[OK] code=OLLAMA_BINARY_VALID version={manifest['ollama_version']}")
        elif args.command == "install-binary":
            install_binary(root, manifest, require_absolute(args.zstd, "zstd executable"))
        else:
            endpoint = validate_endpoint(args.endpoint)
            if args.context_tokens < 512 or args.context_tokens > 8192:
                fail("OLLAMA_CONTEXT", "context tokens must be between 512 and 8192", "use the resource-budgeted configuration", 65)
            unit = require_absolute(args.unit_template, "unit template")
            dropin = require_absolute(args.dropin_template, "drop-in template")
            systemctl = require_absolute(args.systemctl, "systemctl")
            if args.command == "install-service":
                install_service(root, manifest, endpoint, args.context_tokens, unit, dropin, systemctl)
            elif args.command == "service-status":
                validate_binary(root, manifest)
                validate_service(root, manifest, endpoint, args.context_tokens, unit, dropin, systemctl)
                print(f"[OK] code=OLLAMA_SERVICE_HEALTHY endpoint={endpoint}")
            elif args.command == "provision-model":
                provision_model(root, manifest, endpoint, args.model, args.context_tokens, unit, dropin, systemctl)
            else:
                paths = layout(root, manifest["ollama_version"])
                record = read_install_record(paths["record"])
                binary = validate_binary(root, manifest)
                service = validate_service(root, manifest, endpoint, args.context_tokens, unit, dropin, systemctl)
                item = installed_model(endpoint, args.model, manifest["model_digest_prefix"])
                if record is None or item is None or record["validation"] != "passed" or record["model_digest"] != item["digest"]:
                    fail("OLLAMA_MODEL", "installed model state is incomplete or differs", "rerun model provisioning", 1)
                validate_install_record(record, manifest, endpoint, args.model, args.context_tokens, binary, service)
                print(f"[OK] code=OLLAMA_MODEL_HEALTHY model={args.model} digest={item['digest']}")
    except OllamaError as error:
        emit_error(error)
        return error.exit_code
    except (OSError, ValueError) as error:
        emit_error(OllamaError("OLLAMA_IO", str(error), "inspect filesystem ownership, space, and installed state", 73))
        return 73
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
