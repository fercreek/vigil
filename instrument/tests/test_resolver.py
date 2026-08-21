"""The resolver must be blind to side.

backtest_sim.py:106-155 -- the only honest exit simulation in the legacy repo, and
the seed for this module -- tested `low <= sl` and `high >= tp1` without consulting
`side`. Every SHORT it scored was scored as its mirror image. These tests exist so
that defect cannot be inherited.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument.geometry import assert_geometry            # noqa: E402
from instrument.resolver import Candle, resolve            # noqa: E402

ENTRY = 100.0
LONG_G = assert_geometry("LONG", ENTRY, 95.0, 106.0, 112.0)     # 1R = 5, rr1 = 1.2, rr2 = 2.4
SHORT_G = assert_geometry("SHORT", ENTRY, 105.0, 94.0, 88.0)    # exact mirror


def _bar(ts, o, h, l, c):
    return Candle(ts=ts, open=o, high=h, low=l, close=c)


def _mirror(candle: Candle) -> Candle:
    """Reflect a candle about the entry price: high and low swap roles."""
    r = lambda p: 2 * ENTRY - p           # noqa: E731
    return Candle(ts=candle.ts, open=r(candle.open), high=r(candle.low),
                  low=r(candle.high), close=r(candle.close))


SCENARIOS = {
    "stopped out":        [_bar("t1", 100, 101, 94, 95)],
    "tp1 then tp2":       [_bar("t1", 100, 107, 99, 106), _bar("t2", 106, 113, 105, 112)],
    "tp1 then breakeven": [_bar("t1", 100, 107, 99, 106), _bar("t2", 106, 107, 99, 100)],
    "timeout in profit":  [_bar("t1", 100, 103, 99, 102), _bar("t2", 102, 104, 101, 103)],
    "timeout in loss":    [_bar("t1", 100, 101, 97, 98), _bar("t2", 98, 99, 96, 97)],
    "ambiguous bar":      [_bar("t1", 100, 107, 94, 100)],
}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_long_and_short_mirrors_resolve_identically(name):
    bars = SCENARIOS[name]
    long_result = resolve(LONG_G, bars, max_bars=10)
    short_result = resolve(SHORT_G, [_mirror(b) for b in bars], max_bars=10)

    assert long_result.outcome == short_result.outcome, name
    assert long_result.r_realized == pytest.approx(short_result.r_realized), name
    assert long_result.mfe_r == pytest.approx(short_result.mfe_r), name
    assert long_result.mae_r == pytest.approx(short_result.mae_r), name
    assert long_result.tp1_hit == short_result.tp1_hit, name


def test_ambiguous_candle_takes_the_stop_and_says_so():
    """A candle holding both the stop and TP1 is unknowable at this timeframe.
    Guessing in our favour is how a backtest starts describing a bot that does not exist."""
    result = resolve(LONG_G, SCENARIOS["ambiguous bar"], max_bars=10)
    assert result.outcome == "SL"
    assert result.same_bar_ambiguous is True
    assert result.r_realized == -1.0


def test_both_counterfactuals_are_recorded():
    """The '+22.6R vs -17.8R' argument about ZEC was entirely about whether winners
    were assumed to reach TP1 or TP2. Storing both ends the argument."""
    result = resolve(LONG_G, SCENARIOS["tp1 then tp2"], max_bars=10)
    assert result.r_if_tp1_only == pytest.approx(1.2)     # all out at TP1
    assert result.r_if_no_partial == pytest.approx(2.4)   # let it all run
    assert result.r_realized == pytest.approx(1.8)        # half at each


def test_excursions_are_measured_even_on_losers():
    """MFE/MAE are the point of the instrument: with n small the win rate says
    nothing, but 'the stop was never threatened' or 'it reached 1.5R first' does."""
    result = resolve(LONG_G, SCENARIOS["stopped out"], max_bars=10)
    assert result.mfe_r == pytest.approx(0.2)
    assert result.mae_r == pytest.approx(-1.2)


def test_a_geometry_the_legacy_bot_stored_92_times_is_refused():
    from instrument.geometry import InvalidGeometry
    with pytest.raises(InvalidGeometry):
        assert_geometry("LONG", 246.16, 265.39, 268.85, 280.0)   # real row, trades.db id=3
