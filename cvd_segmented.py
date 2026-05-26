"""cvd_segmented.py — Cumulative Volume Delta segmentado por tamaño de orden.

Spec 012 (2026-05-26 — NotebookLM 4 Prompt 1 #2 + Prompt 3 #4): clasifica trades
de Binance Spot por tamaño de orden y calcula CVD (buys - sells) por bucket.

NotebookLM identificó CVD segmentado como TOP 2 estrategia faltante (después de
Funding Rate). El edge real institucional NO está en SMC dibujado, sino en
ver si las ballenas (>$100k orders) acumulan mientras retail (<$1k) vende.

Patrón de divergencia accionable:
  - retail compra + ballenas venden  → top inminente (BEARISH)
  - retail vende + ballenas compran  → bottom inminente (BULLISH)

Buckets (size en USD):
  - retail:  < 1,000          → línea amarilla
  - mid:     1,000 — 100,000  → línea naranja
  - whale:   >= 100,000       → línea marrón

Uso típico:
    from cvd_segmented import compute_cvd_segmented
    cvd = compute_cvd_segmented("BTC/USDT", lookback_trades=1000)
    if cvd.get("divergence_signal") == "BEARISH":
        # smart money vendiendo, retail comprando → posible top
        ...
"""

from __future__ import annotations

import time
from typing import Optional

try:
    from logger_core import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# ── Constantes (no van a config.py para mantener cohesión) ─────────────────
RETAIL_MAX_USD = 1_000.0
WHALE_MIN_USD = 100_000.0
CVD_DIVERGENCE_MIN_USD = 50_000.0   # Magnitud mínima para considerar divergencia accionable
CVD_CACHE_TTL = 60                  # 1 min — trades volátiles, cache corto
CVD_DEFAULT_LOOKBACK = 1000         # max trades Binance fetch_trades en una call

# Cache en memoria
_CACHE: dict = {}


def _cache_get(key: str) -> Optional[dict]:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    if time.time() - entry["ts"] > CVD_CACHE_TTL:
        del _CACHE[key]
        return None
    return entry["data"]


def _cache_set(key: str, data: dict):
    _CACHE[key] = {"ts": time.time(), "data": data}
    if len(_CACHE) > 20:
        oldest = sorted(_CACHE.items(), key=lambda x: x[1]["ts"])[:5]
        for k, _ in oldest:
            del _CACHE[k]


def _classify_bucket(cost_usd: float) -> str:
    """Retorna 'retail' | 'mid' | 'whale' según costo USD del trade."""
    if cost_usd < RETAIL_MAX_USD:
        return "retail"
    if cost_usd < WHALE_MIN_USD:
        return "mid"
    return "whale"


def _classify_divergence(retail_cvd: float, mid_cvd: float, whale_cvd: float) -> str:
    """Clasifica el signal de divergencia basado en CVDs por bucket.

    Reglas:
      BEARISH:  whale_cvd < -threshold AND retail_cvd > +threshold
      BULLISH:  whale_cvd > +threshold AND retail_cvd < -threshold
      NEUTRAL:  cualquier otro
    """
    threshold = CVD_DIVERGENCE_MIN_USD
    if whale_cvd < -threshold and retail_cvd > threshold:
        return "BEARISH"
    if whale_cvd > threshold and retail_cvd < -threshold:
        return "BULLISH"
    return "NEUTRAL"


def compute_cvd_segmented(symbol: str, lookback_trades: int = CVD_DEFAULT_LOOKBACK) -> dict:
    """
    Calcula CVD segmentado por tamaño de orden para un símbolo de Binance Spot.

    Args:
        symbol: Par Binance spot (ej "BTC/USDT").
        lookback_trades: Número de trades recientes a procesar (max ~1000 por API).

    Returns dict:
        {
            "symbol": str,
            "trades_processed": int,
            "total_volume_usd": float,
            "retail_cvd_usd": float,      # buy_vol - sell_vol bucket retail
            "mid_cvd_usd": float,
            "whale_cvd_usd": float,
            "retail_trade_count": int,
            "whale_trade_count": int,
            "divergence_signal": "BEARISH" | "BULLISH" | "NEUTRAL",
            "last_update_ts": int,        # unix timestamp ms del trade más reciente
        }

    Empty dict on failure (sin ccxt, fetch failure, datos insuficientes).
    """
    # Cache check
    cache_key = f"{symbol}:{lookback_trades}"
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.info(f"[CVD] cache hit {symbol}")
        return cached

    try:
        from exchange_singleton import binance_spot
    except ImportError:
        logger.warning("[CVD] exchange_singleton.binance_spot no disponible")
        return {}

    try:
        trades = binance_spot.fetch_trades(symbol, limit=min(lookback_trades, 1000))
    except Exception as e:
        logger.warning(f"[CVD] fetch_trades({symbol}) error: {e}")
        return {}

    if not trades or len(trades) < 10:
        logger.warning(f"[CVD] insuficientes trades para {symbol}: {len(trades) if trades else 0}")
        return {}

    # Acumuladores por bucket
    bucket_cvd = {"retail": 0.0, "mid": 0.0, "whale": 0.0}
    bucket_count = {"retail": 0, "mid": 0, "whale": 0}
    total_volume = 0.0
    last_ts = 0

    for t in trades:
        amount = float(t.get("amount") or 0.0)
        price = float(t.get("price") or 0.0)
        side = (t.get("side") or "").lower()
        cost = amount * price

        if cost <= 0 or side not in ("buy", "sell"):
            continue

        bucket = _classify_bucket(cost)
        # CVD: buy positivo, sell negativo
        delta = cost if side == "buy" else -cost
        bucket_cvd[bucket] += delta
        bucket_count[bucket] += 1
        total_volume += cost

        ts = int(t.get("timestamp") or 0)
        if ts > last_ts:
            last_ts = ts

    signal = _classify_divergence(
        bucket_cvd["retail"], bucket_cvd["mid"], bucket_cvd["whale"]
    )

    result = {
        "symbol": symbol,
        "trades_processed": sum(bucket_count.values()),
        "total_volume_usd": round(total_volume, 2),
        "retail_cvd_usd": round(bucket_cvd["retail"], 2),
        "mid_cvd_usd": round(bucket_cvd["mid"], 2),
        "whale_cvd_usd": round(bucket_cvd["whale"], 2),
        "retail_trade_count": bucket_count["retail"],
        "mid_trade_count": bucket_count["mid"],
        "whale_trade_count": bucket_count["whale"],
        "divergence_signal": signal,
        "last_update_ts": last_ts,
    }
    _cache_set(cache_key, result)
    logger.info(
        f"[CVD] {symbol} processed={result['trades_processed']} "
        f"vol=${result['total_volume_usd']:,.0f} "
        f"whale_cvd=${result['whale_cvd_usd']:+,.0f} "
        f"retail_cvd=${result['retail_cvd_usd']:+,.0f} "
        f"signal={signal}"
    )
    return result


def format_cvd_summary(cvd: dict) -> str:
    """Formato compacto para inyectar en Cuadrilla Zenith voz Genesis o Salmos.

    Output ejemplo:
        "CVD 1k trades · WHALE +$45k · RETAIL -$12k · signal=BULLISH"
    """
    if not cvd:
        return "CVD: sin datos"
    return (
        f"CVD {cvd['trades_processed']} trades · "
        f"WHALE ${cvd['whale_cvd_usd']:+,.0f} · "
        f"RETAIL ${cvd['retail_cvd_usd']:+,.0f} · "
        f"signal={cvd['divergence_signal']}"
    )
