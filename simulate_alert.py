import os
import requests
import time
from dotenv import load_dotenv
import scalp_alert_bot
import tracker

# Cargar credenciales reales
load_dotenv()

def print_win_rate():
    fw, pw, l, t = tracker.get_win_rate()
    print(f"\n📊 --- STATS GLOBALES ---")
    print(f"Ganados Completos (🟢): {fw}")
    print(f"Ganados Parciales (🟡): {pw}")
    print(f"Perdidos (🔴): {l}")
    print(f"Total: {t}")
    if t > 0:
        win_rate = ((fw + pw) / t) * 100
        print(f"Win Rate General: {win_rate:.1f}%")

def simulate():
    print("🚀 Simulador Avanzado: Ciclo Completo de Scalping")
    
    # Reset de testing
    scalp_alert_bot.set_phase("SHORT")
    
    # 1. Simular ENTRADA SHORT
    print("\n👉 [Paso 1] Generando Alerta de Entrada (ETH)")
    # El bot registra el trade internamente
    scalp_alert_bot.check_eth(p=2038, rsi_1h=72.0, rsi_15m=65.0, usdt_d=8.15)
    print_win_rate()
    time.sleep(3)

    # 2. Simular Precio moviéndose a TARGET 1 (Parcial)
    open_trades = tracker.get_open_trades()
    print(f"\n👉 [Paso 2] Simulando caída a Target 1 (1960). Trades abiertos detectados: {len(open_trades)}")
    mock_prices = {"ETH": 1960.0, "TAO": 320, "BTC": 65000}
    scalp_alert_bot.monitor_open_trades(mock_prices) # El sistema detectará que cruzó el TP1
    print_win_rate()
    time.sleep(3)

    # 3. Simular Precio moviéndose a TARGET 2 (Completado)
    print("\n👉 [Paso 3] Simulando caída profunda a Target 2 (1930).")
    mock_prices["ETH"] = 1930.0
    scalp_alert_bot.monitor_open_trades(mock_prices) # El sistema cerrará el trade
    print_win_rate()
    time.sleep(3)
    
    # 4. Simular un SL. Generamos un TAO Short que falla
    print("\n👉 [Paso 4] Generamos un Trade en TAO que falla (Toca Stop Loss)")
    scalp_alert_bot.check_tao(p=321, rsi_1h=71.0, rsi_15m=75.0, usdt_d=8.20)
    mock_prices["TAO"] = 332 # SL de TAO está en P+10 (331) -> Toca SL
    scalp_alert_bot.monitor_open_trades(mock_prices)
    print_win_rate()

if __name__ == "__main__":
    simulate()
