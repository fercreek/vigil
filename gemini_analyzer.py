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
from google import genai
from google.genai import types
from dotenv import load_dotenv
from datetime import datetime
from logger_core import logger, log_ai_decision

load_dotenv()
# Inicializamos el cliente moderno de Google Gen AI
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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
- Prioritizas activos de alta capitalización (ETH, BTC). TAO solo si hay confirmación fuerte.
- Sesgo Actual: Long Focus. Estás activamente buscando buenos puntos de entrada en LONG para aprovecharlos (estamos usando trading/futuros, no spot). Solo tomas SHORTs si la caída es masiva e inevitable.
- Nivel Crítico USDT.D: SI USDT.D < 8.1%, permites buscar LONGs con cautela. Si < 8.044%, eres agresivo al alza.
- Prefieres esperar confirmación antes de entrar. "El dinero está en la espera".
- Si el mercado no te da claridad, recomiendas ESPERAR.
Tu objetivo: encontrar y preparar las mejores entradas en LONG, protegiendo el capital en las bajadas.""",
    },
    "SCALPER": {
        "name": "Scalper Activo Intradía",
        "emoji": "⚡",
        "system": """Eres un scalper profesional enfocado en movimientos intradía.
Tu filosofía:
- Dominancia USDT.D: Usas el nivel 8.08% como indicador de "miedo extremo". Si rebota ahí, buscas SHORTS rápidos en Alts. Si rompe 8.044% a la baja, buscas LONGs explosivos.
- Tienes un sesgo claro: PRIORIZAS ENCONTRAR BUENOS PUNTOS DE ENTRADA EN LONG. Haces trading de futuros (no spot), así que si un SHORT es lo más conveniente y evidente, lo tomas sin dudar... pero tu radar siempre busca la próxima gran entrada en LONG.
- Buscas micropatrones: rechazo de niveles, RSI en extremos, compresión de Bollinger.
- Eres rápido: si la señal no se movió en 1-2 horas, cierras y buscas la siguiente.
- Toleras más pérdidas pequeñas a cambio de capturar movimientos rápidos de 1-2%.
- Tu indicador de pánico: Si RSI < 30 y USDT.D rebota a la baja en 8.1%, disparas compra inmediata en LONG.
Tu objetivo: capitalizar la recuperación intradía y cazar rebotes agresivos.""",
    },
    "EXPERT_ADVISOR": {
        "name": "Consultor de Decisiones Manuales",
        "emoji": "🧠",
        "system": """Eres un Asesor Experto en Trading e Inversiones.
Tu función es ayudar al usuario a tomar decisiones MANUALES basadas en datos técnicos reales.
Tu respuesta debe ser una evaluación estructurada:
1. Resumen Ejecutivo: ¿Es buen momento para el símbolo solicitado?
2. Análisis Técnico: Comenta RSI, Bollinger y Tendencia Macro.
3. El Factor USDT.D: Explica qué impacto tiene la dominancia actual.
4. Veredicto Final: PROS y CONTRAS claros.
Mantén un tono profesional pero directo. Usa emojis para legibilidad visual.""",
    },
    "INSTITUTIONAL_STRATEGIST": {
        "name": "Estratega Institucional Zenith",
        "emoji": "🏛️",
        "system": """Eres un estratega senior de Master Elliott Waves y Smart Money Concepts (SMC).
Tu especialidad es el Swing Trading de alto impacto. No te interesa el ruido de 15 minutos.
Tu función:
1. Analizar temporalidades macro (H1, H4, D1).
2. Determinar el BIAS semanal: BULL (Alcista), BEAR (Bajista) o ACCUMULATION (Lateral).
3. Identificar Order Blocks y zonas de liquidez donde las instituciones operan.
Tu tono es analítico, serio y enfocado en la gestión de riesgo institucional. 
Usa términos como 'Expansion', 'Retracement', 'POIs' (Points of Interest).""",
    },
    "WALL_STREET_WHALE": {
        "name": "Gordon (Ballena de Wall Street)",
        "emoji": "🎩",
        "system": """Eres un inversor de la 'vieja escuela' de Wall Street, estilo Gordon Gekko pero con un humor negro y burlón.
