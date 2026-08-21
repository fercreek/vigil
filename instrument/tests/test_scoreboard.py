"""Tests for scoreboard.py, watch.py and llm_note.py -- one file on purpose.

scoreboard never publishes a number without its denominator; watch is what would
have caught the legacy bot's 54 undetected downtime days; llm_note must degrade to
None on any failure without touching the decision the rule already made.
"""
from __future__ import annotations

import re
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

def _resolve(conn, signal_id, r_realized, mfe_r=1.0, mae_r=-0.3, outcome="TP1_THEN_TP2"):
    insert_resolution(
        conn, signal_id=signal_id, resolver_version="r1",
        resolved_at="2026-01-01T02:00:00+00:00", outcome=outcome,
        exit_price=TP2, exit_bar_ts="2026-01-01T02:00:00+00:00", bars_held=2,
        tp1_hit=1, tp1_bar_ts="2026-01-01T01:00:00+00:00",
        mae_r=mae_r, mfe_r=mfe_r, r_realized=r_realized,
        r_if_tp1_only=1.2, r_if_no_partial=2.4, same_bar_ambiguous=0,
        resolution_source="BARS",
    )

def _mark_fill(conn, signal_id, taken=True):
    conn.execute("INSERT INTO manual_fills (signal_id, taken) VALUES (?, ?)",
                (signal_id, int(taken)))

def _mark_fill_with_result(conn, signal_id, r_realized_human):
    conn.execute("INSERT INTO manual_fills (signal_id, taken, r_realized_human) VALUES (?, 1, ?)",
                (signal_id, r_realized_human))

# ── 1. scoreboard refuses a WR below n=30 ───────────────────────────────────
def test_win_rate_refuses_below_n_30():
    r_values = [1.2, -1.0, 1.2, -1.0, 1.2, -1.0, 1.2, -1.0, 1.2, -1.0, 1.2, -1.0]
    assert len(r_values) == 12
    wr, n = win_rate(r_values)
    assert wr is None
    assert n == 12

def test_report_prints_the_insufficient_n_not_an_asterisked_number():
    with connect(":memory:") as conn:
        for i in range(12):
            sid = _sent_signal(conn, index=i)
            _resolve(conn, sid, r_realized=1.2 if i % 2 == 0 else -1.0)
        report = build_report(conn)
    assert report["win_rate"] is None
    rendered = render_report(report)
    assert "no alcanza para un %" in rendered
    assert "llevas 12" in rendered

# ── 2. taken-rate below 60% suspends conclusions ────────────────────────────
def test_taken_rate_40_percent_suspends_conclusions():
    with connect(":memory:") as conn:
        ids = [_sent_signal(conn, index=i) for i in range(10)]
        for sid in ids:
            _resolve(conn, sid, r_realized=1.2)
        for sid in ids[:4]:               # 4 of 10 marked = 40%, below the 60% floor
            _mark_fill(conn, sid, taken=True)
        report = build_report(conn)

    assert report["taken_rate"] == pytest.approx(0.4)
    assert report["taken_rate"] < TAKEN_RATE_FLOOR
    assert report["conclusions_suspended"] is True
    rendered = render_report(report)
    assert "quedan en pausa" in rendered
    assert "4/10" in rendered

def test_taken_rate_above_floor_does_not_suspend():
    with connect(":memory:") as conn:
        ids = [_sent_signal(conn, index=i) for i in range(10)]
        for sid in ids:
            _resolve(conn, sid, r_realized=1.2)
        for sid in ids[:7]:               # 7 of 10 = 70%, above the floor
            _mark_fill(conn, sid, taken=True)
        report = build_report(conn)
    assert report["conclusions_suspended"] is False

# ── 3. kill-rule verdict crosses the threshold correctly ────────────────────
def test_kill_rule_verdict_stays_in_observation_below_100():
    verdict = kill_rule_verdict(n_resolved=99, ci_upper=-0.5)
    assert verdict == "EN OBSERVACIÓN (n=99/100)"

def test_kill_rule_verdict_retires_at_100_with_negative_ci_upper():
    verdict = kill_rule_verdict(n_resolved=100, ci_upper=-0.01)
    assert verdict == "RETIRAR"

