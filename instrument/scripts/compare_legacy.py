"""Old system vs new instrument, judged on the same trades.

"Better" here cannot mean "makes more money": no rule in this package has shown an
edge, and saying otherwise would repeat the exact sin this repo was built to stop.
What is comparable is the MEASUREMENT -- given the same 59 historical trades, does
the system report what actually happened?

The old bot had no exit price at all (trade_monitor computed it, showed it in a
Telegram message, then called update_trade_status(id, status), which persists a
label and datetime.now()). Its P&L was reconstructed from that label
(tracker.py:958-969): FULL_WON assumed 2R, LOST assumed -1R.
"""
from __future__ import annotations

import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument.geometry import InvalidGeometry, assert_geometry   # noqa: E402
from instrument.resolver import Candle, resolve                    # noqa: E402

CORPUS = Path(__file__).resolve().parents[2] / "corpus"
LEGACY = Path.home() / "Documents/ideas/vigil-legacy-backup/trades-20260821.db"
WIN_LABELS = {"WON", "FULL_WON", "PARTIAL_CLOSED"}


def _candles(symbol: str) -> list[Candle]:
    path = CORPUS / f"{symbol}_1h.csv"
    if not path.exists():
        return []
    with path.open() as fh:
        return [Candle(r["ts"], float(r["open"]), float(r["high"]),
                       float(r["low"]), float(r["close"])) for r in csv.DictReader(fh)]


def legacy_assumed_r(status: str) -> float:
    """What the old system's own formula implied, from the label alone."""
    return 2.0 if status == "FULL_WON" else 1.0 if status == "PARTIAL_CLOSED" else -1.0


def main(max_bars: int = 72) -> int:
    src = sqlite3.connect(f"file:{LEGACY}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    cache: dict[str, list[Candle]] = {}
    rows = []
    for r in src.execute("SELECT * FROM trades WHERE is_sim = 0 OR is_sim IS NULL"):
        cache.setdefault(r["symbol"], _candles(r["symbol"]))
        if not cache[r["symbol"]]:
            continue
        side = "LONG" if (r["type"] or "").upper() == "LONG" else "SHORT"
        try:
            geometry = assert_geometry(side, r["entry_price"], r["sl_price"],
                                       r["tp1_price"], r["tp2_price"] or r["tp1_price"])
        except InvalidGeometry:
            continue
        after = [c for c in cache[r["symbol"]] if c.ts > (r["open_time"] or "").replace(" ", "T")[:19]]
        if len(after) < 2:
            continue
        rows.append((r["status"], resolve(geometry, after, max_bars)))

    n = len(rows)
    agree = sum(1 for s, res in rows if (s in WIN_LABELS) == (res.r_realized > 0))
    old_r = sum(legacy_assumed_r(s) for s, _ in rows)
    new_r = sum(res.r_realized for _, res in rows)
    mislabelled = [(s, res) for s, res in rows if s == "LOST" and res.r_realized > 0]

    print(f"trades comparables: {n}  (de 91 cerrados; el resto no es cripto o tiene geometría imposible)\n")
    print(f"{'':32} {'SISTEMA VIEJO':>16} {'INSTRUMENTO':>16}")
    print(f"{'precio de salida':32} {'no existe':>16} {'vela real':>16}")
    print(f"{'origen del P&L':32} {'la etiqueta':>16} {'las velas':>16}")
    print(f"{'R total':32} {old_r:>+16.1f} {new_r:>+16.1f}")
    print(f"{'R por trade':32} {old_r/n:>+16.3f} {new_r/n:>+16.3f}")
    print(f"{'excursión favorable':32} {'no medible':>16} {'sí':>16}")
    print(f"{'salidas ambiguas marcadas':32} {'no':>16} "
          f"{sum(1 for _, res in rows if res.same_bar_ambiguous):>16}")
    print(f"\ncoinciden viejo y nuevo: {agree}/{n} ({agree/n:.0%})")
    print(f"marcados LOST que en realidad NO perdieron: {len(mislabelled)}/{n} "
          f"({len(mislabelled)/n:.0%})")
    print(f"  → el bot le mandó 🔴 SL HIT por trades que cerraron planos o en verde")
    print(f"\ndesglose real de salidas: {dict(Counter(res.outcome for _, res in rows))}")
    print(f"\nlo que el sistema viejo NO podía decir, y ahora sí:")
    print(f"  · a qué precio salió cada trade y en qué vela")
    print(f"  · cuánto llegó a favor antes de cerrar (MFE mediana "
          f"{sorted(res.mfe_r for _, res in rows)[n // 2]:+.2f}R)")
    print(f"  · qué habría pasado con el objetivo en TP1 vs dejándolo correr")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
