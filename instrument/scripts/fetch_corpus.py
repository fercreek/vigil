"""Download the candles the legacy period was never measured against.

The repo's existing CSVs (data/*_1h_365d.csv) end 2026-03-29 and live trading began
2026-03-30: the tuning corpus and the traded period do not share a single candle.
That alone invalidates every backtest-vs-live comparison the repo ever made.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

import ccxt

OUT = Path(__file__).resolve().parents[2] / "corpus"


def fetch(symbol: str, start: dt.datetime, end: dt.datetime, timeframe: str = "1h",
          exchanges: tuple[str, ...] = ("okx", "kucoin", "binance")) -> list[list]:
    since = int(start.timestamp() * 1000)
    stop = int(end.timestamp() * 1000)
    last_error: Exception | None = None
    for name in exchanges:
        try:
            ex = getattr(ccxt, name)({"enableRateLimit": True, "timeout": 20000})
            rows, cursor = [], since
            while cursor < stop:
                batch = ex.fetch_ohlcv(symbol, timeframe, since=cursor, limit=300)
                if not batch:
                    break
                rows.extend(r for r in batch if r[0] < stop)
                if batch[-1][0] <= cursor:
                    break
                cursor = batch[-1][0] + 1
            if rows:
                print(f"  {symbol:12} {name:8} {len(rows):5} velas")
                return rows
        except Exception as exc:                      # noqa: BLE001 - reported, not swallowed
            last_error = exc
            print(f"  {symbol:12} {name:8} falla: {type(exc).__name__}")
    raise RuntimeError(f"no exchange served {symbol}: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="ZEC,TAO,BTC,ETH,SOL")
    parser.add_argument("--start", default="2026-03-29")
    parser.add_argument("--end", default="2026-05-12")
    args = parser.parse_args()

    OUT.mkdir(exist_ok=True)
    start = dt.datetime.fromisoformat(args.start)
    end = dt.datetime.fromisoformat(args.end)
    print(f"corpus {start.date()} -> {end.date()}")

    for base in args.symbols.split(","):
        target = OUT / f"{base}_1h.csv"
        if target.exists():
            print(f"  {base:12} ya existe, salto")
            continue
        try:
            rows = fetch(f"{base}/USDT", start, end)
        except RuntimeError as exc:
            print(f"  {base:12} SIN DATOS: {exc}")
            continue
        with target.open("w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["ts", "open", "high", "low", "close", "volume"])
            for ms, o, h, l, c, v in rows:
                writer.writerow([dt.datetime.utcfromtimestamp(ms / 1000).isoformat(),
                                 o, h, l, c, v])
    return 0


if __name__ == "__main__":
    sys.exit(main())
