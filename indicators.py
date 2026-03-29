import ccxt
import pandas as pd
import requests

# Configuración de exchanges
# Binance para BTC y ETH
binance = ccxt.binance()
# Gate.io para TAO (Bittensor) suele tener más liquidez y disponibilidad
gateio = ccxt.gateio()

def calculate_rsi(prices, period=14):
    """Calcula el RSI (Relative Strength Index) estándar."""
    if len(prices) < period:
        return 50.0  # Retornar neutral si no hay suficientes datos
    
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def get_rsi(symbol, timeframe='1h'):
    """Obtiene el RSI para un símbolo y temporalidad dados."""
    try:
        # Mapeo de símbolos para los exchanges
        exchange = binance
        exchange_symbol = symbol
        
        if "TAO" in symbol:
            exchange = gateio
            exchange_symbol = "TAO/USDT"
        elif "ETH" in symbol:
            exchange_symbol = "ETH/USDT"
        elif "BTC" in symbol:
            exchange_symbol = "BTC/USDT"
            
        ohlcv = exchange.fetch_ohlcv(exchange_symbol, timeframe=timeframe, limit=50)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return calculate_rsi(df['close'])
    except Exception as e:
        print(f"[Error RSI {symbol} {timeframe}] {e}")
        return 50.0

def get_global_metrics():
    """Obtiene la dominancia de USDT y BTC en una sola llamada para proteger el límite de API."""
    try:
        url = "https://api.coingecko.com/api/v3/global"
        r = requests.get(url, timeout=10)
        data = r.json()
        
        # USDT Dominance
        usdt_perc = data['data']['market_cap_percentage'].get('usdt', 7.75)
        usdt_calibrated = round(usdt_perc + 0.33, 2) # Calibración TradingView
        
        # BTC Dominance
        btc_perc = data['data']['market_cap_percentage'].get('btc', 50.0)
        btc_calibrated = round(btc_perc, 2)
        
        return usdt_calibrated, btc_calibrated
    except Exception as e:
        print(f"[Error Global Metrics] {e}")
        return 8.08, 52.0 # Fallbacks

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calcula las Bandas de Bollinger."""
    if len(prices) < period:
        return None
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper_band = sma + (std_dev * std)
    lower_band = sma - (std_dev * std)
    return upper_band.iloc[-1], sma.iloc[-1], lower_band.iloc[-1]

def calculate_ema(prices, period=200):
    """Calcula la Media Móvil Exponencial (EMA)."""
    if len(prices) < period:
        return prices.mean() if not prices.empty else 0.0
    return prices.ewm(span=period, adjust=False).mean().iloc[-1]

def calculate_atr(df, period=14):
    """Calcula el ATR (Average True Range)."""
    if len(df) < period + 1:
        return 0.0
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean().iloc[-1]

def get_indicators(symbol, timeframe='1h'):
    """Obtiene RSI, BB, EMA 200, ATR y Volume SMA para un símbolo."""
    try:
        exchange = binance
        exchange_symbol = symbol
        if "TAO" in symbol:
            exchange = gateio
            exchange_symbol = "TAO/USDT"
        elif "ETH" in symbol:
            exchange_symbol = "ETH/USDT"
        elif "BTC" in symbol:
            exchange_symbol = "BTC/USDT"
            
        ohlcv = exchange.fetch_ohlcv(exchange_symbol, timeframe=timeframe, limit=300)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        rsi = calculate_rsi(df['close'])
        bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(df['close'])
        ema_200 = calculate_ema(df['close'], period=200)
        atr = calculate_atr(df, period=14)
        vol_sma = df['volume'].rolling(20).mean().iloc[-1]
        
        return rsi, bb_upper, bb_mid, bb_lower, ema_200, atr, vol_sma
    except Exception as e:
        print(f"[Error Indicators {symbol}] {e}")
        return 50.0, None, None, None, 0.0, 0.0, 0.0

def get_macro_trend(symbol):
    """
    Evalúa la tendencia macroscópica (Institucional) en temporalidades 1H y 4H con EMA 200.
    Retorna el estado de la tendencia ("BULL", "BEAR", "NEUTRAL").
    """
    try:
        exchange = binance
        exchange_symbol = symbol
        if "TAO" in symbol:
            exchange = gateio
            exchange_symbol = "TAO/USDT"
        elif "ETH" in symbol:
            exchange_symbol = "ETH/USDT"
        elif "BTC" in symbol:
            exchange_symbol = "BTC/USDT"
            
        # Descargar datos 1h
        ohlcv_1h = exchange.fetch_ohlcv(exchange_symbol, timeframe='1h', limit=250)
        df_1h = pd.DataFrame(ohlcv_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        ema_1h = calculate_ema(df_1h['close'], period=200)
        price_1h = df_1h['close'].iloc[-1]
        trend_1h = "UP" if price_1h > ema_1h else "DOWN"

        # Descargar datos 4h
        ohlcv_4h = exchange.fetch_ohlcv(exchange_symbol, timeframe='4h', limit=250)
        df_4h = pd.DataFrame(ohlcv_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        ema_4h = calculate_ema(df_4h['close'], period=200)
        price_4h = df_4h['close'].iloc[-1]
        trend_4h = "UP" if price_4h > ema_4h else "DOWN"

        # Consenso
        consensus = "NEUTRAL"
        if trend_1h == "UP" and trend_4h == "UP":
            consensus = "BULL"
        elif trend_1h == "DOWN" and trend_4h == "DOWN":
            consensus = "BEAR"

        return {
            "1H": trend_1h,
            "4H": trend_4h,
            "consensus": consensus
        }

    except Exception as e:
        print(f"[Error Macro Trend {symbol}] {e}")
        return {"1H": "UNKNOWN", "4H": "UNKNOWN", "consensus": "NEUTRAL"}
