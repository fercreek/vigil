"""Full backtest of the two LIVE strategies (rules.py, breakout.py) against the
6-symbol corpus, replaying main.py's own mechanics instead of a simplified stand-in.

The question is not "how many alerts" -- it is whether the indicators mark good
moments, which only resolving every alert against what price did next can answer.
Two things this script insists on because skipping them changes the answer:

  1. WINDOW=300: evaluate() gets a rolling 300-candle slice (candles[k-299:k+1]),
     exactly main.py's fetch_ohlcv(limit=300) -- not the whole growing prefix,
     which warms EMA200 over history production never has and turns each O(n)
     evaluate() into O(n^2) over the corpus. The 300-window keeps it O(WINDOW),
     so no sampling is needed -- a full 6-symbol run finishes in minutes (measured).
  2. COOLDOWN: mirrors `_in_cooldown` -- one alert per symbol+side+ruleset while
     the previous one is still inside its 72-bar (=72h, 1h TF, no corpus gaps)
     window. Skipping this reproduces the defect that motivated the rule: ETH
     fired 5x on one ramp and a real +0.110R edge measured -0.005R once entries
     were spaced (see rules.py's docstring for the citation).

Not modeled: the FOMC suppression gate (main.py's `_fomc_suppressions`) -- it needs a
live knowledge-cache entry this corpus has no historical record of, so alerts here
run with suppressions=None; real +/-24h-FOMC alerts would have been SUPPRESSED live.

Baseline (per strategy): unconditional LONG wherever that strategy's geometry is
computable, no gate, no cooldown -- the convention fixed in test_hypotheses.py /
HYPOTHESES.md ("not a tradeable strategy, a drift detector"). Its ATR/Donchian run
once over each symbol's FULL series, not the rolling window -- Wilder recursion
converges fast enough for the gap to be negligible; a documented approximation,
not a claim of bar-for-bar live equivalence.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument import breakout, rules, ta                              # noqa: E402
from instrument.geometry import LONG, InvalidGeometry, assert_geometry  # noqa: E402
from instrument.resolver import Candle, Resolution, resolve             # noqa: E402

CORPUS_DIR = Path(__file__).resolve().parents[2] / "corpus"
SYMBOLS = ("ZEC", "TAO", "BTC", "ETH", "SOL", "BNB")
WINDOW = 300                  # main.py: fetch_ohlcv(..., limit=300)
MAX_BARS = 72                 # main.py: MAX_HOLD_BARS
COOLDOWN_HOURS = 72           # main.py: _in_cooldown's window; 1h TF, no corpus gaps -> = bars
STRATEGIES = {"rules": rules, "breakout": breakout}
SEGMENTS = (("S1", "2024-08-01", "2025-02-01"), ("S2", "2025-02-01", "2025-08-01"),
           ("S3", "2025-08-01", "2026-02-01"), ("S4", "2026-02-01", "2026-08-21"))
REGIME_PCT = 0.15  # +/-15% symbol return over the segment -> alcista/bajista else lateral


def load_candles(symbol: str) -> list[Candle]:
    with (CORPUS_DIR / f"{symbol}_1h.csv").open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [Candle(r["ts"], float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]))
           for r in rows]


@dataclass
class Trade:
    symbol: str
    ts: str
    outcome: str
    r: float
    mfe: float
    mae: float


def _segment_and_regime(symbol: str, candles: list[Candle]) -> dict[str, tuple[str, str, float]]:
    """segment name -> (segment, regime label, symbol's own return over the segment)."""
    by_ts = {c.ts: c.close for c in candles}
    starts = sorted(by_ts)
    out = {}
    for name, start, end in SEGMENTS:
        in_seg = [ts for ts in starts if start <= ts[:10] < end]
        if len(in_seg) < 2:
            continue
        ret = by_ts[in_seg[-1]] / by_ts[in_seg[0]] - 1.0
        label = "alcista" if ret > REGIME_PCT else "bajista" if ret < -REGIME_PCT else "lateral"
        out[name] = (name, label, ret)
    return out


def scan_symbol(strategy, symbol: str, candles: list[Candle]) -> list[dict]:
    """Replays main.py's scan loop for one strategy/symbol: rolling 300-window,
    evaluate the newest closed bar, apply the same per-(side) cooldown _in_cooldown
    enforces. Returns the SENT rows that survive cooldown, geometry attached."""
    alerts, last_sent = [], {}
    for k in range(WINDOW - 1, len(candles)):
        window = candles[k - WINDOW + 1: k + 1]
        row = strategy.evaluate(symbol, "1h", window, WINDOW - 1)
        if row is None or row["decision"] != "SENT":
            continue
        ts = datetime.fromisoformat(row["bar_ts"])
        prior = last_sent.get(row["side"])
        if prior is not None and (ts - prior) < timedelta(hours=COOLDOWN_HOURS):
            continue  # cooldown: same episode already alerted
        last_sent[row["side"]] = ts
        alerts.append({**row, "index": k})
    return alerts


def _resolve_geometry(side: str, entry: float, sl: float, tp1: float, tp2: float,
                      candles: list[Candle], index: int) -> Resolution | None:
    try:
        geometry = assert_geometry(side, entry, sl, tp1, tp2)
    except InvalidGeometry:
        return None
    after = candles[index + 1:]
    if len(after) < MAX_BARS:
        return None  # not enough trailing history yet -- mirrors main.py resolve_pending's skip
    return resolve(geometry, after, MAX_BARS)


def resolve_alerts(alerts: list[dict], candles: list[Candle]) -> tuple[list[Trade], int]:
    trades, unresolved = [], 0
    for a in alerts:
        res = _resolve_geometry(a["side"], a["entry_price"], a["sl_price"], a["tp1_price"],
                                a["tp2_price"], candles, a["index"])
        if res is None:
            unresolved += 1
            continue
        trades.append(Trade(a["symbol"], a["bar_ts"], res.outcome, res.r_realized, res.mfe_r, res.mae_r))
    return trades, unresolved


def baseline_trades(name: str, symbol: str, candles: list[Candle]) -> list[Trade]:
    """Unconditional LONG, no gate, no cooldown -- convention from HYPOTHESES.md."""
    highs, lows, closes = [c.high for c in candles], [c.low for c in candles], [c.close for c in candles]
    mod = STRATEGIES[name]
    atr_arr = ta.atr(highs, lows, closes, mod.ATR_PERIOD)
    out = []
    start = mod.DONCHIAN_PERIOD if name == "breakout" else 0
    for i in range(start, len(candles)):
        if atr_arr[i] is None:
            continue
        entry = candles[i].close
        if name == "rules":
            r = mod.SL_ATR_MULT * atr_arr[i]
            sl, tp1, tp2 = entry - r, entry + mod.TP1_R_MULT * r, entry + mod.TP2_R_MULT * r
        else:
            sl = min(c.low for c in candles[i - mod.DONCHIAN_PERIOD:i])
            if sl >= entry:
                continue
            tp1, tp2 = entry + mod.ATR_MULT_TP1 * atr_arr[i], entry + mod.ATR_MULT_TP2 * atr_arr[i]
        res = _resolve_geometry(LONG, entry, sl, tp1, tp2, candles, i)
        if res is not None:
            out.append(Trade(symbol, candles[i].ts, res.outcome, res.r_realized, res.mfe_r, res.mae_r))
    return out


def stats_of(trades: list[Trade]) -> dict:
    n = len(trades)
    if n == 0:
        return dict(n=0, mean=0.0, lo=0.0, hi=0.0, wr=0.0, mfe=0.0, mae=0.0)
    rs = [t.r for t in trades]
    mean = statistics.mean(rs)
    se = (statistics.stdev(rs) if n > 1 else 0.0) / (n ** 0.5)
    return dict(n=n, mean=mean, lo=mean - 1.96 * se, hi=mean + 1.96 * se,
               wr=sum(1 for r in rs if r > 0) / n,
               mfe=statistics.median(t.mfe for t in trades), mae=statistics.median(t.mae for t in trades))


def fmt_stats(st: dict, label: str) -> str:
    wr = f"{st['wr']:.1%} (n={st['n']})" if st["n"] >= 30 else f"n={st['n']} (<30, rate not reported)"
    return (f"  {label:<10} n={st['n']:>5}  expectancy={st['mean']:+.3f}R  "
           f"95%CI=[{st['lo']:+.3f}, {st['hi']:+.3f}]  win_rate={wr}  "
           f"MFE_med={st['mfe']:+.3f}R  MAE_med={st['mae']:+.3f}R")


def run(symbols: tuple[str, ...]) -> None:
    corpora = {s: load_candles(s) for s in symbols}
    first_ts = datetime.fromisoformat(corpora[symbols[0]][0].ts)
    last_ts = datetime.fromisoformat(corpora[symbols[0]][-1].ts)
    weeks = (last_ts - first_ts).days / 7

    for name, mod in STRATEGIES.items():
        print(f"\n{'=' * 78}\nSTRATEGY: {name}  (ruleset_version={mod.RULESET_VERSION})\n{'=' * 78}", flush=True)
        all_alerts, all_trades, unresolved_total = [], [], 0
        for s in symbols:
            alerts = scan_symbol(mod, s, corpora[s])
            for a in alerts:
                a["symbol"] = s
            trades, unresolved = resolve_alerts(alerts, corpora[s])
            all_alerts += alerts
            all_trades += trades
            unresolved_total += unresolved
            print(f"  ...scanned {s} ({len(corpora[s])} candles): {len(alerts)} alerts", flush=True)

        print(f"n alerts (post-cooldown) = {len(all_alerts)}  "
             f"({len(all_alerts) / weeks:.2f}/week implied, {weeks:.1f} weeks in corpus)")
        print(f"resolved = {len(all_trades)}  unresolved (insufficient trailing bars) = {unresolved_total}")

        outcomes: dict[str, int] = defaultdict(int)
        for t in all_trades:
            outcomes[t.outcome] += 1
        print("outcome breakdown: " + ", ".join(f"{k}={v}" for k, v in sorted(outcomes.items())))
        print(fmt_stats(stats_of(all_trades), "POOLED"))

        print("-- by symbol --")
        for s in symbols:
            print(fmt_stats(stats_of([t for t in all_trades if t.symbol == s]), s))

        print("-- by regime (symbol's own return over the calendar segment) --")
        regime_trades: dict[str, list[Trade]] = defaultdict(list)
        seg_returns: list[str] = []
        for s in symbols:
            seg_info = _segment_and_regime(s, corpora[s])
            for seg, (_, label, ret) in seg_info.items():
                seg_returns.append(f"{s}/{seg}: {label} ({ret:+.1%})")
            for t in all_trades:
                if t.symbol != s:
                    continue
                day = t.ts[:10]
                seg = next((nm for nm, st, en in SEGMENTS if st <= day < en), None)
                if seg in seg_info:
                    regime_trades[seg_info[seg][1]].append(t)
        for label in ("alcista", "bajista", "lateral"):
            print(fmt_stats(stats_of(regime_trades.get(label, [])), label))
        print("  segment returns used for the classification above:")
        for line in seg_returns:
            print(f"    {line}")

        print("-- baseline: unconditional LONG, same geometry, no gate, no cooldown --")
        base_trades: list[Trade] = []
        for s in symbols:
            base_trades += baseline_trades(name, s, corpora[s])
        base_stats = stats_of(base_trades)
        print(fmt_stats(base_stats, "BASELINE"))
        strat_mean = stats_of(all_trades)["mean"]
        beats = strat_mean > base_stats["mean"] if all_trades else None
        print(f"  strategy {strat_mean:+.3f}R vs baseline {base_stats['mean']:+.3f}R -> "
             f"{'BEATS baseline' if beats else 'DOES NOT beat baseline' if beats is False else 'n/a (0 alerts)'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    args = parser.parse_args()
    run(tuple(args.symbols.split(",")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
