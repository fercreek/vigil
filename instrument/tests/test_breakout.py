"""Contract tests for breakout.py: same contract as rules.py (test_rules.py) --
no look-ahead, SENT never ships an empty trigger, an invalid geometry is
always BLOCKED -- plus the two gates specific to this ruleset: no breakout
inside the range, and volatility expansion.

ta.atr is monkeypatched to a fixed value so the expansion-ratio arithmetic is
pinned down without depending on real ATR math (ta.py is tested on its own,
in test_ta.py). Donchian highs/lows come from real candles -- that is the
part this module computes itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument import breakout                     # noqa: E402
from instrument.resolver import Candle               # noqa: E402

N_PRIOR = 25  # > DONCHIAN_PERIOD(20), leaves margin for the ATR(14) warmup too


def _flat_candles(n: int, level: float = 100.0, spread: float = 1.0) -> list[Candle]:
    """n flat candles: high/low/close never leave [level-spread, level+spread]."""
    return [Candle(ts=f"2026-01-01T{i:04d}", open=level, high=level + spread,
                   low=level - spread, close=level) for i in range(n)]


def _with_breakout_bar(prior: list[Candle], close: float, high: float, low: float
                       ) -> list[Candle]:
    bar = Candle(ts=f"2026-01-01T{len(prior):04d}", open=prior[-1].close,
                high=high, low=low, close=close)
    return prior + [bar]


def _fixed_atr(monkeypatch, value: float, recorder: list[int] | None = None):
    def atr(highs, lows, closes, period):
        if recorder is not None:
            recorder.append(len(closes))
        return [value] * len(closes)
    monkeypatch.setattr(breakout.ta, "atr", atr)


def _long_breakout_candles() -> list[Candle]:
    """Flat range at 100 +/- 1, then a bar that closes well above it with a
    wide true range -- clears both the Donchian breakout and (with atr fixed
    at 1.0 below) the 1.5x expansion filter comfortably."""
    prior = _flat_candles(N_PRIOR)
    return _with_breakout_bar(prior, close=150.0, high=152.0, low=149.0)


def test_no_lookahead_result_depends_only_on_prefix(monkeypatch):
    recorder: list[int] = []
    _fixed_atr(monkeypatch, 1.0, recorder)
    full = _long_breakout_candles() + _flat_candles(10, level=150.0)
    index = N_PRIOR  # the breakout bar itself
    truncated = full[: index + 1]

    result_full = breakout.evaluate("ZEC", "1h", full, index)
    result_truncated = breakout.evaluate("ZEC", "1h", truncated, index)

    assert result_full == result_truncated
    assert recorder and all(length == index + 1 for length in recorder)


def test_sent_never_ships_an_empty_trigger(monkeypatch):
    _fixed_atr(monkeypatch, 1.0)
    candles = _long_breakout_candles()

    result = breakout.evaluate("ZEC", "1h", candles, len(candles) - 1)

    assert result is not None
    assert result["decision"] == "SENT"
    assert result["side"] == "LONG"
    assert result["trigger"]
    assert "donchian_upper" in result["trigger"]


def test_short_breakout_sends_with_geometry_on_the_far_band(monkeypatch):
    _fixed_atr(monkeypatch, 1.0)
    prior = _flat_candles(N_PRIOR)
    candles = _with_breakout_bar(prior, close=50.0, high=101.0, low=48.0)

    result = breakout.evaluate("ZEC", "1h", candles, len(candles) - 1)

    assert result["decision"] == "SENT"
    assert result["side"] == "SHORT"
    # stop is the OTHER side of the broken channel (the upper band), not an
    # ATR multiple away from entry
    assert result["sl_price"] == pytest.approx(101.0)


def test_invalid_geometry_is_blocked_never_sent(monkeypatch):
    """Zero out both ATR multiples: tp1 == tp2 == entry, which assert_geometry
    refuses (entry < tp1 required). The breakout + expansion gates still
    pass -- the failure has to surface as BLOCKED, not a broken SENT row."""
    _fixed_atr(monkeypatch, 1.0)
    monkeypatch.setattr(breakout, "ATR_MULT_TP1", 0.0)
    monkeypatch.setattr(breakout, "ATR_MULT_TP2", 0.0)
    candles = _long_breakout_candles()

    result = breakout.evaluate("ZEC", "1h", candles, len(candles) - 1)

    assert result["decision"] == "BLOCKED"
    assert "entry_price" in result
    assert result.get("r_unit") is None


def test_suppressed_when_no_breakout():
    candles = _flat_candles(N_PRIOR + 1)  # close never leaves its own range

    result = breakout.evaluate("ZEC", "1h", candles, len(candles) - 1)

    assert result is not None
    assert result["decision"] == "SUPPRESSED"
    assert result["gates_failed"] == ["donchian_breakout"]


def test_suppressed_when_breakout_lacks_volatility_expansion(monkeypatch):
    """Price clears the channel by a hair, on a narrow bar, with ATR fixed
    high -- the breakout fires but the expansion ratio stays under 1.5x."""
    _fixed_atr(monkeypatch, 100.0)
    prior = _flat_candles(N_PRIOR)
    candles = _with_breakout_bar(prior, close=105.0, high=105.5, low=104.5)

    result = breakout.evaluate("ZEC", "1h", candles, len(candles) - 1)

    assert result["decision"] == "SUPPRESSED"
    assert result["gates_passed"] == ["donchian_breakout"]
    assert result["gates_failed"] == ["volatility_expansion"]


def test_none_when_warmup_is_short_of_a_full_lookback():
    candles = _flat_candles(5)
    assert breakout.evaluate("ZEC", "1h", candles, 4) is None


def test_suppressed_with_active_event_names_event_and_date(monkeypatch):
    _fixed_atr(monkeypatch, 1.0)
    candles = _long_breakout_candles()
    suppressions = {"fomc_calendar": {"event": "FOMC meeting", "date": "2026-09-16T18:00:00+00:00"}}

    result = breakout.evaluate("ZEC", "1h", candles, len(candles) - 1, suppressions=suppressions)

    assert result["decision"] == "SUPPRESSED"
    assert "FOMC meeting" in result["decision_reason"]
    assert "2026-09-16T18:00:00+00:00" in result["decision_reason"]
    assert result["gates_failed"] == ["event_window"]
    assert result["gates_passed"] == ["donchian_breakout"]  # side was already resolved


def test_ruleset_version_changes_when_breakout_bytes_change(tmp_path):
    real_breakout = Path(breakout.__file__)
    geometry_path = real_breakout.parent / "geometry.py"

    modified = tmp_path / "breakout.py"
    modified.write_bytes(real_breakout.read_bytes() + b"\n# tiny edit for the test\n")

    changed_version = breakout._ruleset_version(modified, geometry_path)

    assert changed_version != breakout.RULESET_VERSION
    assert changed_version == breakout._ruleset_version(modified, geometry_path)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
