import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def scientific_analysis(symbol="ETH/USDT"):
    # 1. Cargar Datos
    filename = f"data/{symbol.replace('/', '_')}_1h_365d.csv"
    if not os.path.exists(filename):
        return None
        
    df = pd.read_csv(filename, parse_dates=['timestamp'], index_col='timestamp')
    
    # 2. Filtrar 48h
    limit_date = df.index.max() - timedelta(days=2)
    df = df[df.index >= limit_date].copy()
    
    # 3. Calcular Indicadores (RSI)
    df['rsi'] = calculate_rsi(df['close'], period=14)
    
    # 4. Calcular Pivot Points Diarios
    df_daily = df.resample('1D').agg({'high': 'max', 'low': 'min', 'close': 'last'})
    df_daily['pivot'] = (df_daily['high'] + df_daily['low'] + df_daily['close']) / 3
    df_daily['r1'] = (2 * df_daily['pivot']) - df_daily['low']
    df_daily['s1'] = (2 * df_daily['pivot']) - df_daily['high']
    
    df_daily_shifted = df_daily[['pivot', 'r1', 's1']].shift(1)
    df['date_only'] = df.index.normalize()
    df = df.merge(df_daily_shifted, left_on='date_only', right_index=True, how='left')
    df = df.dropna()

    # 5. ESTADÍSTICAS
    cerca_r1 = df[df['close'] >= df['r1'] * 0.995]
    cerca_s1 = df[df['close'] <= df['s1'] * 1.005]
    
    v2_short = cerca_r1['rsi'].mean() if len(cerca_r1) > 0 else 60
    v2_long = cerca_s1['rsi'].mean() if len(cerca_s1) > 0 else 40
    
    return {
        "symbol": symbol,
        "price_range": [round(df['close'].min(), 2), round(df['close'].max(), 2)],
        "rsi_avg": round(df['rsi'].mean(), 1),
        "rsi_max": round(df['rsi'].max(), 1),
        "rsi_min": round(df['rsi'].min(), 1),
        "r1_touches": len(cerca_r1),
        "s1_touches": len(cerca_s1),
        "v2_short_rec": round(v2_short, 0),
        "v2_long_rec": round(v2_long, 0)
    }

def run_detailed_backtest(symbol="ETH/USDT", days_ago=1):
    """Simula trades detallados para un día específico (ej. Viernes)."""
    filename = f"data/{symbol.replace('/', '_')}_1h_365d.csv"
    if not os.path.exists(filename): return []
    
    df = pd.read_csv(filename, parse_dates=['timestamp'], index_col='timestamp')
    
    # 1. Definir ventana de tiempo (Día solicitado)
    today = datetime.now()
    target_date = (today - timedelta(days=days_ago)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = target_date + timedelta(days=1)
    
    # Necesitamos 24h antes para los Pivots
    df_context = df[df.index < end_date].tail(500).copy()
    
    # 2. Calcular Pivots Diarios
    df_daily = df_context.resample('1D').agg({'high': 'max', 'low': 'min', 'close': 'last'})
    df_daily['pivot'] = (df_daily['high'] + df_daily['low'] + df_daily['close']) / 3
    df_daily['r1'] = (2 * df_daily['pivot']) - df_daily['low']
    df_daily['s1'] = (2 * df_daily['pivot']) - df_daily['high']
    
    df_daily_shifted = df_daily[['pivot', 'r1', 's1', 'high', 'low']].shift(1)
    
    # 3. Filtrar solo el día del reporte
    df_test = df[(df.index >= target_date) & (df.index < end_date)].copy()
    df_test['date_only'] = df_test.index.normalize()
    df_test = df_test.merge(df_daily_shifted, left_on='date_only', right_index=True, how='left')
    df_test['rsi'] = calculate_rsi(df_test['close'], period=14)
    df_test = df_test.dropna()
    
    # 4. Simulación V2 (RSI 40/60 + Pivots)
    simulated_trades = []
    active_trade = None
    
    for date, row in df_test.iterrows():
        p, r1, s1, rsi = row['close'], row['r1'], row['s1'], row['rsi']
        
        if not active_trade:
            # Entrada SHORT (V2 agresiva 60)
            if p >= r1 and rsi >= 60:
                active_trade = {"type": "SHORT", "entry": p, "sl": p * 1.01, "tp2": s1, "time": date}
            # Entrada LONG (V2 agresiva 40)
            elif p <= s1 and rsi <= 40:
                active_trade = {"type": "LONG", "entry": p, "sl": p * 0.99, "tp2": r1, "time": date}
        else:
            # Gestionar Salida
            if active_trade['type'] == "SHORT":
                if p >= active_trade['sl']:
                    simulated_trades.append({"time": active_trade['time'].strftime('%H:%M'), "type": "SHORT", "res": "LOST", "pnl": -20})
                    active_trade = None
                elif p <= active_trade['tp2']:
                    simulated_trades.append({"time": active_trade['time'].strftime('%H:%M'), "type": "SHORT", "res": "WIN", "pnl": 30})
                    active_trade = None
            elif active_trade['type'] == "LONG":
                if p <= active_trade['sl']:
                    simulated_trades.append({"time": active_trade['time'].strftime('%H:%M'), "type": "LONG", "res": "LOST", "pnl": -20})
                    active_trade = None
                elif p >= active_trade['tp2']:
                    simulated_trades.append({"time": active_trade['time'].strftime('%H:%M'), "type": "LONG", "res": "WIN", "pnl": 30})
                    active_trade = None
                    
    return simulated_trades

if __name__ == "__main__":
    for s in ["ETH/USDT", "BTC/USDT", "TAO/USDT"]:
        res = scientific_analysis(s)
        if res:
            print(f"🔬 {s}: RSI Sugerido SHORT {res['v2_short_rec']} | LONG {res['v2_long_rec']}")