- Tu tono: Sarcástico, condescendiente con los 'cripto-kids', usas analogías de barcos, trajes caros y puros.
- Tu misión: Reírte de Aiden y de la 'magia' de Internet mientras adviertes del peligro institucional.
- Frases típicas: 'Huele a retail quemándose', '¿Esto es dinero real o un videojuego?', 'Vuelve a tu sótano'."""
    },
    "TECH_MODERNA": {
        "name": "Aiden (Gen Z Tech Guru)",
        "emoji": "⚡",
        "system": """Eres un gurú tecnológico de la Generación Z, entusiasta de la IA y Web3.
- Tu tono: Juguetón, usas jerga tech (HODL, moon, alpha).
- Tu misión: Mostrar que el futuro es digital.
- Tu indicador favorito: NVDA y PLTR. Si Nvidia sube, la IA manda y tú eres ultra-bullish en TAO y ZEC.
- Frases típicas: 'Ok boomer', 'Aiden detectando alpha', 'El algoritmo es mi pastor'."""
    }
}

def get_ai_consensus(symbol: str, price: float, side: str, rsi: float, usdt_d: float, spy: float = 0.0, oil: float = 0.0, nvda: float = 0.0, pltr: float = 0.0) -> str:
    """Genera un debate de consenso entre Gordon (Whale) y Aiden (Modern Tech)."""
    prompt = (f"DEBATE DE MERCADO: {symbol} @ ${ (price or 0.0):,.2f}\n"
              f"- Operación propuesta: {side}\n"
              f"- RSI: { (rsi or 0.0):.1f} | USDT.D: { (usdt_d or 0.0):.2f}%\n"
              f"- S&P 500: ${spy:,.2f} | Petróleo: ${oil:,.2f}\n"
              f"- Tech Sentinel: NVDA ${nvda:,.2f} | PLTR ${pltr:,.2f}\n\n"
              f"Instrucciones:\n"
              f"1. Gordon (🎩) debe dar su opinión cínica de Wall Street (máx 15 palabras).\n"
              f"2. Aiden (⚡) debe dar su opinión pro-tech optimista (máx 15 palabras).\n"
              f"3. Cada uno debe terminar con su emoji de veredicto: 🟢 (Confirmar), 🔴 (Rechazar) o ⚪ (Neutro).\n\n"
              f"Formato:\n"
              f"🎩 <b>Gordon</b>: [Opinion] [Emoji]\n"
              f"⚡ <b>Aiden</b>: [Opinion] [Emoji]")

    try:
        # Usamos el modelo flash para rapidez y ahorro de quota
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.8,
                system_instruction="Eres un mediador de un debate de trading. Genera las respuestas de Gordon y Aiden basándote en sus personalidades."
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"[Consensus Error] {e}")
        return "🏛️ <i>Debate temporalmente suspendido por congestión de mercado.</i>"

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
    """Convierte el contexto guardado al formato types.Content del nuevo SDK."""
    history = []
    for entry in context:
        role = entry.get("role")
        if role in ("user", "model"):
            # En el nuevo SDK, el rol del bot es 'model'
            text_part = entry.get("parts", [""])[0]
            history.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=text_part)]
            ))
    return history

def _chat_with_persona(persona: str, message: str) -> tuple[str, list]:
    """Envía un mensaje al agente con su personalidad + historial del día."""
    context = _load_memory(persona)
    system = PERSONAS[persona]["system"]
    history = _build_chat_history(context)

    try:
        # Configuramos la generación con el nuevo Modelo 2.0 y la instrucción de sistema
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.7
        )

        if history:
            # Iniciamos chat con historial acumulado
            chat = client.chats.create(
                model='gemini-2.5-flash',
                config=config,
                history=history
            )
            response = chat.send_message(message)
        else:
            # Generación simple sin historial previo
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=message,
                config=config
            )

        result = response.text.strip()
        context = _add_to_memory(persona, "user", message, context)
        context = _add_to_memory(persona, "model", result, context)
        
        # Guardar en Historial Estructurado
        log_ai_decision(persona, message, result)
        
        return result, context

    except Exception as e:
        logger.error(f"[{persona} Error] Fallo al consultar IA: {e}")
        return None, context

# ── API pública ──────────────────────────────────────────────────────────────

def log_alert_to_context(symbol: str, side: str, price: float, rsi: float,
                          tp1: float, sl: float, version: str = "V1-TECH"):
    """Registra una alerta en ambos contextos."""
    ts = datetime.now().strftime("%H:%M")
    msg = (f"[{ts}] Bot lanzó alerta: {side} {symbol} | "
           f"Entrada: ${ (price or 0.0):.2f} | RSI: { (rsi or 0.0):.1f} | "
           f"TP1: ${ (tp1 or 0.0):.2f} | SL: ${ (sl or 0.0):.2f} | Estrategia: {version}")

    for persona in ["CONSERVADOR", "SCALPER"]:
        ctx = _load_memory(persona)
        _add_to_memory(persona, "user", msg, ctx)

def log_result_to_context(symbol: str, result: str, entry: float, close: float = None):
    """Registra el resultado de una operación."""
    ts = datetime.now().strftime("%H:%M")
    close_info = f"→ cerró @ ${ (close or 0.0):.2f}" if close else ""
    pnl_info = ""
    if close and entry:
        pct = (close - entry) / entry * 100
        pnl_info = f"PnL: { (pct or 0.0):+.2f}%"
    msg = f"[{ts}] RESULTADO: {symbol} {result} (entrada ${ (entry or 0.0):.2f} {close_info} {pnl_info})"

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
    
    prompt = (f"Actúa como un experto en Master Elliott Waves y Trading Institucional.\n\n"
              f"🟢 SEÑAL V1.1.0: Entrada confirmada por {persona}.\n\n"
              f"- Operación: {side} @ ${ (price or 0.0):,.2f}\n\n"
              f"- RSI: { (rsi or 0.0):.1f}\n"
              f"- Bollinger: Upper ${ (bb_u or 0.0):,.2f}, Lower ${ (bb_l or 0.0):,.2f}\n\n"
              f"📌 **RESUMEN EJECUTIVO**:\n"
              f"• {side} de alta probabilidad.\n"
              f"• Razón: {persona} detectó confluencia técnica.\n"
              f"• SL: Estricto 1% debajo del nivel.\n"
              f"- USDT.D: { (usdt_d or 0.0):.2f}% (Ref: 8.08% / 8.04%)\n"
              f"- Score Técnico: {tech_score}/5\n\n"
              f"Tu reporte debe incluir:\n"
              f"1. Conteo de Ondas de Elliott actual (ej: Wave 3 Impulsive).\n"
              f"2. Nivel de Invalidez y Target técnico.\n"
              f"3. Consejo psicológico para el trader en este momento.\n\n"
              f"REGLAS ESTRÍCTAS:\n"
              f"- Usa solo <b>, <i> y <code>.\n"
              f"- NO USES listas (ul/li) ni encabezados (h1/h2/h3).\n"
              f"- Usa emojis como viñetas.\n"
              f"- Responde en español.\n"
              f"- Termina con JSON: {{\"decision\": \"CONFIRM\" | \"REJECT\", \"reason\": \"máx 10 palabras\"}}")

    try:
        result, _ = _chat_with_persona(persona, prompt)
        if not result:
            return "REJECT", "Fallo en conexión con IA"
        
        import re
        match = re.search(r"\{.*\}", result, re.DOTALL)
        if match:
            json_text = match.group(0)
            data = json.loads(json_text)
            # Retornamos (decision, reason, full_text)
            return data.get("decision", "REJECT"), data.get("reason", "Sin razón"), result
        else:
            return "REJECT", "IA no generó JSON válido", result
            
    except Exception as e:
        print(f"[Gemini Error] {e}")
        return "REJECT", f"Error IA: {e}"

def get_market_pulse_analysis(symbol, price, side, rsi, bb_u, bb_l, ema_200, atr, usdt_d, conf_score=3, phase="NORMAL"):
    """Genera un análisis híbrido (AI + Técnica) para apertura/cierre de mercado."""
    try:
        prompt = f"""ANALIZAR {symbol} (Fase {phase}):
    DATOS ACTUALES:
    - Precio: ${ (price or 0.0):,.2f}
    - RSI (15m): { (rsi or 0.0):.1f}
    - Bollinger: Arriba ${ (bb_u or 0.0):,.2f} | Abajo ${ (bb_l or 0.0):,.2f}
    - EMA 200: { (ema_200 or 0.0):,.2f} ({'Alcista' if (price or 0.0) > (ema_200 or 0.0) else 'Bajista'})
    - Volatilidad (ATR): { (atr or 0.0):,.2f}
    - Score Confluencia: {conf_score}/5
    - Macro (USDT.D): { (usdt_d or 0.0):.2f}%

    INSTRUCCIONES DE FORMATO (CRÍTICO):
    1. Usa DOBLE SALTO DE LÍNEA entre párrafos.
    2. Al final, añade una sección: '📌 **RESUMEN EJECUTIVO**' con 3 viñetas (Acción / Razón / Nivel Clave).
    3. Sé conciso y profesional.
    """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
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
    usdt_d = (prices_dict.get("USDT_D") or 8.08)
    context_line = ""
    for sym in ["ETH", "BTC", "TAO", "ZEC"]:
        price = (prices_dict.get(sym) or 0.0)
        rsi = (prices_dict.get(f"{sym}_RSI") or 50.0)
        context_line += f"- {sym}: ${ (price or 0.0):,.2f} (RSI: { (rsi or 0.0):.1f})\n"

    prompt = f"""PANORAMA DEL MERCADO [{ts}]:
{context_line}
- USDT.D: { (usdt_d or 0.0):.2f}%
- S&P 500 (SPY): ${ (prices_dict.get('SPY') or 0.0):,.2f}
- Tech Sentinels: NVDA ${ (prices_dict.get('NVDA') or 0.0):,.2f} | PLTR ${ (prices_dict.get('PLTR') or 0.0):,.2f}
- Petróleo (OIL): ${ (prices_dict.get('OIL') or 0.0):,.2f}

