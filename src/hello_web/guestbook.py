import os
import re
import sqlite3
import unicodedata
from contextlib import closing
from datetime import UTC, datetime

NAME_MAX = 50
MESSAGE_MAX = 500

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
    return conn


def add_entry(name: str, message: str) -> None:
    created_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    with closing(_connect()) as conn, conn:
        # Always bind values as parameters; never format user input into SQL.
        conn.execute(
            "INSERT INTO entries (name, message, created_at) VALUES (?, ?, ?)",
            (name, message, created_at),
        )


def list_entries(limit: int = 50) -> list[sqlite3.Row]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT name, message, created_at FROM entries ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
