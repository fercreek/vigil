"""
Shared CCXT exchange instances — one per exchange type, rate-limiting enabled.
All modules must import from here instead of creating their own instances.

Fallback chain for OHLCV: OKX → KuCoin → Bybit → Binance
(Binance demoted to last: Railway IP gets HTTP 451 geo-block. OKX/KuCoin
are geo-friendly + keyless for public OHLCV, so they lead the chain.)
Use fetch_ohlcv_with_fallback() instead of calling exchange directly.
"""
import ccxt

# Spot — used by scalp_alert_bot, indicators, swing_bot, manual_positions_monitor
binance_spot = ccxt.binance({
    'timeout': 15000,
    'enableRateLimit': True,
})

# Futures — used by market_intel (funding rates)
binance_futures = ccxt.binance({
    'timeout': 15000,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'},
})

# Fallback exchanges (no auth needed for public OHLCV)
# OKX leads: geo-friendly, fast, keyless — best primary for restricted IPs.
okx_spot = ccxt.okx({
    'timeout': 15000,
    'enableRateLimit': True,
})

bybit_spot = ccxt.bybit({
    'timeout': 15000,
    'enableRateLimit': True,
})

kucoin_spot = ccxt.kucoin({
    'timeout': 15000,
    'enableRateLimit': True,
})

# Symbol map: bot uses "BTC" → each exchange uses its own format
_SYMBOL_MAP = {
    'bybit':  lambda sym: f"{sym}/USDT",   # BTC/USDT — same as Binance
    'kucoin': lambda sym: f"{sym}-USDT",   # BTC-USDT
}

def fetch_ohlcv_with_fallback(symbol: str, timeframe: str = '1h', limit: int = 300) -> list:
    """
    Fetch OHLCV with automatic fallback: OKX → KuCoin → Bybit → Binance.
    symbol: base asset e.g. "BTC", "ETH", "ZEC"
    Returns raw OHLCV list (same format as ccxt) or [] on total failure.

    Binance is last because Railway's IP gets HTTP 451 (geo-block); leading
    with OKX/KuCoin avoids the per-cycle error spam and saves a round-trip.
    """
    slash_sym = f"{symbol}/USDT"   # OKX, Bybit, Binance
    kucoin_sym = f"{symbol}-USDT"  # KuCoin

    # 1. OKX (primary — geo-friendly, keyless)
    try:
        data = okx_spot.fetch_ohlcv(slash_sym, timeframe=timeframe, limit=limit)
        if data:
            return data
    except Exception as e:
        print(f"⚠️ [OKX] {symbol} {timeframe} failed: {type(e).__name__} — trying KuCoin")

    # 2. KuCoin (fallback 1)
    try:
        data = kucoin_spot.fetch_ohlcv(kucoin_sym, timeframe=timeframe, limit=limit)
        if data:
            print(f"✅ [KuCoin fallback] {symbol} {timeframe} OK")
            return data
    except Exception as e:
        print(f"⚠️ [KuCoin] {symbol} {timeframe} failed: {type(e).__name__} — trying Bybit")

    # 3. Bybit (fallback 2)
    try:
        data = bybit_spot.fetch_ohlcv(slash_sym, timeframe=timeframe, limit=limit)
        if data:
            print(f"✅ [Bybit fallback] {symbol} {timeframe} OK")
            return data
    except Exception as e:
        print(f"⚠️ [Bybit] {symbol} {timeframe} failed: {type(e).__name__} — trying Binance")

    # 4. Binance (last resort — usually 451 on Railway IP)
    try:
        data = binance_spot.fetch_ohlcv(slash_sym, timeframe=timeframe, limit=limit)
        if data:
            print(f"✅ [Binance fallback] {symbol} {timeframe} OK")
            return data
    except Exception as e:
        print(f"❌ [Binance] {symbol} {timeframe} failed: {type(e).__name__} — no data")

    return []
