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
    print(f"🔬 Análisis Científico de Estrategia para {symbol} (Últimas 48h)")
    
    # 1. Cargar Datos
    filename = f"data/{symbol.replace('/', '_')}_1h_365d.csv"
    if not os.path.exists(filename):
        print(f"Error: {filename} no encontrado.")
        return
        
    df = pd.read_csv(filename, parse_dates=['timestamp'], index_col='timestamp')
    
    # 2. Filtrar 48h
    limit_date = df.index.max() - timedelta(days=2)
    df = df[df.index >= limit_date].copy()
    
    # 3. Calcular Indicadores (RSI)
    df['rsi'] = calculate_rsi(df['close'], period=14)
    
    # 4. Calcular Pivot Points Diarios
    # Agrupamos por día para calcular H/L/C de ayer
    df_daily = df.resample('1D').agg({'high': 'max', 'low': 'min', 'close': 'last'})
    df_daily['pivot'] = (df_daily['high'] + df_daily['low'] + df_daily['close']) / 3
    df_daily['r1'] = (2 * df_daily['pivot']) - df_daily['low']
    df_daily['s1'] = (2 * df_daily['pivot']) - df_daily['high']
    
    # Shift manual para aplicar niveles de ayer a hoy
    df_daily_shifted = df_daily[['pivot', 'r1', 's1']].shift(1)
    
    # Merge con el horario
    df['date_only'] = df.index.normalize()
    df = df.merge(df_daily_shifted, left_on='date_only', right_index=True, how='left')
    df = df.dropna()

    # 5. ESTADÍSTICAS CIENTÍFICAS
    print("-" * 50)
    print(f"Rango de Precio: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    print(f"RSI Promedio: {df['rsi'].mean():.1f}")
    print(f"RSI Máximo: {df['rsi'].max():.1f} | RSI Mínimo: {df['rsi'].min():.1f}")
    
    # 6. ¿Cuántas veces el precio estuvo cerca de R1/S1?
    # Definimos "Cerca" como +- 0.5%
    cerca_r1 = df[df['close'] >= df['r1'] * 0.995]
    cerca_s1 = df[df['close'] <= df['s1'] * 1.005]
    
    print("-" * 50)
    print(f"Momentos cerca de Resistencia (R1): {len(cerca_r1)}")
    if len(cerca_r1) > 0:
        print(f"RSI Promedio en R1: {cerca_r1['rsi'].mean():.1f}")
        print(f"Sugerencia RSI Short (V2): {cerca_r1['rsi'].max():.1f} (Usar el máximo histórico de ayer para no fallar)")
        
    print(f"Momentos cerca de Soporte (S1): {len(cerca_s1)}")
    if len(cerca_s1) > 0:
        print(f"RSI Promedio en S1: {cerca_s1['rsi'].mean():.1f}")
        print(f"Sugerencia RSI Long (V2): {cerca_s1['rsi'].min():.1f}")

    print("-" * 50)
    # Generar nueva recomendación dinámica
    v2_short = cerca_r1['rsi'].mean() if len(cerca_r1) > 0 else 60
    v2_long = cerca_s1['rsi'].mean() if len(cerca_s1) > 0 else 40
    
    print(f"💡 RECOMENDACIÓN V2 (Basada en Medias Móviles de RSI de Ayer):")
    print(f"   Configura SHORT RSI: {v2_short:.0f}")
    print(f"   Configura LONG RSI: {v2_long:.0f}")

if __name__ == "__main__":
    scientific_analysis("ETH/USDT")
    scientific_analysis("BTC/USDT")
    scientific_analysis("TAO/USDT")
