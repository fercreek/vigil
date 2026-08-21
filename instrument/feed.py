"""OHLCV feed with exchange fallback: OKX -> KuCoin -> Binance.

Ports the fallback chain from scalp_bot/exchange_singleton.py (95 lines,
fetch_ohlcv_with_fallback). OKX leads on purpose, same reason as the original:
Binance returns HTTP 451 (geo-block) from the production host, so leading
with it burns a request every cycle for nothing. Bybit is dropped -- the
original chained OKX -> KuCoin -> Bybit -> Binance, this instrument only
needs the three the spec asked for.

The one contract change from the legacy version: exchange_singleton.py:95
returned [] when every exchange failed. That made a dead feed indistinguishable
from "checked, no signal" -- part of why the legacy bot ran silently broken
for 54 days (see schema.sql's header). This module raises FeedUnavailable
instead. Nothing downstream may treat an empty list as "fetched fine".
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

import ccxt

from instrument.resolver import Candle

# One ccxt instance per exchange, created once and reused -- each instance
# does its own rate limiting. No other state lives at module level: no
# result cache, no cross-call memory.
_okx = ccxt.okx({"timeout": 15000, "enableRateLimit": True})
_kucoin = ccxt.kucoin({"timeout": 15000, "enableRateLimit": True})
_binance = ccxt.binance({"timeout": 15000, "enableRateLimit": True})

# (label, exchange, symbol formatter) -- each exchange spells the pair differently.
_CHAIN: tuple[tuple[str, ccxt.Exchange, Callable[[str], str]], ...] = (
    ("OKX", _okx, lambda sym: f"{sym}/USDT"),
    ("KuCoin", _kucoin, lambda sym: f"{sym}-USDT"),
    ("Binance", _binance, lambda sym: f"{sym}/USDT"),
)


class FeedUnavailable(Exception):
    """All exchanges in the fallback chain failed for this request.

    Never catch this and substitute []: an empty list means "asked, got
    nothing to evaluate"; this means "couldn't ask at all". Collapsing the
    two is the exact defect this module exists to remove.
    """


def _to_candle(row: list) -> Candle:
    ts_ms, o, h, l, c, _volume = row
    ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return Candle(ts=ts, open=float(o), high=float(h), low=float(l), close=float(c))


def fetch_ohlcv(symbol: str, timeframe: str = "1h", limit: int = 300,
                 since_ms: int | None = None) -> list[Candle]:
    """Fetch up to `limit` CLOSED candles, trying OKX, then KuCoin, then Binance.

    Requests limit+1 bars from whichever exchange answers and drops the last
    one unconditionally: an exchange's most recent OHLCV row is the candle
    still in formation, and a live candle sitting at the trigger index is
    look-ahead bias wearing a trenchcoat -- the signal would be evaluated
    against a bar that hadn't finished happening yet.

    Raises FeedUnavailable if all three exchanges fail. Does not raise if an
    exchange answers with fewer rows than requested (early history, thin
    symbol) -- that is a real, honest answer, just a short one.
    """
    errors: list[str] = []
    for name, exchange, format_symbol in _CHAIN:
        try:
            raw = exchange.fetch_ohlcv(
                format_symbol(symbol), timeframe=timeframe,
                since=since_ms, limit=limit + 1,
            )
        except ccxt.BaseError as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
            continue
        if not raw:
            errors.append(f"{name}: returned no rows")
            continue
        return [_to_candle(row) for row in raw[:-1]]

    raise FeedUnavailable(
        f"{symbol} {timeframe}: OKX, KuCoin and Binance all failed -- " + " | ".join(errors)
    )
