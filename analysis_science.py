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

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    return sma + (std * std_dev), sma - (std * std_dev)

def run_detailed_backtest(symbol="ETH/USDT", target_date_str=None, days_ago=1, version="V1-TECH"):
    """
    Simula trades detallados con nivel de alerta para un día y versión específica.
    Acepta target_date_str (YYYY-MM-DD) o days_ago (int).
    """
    filename = f"data/{symbol.replace('/', '_')}_1h_365d.csv"
    if not os.path.exists(filename): return []
    
    df = pd.read_csv(filename, parse_dates=['timestamp'], index_col='timestamp')
    
    # 1. Determinar el día objetivo
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        except ValueError:
            target_date = datetime.now() - timedelta(days=1)
    else:
        target_date = datetime.now() - timedelta(days=days_ago)
    target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = target_date + timedelta(days=1)
    
    # 2. Contexto para indicadores (24h previas + el día)
    df_context = df[df.index < end_date].tail(720).copy()
    
    # 3. Calcular Pivots Diarios del día anterior
    df_daily = df_context.resample('1D').agg({'high': 'max', 'low': 'min', 'close': 'last'})
    df_daily['p'] = (df_daily['high'] + df_daily['low'] + df_daily['close']) / 3
    df_daily['r1'] = (2 * df_daily['p']) - df_daily['low']
    df_daily['s1'] = (2 * df_daily['p']) - df_daily['high']
    df_daily_shifted = df_daily[['p', 'r1', 's1']].shift(1)
    
    # 4. Dataset de prueba: solo el día objetivo
    df_test = df[(df.index >= target_date) & (df.index < end_date)].copy()
    if df_test.empty:
        return []
    
    df_test['date_only'] = df_test.index.normalize()
    df_test = df_test.merge(df_daily_shifted, left_on='date_only', right_index=True, how='left')
    
    # Calcular indicadores sobre todo el contexto, extraer para el día
    df_context['rsi'] = calculate_rsi(df_context['close'], period=14)
    bb_u, bb_l = calculate_bollinger_bands(df_context['close'])
    df_context['bb_upper'] = bb_u
    df_context['bb_lower'] = bb_l
    
    df_test = df_test.join(df_context[['rsi', 'bb_upper', 'bb_lower']], how='left')
    df_test = df_test.dropna(subset=['r1', 's1', 'rsi'])
    
    if df_test.empty:
        return []
    
    # 5. Umbrales por versión
    rsi_short = 62 if version == "V1-TECH" else 60
    rsi_long = 38 if version == "V1-TECH" else 40
    
    simulated_trades = []
    active_trade = None
    
    for ts, row in df_test.iterrows():
        price = row['close']
        r1, s1, rsi = row['r1'], row['s1'], row['rsi']
        bb_u_val = row.get('bb_upper', None)
        bb_l_val = row.get('bb_lower', None)
        
        # Determinar estado Bollinger
        bb_status = "En rango medio"
        if bb_u_val and price >= bb_u_val * 0.99:
            bb_status = "🔴 Cerca Banda Superior"
        elif bb_l_val and price <= bb_l_val * 1.01:
            bb_status = "🟢 Cerca Banda Inferior"
        
        if not active_trade:
            # — ENTRADA SHORT —
            if price >= r1 and rsi >= rsi_short:
                sl = round(price * 1.01, 2)
                sl_dist = sl - price
                tp1 = round(price - sl_dist * 1.0, 2)  # 1:1 R:R
                tp2 = round(price - sl_dist * 2.0, 2)  # 2:1 R:R
                active_trade = {
                    "symbol": symbol,
                    "version": version,
                    "type": "SHORT",
                    "entry_price": round(price, 2),
                    "rsi_entry": round(rsi, 1),
                    "bb_status": bb_status,
                    "sl": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "pivot_r1": round(r1, 2),
                    "pivot_s1": round(s1, 2),
                    "open_time": ts.strftime('%H:%M'),
                    "open_ts": ts,
                    "alert_reason": f"Precio ${price:.2f} >= R1 ${r1:.2f} | RSI {rsi:.1f} >= {rsi_short}"
                }
            # — ENTRADA LONG —
            elif price <= s1 and rsi <= rsi_long:
                sl = round(price * 0.99, 2)
                sl_dist = price - sl
                tp1 = round(price + sl_dist * 1.0, 2)  # 1:1 R:R
                tp2 = round(price + sl_dist * 2.0, 2)  # 2:1 R:R
                active_trade = {
                    "symbol": symbol,
                    "version": version,
                    "type": "LONG",
                    "entry_price": round(price, 2),
                    "rsi_entry": round(rsi, 1),
                    "bb_status": bb_status,
                    "sl": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "pivot_r1": round(r1, 2),
                    "pivot_s1": round(s1, 2),
                    "open_time": ts.strftime('%H:%M'),
                    "open_ts": ts,
                    "alert_reason": f"Precio ${price:.2f} <= S1 ${s1:.2f} | RSI {rsi:.1f} <= {rsi_long}"
                }
        else:
            t = active_trade
            duration_min = int((ts - t["open_ts"]).total_seconds() / 60)
            
            def close_trade(result, close_price, pnl_usd):
                pnl_pct = round(((close_price - t['entry_price']) / t['entry_price']) * 100 * (-1 if t['type'] == 'SHORT' else 1), 2)
                simulated_trades.append({
                    **{k: v for k, v in t.items() if k != 'open_ts'},
                    "result": result,
                    "close_time": ts.strftime('%H:%M'),
                    "close_price": round(close_price, 2),
                    "duration_min": duration_min,
                    "pnl_usd": pnl_usd,
                    "pnl_pct": pnl_pct,
                })
            
            if t['type'] == "SHORT":
                if price >= t['sl']:
                    close_trade("LOST", price, -20)
                    active_trade = None
                elif price <= t['tp1'] and 'tp1_hit' not in t:
                    t['tp1_hit'] = True  # Anotamos que TP1 fue tocado, no cerramos
                elif price <= t['tp2']:
                    close_trade("WIN_FULL", price, 20)
                    active_trade = None
            elif t['type'] == "LONG":
                if price <= t['sl']:
                    close_trade("LOST", price, -20)
                    active_trade = None
                elif price >= t['tp1'] and 'tp1_hit' not in t:
                    t['tp1_hit'] = True
                elif price >= t['tp2']:
                    close_trade("WIN_FULL", price, 20)
                    active_trade = None
    
    # Cerrar trade abierto al final del día con PnL real (unrealized)
    if active_trade and not df_test.empty:
        last_price = df_test.iloc[-1]['close']
        last_ts = df_test.index[-1]
        duration_min = int((last_ts - active_trade["open_ts"]).total_seconds() / 60)
        entry = active_trade['entry_price']
        direction = 1 if active_trade['type'] == 'LONG' else -1
        move_pct = (last_price - entry) / entry * direction
        # PnL real basado en posición: riesgo=$10, SL=1%, por ende posición=$1000
        pnl_real = round(move_pct * 1000, 2)  # gana/pierde en proporción al movimiento
        pnl_pct = round(move_pct * 100, 2)
        
        simulated_trades.append({
            **{k: v for k, v in active_trade.items() if k != 'open_ts'},
            "result": "OPEN_EOD",
            "close_time": last_ts.strftime('%H:%M'),
            "close_price": round(last_price, 2),
            "duration_min": duration_min,
            "pnl_usd": pnl_real,  # PnL real del movimiento del día
            "pnl_pct": pnl_pct,
        })
    
    return simulated_trades

if __name__ == "__main__":
    for s in ["ETH/USDT", "BTC/USDT", "TAO/USDT"]:
        res = scientific_analysis(s)
        if res:
            print(f"🔬 {s}: RSI Sugerido SHORT {res['v2_short_rec']} | LONG {res['v2_long_rec']}")
