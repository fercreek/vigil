"""
market_intel.py — Phase 2: Market Intelligence Layer

Funding rates, niveles de liquidacion, deteccion de regimen de mercado.
Diseno cache-first con degradacion graceful en todas las funciones.

Funciones principales:
  - get_funding_rates()       → batch fetch de funding rates via ccxt
  - get_funding_signal()      → +1/0/-1 para confluencia contrarian
  - get_liquidation_levels()  → niveles CoinGlass (graceful sin API key)
  - check_sl_near_liquidation() → warning si SL esta cerca de cluster
  - detect_regime()           → TRENDING_UP/DOWN, RANGING, VOLATILE
  - get_funding_html()        → HTML para Telegram /funding
  - get_regime_html()         → HTML para Telegram /regime
  - get_liquidations_html()   → HTML para Telegram /liquidations
"""

import os
import time
import ccxt
import pandas as pd
import numpy as np

from config import (
    FUNDING_EXTREME_LONG, FUNDING_EXTREME_SHORT,
    ADX_TRENDING_THRESHOLD, BB_WIDTH_RANGING_PCT,
    ATR_VOLATILE_PERCENTILE, REGIME_CACHE_TTL,
    FUNDING_CACHE_TTL, COINGLASS_CACHE_TTL,
)

# ── Exchange (publica, sin auth — solo para funding rates) ────────────────────
_binance_futures = ccxt.binance({'timeout': 15000, 'options': {'defaultType': 'future'}})

