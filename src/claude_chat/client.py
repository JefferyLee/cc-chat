"""Minimal IPC client: one request, one response, close (PRD §3.2).

Used by the CLI and by tests to talk to the daemon over its Unix socket.
"""
import socket
from pathlib import Path

from . import ipc, paths


class DaemonNotRunning(Exception):
    pass


class DaemonError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def request(method: str, params: dict | None = None, *, sock_path: Path | None = None):
    sp = str(sock_path or paths.socket_path())
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5.0)
    try:
        s.connect(sp)
    except (FileNotFoundError, ConnectionRefusedError) as e:
        raise DaemonNotRunning("daemon is not running — start it with `cc-chat daemon start`") from e
    try:
        ipc.send_message(s, {"id": "1", "method": method, "params": params or {}})
        resp = ipc.recv_message(s)
    finally:
        s.close()

    if "error" in resp:
        err = resp["error"]
        raise DaemonError(err.get("code", "UNKNOWN"), err.get("message", ""))
    return resp["result"]
