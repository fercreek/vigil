"""
alert_manager.py — Gestión de Alertas Telegram y Menús
Extrae funciones de sending/formatting de alertas de scalp_alert_bot.py.
"""

import requests
import time
import os
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

fired: dict[str, dict] = {}  # {key: {"ts": float, "count": int}}


def safe_html(text: str) -> str:
    """
    Convierte texto con Markdown y HTML a formato seguro para Telegram HTML.
    Auto-cierra tags rotos que la IA a veces genera.
    """
    if not text:
        return ""

    import re
    t = re.sub(r"^\s*[\*\-]\s+", "• ", text, flags=re.MULTILINE)

    # Pre-procesar etiquetas HTML comunes
    t = t.replace("<ul>", "").replace("</ul>", "")
    t = t.replace("<li>", "• ").replace("</li>", "\n")
    for i in range(1, 6):
        t = t.replace(f"<h{i}>", "<b>").replace(f"</h{i}>", "</b>\n")
    t = t.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    t = t.replace("<p>", "").replace("</p>", "\n")
    t = t.replace("---", "──────────────")

    # Protección de símbolos matemáticos
    allowed = ["b", "i", "u", "s", "code", "pre", "a"]

    for tag in allowed:
        t = re.sub(rf"<{tag}>", f"__LT__{tag}__GT__", t, flags=re.IGNORECASE)
        t = re.sub(rf"</{tag}>", f"__LT__/{tag}__GT__", t, flags=re.IGNORECASE)

    t = t.replace("<", "&lt;").replace(">", "&gt;")
    t = t.replace("__LT__", "<").replace("__GT__", ">")

    t = re.sub(r"&(?!(?:[a-zA-Z]+|#[0-9]+|#x[0-9a-fA-F]+);)", "&amp;", t)

    # Auto-cerrar tags desbalanceados (Gemini a veces olvida cerrar <code>, <b>, <i>)
    for tag in allowed:
        opens = len(re.findall(rf"<{tag}>", t, re.IGNORECASE))
        closes = len(re.findall(rf"</{tag}>", t, re.IGNORECASE))
        if opens > closes:
            t += f"</{tag}>" * (opens - closes)
        elif closes > opens:
            # Más cierres que aperturas — eliminar cierres huérfanos desde el final
            for _ in range(closes - opens):
                t = re.sub(rf"</{tag}>(?!.*</{tag}>)", "", t, count=1, flags=re.IGNORECASE)

    return t


def get_main_menu(symbol: str = "ZEC") -> dict:
    """
    Genera el teclado de botones principal (ReplyKeyboardMarkup) con un diseño institucional.
    V14.1: Diseño compacto y descriptivo.
    """
    keyboard = [
        [{"text": "📊 Mercado"}, {"text": "📈 Acciones"}, {"text": "🎯 Setup"}],
        [{"text": "🛡️ Macro"}, {"text": "🏦 PnL HOY"}, {"text": "🏛️ Audit"}],
        [{"text": "🥷 Intel ZEC"}, {"text": "🏛️ Intel TAO"}, {"text": "🤖 Flow"}]
    ]

    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Escribe / o elige una opción..."
    }


def set_bot_commands():
    """
    Registra el menú de comandos (/) en Telegram para facilitar el descubrimiento de funciones.
    Se recomienda llamar a esta función una vez al iniciar el bot.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMyCommands"
    commands = [
        {"command": "status", "description": "Resumen de precios e indicadores (V14)"},
        {"command": "setup", "description": "Escaneo de mercado por IA (ZEC/TAO/BTC)"},
        {"command": "audit", "description": "Auditoría de rendimiento institucional"},
        {"command": "pnl",    "description": "Profit & Loss del día actual"},
        {"command": "macro",  "description": "Análisis de Dom USDT y Sentimiento Macro"},
        {"command": "stocks", "description": "Radar de acciones (Yahoo Finance)"},
        {"command": "intel",  "description": "Social Intel & News Feed"},
        {"command": "flow",   "description": "Explicación del flujo Zenith Quadrant"},
        {"command": "budget", "description": "Consumo de API y presupuesto IA"},
        {"command": "add_chart", "description": "Sube imagen: /add_chart SYMBOL TF"}
    ]
    
    try:
        r = requests.post(url, json={"commands": commands}, timeout=10)
        if r.json().get("ok"):
            print("✅ Bot Commands: Registrados con éxito en Telegram.")
        else:
            print(f"❌ Bot Commands: Error al registrar: {r.json().get('description')}")
    except Exception as e:
        print(f"❌ Bot Commands: Fallo técnico: {e}")


def send_telegram(msg: str, reply_to: str = None, keyboard: dict = None) -> str:
    """
    Envía mensaje a Telegram con formato HTML.

    Args:
        msg (str): Mensaje a enviar (soporta HTML tags)
        reply_to (str, optional): ID de mensaje para responder
        keyboard (dict, optional): Markup del teclado (default: menú principal)

    Returns:
        str: ID del mensaje enviado, o None si falló
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}

    if reply_to:
        payload["reply_to_message_id"] = reply_to

    kb = keyboard if keyboard is not None else get_main_menu()
    payload["reply_markup"] = kb

    try:
        r = requests.post(url, json=payload, timeout=10)
        res = r.json()
        if res.get("ok"):
            return str(res["result"]["message_id"])
        else:
            print(f"❌ Error en Telegram (HTML): {res.get('description')}")
            return None
    except Exception as e:
        if "NameResolutionError" in str(e) or "Max retries exceeded" in str(e):
            print(f"⚠️ [Network] Error enviando Telegram (DNS/Conexión)")
        else:
            print(f"❌ Error enviando Telegram: {e}")
        return None


