"""One-shot test of the 5 exit designs pre-registered in ../EXIT_HYPOTHESES.md.

Entry is fixed and shared with test_hypotheses.py's own neutral baseline
(unconditional LONG on every ATR-eligible bar) -- only the EXIT varies across
designs. X1/X3/X4 reuse resolver.resolve unchanged with different geometry
(wider target / unreachable target+short clock / unreachable-second-target
runner). X2 (ATR trail) and X5 (EMA20 cross) have no resolver mechanic to
reuse, so they get their own bar-walk here, per the restriction: resolver.py,
geometry.py and rules.py are never touched. Never writes instrument.db.
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument import ta                                                     # noqa: E402
from instrument.geometry import LONG, SHORT, InvalidGeometry, assert_geometry  # noqa: E402
from instrument.resolver import resolve                                       # noqa: E402
from instrument.rules import SL_ATR_MULT                                      # noqa: E402
from instrument.scripts.test_hypotheses import (                              # noqa: E402
    SEGMENTS, SYMBOLS, Trade, load_candles, segment_of, stats_of)

UNREACHABLE_R = 1000.0
TRAIL_MULT = 3.0
EMA_PERIOD = 20
BULL_TH, BEAR_TH = 0.15, -0.15
# (name, tp1_r_mult, tp2_r_mult, max_bars) -- the 3 designs resolver.resolve can run
RESOLVER_DESIGNS = (
    ("X1 fixed-wide", 1.5, 3.0, 72),
    ("X3 timebox", UNREACHABLE_R, UNREACHABLE_R, 24),
    ("X4 uncapped-runner", 0.7, UNREACHABLE_R, 240),
)
CUSTOM_DESIGNS = ("X2 trail", "X5 signal-flip")
ALL_DESIGNS = [n for n, *_ in RESOLVER_DESIGNS] + list(CUSTOM_DESIGNS)


def _via_resolver(side, entry, atr_val, candles, i, tp1_mult, tp2_mult, max_bars):
    r = SL_ATR_MULT * atr_val
    try:
        if side == LONG:
            geo = assert_geometry(LONG, entry, entry - r, entry + tp1_mult * r,
                                  entry + tp2_mult * r)
        else:
            geo = assert_geometry(SHORT, entry, entry + r, entry - tp1_mult * r,
                                  entry - tp2_mult * r)
    except InvalidGeometry:
        return None
    res = resolve(geo, candles[i + 1:], max_bars)
    return None if res.outcome == "VOID" else res.r_realized


def x2_trail(side, entry, atr_val, candles, i, max_bars=240, trail_mult=TRAIL_MULT):
    """Chandelier trail: stop only ratchets in the trade's favour. Pessimistic on
    ambiguity like resolver.py -- a candle's own new extreme is never used to
    justify surviving a stop hit that landed inside that same candle; the stop
    only updates for the FOLLOWING candle."""
    r_unit = SL_ATR_MULT * atr_val
    if r_unit <= 0:
        return None
    stop = entry - r_unit if side == LONG else entry + r_unit
    extreme = entry
    bars = candles[i + 1:i + 1 + max_bars]
    if not bars:
        return None
    for c in bars:
        hit = (c.low <= stop) if side == LONG else (c.high >= stop)
        if hit:
            return (stop - entry) / r_unit if side == LONG else (entry - stop) / r_unit
        if side == LONG:
            extreme = max(extreme, c.high)
            stop = max(stop, extreme - trail_mult * r_unit)
        else:
            extreme = min(extreme, c.low)
            stop = min(stop, extreme + trail_mult * r_unit)
    last = bars[-1]
    return (last.close - entry) / r_unit if side == LONG else (entry - last.close) / r_unit


def x5_signal_flip(side, entry, atr_val, candles, closes, ema20, i, max_bars=240):
    """Exit on the first EMA20 cross against the position; SL is a catastrophic
    floor only, not the primary exit mechanic."""
    r_unit = SL_ATR_MULT * atr_val
    if r_unit <= 0:
        return None
    stop = entry - r_unit if side == LONG else entry + r_unit
    end = min(i + 1 + max_bars, len(candles))
    if end <= i + 1:
        return None
    for k in range(i + 1, end):
        c = candles[k]
        if (c.low <= stop) if side == LONG else (c.high >= stop):
            return (stop - entry) / r_unit if side == LONG else (entry - stop) / r_unit
        pe, ce = ema20[k - 1], ema20[k]
        if pe is None or ce is None:
            continue
        pc, cc = closes[k - 1], closes[k]
        crossed = (pc >= pe and cc < ce) if side == LONG else (pc <= pe and cc > ce)
        if crossed:
            return (cc - entry) / r_unit if side == LONG else (entry - cc) / r_unit
    last = candles[end - 1].close
    return (last - entry) / r_unit if side == LONG else (entry - last) / r_unit


def neutral_entries(candles, atr_arr):
    """The one entry every design shares: unconditional LONG, every ATR-eligible bar."""
    return [(i, c.ts, c.close, atr_arr[i]) for i, c in enumerate(candles) if atr_arr[i]]


def regime_cells(corpora, entries):
    """(symbol, segment) -> (label, buy_hold_pct, buy_hold_R_equiv)."""
    cells = {}
    for s in SYMBOLS:
        cs = corpora[s]
        seg_idx = {name: [] for name, _, _ in SEGMENTS}
        for i, c in enumerate(cs):
            seg = segment_of(c.ts)
            if seg:
                seg_idx[seg].append(i)
        seg_runits = {name: [] for name, _, _ in SEGMENTS}
        for _, ts, price, atr_val in entries[s]:
            seg = segment_of(ts)
            if seg:
                seg_runits[seg].append(SL_ATR_MULT * atr_val / price)
        for name, _, _ in SEGMENTS:
            idxs = seg_idx[name]
            if not idxs:
                continue
            pct = (cs[idxs[-1]].close - cs[idxs[0]].close) / cs[idxs[0]].close
            label = "BULL" if pct >= BULL_TH else ("BEAR" if pct <= BEAR_TH else "SIDEWAYS")
            runits = seg_runits[name]
            requiv = (pct / statistics.mean(runits)) if runits else None
            cells[(s, name)] = (label, pct, requiv)
    return cells


def run_design(dname, corpora, atrs, entries) -> dict:
    """(symbol, segment) -> list[Trade] for one design, over every entry."""
    per_cell: dict = {}
    for s in SYMBOLS:
        cs, atr_arr = corpora[s], atrs[s]
        closes = [c.close for c in cs]
        ema20 = ta.ema(closes, EMA_PERIOD) if dname == "X5 signal-flip" else None
        resolver_cfg = next(((t1, t2, mb) for n, t1, t2, mb in RESOLVER_DESIGNS if n == dname), None)
        for i, ts, price, atr_val in entries[s]:
            if resolver_cfg:
                t1, t2, mb = resolver_cfg
                r = _via_resolver(LONG, price, atr_val, cs, i, t1, t2, mb)
            elif dname == "X2 trail":
                r = x2_trail(LONG, price, atr_val, cs, i)
            else:
                r = x5_signal_flip(LONG, price, atr_val, cs, closes, ema20, i)
            if r is None:
                continue
            seg = segment_of(ts)
            if seg is None:
                continue
            per_cell.setdefault((s, seg), []).append(Trade(ts, r))
    return per_cell


def verdict_for(per_cell, cells) -> None:
    all_trades = [t for trades in per_cell.values() for t in trades]
    pooled = stats_of(all_trades)
    by_regime: dict[str, list[Trade]] = {"BULL": [], "BEAR": [], "SIDEWAYS": []}
    bull_requiv = []
    for (s, seg), trades in per_cell.items():
        label, pct, requiv = cells.get((s, seg), (None, None, None))
        if label:
            by_regime[label] += trades
            if label == "BULL" and requiv is not None:
                bull_requiv.append(requiv)

    print(f"  POOLED  n={pooled['n']}  mean={pooled['mean']:+.3f}R  "
         f"95% CI [{pooled['lo']:+.3f}, {pooled['hi']:+.3f}]")
    regime_stats = {}
    for label in ("BULL", "BEAR", "SIDEWAYS"):
        st = stats_of(by_regime[label])
        regime_stats[label] = st
        flag = " low-n" if st["n"] < 30 else ""
        print(f"    {label:>8}: n={st['n']:>6}  mean={st['mean']:+.3f}R{flag}")

    bull_ceiling = statistics.mean(bull_requiv) if bull_requiv else None
    c1 = pooled["n"] >= 30
    c2 = pooled["n"] > 0 and pooled["mean"] > 0 and pooled["lo"] > 0
    qualifying = [l for l in ("BULL", "BEAR", "SIDEWAYS") if regime_stats[l]["n"] >= 30]
    c3 = bool(qualifying) and all(regime_stats[l]["mean"] > 0 for l in qualifying)
    drift = (bull_ceiling is not None and regime_stats["BULL"]["mean"] >= bull_ceiling
             and regime_stats["BEAR"]["mean"] <= 0 and regime_stats["SIDEWAYS"]["mean"] <= 0)
    verdict = "DRIFT-CAPTURE" if drift else ("EDGE" if all([c1, c2, c3]) else "NO EDGE")
    bc = f"{bull_ceiling:+.3f}R" if bull_ceiling is not None else "n/a"
    print(f"  criteria: evidence_floor={c1} positive_ci={c2} "
         f"regime_consistent={c3}({len(qualifying)}/3 qualifying@n>=30) "
         f"bull_ceiling(buy&hold R-equiv)={bc}")
    print(f"  VERDICT: {verdict}")


def run() -> None:
    corpora = {s: load_candles(s) for s in SYMBOLS}
    atrs = {s: ta.atr([c.high for c in cs], [c.low for c in cs], [c.close for c in cs], 14)
           for s, cs in corpora.items()}
    entries = {s: neutral_entries(corpora[s], atrs[s]) for s in SYMBOLS}
    cells = regime_cells(corpora, entries)

    print("=== BUY-AND-HOLD CEILING (per symbol x segment, long-only, non-overlapping) ===")
    for s in SYMBOLS:
        for name, _, _ in SEGMENTS:
            cell = cells.get((s, name))
            if cell:
                label, pct, requiv = cell
                req_txt = f"{requiv:+.2f}R" if requiv is not None else "n/a"
                print(f"  {s:>4} {name}: {label:>8}  buy_hold={pct:+.1%}  R-equiv={req_txt}")

    for dname in ALL_DESIGNS:
        print(f"\n=== {dname} ===")
        per_cell = run_design(dname, corpora, atrs, entries)
        for s in SYMBOLS:
            for name, _, _ in SEGMENTS:
                trades = per_cell.get((s, name), [])
                st = stats_of(trades)
                label = cells.get((s, name), ("?", 0, None))[0]
                print(f"  {s:>4} {name} [{label:>8}]  n={st['n']:>6}  mean={st['mean']:+.3f}R")
        verdict_for(per_cell, cells)


if __name__ == "__main__":
    run()
