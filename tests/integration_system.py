import os
import sys
import time
from datetime import datetime

# Añadir el path actual para importación de core
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

import scalp_alert_bot
import gemini_analyzer
from trading_executor import ZenithExecutor
import indicators

def test_pulse():
    print("\n--- 🧪 TEST DE PULSO ZENITH V14.0 ---")
    
    # 1. Conectividad y Datos
    print("\n📡 [1/3] Verificando Precios e Indicadores...")
    try:
        prices = scalp_alert_bot.get_prices()
        btc = prices.get('BTC', 0)
        sol = prices.get('SOL', 0)
        usdt_d = prices.get('USDT_D', 8.08)
        print(f"✅ Conectividad: BTC \${btc:,.2f} | SOL \${sol:,.2f} | USDT.D {usdt_d:.2f}%")
        
        # Test de RSI Real
        rsi_sol = indicators.get_rsi('SOL', '15m')
        print(f"✅ Cálculo RSI SOL (15m): {rsi_sol:.2f}")
    except Exception as e:
        print(f"❌ Error en Datos: {e}")

    # 2. Gestión de Riesgo (Arquitectura de Ejecución)
    print("\n⚖️ [2/3] Verificando Ejecutor de Riesgo (1% Rule)...")
    try:
        executor = ZenithExecutor()
        executor.mode = "PAPER"
        balance = 1000.0
        entry = 100.0
        sl = 95.0
        # Riesgo 1% de 1000 = $10. Distancia SL = $5. Cantidad = 2.0
        amount = executor.calculate_amount("SOL", entry, sl, balance)
        print(f"✅ Simulación Posición: Entrada 100, SL 95, Balance 1000")
        print(f"✅ Cantidad Calculada: {amount}")
        if amount == 2.0:
            print("✨ INTEGRIDAD MATEMÁTICA: 100% (Riesgo 1% Verificado)")
        else:
            print(f"⚠️ DESVIACIÓN: Se esperaba 2.0, se obtuvo {amount}")
    except Exception as e:
        print(f"❌ Error en Ejecutor: {e}")

    # 3. Inteligencia AI (Sentimiento y Personalidad)
    print("\n🧠 [3/3] Verificando Consenso AI (Gordon & Aiden)...")
    try:
        # Data para sentimiento
        sentiment_data = {
            "BTC": btc,
            "SOL": sol,
            "USDT_D": usdt_d
        }
        report = gemini_analyzer.get_market_sentiment(sentiment_data)
        print(f"✅ AI Bias Detectado: {report.get('bias', 'NEUTRAL')}")
        print(f"🎩 GENESIS: \"{report.get('genesis', 'Sin datos')}\"")
        print(f"⚡ EXODO: \"{report.get('exodo', 'Sin datos')}\"")
    except Exception as e:
        print(f"❌ Error en Inteligencia AI: {e}")

    print("\n🏁 --- SESIÓN DE PRUEBAS FINALIZADA ---")

if __name__ == "__main__":
    test_pulse()
