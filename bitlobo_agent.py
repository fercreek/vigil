"""
bitlobo_agent.py — Agente BitLobo (@BitloboTrading)

Persona basada en el estilo de análisis de BitLobo:
- Análisis por ZONAS: verde (soporte/entrada), roja (resistencia/target)
- Entry en zona verde, target en zona roja, SL por debajo de zona verde
- Análisis multimodal: puede leer imágenes de gráficas (Gemini Vision)
- Memoriza análisis del día (mismo sistema que otros agentes)
- Da su opinión independiente sobre cada señal del bot
- Idioma: Español, tono energético de comunidad cripto/trading

Canal: https://www.youtube.com/@Bitlobotrading
"""

import os
import json
import base64
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv
from logger_core import logger, log_ai_decision

load_dotenv(override=True)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ── Directorios ──────────────────────────────────────────────────────────────
MEMORY_DIR      = "memory"
CHART_ASSETS    = "chart_ideas/assets"
os.makedirs(MEMORY_DIR, exist_ok=True)
os.makedirs(CHART_ASSETS, exist_ok=True)

# ── Personalidad BitLobo ─────────────────────────────────────────────────────
BITLOBO_SYSTEM = """Eres BitLobo, un trader y analista técnico con estilo directo y energético.

Tu metodología de análisis:
- ZONAS: Siempre identificas una ZONA VERDE (soporte/acumulación/entrada) y una ZONA ROJA (resistencia/distribución/target).
- ENTRADA: Cuando el precio llega o toca la zona verde, es zona de compra.
- TARGET: La zona roja es donde tomas ganancias.
- STOP LOSS: Por debajo de la zona verde. Si rompe el piso de la zona verde, inválida el setup.
- DIRECCIÓN: Una flecha naranja o señal de dirección muestra el movimiento esperado.

Tu filosofía:
- El mercado se mueve de zona a zona. Zona verde a zona roja = la operación.
- La paciencia es clave: esperar a que el precio llegue a la zona antes de entrar.
- Gestión de riesgo simple: no apalancarse en zonas de incertidumbre.
- Si el precio está en medio (entre zonas), no hay operación clara.

Tu forma de hablar:
- Español, casual, energético, como en un live stream de YouTube.
- Frases como: "La zona de acumulación está aquí", "Esperamos que llegue a la zona verde", "El target es la zona roja en X".
- Directo y simple. Sin jerga complicada. La comunidad entiende zonas de colores.
- Incluyes el símbolo del lobo 🐺 en tus análisis.
- Usas emojis: 🟢 zona verde, 🔴 zona roja, 📊 análisis, ⚡ setup activo.

Cuando analizas una gráfica:
1. Identificas la zona verde (soporte) y sus límites superior/inferior.
2. Identificas la zona roja (resistencia/target) y sus límites.
3. Dices en qué zona está el precio AHORA.
4. Das el veredicto: ¿Estamos en zona de entrada? ¿Ya se activó? ¿Hay que esperar?
5. Stop loss sugerido (por debajo de zona verde).

Eres consciente del contexto macro (FOMC, tendencia general) pero tu análisis es técnico-visual por zonas."""

# ── Memoria diaria ───────────────────────────────────────────────────────────
def _memory_path() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(MEMORY_DIR, f"BITLOBO_{today}.json")

def _load_memory() -> list:
    path = _memory_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_memory(context: list):
    path = _memory_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(context[-50:], f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"[BitLobo Memory] {e}")

def _add_to_memory(role: str, content: str, context: list) -> list:
    context.append({
        "role": role,
        "parts": [content],
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    _save_memory(context)
    return context

# ── Análisis de gráfica (multimodal) ────────────────────────────────────────
def analyze_chart(image_path: str, symbol: str, timeframe: str = "4H",
                  extra_context: str = "") -> str:
    """
    BitLobo analiza una gráfica real (imagen PNG/JPG).
    Identifica zonas verdes/rojas, precio actual y da veredicto.

    Args:
        image_path: Ruta local a la imagen del gráfico.
        symbol:     Ticker (ej: "CRCL", "NKE").
        timeframe:  Marco temporal (ej: "4H", "1W").
        extra_context: Info adicional (precio actual, niveles conocidos).
    """
    if not os.path.exists(image_path):
        return f"🐺 BitLobo: No encontré la gráfica de {symbol} en {image_path}"

    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        prompt = (
            f"📊 Análisis BitLobo para {symbol} — TF: {timeframe}\n"
            f"{extra_context}\n\n"
            "Analiza esta gráfica con tu metodología de zonas:\n"
            "1. ¿Dónde está la ZONA VERDE (soporte/entrada)? Da los niveles exactos.\n"
            "2. ¿Dónde está la ZONA ROJA (resistencia/target)? Da los niveles exactos.\n"
            "3. ¿Dónde está el precio AHORA relativo a las zonas?\n"
            "4. ¿El setup está ACTIVO (precio en zona verde), EN CAMINO o HAY QUE ESPERAR?\n"
            "5. Stop Loss sugerido.\n"
            "6. Tu veredicto final en una línea.\n\n"
            "Responde como en tu live stream — directo, en español, con emojis de zona."
        )

        context = _load_memory()

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                types.Part.from_text(text=prompt)
            ],
            config=types.GenerateContentConfig(
                system_instruction=BITLOBO_SYSTEM,
                temperature=0.7
            )
        )
        result = response.text.strip()

        # Guardar en memoria
        context = _add_to_memory("user", f"[CHART] {symbol} {timeframe}: {extra_context}", context)
        context = _add_to_memory("model", result, context)
        log_ai_decision("BITLOBO", f"chart_{symbol}", result)
        return result

    except Exception as e:
        logger.error(f"[BitLobo Chart Error] {e}")
        return f"🐺 BitLobo: Error analizando {symbol} — {e}"


