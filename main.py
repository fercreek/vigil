import threading
import time
import os
from dotenv import load_dotenv

# Cargamos .env ANTES de cualquier import que use variables de entorno
load_dotenv(override=True)

# F6 BOT_MODE resolver — selecciona token/chat_id según PROD vs DEV
# Runs BEFORE any module imports TELEGRAM_TOKEN/TELEGRAM_CHAT_ID at module scope
_bot_mode = os.getenv("BOT_MODE", "PROD").upper()
if _bot_mode == "DEV":
    _dev_token = os.getenv("TELEGRAM_TOKEN_DEV") or os.getenv("TELEGRAM_BOT_TOKEN_DEV")
    _dev_chat  = os.getenv("TELEGRAM_CHAT_ID_DEV")
    if _dev_token:
        os.environ["TELEGRAM_TOKEN"] = _dev_token
    if _dev_chat:
        os.environ["TELEGRAM_CHAT_ID"] = _dev_chat
    # Force PAPER in DEV to avoid real trades from dev iteration
    os.environ["EXECUTION_MODE"] = "PAPER"
    print(f"[BOOT] BOT_MODE=DEV — using dev token + EXECUTION_MODE=PAPER forced")
else:
    print(f"[BOOT] BOT_MODE=PROD")

from logger_core import logger
from app import app
import scalp_alert_bot
import swing_bot
import stock_analyzer
import commodities_bot
import thread_health


# --- Thread restart helpers ---

_thread_registry = {}  # name -> (thread_obj, target_fn)


def _start_thread(name: str, target_fn):
    """Arranca un hilo daemon con auto-restart y lo registra."""
    def _wrapper():
        restarts = 0
        while restarts < thread_health.MAX_RESTARTS:
            try:
                logger.info("🚀 Hilo '%s' iniciado (intento %d)", name, restarts + 1)
                target_fn()
                # Si target_fn retorna normalmente, es inesperado — reiniciar
                logger.warning("⚠️ Hilo '%s' retornó inesperadamente — reiniciando", name)
            except Exception as e:
                logger.error("❌ Hilo '%s' crasheó: %s", name, e, exc_info=True)
                thread_health.notify(name, "CRASH", str(e))
            restarts += 1
            backoff = min(30, 5 * restarts)
            logger.info("⏳ Hilo '%s' reiniciando en %ds...", name, backoff)
            time.sleep(backoff)
        logger.critical("💀 Hilo '%s' agotó reintentos (%d)", name, thread_health.MAX_RESTARTS)
        thread_health.notify(name, "DEAD", f"Agotó {thread_health.MAX_RESTARTS} reintentos")

    t = threading.Thread(target=_wrapper, daemon=True, name=name)
    t.start()
    _thread_registry[name] = (t, target_fn)

    # Registrar callback en watchdog para reinicio por heartbeat timeout
    def _restart_callback():
        logger.warning("🛡️ Watchdog reiniciando hilo '%s'", name)
        _start_thread(name, target_fn)
    thread_health.register(name, _restart_callback)

    return t


def run_flask():
    """Ejecuta el Dashboard Web en el puerto 8080 (requerido por Replit)."""
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 Dashboard Web iniciado en puerto {port}")
    app.run(host='0.0.0.0', port=port)


if __name__ == "__main__":
    print("🚀 --- INICIANDO SISTEMA HÍBRIDO (V2.0 DUAL ENGINE + WATCHDOG) ---")

    # 1. Registro de Comandos (Telegram UI)
    import alert_manager
    alert_manager.set_bot_commands()

    # 2. Arrancar watchdog PRIMERO
    thread_health.start_watchdog()

    # 3. Hilos principales con auto-restart
    _start_thread("scalp_bot", scalp_alert_bot.main)
    _start_thread("swing", swing_bot.run_zenith_swing)
    _start_thread("telegram", scalp_alert_bot.run_telegram_worker)
    _start_thread("stock", stock_analyzer.stock_watchdog)
    _start_thread("commodities", commodities_bot.run_commodities_bot)

    # 4. Hilo principal para Flask (Keep-Alive)
    run_flask()
