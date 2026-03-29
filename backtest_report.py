import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from auto_levels import map_levels_to_hourly

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def fetch_48h_data(symbol, exchange_id='binance'):
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class()
    since = int((datetime.utcnow() - timedelta(days=3)).timestamp() * 1000) # 3 días para tener contexto diario previo
    ohlcv = exchange.fetch_ohlcv(symbol, '15m', since=since, limit=1000)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def simulate_yesterday():
    print("⏳ Analizando mercado de las últimas 48 horas...")
    
    # 1. Obtener Datos
    df_eth = fetch_48h_data('ETH/USDT', 'binance')
    df_tao = fetch_48h_data('TAO/USDT', 'gateio')
    
    # 2. Calcular Niveles Dinámicos (Pivots)
    df_eth = map_levels_to_hourly(df_eth)
    df_tao = map_levels_to_hourly(df_tao)
    
    # 3. Calcular Indicadores (RSI 1h y 15m)
    # Para simular RSI 1h en velas de 15m, usamos periodo 56
    df_eth['rsi_1h'] = calculate_rsi(df_eth['close'], period=56)
    df_eth['rsi_15m'] = calculate_rsi(df_eth['close'], period=14)
    df_tao['rsi_1h'] = calculate_rsi(df_tao['close'], period=56)
    df_tao['rsi_15m'] = calculate_rsi(df_tao['close'], period=14)
    
    # 4. Simulación
    balance = 1000.0
    risk_pct = 0.02 # 2% por trade
    trades_log = []
    
    # Simulación ETH (Solo las últimas 48h reales del dataset)
    mask = df_eth.index > (datetime.utcnow() - timedelta(days=2))
    df_eth_recent = df_eth[mask]
    
    active_trade = None
    
    for date, row in df_eth_recent.iterrows():
        p, r1, s1, pivot = row['close'], row['r1'], row['s1'], row['pivot']
        rsi_1h, rsi_15m = row['rsi_1h'], row['rsi_15m']
        
        if active_trade:
            # Gestionar salida
            if active_trade['type'] == "SHORT":
                if p >= active_trade['sl']:
                    balance -= active_trade['risk_usd']
                    trades_log.append({"date": date, "sym": "ETH", "type": "SHORT", "res": "🔴 LOST", "pnl": -active_trade['risk_usd']})
                    active_trade = None
                elif p <= active_trade['tp2']:
                    win = active_trade['risk_usd'] * 1.5 # R:R simple para reporte
                    balance += win
                    trades_log.append({"date": date, "sym": "ETH", "type": "SHORT", "res": "🟢 FULL WON", "pnl": win})
                    active_trade = None
            continue
            
        # Buscar Entrada SHORT (Resistencia 1 + RSI 1h Alto)
        if p >= r1 and rsi_1h >= 65:
            risk_usd = balance * risk_pct
            active_trade = {
                "type": "SHORT", "entry": p, "sl": p * 1.01, "tp2": s1, "risk_usd": risk_usd
            }

    # Generar Reporte Markdown
    with open("reporte_ayer.md", "w") as f:
        f.write("# Reporte de Estrategia: Ayer y Hoy\n\n")
        f.write(f"**Balance Inicial:** $1,000.00\n")
        f.write(f"**Balance Final:** ${balance:,.2f}\n")
        f.write(f"**Trades Totales:** {len(trades_log)}\n\n")
        f.write("## Bitácora de Operaciones\n")
        f.write("| Fecha | Moneda | Tipo | Resultado | PnL ($) |\n")
        f.write("|-------|--------|------|-----------|---------|\n")
        for t in trades_log:
            f.write(f"| {t['date'].strftime('%d/%m %H:%M')} | {t['sym']} | {t['type']} | {t['res']} | ${t['pnl']:,.2f} |\n")
            
    print("✅ Reporte generado en reporte_ayer.md")

if __name__ == "__main__":
    simulate_yesterday()
