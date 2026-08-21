"""Resolve the legacy trades against real candles -- the first honest exit prices
this bot has ever had.

The legacy DB stores entry/sl/tp levels and a status label, no exit price. Every R
figure ever quoted about this bot (including '-54R' and the contradicting '+22.6R'
for ZEC) was an ASSUMED-FILL reconstruction: it took the status and imagined the
trade reached a level. This walks the actual candles instead.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument.geometry import InvalidGeometry, assert_geometry   # noqa: E402
from instrument.resolver import Candle, resolve                    # noqa: E402

CORPUS = Path(__file__).resolve().parents[2] / "corpus"


def load_candles(symbol: str) -> list[Candle]:
    path = CORPUS / f"{symbol}_1h.csv"
    if not path.exists():
        return []
    with path.open() as fh:
        return [Candle(ts=r["ts"], open=float(r["open"]), high=float(r["high"]),
                       low=float(r["low"]), close=float(r["close"]))
                for r in csv.DictReader(fh)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(Path.home() /
                        "Documents/ideas/vigil-legacy-backup/trades-20260821.db"))
    parser.add_argument("--max-bars", type=int, default=36,
                        help="the bot's own documented time-exit was 36h")
    args = parser.parse_args()

    src = sqlite3.connect(f"file:{args.source}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    rows = src.execute("SELECT * FROM trades WHERE is_sim = 0 OR is_sim IS NULL").fetchall()

    candles: dict[str, list[Candle]] = {}
    stats: dict[str, list] = defaultdict(list)
    skipped: dict[str, int] = defaultdict(int)
    resolved = []

    for r in rows:
        symbol = r["symbol"]
        if symbol not in candles:
            candles[symbol] = load_candles(symbol)
        series = candles[symbol]
        if not series:
            skipped["sin corpus (no cripto)"] += 1
            continue
        side = "LONG" if (r["type"] or "").upper() == "LONG" else "SHORT"
        try:
            geometry = assert_geometry(side, r["entry_price"], r["sl_price"],
                                       r["tp1_price"], r["tp2_price"] or r["tp1_price"])
        except InvalidGeometry:
            skipped["geometria imposible"] += 1
            continue

        opened = (r["open_time"] or "").replace(" ", "T")[:19]
        after = [c for c in series if c.ts > opened]
        if len(after) < 2:
            skipped["sin velas posteriores"] += 1
            continue

        res = resolve(geometry, after, max_bars=args.max_bars)
        resolved.append((r["id"], symbol, side, r["status"], res))
        stats[symbol].append(res)

    print(f"filas leidas            : {len(rows)}")
    for reason, n in skipped.items():
        print(f"  saltadas ({reason}): {n}")
    print(f"RESUELTAS CON VELAS REALES: {len(resolved)}\n")

    print(f"{'simbolo':8} {'n':>3} {'R real':>9} {'R si TP1':>9} {'R si corre':>11} "
          f"{'WR':>7} {'MFE med':>8} {'MAE med':>8} {'ambig':>6}")
    total = [0.0, 0.0, 0.0, 0, 0]
    for symbol, results in sorted(stats.items(), key=lambda kv: -len(kv[1])):
        n = len(results)
        r_real = sum(x.r_realized for x in results)
        r_tp1 = sum(x.r_if_tp1_only for x in results)
        r_run = sum(x.r_if_no_partial for x in results)
        wins = sum(1 for x in results if x.r_realized > 0)
        mfe = sorted(x.mfe_r for x in results)[n // 2]
        mae = sorted(x.mae_r for x in results)[n // 2]
        amb = sum(1 for x in results if x.same_bar_ambiguous)
        print(f"{symbol:8} {n:3} {r_real:+9.1f} {r_tp1:+9.1f} {r_run:+11.1f} "
              f"{wins/n:6.1%} {mfe:+8.2f} {mae:+8.2f} {amb:6}")
        total[0] += r_real; total[1] += r_tp1; total[2] += r_run
        total[3] += wins; total[4] += n
    n = total[4]
    print(f"{'TOTAL':8} {n:3} {total[0]:+9.1f} {total[1]:+9.1f} {total[2]:+11.1f} "
          f"{total[3]/n:6.1%}")
    print(f"\nexpectancy real: {total[0]/n:+.3f} R/senal  (n={n})")

    agree = sum(1 for _, _, _, status, res in resolved
                if (status in ("WON", "FULL_WON", "PARTIAL_CLOSED")) == (res.r_realized > 0))
    print(f"la etiqueta vieja coincide con la resolucion real en {agree}/{len(resolved)} "
          f"({agree/len(resolved):.0%})")
    amb_total = sum(1 for _, _, _, _, res in resolved if res.same_bar_ambiguous)
    print(f"velas ambiguas (TP y SL en la misma): {amb_total}/{len(resolved)} "
          f"({amb_total/len(resolved):.0%})  <- si supera 15% hay que bajar a 5m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
