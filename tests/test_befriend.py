"""Milestone (step 4): two independent daemons befriend each other over the real
Tox DHT. Marked `dht` (slow, network-bound) — run with `pytest -m dht`.

Two daemons can't share one process (CLAUDE_CHAT_HOME is a single env var), so we
run each as its own subprocess with its own home and talk to each by socket path.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from claude_chat import client


def _sock(home: str) -> Path:
    return Path(home) / "daemon.sock"


def _req(home: str, method: str, params: dict | None = None):
    return client.request(method, params, sock_path=_sock(home))


def _start(home: str) -> subprocess.Popen:
    env = dict(os.environ, CLAUDE_CHAT_HOME=home)
    p = subprocess.Popen(
        [sys.executable, "-m", "claude_chat.daemon"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        if p.poll() is not None:
            raise RuntimeError("daemon exited during startup")
        try:
            _req(home, "get_status")
            return p
        except client.DaemonNotRunning:
            time.sleep(0.05)
    raise TimeoutError("daemon did not become ready")


def _stop(home: str, p: subprocess.Popen) -> None:
    try:
        _req(home, "shutdown")
    except Exception:
        pass
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()


def _poll(cond, seconds: float) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.5)
    return cond()


def _online(home: str, alias: str) -> bool:
    for c in _req(home, "list_contacts")["contacts"]:
        if c["alias"] == alias:
            return bool(c["is_online"])
    return False


def _add_and_accept(adder: str, target: str, adder_alias: str, target_alias: str) -> None:
    """`adder` adds `target` by Tox ID; `target` accepts. Blocks until both online."""
    target_id = _req(target, "get_me")["tox_id"]
    _req(adder, "add_contact", {"alias": adder_alias, "tox_id": target_id})
    # 120s: fresh-node DHT discovery can be slow, especially with several nodes
    # churning on one host (e.g. running the whole dht suite back-to-back).
    assert _poll(lambda: _req(target, "list_requests")["requests"], 120), "no friend request"
    pk = _req(target, "list_requests")["requests"][0]["public_key"]
    _req(target, "accept_request", {"alias": target_alias, "public_key": pk})
    assert _poll(lambda: _online(adder, adder_alias) and _online(target, target_alias), 120), \
        "link never came online"


def _befriend(home_a: str, home_b: str) -> None:
    """B adds A, A accepts B; block until both see the other online."""
    alice_id = _req(home_a, "get_me")["tox_id"]
    _req(home_b, "add_contact", {"alias": "alice", "tox_id": alice_id})
    assert _poll(lambda: _req(home_a, "list_requests")["requests"], 120), \
        "Alice never received the friend request"
    pk = _req(home_a, "list_requests")["requests"][0]["public_key"]
    _req(home_a, "accept_request", {"alias": "bob", "public_key": pk})

    def both_online():
        a = _req(home_a, "list_contacts")["contacts"]
        b = _req(home_b, "list_contacts")["contacts"]
        return a and a[0]["is_online"] and b and b[0]["is_online"]

    assert _poll(both_online, 120), "the friend link never came online"


@pytest.mark.dht
def test_two_daemons_befriend():
    home_a = tempfile.mkdtemp(prefix="cc-a-", dir="/tmp")
    home_b = tempfile.mkdtemp(prefix="cc-b-", dir="/tmp")
    pa = pb = None
    try:
        pa = _start(home_a)
        pb = _start(home_b)
        _befriend(home_a, home_b)

        assert _req(home_a, "list_contacts")["contacts"][0]["alias"] == "bob"
        assert _req(home_b, "list_contacts")["contacts"][0]["alias"] == "alice"
        # Alice accepted via a request, so she has no full Tox ID for Bob.
        assert _req(home_a, "list_contacts")["contacts"][0]["tox_id"] is None
    finally:
        if pb:
            _stop(home_b, pb)
        if pa:
            _stop(home_a, pa)
        shutil.rmtree(home_a, ignore_errors=True)
        shutil.rmtree(home_b, ignore_errors=True)


@pytest.mark.dht
def test_introduce_lets_bob_add_carol():
    """Step 8 milestone (PRD §8 metric ③): Alice introduces Carol to Bob, and Bob
    ends up connected to Carol."""
    homes = {n: tempfile.mkdtemp(prefix=f"cc-{n[0]}-", dir="/tmp")
             for n in ("alice", "bob", "carol")}
    procs = {}
    try:
        for n, h in homes.items():
            procs[n] = _start(h)
        a, b, c = homes["alice"], homes["bob"], homes["carol"]

        # Alice needs both as contacts, with their full Tox IDs (so she added them).
        _add_and_accept(a, b, "bob", "alice")
        _add_and_accept(a, c, "carol", "alice")

        # Alice introduces Carol to Bob.
        _req(a, "introduce", {"to_alias": "bob", "contact_alias": "carol", "note": "coworker"})
        assert _poll(lambda: _req(b, "list_introductions")["introductions"], 60), \
            "Bob never received the introduction"
        intro = _req(b, "list_introductions")["introductions"][0]
        assert intro["from_alias"] == "alice" and intro["suggested_alias"] == "carol"

        # Bob accepts → friend request goes to Carol; Carol accepts → they connect.
        _req(b, "accept_introduction", {"from_alias": "alice", "whom": "carol", "alias": "carol"})
        assert _poll(lambda: _req(c, "list_requests")["requests"], 90), \
            "Carol never received Bob's friend request"
        pk = _req(c, "list_requests")["requests"][0]["public_key"]
        _req(c, "accept_request", {"alias": "bob", "public_key": pk})
        assert _poll(lambda: _online(b, "carol") and _online(c, "bob"), 90), \
            "Bob and Carol never connected"
    finally:
        for n, h in homes.items():
            if procs.get(n):
                _stop(h, procs[n])
            shutil.rmtree(h, ignore_errors=True)


@pytest.mark.dht
def test_offline_queue_delivered_in_order():
    """Step 6 milestone (PRD §8 metric ②): 10 messages sent while Bob is offline
    are all delivered, in order, once he comes back online."""
    home_a = tempfile.mkdtemp(prefix="cc-a-", dir="/tmp")
    home_b = tempfile.mkdtemp(prefix="cc-b-", dir="/tmp")
    pa = pb = None
    try:
        pa = _start(home_a)
        pb = _start(home_b)
        _befriend(home_a, home_b)

        # Bob goes offline; wait until Alice actually notices (so sends queue).
        _stop(home_b, pb)
        pb = None
        assert _poll(
            lambda: not _req(home_a, "list_contacts")["contacts"][0]["is_online"], 90
        ), "Alice never saw Bob go offline"

        for i in range(10):
            res = _req(home_a, "send_message", {"alias": "bob", "body": f"msg-{i}"})
            assert res["status"] == "queued"
        assert len(_req(home_a, "list_queue")["queue"]) == 10

        # Bob comes back; Alice's reconnect callback should flush the queue.
        pb = _start(home_b)
        assert _poll(
            lambda: len(_req(home_b, "get_messages", {"limit": 100})["messages"]) == 10, 90
        ), "Bob did not receive all 10 messages"

        msgs = _req(home_b, "get_messages", {"limit": 100})["messages"]
        bodies = [m["content"] for m in reversed(msgs)]  # chronological
        assert bodies == [f"msg-{i}" for i in range(10)]
        assert _req(home_a, "list_queue")["queue"] == []
    finally:
        if pb:
            _stop(home_b, pb)
        if pa:
            _stop(home_a, pa)
        shutil.rmtree(home_a, ignore_errors=True)
        shutil.rmtree(home_b, ignore_errors=True)


@pytest.mark.dht
def test_online_message_round_trip():
    """Step 5 milestone: a live message from Alice reaches Bob and is stored."""
    home_a = tempfile.mkdtemp(prefix="cc-a-", dir="/tmp")
    home_b = tempfile.mkdtemp(prefix="cc-b-", dir="/tmp")
    pa = pb = None
    try:
        pa = _start(home_a)
        pb = _start(home_b)
        _befriend(home_a, home_b)

        res = _req(home_a, "send_message", {"alias": "bob", "body": "hello bob"})
        assert res["status"] == "sent"

        assert _poll(
            lambda: _req(home_b, "get_messages", {"unread_only": True})["messages"], 30
        ), "Bob never received the message"
        msgs = _req(home_b, "get_messages", {"unread_only": True})["messages"]
        assert msgs[0]["content"] == "hello bob"
        assert msgs[0]["alias"] == "alice"
        assert msgs[0]["direction"] == "in"

        # Bob's daemon ACKs; Alice's copy should flip sent -> delivered.
        assert _poll(
            lambda: _req(home_a, "get_messages", {"alias": "bob"})["messages"][0]["status"]
            == "delivered",
            30,
        ), "Alice never saw the message delivered"
    finally:
        if pb:
            _stop(home_b, pb)
        if pa:
            _stop(home_a, pa)
        shutil.rmtree(home_a, ignore_errors=True)
        shutil.rmtree(home_b, ignore_errors=True)
