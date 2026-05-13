"""
Shared CCXT exchange instances — one per exchange type, rate-limiting enabled.
All modules must import from here instead of creating their own instances.

Fallback chain for OHLCV: Binance → Bybit → KuCoin
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
    Fetch OHLCV with automatic fallback: Binance → Bybit → KuCoin.
    symbol: base asset e.g. "BTC", "ETH", "ZEC"
    Returns raw OHLCV list (same format as ccxt) or [] on total failure.
    """
    binance_sym = f"{symbol}/USDT"
    bybit_sym   = f"{symbol}/USDT"
    kucoin_sym  = f"{symbol}-USDT"

    # 1. Binance (primary)
    try:
        data = binance_spot.fetch_ohlcv(binance_sym, timeframe=timeframe, limit=limit)
        if data:
            return data
    except Exception as e:
        print(f"⚠️ [Binance] {symbol} {timeframe} failed: {type(e).__name__} — trying Bybit")

    # 2. Bybit (fallback 1)
    try:
        data = bybit_spot.fetch_ohlcv(bybit_sym, timeframe=timeframe, limit=limit)
        if data:
            print(f"✅ [Bybit fallback] {symbol} {timeframe} OK")
            return data
    except Exception as e:
        print(f"⚠️ [Bybit] {symbol} {timeframe} failed: {type(e).__name__} — trying KuCoin")

    # 3. KuCoin (fallback 2)
    try:
        data = kucoin_spot.fetch_ohlcv(kucoin_sym, timeframe=timeframe, limit=limit)
        if data:
            print(f"✅ [KuCoin fallback] {symbol} {timeframe} OK")
            return data
    except Exception as e:
        print(f"❌ [KuCoin] {symbol} {timeframe} failed: {type(e).__name__} — no data")

    return []
