"""knowledge/cache.py — separates "the data exists" from "the data is still
valid". The legacy bot (scalp_bot) never asked the second question: four
hand-typed constants (FOMC_NEXT_MEETING config.py:340, EARNINGS_CALENDAR
config.py:348, QUANTUM_SUPPRESSED_UNTIL config.py:243, OPEC_MEETING_DATES
commodities_bot.py:98) governed signal suppression and none of them ever
raised an alert when they expired -- one was 108 days stale before anyone
looked. schema.sql has the full incident list.

The asymmetry in require() is the actual fix, not a detail: a stale
SUPPRESSION must stop suppressing (on_stale="open"). Treating "I don't know
if this still applies" as "assume it still applies" is exactly how a single
missed calendar update turned into weeks of signals silently eaten.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..store import _SQLITE_RULES  # the one PG->SQLite translation; not a second one

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")

FRESH = "fresh"
STALE_FAIL_OPEN = "stale_fail_open"
STALE_FAIL_CLOSED = "stale_fail_closed"
MISSING = "missing"


@dataclass(frozen=True)
class Entry:
    key: str
    value: Any
    source: str
    fetched_at: str
    valid_until: str
    manual_override: bool


def _schema_sql() -> str:
    sql = _SCHEMA_PATH.read_text()
    for pattern, replacement in _SQLITE_RULES:
        sql = re.sub(pattern, replacement, sql)
    return sql


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_schema_sql())


def _parse_ts(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _row_to_entry(row: sqlite3.Row) -> Entry:
    value = row["value"]
    try:
        value = json.loads(value)
    except (TypeError, ValueError):
        pass  # stored as a raw string (put() accepts either)
    return Entry(key=row["key"], value=value, source=row["source"],
                 fetched_at=row["fetched_at"], valid_until=row["valid_until"],
                 manual_override=bool(row["manual_override"]))


def put(conn: sqlite3.Connection, key: str, value: Any, source: str, valid_until: str,
        manual_override: bool = False) -> None:
    """Insert or update `key`. Commit is the caller's job, same as store.py's
    insert_signal/insert_resolution -- this stays inside the caller's transaction."""
    _ensure_schema(conn)
    fetched_at = datetime.now(timezone.utc).isoformat()
    payload = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
    conn.execute(
        "INSERT INTO knowledge (key, value, source, fetched_at, valid_until, manual_override) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, source=excluded.source, "
        "fetched_at=excluded.fetched_at, valid_until=excluded.valid_until, "
        "manual_override=excluded.manual_override",
        (key, payload, source, fetched_at, valid_until, int(manual_override)),
    )


def get(conn: sqlite3.Connection, key: str) -> Entry | None:
    _ensure_schema(conn)
    row = conn.execute(
        "SELECT key, value, source, fetched_at, valid_until, manual_override "
        "FROM knowledge WHERE key = ?", (key,)).fetchone()
    return None if row is None else _row_to_entry(row)


def _is_expired(entry: Entry, now: datetime) -> bool:
    valid_until = _parse_ts(entry.valid_until)
    return valid_until is None or now > valid_until


def is_stale(conn: sqlite3.Connection, key: str, now: datetime | None = None) -> bool:
    """Missing, or past valid_until. Deliberately NOT true just because an
    entry is manual_override -- a value a human set correctly on purpose must
    still be usable by require(). stale_keys() below is the broader
    "needs a look" list; this is the narrow "can require() trust it" check."""
    entry = get(conn, key)
    if entry is None:
        return True
    return _is_expired(entry, now or datetime.now(timezone.utc))


def require(conn: sqlite3.Connection, key: str, on_stale: str,
            now: datetime | None = None) -> tuple[Any | None, str]:
    """The asymmetric core -- see module docstring. Never returns the stored
    value once it's stale, on either branch: on_stale="open" means "the
    caller must treat this as if the suppression were lifted", not "here is
    the old value, good luck"."""
    if on_stale not in ("open", "closed"):
        raise ValueError(f"on_stale must be 'open' or 'closed', got {on_stale!r}")
    entry = get(conn, key)
    if entry is None:
        return None, MISSING
    now = now or datetime.now(timezone.utc)
    if _is_expired(entry, now):
        return None, STALE_FAIL_OPEN if on_stale == "open" else STALE_FAIL_CLOSED
    return entry.value, FRESH


def _all_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    _ensure_schema(conn)
    return conn.execute(
        "SELECT key, fetched_at, valid_until, manual_override FROM knowledge ORDER BY key"
    ).fetchall()


def stale_keys(conn: sqlite3.Connection, now: datetime | None = None) -> list[str]:
    """Keys that need attention right now: expired by valid_until, OR set by
    hand. manual_override is included even before it expires -- a hand-typed
    value is 'someone stood in for the real source', which is precisely the
    FOMC_NEXT_MEETING failure mode, and it must stay visible instead of
    quietly passing as a live feed until it also happens to expire."""
    now = now or datetime.now(timezone.utc)
    out = []
    for row in _all_rows(conn):
        valid_until = _parse_ts(row["valid_until"])
        expired = valid_until is None or now > valid_until
        if expired or row["manual_override"]:
            out.append(row["key"])
    return out


def freshness_report(conn: sqlite3.Connection, now: datetime | None = None) -> list[dict]:
    """One row per entry: key, age in hours, whether it's expired, how long
    ago it expired, and whether it's manual. This is what a daily healthcheck
    prints -- the piece that would have caught all four scalp_bot constants
    the day they expired instead of in a three-month-later audit. Rows
    needing attention (expired or manual) sort first."""
    now = now or datetime.now(timezone.utc)
    report = []
    for row in _all_rows(conn):
        fetched = _parse_ts(row["fetched_at"])
        valid_until = _parse_ts(row["valid_until"])
        age_hours = round((now - fetched).total_seconds() / 3600, 1) if fetched else None
        expired = valid_until is None or now > valid_until
        expired_for_hours = (
            round((now - valid_until).total_seconds() / 3600, 1)
            if expired and valid_until is not None else None
        )
        is_manual = bool(row["manual_override"])
        report.append({
            "key": row["key"], "age_hours": age_hours, "expired": expired,
            "expired_for_hours": expired_for_hours, "is_manual": is_manual,
        })
    report.sort(key=lambda r: not (r["expired"] or r["is_manual"]))
    return report
