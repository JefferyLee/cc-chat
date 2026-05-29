"""SQLite storage (see PRD §4.1.2, §4.2.1, §4.5.2).

The daemon is the only writer; CLI clients reach the data through IPC, never by
opening this database directly.
"""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tox_id TEXT UNIQUE,                     -- 76-char full Tox ID; NULL when added via an
                                            -- accepted request (we only learn their public key)
    public_key TEXT NOT NULL UNIQUE,
    alias TEXT NOT NULL UNIQUE,
    display_name TEXT,
    status_message TEXT,
    added_at INTEGER NOT NULL,
    added_by TEXT,
    last_seen INTEGER,
    is_online BOOLEAN DEFAULT 0,
    friend_number INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_uuid TEXT NOT NULL UNIQUE,
    contact_id INTEGER NOT NULL,
    direction TEXT NOT NULL,
    msg_type TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    received_at INTEGER,
    status TEXT NOT NULL,
    delivered_at INTEGER,
    read_at INTEGER,
    last_attempt_at INTEGER,                -- when we last (re)sent; drives ACK-timeout retry
    FOREIGN KEY (contact_id) REFERENCES contacts(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_contact ON messages(contact_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_queue ON messages(contact_id, status, created_at)
    WHERE status = 'queued';

CREATE TABLE IF NOT EXISTS friend_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_key TEXT NOT NULL UNIQUE,        -- 64-char public key of the requester
    message TEXT,
    received_at INTEGER NOT NULL,
    status TEXT NOT NULL                     -- 'pending' / 'accepted' / 'rejected'
);

CREATE TABLE IF NOT EXISTS pending_introductions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_contact_id INTEGER NOT NULL,
    introduced_tox_id TEXT NOT NULL,
    suggested_alias TEXT,
    note TEXT,
    received_at INTEGER NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (from_contact_id) REFERENCES contacts(id)
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    """Open the database, applying schema and pragmas. Idempotent."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
