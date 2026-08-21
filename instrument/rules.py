"""The one deterministic ruleset. It fires; the LLM only annotates alongside it
(decision 2, 2026-08-21) -- this module is the sole gate on `decision`.

Shape: EMA200 sets the side (pullback-in-trend, not pure mean-reversion), RSI
extremes + Bollinger %B confirm the pullback is stretched, ADX confirms it's a
real trend and not chop. All four indicators come from `ta.py`'s documented
contract (list in, same-length list out, None where there isn't history yet).

Where the targets came from: the 59-trade baseline (see _MAP-instrument.md)
measured MFE median +0.67R against legacy targets that averaged 1.27R and were
touched by only 7 of 59 trades -- the objective was placed past where price
actually goes. TP1_R_MULT below sits on that median instead of on a multiplier
that "looks right"; TP2_R_MULT is the stretch leg for the runner half that
resolver.py sends to breakeven once TP1 fills.

Everything this function decides is logged -- SENT, SUPPRESSED, BLOCKED, or a
skip for insufficient warmup -- because the legacy bot only ever wrote down the
signals that fired and could never say how many times it looked and passed.

NOT LIVE-READY. A temporal-split grid search over ZEC 1h (calibrate on the
first ~1.9 weeks, freeze thresholds, test on the remaining ~3 weeks, n>=30
required before a config enters the comparison) found no config that clears
both n>=30 and <=3 alerts/week -- that ceiling caps this corpus at roughly 19
signals total, so the sample is structurally too small (matches
_MAP-instrument.md's own ~10-week estimate to reach n=30 live at this budget
with one symbol). Every grid cell that *did* reach n>=30 needed ~20-26
alerts/week to get there, and the best of those (rsi<=45, bb<=0.4, adx>=10)
went from +0.382R / 83.3% WR in calibration (n=48) to -0.341R / 39.1% WR out
of sample (n=69) -- a full sign flip, the same shape of defect that let a
cherry-picked n=15 cell get shipped and quoted as "60% WR, +8.38R" for months
in the legacy bot. A naive always-LONG baseline with the *same* geometry and
no gate at all was mildly positive in both halves (+0.046R calib, +0.172R
test) -- ZEC drifted up over the whole window, so part of any long-biased
config's apparent edge is that drift, not the RSI/BB/ADX gates.

The thresholds below are therefore left at standard textbook values (RSI
30/70, ADX>=25, %B within 20% of a band edge) instead of anything fit to this
corpus. On this ~44-day window they never all align at once (0 SENT signals
in either half) -- a consequence of being untuned, not a bug, and strictly
safer than shipping a fitted config that later inverts. Retiring or keeping
this ruleset per the pre-registered criterion (_MAP-instrument.md: retire if
the expectancy CI's upper bound stays < 0 after 100 resolved signals) needs
live or paper accumulation first; there is no sample here big enough to apply
that criterion yet.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import ta
from .geometry import LONG, SHORT, InvalidGeometry, assert_geometry
from .resolver import Candle

# ---------------------------------------------------------------------------
# RULESET_VERSION -- sha of the bytes that actually define the rule. Computed
# at import time so a change to either file changes the version automatically;
# nobody has to remember to bump a string by hand.
# ---------------------------------------------------------------------------
def _ruleset_version(rules_path: Path | None = None, geometry_path: Path | None = None) -> str:
    here = Path(__file__).parent
    rules_path = rules_path or (here / "rules.py")
    geometry_path = geometry_path or (here / "geometry.py")
    payload = rules_path.read_bytes() + geometry_path.read_bytes()
    return hashlib.sha256(payload).hexdigest()[:10]


RULESET_VERSION = _ruleset_version()

# ---------------------------------------------------------------------------
# Indicator periods -- standard defaults, nothing tuned here.
# ---------------------------------------------------------------------------
RSI_PERIOD = 14
ATR_PERIOD = 14
EMA_PERIOD = 200
BB_PERIOD = 20
BB_K = 2.0
ADX_PERIOD = 14

# ---------------------------------------------------------------------------
# Gate thresholds -- standard textbook values, deliberately NOT fit to the ZEC
# corpus (see the module docstring: the grid search that tried to fit them
# produced a config whose sign flipped out of sample, which is exactly the
# failure mode these defaults avoid). No calendar, no hand-picked expiry date:
# the legacy bot's 4 calendars were all stale and gated signals in silence.
# ---------------------------------------------------------------------------
RSI_OVERSOLD = 30.0
RSI_OVERBOUGHT = 70.0
BB_PCTB_LOW = 0.2
BB_PCTB_HIGH = 0.8
ADX_MIN = 25.0
ATR_MIN_PCT = 0.004  # legacy MIN_ATR_PCT was 0.005; kept in the same order of magnitude

# ---------------------------------------------------------------------------
# Geometry -- SL sizes 1R in ATR; TP1 sits at the measured MFE median, TP2 is
# the stretch leg. min_rr=0.0: the ratio is a reported fact (breakeven_wr),
# not a gate -- gating on it would just re-introduce a hand-picked floor.
# ---------------------------------------------------------------------------
SL_ATR_MULT = 1.5
TP1_R_MULT = 0.7
TP2_R_MULT = 1.3
MIN_RR = 0.0

REGIME = "TREND_PULLBACK"


def _event_suppression(suppressions: dict[str, dict] | None) -> str | None:
    """First active entry in `suppressions`, formatted for decision_reason, or
    None. `suppressions` is context the CALLER already resolved (main.py's
    cache.require("fomc_calendar", on_stale="open") plus its own +/-24h window
    check) -- this function only reads the dict handed to it. That is what
    keeps evaluate() a pure function of its arguments: no database, no
    network, no wall-clock read, here or anywhere else in this module."""
    if not suppressions:
        return None
    _, info = next(iter(suppressions.items()))
    return f"{info.get('event', 'scheduled event')} on {info.get('date', 'unknown date')}"


def evaluate(symbol: str, timeframe: str, candles: list[Candle], index: int,
             suppressions: dict[str, dict] | None = None) -> dict | None:
    """Evaluate the CLOSED candle at `index`. Entry is its close.

    Reads candles[:index+1] and nothing past it -- that slice is the only place
    in this function that touches `candles`, which is what keeps this look-ahead
    free. Returns a signals-table-ready dict, or None when there isn't enough
    warmup yet for the indicators to mean anything (not a registrable evaluation).

    `suppressions` is optional pre-resolved event context (see
    `_event_suppression`) -- e.g. a live FOMC blackout window. When it names an
    active event the decision is SUPPRESSED with a reason that names the event
    and its date, ahead of the RSI/BB/ADX gates below.
    """
    if index < 0 or index >= len(candles):
        raise IndexError(f"index {index} out of range for {len(candles)} candles")

    window = candles[: index + 1]
    bar = window[-1]
    closes = [c.close for c in window]
    highs = [c.high for c in window]
    lows = [c.low for c in window]

    rsi = ta.rsi(closes, RSI_PERIOD)[-1]
    atr = ta.atr(highs, lows, closes, ATR_PERIOD)[-1]
    ema200 = ta.ema(closes, EMA_PERIOD)[-1]
    bb_upper, _bb_mid, bb_lower = ta.bbands(closes, BB_PERIOD, BB_K)
    bb_upper, bb_lower = bb_upper[-1], bb_lower[-1]
    adx = ta.adx(highs, lows, closes, ADX_PERIOD)[-1]

    if None in (rsi, atr, ema200, bb_upper, bb_lower, adx):
        return None  # not enough warmup -- nothing to log yet

    close = bar.close
    pctb = (close - bb_lower) / (bb_upper - bb_lower) if bb_upper > bb_lower else None

    trigger = {"rsi": round(rsi, 2), "atr": round(atr, 6), "ema200": round(ema200, 4),
               "bb_pctb": round(pctb, 4) if pctb is not None else None, "adx": round(adx, 2),
               "close": close}
    base = dict(ruleset_version=RULESET_VERSION, emitted_at=bar.ts, bar_ts=bar.ts,
               symbol=symbol, timeframe=timeframe, trigger=trigger, regime=REGIME,
               atr_pct=round(atr / close, 4) if close else None)

    if close > ema200:
        side = LONG
    elif close < ema200:
        side = SHORT
    else:
        # Degenerate tie. `side` is NOT NULL in the schema, so a value has to go
        # in -- LONG is an arbitrary pick, made harmless by decision=SUPPRESSED
        # and a reason that says exactly why.
        return {**base, "side": LONG, "decision": "SUPPRESSED",
                "decision_reason": "close == ema200: no directional bias",
                "gates_passed": [], "gates_failed": ["trend_bias"]}

    event = _event_suppression(suppressions)
    if event is not None:
        return {**base, "side": side, "decision": "SUPPRESSED",
                "decision_reason": f"event window: {event}",
                "gates_passed": [], "gates_failed": ["event_window"]}

    gates_passed: list[str] = []
    gates_failed: list[str] = []

    def gate(name: str, passed: bool) -> None:
        (gates_passed if passed else gates_failed).append(name)

    gate("rsi_extreme", rsi <= RSI_OVERSOLD if side == LONG else rsi >= RSI_OVERBOUGHT)
    gate("bb_confluence", pctb is not None and
        (pctb <= BB_PCTB_LOW if side == LONG else pctb >= BB_PCTB_HIGH))
    gate("adx_trending", adx >= ADX_MIN)
    gate("atr_min", bool(close) and (atr / close) >= ATR_MIN_PCT)

    if gates_failed:
        return {**base, "side": side, "decision": "SUPPRESSED",
                "decision_reason": f"failed: {', '.join(gates_failed)}",
                "gates_passed": gates_passed, "gates_failed": gates_failed}

    r_unit_raw = SL_ATR_MULT * atr
    if side == LONG:
        entry, sl = close, close - r_unit_raw
        tp1, tp2 = close + TP1_R_MULT * r_unit_raw, close + TP2_R_MULT * r_unit_raw
    else:
        entry, sl = close, close + r_unit_raw
        tp1, tp2 = close - TP1_R_MULT * r_unit_raw, close - TP2_R_MULT * r_unit_raw

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
    # worst end of the range on purpose: it is the bar to clear when the runner
    # never reaches TP2. Storing the all-out-at-TP1 figure let the alert claim
    # "you are ahead" against a floor up to 15 points too low.
