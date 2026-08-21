"""Tests for the two edges of the system: feed.py (data in) and notify.py
(message out). One file, per brief -- both edges are small enough to share it.

The render() snapshot is the guardrail against silent format drift: the
message layout is a contract with the user (he trades from it by eye), so
a change to it must show up as a diff in this test, not as a surprise in
Telegram.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ccxt  # noqa: E402

from instrument import feed, store  # noqa: E402
from instrument.feed import Candle, FeedUnavailable, fetch_ohlcv  # noqa: E402
from instrument.notify import render, safe_html  # noqa: E402

# ── render(): a full row, every optional field populated ────────────────────

ROW = {
    "id": 418, "symbol": "ZEC", "side": "LONG", "timeframe": "1h",
    "entry_price": 212.40, "sl_price": 206.10, "tp1_price": 220.20, "tp2_price": 228.00,
    "r_unit": 6.30, "rr_tp1": 1.24, "rr_tp2": 2.48, "breakeven_wr": 0.446,
    "trigger": '{"rsi": 18.4}',
    "gates_passed": '["cierre bajo BB inferior", "precio < EMA200"]',
    "gates_failed": "[]",
    "bar_ts": "2026-08-21T14:00:00Z",
    "ruleset_version": "r7", "ruleset_resolved_n": 34, "ruleset_wr": 0.29,
    "ruleset_wr_lo": 0.15, "ruleset_wr_hi": 0.45, "ruleset_exp_r": -0.11,
    "llm_verdict": '{"side": "LONG", "score": 4, "max_score": 5, '
                   '"reason": "divergencia en CVD"}',
    "expires_at": "2026-08-21T16:00:00Z",
}

EXPECTED = (
    "ZEC LONG · 1h · señal #418\n"
    "Entrada  212.40\n"
    "Stop     206.10   (−2.97%)   1R = 6.30\n"
    "TP1      220.20   RR 1.24\n"
    "TP2      228.00   RR 2.48\n"
    "\n"
    "Necesita hasta 44.6% de aciertos; r7 trae 29% en 34 señales resueltas "
    "(intervalo de confianza 15-45%) — por debajo del umbral.\n"
    "Esa cifra mide señales YA resueltas, no ésta — se manda igual para auditar si "
    "r7 mejora o se retira, exp −0.11R.\n"
    "Disparo: RSI 18.4 · cierre bajo BB inferior · precio < EMA200\n"
    "Vela cerrada 2026-08-21 14:00 UTC\n"
    "💰 Riesgo 1% de $1,000 = 1.6 ZEC (~$337) · SL a 2.97% = −$10\n"
    "\n"
    '🤖 LLM: LONG 4/5 — "divergencia en CVD" (no gatea, solo se registra)\n'
    "Ahora: 213.05 (+0.31% de la entrada) · quedan 47min (vence 16:00 UTC, después: muerta)"
)


def test_render_snapshot_matches_expected_format():
    """Locks the exact layout Fernando trades from. A failure here means the
    format changed -- confirm on purpose, then update EXPECTED; don't chase
    the test into passing without reading the diff."""
    out = render(ROW, account_size=1000.0, risk_pct=0.01, current_price=213.05,
                 now=datetime(2026, 8, 21, 15, 13, tzinfo=timezone.utc))
    assert out == EXPECTED


def test_render_omits_llm_line_when_verdict_is_null():
    row = dict(ROW, llm_verdict=None)
    out = render(row, now=datetime(2026, 8, 21, 15, 13, tzinfo=timezone.utc))
    assert "LLM" not in out
    assert "🤖" not in out


def test_render_omits_ahora_line_without_live_inputs():
    """No current_price/now passed -> no opinion about the present moment."""
    out = render(ROW)
    assert "Ahora:" not in out
    assert "quedan" not in out


def test_render_does_not_crash_on_missing_optional_fields():
    """A minimal row -- only what's guaranteed for a non-SENT decision --
    must still render without raising."""
    minimal = {"id": 1, "symbol": "BTC", "side": "LONG", "timeframe": "1h"}
    out = render(minimal)
    assert out == "BTC LONG · 1h · señal #1"


def test_render_reads_from_a_real_sqlite_row():
    """render() must work against sqlite3.Row (IndexError on miss), not just
    dict (KeyError on miss) -- the two raise differently on a missing key."""
    with store.connect(":memory:") as conn:
        signal_id = store.insert_signal(
            conn, ruleset_version="r7", emitted_at="2026-08-21T14:00:05Z",
            bar_ts="2026-08-21T14:00:00Z", symbol="ZEC", timeframe="1h", side="LONG",
            decision="SENT", decision_reason="rsi oversold + bb breach",
            entry_price=212.40, sl_price=206.10, tp1_price=220.20, tp2_price=228.00,
            r_unit=6.30, rr_tp1=1.24, rr_tp2=2.48, breakeven_wr=0.446,
            trigger={"rsi": 18.4},
            gates_passed=["cierre bajo BB inferior", "precio < EMA200"],
        )
        row = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()

    out = render(row)
    assert out.startswith("ZEC LONG · 1h · señal #")
    assert "Disparo: RSI 18.4 · cierre bajo BB inferior · precio < EMA200" in out
    assert "TP2      228.00   RR 2.48" in out


def test_safe_html_escapes_the_production_incident_payload():
    """The exact string that 400'd a live message: "score 3/5 < 4"."""
    assert safe_html("score 3/5 < 4") == "score 3/5 &lt; 4"


