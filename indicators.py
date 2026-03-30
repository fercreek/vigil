import ccxt
import pandas as pd
import requests

import time

# Binance para BTC, ETH y TAO
binance = ccxt.binance()

# --- CACHE LOCAL PARA INDICADORES ---
INDICATOR_CACHE = {
    "metrics": {"usdt_d": 8.08, "btc_d": 52.0, "last_update": 0}
}
TTL_METRICS = 300 # 5 min

def calculate_rsi(prices, period=14):
    """Calcula el RSI (Relative Strength Index) con suavizado de Wilder (RMA)."""
    if len(prices) < period:
        return 50.0
    
    delta = prices.diff()
    # Wilder's Smoothing (RMA) using EWM
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def get_rsi(symbol, timeframe='1h'):
    """Obtiene el RSI para un símbolo y temporalidad dados."""
    try:
        # Mapeo de símbolos para los exchanges
        exchange = binance
        exchange_symbol = f"{symbol}/USDT"
            
        ohlcv = exchange.fetch_ohlcv(exchange_symbol, timeframe=timeframe, limit=50)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return calculate_rsi(df['close'])
    except Exception:
        # Silencioso: Fallback estándar
        return 50.0

def get_global_metrics():
    """Obtiene la dominancia de USDT y BTC con Caché interna para proteger el límite de API."""
    now = time.time()
    
    # 1. ¿Usar Caché?
    if now - INDICATOR_CACHE["metrics"]["last_update"] < TTL_METRICS:
        return INDICATOR_CACHE["metrics"]["usdt_d"], INDICATOR_CACHE["metrics"]["btc_d"]

    try:
        url = "https://api.coingecko.com/api/v3/global"
        r = requests.get(url, timeout=10)
        data = r.json()
        
        if 'data' not in data or 'market_cap_percentage' not in data['data']:
            # Retornamos caché si la respuesta es inválida
            return INDICATOR_CACHE["metrics"]["usdt_d"], INDICATOR_CACHE["metrics"]["btc_d"]
            
        # USDT Dominance
        usdt_perc = data['data']['market_cap_percentage'].get('usdt', 7.75)
        usdt_calibrated = round(usdt_perc + 0.33, 2) # Calibración TradingView
        
        # BTC Dominance
        btc_perc = data['data']['market_cap_percentage'].get('btc', 50.0)
        btc_calibrated = round(btc_perc, 2)
        
        # Actualizamos caché
        INDICATOR_CACHE["metrics"].update({
            "usdt_d": usdt_calibrated,
            "btc_d": btc_calibrated,
            "last_update": now
        })
        
        return usdt_calibrated, btc_calibrated
    except Exception as e:
        # Silencioso: Retornamos lo último que sabemos
        return INDICATOR_CACHE["metrics"]["usdt_d"], INDICATOR_CACHE["metrics"]["btc_d"]

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calcula las Bandas de Bollinger con precisión ddof=0."""
    if len(prices) < period:
        return None
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std(ddof=0)
    upper_band = sma + (std_dev * std)
    lower_band = sma - (std_dev * std)
    return upper_band.iloc[-1], sma.iloc[-1], lower_band.iloc[-1]

def calculate_ema(prices, period=200):
    """Calcula la Media Móvil Exponencial (EMA)."""
    if len(prices) < period:
        return prices.mean() if not prices.empty else 0.0
    return prices.ewm(span=period, adjust=False).mean().iloc[-1]

def calculate_atr(df, period=14):
    """Calcula el ATR (Average True Range) con suavizado de Wilder."""
    if len(df) < period + 1:
        return 0.0
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    # Wilder's Smoothing (RMA) using EWM
    return true_range.ewm(alpha=1/period, adjust=False).mean().iloc[-1]

def detect_elliot_wave(df):
    """
    Detecta de forma simplificada impulsos de Ondas de Elliott (1-2-3-4-5).
    Retorna el estado detectado ("Wave 3 Impulse", "Wave 4 Correction", etc.)
    """
    try:
        if len(df) < 50:
            return "Indeterminado"

        # 1. Encontrar Pivots (Giros) locales simplificados
        # Usamos una ventana de 5 para detectar picos y valles
        df['min'] = df['close'][(df['close'].shift(1) > df['close']) & (df['close'].shift(-1) > df['close'])]
        df['max'] = df['close'][(df['close'].shift(1) < df['close']) & (df['close'].shift(-1) < df['close'])]
        
        pivots = df[['min', 'max']].dropna(how='all').tail(10)
        if len(pivots) < 5:
            return "Buscando Estructura"

        prices = pivots['min'].fillna(pivots['max']).tolist()
        
        # Lógica de validación de Impulso Alcista (1-2-3-4-5)
        # p0 (inicio), p1 (onda 1), p2 (onda 2), p3 (onda 3), p4 (onda 4), p5 (onda 5)
        # Para simplificar, evaluamos los últimos 5 puntos de giro
        p1, p2, p3, p4, p5 = prices[-5:]

        # Regla 1: Onda 2 no retrocede el 100% de la 1 (p2 > p1 si es long, o p2 < p1 si es short)
        # Aquí asumimos tendencia alcista para el ejemplo de detección de impulso
        is_bullish_impulse = (p1 > prices[-6] if len(prices) > 5 else True) and (p3 > p1) and (p5 > p3) and (p2 > prices[-6] if len(prices) > 5 else True)

        if is_bullish_impulse:
            # Regla 2: Onda 3 no es la más corta
            w1_len = abs(p1 - (prices[-6] if len(prices) > 5 else p1*0.99))
            w3_len = abs(p3 - p2)
            w5_len = abs(p5 - p4)
            
            # Regla 3: Onda 4 no entra en territorio de Onda 1
            no_overlap = p4 > p1
            
            if w3_len > w1_len and w3_len > w5_len and no_overlap:
                return "Impulso Onda 5 (Final)"
            elif p3 > p2 and no_overlap:
                return "Impulso Onda 3 (Fuerte)"
            elif p4 < p3 and p4 > p1:
                return "Corrección Onda 4"
        
        return "Estructura Correctiva"

    except Exception:
        return "Analizando..."

def get_indicators(symbol, timeframe='1h'):
    """Obtiene RSI, BB, EMA 200, ATR, Volume SMA y Elliott Wave."""
    try:
        exchange = binance
        exchange_symbol = f"{symbol}/USDT"
            
        ohlcv = exchange.fetch_ohlcv(exchange_symbol, timeframe=timeframe, limit=300)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        rsi = calculate_rsi(df['close'])
        bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(df['close'])
        ema_200 = calculate_ema(df['close'], period=200)
        atr = calculate_atr(df, period=14)
        vol_sma = (df['volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else 0.0)
        
        elliott = detect_elliot_wave(df)
        
        return (rsi or 50.0), (bb_upper or 0.0), (bb_mid or 0.0), (bb_lower or 0.0), (ema_200 or 0.0), (atr or 0.0), (vol_sma or 0.0), (elliott or "Analizando...")
    except Exception:
        # Silencioso: Retornamos lo último que sabemos para que el bot use caché
        return 50.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "S/D"

def get_macro_trend(symbol):
    """
    Evalúa la tendencia macroscópica (Institucional) en temporalidades 1H y 4H con EMA 200.
    Retorna el estado de la tendencia ("BULL", "BEAR", "NEUTRAL").
    """
    try:
        exchange = binance
        exchange_symbol = f"{symbol}/USDT"
            
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

    except Exception:
        return {"1H": "UNKNOWN", "4H": "UNKNOWN", "consensus": "NEUTRAL"}
