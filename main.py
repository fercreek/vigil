import threading
import os
from dotenv import load_dotenv
from app import app
import scalp_alert_bot

# Cargamos .env para ejecución local (Replit usa Secrets de sistema)
load_dotenv(override=True)

def run_flask():
    """Ejecuta el Dashboard Web en el puerto 8080 (requerido por Replit)."""
    # Replit usa el puerto 8080 por defecto para mostrar la web
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 Dashboard Web iniciado en puerto {port}")
    app.run(host='0.0.0.0', port=port)
def run_bot():
    """Ejecuta el bucle principal del Scalp Alert Bot."""
    print("🤖 Scalp Alert Bot iniciado en segundo plano")
    try:
        scalp_alert_bot.main()
    except Exception as e:
        print(f"❌ Error crítico en el Bot: {e}")

import swing_bot

def run_swing_bot():
    """Ejecuta el bucle principal del Zenith Swing Bot (H4)."""
    print("🏛️ Zenith Swing Bot iniciado en segundo plano")
    try:
        swing_bot.run_zenith_swing()
    except Exception as e:
        print(f"❌ Error crítico en Zenith Swing Bot: {e}")

import stock_analyzer

def run_stock_watchdog():
    """Ejecuta el bucle del Centinela de Acciones."""
    print("👁️ Stock Watchdog iniciado en segundo plano")
    try:
        stock_analyzer.stock_watchdog()
    except Exception as e:
        print(f"❌ Error crítico en Stock Watchdog: {e}")

if __name__ == "__main__":
    print("🚀 --- INICIANDO SISTEMA HÍBRIDO (V2.0 DUAL ENGINE) ---")
    
    # 1. Registro de Comandos (Telegram UI)
    import alert_manager
    alert_manager.set_bot_commands()

    # 2. Hilo para el Scalp Alert Bot (15m)
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # 2. Hilo para el Zenith Swing Bot (H4)
    swing_thread = threading.Thread(target=run_swing_bot)
    swing_thread.daemon = True
    swing_thread.start()
    # 3. Hilo para Telegram Listener (Agente Interactivo)
    telegram_thread = threading.Thread(target=scalp_alert_bot.run_telegram_worker)
    telegram_thread.daemon = True
    telegram_thread.start()

    # 4. Hilo para Centinela de Acciones (Watchdog)
    stock_thread = threading.Thread(target=run_stock_watchdog)
    stock_thread.daemon = True
    stock_thread.start()
    
    # 5. Hilo principal para Flask (Keep-Alive)
    run_flask()
# Hot Reload Test