def test_safe_html_keeps_allowed_tags_and_escapes_the_rest():
    assert safe_html("<b>bold</b> & <script>x</script>") == \
        "<b>bold</b> &amp; &lt;script&gt;x&lt;/script&gt;"


def test_safe_html_empty_string():
    assert safe_html("") == ""


# ── feed.py: exchange fallback, mocked -- no network in this suite ─────────

def _row(ts_ms: int, price: float) -> list:
    return [ts_ms, price, price + 1, price - 1, price + 0.5, 100.0]


def test_fetch_ohlcv_drops_the_forming_candle(monkeypatch):
    rows = [_row(1_700_000_000_000 + i * 3_600_000, 100 + i) for i in range(7)]
    monkeypatch.setattr(feed._okx, "fetch_ohlcv", lambda *a, **k: rows)

    result = fetch_ohlcv("ZEC", timeframe="1h", limit=6)

    assert len(result) == 6
    assert all(isinstance(c, Candle) for c in result)
    # the 7th (forming) row must not appear -- its close (106.5) is absent
    assert all(c.close != rows[-1][4] for c in result)
    assert result[0].close == rows[0][4]


def test_fetch_ohlcv_falls_back_okx_to_kucoin(monkeypatch):
    monkeypatch.setattr(feed._okx, "fetch_ohlcv",
                         lambda *a, **k: (_ for _ in ()).throw(ccxt.NetworkError("timeout")))
    good_rows = [_row(1_700_000_000_000 + i * 3_600_000, 50 + i) for i in range(3)]
    monkeypatch.setattr(feed._kucoin, "fetch_ohlcv", lambda *a, **k: good_rows)

    result = fetch_ohlcv("ZEC", limit=2)

    assert len(result) == 2
    assert result[0].close == good_rows[0][4]


def test_fetch_ohlcv_raises_feed_unavailable_when_all_three_fail(monkeypatch):
    for exchange in (feed._okx, feed._kucoin, feed._binance):
        monkeypatch.setattr(exchange, "fetch_ohlcv",
                             lambda *a, **k: (_ for _ in ()).throw(ccxt.NetworkError("down")))

    with pytest.raises(FeedUnavailable):
        fetch_ohlcv("ZEC", timeframe="1h", limit=300)
