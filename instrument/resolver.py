"""Walk closed candles and decide what actually happened to a signal.

This is the module the legacy bot never had. It computed the exit price
(trade_monitor.py:141,162,186), put it in a Telegram message, and then called
update_trade_status(id, status) -- which persisted a label and datetime.now().
That is why 31 of 91 closes share one timestamp to the second, why there is no
exit_price column, and why the P&L had to be fabricated from the status
(tracker.py:958-969).

Two properties are non-negotiable here:
  1. SIDE-AWARE. The legacy simulate_trade (backtest_sim.py:106-155) tested
     `low <= sl` and `high >= tp1` without looking at side, so every SHORT was
     scored as its own mirror image. Copying it unchanged would have reproduced
     the 22-row defect inside the resolver -- the worst possible place.
  2. PESSIMISTIC ON AMBIGUITY. When a candle contains both the stop and a target,
     the true order is unknowable at this timeframe. We take the stop and flag the
     row. A resolver that guesses in its own favour is how backtests come to
     describe a bot that does not exist.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Sequence

from .geometry import Geometry, LONG

RESOLVER_VERSION = "r1"
PARTIAL_AT_TP1 = 0.5   # half off at TP1, stop to breakeven on the rest


@dataclass(frozen=True)
class Candle:
    ts: str
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Resolution:
    outcome: str
    exit_price: float
    exit_bar_ts: str
    bars_held: int
    tp1_hit: bool
    tp1_bar_ts: str | None
    mae_r: float
    mfe_r: float
    r_realized: float
    r_if_tp1_only: float
    r_if_no_partial: float
    same_bar_ambiguous: bool
    resolution_source: str = "BARS"

    def as_row(self) -> dict:
        return asdict(self)


def _touched(geometry: Geometry, candle: Candle, level: float, favourable: bool) -> bool:
    """Did price reach `level`? Direction depends on side and on which way helps us."""
    if geometry.side == LONG:
        return candle.high >= level if favourable else candle.low <= level
    return candle.low <= level if favourable else candle.high >= level


def resolve(geometry: Geometry, candles: Sequence[Candle] | Iterable[Candle],
            max_bars: int) -> Resolution:
    """Resolve one signal against the candles that followed it.

    `candles` must start at the bar AFTER the trigger bar and be strictly ordered.
    """
    bars = list(candles)
    if not bars:
        return Resolution("VOID", geometry.entry, "", 0, False, None, 0.0, 0.0,
                          0.0, 0.0, 0.0, False, "FORCED")

    mfe_r = mae_r = 0.0
    tp1_hit = False
    tp1_bar_ts: str | None = None
    ambiguous = False
    # the stop that is actually in force: entry once half is off at TP1
    active_stop = geometry.sl

    for index, candle in enumerate(bars[:max_bars], start=1):
        best = candle.high if geometry.side == LONG else candle.low
        worst = candle.low if geometry.side == LONG else candle.high
        mfe_r = max(mfe_r, geometry.r_at(best))
        mae_r = min(mae_r, geometry.r_at(worst))

        hit_stop = _touched(geometry, candle, active_stop, favourable=False)
        hit_tp1 = not tp1_hit and _touched(geometry, candle, geometry.tp1, favourable=True)
        hit_tp2 = _touched(geometry, candle, geometry.tp2, favourable=True)

        if not tp1_hit:
            if hit_stop and hit_tp1:
                ambiguous = True          # both in one candle: take the stop
                return _finish("SL", geometry.sl, candle.ts, index, False, None,
                               mae_r, mfe_r, geometry, ambiguous)
            if hit_stop:
                return _finish("SL", geometry.sl, candle.ts, index, False, None,
                               mae_r, mfe_r, geometry, ambiguous)
            if hit_tp1:
                tp1_hit, tp1_bar_ts = True, candle.ts
                active_stop = geometry.entry           # breakeven on the runner
                if hit_tp2:
                    return _finish("TP2", geometry.tp2, candle.ts, index, True,
                                   tp1_bar_ts, mae_r, mfe_r, geometry, ambiguous)
                continue

        # Same pessimism as before TP1, and for the same reason. This branch used to
        # check TP2 first and never set the flag, so a candle holding both breakeven
        # and TP2 resolved as the best case -- exactly on the highest-paying path.
        if hit_tp2 and hit_stop:
            ambiguous = True
            return _finish("TP1_THEN_BE", geometry.entry, candle.ts, index, True,
                           tp1_bar_ts, mae_r, mfe_r, geometry, ambiguous)
        if hit_tp2:
            return _finish("TP1_THEN_TP2", geometry.tp2, candle.ts, index, True,
                           tp1_bar_ts, mae_r, mfe_r, geometry, ambiguous)
        if hit_stop:                                   # stopped at breakeven
            return _finish("TP1_THEN_BE", geometry.entry, candle.ts, index, True,
                           tp1_bar_ts, mae_r, mfe_r, geometry, ambiguous)

    last = bars[min(len(bars), max_bars) - 1]
    return _finish("TIMEOUT", last.close, last.ts, min(len(bars), max_bars),
                   tp1_hit, tp1_bar_ts, mae_r, mfe_r, geometry, ambiguous)


def _finish(outcome: str, exit_price: float, exit_ts: str, bars: int, tp1_hit: bool,
            tp1_ts: str | None, mae_r: float, mfe_r: float, geometry: Geometry,
            ambiguous: bool) -> Resolution:
    """Compute the three R figures. Both counterfactuals are stored so nobody has
    to argue later about whether a number assumed TP1 or TP2 -- the legacy '+22.6R
    vs -17.8R' disagreement was exactly that, and it decided which experiment lived."""
    exit_r = geometry.r_at(exit_price)

    if outcome == "SL":
        r_realized = -1.0
    elif outcome in ("TP2", "TP1_THEN_TP2"):
        r_realized = PARTIAL_AT_TP1 * geometry.rr_tp1 + (1 - PARTIAL_AT_TP1) * geometry.rr_tp2
    elif outcome == "TP1_THEN_BE":
        r_realized = PARTIAL_AT_TP1 * geometry.rr_tp1
    else:  # TIMEOUT
        r_realized = (PARTIAL_AT_TP1 * geometry.rr_tp1 + (1 - PARTIAL_AT_TP1) * exit_r
                      if tp1_hit else exit_r)

    if outcome == "SL":
        r_tp1_only = r_no_partial = -1.0
    else:
        r_tp1_only = geometry.rr_tp1 if tp1_hit else exit_r
        r_no_partial = geometry.rr_tp2 if outcome in ("TP2", "TP1_THEN_TP2") else exit_r

    return Resolution(
        outcome=outcome, exit_price=round(exit_price, 8), exit_bar_ts=exit_ts,
        bars_held=bars, tp1_hit=tp1_hit, tp1_bar_ts=tp1_ts,
        mae_r=round(mae_r, 3), mfe_r=round(mfe_r, 3),
        r_realized=round(r_realized, 3), r_if_tp1_only=round(r_tp1_only, 3),
        r_if_no_partial=round(r_no_partial, 3),
        same_bar_ambiguous=ambiguous, resolution_source="BARS")
