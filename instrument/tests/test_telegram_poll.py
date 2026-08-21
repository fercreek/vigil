"""Tests for telegram_poll.py -- no network, every requests.post call is
faked. Covers the hole this module exists to close: TOMADA/PASO taps on
notify.signal_keyboard() used to go nowhere, so manual_fills stayed empty.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument import telegram_poll                              # noqa: E402
from instrument.store import connect, insert_signal                # noqa: E402

TOKEN = "test-token"

ENTRY, SL, TP1 = 100.0, 95.0, 106.0
R_UNIT = ENTRY - SL


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def conn():
    with connect(":memory:") as c:
        yield c


def _signal(conn, index=0) -> int:
    bar_ts = f"2026-01-01T{index:02d}:00:00+00:00"
    return insert_signal(
        conn, ruleset_version="v1", emitted_at=bar_ts, bar_ts=bar_ts,
        symbol="ZEC", timeframe="1h", side="LONG", decision="SENT",
        decision_reason="test fixture", entry_price=ENTRY, sl_price=SL,
        tp1_price=TP1, tp2_price=None, r_unit=R_UNIT, rr_tp1=1.2,
        breakeven_wr=0.45, trigger={"rsi": 20}, gates_passed=[], gates_failed=[],
    )


def _capture_posts(monkeypatch, get_updates_result: list[dict]):
    calls: list[tuple[str, dict]] = []

    def fake_post(url, json=None, timeout=None):
        calls.append((url, json))
        if url.endswith("/getUpdates"):
            return _FakeResponse({"ok": True, "result": get_updates_result})
        return _FakeResponse({"ok": True, "result": {}})

    monkeypatch.setattr(telegram_poll.requests, "post", fake_post)
    return calls


# ---------- keyboard shape ----------

def test_keyboard_has_exactly_the_three_working_buttons():
    markup = telegram_poll.keyboard_markup()
    labels = [row[0]["text"] for row in markup["keyboard"]]
    assert labels == list(telegram_poll.REPORT_BUTTONS)
    assert len(labels) == 3
    assert markup["resize_keyboard"] is True


# ---------- freshness formatting ----------

def test_format_freshness_empty():
    assert "Todavía no tengo datos guardados" in telegram_poll._format_freshness([])


def test_format_freshness_marks_expired_and_manual():
    report = [
        {"key": "fomc_calendar", "age_hours": 2.0, "expired": False,
         "expired_for_hours": None, "is_manual": False},
        {"key": "funding_btc", "age_hours": 30.0, "expired": True,
         "expired_for_hours": 6.0, "is_manual": True},
    ]
    text = telegram_poll._format_freshness(report)
    assert "fomc_calendar: actualizado hace 2.0h · vigente" in text
    assert "funding_btc: actualizado hace 30.0h · cargado a mano · ⚠️ vencido hace 6.0h" in text


# ---------- report buttons over getUpdates ----------

def test_text_message_matching_a_button_sends_its_report(conn, monkeypatch):
    update = {"update_id": 1, "message": {"chat": {"id": 555}, "text": "💓 Pulso semanal"}}
    calls = _capture_posts(monkeypatch, [update])

    next_offset = telegram_poll.poll_once(conn, TOKEN, 0)

    assert next_offset == 2
    send_calls = [c for c in calls if c[0].endswith("/sendMessage")]
    assert len(send_calls) == 1
    assert send_calls[0][1]["chat_id"] == 555
    assert "alertas esta semana" in send_calls[0][1]["text"]


def test_text_message_not_matching_any_button_sends_nothing(conn, monkeypatch):
    update = {"update_id": 1, "message": {"chat": {"id": 555}, "text": "hola"}}
    calls = _capture_posts(monkeypatch, [update])

    telegram_poll.poll_once(conn, TOKEN, 0)

    assert not [c for c in calls if c[0].endswith("/sendMessage")]


# ---------- TOMADA / PASO callback -> manual_fills ----------

def test_taken_callback_writes_manual_fills_and_edits_the_message(conn, monkeypatch):
    signal_id = _signal(conn)
    update = {
        "update_id": 7,
        "callback_query": {
            "id": "cbid-1", "data": f"taken:{signal_id}",
            "message": {"chat": {"id": 555}, "message_id": 42, "text": "ZEC LONG · señal"},
        },
    }
    calls = _capture_posts(monkeypatch, [update])

    next_offset = telegram_poll.poll_once(conn, TOKEN, 0)

    assert next_offset == 8
    row = conn.execute(
        "SELECT taken FROM manual_fills WHERE signal_id = ?", (signal_id,)
    ).fetchone()
    assert row is not None and row["taken"] == 1

    edit_calls = [c for c in calls if c[0].endswith("/editMessageText")]
    assert len(edit_calls) == 1
    assert "TOMADA" in edit_calls[0][1]["text"]
    assert edit_calls[0][1]["reply_markup"] == {"inline_keyboard": []}
    assert [c for c in calls if c[0].endswith("/answerCallbackQuery")]


def test_pass_callback_marks_taken_false(conn, monkeypatch):
    signal_id = _signal(conn)
    update = {
        "update_id": 7,
        "callback_query": {
            "id": "cbid-2", "data": f"pass:{signal_id}",
            "message": {"chat": {"id": 555}, "message_id": 42, "text": "ZEC LONG · señal"},
        },
    }
    _capture_posts(monkeypatch, [update])

    telegram_poll.poll_once(conn, TOKEN, 0)

    row = conn.execute(
        "SELECT taken FROM manual_fills WHERE signal_id = ?", (signal_id,)
    ).fetchone()
    assert row is not None and row["taken"] == 0


def test_callback_for_unknown_signal_is_swallowed_and_offset_still_advances(conn, monkeypatch):
    """FK-invalid signal_id must not crash the batch or freeze the offset --
    a poison update would otherwise be retried forever."""
    update = {"update_id": 3, "callback_query": {"id": "cbid-3", "data": "taken:999999"}}
    _capture_posts(monkeypatch, [update])

    next_offset = telegram_poll.poll_once(conn, TOKEN, 0)

    assert next_offset == 4
    assert conn.execute("SELECT COUNT(*) AS n FROM manual_fills").fetchone()["n"] == 0


def test_malformed_callback_data_is_ignored(conn, monkeypatch):
    update = {"update_id": 4, "callback_query": {"id": "cbid-4", "data": "not-a-choice"}}
    _capture_posts(monkeypatch, [update])

    next_offset = telegram_poll.poll_once(conn, TOKEN, 0)

    assert next_offset == 5
    assert conn.execute("SELECT COUNT(*) AS n FROM manual_fills").fetchone()["n"] == 0


def test_offset_advances_past_a_bad_update_so_the_next_one_still_runs(conn, monkeypatch):
    signal_id = _signal(conn)
    updates = [
        {"update_id": 10, "callback_query": {"id": "cbid-5", "data": "taken:not-an-int"}},
        {"update_id": 11, "callback_query": {"id": "cbid-6", "data": f"taken:{signal_id}"}},
    ]
    _capture_posts(monkeypatch, updates)

    next_offset = telegram_poll.poll_once(conn, TOKEN, 0)

    assert next_offset == 12
    row = conn.execute(
        "SELECT taken FROM manual_fills WHERE signal_id = ?", (signal_id,)
    ).fetchone()
    assert row is not None and row["taken"] == 1


def test_getupdates_receives_the_offset(conn, monkeypatch):
    calls = _capture_posts(monkeypatch, [])

    telegram_poll.poll_once(conn, TOKEN, 42)

    get_calls = [c for c in calls if c[0].endswith("/getUpdates")]
    assert get_calls[0][1]["offset"] == 42
