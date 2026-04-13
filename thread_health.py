"""
thread_health.py — Watchdog interno para hilos del bot.

Módulo standalone (sin imports del bot) para evitar circularidad.
Cada hilo llama heartbeat("nombre") en su loop.
El watchdog detecta hilos sin heartbeat >5 min y los reinicia.
"""

import threading
import time
import os
import requests
import logging

logger = logging.getLogger("ScalpBot")

WATCHDOG_INTERVAL = 120      # Revisar cada 2 minutos
HEARTBEAT_TIMEOUT = 300      # 5 minutos sin heartbeat = muerto

# --- Estado compartido (thread-safe) ---
_heartbeats = {}             # {name: timestamp}
_lock = threading.Lock()
_restart_callbacks = {}      # {name: callable}
_restart_counts = {}         # {name: int}
MAX_RESTARTS = 10

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def heartbeat(name: str):
    """Llamar al inicio de cada iteración del loop principal."""
    with _lock:
        _heartbeats[name] = time.time()


def get_status() -> dict:
    """Retorna estado de cada hilo registrado."""
    with _lock:
        now = time.time()
        return {
            k: {
                "last_beat": v,
                "age_seconds": round(now - v),
                "alive": (now - v) < HEARTBEAT_TIMEOUT,
            }
            for k, v in _heartbeats.items()
        }


def register(name: str, callback):
    """Registra un callback para reiniciar un hilo por nombre."""
    with _lock:
        _restart_callbacks[name] = callback
        _restart_counts[name] = 0


def notify(name: str, event: str, detail: str = ""):
    """Envía notificación Telegram sobre estado de hilo."""
    token = TELEGRAM_TOKEN or os.getenv("TELEGRAM_TOKEN")
    chat_id = TELEGRAM_CHAT_ID or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    msg = f"🛡️ <b>WATCHDOG [{event}]</b>\nHilo: <code>{name}</code>"
    if detail:
        msg += f"\nDetalle: {detail[:200]}"
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass


def _watchdog_loop():
    """Loop del watchdog — revisa heartbeats y reinicia hilos muertos."""
    logger.info("🛡️ Watchdog: Iniciado — revisando heartbeats cada %ds", WATCHDOG_INTERVAL)
    while True:
        time.sleep(WATCHDOG_INTERVAL)
        now = time.time()
        with _lock:
            for name, last_beat in list(_heartbeats.items()):
                age = now - last_beat
                if age > HEARTBEAT_TIMEOUT:
                    count = _restart_counts.get(name, 0)
                    if count >= MAX_RESTARTS:
                        logger.critical(
                            "🛡️ Watchdog: Hilo '%s' agotó reintentos (%d/%d)",
                            name, count, MAX_RESTARTS,
                        )
                        continue

                    logger.warning(
                        "🛡️ Watchdog: Hilo '%s' sin heartbeat hace %ds — reiniciando (%d/%d)",
                        name, int(age), count + 1, MAX_RESTARTS,
                    )
                    callback = _restart_callbacks.get(name)
                    if callback:
                        _restart_counts[name] = count + 1
                        # Reset heartbeat para evitar reinicio doble
                        _heartbeats[name] = now
                        try:
                            notify(name, "RESTART", f"Sin heartbeat hace {int(age)}s (intento {count + 1})")
                            callback()
                        except Exception as e:
                            logger.error("🛡️ Watchdog: Error reiniciando '%s': %s", name, e)
                    else:
                        logger.warning("🛡️ Watchdog: No hay callback de restart para '%s'", name)


def start_watchdog():
    """Arranca el hilo watchdog (llamar una vez desde main.py)."""
    t = threading.Thread(target=_watchdog_loop, daemon=True, name="watchdog")
    t.start()
    return t
