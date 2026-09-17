"""Runtime identity for immutable GonKen releases.

The runtime package location, not the Python executable target, is authoritative.
A venv interpreter may be a symlink to /usr/bin/python and resolving that symlink
must never erase the immutable release identity of the package that is executing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_MAX_RECORD_BYTES = 16_384


@dataclass(frozen=True, slots=True)
class RuntimeReleaseIdentity:
    commit: str
    profile: str
    release_dir: Path | None
    source: str

    @property
    def immutable(self) -> bool:
        return self.release_dir is not None and bool(_COMMIT_RE.fullmatch(self.commit))


def _release_directory_from_anchor(anchor: Path | str) -> Path | None:
    try:
        resolved = Path(anchor).resolve(strict=True)
    except OSError:
        return None
    candidates = (resolved, *resolved.parents)
    for candidate in candidates:
        if _COMMIT_RE.fullmatch(candidate.name) and candidate.parent.name == "releases":
            return candidate
    return None


def _release_profile(release: Path) -> str:
    record = release / "release.record"
    try:
        if not record.is_file() or record.is_symlink() or record.stat().st_size > _MAX_RECORD_BYTES:
            return "unknown"
        for line in record.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key == "profile" and _PROFILE_RE.fullmatch(value):
                return value
    except (OSError, UnicodeError):
        return "unknown"
    return "unknown"


def runtime_release_identity(*, package_anchor: Path | str | None = None) -> RuntimeReleaseIdentity:
    """Return identity of the immutable release containing this package.

    ``package_anchor`` exists for deterministic tests. Production callers omit it,
    making this installed module file the anchor.  Resolving the package path is
    safe because it remains underneath ``releases/<commit>`` even when the console
    script's venv interpreter ultimately resolves to a system Python binary.
    """
    anchor = Path(__file__) if package_anchor is None else Path(package_anchor)
    release = _release_directory_from_anchor(anchor)
    if release is None:
        return RuntimeReleaseIdentity(
            commit="development", profile="development", release_dir=None, source="package_path"
        )
    return RuntimeReleaseIdentity(
        commit=release.name,
        profile=_release_profile(release),
        release_dir=release,
        source="package_path",
    )
