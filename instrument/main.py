"""Wiring. Two loops and nothing else.

Deliberately thin: every decision lives in the module that owns it, so this file
has no thresholds, no calendars and no judgement. The legacy bot's equivalent grew
to 1,299 lines and became the module every other module imported back.

  scan     -- fetch closed candles, evaluate, store every evaluation, notify the SENT
  resolve  -- walk forward the signals that are still open and write their outcome

Not started here: no execution, no exchange keys. The operator trades by hand.
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

from . import llm_note, notify, rules, watch
from .feed import FeedUnavailable, fetch_ohlcv
from .geometry import InvalidGeometry, assert_geometry
from .knowledge import cache
from .resolver import RESOLVER_VERSION, resolve
from .store import RowRejected, connect, insert_resolution, insert_signal

SYMBOLS = ["ZEC"]          # universe is fixed for the whole evaluation window
TIMEFRAME = "1h"
MAX_HOLD_BARS = 72         # the max-hold decision, 2026-08-21
SCAN_SLEEP_SECONDS = 300
FOMC_WINDOW_HOURS = 24     # how close to the meeting (either side) rules.py suppresses


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fomc_suppressions(conn, now: datetime) -> dict[str, dict]:
    """The one place that consults the knowledge cache -- rules.py stays pure
    and only reads whatever this returns. The asymmetry is cache.require()'s
    on_stale="open": a stale or missing calendar entry must NOT suppress, and
    that miss is logged to `heartbeats` (visible next to scan/feed status)
    instead of silently behaving as "nothing to suppress today". Only a
    FRESH entry inside the +/-24h window produces an active suppression."""
    value, status = cache.require(conn, "fomc_calendar", on_stale="open", now=now)
    if status != cache.FRESH:
        watch.record(conn, "knowledge:fomc_calendar", status,
                     "not suppressing (fail-open)", now.isoformat())
        return {}
    meeting = _parse_iso(value.get("next_meeting_date", "")) if value else None
    if meeting is None or abs((meeting - now).total_seconds()) > FOMC_WINDOW_HOURS * 3600:
        return {}
    return {"fomc_calendar": {"event": "FOMC meeting", "date": value["next_meeting_date"]}}


def scan_once(conn, symbols=SYMBOLS, send=True) -> int:
    """Evaluate the newest closed candle of every symbol. Returns signals sent."""
    sent = 0
    suppressions = _fomc_suppressions(conn, datetime.now(timezone.utc))
    for symbol in symbols:
        candles = fetch_ohlcv(symbol, TIMEFRAME, limit=300)
        if len(candles) < 2:
            continue
        row = rules.evaluate(symbol, TIMEFRAME, candles, len(candles) - 1,
                              suppressions=suppressions)
        if row is None:
            continue
        if row.get("decision") == "SENT":
            row["llm_verdict"] = llm_note.annotate(row)     # annotates, never gates
        try:
            signal_id = insert_signal(conn, **row)
        except RowRejected as exc:
            if exc.constraint == "ux_signal_dedup":         # same bar, already stored
                continue
            raise
        conn.commit()
        if row.get("decision") == "SENT":
            sent += 1
            if send:
                stored = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
                notify.send_signal(stored, current_price=candles[-1].close)
        watch.record(conn, f"scan:{symbol}", "ok", f"evaluated bar {candles[-1].ts}", _now())
        conn.commit()
    return sent


def resolve_pending(conn, max_hold_bars: int = MAX_HOLD_BARS) -> int:
    """Resolve every SENT signal that has no resolution yet and has enough candles."""
    pending = conn.execute(
        "SELECT s.* FROM signals s LEFT JOIN resolutions r ON r.signal_id = s.id "
        "WHERE s.decision = 'SENT' AND r.signal_id IS NULL"
    ).fetchall()
    resolved = 0
    for row in pending:
        try:
            geometry = assert_geometry(row["side"], row["entry_price"], row["sl_price"],
                                       row["tp1_price"], row["tp2_price"])
        except InvalidGeometry:
            continue                                        # the schema should have caught it
        candles = fetch_ohlcv(row["symbol"], row["timeframe"], limit=max_hold_bars + 50)
        after = [c for c in candles if c.ts > row["bar_ts"]]
        if len(after) < max_hold_bars:
            continue                                        # not enough history yet, try later
        result = resolve(geometry, after, max_bars=max_hold_bars)
        if result.outcome == "VOID":
            continue
        insert_resolution(conn, signal_id=row["id"], resolver_version=RESOLVER_VERSION,
                          resolved_at=_now(), **result.as_row())
        conn.commit()
        resolved += 1
    return resolved


def run_forever(db_path: str | None = None) -> None:
    with connect(db_path) as conn:
        while True:
            try:
                sent = scan_once(conn)
                resolved = resolve_pending(conn)
                print(f"[{_now()}] sent={sent} resolved={resolved}")
            except FeedUnavailable as exc:
                # A dead feed must look different from a quiet market. This is the
                # distinction the legacy bot could not make for 54 days.
                watch.record(conn, "feed", "down", str(exc), _now())
                conn.commit()
                print(f"[{_now()}] FEED DOWN: {exc}")
            time.sleep(SCAN_SLEEP_SECONDS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Zenith instrument")
    parser.add_argument("--db", default=None)
    parser.add_argument("--once", action="store_true", help="one pass, then exit")
    parser.add_argument("--no-send", action="store_true", help="evaluate but do not notify")
    args = parser.parse_args()
    if not args.once:
        run_forever(args.db)
        return 0
    with connect(args.db) as conn:
        sent = scan_once(conn, send=not args.no_send)
        resolved = resolve_pending(conn)
        print(f"sent={sent} resolved={resolved}")
        print(watch.format_weekly_pulse(watch.weekly_pulse(conn, "scan:ZEC", 60)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
