"""Pure technical-analysis calculators -- no network, no cache, no global state.

Ported from ~/Documents/ideas/scalp_bot/indicators.py:22-215 (the calculate_*
functions only). Deliberately NOT ported: indicators.py:274-658, the get_*
wrappers that hit exchanges/CoinGecko and seed INDICATOR_CACHE with
{"usdt_d": 8.08, "btc_d": 52.0} -- an invented default that becomes real data
the moment a network call fails or the cache goes stale. That is the exact
defect this module exists to stop repeating.

Every function returns a list the SAME LENGTH as its input, None at indices
that do not yet have enough history. A caller reading index i is reading only
what was knowable at bar i -- never a value smoothed over bars that had not
closed yet. That is what closes the look-ahead hole.
"""
from __future__ import annotations

import statistics
from typing import Sequence


def rsi(closes: Sequence[float], period: int = 14) -> list[float | None]:
    """Wilder RSI, ported exactly from indicators.py:calculate_rsi (lines 22-35).

    Matches its pandas .ewm(alpha=1/period, adjust=False) recursion bar-for-bar:
    the running average gain/loss starts at 0 (there is no delta before the
    first close) and is smoothed forward from there -- never seeded from a
    plain SMA window, which is what most "Wilder RSI" reimplementations do and
    why they drift from this one after a few dozen bars.

    avg_loss == 0 (no down move has been smoothed in yet, or a flat series)
    maps to 50.0 -- neutral -- the same fallback indicators.py applies when its
    pandas division produces NaN.
    """
    n = len(closes)
    out: list[float | None] = [None] * n
    if n == 0:
        return out
    alpha = 1.0 / period
    avg_gain = 0.0
    avg_loss = 0.0
    for i in range(n):
        delta = closes[i] - closes[i - 1] if i > 0 else 0.0
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = alpha * gain + (1 - alpha) * avg_gain
        avg_loss = alpha * loss + (1 - alpha) * avg_loss
        if i >= period:
            if avg_loss == 0:
                out[i] = 50.0
            else:
                rs = avg_gain / avg_loss
                out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def _true_range(highs: Sequence[float], lows: Sequence[float],
                 closes: Sequence[float], i: int) -> float:
    """True range at index i. Index 0 has no prior close, so it is just the
    bar's own high-low range -- same as pandas' skipna max() on that row in
    indicators.py:calculate_atr / calculate_adx."""
    if i == 0:
        return highs[i] - lows[i]
    return max(highs[i] - lows[i],
               abs(highs[i] - closes[i - 1]),
               abs(lows[i] - closes[i - 1]))


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
        period: int = 14) -> list[float | None]:
    """Average True Range, Wilder-smoothed the same way as rsi() above."""
    n = len(closes)
    out: list[float | None] = [None] * n
    if n == 0:
        return out
    alpha = 1.0 / period
    avg = 0.0
    for i in range(n):
        avg = alpha * _true_range(highs, lows, closes, i) + (1 - alpha) * avg
        if i >= period:
            out[i] = avg
    return out


def ema(values: Sequence[float], period: int) -> list[float | None]:
    """Exponential moving average, SMA-seeded (the standard TA convention): the
    first `period` values give the seed, then the recursion runs with
    alpha=2/(period+1)."""
    n = len(values)
    out: list[float | None] = [None] * n
    if n < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    alpha = 2.0 / (period + 1)
    prev = seed
    for i in range(period, n):
        prev = alpha * values[i] + (1 - alpha) * prev
        out[i] = prev
    return out


def bbands(closes: Sequence[float], period: int = 20, k: float = 2.0
           ) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Bollinger Bands with population stdev (ddof=0), matching
    indicators.py:calculate_bollinger_bands. Returns (upper, mid, lower)."""
    n = len(closes)
    upper: list[float | None] = [None] * n
    mid: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = closes[i - period + 1:i + 1]
        mean = sum(window) / period
        std = statistics.pstdev(window)
        upper[i] = mean + k * std
        mid[i] = mean
        lower[i] = mean - k * std
    return upper, mid, lower


def adx(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
        period: int = 14) -> list[float | None]:
    """Average Directional Index, Wilder-smoothed. +DM/-DM use the textbook
    definition, compared against the RAW up/down move -- not a partially
    filtered one. indicators.py:calculate_adx reassigns plus_dm before it
    computes the minus_dm mask, so its minus_dm ends up compared against the
    already-filtered plus_dm instead of the raw move. That order dependency is
    a bug in the source, not a spec, so it is not ported."""
    n = len(closes)
    out: list[float | None] = [None] * n
    if n == 0:
        return out
    alpha = 1.0 / period
    atr_avg = plus_dm_avg = minus_dm_avg = dx_avg = 0.0
    for i in range(n):
        tr = _true_range(highs, lows, closes, i)
        if i == 0:
            plus_dm = minus_dm = 0.0
        else:
            up_move = highs[i] - highs[i - 1]
            down_move = lows[i - 1] - lows[i]
            plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
            minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0
        atr_avg = alpha * tr + (1 - alpha) * atr_avg
        plus_dm_avg = alpha * plus_dm + (1 - alpha) * plus_dm_avg
        minus_dm_avg = alpha * minus_dm + (1 - alpha) * minus_dm_avg

        plus_di = 100.0 * plus_dm_avg / atr_avg if atr_avg else 0.0
        minus_di = 100.0 * minus_dm_avg / atr_avg if atr_avg else 0.0
        di_sum = plus_di + minus_di
        dx = 100.0 * abs(plus_di - minus_di) / di_sum if di_sum else 0.0
        dx_avg = alpha * dx + (1 - alpha) * dx_avg

        if i >= period * 2:
            out[i] = dx_avg
    return out


def rvol(volumes: Sequence[float], period: int = 20) -> list[float | None]:
    """Relative volume: current bar vs the mean of the trailing `period` bars,
    current bar included -- matches indicators.py:calculate_rvol's tail(period)
    window, which is not a lookback that excludes the bar being scored."""
    n = len(volumes)
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = volumes[i - period + 1:i + 1]
        avg = sum(window) / period
        out[i] = volumes[i] / avg if avg else 1.0
    return out