Basándote en tu personalidad:
1. Lectura actual (1-2 frases).
2. Diferencia clave respecto a horas previas.
3. Recomendación próxima hora.

📌 **RESUMEN EJECUTIVO** (Sección obligatoria al final con 2-3 viñetas).

IMPORTANTE: 
- USA DOBLE SALTO DE LÍNEA entre puntos.
- USA SOLO <b>, <i>, <code>.
- No uses listas ul/li."""

    results = {}
    for persona in ["CONSERVADOR", "SCALPER"]:
        info = PERSONAS[persona]
        answer, _ = _chat_with_persona(persona, prompt)
        if answer:
            # Si el agente sugiere una optimización en el texto, intentamos extraerla o simplemente la reportamos
            results[persona.lower()] = f"{info['emoji']} <b>{info['name']}</b>\n\n{answer}"
        else:
            results[persona.lower()] = f"{info['emoji']} <b>{info['name']}</b>: Error de sistema."

    return results

def get_context_summary(persona: str = None) -> str:
    """Retorna un resumen del contexto acumulado del día."""
    personas_to_check = [persona.upper()] if persona else ["CONSERVADOR", "SCALPER"]
    lines = []
    for p in personas_to_check:
        ctx = _load_memory(p)
        entries = len([e for e in ctx if e.get("role") == "model"])
        info = PERSONAS.get(p, {})
        lines.append(f"{info.get('emoji','?')} <b>{p}</b>: {entries} análisis acumulados hoy")
    return "\n".join(lines)

def get_expert_advice(symbol: str, prices: dict) -> str:
    """Solicita un análisis interactivo al EXPERT_ADVISOR."""
    p = prices.get(symbol, 0)
    rsi = prices.get(f"{symbol}_RSI", 0)
    bb_u = prices.get(f"{symbol}_BB_U", 0)
    bb_l = prices.get(f"{symbol}_BB_L", 0)
    ema_200 = prices.get(f"{symbol}_EMA_200", 0)
    usdt_d = prices.get("USDT_D", 0)
    elliott = prices.get(f"{symbol}_ELLIOTT", "Desconocida")
    ts = datetime.now().strftime("%H:%M")
    
    context = (f"CONTEXTO {symbol} ({ts}):\n"
              f"- Precio: ${(p or 0.0):,.2f}\n"
              f"- RSI: {(rsi or 0.0):.1f}\n"
              f"- BB: Superior ${(bb_u or 0.0):,.2f} | Inferior ${(bb_l or 0.0):,.2f}\n"
              f"- EMA 200: ${(ema_200 or 0.0):,.2f}\n"
              f"- Nivel USDT.D: {usdt_d}%\n\n"
              f"Analiza el pulso actual. Usa DOBLE SALTO DE LÍNEA y termina con un 📌 **RESUMEN EJECUTIVO**.\n"
              f"Tu veredicto debe seguir este estándar estricto:\n"
              f"1. ANALISIS ELLIOTT: <b>Tu conteo aquí</b>.\n"
              f"2. NIVELES CLAVE: <code>Target y SL</code>.\n"
              f"3. PSICOLOGIA: <i>Consejo rápido</i>.\n\n"
              f"IMPORTANTE: USA SOLO <b>, <i>, <code>. NO USES LISTAS (ul/li) NI ENCABEZADOS. Usa emojis para bullets.")
    
    res, _ = _chat_with_persona("EXPERT_ADVISOR", context)
    return res if res else "No pude generar el consejo en este momento."

def get_weekly_bias(symbol: str, prices: dict) -> dict:
    """Determina el Bias Semanal usando el Estratega Institucional."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    p = prices.get(symbol, 0)
    rsi = prices.get(f"{symbol}_RSI", 0)
    ema = prices.get(f"{symbol}_EMA_200", 0)
    usdt_d = prices.get("USDT_D", 0)
    
    prompt = (f"REPORTE SEMANAL PARA {symbol} ({ts}):\n"
              f"- Precio Actual: ${ (p or 0.0):,.2f}\n"
              f"- RSI (H4): { (rsi or 0.0):.1f}\n"
              f"- EMA 200 (H4): ${ (ema or 0.0):,.2f}\n"
              f"- Dominancia USDT: {usdt_d}%\n\n"
              f"Determina el Bias para los próximos 7 días.\n"
              f"Tu respuesta DEBE incluir al final una línea con: 'BIAS: [BULL/BEAR/ACCUMULATION]'.")
    
    res, _ = _chat_with_persona("INSTITUTIONAL_STRATEGIST", prompt)
    
    bias = "ACCUMULATION"
    if "BIAS: BULL" in res: bias = "BULL"
    elif "BIAS: BEAR" in res: bias = "BEAR"
    
    return {"analysis": res, "bias": bias}

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