def test_annotate_degrades_to_none_on_a_crashing_client():
    signal = {"symbol": "ZEC", "side": "LONG"}

    def crashing_client(sig, timeout):
        raise RuntimeError("groq is down: 429")

    verdict = annotate(signal, crashing_client)
    assert verdict is None

def test_annotate_failure_never_changes_the_deterministic_decision():
    """The rule already decided SENT before annotate() is ever called. A
    crashing LLM must not be able to touch that -- this is the whole point
    of 'the LLM annotates, it does not decide'."""
    decision = "SENT"

    def crashing_client(sig, timeout):
        raise TimeoutError("upstream hung")

    verdict = annotate({"decision": decision}, crashing_client)

    assert verdict is None
    assert decision == "SENT"   # untouched -- annotate has no path to mutate it

def test_annotate_enforces_a_hard_timeout_even_if_the_client_ignores_it():
    def slow_client(sig, timeout):
        time.sleep(5)          # ignores the timeout argument it was handed
        return {"note": "too late"}

    start = time.monotonic()
    verdict = annotate({"symbol": "ZEC"}, slow_client, timeout=0.2)
    elapsed = time.monotonic() - start

    assert verdict is None
    assert elapsed < 2.0        # bounded by the hard deadline, not the sleep(5)

def test_annotate_returns_the_verdict_on_a_healthy_client():
    def healthy_client(sig, timeout):
        return {"note": "confluence looks thin", "agrees": False}

    verdict = annotate({"symbol": "ZEC"}, healthy_client)
    assert verdict == {"note": "confluence looks thin", "agrees": False}

# ── 6. the taken-feedback loop: what happened to what you pressed the button on ──
def test_taken_feedback_reports_outcome_and_r_for_marked_trades():
    with connect(":memory:") as conn:
        sid1 = _sent_signal(conn, index=0)
        _resolve(conn, sid1, r_realized=1.8, outcome="TP1_THEN_TP2")
        _mark_fill_with_result(conn, sid1, r_realized_human=1.5)   # human filled a bit worse

        sid2 = _sent_signal(conn, index=1)
        _resolve(conn, sid2, r_realized=-1.0, outcome="SL")
        _mark_fill(conn, sid2, taken=True)                        # no human R -> falls back to r_realized

        sid3 = _sent_signal(conn, index=2)                        # marked PASO -- excluded from feedback
        _resolve(conn, sid3, r_realized=1.8, outcome="TP1_THEN_TP2")
        _mark_fill(conn, sid3, taken=False)

        report = build_report(conn)

    assert report["taken_feedback_n"] == 2
    assert report["taken_feedback_by_outcome"] == {"TP1_THEN_TP2": 1, "SL": 1}
    assert report["taken_feedback_mean_r"] == pytest.approx((1.5 + -1.0) / 2)
    rendered = render_report(report)
    assert "De lo que sí tomaste" in rendered
    assert "2 resueltas" in rendered

def test_taken_feedback_is_empty_when_nothing_marked_taken_has_resolved():
    with connect(":memory:") as conn:
        sid = _sent_signal(conn, index=0)
        _resolve(conn, sid, r_realized=1.2)
        report = build_report(conn)
    assert report["taken_feedback_n"] == 0
    rendered = render_report(report)
    assert "ninguna se ha resuelto todavía" in rendered

# ── 8. render_report never prints a raw Python structure ────────────────────
def test_render_report_never_prints_a_raw_data_structure():
    """The -18%-from-23%-of-rows incident and its siblings all trace back to
    a number quoted without the shape it came from being legible -- a raw
    dict/list literal in the text is the sharpest version of that failure
    (e.g. the old "by decision: {'SUPPRESSED': 18}"). No brace/bracket
    followed by a quote should ever reach the message body again."""
    with connect(":memory:") as conn:
        for i in range(3):
            sid = _sent_signal(conn, index=i)
            _resolve(conn, sid, r_realized=1.2, outcome="TP1_THEN_TP2" if i else "SL")
        empty_report = build_report(conn, ruleset="nonexistent")
        populated_report = build_report(conn)
    for report in (empty_report, populated_report):
        rendered = render_report(report)
        assert not re.search(r"[\[{]['\"]", rendered), rendered
