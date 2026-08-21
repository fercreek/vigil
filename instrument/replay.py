"""Replay `rules.evaluate` + `resolver.resolve` over one symbol's corpus.

This calls the exact same functions the live path would call -- that sharing is
the point. A backtest that runs its own copy of the logic is how the legacy repo
ended up with strategies that were tuned offline and never operated, and trades
that operated live with no backtest behind them at all (_MAP-instrument.md).

Universe is ZEC-only by decision; --symbol stays generic so the other four
corpora (TAO/BTC/ETH/SOL) can be used for exploratory comparison, not because
the policy is enforced here.
"""
from __future__ import annotations

import argparse
import csv
import statistics
from datetime import datetime
from pathlib import Path

from . import rules
from .geometry import assert_geometry
from .resolver import RESOLVER_VERSION, Candle, resolve
from .store import connect, insert_resolution, insert_signal

CORPUS_DIR = Path(__file__).resolve().parents[1] / "corpus"
TIMEFRAME = "1h"
DECISIONS = ("SENT", "SUPPRESSED", "BLOCKED", "ERROR")


def load_candles(symbol: str) -> list[Candle]:
    path = CORPUS_DIR / f"{symbol}_1h.csv"
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [Candle(ts=r["ts"], open=float(r["open"]), high=float(r["high"]),
                   low=float(r["low"]), close=float(r["close"])) for r in rows]


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def run(symbol: str, db_path: str, max_bars: int) -> dict:
    """Evaluate every bar, resolve every SENT signal, write both to `db_path`."""
    candles = load_candles(symbol)
    counts = {d: 0 for d in DECISIONS}
    skipped = 0
    r_realized: list[float] = []
    mfe: list[float] = []
    mae: list[float] = []
    n_void = 0

    with connect(db_path) as conn:
        for index in range(len(candles)):
            result = rules.evaluate(symbol, TIMEFRAME, candles, index)
            if result is None:
                skipped += 1
                continue

            signal_id = insert_signal(conn, **result)
            counts[result["decision"]] += 1
            if result["decision"] != "SENT":
                continue

            geometry = assert_geometry(result["side"], result["entry_price"],
                                       result["sl_price"], result["tp1_price"],
                                       result["tp2_price"])
            resolution = resolve(geometry, candles[index + 1:], max_bars)
            resolved_at = resolution.exit_bar_ts or candles[index].ts
            insert_resolution(conn, signal_id=signal_id, resolver_version=RESOLVER_VERSION,
                              resolved_at=resolved_at, **resolution.as_row())

            if resolution.outcome == "VOID":
                n_void += 1  # ran out of candles at the tail of the corpus
                continue
            r_realized.append(resolution.r_realized)
            mfe.append(resolution.mfe_r)
            mae.append(resolution.mae_r)
        conn.commit()

    evaluated = len(candles) - skipped
    span_days = (datetime.fromisoformat(candles[-1].ts) - datetime.fromisoformat(candles[0].ts)).days
    weeks = max(span_days / 7.0, 1e-9)
    n_resolved = len(r_realized)
    wins = sum(1 for r in r_realized if r > 0)

    return dict(
        evaluated=evaluated, skipped=skipped, counts=counts, weeks=weeks,
        alerts_per_week=counts["SENT"] / weeks, n_resolved=n_resolved, n_void=n_void,
        wins=wins, expectancy_r=(sum(r_realized) / n_resolved if n_resolved else 0.0),
        win_rate=(wins / n_resolved if n_resolved else 0.0),
        mfe_median=_median(mfe), mae_median=_median(mae),
    )


def report(symbol: str, stats: dict) -> None:
    print(f"\n=== replay: {symbol} {TIMEFRAME} ===")
    print(f"evaluated: {stats['evaluated']} bars had full indicator history "
         f"(skipped for warmup: {stats['skipped']})")
    c = stats["counts"]
    print(f"decisions over {stats['evaluated']} evaluations -- "
         f"SENT: {c['SENT']}  SUPPRESSED: {c['SUPPRESSED']}  "
         f"BLOCKED: {c['BLOCKED']}  ERROR: {c['ERROR']}")
    print(f"alerts/week: {stats['alerts_per_week']:.2f}  "
         f"(n_sent={c['SENT']} over {stats['weeks']:.1f} weeks)")
    print(f"resolved: {stats['n_resolved']} of {c['SENT']} SENT signals "
         f"({stats['n_void']} VOID, ran out of candles -- excluded below)")
    if stats["n_resolved"]:
        print(f"expectancy: {stats['expectancy_r']:.3f}R  (n={stats['n_resolved']})")
        print(f"win rate: {stats['win_rate']:.1%}  "
             f"(n={stats['n_resolved']}, wins={stats['wins']})")
        print(f"MFE median: {stats['mfe_median']:.3f}R  MAE median: {stats['mae_median']:.3f}R  "
             f"(n={stats['n_resolved']})")
    else:
        print("no resolved signals -- nothing to report on expectancy/WR/MFE/MAE")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--max-bars", type=int, default=72)
    args = parser.parse_args()

    stats = run(args.symbol, args.db, args.max_bars)
    report(args.symbol, stats)


if __name__ == "__main__":
    main()