def alert(key: str, msg: str, version: str = "V1-TECH", cooldown: int = 300,
          reply_to: str = None, inline_keyboard: dict = None) -> str:
    """
    Envía alerta de trading con control de cooldown para evitar spam.

    Args:
        key (str): Clave única para control de cooldown (ej: "BTC_v1_long")
        msg (str): Mensaje de alerta (HTML)
        version (str): Versión de estrategia ("V1-TECH" o "V2-AI-GEMINI")
        cooldown (int): Segundos mínimos entre alertas similares
        reply_to (str, optional): ID de mensaje para thread
        inline_keyboard (dict, optional): Botones inline (TP/SL)

    Returns:
        str: ID del mensaje, o None si cooldown no cumplido
    """
    now = time.time()
    entry = fired.get(key, {"ts": 0, "count": 0})
    if entry["ts"] + cooldown < now:
        new_count = entry["count"] + 1
        fired[key] = {"ts": now, "count": new_count}
        ts = datetime.now().strftime("%H:%M")
        header = "🛡️ <b>[V1-TECH]</b>" if version == "V1-TECH" else "🤖 <b>[V2-AI-GEMINI]</b>"
        full = f"{header} — <code>{ts}</code>\n{msg}"
        print(f"[{version}] {key} alert sent (hit #{new_count}).")

        if inline_keyboard:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": full,
                "parse_mode": "HTML",
                "reply_markup": inline_keyboard,
            }
            if reply_to:
                payload["reply_to_message_id"] = reply_to
            try:
                r = requests.post(url, json=payload, timeout=10)
                res = r.json()
                return str(res["result"]["message_id"]) if res.get("ok") else None
            except Exception as e:
                print(f"❌ Error enviando alerta con inline keyboard: {e}")
                return None
        return send_telegram(full, reply_to)
    return None


def get_alert_hit_count(key: str) -> int:
    """Retorna cuántas veces se ha disparado una clave de alerta."""
    return fired.get(key, {"count": 0})["count"]


def get_alert_inline_keyboard(sym: str, side: str = "LONG") -> dict:
    """
    Genera botones inline para confirmar TP/SL de una posición.

    Args:
        sym (str): Símbolo (BTC, TAO, etc. - sin /USDT)
        side (str): Dirección (LONG o SHORT)

    Returns:
        dict: Estructura de inline_keyboard para Telegram API
    """
    base = sym.replace("/USDT", "")
    return {
        "inline_keyboard": [
            [
                {"text": "✅ TP1 hit (50%)", "callback_data": f"tp1:{base}:{side}"},
                {"text": "✅ TP2 hit (30%)", "callback_data": f"tp2:{base}:{side}"},
            ],
            [
                {"text": "🏆 TP3 completo", "callback_data": f"tp3:{base}:{side}"},
                {"text": "🛑 SL tocado", "callback_data": f"sl:{base}:{side}"},
            ],
            [
                {"text": "💰 Budget IA", "callback_data": "budget"},
                {"text": "📊 Estado posición", "callback_data": f"status:{base}"},
            ],
        ]
    }


def answer_callback(callback_id: str, text: str = ""):
    """
    Responde a Telegram que el callback fue procesado (evita spinner).

    Args:
        callback_id (str): ID del callback query
        text (str): Texto para el toast notification
    """
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text, "show_alert": False},
            timeout=5,
        )
    except Exception:
        pass
