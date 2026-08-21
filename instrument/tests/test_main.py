"""Tests for main.py's knowledge-cache wiring (_fomc_suppressions).

rules.py stays pure -- main.py is the only place that reads the knowledge
cache and decides whether a suppression is active. These tests exercise the
asymmetry directly: a FRESH entry inside the +/-24h window suppresses (and
names the event+date); a STALE or MISSING entry must NOT suppress and must
be logged visibly to `heartbeats` instead of silently passing -- that
fail-open behaviour is the actual fix for the FOMC_NEXT_MEETING bug
documented in knowledge/cache.py's module docstring.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from instrument import main  # noqa: E402
from instrument.knowledge import cache  # noqa: E402
from instrument.store import connect  # noqa: E402

NOW = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)  # 8h before the meeting below
MEETING = "2026-09-16T18:00:00+00:00"


def test_fresh_entry_inside_window_suppresses_with_event_and_date():
    with connect(":memory:") as conn:
        cache.put(conn, "fomc_calendar", {"available": True, "next_meeting_date": MEETING},
                  "fred_releases_dates", MEETING)
        suppressions = main._fomc_suppressions(conn, NOW)

    assert suppressions == {"fomc_calendar": {"event": "FOMC meeting", "date": MEETING}}


def test_fresh_entry_outside_window_does_not_suppress():
    far_now = NOW - timedelta(days=10)
    with connect(":memory:") as conn:
        cache.put(conn, "fomc_calendar", {"available": True, "next_meeting_date": MEETING},
                  "fred_releases_dates", MEETING)
        suppressions = main._fomc_suppressions(conn, far_now)

    assert suppressions == {}


def test_stale_entry_does_not_suppress_and_is_logged_visibly():
    """The fail-open case: an expired calendar must stop suppressing, not
    keep suppressing forever -- and the miss has to show up in heartbeats,
    not vanish the way the legacy bot's four expired constants did."""
    past = "2020-01-01T00:00:00+00:00"
    with connect(":memory:") as conn:
        cache.put(conn, "fomc_calendar", {"available": True, "next_meeting_date": past},
                  "fred_releases_dates", past)
        suppressions = main._fomc_suppressions(conn, NOW)
        row = conn.execute(
            "SELECT detail FROM heartbeats WHERE component = 'knowledge:fomc_calendar'"
        ).fetchone()

    assert suppressions == {}
    assert row is not None
    assert cache.STALE_FAIL_OPEN in row["detail"]


def test_missing_entry_does_not_suppress_and_is_logged_visibly():
    with connect(":memory:") as conn:
        suppressions = main._fomc_suppressions(conn, NOW)
        row = conn.execute(
            "SELECT detail FROM heartbeats WHERE component = 'knowledge:fomc_calendar'"
        ).fetchone()

    assert suppressions == {}
    assert row is not None
    assert cache.MISSING in row["detail"]
