"""Application-layer message envelope carried inside a Tox message (PRD §4.2.3).

Tox only moves opaque bytes between friends; all structure lives here as JSON:
    {"v": 1, "uuid": "...", "type": "text", "ts": 1716700000, "data": {...}}
"""
import json
import time
import uuid as _uuid

VERSION = 1


def text_envelope(uuid: str, ts: int, body: str) -> dict:
    return {"v": VERSION, "uuid": uuid, "type": "text", "ts": ts, "data": {"body": body}}


def make_text(body: str) -> dict:
    return text_envelope(str(_uuid.uuid4()), int(time.time()), body)


def make_ack(ref_uuid: str) -> dict:
    return {
        "v": VERSION,
        "uuid": str(_uuid.uuid4()),
        "type": "ack",
        "ts": int(time.time()),
        "data": {"ref_uuid": ref_uuid},
    }


def make_contact_share(tox_id: str, suggested_alias: str, note: str = "") -> dict:
    return {
        "v": VERSION,
        "uuid": str(_uuid.uuid4()),
        "type": "contact_share",
        "ts": int(time.time()),
        "data": {"tox_id": tox_id, "suggested_alias": suggested_alias, "note": note},
    }


def encode(envelope: dict) -> bytes:
    return json.dumps(envelope).encode("utf-8")


def parse(raw: bytes) -> dict:
    """Decode a received Tox message. Anything that isn't our JSON envelope
    (e.g. a plain message from another Tox client) is wrapped as a text message."""
    try:
        env = json.loads(raw.decode("utf-8"))
        if isinstance(env, dict) and "type" in env:
            env.setdefault("uuid", str(_uuid.uuid4()))
            env.setdefault("ts", int(time.time()))
            return env
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    return {
        "v": VERSION,
        "uuid": str(_uuid.uuid4()),
        "type": "text",
        "ts": int(time.time()),
        "data": {"body": raw.decode("utf-8", "replace")},
    }
