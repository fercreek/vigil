import os
import sys

# Mocking modules to test logic without network
class MockRequests:
    def post(self, url, json, timeout):
        print(f"[MOCK TELEGRAM] Sending: {json.get('text')}")
        return type('obj', (object,), {'status_code': 200})

import scalp_alert_bot
scalp_alert_bot.requests = MockRequests()
scalp_alert_bot.TELEGRAM_TOKEN = "TEST"
scalp_alert_bot.TELEGRAM_CHAT_ID = "TEST"

def test_phase_transition():
    print("--- Test de Transición de Fase ---")
    
    # Asegurar fase inicial SHORT
    scalp_alert_bot.set_phase("SHORT")
    
    print("\n1. Precio de ETH bajando a Target 1...")
    scalp_alert_bot.check_eth(1960) # Target 1
    
    print("\n2. Precio de ETH bajando a Zona LONG...")
    scalp_alert_bot.check_eth(1900) # Debería cambiar a LONG
    
    current_phase = scalp_alert_bot.get_phase()
    print(f"\nFase actual después del test: {current_phase}")
    
    if current_phase == "LONG":
        print("\n✅ TEST PASADO: El bot cambió a MODO LONG al tocar el fondo.")
    else:
        print("\n❌ TEST FALLIDO: El bot no cambió de fase.")

if __name__ == "__main__":
    test_phase_transition()
