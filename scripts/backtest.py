import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Configuración del Backtest
INITIAL_BALANCE = 1000.0  # Saldo inicial en USD
RISK_PER_TRADE = 0.02     # Arriesgar 2% del balance por trade

# Niveles del Plan (Copiados de scalp_alert_bot.py)
LEVELS = {
    "ETH": {
        "short_entry_high": 2037,
        "sl_short":         2045,
        "target1":          1960,
        "target2":          1930,
        "long_zone":        1905,
    },
    "TAO": {
        "resistance":       320,
        "target1":          290,
        "target2":          270,
        "long_zone":        265,
        "long_sl":          238,
    }
}

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def fetch_data(symbol, exchange, timeframe='15m', days=2):
    since_dt = datetime.utcnow() - timedelta(days=days)
    since = int(since_dt.timestamp() * 1000)
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('date')
    
    # Calcular RSIs
    df['rsi_15m'] = calculate_rsi(df['close'], period=14)
    
    # Para simular RSI de 1H en gráfica de 15m, usamos un periodo de 14 * 4 = 56
    df['rsi_1h'] = calculate_rsi(df['close'], period=56)
    
    return df.dropna()

def run_backtest():
    print("=" * 50)
    print("📈 Iniciando Backtest (Últimos 2 Días)")
    print(f"💰 Presupuesto Inicial: ${INITIAL_BALANCE:,.2f}")
    print("=" * 50)
    
    binance = ccxt.binance()
    gateio = ccxt.gateio()
    
    print("Descargando historial...")
    df_eth = fetch_data('ETH/USDT', binance, days=2)
    df_tao = fetch_data('TAO/USDT', gateio, days=2)
    
    # Merge datasets para iterar cronológicamente
    df_eth = df_eth.add_prefix('eth_')
    df_tao = df_tao.add_prefix('tao_')
    df_combined = pd.concat([df_eth, df_tao], axis=1).ffill().dropna()

    balance = INITIAL_BALANCE
    trades_log = []
    
    # Variables de estado
    eth_phase = "SHORT"
    tao_phase = "SHORT"
    active_trade = None # Soporta solo 1 trade activo a la vez para simulación realista
    
    for date, row in df_combined.iterrows():
        # Variables actuales
        eth_p, eth_rsi_15m, eth_rsi_1h = row['eth_close'], row['eth_rsi_15m'], row['eth_rsi_1h']
        tao_p, tao_rsi_15m, tao_rsi_1h = row['tao_close'], row['tao_rsi_15m'], row['tao_rsi_1h']
        usdt_d_mock = 8.15 # Asumimos contexto bajista/neutral para la prueba de hoy
        
        # --- GESTOR DE TRADE ACTIVO ---
        if active_trade:
            sym = active_trade['symbol']
            p = eth_p if sym == "ETH" else tao_p
            
            if active_trade['type'] == "SHORT":
                if p >= active_trade['sl']:
                    loss = active_trade['risk_amount']
                    balance -= loss
                    trades_log.append({"date": date, "symbol": sym, "type": "SHORT", "status": "LOST", "pnl": -loss})
                    active_trade = None
                elif p <= active_trade['tp2']:
                    win = active_trade['risk_amount'] * 2 # R:R simulado 1:2
                    balance += win
                    trades_log.append({"date": date, "symbol": sym, "type": "SHORT", "status": "FULL_WON", "pnl": win})
                    active_trade = None
                elif p <= active_trade['tp1'] and active_trade['status'] == 'OPEN':
                    active_trade['status'] = 'PARTIAL'
                    active_trade['sl'] = active_trade['entry'] # Break Even
                    
            elif active_trade['type'] == "LONG":
                if p <= active_trade['sl']:
                    loss = active_trade['risk_amount']
                    balance -= loss
                    trades_log.append({"date": date, "symbol": sym, "type": "LONG", "status": "LOST", "pnl": -loss})
                    active_trade = None
                elif p >= active_trade['tp2']:
                    win = active_trade['risk_amount'] * 2
                    balance += win
                    trades_log.append({"date": date, "symbol": sym, "type": "LONG", "status": "FULL_WON", "pnl": win})
                    active_trade = None
                elif p >= active_trade['tp1'] and active_trade['status'] == 'OPEN':
                    active_trade['status'] = 'PARTIAL'
                    active_trade['sl'] = active_trade['entry'] # Break Even
            continue
            
        # --- BUSCADOR DE ENTRADAS (Si no hay trade activo) ---
        risk_amount = balance * RISK_PER_TRADE
        
        # LOGICA ETH
        L = LEVELS["ETH"]
        if eth_phase == "SHORT":
            if eth_p >= L["short_entry_high"] and eth_rsi_1h >= 65: # Relajamos RSI a 65 para test
                active_trade = {'symbol': 'ETH', 'type': 'SHORT', 'entry': eth_p, 'tp1': L["target1"], 'tp2': L["target2"], 'sl': L["sl_short"], 'risk_amount': risk_amount, 'status': 'OPEN'}
            elif eth_p <= L["long_zone"]:
                eth_phase = "LONG"
        elif eth_phase == "LONG":
            if eth_rsi_15m >= 30 and eth_rsi_1h <= 45 and eth_p <= L["long_zone"] + 15:
                active_trade = {'symbol': 'ETH', 'type': 'LONG', 'entry': eth_p, 'tp1': eth_p + 50, 'tp2': L["short_entry_high"], 'sl': eth_p - 50, 'risk_amount': risk_amount, 'status': 'OPEN'}
                
        # LOGICA TAO (Solo busca si no entró en ETH)
        if not active_trade:
            L = LEVELS["TAO"]
            if tao_phase == "SHORT":
                if tao_p >= L["resistance"] and tao_rsi_1h >= 65:
                    active_trade = {'symbol': 'TAO', 'type': 'SHORT', 'entry': tao_p, 'tp1': L["target1"], 'tp2': L["target2"], 'sl': tao_p + 10, 'risk_amount': risk_amount, 'status': 'OPEN'}
                elif tao_p <= L["long_zone"]:
                    tao_phase = "LONG"
            elif tao_phase == "LONG":
                if tao_rsi_15m >= 30 and tao_rsi_1h <= 45 and tao_p <= L["long_zone"] + 5:
                    active_trade = {'symbol': 'TAO', 'type': 'LONG', 'entry': tao_p, 'tp1': tao_p + 15, 'tp2': L["resistance"], 'sl': tao_p - 15, 'risk_amount': risk_amount, 'status': 'OPEN'}
                    
    # Reporte Final
    print("\n" + "=" * 50)
    print("📋 REPORTE FINAL DE BACKTEST")
    print("=" * 50)
    wins = len([t for t in trades_log if t['status'] == 'FULL_WON'])
    losses = len([t for t in trades_log if t['status'] == 'LOST'])
    total = len(trades_log)
    
    print(f"💰 Balance Final: ${balance:,.2f} ({((balance/INITIAL_BALANCE)-1)*100:+.2f}%)")
    print(f"📊 Trades Ejecutados: {total}")
    if total > 0:
        print(f"✅ Ganados (Full TP2): {wins}")
        print(f"❌ Perdidos (Stop Loss): {losses}")
        print(f"🎯 Win Rate: {(wins/total)*100:.1f}%")
        print("\nHistorial:")
        for t in trades_log:
            sign = "+" if t['pnl'] > 0 else "-"
            print(f"  [{t['date']}] {t['symbol']} {t['type']} -> {t['status']} ({sign}${abs(t['pnl']):.2f})")
    else:
        print("No se encontraron oportunidades bajo los parámetros estrictos de la estrategia en los últimos 2 días.")

if __name__ == "__main__":
    run_backtest()
