#!/usr/bin/env python3
"""Validate GonKen systemd/user-session runtime context without opening audio/GPIO/I2C devices.

This gate deliberately distinguishes structural service-context readiness from the later
physical appliance probe.  It can verify the dedicated service account, generated
XDG/DBus environment, no-login PipeWire user manager and optional Bluetooth session
without recording audio or starting the environment controller.
"""
from __future__ import annotations

import argparse
import json
import os
import pwd
import subprocess
import sys
from pathlib import Path
from typing import Any

RUNTIME_ENV = Path("/etc/gonken-agent/runtime-environment")
LINGER_DIR = Path("/var/lib/systemd/linger")


class RuntimeContextError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, status: int = 74):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.status = status


def fail(code: str, message: str, remediation: str, status: int = 74) -> None:
    raise RuntimeContextError(code, message, remediation, status)


def _run(args: list[str], *, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(args, 127, "", type(exc).__name__)


def _run_user(user: str, uid: int, args: list[str]) -> subprocess.CompletedProcess[str]:
    runtime = f"/run/user/{uid}"
    command = [
        "/usr/sbin/runuser", "-u", user, "--", "env",
        f"HOME={pwd.getpwnam(user).pw_dir}", f"USER={user}", f"LOGNAME={user}",
        f"XDG_RUNTIME_DIR={runtime}", f"DBUS_SESSION_BUS_ADDRESS=unix:path={runtime}/bus",
        *args,
    ]
    return _run(command)


def _runtime_env_expected(uid: int) -> str:
    return f"XDG_RUNTIME_DIR=/run/user/{uid}\nDBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus\n"


def inspect(*, audio_user: str, require_pipewire: bool, runtime_env: Path = RUNTIME_ENV, runtime_root: Path = Path("/run/user"), linger_dir: Path = LINGER_DIR, runner=_run, user_runner=_run_user) -> dict[str, Any]:
    try:
        account = pwd.getpwnam(audio_user)
    except KeyError:
        fail("RUNTIME_CONTEXT_USER_MISSING", f"service user does not exist: {audio_user}", "rerun installer account convergence", 73)
    uid = account.pw_uid
    runtime = runtime_root / str(uid)
    expected = _runtime_env_expected(uid)
    runtime_env_exact = False
    if runtime_env.is_file() and not runtime_env.is_symlink():
        try:
            runtime_env_exact = runtime_env.read_text(encoding="utf-8") == expected
        except OSError:
            runtime_env_exact = False

    runtime_dir_ready = False
    try:
        st = runtime.stat()
        runtime_dir_ready = runtime.is_dir() and not runtime.is_symlink() and st.st_uid == uid
    except OSError:
        pass

    linger = (linger_dir / audio_user).is_file()
    user_manager = runner(["/usr/bin/systemctl", "is-active", "--quiet", f"user@{uid}.service"]).returncode == 0

    pipewire = wireplumber = pulse = None
    if require_pipewire:
        pipewire = user_runner(audio_user, uid, ["systemctl", "--user", "is-active", "--quiet", "pipewire.service"]).returncode == 0
        wireplumber = user_runner(audio_user, uid, ["systemctl", "--user", "is-active", "--quiet", "wireplumber.service"]).returncode == 0
        pulse = user_runner(audio_user, uid, ["pactl", "info"]).returncode == 0

    structural = runtime_env_exact
    headless = runtime_dir_ready and linger and user_manager
    pipewire_ready = (pipewire is True and wireplumber is True and pulse is True) if require_pipewire else None
    ready = structural and (headless and pipewire_ready if require_pipewire else True)
    return {
        "format": "gonken-runtime-context-v1",
        "audio_user": audio_user,
        "uid": uid,
        "runtime_environment_exact": runtime_env_exact,
        "runtime_dir": str(runtime),
        "runtime_dir_ready": runtime_dir_ready,
        "linger_enabled": linger,
        "user_manager_active": user_manager,
        "pipewire_required": require_pipewire,
        "pipewire_active": pipewire,
        "wireplumber_active": wireplumber,
        "pulse_endpoint_ready": pulse,
        "ready": ready,
        "physical_audio_claimed": False,
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("status", nargs="?", default="status")
    p.add_argument("--audio-user", default="gonken-agent")
    p.add_argument("--require-pipewire", action="store_true")
    p.add_argument("--require-ready", action="store_true")
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        payload = inspect(audio_user=args.audio_user, require_pipewire=args.require_pipewire)
        if args.json:
            print(json.dumps(payload, sort_keys=True))
        else:
            print(
                f"[OK] code=RUNTIME_CONTEXT status={'READY' if payload['ready'] else 'NOT_READY'} "
                f"user={args.audio_user} runtime_env={str(payload['runtime_environment_exact']).lower()} "
                f"runtime_dir={str(payload['runtime_dir_ready']).lower()} linger={str(payload['linger_enabled']).lower()} "
                f"user_manager={str(payload['user_manager_active']).lower()} "
                f"pipewire_required={str(payload['pipewire_required']).lower()} physical_audio_claimed=false"
            )
        if args.require_ready and not payload["ready"]:
            fail(
                "RUNTIME_CONTEXT_NOT_READY",
                "service/user-session runtime context is incomplete",
                "rerun service/Bluetooth convergence and inspect the generated runtime environment and user manager",
                75,
            )
        return 0
    except RuntimeContextError as exc:
        print(f"[ERROR] code={exc.code} message={exc} remediation={exc.remediation}", file=sys.stderr)
        return exc.status


if __name__ == "__main__":
    raise SystemExit(main())
