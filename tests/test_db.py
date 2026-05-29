import time

from toxi import db


def test_schema_creates_tables(tmp_path):
    conn = db.connect(tmp_path / "chat.db")
    tables = {row["name"] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"contacts", "messages", "pending_introductions"} <= tables


def test_connect_is_idempotent(tmp_path):
    p = tmp_path / "chat.db"
    db.connect(p).close()
    db.connect(p).close()  # second open must not raise


def test_insert_contact_and_message(tmp_path):
    conn = db.connect(tmp_path / "chat.db")
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO contacts (tox_id, public_key, alias, added_at, added_by) "
        "VALUES (?, ?, ?, ?, ?)",
        ("A" * 76, "A" * 64, "bob", now, "manual"),
    )
    contact_id = cur.lastrowid
    conn.execute(
        "INSERT INTO messages (msg_uuid, contact_id, direction, msg_type, content, "
        "created_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("uuid-1", contact_id, "out", "text", "hi", now, "queued"),
    )
    conn.commit()

    row = conn.execute("SELECT alias FROM contacts WHERE id=?", (contact_id,)).fetchone()
    assert row["alias"] == "bob"
    queued = conn.execute("SELECT COUNT(*) c FROM messages WHERE status='queued'").fetchone()
    assert queued["c"] == 1
