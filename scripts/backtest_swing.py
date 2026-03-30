import pandas as pd
import indicators_swing
import os
from datetime import datetime, timedelta

def run_swing_backtest(symbol="ETH_USDT", target_days=180):
    """Backtest de la estrategia Zenith Swing (H1/H4)."""
    filename = f"data/{symbol}_1h_365d.csv"
    if not os.path.exists(filename):
        print(f"❌ No hay datos para {symbol}")
        return
        
    df = pd.read_csv(filename, parse_dates=['timestamp'], index_col='timestamp')
    df = indicators_swing.calculate_ichimoku(df)
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # Simulación
    trades = []
    active_trade = None
    
    # Filtramos los últimos 180 días
    start_date = df.index.max() - timedelta(days=target_days)
    df_test = df[df.index >= start_date].copy()
    
    for ts, row in df_test.iterrows():
        p = row['close']
        ema = row['ema_200']
        t, k = row['tenkan_sen'], row['kijun_sen']
        span_a, span_b = row['senkou_span_a'], row['senkou_span_b']
        kumo_max = max(span_a, span_b)
        kumo_min = min(span_a, span_b)
        
        if not active_trade:
            # LONG: Precio sobre Nube, sobre EMA y TK Golden Cross
            if p > kumo_max and p > ema and t > k:
                active_trade = {
                    "type": "LONG",
                    "entry": p,
                    "sl": p * 0.985, # 1.5% SL
                    "tp": p * 1.03,  # 3% TP
                    "open_ts": ts
                }
            # SHORT: Precio bajo Nube, bajo EMA y TK Death Cross
            elif p < kumo_min and p < ema and t < k:
                active_trade = {
                    "type": "SHORT",
                    "entry": p,
                    "sl": p * 1.015,
                    "tp": p * 0.97,
                    "open_ts": ts
                }
        else:
            # Gestión de Cierre
            t_type = active_trade["type"]
            entry = active_trade["entry"]
            sl = active_trade["sl"]
            tp = active_trade["tp"]
            
            pnl_pct = 0
            closed = False
            
            if t_type == "LONG":
                if p >= tp:
                    pnl_pct = 3.0
                    closed = True
                elif p <= sl:
                    pnl_pct = -1.5
                    closed = True
            else: # SHORT
                if p <= tp:
                    pnl_pct = 3.0
                    closed = True
                elif p >= sl:
                    pnl_pct = -1.5
                    closed = True
                    
            if closed:
                trades.append({
                    "symbol": symbol,
                    "type": t_type,
                    "entry": entry,
                    "close": p,
                    "pnl": pnl_pct,
                    "duration": (ts - active_trade["open_ts"]).days
                })
                active_trade = None
                
    # Resultados
    if not trades:
        print(f"📊 {symbol}: No se detectaron señales claras en el periodo.")
        return
        
    res_df = pd.DataFrame(trades)
    win_rate = (len(res_df[res_df['pnl'] > 0]) / len(res_df)) * 100
    total_pnl = res_df['pnl'].sum()
    
    print(f"\n--- REPORTE SWING: {symbol} ---")
    print(f"💰 PnL Acumulado: {total_pnl:+.2f}%")
    print(f"🎯 Win Rate: {win_rate:.1f}% ({len(res_df)} trades)")
    print(f"⏳ Duración Promedio: {res_df['duration'].mean():.1f} días")
    print(f"----------------------------")

if __name__ == "__main__":
    for s in ["BTC_USDT", "ETH_USDT", "TAO_USDT"]:
        run_swing_backtest(s)