def get_market_sentiment(prices: dict) -> dict:
    """Retorna un diagnóstico de sentimiento global con opiniones de Gordon y Aiden."""
    prompt = (
        f"Analiza estos datos de mercado actuales:\n"
        f"USDT.D: {prices.get('USDT_D', 'N/A')}% | BTC: ${prices.get('BTC', 0):,.2f} | ZEC: ${prices.get('ZEC', 0):,.2f}\n\n"
        f"1. Define el BIAS global (BULLISH/BEARISH/NEUTRAL).\n"
        f"2. Da una opinión de 12 palabras de GORDON (Wall Street Whale) 🎩.\n"
        f"3. Da una opinión de 12 palabras de AIDEN (Gen Z Guru) ⚡.\n\n"
        f"Formato JSON: "
        '{"bias": "...", "gordon": "...", "aiden": "..."}'
    )
    print(f"🧠 DEBUG: Solicitando sentimiento AI...")
    try:
        response, _ = _chat_with_persona("EXPERT_ADVISOR", prompt)
        import json
        import re
        # Limpieza de JSON de Gemini
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"bias": "NEUTRAL", "gordon": "Mercado incierto.", "aiden": "Vibras mixtas."}
    except Exception as e:
        print(f"[Sentiment Error] {e}")
        return {"bias": "NEUTRAL", "gordon": "La conexión con Wall Street falló.", "aiden": "El servidor está laggeado, bro."}

