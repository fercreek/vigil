"""Breakout strategy: range expansion, not pullback-in-trend.

The problem this exists to fix is measured, not theoretical: in 30 days of
production the bot sent 8 alerts, all 8 on ZEC, and on 2026-08-19 ETH moved
+19.6% in 24h with rules.py silent -- at that moment ETH's RSI was 96.6 and
price sat ABOVE the upper Bollinger band, the exact opposite of what
rules.py's pullback gates require (RSI<=30, price in the LOWER band -- see
that module's docstring). rules.py is not broken; it is a pullback-in-trend
ruleset and is, by design, blind to a clean directional break of a range.
This module is built to see that move instead.

Mechanism -- the closest thing to an edge pre-registered in HYPOTHESES.md is
H3 (four consecutive same-direction closes, +0.015R, beat the baseline in 4 of
6 symbols, missed its own significance bar): momentum continuation, the same
family as a breakout -- price has already shown its hand, trade with it
instead of against it. This module operationalises that mechanism with a
textbook range-breakout instrument (a Donchian channel plus a
volatility-expansion filter) rather than H3's raw streak count, because a
streak of same-direction closes says nothing about whether the move clears
enough ground to be worth trading; a channel breakout does.

Parameters, fixed for a stated reason, NOT fit to this corpus:
  - DONCHIAN_PERIOD=20: the Entry-1 lookback from the original Turtle Trading
    rules (a 20-period Donchian channel breakout), and the same period
    BB_PERIOD already uses two doors down in rules.py -- 20 is a length this
    package already treats as a standard, not a knob.
  - ATR_PERIOD=14: the same Wilder default used everywhere else in ta.py.
  - EXPANSION_ATR_MULT=1.5: the breakout bar's true range against its own
    TRAILING ATR(14) -- the ATR reading from the bar BEFORE the breakout bar,
    exactly H4's convention in HYPOTHESES.md ("trailing ATR, excludes the
    shock bar itself"). 1.5x sits at the midpoint between "no filter" (1.0x,
    any range at all would count) and the 3.0x this package already reserves
    for an extreme single-bar capitulation shock in H4 -- a breakout needs a
    visibly-above-normal range, not that extremity.

Geometry deliberately differs from rules.py's, and the difference is the
point, not an inconsistency:
  - STOP sits on the OTHER SIDE of the SAME Donchian channel that was broken
    (the far band, not entry minus an ATR multiple) -- risking the width of
    the base, the standard breakout risk definition. A pullback's stop
    protects a stretched entry against reverting the last leg; a breakout's
    stop protects against the break being false, which only reverting the
    WHOLE base range would confirm.
  - TARGET is an outright ATR multiple added to entry (ATR_MULT_TP1=2.0,
    ATR_MULT_TP2=4.0 -- TP2 is exactly 2x TP1's distance, a round ratio,
    picked before any run, not after one), not an R-multiple of the stop the
    way rules.py's TP1/TP2 are. The stop here is sized by the base (can be
    wide or narrow independent of current volatility); the distance a genuine
    breakout can travel is sized by volatility, not by how wide the base
    happened to be. R:R is still always derived from the real prices via
    geometry.py, never from a multiplier -- it just will not land near a
    round number by construction, because the two legs come from different
    rulers.

Same evaluation contract as rules.py: reads candles[:index+1] and nothing
past it, returns a signals-table-ready dict or None for insufficient warmup,
and every evaluation is logged with a decision in
{SENT, SUPPRESSED, BLOCKED, ERROR}.

NOT LIVE-READY, same reason as rules.py: this operationalises H3's mechanism,
it is not H3's tested configuration, and HYPOTHESES.md's success criteria
have not been run against this exact instrument. There is no evidence yet
that this has an edge -- see notify.py, which says so on every alert.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import ta
from .geometry import LONG, SHORT, InvalidGeometry, assert_geometry
from .resolver import Candle

# ---------------------------------------------------------------------------
# RULESET_VERSION -- same technique as rules.py: sha of the bytes that define
# this rule, computed at import time so nobody has to remember to bump it.
# ---------------------------------------------------------------------------
def _ruleset_version(breakout_path: Path | None = None, geometry_path: Path | None = None) -> str:
    here = Path(__file__).parent
    breakout_path = breakout_path or (here / "breakout.py")
    geometry_path = geometry_path or (here / "geometry.py")
    payload = breakout_path.read_bytes() + geometry_path.read_bytes()
    return hashlib.sha256(payload).hexdigest()[:10]


RULESET_VERSION = _ruleset_version()

# ---------------------------------------------------------------------------
# Parameters -- see the module docstring for why each value is what it is.
# ---------------------------------------------------------------------------
DONCHIAN_PERIOD = 20
ATR_PERIOD = 14
EXPANSION_ATR_MULT = 1.5
ATR_MULT_TP1 = 2.0
ATR_MULT_TP2 = 4.0
MIN_RR = 0.0  # a reported fact (breakeven_wr), not a gate -- see rules.py's rationale

REGIME = "BREAKOUT_EXPANSION"


def _event_suppression(suppressions: dict[str, dict] | None) -> str | None:
    """Same helper as rules.py, duplicated rather than imported: the two
    strategy modules stay independent on purpose, so retiring one is never a
    reason to touch the other."""
    if not suppressions:
        return None
    _, info = next(iter(suppressions.items()))
    return f"{info.get('event', 'scheduled event')} on {info.get('date', 'unknown date')}"


def evaluate(symbol: str, timeframe: str, candles: list[Candle], index: int,
             suppressions: dict[str, dict] | None = None) -> dict | None:
    """Evaluate the CLOSED candle at `index`. Entry is its close.

    Reads candles[:index+1] and nothing past it. Returns a signals-table-ready
    dict, or None when there isn't enough warmup for a full DONCHIAN_PERIOD
    lookback plus ATR history yet (not a registrable evaluation).
    """
    if index < 0 or index >= len(candles):
        raise IndexError(f"index {index} out of range for {len(candles)} candles")
    if index < DONCHIAN_PERIOD:
        return None  # not enough bars for a full lookback window yet

    window = candles[: index + 1]
    bar = window[-1]
    closes = [c.close for c in window]
    highs = [c.high for c in window]
    lows = [c.low for c in window]

    atr_series = ta.atr(highs, lows, closes, ATR_PERIOD)
    atr_now, atr_trailing = atr_series[-1], atr_series[-2]
    if atr_now is None or atr_trailing is None:
        return None  # not enough warmup yet -- nothing to log

    close = bar.close
    # prior N bars, excluding the current one -- the range that gets broken
    prior_highs, prior_lows = highs[-(DONCHIAN_PERIOD + 1):-1], lows[-(DONCHIAN_PERIOD + 1):-1]
    donchian_upper, donchian_lower = max(prior_highs), min(prior_lows)
    # true range of the breakout bar itself, same definition as ta.py's _true_range
    prev_close = closes[-2]
    tr = max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))
    expansion_ratio = round(tr / atr_trailing, 3) if atr_trailing else None

    trigger = {"donchian_upper": round(donchian_upper, 8), "donchian_lower": round(donchian_lower, 8),
               "close": close, "tr": round(tr, 8), "atr_trailing": round(atr_trailing, 6),
               "expansion_ratio": expansion_ratio}
    base = dict(ruleset_version=RULESET_VERSION, emitted_at=bar.ts, bar_ts=bar.ts,
               symbol=symbol, timeframe=timeframe, trigger=trigger, regime=REGIME,
               atr_pct=round(atr_now / close, 4) if close else None)

    # donchian_upper >= donchian_lower always (max highs >= min lows), so a
    # single close cannot break both sides at once -- unlike H1, there is no
    # "both fired, skip" branch to write here.
    broke_up, broke_down = close > donchian_upper, close < donchian_lower
    if not (broke_up or broke_down):
        # `side` is NOT NULL in the schema, so a value has to go in -- LONG is
        # an arbitrary pick, made harmless by decision=SUPPRESSED. This is the
        # OVERWHELMING majority case: most bars sit inside their own range.
        return {**base, "side": LONG, "decision": "SUPPRESSED",
                "decision_reason": f"close inside the Donchian({DONCHIAN_PERIOD}) range: no breakout",
                "gates_passed": [], "gates_failed": ["donchian_breakout"]}
    side = LONG if broke_up else SHORT

    event = _event_suppression(suppressions)
    if event is not None:
        return {**base, "side": side, "decision": "SUPPRESSED",
                "decision_reason": f"event window: {event}",
                "gates_passed": ["donchian_breakout"], "gates_failed": ["event_window"]}

    gates_passed, gates_failed = ["donchian_breakout"], []
    if expansion_ratio is not None and expansion_ratio >= EXPANSION_ATR_MULT:
        gates_passed.append("volatility_expansion")
    else:
        gates_failed.append("volatility_expansion")

    if gates_failed:
        return {**base, "side": side, "decision": "SUPPRESSED",
                "decision_reason": f"failed: {', '.join(gates_failed)}",
                "gates_passed": gates_passed, "gates_failed": gates_failed}

    if side == LONG:
        entry, sl = close, donchian_lower
        tp1, tp2 = entry + ATR_MULT_TP1 * atr_now, entry + ATR_MULT_TP2 * atr_now
    else:
        entry, sl = close, donchian_upper
        tp1, tp2 = entry - ATR_MULT_TP1 * atr_now, entry - ATR_MULT_TP2 * atr_now

    try:
        geometry = assert_geometry(side, entry, sl, tp1, tp2, min_rr=MIN_RR)
    except InvalidGeometry as exc:
        return {**base, "side": side, "decision": "BLOCKED", "decision_reason": str(exc),
                "gates_passed": gates_passed, "gates_failed": gates_failed,
                "entry_price": round(entry, 8), "sl_price": round(sl, 8),
                "tp1_price": round(tp1, 8), "tp2_price": round(tp2, 8)}

    return {**base, "side": side, "decision": "SENT",
            "decision_reason": f"passed: {', '.join(gates_passed)}",
            "gates_passed": gates_passed, "gates_failed": gates_failed,
            "entry_price": geometry.entry, "sl_price": geometry.sl,
            "tp1_price": geometry.tp1, "tp2_price": geometry.tp2,
            "r_unit": geometry.r_unit, "rr_tp1": round(geometry.rr_tp1, 3),
            "rr_tp2": round(geometry.rr_tp2, 3), "breakeven_wr": round(geometry.breakeven_wr_range()[1], 4)}
    # worst end of the range, same reason as rules.py's tail comment: it is
    # the bar to clear when the runner never reaches TP2.
