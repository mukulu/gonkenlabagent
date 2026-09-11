#!/usr/bin/env python3
"""Explicitly update GonKenLab Agent through immutable release activation."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_SOURCE_URL = "https://github.com/mukulu/gonkenlabagent.git"
DEFAULT_REF = "main"
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class UpdateError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, exit_code: int = 74):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.exit_code = exit_code


def fail(code: str, message: str, remediation: str, exit_code: int = 74) -> None:
    raise UpdateError(code, message, remediation, exit_code)


def emit_error(error: UpdateError) -> None:
    print(f"[ERROR] code={error.code} message={error} remediation={error.remediation}", file=sys.stderr)


def require_absolute(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or "\n" in value or "\r" in value or ".." in path.parts:
        fail("UPDATE_PATH", f"{label} must be an absolute normalized path", "supply a safe absolute path", 64)
    return path


def validate_source(source_url: str, ref: str) -> None:
    if not REF_RE.fullmatch(ref) or ref.endswith("/") or "//" in ref:
        fail("UPDATE_REF", "source ref is not a safe branch or tag name", "use a named branch or tag", 64)
    if source_url.startswith("https://"):
        if "@" in source_url.partition("://")[2].partition("/")[0] or any(ch in source_url for ch in "?#\r\n"):
            fail("UPDATE_SOURCE", "HTTPS source URL is not an unauthenticated repository URL", "use the public repository URL", 64)
        return
    if source_url.startswith("file:///") and os.environ.get("GONKEN_ENABLE_TEST_FAILURES") == "1":
        return
    fail("UPDATE_SOURCE", "updates require HTTPS source URL outside isolated tests", "use the public repository URL", 64)


def run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(arguments, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")[:400]
        fail("UPDATE_COMMAND", f"command failed ({result.returncode}): {detail or arguments[0]}", "inspect update output and rerun", result.returncode if 1 <= result.returncode <= 125 else 74)
    return result


def resolve_ref(source_url: str, ref: str) -> str:
    validate_source(source_url, ref)
    output = run(["git", "ls-remote", "--heads", "--tags", source_url, ref, f"refs/heads/{ref}", f"refs/tags/{ref}"]).stdout
    commits: set[str] = set()
    for line in output.splitlines():
        if not line:
            continue
        commit, name = line.split("\t", 1)
        if name.endswith("^{}"):
            name = name[:-3]
        if name in {ref, f"refs/heads/{ref}", f"refs/tags/{ref}"}:
            if not COMMIT_RE.fullmatch(commit.lower()):
                fail("UPDATE_SOURCE", "remote ref resolved to an invalid commit", "inspect the remote repository", 69)
            commits.add(commit.lower())
    if len(commits) != 1:
        fail("UPDATE_REF", "source ref is missing or ambiguous", "use an unambiguous branch or tag", 69)
    return commits.pop()


def active_commit(release_manager, release_root: Path) -> str | None:
    return release_manager.current_commit(release_root)


def update(
    release_root: Path,
    state_root: Path,
    source_url: str,
    ref: str,
    profile: str,
    service_user: str,
    systemctl: Path,
    restart: bool,
) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import release_manager  # type: ignore

    release_manager.reconcile(release_root, state_root, service_user)
    commit = resolve_ref(source_url, ref)
    current = active_commit(release_manager, release_root)
    if current == commit:
        release_manager.status(release_root, state_root, commit, service_user)
        print(f"[OK] code=UPDATE_ALREADY_CURRENT commit={commit}")
        return
    release_manager.build_release(source_url, ref, commit, release_root, profile, service_user)
    with release_manager.maintenance_lock(state_root):
        release_manager.activate(release_root, state_root, commit, service_user)
        release_manager.prune_releases(release_root, state_root, service_user)
    if restart:
        run([str(systemctl), "restart", "gonken-agent.service"])
    print(f"[OK] code=UPDATE_COMPLETE commit={commit} previous={current or 'none'}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--release-root", default="/usr/local/lib/gonken-agent")
    result.add_argument("--state-root", default="/var/lib/gonken-agent/install")
    result.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    result.add_argument("--ref", default=DEFAULT_REF)
    result.add_argument("--profile", default="core-pi-trixie-py313")
    result.add_argument("--service-user", default="gonken-agent")
    result.add_argument("--systemctl", default="/usr/bin/systemctl")
    result.add_argument("--no-restart", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        release_root = require_absolute(args.release_root, "release root")
        state_root = require_absolute(args.state_root, "state root")
        systemctl = require_absolute(args.systemctl, "systemctl")
        if release_root == Path("/usr/local/lib/gonken-agent") and os.geteuid() != 0:
            fail("UPDATE_PRIVILEGE", "production update requires root", "run through an explicit administrator transition", 77)
        update(
            release_root,
            state_root,
            args.source_url,
            args.ref,
            args.profile,
            args.service_user,
            systemctl,
            not args.no_restart,
        )
    except UpdateError as error:
        emit_error(error)
        return error.exit_code
    except Exception as error:
        emit_error(UpdateError("UPDATE_FAILED", str(error), "inspect update state and rerun", 74))
        return 74
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
