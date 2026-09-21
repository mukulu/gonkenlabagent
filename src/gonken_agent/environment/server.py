"""AF_UNIX JSON server for the V09 environment protocol."""

from __future__ import annotations

import errno
import fcntl
import os
import socket
import socketserver
import stat
from pathlib import Path
from typing import Any

from .protocol import (
    MAX_REQUEST_BYTES,
    encode_response,
    make_error,
    make_success,
    parse_request_bytes,
)
from .service import EnvironmentServiceCore, EnvironmentServiceError


class EnvironmentRequestHandler(socketserver.StreamRequestHandler):
    """Handle exactly one bounded newline-delimited JSON request."""

    def handle(self) -> None:
        # An authorized but stalled client must not retain a thread indefinitely.
        self.request.settimeout(2.0)
        request = None
        try:
            line = self.rfile.readline(MAX_REQUEST_BYTES + 2)
            if not line:
                response = make_error("BAD_REQUEST", "empty request", daemon=self.server.core.daemon_metadata())
            elif len(line) > MAX_REQUEST_BYTES + 1:
                response = make_error("BAD_REQUEST", "request exceeds maximum size", daemon=self.server.core.daemon_metadata())
            else:
                request = parse_request_bytes(line.rstrip(b"\n"))
                result = self.server.core.handle(request)
                response = make_success(request, result, daemon=self.server.core.daemon_metadata())
        except EnvironmentServiceError as exc:
            response = make_error(exc.code, str(exc).split(": ", 1)[-1], request=request, daemon=self.server.core.daemon_metadata())
        except Exception as exc:
            code = getattr(exc, "code", "BAD_REQUEST")
            response = make_error(str(code), str(exc).split(": ", 1)[-1], request=request, daemon=self.server.core.daemon_metadata())
        self.wfile.write(encode_response(response) + b"\n")
        self.wfile.flush()


class EnvironmentUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    """Small local-only AF_UNIX server with a single service core."""

    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, socket_path: str | Path, core: EnvironmentServiceCore, *, socket_mode: int = 0o660) -> None:
        self.socket_path = Path(socket_path)
        self.core = core
        self.socket_mode = socket_mode
        self._closed = False
        self._socket_identity = None
        self._owner_lock = None
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = str(self.socket_path) + ".owner.lock"
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
                raise OSError("ENV_SOCKET_OWNER_LOCK_UNSAFE")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise OSError("ENV_SOCKET_ALREADY_OWNED") from exc
            self._owner_lock = descriptor
            _prepare_socket_path(self.socket_path)
            # Binding and chmod are protected by the lifetime owner lock.
            super().__init__(str(self.socket_path), EnvironmentRequestHandler, bind_and_activate=False)
            self.server_bind()
            self.server_activate()
            info = self.socket_path.lstat()
            self._socket_identity = (info.st_dev, info.st_ino)
            os.chmod(self.socket_path, self.socket_mode)
        except BaseException:
            if getattr(self, "socket", None) is not None:
                self.socket.close()
            self._unlink_owned_socket()
            os.close(descriptor)
            self._owner_lock = None
            raise

    def _unlink_owned_socket(self) -> None:
        try:
            info = self.socket_path.lstat()
            if (stat.S_ISSOCK(info.st_mode) and
                    (info.st_dev, info.st_ino) == self._socket_identity):
                self.socket_path.unlink()
        except FileNotFoundError:
            pass

    def server_close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            shutdown = getattr(self.core, "shutdown_safe_off", None)
            if callable(shutdown):
                shutdown()
        finally:
            try:
                super().server_close()
            finally:
                try:
                    self._unlink_owned_socket()
                finally:
                    if self._owner_lock is not None:
                        os.close(self._owner_lock)
                        self._owner_lock = None
                    # Never unlink the lock: doing so would allow two lock inodes.


def _prepare_socket_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(info.st_mode):
        raise OSError("ENV_SOCKET_PATH_UNSAFE")
    # Compatibility: an older daemon has no owner lock. Refuse to steal its live
    # socket. Only ECONNREFUSED proves a stale socket; permissions/timeouts do not.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        try:
            probe.connect(str(path))
        except OSError as exc:
            if exc.errno != errno.ECONNREFUSED:
                raise OSError("ENV_SOCKET_OWNERSHIP_UNCERTAIN") from exc
        else:
            raise OSError("ENV_SOCKET_ALREADY_OWNED")
    current = path.lstat()
    if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
        raise OSError("ENV_SOCKET_CHANGED_DURING_CHECK")
    path.unlink()


def _is_socket(path: Path) -> bool:
    try:
        return stat.S_ISSOCK(path.lstat().st_mode)
    except OSError:
        return False
