import socket

import pytest

from claude_chat import ipc


def test_roundtrip():
    a, b = socket.socketpair()
    obj = {"id": "req-001", "method": "send_message", "params": {"alias": "bob", "body": "héllo 🌍"}}
    ipc.send_message(a, obj)
    assert ipc.recv_message(b) == obj


def test_two_frames_in_order():
    a, b = socket.socketpair()
    ipc.send_message(a, {"n": 1})
    ipc.send_message(a, {"n": 2})
    assert ipc.recv_message(b) == {"n": 1}
    assert ipc.recv_message(b) == {"n": 2}


def test_closed_connection_raises():
    a, b = socket.socketpair()
    a.close()
    with pytest.raises(ipc.IPCError):
        ipc.recv_message(b)


def test_oversized_frame_rejected():
    a, _ = socket.socketpair()
    with pytest.raises(ipc.IPCError):
        ipc.send_message(a, {"big": "x" * (ipc.MAX_FRAME + 1)})
