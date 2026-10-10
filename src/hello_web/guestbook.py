import math
import os
import re
import sqlite3
import unicodedata
from contextlib import closing
from datetime import UTC, datetime
from time import time

NAME_MAX = 50
MESSAGE_MAX = 500
POST_INTERVAL = 60  # seconds a client must wait between posts

# Control characters (tab and newline are kept) and invisible bidi overrides that can spoof how text reads.
_DISALLOWED = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")


def _clean(value: str, *, multiline: bool) -> str:
    value = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    if not multiline:
        value = value.replace("\n", " ")
    return _DISALLOWED.sub("", value).strip()


def validate(name: str, message: str) -> tuple[str, str, list[str]]:
    """Normalize the raw form input and return it with any validation errors.

    Text is stored as plain text, never as HTML; templates escape it on output.
    """
    name = _clean(name, multiline=False)
    message = _clean(message, multiline=True)
    errors = []
    if not name:
        errors.append("Please enter your name.")
    elif len(name) > NAME_MAX:
        errors.append(f"Name must be at most {NAME_MAX} characters.")
    if not message:
        errors.append("Please write a message.")
    elif len(message) > MESSAGE_MAX:
        errors.append(f"Message must be at most {MESSAGE_MAX} characters.")
    return name, message, errors


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(os.environ.get("GUESTBOOK_DB", "guestbook.db"))
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS entries ("
        "id INTEGER PRIMARY KEY, name TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS last_posts (client TEXT PRIMARY KEY, posted_at REAL NOT NULL)"
    )
    return conn


def add_entry(client: str, name: str, message: str) -> int:
    """Store the entry unless `client` posted within the last POST_INTERVAL seconds.

    Returns 0 when the entry was stored, otherwise the seconds left until the client may post again.
    """
    now = time()
    created_at = datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%d %H:%M UTC")
    with closing(_connect()) as conn, conn:
        # Forget clients whose wait is over, so the table only ever holds the last minute's posters.
        conn.execute("DELETE FROM last_posts WHERE posted_at <= ?", (now - POST_INTERVAL,))
        # The primary key makes claiming the slot atomic, even for concurrent requests.
        claimed = conn.execute(
            "INSERT INTO last_posts (client, posted_at) VALUES (?, ?) ON CONFLICT (client) DO NOTHING",
            (client, now),
        ).rowcount
        if not claimed:
            (posted_at,) = conn.execute(
                "SELECT posted_at FROM last_posts WHERE client = ?", (client,)
            ).fetchone()
            return max(1, math.ceil(posted_at + POST_INTERVAL - now))
        # Always bind values as parameters; never format user input into SQL.
        conn.execute(
            "INSERT INTO entries (name, message, created_at) VALUES (?, ?, ?)",
            (name, message, created_at),
        )
    return 0


def list_entries(limit: int = 50) -> list[sqlite3.Row]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT name, message, created_at FROM entries ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
