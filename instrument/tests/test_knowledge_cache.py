"""Tests for instrument/knowledge/cache.py.

The module exists because four scalp_bot constants (FOMC_NEXT_MEETING,
EARNINGS_CALENDAR, QUANTUM_SUPPRESSED_UNTIL, OPEC_MEETING_DATES) governed
signal suppression and none of them ever raised an alert when they expired.
test_four_real_scalp_bot_dates_all_report_stale below loads the exact four
values and proves stale_keys() would have caught all of them on 2026-08-21 --
that is the test that documents why this module exists, not just that it
runs.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from instrument.knowledge import cache  # noqa: E402

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
PAST = "2020-01-01T00:00:00Z"
FUTURE = "2030-01-01T00:00:00Z"


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


# ── put()/get() round trip ───────────────────────────────────────────────

def test_put_get_roundtrip_deserialises_json_value(conn):
    cache.put(conn, "vix_regime", {"level": "elevated", "value": 24.1}, "manual", FUTURE)
    entry = cache.get(conn, "vix_regime")
    assert entry.value == {"level": "elevated", "value": 24.1}
    assert entry.source == "manual"
    assert entry.valid_until == FUTURE
    assert entry.manual_override is False


def test_get_missing_key_returns_none(conn):
    assert cache.get(conn, "does_not_exist") is None


def test_put_twice_same_key_updates_not_duplicates(conn):
    cache.put(conn, "fomc", "2026-07-28", "manual", FUTURE)
    cache.put(conn, "fomc", "2026-09-15", "manual", FUTURE)
    rows = conn.execute("SELECT COUNT(*) AS n FROM knowledge").fetchone()
    assert rows["n"] == 1
    assert cache.get(conn, "fomc").value == "2026-09-15"


# ── is_stale() ────────────────────────────────────────────────────────────

def test_is_stale_missing_key_is_true(conn):
    assert cache.is_stale(conn, "nope", now=NOW) is True


def test_is_stale_fresh_entry_is_false(conn):
    cache.put(conn, "k", "v", "src", FUTURE)
    assert cache.is_stale(conn, "k", now=NOW) is False


def test_is_stale_expired_entry_is_true(conn):
    cache.put(conn, "k", "v", "src", PAST)
    assert cache.is_stale(conn, "k", now=NOW) is True


# ── require(): the asymmetric core ───────────────────────────────────────

def test_require_fresh_returns_value(conn):
    cache.put(conn, "k", {"suppress": True}, "src", FUTURE)
    value, status = cache.require(conn, "k", on_stale="open", now=NOW)
    assert status == "fresh"
    assert value == {"suppress": True}


def test_require_missing_returns_none_and_missing(conn):
    value, status = cache.require(conn, "nope", on_stale="open", now=NOW)
    assert value is None
    assert status == "missing"


def test_require_stale_never_returns_the_old_value_either_route(conn):
    """Requirement 1: a stale value is never handed back as good, on neither
    on_stale route."""
    cache.put(conn, "k", "the-old-value", "src", PAST)
    open_value, open_status = cache.require(conn, "k", on_stale="open", now=NOW)
    closed_value, closed_status = cache.require(conn, "k", on_stale="closed", now=NOW)
    assert open_value is None and open_status == "stale_fail_open"
    assert closed_value is None and closed_status == "stale_fail_closed"


def test_require_stale_open_on_suppression_key_means_stop_suppressing(conn):
    """Requirement 2: this is the actual FOMC_NEXT_MEETING fix. A suppression
    date that expired must produce the result the caller reads as 'do not
    suppress' -- not 'keep suppressing forever because nothing checked'."""
    cache.put(conn, "fomc_suppression_until", "2026-07-28", "manual_migration", "2026-07-28")
    value, status = cache.require(conn, "fomc_suppression_until", on_stale="open", now=NOW)
    assert value is None
    should_suppress = status == "fresh"
    assert should_suppress is False  # the caller's contract: only "fresh" may suppress


def test_require_rejects_unknown_on_stale(conn):
    cache.put(conn, "k", "v", "src", FUTURE)
    with pytest.raises(ValueError):
        cache.require(conn, "k", on_stale="sideways", now=NOW)


# ── manual_override ───────────────────────────────────────────────────────

def test_manual_override_flagged_in_freshness_report_even_when_fresh(conn):
    """Requirement 3: a manual entry shows up as manual in freshness_report
    even though its valid_until has not passed yet."""
    cache.put(conn, "quantum_suppressed_until", "2030-06-15", "fernando_manual", FUTURE,
              manual_override=True)
    report = cache.freshness_report(conn, now=NOW)
    row = next(r for r in report if r["key"] == "quantum_suppressed_until")
    assert row["is_manual"] is True
    assert row["expired"] is False


def test_manual_override_true_does_not_block_require_when_still_valid(conn):
    """is_stale()/require() stay time-based: a human set this on purpose and
    it hasn't expired, so require() must still be able to use it."""
    cache.put(conn, "k", "human-verified", "manual", FUTURE, manual_override=True)
    value, status = cache.require(conn, "k", on_stale="open", now=NOW)
    assert status == "fresh"
    assert value == "human-verified"


def test_stale_keys_includes_manual_entry_even_before_it_expires(conn):
    cache.put(conn, "manual_key", "v", "manual", FUTURE, manual_override=True)
    cache.put(conn, "auto_key", "v", "feed", FUTURE, manual_override=False)
    stale = cache.stale_keys(conn, now=NOW)
    assert "manual_key" in stale
    assert "auto_key" not in stale


# ── the four real scalp_bot constants ─────────────────────────────────────

def test_four_real_scalp_bot_dates_all_report_stale(conn):
    """config.py:340, config.py:348, config.py:243, commodities_bot.py:98 --
    the literal values that sat expired in prod for up to 108 days. On
    2026-08-21 stale_keys() must report all four."""
    cache.put(conn, "fomc_next_meeting", "2026-07-28", "scalp_bot_migration", "2026-07-28")
    cache.put(conn, "earnings_calendar", {"TSLA": "2026-07-22", "GOOGL": "2026-07-22"},
              "scalp_bot_migration", "2026-07-22")
    cache.put(conn, "quantum_suppressed_until", "2026-06-15", "scalp_bot_migration",
              "2026-06-15")
    cache.put(conn, "opec_meeting_dates", ["2026-05-05"], "scalp_bot_migration", "2026-05-05")

    stale = cache.stale_keys(conn, now=NOW)

    for key in ("fomc_next_meeting", "earnings_calendar", "quantum_suppressed_until",
                "opec_meeting_dates"):
        assert key in stale, f"{key} should have reported stale on {NOW.date()}"
