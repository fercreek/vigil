"""
Shared CCXT exchange instances — one per exchange type, rate-limiting enabled.
All modules must import from here instead of creating their own instances.
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
