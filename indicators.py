import ccxt
import pandas as pd
import requests
import time

try:
    import yfinance as yf
    _HAS_YF = True
except ImportError:
    _HAS_YF = False
    print("[indicators] yfinance no disponible — DXY/VIX deshabilitados")

# Binance para BTC, SOL y TAO
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
        exchange = binance
        exchange_symbol = f"{symbol}/USDT"
        ohlcv = exchange.fetch_ohlcv(exchange_symbol, timeframe=timeframe, limit=50)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return calculate_rsi(df['close'])
    except Exception as e:
        print(f"[RSI ERROR] {symbol}/{timeframe}: {e}")
        # Retorna None para que el caller use el valor cacheado, nunca un 50 inventado
        return None

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

def calculate_bb_width(prices, period=20, std_dev=2):
    """Calcula el ancho relativo de las Bandas de Bollinger (porcentaje)."""
    result = calculate_bollinger_bands(prices, period, std_dev)
    if result is None:
        return 0.0
    upper, mid, lower = result
    if mid == 0:
        return 0.0
    return (upper - lower) / mid

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

def calculate_adx(df, period=14):
    """Calcula el ADX (Average Directional Index) con suavizado de Wilder.

    ADX > 25 indica tendencia fuerte, < 20 indica mercado lateral.
    Usa el mismo patron de Wilder smoothing que calculate_atr() y calculate_rsi().
    """
    if len(df) < period * 2:
        return 0.0

    high = df['high']
    low = df['low']
    close = df['close']

    # +DM / -DM (Directional Movement)
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    # True Range (misma logica que calculate_atr)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder smoothing (alpha=1/period, igual que ATR/RSI)
    atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)

    # DX → ADX
    di_sum = plus_di + minus_di
    di_sum = di_sum.replace(0, 1e-10)  # Evitar division por cero
    dx = ((plus_di - minus_di).abs() / di_sum) * 100
    adx = dx.ewm(alpha=1/period, adjust=False).mean()

    return float(adx.iloc[-1])

def calculate_volume_profile(df, bins=30):
    """Calcula el Volume Profile (POC, VAH, VAL) para detectar nodos de volumen."""
    try:
        if df.empty or len(df) < 50:
            return None, None, None
            
        # 1. Definir los bins de precio
        min_p = df['low'].min()
        max_p = df['high'].max()
        if min_p == max_p: return min_p, min_p, min_p
        
        # 2. Histograma de Volumen
        price_bins = pd.cut(df['close'], bins=bins)
        profile = df.groupby(price_bins, observed=True)['volume'].sum()
        
        # 3. Punto de Control (POC)
        poc_idx = profile.idxmax()
        poc = (poc_idx.left + poc_idx.right) / 2
        
        # 4. Value Area (70% del volumen total)
        total_vol = profile.sum()
        target_vol = total_vol * 0.70
        
        # Ordenar por volumen descendente para acumular el 70%
        sorted_profile = profile.sort_values(ascending=False)
        accum_vol = 0
        va_bins = []
        for idx, vol in sorted_profile.items():
            accum_vol += vol
            va_bins.append(idx)
            if accum_vol >= target_vol:
                break
        
        # VAH (High) y VAL (Low) del Value Area
        va_prices = [b.left for b in va_bins] + [b.right for b in va_bins]
        vah = max(va_prices)
        val = min(va_prices)
        
        return round(poc, 2), round(vah, 2), round(val, 2)
    except:
        return None, None, None

def calculate_rvol(df, period=24):
    """Calcula el Volumen Relativo (RVOL) comparado con la media de 24 periodos."""
    if len(df) < period:
        return 1.0
    current_vol = df['volume'].iloc[-1]
    avg_vol = df['volume'].tail(period).mean()
    if avg_vol == 0: return 1.0
    return round(current_vol / avg_vol, 2)

def calculate_atr_trailing_stop(price, atr, side="LONG", multiplier=2.5):
    """Calcula un Stop Loss dinámico (Trailing) basado en la volatilidad ATR."""
    if side == "LONG":
        return round(price - (atr * multiplier), 2)
    else:
        return round(price + (atr * multiplier), 2)

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

