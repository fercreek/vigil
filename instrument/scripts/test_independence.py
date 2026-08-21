"""Re-run the exit designs with NON-OVERLAPPING entries, and watch the edge vanish.

test_exits.py reported that a chandelier trail earned +0.110R and held up in bull,
bear and sideways alike -- the first positive result this repo has produced. Its own
author flagged the reason to doubt it: entries were taken every hour and held for up
to 240 bars, so neighbouring "trades" are the same price movement counted dozens of
times over. That inflates n, and it manufactures the cross-regime consistency too,
because adjacent segments are literally the same trade again.

This spaces entries by the full holding period so no two overlap. The effect does not
survive. At n=432 independent trades there is ample power to see +0.110R if it were
there; measured is -0.005R with an interval straddling zero, and the per-cell numbers
swing from +1.13R to -0.59R, which is what noise looks like.

Kept as a script because a number nobody can re-derive is not evidence.
"""
from __future__ import annotations

import csv
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument.ta import atr as compute_atr  # noqa: E402

SYMBOLS = ["ZEC", "TAO", "BTC", "ETH", "SOL", "BNB"]
CORPUS = Path(__file__).resolve().parents[2] / "corpus"
STOP_ATR_MULT = 1.5
TRAIL_ATR_MULT = 3.0
TRAIL_HOLD = 240
TIMEBOX_HOLD = 24
REGIME_BAND = 0.15


def _load(symbol: str) -> tuple[list[float], list[float], list[float]]:
    rows = list(csv.DictReader((CORPUS / f"{symbol}_1h.csv").open()))
    return ([float(r["high"]) for r in rows], [float(r["low"]) for r in rows],
            [float(r["close"]) for r in rows])


def _run_trade(highs, lows, closes, atrs, index, trailing: bool, hold: int) -> float | None:
    entry = closes[index]
    risk = STOP_ATR_MULT * (atrs[index] or 0.0)
    if not risk:
        return None
    stop, peak = entry - risk, highs[index]
    for j in range(index + 1, min(index + hold + 1, len(closes))):
        if lows[j] <= stop:
            return (stop - entry) / risk
        if trailing:
            peak = max(peak, highs[j])
            if atrs[j]:
                stop = max(stop, peak - TRAIL_ATR_MULT * atrs[j])
    return (closes[min(index + hold, len(closes) - 1)] - entry) / risk


def main() -> int:
    pooled: dict[str, list[float]] = {"trail": [], "timebox": []}
    print(f"{'symbol':8} {'regime':8} {'n':>4} {'trail':>8} {'timebox':>8}")
    for symbol in SYMBOLS:
        highs, lows, closes = _load(symbol)
        atrs = compute_atr(highs, lows, closes, 14)
        segment = len(closes) // 4
        for k in range(4):
            lo, hi = k * segment, (k + 1) * segment
            change = (closes[hi - 1] - closes[lo]) / closes[lo]
            regime = ("BULL" if change > REGIME_BAND
                      else "BEAR" if change < -REGIME_BAND else "FLAT")
            trail, timebox = [], []
            # step == holding period: consecutive trades cannot overlap
            for i in range(lo + 50, hi - TRAIL_HOLD - 10, TRAIL_HOLD):
                if atrs[i] is None:
                    continue
                a = _run_trade(highs, lows, closes, atrs, i, True, TRAIL_HOLD)
                b = _run_trade(highs, lows, closes, atrs, i, False, TIMEBOX_HOLD)
                if a is not None:
                    trail.append(a)
                if b is not None:
                    timebox.append(b)
            if len(trail) < 3:
                continue
            pooled["trail"] += trail
            pooled["timebox"] += timebox
            print(f"{symbol:8} {regime:8} {len(trail):4} "
                  f"{st.mean(trail):+8.3f} {st.mean(timebox):+8.3f}")

    print()
    for name, values in pooled.items():
        mean = st.mean(values)
        stderr = st.stdev(values) / len(values) ** 0.5
        print(f"  {name:8} n={len(values):4}  {mean:+.3f}R  "
              f"95% CI [{mean - 1.96 * stderr:+.3f}, {mean + 1.96 * stderr:+.3f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