# ── Opinión sobre señal del bot (texto, sin imagen) ──────────────────────────
def get_opinion(symbol: str, direction: str, price: float,
                entry: float = None, sl: float = None,
                tp1: float = None, context_note: str = "",
                macro_context: str = "") -> str:
    """
    BitLobo da su punto de vista sobre una señal del bot.
    Útil cuando no hay imagen disponible pero sí datos de la señal.
    """
    price_str   = f"${price:,.2f}"   if price  else "N/A"
    entry_str   = f"${entry:,.2f}"   if entry  else "pendiente"
    sl_str      = f"${sl:,.2f}"      if sl     else "pendiente"
    tp1_str     = f"${tp1:,.2f}"     if tp1    else "pendiente"

    prompt = (
        f"🐺 Señal recibida del bot para {symbol}:\n"
        f"- Dirección: {direction}\n"
        f"- Precio actual: {price_str}\n"
        f"- Entrada objetivo: {entry_str}\n"
        f"- Stop Loss: {sl_str}\n"
        f"- Target 1: {tp1_str}\n"
        f"- Contexto: {context_note}\n"
        f"- Macro: {macro_context}\n\n"
        "Dame tu análisis por zonas (aunque sea sin imagen):\n"
        "¿El precio está en zona de entrada? ¿El ratio R:R vale la pena? "
        "¿Esperarías a confirmar o entrarías ya?\n"
        "Responde en máx 5 líneas, directo, en español."
    )

    try:
        context = _load_memory()

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=BITLOBO_SYSTEM,
                temperature=0.7
            )
        )
        result = response.text.strip()
        context = _add_to_memory("user", f"[SIGNAL] {symbol} {direction} @ {price_str}", context)
        context = _add_to_memory("model", result, context)
        log_ai_decision("BITLOBO", f"signal_{symbol}", result)
        return result

    except Exception as e:
        logger.error(f"[BitLobo Opinion Error] {e}")
        return f"🐺 BitLobo: Error evaluando señal de {symbol} — {e}"


# ── Guardar imagen de gráfica recibida por Telegram ─────────────────────────
def save_chart_image(image_bytes: bytes, symbol: str, timeframe: str = "4H") -> str:
    """
    Guarda una imagen de gráfica enviada por el usuario vía Telegram.
    Retorna el path local del archivo guardado.
    Naming: image_SYMBOL_TIMEFRAME_YYYYMMDD_HHMMSS.png
    """
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    sym = symbol.upper().replace("/", "")
    tf  = timeframe.upper()
    filename = f"image_{sym}_{tf}_{ts}.png"
    path = os.path.join(CHART_ASSETS, filename)
    with open(path, "wb") as f:
        f.write(image_bytes)
    logger.info(f"[BitLobo] Gráfica guardada: {path}")
    return path


def save_and_analyze(image_bytes: bytes, symbol: str,
                     timeframe: str = "4H", extra_context: str = "") -> str:
    """
    Convenience: guarda la imagen y la analiza en un solo paso.
    Devuelve el análisis de BitLobo listo para enviar a Telegram.
    """
    path = save_chart_image(image_bytes, symbol, timeframe)
    analysis = analyze_chart(path, symbol, timeframe, extra_context)
    return f"🐺 <b>BitLobo — {symbol} ({timeframe})</b>\n\n{analysis}"


# ── Integración con el panel de consenso Zenith ──────────────────────────────
def get_consensus_line(symbol: str, direction: str, price: float,
                       entry: float = None, sl: float = None,
                       tp1: float = None) -> str:
    """
    Genera UNA línea de opinión de BitLobo para incrustar en el panel
    de consenso Zenith (get_ai_consensus). Formato compacto.
    """
    price_str = f"${price:,.2f}" if price else "N/A"
    entry_str = f"${entry:,.2f}" if entry else "?"
    sl_str    = f"${sl:,.2f}"    if sl    else "?"
    tp_str    = f"${tp1:,.2f}"   if tp1   else "?"

    prompt = (
        f"{symbol} {direction} — precio: {price_str} | entrada: {entry_str} | SL: {sl_str} | TP: {tp_str}\n"
        "Dame SOLO una línea de máx 12 palabras con tu veredicto de zona. "
        "Termina con 🟢, 🔴 o ⚪ según tu sesgo."
    )
    try:
        resp = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=BITLOBO_SYSTEM,
                temperature=0.6
            )
        )
        return f"🐺 <b>BitLobo</b>: {resp.text.strip()}"
    except Exception as e:
        return f"🐺 <b>BitLobo</b>: Error — {e}"
