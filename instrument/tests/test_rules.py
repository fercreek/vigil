"""Contract tests for rules.py: no look-ahead, SENT never ships an empty
trigger, an invalid geometry is always BLOCKED, and RULESET_VERSION tracks the
bytes that define the rule.

ta.py's real implementation is a separate module written independently against
its documented contract (list in, same-length list out, None where there's no
history). These tests monkeypatch that contract directly so the gating logic
here can be pinned down without depending on real indicator math.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument import rules                       # noqa: E402
from instrument.resolver import Candle              # noqa: E402


def _candles(n: int, start: float = 100.0, step: float = 0.1) -> list[Candle]:
    out = []
    for i in range(n):
        c = start + i * step
        out.append(Candle(ts=f"2026-01-01T{i:04d}", open=c, high=c + 0.5,
                          low=c - 0.5, close=c))
    return out


def _passing_ta(monkeypatch, recorder: list[int] | None = None):
    """Wire ta.* so every gate passes for a LONG at whatever length is asked.

    If `recorder` is given, each call appends the length of `closes` it was
    handed -- the no-look-ahead test uses that to prove the window never grew
    past index+1, however long the underlying candle list actually is.
    """
    def _fixed(n: int, value: float):
        return [value] * n

    def rsi(closes, period):
        if recorder is not None:
            recorder.append(len(closes))
        return _fixed(len(closes), 20.0)          # oversold -> LONG gate passes

    def atr(highs, lows, closes, period):
        return _fixed(len(closes), 1.0)            # 1.0 / ~100 close => atr_min passes

    def ema(values, period):
        return _fixed(len(values), 90.0)            # close > ema200 -> LONG bias

    def bbands(closes, period, k):
        n = len(closes)
        # wide band, close sits near the lower edge for every candle in _candles()
        # (close ranges 100-105) -> pctb stays comfortably under BB_PCTB_LOW
        return _fixed(n, 300.0), _fixed(n, 195.0), _fixed(n, 90.0)

    def adx(highs, lows, closes, period):
        return _fixed(len(closes), 40.0)            # well above ADX_MIN

    monkeypatch.setattr(rules.ta, "rsi", rsi)
    monkeypatch.setattr(rules.ta, "atr", atr)
    monkeypatch.setattr(rules.ta, "ema", ema)
    monkeypatch.setattr(rules.ta, "bbands", bbands)
    monkeypatch.setattr(rules.ta, "adx", adx)


def test_no_lookahead_result_depends_only_on_prefix(monkeypatch):
    """evaluate(..., index) must be identical whether the caller hands it the
    full candle list or just candles[:index+1] -- and the indicator window it
    builds must never exceed index+1 candles, however long the list is."""
    recorder: list[int] = []
    _passing_ta(monkeypatch, recorder)

    full = _candles(50)
    index = 10
    truncated = full[: index + 1]

    result_full = rules.evaluate("ZEC", "1h", full, index)
    result_truncated = rules.evaluate("ZEC", "1h", truncated, index)

    assert result_full == result_truncated
    # both calls above fed the indicator functions exactly index+1 closes
    assert recorder and all(length == index + 1 for length in recorder)


def test_sent_never_ships_an_empty_trigger(monkeypatch):
    _passing_ta(monkeypatch)
    candles = _candles(50)

    result = rules.evaluate("ZEC", "1h", candles, len(candles) - 1)

    assert result is not None
    assert result["decision"] == "SENT"
    assert result["trigger"]                 # non-empty dict
    assert "rsi" in result["trigger"]


def test_invalid_geometry_is_blocked_never_sent(monkeypatch):
    """Force the multiplier that sizes 1R to zero: entry == sl, InvalidGeometry.
    The gates all still pass -- the failure has to surface as BLOCKED, not as a
    broken SENT row."""
    _passing_ta(monkeypatch)
    monkeypatch.setattr(rules, "SL_ATR_MULT", 0.0)
    candles = _candles(50)

    result = rules.evaluate("ZEC", "1h", candles, len(candles) - 1)

    assert result is not None
    assert result["decision"] == "BLOCKED"
    assert "sl" in result["decision_reason"].lower() or "entry" in result["decision_reason"].lower()
    assert "entry_price" not in result or result.get("r_unit") is None


def test_suppressed_when_a_gate_fails(monkeypatch):
    _passing_ta(monkeypatch)
    # RSI far from oversold -> rsi_extreme gate fails for the LONG side
    monkeypatch.setattr(rules.ta, "rsi", lambda closes, period: [55.0] * len(closes))
    candles = _candles(50)

    result = rules.evaluate("ZEC", "1h", candles, len(candles) - 1)

    assert result is not None
    assert result["decision"] == "SUPPRESSED"
    assert "rsi_extreme" in result["gates_failed"]


def test_none_when_indicators_have_no_history_yet(monkeypatch):
    monkeypatch.setattr(rules.ta, "rsi", lambda closes, period: [None] * len(closes))
    _passing_ta_partial = None  # other indicators don't matter, rsi alone forces None
    candles = _candles(5)

    assert rules.evaluate("ZEC", "1h", candles, 4) is None


def test_ruleset_version_changes_when_rules_bytes_change(tmp_path):
    real_rules = Path(rules.__file__)
    geometry_path = real_rules.parent / "geometry.py"

    modified = tmp_path / "rules.py"
    modified.write_bytes(real_rules.read_bytes() + b"\n# tiny edit for the test\n")

    changed_version = rules._ruleset_version(modified, geometry_path)

    assert changed_version != rules.RULESET_VERSION
    # and the function is a pure function of those bytes: same input, same output
    assert changed_version == rules._ruleset_version(modified, geometry_path)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
