import pandas as pd
import numpy as np
import itertools
from datetime import datetime, timedelta
from auto_levels import map_levels_to_hourly

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def load_data_from_cache(symbol, days=365):
    safe_symbol = symbol.replace("/", "_")
    filename = f"data/{safe_symbol}_1h_{days}d.csv"
    try:
        df = pd.read_csv(filename, parse_dates=['timestamp'], index_col='timestamp')
        print(f"[DATA] Cargado historial {symbol}: {len(df)} horas.")
        return df
    except Exception as e:
        print(f"Error cargando {filename}: {e}")
        return None

def backtest_strategy(df, params):
    sl_pct, rsi_ob, rsi_os = params['sl_pct'], params['rsi_ob'], params['rsi_os']
    
    INITIAL_BALANCE = 1000.0
    RISK_PER_TRADE = 0.02 # Arriesgamos el 2% del capital total en cada trade
    balance = INITIAL_BALANCE
    
    trades = []
    active_trade = None
    
    # Pre-calcular distancias de iterrows extra para acelerar pandas
    # Pero lo haremos secuencial para manejar el PnL y estado correctamente
    
    for i, (date, row) in enumerate(df.iterrows()):
        p = row['close']
        rsi = row['rsi']
        r1, s1, pivot = row['r1'], row['s1'], row['pivot']
        
        # Ignorar si hay NAN de los primeros días
        if pd.isna(r1) or pd.isna(rsi): continue
        
        if active_trade:
            # GESTOR DE TRADE ABIERTO
            if active_trade['type'] == "SHORT":
                if p >= active_trade['sl']:
                    balance -= active_trade['risk']
                    trades.append({'status': 'LOST', 'pnl': -active_trade['risk']})
                    active_trade = None
                elif p <= active_trade['tp2']:
                    win = active_trade['reward']
                    balance += win
                    trades.append({'status': 'FULL_WON', 'pnl': win})
                    active_trade = None
                elif p <= active_trade['tp1'] and active_trade['status'] == 'OPEN':
                    active_trade['status'] = 'PARTIAL'
                    active_trade['sl'] = active_trade['entry'] # Break Even
                    
            elif active_trade['type'] == "LONG":
                if p <= active_trade['sl']:
                    balance -= active_trade['risk']
                    trades.append({'status': 'LOST', 'pnl': -active_trade['risk']})
                    active_trade = None
                elif p >= active_trade['tp2']:
                    win = active_trade['reward']
                    balance += win
                    trades.append({'status': 'FULL_WON', 'pnl': win})
                    active_trade = None
                elif p >= active_trade['tp1'] and active_trade['status'] == 'OPEN':
                    active_trade['status'] = 'PARTIAL'
                    active_trade['sl'] = active_trade['entry'] # Break Even
                    
            continue # Una vez dentro, no buscar nuevas entradas
            
        # BUSCADOR DE ENTRADAS (Dinámico usando Pivot Points)
        risk_amount = balance * RISK_PER_TRADE
        
        # Estrategia SHORT
        # Precio rompiendo o testeando la Resistencia 1 (R1) con RSI sobrecomprado
        if p >= r1 and rsi >= rsi_ob:
            sl_price = p * (1 + sl_pct) # Stop loss % arriba de la entrada
            # Reward: Desde P hasta TP2
            reward_amount = risk_amount * ((p - s1) / (sl_price - p)) # Riesgo Real = (Entrada - TP2 / SL - Entrada) x Riesgo 
            active_trade = {
                'type': 'SHORT', 'entry': p, 'sl': sl_price, 
                'tp1': pivot, 'tp2': s1, # Objetivos naturales del pivot
                'risk': risk_amount, 'reward': reward_amount, 'status': 'OPEN'}
                
        # Estrategia LONG
        # Precio tocando o bajo Soporte 1 (S1) con RSI sobrevendido
        elif p <= s1 and rsi <= rsi_os:
            sl_price = p * (1 - sl_pct) # Stop loss % debajo de la entrada
            reward_amount = risk_amount * ((r1 - p) / (p - sl_price))
            active_trade = {
                'type': 'LONG', 'entry': p, 'sl': sl_price, 
                'tp1': pivot, 'tp2': r1, 
                'risk': risk_amount, 'reward': reward_amount, 'status': 'OPEN'}
                
    wins = len([t for t in trades if t['status'] == 'FULL_WON'])
    losses = len([t for t in trades if t['status'] == 'LOST'])
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0
    pnl_pct = ((balance / INITIAL_BALANCE) - 1) * 100
    
    return {'total_trades': total, 'wins': wins, 'losses': losses, 'win_rate': win_rate, 'final_balance': balance, 'pnl_pct': pnl_pct}

def run_grid_search(symbol):
    print(f"\n--- Iniciando Grid Search para {symbol} (Últimas 48h) ---")
    df_raw = load_data_from_cache(symbol, 365) # Cargar cache de 1 año
    if df_raw is None: return
    
    # Filtrar solo las últimas 48 horas para el reporte de "Ayer"
    limit_date = datetime.utcnow() - timedelta(days=2)
    df_raw = df_raw[df_raw.index >= limit_date]
    
    if df_raw.empty:
        print(f"[!] No hay datos recientes en el cache para {symbol}.")
        return

    df_raw['rsi'] = calculate_rsi(df_raw['close'], period=14)
    df = map_levels_to_hourly(df_raw) # Proyectar Pivot Points
    
    # Parámetros a probar (Relajados para encontrar trades en 48h)
    sl_pct_grid = [0.005, 0.01] 
    rsi_ob_grid = [50, 60, 70] 
    rsi_os_grid = [30, 40, 50] 
    
    results = []
    total_combinations = len(sl_pct_grid) * len(rsi_ob_grid) * len(rsi_os_grid)
    curr = 1
    
    for sl, ob, os in itertools.product(sl_pct_grid, rsi_ob_grid, rsi_os_grid):
        print(f"[{curr}/{total_combinations}] Testeando: SL {sl*100:.1f}%, RSI OB {ob}, RSI OS {os}... \r", end="")
        params = {'sl_pct': sl, 'rsi_ob': ob, 'rsi_os': os}
        res = backtest_strategy(df, params)
        res.update(params)
        results.append(res)
        curr += 1
        
    print("\n--- Optimizador Terminado ---")
    res_df = pd.DataFrame(results)
    
    # Ordenar por PnL Final (Retorno)
    best_ret = res_df.sort_values(by='pnl_pct', ascending=False).head(3)
    print("\n🏆 Top 3 Configuraciones por PROFIT ($):")
    print(best_ret[['sl_pct', 'rsi_ob', 'rsi_os', 'total_trades', 'win_rate', 'pnl_pct']])
    
    # Ordenar por Win Rate (Min 50 trades)
    res_df_valid = res_df[res_df['total_trades'] >= 50]
    if not res_df_valid.empty:
        best_wr = res_df_valid.sort_values(by='win_rate', ascending=False).head(3)
        print("\n🎯 Top 3 Configuraciones por ASERTIVIDAD (Win Rate):")
        print(best_wr[['sl_pct', 'rsi_ob', 'rsi_os', 'total_trades', 'win_rate', 'pnl_pct']])

if __name__ == "__main__":
    run_grid_search("ETH/USDT")
    run_grid_search("BTC/USDT")
    
    # Probar TAO con try-catch por el menor histórico
    try:
        run_grid_search("TAO/USDT")
    except Exception as e:
        print(f"Error procesando TAO: {e}")
