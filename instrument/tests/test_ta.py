"""Tests for the pure TA calculators.

The RSI cross-check does not import indicators.py (it drags in ccxt +
exchange_singleton, which touch the network at import time). Instead it
replicates indicators.py:calculate_rsi's exact pandas expression -- the thing
ta.rsi() is supposed to match bar-for-bar -- as an independent oracle.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument.ta import adx, atr, bbands, ema, rsi, rvol      # noqa: E402

# Deterministic jagged series -- real-looking, not monotonic, no exact repeats
# that would make a division land on zero by accident.
PRICES = [100, 102, 101, 105, 107, 106, 108, 110, 109, 111, 115, 114, 116, 120,
          118, 119, 121, 117, 115, 116, 118, 122, 125, 123, 128, 130, 129, 127,
          126, 124]
HIGHS = [p + 1 for p in PRICES]
LOWS = [p - 1 for p in PRICES]
VOLUMES = [1000 + (i % 7) * 250 for i in range(len(PRICES))]

PERIOD = 14
SIX_FUNCS_ON = {
    "rsi": lambda: rsi(PRICES, PERIOD),
    "atr": lambda: atr(HIGHS, LOWS, PRICES, PERIOD),
    "ema": lambda: ema(PRICES, PERIOD),
    "adx": lambda: adx(HIGHS, LOWS, PRICES, PERIOD),
    "rvol": lambda: rvol(VOLUMES, PERIOD),
}


@pytest.mark.parametrize("name", list(SIX_FUNCS_ON))
def test_output_length_matches_input_length(name):
    assert len(SIX_FUNCS_ON[name]()) == len(PRICES)


def test_bbands_output_length_matches_input_length():
    upper, mid, lower = bbands(PRICES, period=20)
    assert len(upper) == len(mid) == len(lower) == len(PRICES)


def _pandas_wilder_rsi(prices: list[float], period: int) -> list[float]:
    """Same expression as indicators.py:calculate_rsi, lines 27-35, but kept
    as a full series instead of only the last bar. NaN (avg_loss == 0) folds
    to 50.0, same fallback calculate_rsi itself applies to its own last value."""
    pd = pytest.importorskip("pandas")
    s = pd.Series(prices, dtype=float)
    delta = s.diff()
    gain = delta.where(delta > 0, 0.0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1 / period, adjust=False).mean()
    loss_safe = loss.replace(0, float("nan"))
    rs = gain / loss_safe
    out = 100 - (100 / (1 + rs))
    return [50.0 if pd.isna(v) else float(v) for v in out]


def test_rsi_matches_wilder_smoothing_from_the_legacy_bot():
    ours = rsi(PRICES, PERIOD)
    reference = _pandas_wilder_rsi(PRICES, PERIOD)
    for i in range(PERIOD, len(PRICES)):
        assert ours[i] == pytest.approx(reference[i], abs=1e-9), f"index {i}"


@pytest.mark.parametrize("name,call", [
    ("rsi", lambda short: rsi(short, PERIOD)),
    ("atr", lambda short: atr(short, short, short, PERIOD)),
    ("ema", lambda short: ema(short, PERIOD)),
    ("adx", lambda short: adx(short, short, short, PERIOD)),
    ("rvol", lambda short: rvol(short, PERIOD)),
])
def test_short_input_returns_all_none_without_raising(name, call):
    short_series = PRICES[:5]  # shorter than PERIOD=14
    result = call(short_series)
    assert len(result) == len(short_series)
    assert all(v is None for v in result)


def test_bbands_short_input_returns_all_none_without_raising():
    short_series = PRICES[:5]
    upper, mid, lower = bbands(short_series, period=20)
    assert all(v is None for v in upper + mid + lower)


def test_flat_series_atr_is_zero_and_rsi_never_divides_by_zero():
    flat = [100.0] * 30
    atr_out = atr(flat, flat, flat, PERIOD)
    rsi_out = rsi(flat, PERIOD)
    for i in range(PERIOD, len(flat)):
        assert atr_out[i] == 0.0, f"atr index {i}"
        assert rsi_out[i] == 50.0, f"rsi index {i}"  # neutral, not NaN/inf


def test_bbands_upper_is_never_below_mid_which_is_never_below_lower():
    upper, mid, lower = bbands(PRICES, period=10)
    for i in range(len(PRICES)):
        if mid[i] is None:
            continue
        assert upper[i] >= mid[i] >= lower[i], f"index {i}"
