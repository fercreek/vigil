"""One-shot test of the 5 hypotheses pre-registered in ../HYPOTHESES.md. Reuses
geometry.assert_geometry and resolver.resolve unchanged -- no reimplemented touch/exit
logic, only entry timing/side per hypothesis. Never writes instrument.db, never edits
rules.py/geometry.py. Every hypothesis and the baseline share one geometry (imported
from rules.py) so timing/side is the only thing under test. Run as a module.
"""
from __future__ import annotations

import csv
import statistics
import sys
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument import ta                                                     # noqa: E402
from instrument.geometry import LONG, SHORT, InvalidGeometry, assert_geometry  # noqa: E402
from instrument.resolver import Candle, resolve                               # noqa: E402
from instrument.rules import SL_ATR_MULT, TP1_R_MULT, TP2_R_MULT              # noqa: E402

CORPUS_DIR = Path(__file__).resolve().parents[2] / "corpus"
SYMBOLS = ("ZEC", "TAO", "BTC", "ETH", "SOL", "BNB")
MAX_BARS = 72
ATR_PERIOD = 14
SEGMENTS = (  # fixed calendar walk-forward splits, see HYPOTHESES.md
    ("S1", "2024-08-01", "2025-02-01"), ("S2", "2025-02-01", "2025-08-01"),
    ("S3", "2025-08-01", "2026-02-01"), ("S4", "2026-02-01", "2026-08-21"),
)


def load_candles(symbol: str) -> list[Candle]:
    with (CORPUS_DIR / f"{symbol}_1h.csv").open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [Candle(r["ts"], float(r["open"]), float(r["high"]), float(r["low"]),
                   float(r["close"])) for r in rows]


def segment_of(ts: str) -> str | None:
    d = datetime.fromisoformat(ts).date()
    for name, start, end in SEGMENTS:
        if date.fromisoformat(start) <= d < date.fromisoformat(end):
            return name
    return None


def _geometry(side: str, entry: float, atr_val: float):
    r = SL_ATR_MULT * atr_val
    if side == LONG:
        return assert_geometry(LONG, entry, entry - r, entry + TP1_R_MULT * r,
                               entry + TP2_R_MULT * r)
    return assert_geometry(SHORT, entry, entry + r, entry - TP1_R_MULT * r,
                           entry - TP2_R_MULT * r)


def _resolve_r(side: str, entry: float, atr_val: float | None, candles: list[Candle], i: int) -> float | None:
    if atr_val is None:
        return None
    try:
        geo = _geometry(side, entry, atr_val)
    except InvalidGeometry:
        return None
    res = resolve(geo, candles[i + 1:], MAX_BARS)
    return None if res.outcome == "VOID" else res.r_realized


@dataclass
class Trade:
    ts: str
    r: float


def baseline_trades(candles: list[Candle], atr_arr: list) -> list[Trade]:
    """Unconditional LONG on every ATR-eligible bar -- the drift detector."""
    out = []
    for i, c in enumerate(candles):
        if atr_arr[i] is None:
            continue
        r = _resolve_r(LONG, c.close, atr_arr[i], candles, i)
        if r is not None:
            out.append(Trade(c.ts, r))
    return out


# --- hypothesis trigger generators: yield (index, side) --------------------------
# Mechanism + reasoning for each fixed parameter lives in HYPOTHESES.md, not here.

def h1_sweep(candles, atr_arr):
    n = 24
    for i in range(n, len(candles)):
        prior_hi = max(c.high for c in candles[i - n:i])
        prior_lo = min(c.low for c in candles[i - n:i])
        swept_hi = candles[i].high > prior_hi and candles[i].close < prior_hi
        swept_lo = candles[i].low < prior_lo and candles[i].close > prior_lo
        if swept_hi and not swept_lo:
            yield i, SHORT
        elif swept_lo and not swept_hi:
            yield i, LONG


def h2_session(candles, atr_arr):
    by_date: dict = {}
    for i, c in enumerate(candles):
        ts = datetime.fromisoformat(c.ts)
        by_date.setdefault(ts.date(), {})[ts.hour] = i
    history: deque = deque(maxlen=20)
    for d in sorted(by_date):
        hours = by_date[d]
        if not all(h in hours for h in range(8)):
            continue
        idxs = [hours[h] for h in range(8)]
        rng = max(candles[k].high for k in idxs) - min(candles[k].low for k in idxs)
        if len(history) == 20:
            ref = statistics.median(history)
            trigger_i = hours.get(8)
            if ref > 0 and rng <= 0.6 * ref and trigger_i is not None:
                move = candles[idxs[-1]].close - candles[idxs[0]].open
                if move > 0:
                    yield trigger_i, LONG
                elif move < 0:
                    yield trigger_i, SHORT
        history.append(rng)


def h3_momentum(candles, atr_arr):
    for i in range(4, len(candles)):
        c = [candles[k].close for k in range(i - 4, i + 1)]
        if c[4] > c[3] > c[2] > c[1] > c[0]:
            yield i, LONG
        elif c[4] < c[3] < c[2] < c[1] < c[0]:
            yield i, SHORT


