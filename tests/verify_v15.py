
import os
import sys
import json
from datetime import datetime

# Añadir el root al path
sys.path.append(os.getcwd())

import scalp_alert_bot
import gemini_analyzer
import ai_budget
import telegram_commands

def test_v15_features():
    print("🚀 --- INICIANDO VERIFICACIÓN ZENITH V15 ---")
    
    # 1. Verificar Precios e Indicadores (incluyendo ETH)
    print("\n📦 1. Verificando Precios e Indicadores...")
    prices = scalp_alert_bot.get_prices()
    for sym in ["BTC", "ETH", "TAO", "ZEC"]:
        p = prices.get(sym)
        rsi = prices.get(f"{sym}_RSI")
        if p and rsi:
            print(f"  ✅ {sym}: ${p:,.2f} | RSI: {rsi:.1f}")
        else:
            print(f"  ❌ {sym}: Datos faltantes")
            
    # 2. Verificar Budget Guard
    print("\n🛡️ 2. Verificando Budget Guard...")
    can_use, reason = ai_budget.can_use_ai(call_type="decision")
    print(f"  AI Status: {'CONCEDIDO' if can_use else 'BLOQUEADO'}")
    print(f"  Razón: {reason}")
    
    # 3. Verificar Sentimiento Global (Genesis, Exodo, Salmos)
    print("\n🧠 3. Verificando Sentimiento AI (3 Personas)...")
    sentiment = gemini_analyzer.get_market_sentiment(prices)
    if all(k in sentiment for k in ["genesis", "exodo", "salmos"]):
        print(f"  ✅ Bias: {sentiment['bias']}")
        print(f"  🎩 Genesis: {sentiment['genesis'][:40]}...")
        print(f"  ⚡ Exodo: {sentiment['exodo'][:40]}...")
        print(f"  🌊 Salmos: {sentiment['salmos'][:40]}...")
    else:
        print(f"  ❌ Faltan llaves en el sentimiento: {sentiment.keys()}")
        
    # 4. Verificar Shadow Intel
    print("\n🥷 4. Verificando Shadow Intel Cache...")
    # Forzar un mensaje shadow
    scalp_alert_bot.add_shadow_intel("TEST", "Sistema V15 operativo y verificado.")
    msgs = scalp_alert_bot.GLOBAL_CACHE.get("shadow_messages", [])
    if len(msgs) > 0:
        print(f"  ✅ Mensajes encontrados: {len(msgs)}")
        print(f"  Último: {msgs[0]['msg']}")
    else:
        print("  ❌ Shadow Intel vacío")

    print("\n✨ --- VERIFICACIÓN FINALIZADA ---")

if __name__ == "__main__":
    test_v15_features()
