"""Persistence for the Zenith instrument.

One schema file (schema.sql, PostgreSQL dialect) is the single source of truth.
For local and replay runs it is translated to SQLite here. There is deliberately
no second hand-maintained DDL: the legacy bot kept RSI in 8 places and the
confluence score in 4, and they drifted.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# PostgreSQL -> SQLite. Order matters: NUMERIC(x,y) before the bare types.
_SQLITE_RULES: list[tuple[str, str]] = [
    (r"\bBIGSERIAL\s+PRIMARY\s+KEY\b", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    (r"\bNUMERIC\s*\(\s*\d+\s*,\s*\d+\s*\)", "REAL"),
    (r"\bTIMESTAMPTZ\b", "TEXT"),
    (r"\bBIGINT\b", "INTEGER"),
    (r"\bBOOLEAN\b", "INTEGER"),
]


class RowRejected(Exception):
    """The database refused a row. Carries the constraint that fired."""

    def __init__(self, constraint: str, detail: str = "") -> None:
        super().__init__(f"{constraint}: {detail}" if detail else constraint)
        self.constraint = constraint
        self.detail = detail


def schema_sql(dialect: str = "sqlite") -> str:
    sql = SCHEMA_PATH.read_text()
    if dialect == "postgres":
        return sql
    if dialect != "sqlite":
        raise ValueError(f"unknown dialect: {dialect}")
    for pattern, replacement in _SQLITE_RULES:
        sql = re.sub(pattern, replacement, sql)
    return sql


def _constraint_from_sqlite_error(message: str) -> str:
    """SQLite reports 'CHECK constraint failed: <name>'. Postgres uses its own
    wording; both are normalised to the constraint name so callers can branch."""
    match = re.search(r"CHECK constraint failed:\s*(\w+)", message)
    if match:
        return match.group(1)
    if "UNIQUE constraint failed" in message:
        return "ux_signal_dedup"
    return message.strip()


@contextmanager
def connect(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    """Open the local store, creating it if needed.

    STATE_DIR exists because the legacy bot had 11 persistence paths and only 2
    pointed at the Railway volume; signal_episodes -- the one table that measured
    signal quality -- wrote to ephemeral disk for five months.
    """
    path = db_path or os.getenv("INSTRUMENT_DB") or str(
        Path(os.getenv("STATE_DIR", ".")) / "instrument.db"
    )
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(schema_sql("sqlite"))
        yield conn
    finally:
        conn.close()


def _dumps(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))


def insert_signal(conn: sqlite3.Connection, **fields: Any) -> int:
    """Insert one evaluation. Raises RowRejected if the schema refuses it.

    JSON-ish columns accept either a Python object or a pre-serialised string.
    """
    for key in ("trigger", "gates_passed", "gates_failed", "llm_verdict"):
        if key in fields and fields[key] is not None:
            fields[key] = _dumps(fields[key])
    fields.setdefault("gates_passed", "[]")
    fields.setdefault("gates_failed", "[]")
    fields.setdefault("trigger", "{}")

    columns = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    try:
        cursor = conn.execute(
            f"INSERT INTO signals ({columns}) VALUES ({placeholders})",
            tuple(fields.values()),
        )
    except sqlite3.IntegrityError as exc:
        raise RowRejected(_constraint_from_sqlite_error(str(exc)), str(exc)) from exc
    return int(cursor.lastrowid)


def insert_resolution(conn: sqlite3.Connection, **fields: Any) -> None:
    columns = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    try:
        conn.execute(
            f"INSERT INTO resolutions ({columns}) VALUES ({placeholders})",
            tuple(fields.values()),
        )
    except sqlite3.IntegrityError as exc:
        raise RowRejected(_constraint_from_sqlite_error(str(exc)), str(exc)) from exc


def insert_legacy(conn: sqlite3.Connection, **fields: Any) -> None:
    """Quarantined import of the old trades table. No constraints by design."""
    columns = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    conn.execute(
        f"INSERT OR REPLACE INTO legacy_trades ({columns}) VALUES ({placeholders})",
        tuple(fields.values()),
    )


def beat(conn: sqlite3.Connection, component: str, when: str, detail: Any = None) -> None:
    conn.execute(
        "INSERT INTO heartbeats (component, last_beat, detail) VALUES (?, ?, ?) "
        "ON CONFLICT(component) DO UPDATE SET last_beat=excluded.last_beat, detail=excluded.detail",
        (component, when, _dumps(detail) if detail is not None else None),
    )
