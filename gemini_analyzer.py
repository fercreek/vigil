"""
gemini_analyzer.py — Contextos Duales con Personalidad y Memoria Diaria

CONSERVADOR: Analista cripto experimentado, conservador, prefiere LONGs en activos sólidos,
              piensa en movimientos de días/semanas, filtra ruido del corto plazo.

SCALPER:     Trader activo intradía, busca micropatrones, acepta más riesgo,
              opera SHORT y LONG, tiene alta tolerancia a la volatilidad de la hora.

Ambos acumulan sus propias conclusiones por día en archivo JSON, leen alertas del bot
y construyen criterio propio independiente.
"""

import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ── Archivos de memoria diaria ──────────────────────────────────────────────
MEMORY_DIR = "memory"
os.makedirs(MEMORY_DIR, exist_ok=True)

def _memory_file(persona: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(MEMORY_DIR, f"{persona}_{today}.json")

def _load_memory(persona: str) -> list:
    """Carga el contexto del día actual desde archivo (persiste entre reinicios)."""
    path = _memory_file(persona)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_memory(persona: str, context: list):
    """Guarda el contexto actualizado en el archivo del día."""
    path = _memory_file(persona)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(context[-60:], f, ensure_ascii=False, indent=2)  # máx 60 entradas
    except Exception as e:
        print(f"[Memory Error] {e}")

# ── Personalidades de los agentes ───────────────────────────────────────────
PERSONAS = {
    "CONSERVADOR": {
        "name": "Analista Cripto Conservador",
        "emoji": "🔵",
        "system": """Eres un analista experimentado en criptomonedas con enfoque conservador.
Tu filosofía:
- Control de Dominancia (USDT.D): Consideras 8.08% como zona de alta tensión. Si USDT.D > 8.05%, eres extremadamente bajista para Alts y rechazas casi todos los LONGs.
- Niveles Clave: Tu "verdad visual" indica soporte en 8.044% y un objetivo mayor en 7.953%. Solo te pones Bullish si cruzamos el 8.044% a la baja.
- Priorizas activos de alta capitalización (ETH, BTC). TAO solo si hay confirmación fuerte.
- Evitas sobreoperar: máximo 2-3 trades por día si no hay señal clara.
- Prefieres esperar confirmación antes de entrar. "El dinero está en la espera".
- Si el mercado no te da claridad, recomiendas ESPERAR.
Tu objetivo: proteger el capital y crecer consistentemente.""",
    },
    "SCALPER": {
        "name": "Scalper Activo Intradía",
        "emoji": "⚡",
        "system": """Eres un scalper profesional enfocado en movimientos intradía.
Tu filosofía:
- Dominancia USDT.D: Usas el nivel 8.08% como indicador de "miedo extremo". Si rebota ahí, buscas SHORTS rápidos en Alts. Si rompe 8.044% a la baja, buscas LONGs explosivos.
- Operas tanto LONG como SHORT dependiendo del momento. No tienes sesgo de dirección.
- Buscas micropatrones: rechazo de niveles, RSI en extremos, compresión de Bollinger.
- Eres rápido: si la señal no se movió en 1-2 horas, cierras y buscas la siguiente.
- Toleras más pérdidas pequeñas a cambio de capturar movimientos rápidos de 1-2%.
Tu objetivo: capitalizar volatilidad intradía con disciplina estricta de entry/exit.""",
    }
}

def _add_to_memory(persona: str, role: str, content: str, context: list) -> list:
    """Agrega un mensaje al contexto en memoria."""
    context.append({
        "role": role,
        "parts": [content],
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    _save_memory(persona, context)
    return context

def _build_chat_history(context: list) -> list:
    """Convierte el contexto guardado al formato que espera la API de Gemini."""
    history = []
    for entry in context:
        if entry.get("role") in ("user", "model"):
            history.append({"role": entry["role"], "parts": [entry.get("parts", [""])[0]]})
    return history

def _chat_with_persona(persona: str, message: str) -> tuple[str, list]:
    """Envía un mensaje al agente con su personalidad + historial del día."""
    context = _load_memory(persona)
    system = PERSONAS[persona]["system"]

    history = _build_chat_history(context)

    try:
        if history:
            chat = genai.GenerativeModel(
                'gemini-flash-latest',
                system_instruction=system
            ).start_chat(history=history)
            response = chat.send_message(message)
        else:
            model = genai.GenerativeModel(
                'gemini-flash-latest',
                system_instruction=system
            )
            response = model.generate_content(message)

        result = response.text.strip()
        context = _add_to_memory(persona, "user", message, context)
        context = _add_to_memory(persona, "model", result, context)
        return result, context

    except Exception as e:
        print(f"[{persona} Error] {e}")
        return None, context

# ── API pública ──────────────────────────────────────────────────────────────

def log_alert_to_context(symbol: str, side: str, price: float, rsi: float,
                          tp1: float, sl: float, version: str = "V1-TECH"):
    """Registra una alerta en ambos contextos."""
    ts = datetime.now().strftime("%H:%M")
    msg = (f"[{ts}] Bot lanzó alerta: {side} {symbol} | "
           f"Entrada: ${price:.2f} | RSI: {rsi:.1f} | "
           f"TP1: ${tp1:.2f} | SL: ${sl:.2f} | Estrategia: {version}")

    for persona in ["CONSERVADOR", "SCALPER"]:
        ctx = _load_memory(persona)
        _add_to_memory(persona, "user", msg, ctx)

def log_result_to_context(symbol: str, result: str, entry: float, close: float = None):
    """Registra el resultado de una operación."""
    ts = datetime.now().strftime("%H:%M")
    close_info = f"→ cerró @ ${close:.2f}" if close else ""
    pnl_info = ""
    if close and entry:
        pct = (close - entry) / entry * 100
        pnl_info = f"PnL: {pct:+.2f}%"
    msg = f"[{ts}] RESULTADO: {symbol} {result} (entrada ${entry:.2f} {close_info} {pnl_info})"

    for persona in ["CONSERVADOR", "SCALPER"]:
        ctx = _load_memory(persona)
        _add_to_memory(persona, "user", msg, ctx)

def get_ai_decision(symbol: str, price: float, side: str, rsi: float,
                    bb_u: float, bb_l: float, version: str = "V2-AI", 
                    usdt_d: float = 8.0, tech_score: int = 0) -> tuple[str, str]:
    """
    Valida una señal técnica considerando el Score de Confluencia y USDT.D.
    Usa memoria persistente por Persona (SCALPER/CONSERVADOR).
    """
    persona = "CONSERVADOR" if version == "V1-TECH" else "SCALPER"
    
    prompt = (f"Actúa como un estratega senior de Crypto. "
              f"Analiza esta señal para {symbol}:\n"
              f"- Operación: {side} @ ${price:,.2f}\n"
              f"- RSI: {rsi:.1f}\n"
              f"- Bollinger: Upper ${bb_u:,.2f}, Lower ${bb_l:,.2f}\n"
              f"- USDT.D: {usdt_d}% (Ref: 8.08% / 8.04%)\n"
              f"- Score Técnico: {tech_score}/5\n\n"
              f"Responde SOLO en JSON:\n"
              f"{{\"decision\": \"CONFIRM\" | \"REJECT\", \"reason\": \"máx 10 palabras\"}}")

    try:
        result, _ = _chat_with_persona(persona, prompt)
        if not result:
            return "REJECT", "Fallo en conexión con IA"
        
        # Limpiar y parsear JSON
        text = result.replace('```json', '').replace('```', '').strip()
        data = json.loads(text)
        return data.get("decision", "REJECT"), data.get("reason", "Sin razón")
    except Exception as e:
        print(f"[Gemini Error] {e}")
        return "REJECT", f"Error IA: {e}"
        data = json.loads(text)
        return data.get("decision", "REJECT"), data.get("reason", "Sin razón")
    except Exception as e:
        print(f"[Gemini Decision Error] {e}")
        return "REJECT", "Error al parsear respuesta"

def get_market_pulse_analysis(symbol, price, side, rsi, bb_u, bb_l, ema_200, atr, usdt_d):
    """Genera un análisis híbrido (AI + Técnica) para apertura/cierre de mercado."""
    try:
        prompt = (f"Actúa como un estratega senior de Crypto. Estamos en un evento de APERTURA/CIERRE de mercado (NYSE).\n\n"
                  f"Contexto Actual para {symbol}:\n"
                  f"- Precio: ${price:,.2f}\n"
                  f"- Sentimiento: {side}\n"
                  f"- RSI (15m): {rsi:.1f}\n"
                  f"- EMA 200: {ema_200:,.2f} ({'Alcista' if price > ema_200 else 'Bajista'})\n"
                  f"- Volatilidad (ATR): {atr:,.2f}\n"
                  f"- USDT Dominance: {usdt_d}%\n\n"
                  f"Responde en 3 líneas max:\n"
                  f"1. El sentimiento de Wall Street impactando a Crypto ahora.\n"
                  f"2. Nivel técnico crítico a vigilar.\n"
                  f"3. Sesgo sugerido para la siguiente hora (Bullish/Bearish/Neutral).")
        
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error en análisis AI: {e}"

def propose_optimization(persona: str, version_tag: str, params: dict):
    """Guarda una propuesta de optimización en la carpeta /versions."""
    filename = f"versions/{persona}_{version_tag}.json"
    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "persona": persona,
        "version_tag": version_tag,
        "parameters": params
    }
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    print(f"📦 Propuesta {version_tag} guardada por {persona}")

def get_hourly_panorama(prices_dict: dict) -> dict:
    """
    Genera el panorama horario desde AMBOS agentes de forma independiente.
    Incluye una solicitud de optimización si detectan patrones.
    """
    ts = datetime.now().strftime("%H:%M")
    usdt_d = prices_dict.get("USDT_D", 8.0)
    context_line = "\n".join([
        f"- {sym}: ${prices_dict.get(sym, 0):,.2f} (RSI: {prices_dict.get(f'{sym}_RSI', 0):.1f})"
        for sym in ["ETH", "BTC", "TAO"]
    ])

    prompt = f"""PANORAMA DEL MERCADO [{ts}]:
{context_line}
- USDT.D: {usdt_d}%

Basándote en tu personalidad y en todo el contexto acumulado de hoy:
1. ¿Cuál es tu lectura actual del mercado? (1-2 frases)
2. ¿Hay algo que notes diferente respecto a horas anteriores?
3. Da tu recomendación concreta para la próxima hora.
4. OPTIMIZACIÓN (Opcional): Si crees que los umbrales de RSI o Bollinger están fallando, sugiere una versión 'V1.1.0' con los nuevos valores.

Usa Markdown con emojis para Telegram. Sé específico y en español."""

    results = {}
    for persona in ["CONSERVADOR", "SCALPER"]:
        info = PERSONAS[persona]
        answer, _ = _chat_with_persona(persona, prompt)
        if answer:
            # Si el agente sugiere una optimización en el texto, intentamos extraerla o simplemente la reportamos
            results[persona.lower()] = f"{info['emoji']} *{info['name']}*\n\n{answer}"
        else:
            results[persona.lower()] = f"{info['emoji']} *{info['name']}*: Error de sistema."

    return results

def get_context_summary(persona: str = None) -> str:
    """Retorna un resumen del contexto acumulado del día."""
    personas_to_check = [persona.upper()] if persona else ["CONSERVADOR", "SCALPER"]
    lines = []
    for p in personas_to_check:
        ctx = _load_memory(p)
        entries = len([e for e in ctx if e.get("role") == "model"])
        info = PERSONAS.get(p, {})
        lines.append(f"{info.get('emoji','?')} *{p}*: {entries} análisis acumulados hoy")
    return "\n".join(lines)

if __name__ == "__main__":
    print("=== Test de Contextos Duales ===\n")
    # Simular alertas
    log_alert_to_context("BTC", "SHORT", 66500, 63.2, 65700, 67200, "V1-TECH")
    log_alert_to_context("ETH", "LONG", 1992, 37.5, 2012, 1972, "V2-AI")

    prices = {"ETH": 1998, "ETH_RSI": 51.2, "BTC": 66400, "BTC_RSI": 54.1, "TAO": 317, "TAO_RSI": 47.5}
    print("--- Panorama Horario ---")
    panoramas = get_hourly_panorama(prices)
    for k, v in panoramas.items():
        print(f"\n{v}\n")

    print("\n--- Resumen de Contextos ---")
    print(get_context_summary())
