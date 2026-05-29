"""Tox binding tests.

The fast tests are offline (no DHT). The end-to-end DHT test is marked `dht`
and skipped by default — run it with `pytest -m dht`.
"""
import time

import pytest

from toxi.tox import Tox, ADDRESS_SIZE


def test_construct_and_address():
    t = Tox()
    try:
        addr = t.self_get_address()
        assert len(addr) == ADDRESS_SIZE
        assert len(t.self_get_address_hex()) == ADDRESS_SIZE * 2
    finally:
        t.kill()


def test_set_and_get_name():
    """tox_self_set_name is exactly what segfaulted in py-toxcore-c; works via ctypes."""
    t = Tox()
    try:
        assert t.self_get_name() == b""
        assert t.self_set_name(b"alice")
        assert t.self_get_name() == b"alice"
    finally:
        t.kill()


def test_savedata_persists_identity():
    """A Tox created from saved state must keep the same Tox ID (PRD §4.1.1)."""
    t = Tox()
    addr = t.self_get_address()
    savedata = t.get_savedata()
    t.kill()
    assert len(savedata) > 0

    t2 = Tox(savedata=savedata)
    try:
        assert t2.self_get_address() == addr
    finally:
        t2.kill()


BOOTSTRAP = [
    ("144.217.167.73", 33445, "7E5668E0EE09E19F320AD47902419331FFEE147BB3606769CFBE921A2A2FD34C"),
    ("139.162.110.188", 33445, "F76A11284547163889DDC89A7738CF271797BF5E5E220643E97AD3C7E7903D55"),
    ("205.185.115.131", 53, "3091C6BEB2A993F1C6300C16549FABA67098FF3D62C6D253828B531470B53D68"),
]


@pytest.mark.dht
def test_end_to_end_message_over_dht():
    """Two instances bootstrap, befriend, and exchange a message (PRD §8 metric)."""
    alice, bob = Tox(), Tox()
    received: list[bytes] = []

    def accept(pk, _msg):
        bob.friend_add_norequest(pk)

    state = {"alice_conn": False, "bob_conn": False,
             "alice_friend": False, "bob_friend": False}
    alice.on_self_connection_status(lambda s: state.__setitem__("alice_conn", s != 0))
    bob.on_self_connection_status(lambda s: state.__setitem__("bob_conn", s != 0))
    bob.on_friend_request(accept)
    alice.on_friend_connection_status(lambda fn, s: state.__setitem__("alice_friend", s != 0))
    bob.on_friend_connection_status(lambda fn, s: state.__setitem__("bob_friend", s != 0))
    bob.on_friend_message(lambda fn, msg, t: received.append(msg))

    for n in (alice, bob):
        for host, port, key in BOOTSTRAP:
            n.bootstrap(host, port, key)

    def pump(seconds, until):
        end = time.time() + seconds
        while time.time() < end:
            alice.iterate()
            bob.iterate()
            if until():
                return True
            time.sleep(0.05)
        return until()

    try:
        assert pump(90, lambda: state["alice_conn"] and state["bob_conn"]), "DHT not connected"
        fn = alice.friend_add(bob.self_get_address(), b"hi bob")
        # Friend discovery over the DHT is timing-sensitive and can spike well past
        # a minute, especially right after the nodes themselves connected.
        assert pump(120, lambda: state["alice_friend"] and state["bob_friend"]), "no friend link"
        alice.friend_send_message(fn, b"hello over Tox")
        assert pump(30, lambda: received), "message not received"
        assert received[0] == b"hello over Tox"
    finally:
        alice.kill()
        bob.kill()
