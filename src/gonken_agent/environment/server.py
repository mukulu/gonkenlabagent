"""AF_UNIX JSON server for the V09 environment protocol."""

from __future__ import annotations

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
        _prepare_socket_path(self.socket_path)
        super().__init__(str(self.socket_path), EnvironmentRequestHandler)
        os.chmod(self.socket_path, self.socket_mode)

    def server_close(self) -> None:
        try:
            super().server_close()
        finally:
            try:
                if self.socket_path.exists() and _is_socket(self.socket_path):
                    self.socket_path.unlink()
            except OSError:
                pass


def _prepare_socket_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if not _is_socket(path):
            raise OSError(f"refusing to replace non-socket path: {path}")
        path.unlink()


def _is_socket(path: Path) -> bool:
    try:
        return stat.S_ISSOCK(path.stat().st_mode)
    except OSError:
        return False
