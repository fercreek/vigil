"""Tests for watch.py -- liveness, heartbeats and the weekly pulse.

Split out of test_scoreboard.py so each file stays under the 250-line ceiling
the gate enforces, and so one module maps to one test file.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument.store import connect, insert_signal, insert_resolution, beat  # noqa: E402
from instrument.scoreboard import (                                          # noqa: E402
    win_rate, kill_rule_verdict, build_report, render_report, TAKEN_RATE_FLOOR,
)
from instrument.watch import is_stale, weekly_pulse, format_weekly_pulse     # noqa: E402
from instrument.llm_note import annotate                                     # noqa: E402

ENTRY, SL, TP1, TP2 = 100.0, 95.0, 106.0, 112.0
R_UNIT = ENTRY - SL
BREAKEVEN_WR = 1.0 / (1.0 + (TP1 - ENTRY) / R_UNIT)

def _sent_signal(conn, ruleset="v1", index=0):
    # bar_ts is part of the dedup unique index (symbol, ruleset_version, bar_ts) --
    # each fixture signal needs its own bar so inserts don't collide.
    emitted_at = f"2026-01-01T{index:02d}:00:00+00:00"
    return insert_signal(
        conn, ruleset_version=ruleset, emitted_at=emitted_at, bar_ts=emitted_at,
        symbol="ZEC", timeframe="1h", side="LONG", decision="SENT",
        decision_reason="test fixture", entry_price=ENTRY, sl_price=SL,
        tp1_price=TP1, tp2_price=TP2, r_unit=R_UNIT,
        rr_tp1=(TP1 - ENTRY) / R_UNIT, rr_tp2=(TP2 - ENTRY) / R_UNIT,
        breakeven_wr=BREAKEVEN_WR, trigger={"rsi": 20}, gates_passed=[], gates_failed=[],
    )

def test_kill_rule_verdict_stays_alive_at_100_with_nonnegative_ci_upper():
    verdict = kill_rule_verdict(n_resolved=150, ci_upper=0.02)
    assert verdict == "VIVO"

# ── 4. is_stale catches the 54-days-undetected class of bug ─────────────────
def test_is_stale_detects_an_old_heartbeat():
    with connect(":memory:") as conn:
        old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        beat(conn, "resolver_loop", old)
        assert is_stale(conn, "resolver_loop", max_age_minutes=60) is True

def test_is_stale_is_false_for_a_fresh_heartbeat():
    with connect(":memory:") as conn:
        now = datetime.now(timezone.utc).isoformat()
        beat(conn, "resolver_loop", now)
        assert is_stale(conn, "resolver_loop", max_age_minutes=60) is False

def test_is_stale_true_when_component_never_beat():
    with connect(":memory:") as conn:
        assert is_stale(conn, "never_ran", max_age_minutes=60) is True

# ── 5. the LLM annotates but never gates ─────────────────────────────────────
def test_weekly_pulse_reports_zero_alerts_with_the_old_date_that_reveals_it():
    with connect(":memory:") as conn:
        _sent_signal(conn, index=0)   # emitted_at = 2026-01-01T00:00:00+00:00
        beat(conn, "signal_loop", "2026-03-01T00:00:00+00:00")   # process itself is alive
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        pulse = weekly_pulse(conn, "signal_loop", max_age_minutes=60, now=now)

    assert pulse["alerts_this_week"] == 0
    assert pulse["last_signal_at"] == "2026-01-01T00:00:00+00:00"
    assert pulse["status"] == "vivo"
    rendered = format_weekly_pulse(pulse)
    assert "0 alertas esta semana" in rendered
    assert "2026-01-01" in rendered   # the old date, not the silence, is what gives it away

def test_weekly_pulse_says_none_sent_yet_when_nothing_was_ever_sent():
    with connect(":memory:") as conn:
        beat(conn, "signal_loop", datetime.now(timezone.utc).isoformat())
        pulse = weekly_pulse(conn, "signal_loop", max_age_minutes=60)
    assert pulse["last_signal_at"] is None
    assert pulse["alerts_this_week"] == 0
    assert "aún no manda ninguna señal" in format_weekly_pulse(pulse)

def test_weekly_pulse_flags_possible_outage_when_the_heartbeat_is_stale():
    with connect(":memory:") as conn:
        old_beat = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        beat(conn, "signal_loop", old_beat)
        pulse = weekly_pulse(conn, "signal_loop", max_age_minutes=60)
    assert pulse["status"] == "posible caída"

def test_weekly_pulse_is_pure_and_sends_nothing_itself():
    """No network arg exists to give it -- the only way to see this message
    is for the CALLER to take the returned text/dict and send it elsewhere."""
    with connect(":memory:") as conn:
        _sent_signal(conn, index=0)
        beat(conn, "signal_loop", datetime.now(timezone.utc).isoformat())
        first = weekly_pulse(conn, "signal_loop", max_age_minutes=60,
                             now=datetime(2026, 6, 1, tzinfo=timezone.utc))
        second = weekly_pulse(conn, "signal_loop", max_age_minutes=60,
                              now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert first == second   # deterministic given the same inputs -- no side effects
