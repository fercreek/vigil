import pandas as pd
import numpy as np

def calculate_ichimoku(df):
    """Calcula la Nube de Ichimoku (Configuración estándar: 9, 26, 52)."""
    # 1. Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
    high_9 = df['high'].rolling(window=9).max()
    low_9 = df['low'].rolling(window=9).min()
    df['tenkan_sen'] = (high_9 + low_9) / 2

    # 2. Kijun-sen (Base Line): (26-period high + 26-period low) / 2
    high_26 = df['high'].rolling(window=26).max()
    low_26 = df['low'].rolling(window=26).min()
    df['kijun_sen'] = (high_26 + low_26) / 2

    # 3. Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2
    df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(26)

    # 4. Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2
    high_52 = df['high'].rolling(window=52).max()
    low_52 = df['low'].rolling(window=52).min()
    df['senkou_span_b'] = ((high_52 + low_52) / 2).shift(26)

    # 5. Chikou Span (Lagging Span): Close price shifted back 26 periods
    df['chikou_span'] = df['close'].shift(-26)

    return df

def find_order_blocks(df, lookback=50):
    """Detecta Order Blocks alcistas y bajistas (simplificado)."""
    obs = []
    for i in range(len(df) - lookback, len(df) - 1):
        # 1. Movimiento Impulsivo (Cuerpo grande)
        body_size = abs(df['close'].iloc[i+1] - df['open'].iloc[i+1])
        avg_body = abs(df['close'].iloc[i-5:i].mean() - df['open'].iloc[i-5:i].mean())
        
        if body_size > avg_body * 2:
            # Si sube fuerte, el OB es la vela bajista anterior
            if df['close'].iloc[i+1] > df['open'].iloc[i+1] and df['close'].iloc[i] < df['open'].iloc[i]:
                obs.append({
                    "type": "BULL_OB",
                    "high": df['high'].iloc[i],
                    "low": df['low'].iloc[i],
                    "time": df.index[i]
                })
            # Si baja fuerte, el OB es la vela alcista anterior
            elif df['close'].iloc[i+1] < df['open'].iloc[i+1] and df['close'].iloc[i] > df['open'].iloc[i]:
                obs.append({
                    "type": "BEAR_OB",
                    "high": df['high'].iloc[i],
                    "low": df['low'].iloc[i],
                    "time": df.index[i]
                })
    return obs[-3:] # Retornamos los últimos 3 OBs detectados

def analyze_swing_signals(df):
    """Genera consenso Swing basado en Ichimoku + OB."""
    df = calculate_ichimoku(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # 1. Kumo Breakout con hysteresis (evita whipsaw en nubes delgadas)
    kumo_max = max(last['senkou_span_a'], last['senkou_span_b'])
    kumo_min = min(last['senkou_span_a'], last['senkou_span_b'])

    # ATR-based buffer: require price to clear cloud by 25% of ATR
    hl  = df["high"] - df["low"]
    hc  = (df["high"] - df["close"].shift()).abs()
    lc  = (df["low"]  - df["close"].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    _atr = float(tr.ewm(alpha=1/14, adjust=False).mean().iloc[-1])
    hysteresis = _atr * 0.25

    bias = "NEUTRAL"
    if last['close'] > kumo_max + hysteresis: bias = "BULL"
    elif last['close'] < kumo_min - hysteresis: bias = "BEAR"
    
    # 2. Tenkan/Kijun Cross
    tk_cross = "NONE"
    if prev['tenkan_sen'] <= prev['kijun_sen'] and last['tenkan_sen'] > last['kijun_sen']:
        tk_cross = "GOLDEN"
    elif prev['tenkan_sen'] >= prev['kijun_sen'] and last['tenkan_sen'] < last['kijun_sen']:
        tk_cross = "DEAD"
        
    return {
        "bias": bias,
        "tk_cross": tk_cross,
        "price": last['close'],
        "kumo_cloud": {"top": kumo_max, "bottom": kumo_min}
    }
