"""OHLCV feed. Cripto por la cadena de exchanges, acciones por yfinance.

El despacho es por simbolo (`equities.is_equity`) y no por argumento, para que
todo lo de arriba -- scan_once, resolve_pending -- siga llamando `fetch_ohlcv`
sin saber en que mercado esta. Un solo contrato: velas CERRADAS, la ultima
descartada, y FeedUnavailable si no se pudo preguntar.

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

from instrument import equities
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


# yfinance no acepta "cuantas velas quiero", acepta un periodo. Se pide de mas y
# se recorta: en acciones una vela horaria solo avanza mientras la bolsa abre, asi
# que 300 velas son ~46 sesiones, no 12 dias.
_YF_PERIOD_FOR = {"1h": "60d", "1d": "2y", "1wk": "5y"}


def _fetch_equity(symbol: str, timeframe: str, limit: int) -> list[Candle]:
    """Velas de una accion. Descarta la ultima fila igual que la rama de cripto.

    Ese descarte es incondicional a proposito, misma disciplina que arriba: la
    fila mas reciente de yfinance es la vela en formacion cuando el mercado esta
    abierto, y distinguirla mirando el reloj es introducir una decision de
    calendario en el unico modulo que no deberia tener ninguna. Fuera de horario
    el costo es retrasar una vela; el look-ahead no tiene ese precio.
    """
    try:
        import yfinance as yf
    except ImportError as exc:                      # pragma: no cover
        raise FeedUnavailable(f"{symbol}: yfinance no instalado ({exc})") from exc
    period = _YF_PERIOD_FOR.get(timeframe, "60d")
    try:
        df = yf.download(symbol, period=period, interval=timeframe,
                         progress=False, auto_adjust=False, threads=False)
    except Exception as exc:                        # yfinance lanza de todo
        raise FeedUnavailable(f"{symbol} {timeframe}: yfinance fallo: {exc}") from exc
    if df is None or len(df) < 2:
        raise FeedUnavailable(f"{symbol} {timeframe}: yfinance devolvio {0 if df is None else len(df)} filas")
    if hasattr(df.columns, "levels"):               # yfinance devuelve MultiIndex a veces
        df.columns = df.columns.get_level_values(0)
    rows = [
        Candle(ts=ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ") if ts.tzinfo
               else ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
               open=float(o), high=float(h), low=float(l), close=float(c))
        for ts, o, h, l, c in zip(df.index, df["Open"], df["High"], df["Low"], df["Close"])
        if not (o != o or h != h or l != l or c != c)   # NaN: la bolsa estaba cerrada
    ]
    return rows[:-1][-limit:]


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
    if equities.is_equity(symbol):
        return _fetch_equity(symbol, timeframe, limit)

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