def h4_capitulation(candles, atr_arr):
    for i in range(1, len(candles)):
        prev_close = candles[i - 1].close
        tr = max(candles[i].high - candles[i].low, abs(candles[i].high - prev_close),
                 abs(candles[i].low - prev_close))
        prior_atr = atr_arr[i - 1]
        if prior_atr is None or prior_atr <= 0 or tr < 3.0 * prior_atr:
            continue
        if candles[i].close < candles[i].open:
            yield i, LONG
        elif candles[i].close > candles[i].open:
            yield i, SHORT


def h5_weekend(candles, atr_arr):
    for i in range(48, len(candles)):
        ts = datetime.fromisoformat(candles[i].ts)
        if ts.weekday() != 0 or ts.hour != 0:
            continue
        prior_atr = atr_arr[i - 1]
        if prior_atr is None or prior_atr <= 0:
            continue
        drift_r = (candles[i].close - candles[i - 48].close) / prior_atr
        if drift_r >= 1.0:
            yield i, SHORT
        elif drift_r <= -1.0:
            yield i, LONG


HYPOTHESES = {"H1 sweep": h1_sweep, "H2 session": h2_session, "H3 momentum": h3_momentum,
             "H4 capitulation": h4_capitulation, "H5 weekend": h5_weekend}


def stats_of(trades: list[Trade]) -> dict:
    n = len(trades)
    if n == 0:
        return dict(n=0, mean=0.0, lo=0.0, hi=0.0, wr=0.0)
    rs = [t.r for t in trades]
    mean = statistics.mean(rs)
    se = (statistics.stdev(rs) if n > 1 else 0.0) / (n ** 0.5)
    return dict(n=n, mean=mean, lo=mean - 1.96 * se, hi=mean + 1.96 * se,
               wr=sum(1 for r in rs if r > 0) / n)


def by_segment(trades: list[Trade]) -> dict[str, list[Trade]]:
    out: dict[str, list[Trade]] = {name: [] for name, _, _ in SEGMENTS}
    for t in trades:
        seg = segment_of(t.ts)
        if seg:
            out[seg].append(t)
    return out


def run() -> None:
    corpora = {s: load_candles(s) for s in SYMBOLS}
    atrs = {s: ta.atr([c.high for c in cs], [c.low for c in cs], [c.close for c in cs], ATR_PERIOD)
           for s, cs in corpora.items()}

    print("=== BASELINE (unconditional LONG, same geometry, every ATR-eligible bar) ===")
    baseline_all: list[Trade] = []
    for s in SYMBOLS:
        trades = baseline_trades(corpora[s], atrs[s])
        baseline_all += trades
        st = stats_of(trades)
        print(f"  {s:>4}  n={st['n']:>6}  mean={st['mean']:+.3f}R  wr={st['wr']:.1%}")
    base_pooled = stats_of(baseline_all)
    print(f"  POOLED  n={base_pooled['n']}  mean={base_pooled['mean']:+.3f}R  "
         f"95% CI [{base_pooled['lo']:+.3f}, {base_pooled['hi']:+.3f}]")

    for hname, fn in HYPOTHESES.items():
        print(f"\n=== {hname} ===")
        per_symbol: dict[str, list[Trade]] = {}
        for s in SYMBOLS:
            cs, atr_arr = corpora[s], atrs[s]
            trades = []
            for i, side in fn(cs, atr_arr):
                r = _resolve_r(side, cs[i].close, atr_arr[i], cs, i)
                if r is not None:
                    trades.append(Trade(cs[i].ts, r))
            per_symbol[s] = trades
            st = stats_of(trades)
            print(f"  {s:>4}  n={st['n']:>5}  mean={st['mean']:+.3f}R  wr={st['wr']:.1%}"
                 f"{'  (n<10)' if st['n'] < 10 else ''}")

        pooled_trades = [t for trades in per_symbol.values() for t in trades]
        pooled = stats_of(pooled_trades)
        print(f"  POOLED  n={pooled['n']}  mean={pooled['mean']:+.3f}R  "
             f"95% CI [{pooled['lo']:+.3f}, {pooled['hi']:+.3f}]  "
             f"vs baseline {base_pooled['mean']:+.3f}R")

        seg_all = by_segment(pooled_trades)
        pos_segs = 0
        for name, _, _ in SEGMENTS:
            st = stats_of(seg_all[name])
            if st["n"] and st["mean"] > 0:
                pos_segs += 1
            print(f"    {name}: n={st['n']:>5}  mean={st['mean']:+.3f}R  "
                 f"{'low-n' if st['n'] < 30 else ''}")

        qualifying = [s for s in SYMBOLS if stats_of(per_symbol[s])["n"] >= 10]
        pos_symbols = sum(1 for s in qualifying if stats_of(per_symbol[s])["mean"] > 0)

        c1 = pooled["n"] >= 30
        c2 = pooled["n"] > 0 and pooled["mean"] > 0 and pooled["lo"] > 0
        c3 = pooled["n"] > 0 and pooled["mean"] > base_pooled["mean"]
        c4 = len(qualifying) >= 5 and pos_symbols >= 4
        c5 = pos_segs >= 3
        verdict = "EDGE" if all([c1, c2, c3, c4, c5]) else "NO EDGE"
        print(f"  criteria: evidence_floor={c1} positive_ci={c2} beats_baseline={c3} "
             f"cross_symbol={c4}({pos_symbols}/{len(qualifying)} qualifying@n>=10) "
             f"cross_regime={c5}({pos_segs}/4)")
        print(f"  VERDICT: {verdict}")


if __name__ == "__main__":
    run()