def get_df(symbol, timeframe='1h', limit=300):
    """Obtiene el DataFrame de precios (OHLCV) desde Binance."""
    try:
        exchange_symbol = f"{symbol}/USDT"
        ohlcv = binance.fetch_ohlcv(exchange_symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        print(f"Error fetching DF: {e}")
        return pd.DataFrame()

def get_indicators(symbol, timeframe='1h'):
    """Obtiene RSI, BB, EMA 200, ATR, Volume SMA y Elliott Wave."""
    try:
        df = get_df(symbol, timeframe=timeframe, limit=300)
        if df.empty:
            print(f"[INDICATORS ERROR] DataFrame vacío para {symbol}/{timeframe}")
            return None, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "S/D", 0.0

        rsi = calculate_rsi(df['close'])
        bb_result = calculate_bollinger_bands(df['close'])
        bb_upper, bb_mid, bb_lower = bb_result if bb_result else (0.0, 0.0, 0.0)
        ema_200 = calculate_ema(df['close'], period=200)
        atr = calculate_atr(df, period=14)
        vol_sma = (df['volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else 0.0)

        # V6.0: Volume Profile context
        poc, vah, val = calculate_volume_profile(df)

        elliott = detect_elliot_wave(df)

        return rsi, (bb_upper or 0.0), (bb_mid or 0.0), (bb_lower or 0.0), (ema_200 or 0.0), (atr or 0.0), (vol_sma or 0.0), (elliott or "Analizando..."), (poc or 0.0)
    except Exception as e:
        print(f"[INDICATORS ERROR] {symbol}/{timeframe}: {e}")
        return None, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "S/D", 0.0

def get_dxy_vix():
    """
    Obtiene DXY (índice del dólar) y VIX (volatilidad S&P 500) via yfinance.
    Retorna: (dxy: float, vix: float) — 0.0 si no disponible.

    Reglas de interpretación para el bot:
    - DXY > 105 y subiendo → presión bajista en cripto (safe haven flows)
    - VIX > 25 → mercado de pánico → usar tamaños de posición reducidos (RAPIDA)
    - VIX > 35 → riesgo extremo → no operar o posición mínima
    """
    if not _HAS_YF:
        return 0.0, 0.0
    try:
        dxy_ticker = yf.Ticker("DX-Y.NYB")
        dxy_hist = dxy_ticker.history(period="2d", interval="1h")
        dxy = float(dxy_hist['Close'].iloc[-1]) if not dxy_hist.empty else 0.0
    except Exception as e:
        print(f"[DXY ERROR] {e}")
        dxy = 0.0
    try:
        vix_ticker = yf.Ticker("^VIX")
        vix_hist = vix_ticker.history(period="2d", interval="1h")
        vix = float(vix_hist['Close'].iloc[-1]) if not vix_hist.empty else 0.0
    except Exception as e:
        print(f"[VIX ERROR] {e}")
        vix = 0.0
    return round(dxy, 2), round(vix, 2)


def get_macro_trend(symbol):
    """
    Evalúa la tendencia macroscópica (Institucional) en temporalidades 1H, 4H y 1D con EMA 200.
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

        # Descargar datos 1d
        ohlcv_1d = exchange.fetch_ohlcv(exchange_symbol, timeframe='1d', limit=250)
        df_1d = pd.DataFrame(ohlcv_1d, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        ema_1d = calculate_ema(df_1d['close'], period=200)
        price_1d = df_1d['close'].iloc[-1]
        trend_1d = "UP" if price_1d > ema_1d else "DOWN"

        # Consenso
        consensus = "NEUTRAL"
        if trend_1h == "UP" and trend_4h == "UP":
            consensus = "BULL"
        elif trend_1h == "DOWN" and trend_4h == "DOWN":
            consensus = "BEAR"

        return {
            "1H": trend_1h,
            "4H": trend_4h,
            "1D": trend_1d,
            "consensus": consensus
        }

    except Exception:
        return {"1H": "UNKNOWN", "4H": "UNKNOWN", "1D": "UNKNOWN", "consensus": "NEUTRAL"}

def get_fibonacci_levels(symbol, timeframe='4h', lookback=100):
    """
    Calcula niveles Fibonacci (0.23, 0.38, 0.78) desde el último swing H/L.
    Retorna dict con niveles.
    """
    try:
        df = get_df(symbol, timeframe=timeframe, limit=lookback)
        if df.empty: return {}

        swing_high = df['high'].max()
        swing_low  = df['low'].min()
        rango = swing_high - swing_low

        levels = {
            "swing_high": round(swing_high, 2),
            "swing_low":  round(swing_low, 2),
            "fib_0.23":   round(swing_high - rango * 0.236, 2),
            "fib_0.38":   round(swing_high - rango * 0.382, 2),
            "fib_0.50":   round(swing_high - rango * 0.500, 2),
            "fib_0.618":  round(swing_high - rango * 0.618, 2),
            "fib_0.78":   round(swing_high - rango * 0.786, 2),
        }
        return levels
    except Exception as e:
        print(f"[Fibonacci ERROR] {symbol}/{timeframe}: {e}")
        return {}

def detect_head_and_shoulders(symbol, timeframe='1d', lookback=200):
    """
    Detección simplificada de Head & Shoulders (PHY) en TF alto.
    Retorna: "BEARISH_HnS" | "BULLISH_HnS" | "NONE"
    """
    try:
        df = get_df(symbol, timeframe=timeframe, limit=lookback)
        if len(df) < 50: return "NONE"

        # Detectar pivots locales (ventana 10)
        highs = df['high']
        lows  = df['low']

        # Picos: candidatos a hombros y cabeza
        peaks_idx = [i for i in range(10, len(highs)-10)
                     if highs.iloc[i] == highs.iloc[i-10:i+10].max()]

        if len(peaks_idx) >= 3:
            # Tomar últimos 3 picos
            ls_i, head_i, rs_i = peaks_idx[-3], peaks_idx[-2], peaks_idx[-1]
            ls  = highs.iloc[ls_i]
            head = highs.iloc[head_i]
            rs  = highs.iloc[rs_i]

            # H&S Bajista: cabeza más alta que hombros, hombros aprox iguales
            is_bearish_hns = (
                head > ls * 1.02 and head > rs * 1.02
                and abs(ls - rs) / ls < 0.05  # hombros dentro del 5%
            )
            if is_bearish_hns: return "BEARISH_HnS"

        # Valleys: candidatos a hombros y cabeza (Inverso)
        valleys_idx = [i for i in range(10, len(lows)-10)
                       if lows.iloc[i] == lows.iloc[i-10:i+10].min()]
        
        if len(valleys_idx) >= 3:
            ls_i, head_i, rs_i = valleys_idx[-3], valleys_idx[-2], valleys_idx[-1]
            ls_v  = lows.iloc[ls_i]
            head_v = lows.iloc[head_i]
            rs_v  = lows.iloc[rs_i]

            is_bullish_hns = (
                head_v < ls_v * 0.98 and head_v < rs_v * 0.98
                and abs(ls_v - rs_v) / ls_v < 0.05
            )
            if is_bullish_hns: return "BULLISH_HnS"

        return "NONE"
    except Exception as e:
        print(f"[PHY Detection ERROR] {symbol}/{timeframe}: {e}")
        return "NONE"