def get_top_setup(prices_dict: dict) -> str:
    """Escanea las monedas foco (BTC, TAO, ZEC) y usa la IA para coronar al mejor setup."""
    ts = datetime.now().strftime("%H:%M")
    
    usdt_d = prices_dict.get("USDT_D", 8.08)
    context_data = ""
    for sym in ["BTC", "TAO", "ZEC"]:
        price = prices_dict.get(sym, 0.0)
        rsi = prices_dict.get(f"{sym}_RSI", 50.0)
        context_data += f"• {sym}: ${price:,.2f} | RSI: {rsi:.1f}\n"

    prompt = (
        f"Eres un Scalper agresivo y enfocado (Bias: LONG_FOCUS). "
        f"Tu misión es evaluar estas 4 monedas y elegir ÚNICAMENTE LA MEJOR para operar AHORA.\n"
        f"Si ninguna sirve, di que debes esperar.\n\n"
        f"USDT.D actual: {usdt_d}%\n"
        f"Data ({ts}):\n"
        f"{context_data}\n\n"
        f"Instrucciones:\n"
        f"1. Descarta rápidamente 3 monedas (sin explicaciones largas).\n"
        f"2. Da un Veredicto Directo de 1 moneda elegida (LONG o SHORT).\n"
        f"3. Explica tu racional en 3 viñetas explosivas y analíticas.\n"
        f"Mantén la respuesta por debajo de las 120 palabras. Sé asertivo, usa viñetas para la justificación."
    )
    
    try:
        response, _ = _chat_with_persona("SCALPER", prompt)
        return response
    except Exception as e:
        return f"❌ Error generando Top Setup: {str(e)}"