# ── Cache ─────────────────────────────────────────────────────────────────────
_CACHE = {
    "funding": {"data": {}, "last_update": 0},
    "liquidations": {},   # {symbol: {"data": {...}, "last_update": 0}}
    "regime": {},          # {symbol: {"result": {...}, "last_update": 0}}
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. FUNDING RATES
# ═══════════════════════════════════════════════════════════════════════════════

def get_funding_rates(symbols=None):
    """
    Fetch batch de funding rates de Binance Futures.

    Retorna dict: {"TAO": {"rate": 0.0003, "annualized": 0.11, ...}, ...}
    Cache TTL: FUNDING_CACHE_TTL (5 min).
    """
    now = time.time()
    if now - _CACHE["funding"]["last_update"] < FUNDING_CACHE_TTL:
        cached = _CACHE["funding"]["data"]
        if cached:
            return cached

    if symbols is None:
        symbols = ["ZEC", "TAO", "ETH"]

    try:
        raw = _binance_futures.fetch_funding_rates()
        result = {}
        for sym in symbols:
            key = f"{sym}/USDT:USDT"
            if key in raw:
                rate = raw[key].get("fundingRate", 0.0)
                if rate is None:
                    rate = 0.0
                result[sym] = {
                    "rate": rate,
                    "annualized": round(rate * 3 * 365 * 100, 2),  # 3 pagos/dia, anualizado %
                    "timestamp": raw[key].get("timestamp", 0),
                    "next_funding_time": raw[key].get("fundingDatetime", ""),
                }
        _CACHE["funding"]["data"] = result
        _CACHE["funding"]["last_update"] = now
        return result
    except Exception as e:
        print(f"⚠️ [MarketIntel] Error fetching funding rates: {e}")
        return _CACHE["funding"]["data"]  # Retorna cache anterior


def get_funding_signal(symbol, side, funding_data=None):
    """
    Retorna señal contrarian basada en funding rate.

    +1 = funding confirma la direccion contrarian (a favor del trade)
    -1 = funding contradice (en contra del trade)
     0 = neutral

    Logica contrarian:
    - rate > 0.05% (longs crowded) → SHORT confirmado (+1), LONG penalizado (-1)
    - rate < -0.05% (shorts crowded) → LONG confirmado (+1), SHORT penalizado (-1)
    """
    if funding_data is None:
        funding_data = get_funding_rates([symbol])

    sym_data = funding_data.get(symbol, {})
    rate = sym_data.get("rate", 0.0)

    if rate > FUNDING_EXTREME_LONG:
        # Longs crowded — contrarian SHORT
        return 1 if side == "SHORT" else -1
    elif rate < FUNDING_EXTREME_SHORT:
        # Shorts crowded — contrarian LONG
        return 1 if side == "LONG" else -1
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. LIQUIDATION LEVELS (CoinGlass)
# ═══════════════════════════════════════════════════════════════════════════════

def get_liquidation_levels(symbol):
    """
    Fetch niveles de liquidacion de CoinGlass API.

    Requiere COINGLASS_API_KEY en .env. Sin key → retorna {"available": False}.
    Free tier: 10 calls/min — cache agresivo.
    """
    api_key = os.getenv("COINGLASS_API_KEY", "")
    if not api_key:
        return {"available": False, "reason": "no_api_key"}

    # Check cache
    now = time.time()
    cached = _CACHE["liquidations"].get(symbol, {})
    if cached and now - cached.get("last_update", 0) < COINGLASS_CACHE_TTL:
        return cached.get("data", {"available": False, "reason": "cached_empty"})

    try:
        import requests
        url = f"https://open-api.coinglass.com/public/v2/liquidation/info"
        headers = {"coinglassSecret": api_key, "accept": "application/json"}
        params = {"symbol": symbol}
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") == "0" and data.get("data"):
            liq_data = data["data"]
            result = {
                "available": True,
                "long_liquidations": liq_data.get("longLiquidationInfo", []),
                "short_liquidations": liq_data.get("shortLiquidationInfo", []),
                "timestamp": now,
            }
        else:
            result = {"available": False, "reason": f"api_code_{data.get('code', 'unknown')}"}

        _CACHE["liquidations"][symbol] = {"data": result, "last_update": now}
        return result

    except Exception as e:
        print(f"⚠️ [MarketIntel] Error fetching liquidation levels for {symbol}: {e}")
        if cached and cached.get("data"):
            return cached["data"]
        return {"available": False, "reason": str(e)}


def check_sl_near_liquidation(symbol, sl_price, side):
    """
    Verifica si el SL esta cerca (<1%) de un cluster de liquidacion.

    Retorna: {"warning": bool, "nearest_cluster": float, "distance_pct": float}
    """
    liq = get_liquidation_levels(symbol)
    if not liq.get("available"):
        return {"warning": False, "reason": "data_unavailable"}

    # Para LONG, preocupan las liquidaciones SHORT (debajo)
    # Para SHORT, preocupan las liquidaciones LONG (arriba)
    if side == "LONG":
        levels = liq.get("short_liquidations", [])
    else:
        levels = liq.get("long_liquidations", [])

    if not levels or sl_price <= 0:
        return {"warning": False, "reason": "no_levels"}

    # Buscar cluster mas cercano al SL
    nearest = None
    min_dist = float('inf')

    for level in levels:
        liq_price = float(level.get("price", 0))
        if liq_price <= 0:
            continue
        dist = abs(sl_price - liq_price) / sl_price
        if dist < min_dist:
            min_dist = dist
            nearest = liq_price

    if nearest is None:
        return {"warning": False, "reason": "no_valid_levels"}

    return {
        "warning": min_dist < 0.01,  # <1%
        "nearest_cluster": nearest,
        "distance_pct": round(min_dist * 100, 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. REGIME DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_regime(symbol):
    """
    Detecta el regimen de mercado actual para un simbolo.

    Retorna dict: {"regime": str, "adx": float, "bb_width": float, "atr_percentile": float}

    Regimenes:
    - TRENDING_UP:   ADX > 25 y precio > EMA200
    - TRENDING_DOWN: ADX > 25 y precio < EMA200
    - RANGING:       BB width < 2% (mercado comprimido, bajo edge)
    - VOLATILE:      ATR percentil > 80 (alta volatilidad sin tendencia clara)

    Cache TTL: REGIME_CACHE_TTL (15 min) por simbolo.
    """
    import indicators  # Lazy import para evitar circularidad

    now = time.time()
    cached = _CACHE["regime"].get(symbol, {})
    if cached and now - cached.get("last_update", 0) < REGIME_CACHE_TTL:
        return cached.get("result", _default_regime())

    try:
        df = indicators.get_df(symbol, '1h', limit=300)
        if df is None or df.empty or len(df) < 30:
            return _default_regime()

        # Calcular componentes
        adx = indicators.calculate_adx(df)
        bb_width = indicators.calculate_bb_width(df['close'])
        atr_current = indicators.calculate_atr(df)
        ema_200 = indicators.calculate_ema(df['close'], period=200)
        current_price = float(df['close'].iloc[-1])

        # ATR percentil: calcular ATR rolling y ver donde esta el actual
        atr_series = []
        window = 14
        for i in range(50, len(df)):
            chunk = df.iloc[max(0, i - window):i + 1]
            if len(chunk) >= window:
                atr_val = indicators.calculate_atr(chunk)
                atr_series.append(atr_val)

        if atr_series:
            atr_percentile = float(np.percentile(
                [x for x in atr_series if x > 0] or [0],
                [ATR_VOLATILE_PERCENTILE]
            )[0])
            is_volatile = atr_current > atr_percentile if atr_percentile > 0 else False
        else:
            atr_percentile = 0.0
            is_volatile = False

        # Clasificacion
        if adx > ADX_TRENDING_THRESHOLD:
            regime = "TRENDING_UP" if current_price > ema_200 else "TRENDING_DOWN"
        elif bb_width < BB_WIDTH_RANGING_PCT:
            regime = "RANGING"
        elif is_volatile:
            regime = "VOLATILE"
        else:
            # Default: determinar por posicion relativa a EMA200
            regime = "TRENDING_UP" if current_price > ema_200 else "TRENDING_DOWN"

        result = {
            "regime": regime,
            "adx": round(adx, 1),
            "bb_width": round(bb_width, 4),
            "atr_percentile": round(atr_current, 2),
            "ema_200": round(ema_200, 2),
            "price": round(current_price, 2),
        }

        _CACHE["regime"][symbol] = {"result": result, "last_update": now}
        return result

    except Exception as e:
        print(f"⚠️ [MarketIntel] Error detecting regime for {symbol}: {e}")
        if cached and cached.get("result"):
            return cached["result"]
        return _default_regime()


def _default_regime():
    """Regimen por defecto (safe: no suprime senales)."""
    return {"regime": "TRENDING_UP", "adx": 0.0, "bb_width": 0.0, "atr_percentile": 0.0}


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TELEGRAM HTML GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

_REGIME_EMOJI = {
    "TRENDING_UP": "📈",
    "TRENDING_DOWN": "📉",
    "RANGING": "↔️",
    "VOLATILE": "🌪️",
}


def get_funding_html(symbols=None):
    """HTML formateado de funding rates para Telegram."""
    if symbols is None:
        symbols = ["ZEC", "TAO", "ETH", "BTC", "SOL"]

    rates = get_funding_rates(symbols)

    lines = ["🏦 <b>FUNDING RATES</b>\n"]

    if not rates:
        lines.append("<i>No se pudieron obtener funding rates.</i>")
        return "\n".join(lines)

    for sym in symbols:
        data = rates.get(sym, {})
        rate = data.get("rate", 0.0)
        ann = data.get("annualized", 0.0)

        # Emoji segun nivel
        if rate > FUNDING_EXTREME_LONG:
            emoji = "🔴"  # Longs crowded
            label = "LONGS CROWDED"
        elif rate < FUNDING_EXTREME_SHORT:
            emoji = "🟢"  # Shorts crowded
            label = "SHORTS CROWDED"
        else:
            emoji = "⚪"
            label = "NEUTRAL"

        rate_pct = rate * 100  # Convertir a porcentaje
        lines.append(
            f"{emoji} <b>{sym}</b>: {rate_pct:+.4f}% ({ann:+.1f}% anual) — {label}"
        )

    lines.append("")
    lines.append("<i>💡 Funding > 0.05% = longs pagan (contrarian SHORT)</i>")
    lines.append("<i>💡 Funding < -0.05% = shorts pagan (contrarian LONG)</i>")

    return "\n".join(lines)


def get_regime_html(symbols=None):
    """HTML formateado del regimen de mercado para Telegram."""
    if symbols is None:
        symbols = ["ZEC", "TAO", "ETH"]

    lines = ["🌍 <b>MARKET REGIME DETECTOR</b>\n"]

    for sym in symbols:
        try:
            info = detect_regime(sym)
            regime = info.get("regime", "UNKNOWN")
            adx = info.get("adx", 0.0)
            bb_w = info.get("bb_width", 0.0)
            emoji = _REGIME_EMOJI.get(regime, "❓")

            lines.append(
                f"{emoji} <b>{sym}</b>: {regime}\n"
                f"   ADX: {adx:.1f} | BB Width: {bb_w:.3f} | "
                f"Price: ${info.get('price', 0):.2f}"
            )
        except Exception as e:
            lines.append(f"❓ <b>{sym}</b>: Error ({e})")

    lines.append("")
    lines.append(
        "<i>📈 TRENDING: ADX > 25 | ↔️ RANGING: BB < 2% | 🌪️ VOLATILE: ATR alto</i>"
    )

    return "\n".join(lines)


def get_liquidations_html(symbol="TAO"):
    """HTML formateado de niveles de liquidacion para Telegram."""
    liq = get_liquidation_levels(symbol)

    lines = [f"💥 <b>LIQUIDATION LEVELS — {symbol}</b>\n"]

    if not liq.get("available"):
        reason = liq.get("reason", "unknown")
        if reason == "no_api_key":
            lines.append(
                "<i>⚠️ COINGLASS_API_KEY no configurada en .env</i>\n"
                "<i>Agrega la key para activar esta feature.</i>"
            )
        else:
            lines.append(f"<i>⚠️ Data no disponible: {reason}</i>")
        return "\n".join(lines)

    long_liqs = liq.get("long_liquidations", [])[:5]  # Top 5
    short_liqs = liq.get("short_liquidations", [])[:5]

    if long_liqs:
        lines.append("🔴 <b>Long Liquidations (arriba):</b>")
        for lvl in long_liqs:
            price = lvl.get("price", 0)
            vol = lvl.get("vol", 0)
            lines.append(f"  • ${float(price):,.2f} — Vol: {vol}")

    if short_liqs:
        lines.append("\n🟢 <b>Short Liquidations (abajo):</b>")
        for lvl in short_liqs:
            price = lvl.get("price", 0)
            vol = lvl.get("vol", 0)
            lines.append(f"  • ${float(price):,.2f} — Vol: {vol}")

    if not long_liqs and not short_liqs:
        lines.append("<i>Sin niveles de liquidacion significativos.</i>")

    return "\n".join(lines)