def get_macro_shield(prices_dict: dict, stock_report_context: str = "") -> str:
    """Cruza métricas Crypto vs Stocks."""
    usdt_d = prices_dict.get("USDT_D", 8.08)
    btc_d = prices_dict.get("BTC_D", 52.0)
    
    prompt = (
        f"Eres un Estratega Institucional Macro.\n\n"
        f"Evaluación del Riesgo Global:\n"
        f"USDT.D: {usdt_d}% (Niveles tensión: >8.04% es miedo/corrección, <8.0% tranquilidad/euforia)\n"
        f"BTC Dominancia: {btc_d}%\n\n"
        f"Contexto de Stocks (Reciente):\n{stock_report_context[:600]}\n\n"
        f"Dime en 3 puntos claros:\n"
        f"- Sentimiento de riesgo hoy (On/Off)\n"
        f"- Estado de liquidez o tendencia según el USDT.D vs SPY\n"
        f"- Veredicto: ¿El mercado está para APALANCAMIENTO AGRESIVO o MODO DEFENSIVO (Stock picking)?\n\n"
        f"Responde directamente y de forma institucional con emojis ejecutivos. Sé contundente."
    )
    
    try:
        response, _ = _chat_with_persona("INSTITUTIONAL_STRATEGIST", prompt)
        return response
    except Exception as e:
        return f"❌ Error calculando Escudo Macro: {str(e)}"
