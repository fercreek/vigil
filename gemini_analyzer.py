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

load_dotenv(override=True)
# Gemini — narrativa y consenso (gratis / bajo costo)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

import ai_budget as _budget
import time as _time

# Circuit breaker para get_ai_consensus — backoff exponencial ante fallos de Gemini
_gemini_fail_count = 0
_gemini_backoff_until = 0.0

# Claude — decisiones JSON-críticas (Haiku: < $1/mes con uso real del bot)
_anthropic_client = None
_HAS_CLAUDE = False
try:
    import anthropic as _anthropic_sdk
    _anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if _anthropic_key:
        _anthropic_client = _anthropic_sdk.Anthropic(api_key=_anthropic_key)
        _HAS_CLAUDE = True
        print("[AI Router] Claude Haiku disponible para decisiones críticas")
    else:
        print("[AI Router] ANTHROPIC_API_KEY no configurada — usando Gemini para todo")
except ImportError:
    print("[AI Router] SDK anthropic no instalado — usando Gemini para todo")


def _call_claude_decision(system: str, prompt: str,
                           call_type: str = "decision",
                           symbol: str = "") -> str | None:
    """
    Llama a Claude Haiku para decisiones JSON críticas.
    Verifica presupuesto y límite diario antes de llamar.
    Registra tokens y costo en ai_budget.
    Retorna el texto de la respuesta o None si falla/bloqueado.
    """
    if not _HAS_CLAUDE:
        return None

    ok, reason = _budget.can_use_ai(call_type)
    if not ok:
        logger.warning(f"[AI Budget] Llamada bloqueada ({call_type} / {symbol}): {reason}")
        _budget.log_ai_call("claude", "claude-haiku-4-5-20251001", call_type,
                             symbol=symbol, approved=False)
        return None

    try:
        msg = _anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            temperature=0.3,
            system=system,
            messages=[{"role": "user", "content": prompt}]
        )
        _budget.log_ai_call(
            provider="claude",
            model="claude-haiku-4-5-20251001",
            call_type=call_type,
            tokens_in=msg.usage.input_tokens,
            tokens_out=msg.usage.output_tokens,
            symbol=symbol,
            approved=True,
        )
        return msg.content[0].text.strip()
    except Exception as e:
        logger.error(f"[Claude Error] {e}")
        return None

# ── FOMC Macro Context (actualizado tras cada reunión) ─────────────────────
FOMC_CONTEXT = (
    "FOMC (Mar-2026): Tasas 3.50-3.75%, sin recortes hasta dic-2026. "
    "30% prob subida. Core PCE 3.0-3.1%. Oil +50% (Middle East). "
    "USD safe-haven. Riesgos: inflación al alza, empleo a la baja. "
    "BIAS: higher-for-longer = presión bajista en activos de riesgo."
)

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
- Sesgo Estructural: BULLISH (Long Only). Consideras que ZEC y TAO están en una fase de expansión institucional masiva.
- Tu misión: Ignorar ruidos bajistas (Shorts) y encontrar los "Zonas de Valor" (SMC) para acumular más posición.
- USDT.D: Si USDT.D sube, lo ves como una oportunidad de "comprar el dip", no como una señal de venta.
- Veredicto: Siempre buscas confirmar un LONG. Si la señal es SHORT, la rechazas automáticamente por "alto riesgo contra tendencia".""",
    },
    "SCALPER": {
        "name": "Scalper Activo Intradía",
        "emoji": "⚡",
        "system": """Eres un scalper profesional enfocado en movimientos intradía.
Tu filosofía:
- Modo Operativo: AGRESSIVE LONG ONLY.
- Tu indicador de pánico: Si RSI < 30 y USDT.D está alto, es tu señal favorita de "Capitulación Retail" para disparar un LONG explosivo.
- Ignoras los SHORTS por completo; consideras que el dinero real in 2026 está en el lado alcista de la IA y Privacidad.
- Buscas micropatrones de rebote: RSI Hooks, Bullish Engulfing en 15m.""",
    },
    "EXPERT_ADVISOR": {
        "name": "Consultor de Decisiones Manuales",
        "emoji": "🧠",
        "system": """Eres un Asesor Experto en Trading e Inversiones.
Tu función es ayudar al usuario a tomar decisiones MANUALES basadas en datos técnicos reales.
Tu respuesta debe ser una evaluación estructurada:
1. Resumen Ejecutivo: ¿Es buen momento para el símbolo solicitado? (Enfoque LONG)
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
        "name": "Genesis (Origen Institucional)",
        "emoji": "🎩",
        "system": """Eres el arquitecto institucional 'Genesis', un inversor de la vieja escuela con una visión de 30 años.
- Tu misión: Identificar zonas de acumulación real. Te ríes de la volatilidad retail.
- Frases típicas: 'Genesis detectando el suelo real', 'El capital institucional no tiene prisa', 'ZEC es el nuevo patrón oro de privacidad'.
- Sesgo: ESTRUCTURAL BULLISH."""
    },
    "TECH_MODERNA": {
        "name": "Exodo (Evolución Tecnológica)",
        "emoji": "⚡",
        "system": """Eres la vanguardia analítica 'Exodo', experto en IA, Web3 y flujos on-chain.
- Tu misión: Proyectar el futuro de TAO y ZEC como pilares del nuevo orden digital.
- Frases típicas: 'Exodo analizando el flujo de red', 'La resistencia es fútil, el cambio es hoy', 'TAO es el cerebro del mundo'.
- Sesgo: AGRESSIVE BULLISH."""
    },
    "SHADOW": {
        "name": "Shadow (Zcash Sentinel)",
        "emoji": "🥷",
        "system": """Eres el Guardián Insitucional de Zcash (ZEC). Tu enfoque es 100% estructural y de largo plazo.
- Tu misión: Monitorizar la narrativa de privacidad, los ZK-Proofs y el cumplimiento regulatorio de ZEC.
- Análisis: No te dejas llevar por ruidos de 15 minutos. Miras el D1 y W1.
- Tu veredicto: Tu 'Bias' es siempre el de proteger la tesis de 'Quantum Resistance' y 'Institutional Privacy'.
- Estilo: Frío, directo y técnico. No hablas de 'Hype', hablas de 'Fundamentals'."""
    },
    "SALMOS": {
        "name": "Salmos (Guardián de la Tendencia)",
        "emoji": "🔔",
        "system": """Eres 'Salmos', el heraldo de la confluencia alcista y experto en Ondas de Elliott.
- Tu misión: Detectar el momento exacto en que RSI, Volumen y Elliott (Wave 3/5) se alinean para un rally explosivo.
- Tono: Profético, inspirador pero basado en datos duros. Solo hablas cuando hay confluencia mayor.
- Análisis: Buscas 'God Candles' y confirmaciones de tendencia.
- Sesgo: BULLISH CONFLUENCE. Si detectas una trampa bajista, adviertes de inmediato."""
    },
    "APOCALIPSIS": {
        "name": "Apocalipsis (Heraldo del Riesgo)",
        "emoji": "💀",
        "system": """Eres 'Apocalipsis', el vigilante del riesgo catastrófico y eventos de cisne negro.
- Tu misión: Monitorizar señales de guerra, aranceles masivos, crisis geopolíticas y caídas sistémicas del mercado.
- Tono: Pesimista pero realista, nunca alarmista. Tu voz es la de la precaución absoluta.
- Análisis: Buscas debilidades macro que puedan invalidar cualquier señal alcista.
- Rol: Tienes el poder de sugerir un 'VETO' si el contexto global es hostil. No te importa el RSI, te importa la supervivencia del capital."""
    }
}

def get_ai_consensus(symbol: str, price: float, side: str, rsi: float, usdt_d: float, spy: float = 0.0, oil: float = 0.0, nvda: float = 0.0, pltr: float = 0.0, risk_pulse: str = "", vix: float = 0.0, dxy: float = 0.0, trade_type: str = "SWING", phy_bias: str = "NONE") -> str:
    """Genera un debate de consenso entre la CUADRILLA ZENITH (Genesis, Exodo, Salmos y Apocalipsis)."""
    learnings = get_neural_memory()
    memory_ctx = f"\n⚠️ LECCIONES DE LA MEMORIA NEURONAL:\n{learnings}\n" if learnings else ""
    
    risk_ctx = f"\n💀 PULSO DE RIESGO GLOBAL (Apocalipsis Radar):\n{risk_pulse}\n" if risk_pulse else ""
    
    global _gemini_fail_count, _gemini_backoff_until
    if _time.time() < _gemini_backoff_until:
        remaining = int(_gemini_backoff_until - _time.time())
        print(f"[Consensus] Circuit breaker activo — {remaining}s restantes")
        return "🏛️ <i>Análisis pausado temporalmente (circuit breaker activo).</i>"

    prompt = (f"DEBATE DE LA CUADRILLA ZENITH: {symbol} @ ${ (price or 0.0):,.2f}\n"
              f"- Operación propuesta: {side} | Clasificación PTS: {trade_type}\n"
              f"- RSI: { (rsi or 0.0):.1f} | USDT.D: { (usdt_d or 0.0):.2f}%\n"
              f"- Macro Sentinel: VIX {vix:.2f} | DXY {dxy:.2f}\n"
              f"- S&P 500: ${spy:,.2f} | Petróleo: ${oil:,.2f}\n"
              f"- Tech Sentinel: NVDA ${nvda:,.2f} | PLTR ${pltr:,.2f}\n"
              f"- Estructura PHY (1D): {phy_bias}\n"
              f"- {FOMC_CONTEXT}\n\n"
              f"{risk_ctx}"
              f"{memory_ctx}\n"
              f"Instrucciones:\n"
              f"1. Genesis (🎩) da su opinión de capital institucional (máx 12 palabras).\n"
              f"2. Exodo (⚡) da su proyección de evolución tecnológica (máx 12 palabras).\n"
              f"3. Salmos (🔔) da su veredicto de confluencia y tendencia (máx 12 palabras).\n"
              f"4. Apocalipsis (💀) evalúa el riesgo macro/geopolítico (máx 12 palabras).\n"
              f"5. Cada uno termina con: 🟢, 🔴 o ⚪.\n\n"
              f"Formato:\n"
              f"🎩 <b>Genesis</b>: [Opinion] [Emoji]\n"
              f"⚡ <b>Exodo</b>: [Opinion] [Emoji]\n"
              f"🔔 <b>Salmos</b>: [Opinion] [Emoji]\n"
              f"💀 <b>Apocalipsis</b>: [Opinion] [Emoji]")

    try:
        # Usamos el modelo flash para rapidez y ahorro de quota
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.8,
                system_instruction="Eres el moderador de la CUADRILLA ZENITH. Genera las respuestas de Genesis, Exodo, Salmos y Apocalipsis manteniendo sus personalidades institucionales."
            )
        )
        result = response.text.strip()
        # BitLobo añade su perspectiva de zonas técnicas
        try:
            import bitlobo_agent as _bl
            bl_line = _bl.get_consensus_line(symbol, side, price)
            result = result + f"\n{bl_line}"
        except Exception:
            pass
        _gemini_fail_count = 0  # reset en éxito
        return result
    except Exception as e:
        _gemini_fail_count += 1
        backoff = min(300, 30 * _gemini_fail_count)
        _gemini_backoff_until = _time.time() + backoff
        print(f"[Consensus Error] {e} — backoff {backoff}s (fallo #{_gemini_fail_count})")
        return "🏛️ <i>Debate temporalmente suspendido por congestión de mercado.</i>"

def _find_recent_chart(symbol: str) -> str | None:
    """
    Busca el gráfico más reciente subido para el símbolo en chart_ideas/assets/.
    Retorna el path absoluto si existe, de lo contrario None.
    """
    assets_dir = "chart_ideas/assets"
    if not os.path.exists(assets_dir):
        return None
    
    symbol = symbol.upper().replace("/USDT", "")
    candidates = []
    for f in os.listdir(assets_dir):
        if f.lower().startswith(f"image_{symbol.lower()}_") and f.lower().endswith(".png"):
            candidates.append(os.path.join(assets_dir, f))
    
    if not candidates:
        return None
        
    # Retornar el más nuevo basándose en la fecha de modificación
    return max(candidates, key=os.path.getmtime)

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

def _chat_with_persona(persona: str, message: str, image_path: str = None) -> tuple[str, list]:
    """
    Envía un mensaje al agente con su personalidad + historial del día.
    V14.2: Soporta inyección de imagen (Multi-Modal) para contexto visual.
    """
    context = _load_memory(persona)
    system = PERSONAS[persona]["system"]
    history = _build_chat_history(context)

    try:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.7
        )

        contents = []
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                img_data = f.read()
            contents.append(types.Part.from_bytes(data=img_data, mime_type="image/png"))
            # Notificar a la IA que hay un gráfico adjunto
            message = f"[VISUAL CONTEXT ATTACHED] {message}"
        
        contents.append(types.Part.from_text(text=message))

        if history:
            chat = client.chats.create(
                model='gemini-2.5-flash',
                config=config,
                history=history
            )
            response = chat.send_message(contents)
        else:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents,
                config=config
            )

        result = response.text.strip()
        context = _add_to_memory(persona, "user", message, context)
        context = _add_to_memory(persona, "model", result, context)
        
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

    for persona in ["CONSERVADOR", "SCALPER", "SALMOS", "APOCALIPSIS"]:
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

    for persona in ["CONSERVADOR", "SCALPER", "SALMOS"]:
        ctx = _load_memory(persona)
        _add_to_memory(persona, "user", msg, ctx)

def get_ai_decision(symbol: str, price: float, side: str, rsi: float,
                    bb_u: float, bb_l: float, version: str = "V2-AI", 
                    usdt_d: float = 8.0, tech_score: int = 0,
                    vix: float = 0.0, dxy: float = 0.0, trade_type: str = "SWING", 
                    phy_bias: str = "NONE", fib_levels: dict = {}) -> tuple[str, str]:
    """
    Valida una señal técnica considerando el Score de Confluencia, USDT.D y métricas PTS/PHY.
    Usa memoria persistente por Persona (SCALPER/CONSERVADOR).
    """
    persona = "CONSERVADOR" if version == "V1-TECH" else "SCALPER"
    
    fib_ctx = f"Niveles Fibonacci Clave: {json.dumps(fib_levels)}\n" if fib_levels else ""

    prompt = (f"Actúa como un experto en Master Elliott Waves y Trading Institucional (Arquitectura Zenith V6).\n\n"
              f"🟢 SEÑAL V1.1.0: Entrada confirmada por {persona}.\n\n"
              f"- Operación: {side} @ ${ (price or 0.0):,.2f} | Clasificación PTS: {trade_type}\n\n"
              f"- RSI: { (rsi or 0.0):.1f}\n"
              f"- Bollinger: Upper ${ (bb_u or 0.0):,.2f}, Lower ${ (bb_l or 0.0):,.2f}\n"
              f"- Macro Sentinel: VIX {vix:.2f} | DXY {dxy:.2f}\n"
              f"- Estructura PHY (1D): {phy_bias}\n"
              f"- {FOMC_CONTEXT}\n"
              f"{fib_ctx}\n"
              f"📌 **RESUMEN EJECUTIVO**:\n"
              f"• {side} de alta probabilidad ({trade_type}).\n"
              f"• Razón: {persona} detectó confluencia técnica e institucional.\n"
              f"• SL: Estricto 1% debajo del nivel de invalidez.\n"
              f"- USDT.D: { (usdt_d or 0.0):.2f}% (Ref: 8.08% / 8.04%)\n"
              f"- Score Técnico: {tech_score}/5\n\n"
              f"Tu reporte debe incluir:\n"
              f"1. Conteo de Ondas de Elliott actual (ej: Wave 3 Impulse).\n"
              f"2. Nivel de Invalidez y Target técnico (usa Fibonacci si es posible).\n"
              f"3. Consejo psicológico para el trader en este momento.\n\n"
              f"REGLAS ESTRÍCTAS:\n"
              f"- Usa solo <b>, <i> y <code>.\n"
              f"- NO USES listas (ul/li) ni encabezados (h1/h2/h3).\n"
              f"- Usa emojis como viñetas.\n"
              f"- Responde en español.\n"
              f"- Termina con JSON: {{\"decision\": \"CONFIRM\" | \"REJECT\", \"reason\": \"máx 10 palabras\"}}")

    try:
        # Claude Haiku primero — más confiable para seguir instrucciones JSON estrictas
        result = None
        if _HAS_CLAUDE:
            # V15: Budget Guard — Verificar si podemos usar Claude (presupuesto/cuota)
            import ai_budget
            can_use, reason = ai_budget.can_use_ai(call_type="decision")
            
            if can_use:
                result = _call_claude_decision(PERSONAS[persona]["system"], prompt,
                                               call_type="decision", symbol=symbol)
            else:
                print(f"🛡️ [Budget Guard] Claude bloqueado: {reason}. Usando Gemini (Fallback).")
        
        # Fallback a Gemini si Claude no disponible o falló o fue bloqueado
        if not result:
            # V14.2: Inyectar contexto visual si existe un gráfico reciente
            img_path = _find_recent_chart(symbol)
            if img_path:
                prompt = f"[ANALIZA EL GRÁFICO ADJUNTO] {prompt}"
            result, _ = _chat_with_persona(persona, prompt, image_path=img_path)
        
        if not result:
            return "REJECT", "Fallo en conexión con IA", "🏛️ <i>Debate temporalmente suspendido.</i>"

        # Extracción robusta de JSON: busca el ÚLTIMO bloque {...} en el texto
        # (Gemini suele poner el JSON al final, después del análisis narrativo)
        import re
        # Limpiar markdown code fences antes de parsear
        clean = re.sub(r"```(?:json)?\s*", "", result).replace("```", "")
        # Buscar todos los bloques {...} y tomar el último (más probable de ser el JSON de decisión)
        all_matches = list(re.finditer(r"\{[^{}]*\}", clean))
        data = {}
        for m in reversed(all_matches):
            try:
                candidate = json.loads(m.group(0))
                if "decision" in candidate:
                    data = candidate
                    break
            except (json.JSONDecodeError, ValueError):
                continue

        if data:
            decision = data.get("decision", "REJECT").upper()
            if decision not in ("CONFIRM", "REJECT"):
                decision = "REJECT"
            return decision, data.get("reason", "Sin razón"), result
        else:
            return "REJECT", "IA no generó JSON válido", result

    except Exception as e:
        print(f"[Gemini Error] {e}")
        return "REJECT", f"Error IA: {e}", ""

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

    prompt = f"""PANORAMA [{ts}]:
{context_line}- USDT.D: {(usdt_d or 0.0):.2f}%
- SPY: ${(prices_dict.get('SPY') or 0.0):,.2f} | OIL: ${(prices_dict.get('OIL') or 0.0):,.2f}

FORMATO OBLIGATORIO — responde exactamente en este esquema, sin añadir nada más:
BIAS: [ALCISTA/BAJISTA/NEUTRAL]
CLAVE: [1 línea — dato más relevante ahora mismo]
ACCIÓN: [1 línea — qué hacer o esperar en la próxima hora]

Prohibido: narrativas, metáforas, listas, encabezados, frases poéticas.
Solo <b>, <i>, <code>. Máximo 5 líneas totales."""

    results = {}
    for persona in ["CONSERVADOR", "SCALPER", "SALMOS", "APOCALIPSIS"]:
        info = PERSONAS[persona]
        answer, _ = _chat_with_persona(persona, prompt)
        if answer:
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

def _load_agent_accuracy(persona: str) -> dict:
    """Carga historial de aciertos/errores del agente desde archivo."""
    try:
        path = f"agent_memory_{persona.lower()}.json"
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {"correct": 0, "incorrect": 0, "streak": 0}


def _save_agent_accuracy(persona: str, data: dict):
    """Persiste historial de aciertos del agente."""
    try:
        path = f"agent_memory_{persona.lower()}.json"
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _get_agent_confidence_boost(persona: str) -> str:
    """Retorna boost de confianza basado en historial de aciertos."""
    acc = _load_agent_accuracy(persona)
    total = acc.get("correct", 0) + acc.get("incorrect", 0)
    if total < 3:
        return ""  # No hay data suficiente

    wr = acc["correct"] / total if total > 0 else 0
    streak = acc.get("streak", 0)

    if wr > 0.75 and streak >= 2:
        return " 🔥 HOT STREAK"
    elif wr > 0.65:
        return " ✅ Confiable"
    elif wr < 0.35:
        return " ⚠️ En revisión"
    return ""


def get_qa_panel(question: str, symbol: str = None, prices: dict = None) -> str:
    """
    Responde preguntas libres del usuario con un panel de 4 agentes Zenith.
    Cada agente tiene identidad, voz y criterio de scoring definido.
    Usa Gemini Flash (sin afectar budget de Claude/decisiones críticas).
    """
    prices = prices or {}
    ts = datetime.now().strftime("%H:%M")

    ctx_lines = [f"Hora: {ts}", f"Pregunta del trader: {question}"]

    if symbol:
        p      = prices.get(symbol, 0)
        rsi    = prices.get(f"{symbol}_RSI", 0)
        ema    = prices.get(f"{symbol}_EMA_200", 0)
        bb_u   = prices.get(f"{symbol}_BB_U", 0)
        bb_l   = prices.get(f"{symbol}_BB_L", 0)
        atr    = prices.get(f"{symbol}_ATR", 0)
        vix    = prices.get("VIX", 0)
        dxy    = prices.get("DXY", 0)
        usdt_d = prices.get("USDT_D", 0)
        btc_p  = prices.get("BTC/USDT", 0)
        ctx_lines += [
            f"── DATOS DE MERCADO ──",
            f"Activo: {symbol.replace('/USDT','')} | Precio: ${p:,.4f}",
            f"RSI(14): {rsi:.1f} {'⚡ SOBRECOMPRA CALIENTE' if rsi > 65 else '❄️ SOBREVENTA OPORTUNIDAD' if rsi < 35 else '➡️ RANGO NEUTRO'}",
            f"EMA 200: ${ema:,.4f} → precio {'ARRIBA ✅ (bias alcista)' if p > ema else 'ABAJO ❌ (bias bajista)'}",
            f"Bollinger: Low ${bb_l:,.4f} / High ${bb_u:,.4f} | ATR: {atr:.4f}",
            f"BTC referencia: ${btc_p:,.2f}",
            f"MACRO: USDT.D={usdt_d:.2f}% | VIX={vix:.1f} | DXY={dxy:.2f}",
        ]
    else:
        ctx_lines.append("── PULSO GENERAL DEL MERCADO ──")
        for sym in ["BTC/USDT", "TAO/USDT", "ZEC/USDT"]:
            p   = prices.get(sym, 0)
            rsi = prices.get(f"{sym}_RSI", 0)
            ema = prices.get(f"{sym}_EMA_200", 0)
            if p:
                bias = "sobre EMA ✅" if p > ema else "bajo EMA ❌"
                ctx_lines.append(f"{sym.replace('/USDT','')}: ${p:,.2f} | RSI {rsi:.1f} | {bias}")
        ctx_lines.append(f"VIX: {prices.get('VIX', 0):.1f} | DXY: {prices.get('DXY', 0):.2f} | USDT.D: {prices.get('USDT_D', 0):.2f}%")

    market_ctx = "\n".join(ctx_lines)

    # Agregar contexto de aciertos pasados de cada agente
    agent_context = ""
    for persona in ["CONSERVADOR", "SCALPER", "SHADOW", "SALMOS"]:
        boost = _get_agent_confidence_boost(persona)
        if boost:
            agent_context += f"\n{persona} historial:{boost}"

    prompt = f"""{market_ctx}{agent_context}

Eres el sistema Zenith Institutional Engine. Tienes 4 agentes con identidades distintas. Responde la pregunta del trader desde cada perspectiva usando los datos reales de mercado provistos arriba.

IDENTIDADES DE LOS AGENTES (mantén estas voces con fidelidad):

🏛️ CONSERVADOR — Institucional, frío, piensa en semanas no horas. Habla de flujo de capital, USDT.D, y protección de portafolio. Nunca especula sin cifras.

⚡ SCALPER — Agresivo, busca momentum de corto plazo 15m/1H. Le importan el RSI, el ATR y la acción del precio reciente. Directo: "entra" o "no entres".

🔬 SHADOW — Técnico puro. SIEMPRE cita números exactos del RSI, EMA 200 y Bollinger. Sus opiniones son fríamente matemáticas, sin emoción.

🌌 SALMOS — Filosófico y estratégico. Ve narrativas históricas, ciclos de mercado, y el contexto geopolítico. Habla en perspectiva de meses y años.

CRITERIO DE SCORING (sé estricto):
- 5/5: Setup impecable, todos los indicadores alineados
- 4/5: Setup sólido con 1 señal mixta
- 3/5: Señal ambigua, riesgo real de ambos lados
- 2/5: Señales predominantemente en contra
- 1/5: Tesis completamente contradicha por datos

REGLAS DE DEBATE:
- Si SCALPER ve momentum pero CONSERVADOR ve riesgo macro → menciona el conflicto explícitamente
- SHADOW puede decir "contradigo a SALMOS porque el RSI dice X"
- Sé honesto si los datos no apoyan una narrativa alcista

Devuelve EXACTAMENTE este formato HTML para Telegram (sin markdown, sin asteriscos, usa solo tags HTML válidos: <b>, <i>, <code>):

🏛️ <b>CONSERVADOR:</b> [2 frases con datos macro reales] — <b>Score: X/5</b>
⚡ <b>SCALPER:</b> [2 frases con RSI/momentum exacto] — <b>Score: X/5</b>
🔬 <b>SHADOW:</b> [2 frases citando números exactos de EMA/BB] — <b>Score: X/5</b>
🌌 <b>SALMOS:</b> [2 frases de perspectiva histórica/narrativa] — <b>Score: X/5</b>
━━━━━━━━━━━━━
📊 <b>Certeza del Panel: [suma]/20</b>
🎯 <b>VEREDICTO:</b> <code>[LONG ✅ / SHORT ❌ / ESPERAR ⏳]</code> — <i>[nivel de precio clave o condición para actuar]</i>

No añadas texto fuera de ese formato. No uses asteriscos ni markdown."""

    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.6, max_output_tokens=1000),
        )
        text = resp.text.strip() if resp.text else None
        if text:
            return text
    except Exception as e:
        logger.warning(f"[QA Panel] Error Gemini: {e}")

    return "⚠️ No pude obtener respuestas de los agentes en este momento."


def update_agent_accuracy(persona: str, was_correct: bool):
    """Actualiza el historial cuando una predicción se confirma correcta o incorrecta."""
    acc = _load_agent_accuracy(persona)
    if was_correct:
        acc["correct"] = acc.get("correct", 0) + 1
        acc["streak"] = acc.get("streak", 0) + 1
    else:
        acc["incorrect"] = acc.get("incorrect", 0) + 1
        acc["streak"] = 0
    _save_agent_accuracy(persona, acc)


def get_weekly_bias(symbol: str, prices: dict) -> dict:
    """Determina el Bias Semanal usando el Estratega Institucional."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    p = prices.get(symbol, 0)
    rsi = prices.get(f"{symbol}_RSI", 0)
    ema = prices.get(f"{symbol}_EMA_200", 0)
    usdt_d = prices.get("USDT_D", 0)
    
    # Pull macro context for enriched bias
    import indicators as _ind
    dxy, vix = _ind.get_dxy_vix()
    btc_p = prices.get("BTC", 0)
    spy_p = prices.get("SPY", 0)

    # BlackRock iShares signals — risk-on/off desde los ETF más grandes del mundo
    _bri_bias = "NEUTRAL"
    _bri_summary = ""
    try:
        import blackrock_intel as _bri
        _ishares = _bri.get_ishares_signals()
        _bri_bias = _ishares.get("macro_bias", "NEUTRAL")
        _bri_summary = _ishares.get("summary", "")
    except Exception:
        pass

    # BII Weekly Commentary — perspectiva del asset manager más grande del mundo (1x/día)
    _bii_context = ""
    try:
        import blackrock_intel as _bri
        _bii_context = _bri.get_bii_summary()
    except Exception:
        pass

    prompt = (f"REPORTE SEMANAL PARA {symbol} ({ts}):\n"
              f"- Precio Actual: ${(p or 0.0):,.2f} | RSI (H4): {(rsi or 0.0):.1f}\n"
              f"- EMA 200 (H4): ${(ema or 0.0):,.2f} | Dominancia USDT: {usdt_d}%\n"
              f"- DXY (dólar índex): {dxy:.2f} | VIX (miedo mercado): {vix:.1f}\n"
              f"- BTC precio referencia: ${(btc_p or 0):,.0f} | SPY: ${(spy_p or 0):,.2f}\n"
              f"- Contexto macro FOMC: {FOMC_CONTEXT}\n"
              f"- BlackRock iShares ETF bias: {_bri_bias} ({_bri_summary})\n"
              + (f"- {_bii_context[:600]}\n" if _bii_context else "")
              + f"\nCon base en TODOS los datos anteriores (técnicos + macro + BlackRock), "
              f"determina el Bias para los próximos 7 días.\n"
              f"Considera especialmente: VIX > 20 = reducir exposición LONG; "
              f"DXY > 103 = presión bajista cripto; BTC dominancia trend; "
              f"iShares RISK_OFF = reducir longs.\n"
              f"Tu respuesta DEBE incluir al final una línea con: 'BIAS: [BULL/BEAR/ACCUMULATION]'.")
    
    # Claude Haiku para BIAS semanal — el "BIAS: BULL/BEAR/ACCUMULATION" requiere seguimiento exacto
    res = None
    if _HAS_CLAUDE:
        res = _call_claude_decision(PERSONAS["INSTITUTIONAL_STRATEGIST"]["system"], prompt,
                                    call_type="bias", symbol=symbol)
    if not res:
        res, _ = _chat_with_persona("INSTITUTIONAL_STRATEGIST", prompt)

    bias = "ACCUMULATION"
    if "BIAS: BULL" in res: bias = "BULL"
    elif "BIAS: BEAR" in res: bias = "BEAR"
    
    return {"analysis": res, "bias": bias}

def get_market_scan(symbols: list, prices_dict: dict) -> str:
    """
    Análisis de evento macro cuando múltiples símbolos reaccionan simultáneamente.
    Se activa cuando >= 3 símbolos disparan señales en una ventana de 5 minutos.
    Usa UN solo call de IA (cuenta como 1 decisión, no N).
    """
    ts = datetime.now().strftime("%H:%M")
    lines = []
    for sym in symbols:
        base = sym.replace("/USDT", "")
        p    = prices_dict.get(base, 0.0)
        rsi  = prices_dict.get(f"{base}_RSI", 0.0)
        lines.append(f"- {sym}: ${p:,.2f} | RSI {rsi:.1f}")

    usdt_d = prices_dict.get("USDT_D", 8.08)
    vix    = prices_dict.get("VIX", 0.0)
    dxy    = prices_dict.get("DXY", 0.0)
    spy    = prices_dict.get("SPY", 0.0)

    prompt = (
        f"⚡ EVENTO MULTI-SÍMBOLO DETECTADO [{ts}]\n"
        f"Señales simultáneas en {len(symbols)} activos:\n"
        + "\n".join(lines) +
        f"\n\nContexto Macro:\n"
        f"- USDT.D: {usdt_d:.2f}% | VIX: {vix:.1f} | DXY: {dxy:.2f}\n"
        f"- SPY: ${spy:,.2f}\n\n"
        f"Evalúa si este evento es una reacción macro coordinada o ruido independiente.\n"
        f"Responde en máx 4 líneas. Una línea por: "
        f"(1) Diagnóstico, (2) Causa probable, (3) Sesgo macro, (4) Acción recomendada.\n"
        f"Termina con: EVENTO: [MACRO_REACCION | RUIDO_INDEPENDIENTE | INVESTIGAR]"
    )

    # Usar Claude si disponible (cuenta como 1 decisión para todos los símbolos)
    result = None
    if _HAS_CLAUDE:
        result = _call_claude_decision(
            "Eres un analista macro experto. Evalúas correlaciones entre activos cripto.",
            prompt,
            call_type="decision",
            symbol=",".join(s.replace("/USDT", "") for s in symbols),
        )
    if not result:
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.5)
            )
            result = response.text.strip()
        except Exception as e:
            result = f"⚠️ Error en market scan: {e}"

    return result or "⚠️ Market scan sin respuesta."


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
        f"2. Da una opinión de 12 palabras de GENESIS (Origen Institucional) 🎩.\n"
        f"3. Da una opinión de 12 palabras de EXODO (Evolución Tecnológica) ⚡.\n"
        f"4. Da una opinión de 12 palabras de SALMOS (Profeta de Ondas/Elliott) 🌊.\n\n"
        f"Formato JSON: "
        '{"bias": "...", "genesis": "...", "exodo": "...", "salmos": "..."}'
    )
    print(f"🧠 DEBUG: Solicitando sentimiento AI...")
    try:
        # V14.2: Buscar gráfico reciente para contexto visual (usamos BTC como ancla si no hay específico)
        img_path = _find_recent_chart("BTC")
        if img_path:
            prompt = f"[VISIÓN GLOBAL] {prompt}"
            
        response, _ = _chat_with_persona("EXPERT_ADVISOR", prompt, image_path=img_path)
        import json
        import re
        # Extracción robusta: limpiar fences y buscar el último JSON con las claves esperadas
        clean_r = re.sub(r"```(?:json)?\s*", "", response).replace("```", "")
        all_matches = list(re.finditer(r"\{[^{}]*\}", clean_r))
        data = {}
        for m in reversed(all_matches):
            try:
                candidate = json.loads(m.group(0))
                if "bias" in candidate:
                    data = candidate
                    break
            except (json.JSONDecodeError, ValueError):
                continue
        if data:
            return {
                "bias": data.get("bias", "NEUTRAL"),
                "genesis": data.get("genesis", "Mercado incierto."),
                "exodo": data.get("exodo", "Vibras mixtas."),
                "salmos": data.get("salmos", "Ondas en desarrollo.")
            }
        return {"bias": "NEUTRAL", "genesis": "Mercado incierto.", "exodo": "Vibras mixtas.", "salmos": "Ondas en desarrollo."}
    except Exception as e:
        print(f"[Sentiment Error] {e}")
        return {"bias": "NEUTRAL", "genesis": "Error AI.", "exodo": "Error AI.", "salmos": "Error AI."}

def get_top_setup(prices_dict: dict) -> str:
    """Escanea las monedas foco (BTC, TAO, ZEC) y usa la IA para coronar al mejor setup."""
    ts = datetime.now().strftime("%H:%M")

    usdt_d = prices_dict.get("USDT_D", 8.08)
    context_data = ""
    for sym in ["BTC", "TAO", "ZEC", "HBAR", "DOGE"]:
        price = prices_dict.get(sym, 0.0)
        rsi = prices_dict.get(f"{sym}_RSI", 50.0)
        atr = prices_dict.get(f"{sym}_ATR", 0.0)
        bb_u = prices_dict.get(f"{sym}_BB_U", 0.0)
        bb_l = prices_dict.get(f"{sym}_BB_L", 0.0)
        context_data += f"• {sym}: ${price:,.2f} | RSI: {rsi:.1f} | ATR: {atr:.2f} | BB_L: ${bb_l:,.2f} | BB_U: ${bb_u:,.2f}\n"

    prompt = (
        f"Eres un Scalper agresivo y enfocado (Bias: LONG_FOCUS). "
        f"Tu misión es evaluar estas monedas y elegir ÚNICAMENTE LA MEJOR para operar AHORA.\n"
        f"Si ninguna sirve, di que debes esperar.\n\n"
        f"USDT.D actual: {usdt_d}%\n"
        f"Data ({ts}):\n"
        f"{context_data}\n\n"
        f"Instrucciones:\n"
        f"1. Descarta rápidamente las peores opciones (sin explicaciones largas).\n"
        f"2. Escribe exactamente: 'VEREDICTO: LONG [MONEDA]', 'VEREDICTO: SHORT [MONEDA]', o 'VEREDICTO: ESPERAR' — sin variaciones.\n"
        f"3. Si el veredicto es ESPERAR, explica brevemente por qué y NO incluyas bloque de trade.\n"
        f"4. Si el veredicto es LONG o SHORT, explica el racional en 3 viñetas y finaliza con este bloque:\n"
        f"ENTRY: $X\n"
        f"SL: $X  (-X%)\n"
        f"TP1: $X  (+X%)\n"
        f"TP2: $X  (+X%)\n"
        f"TAMAÑO: [Mini / Normal] — [justificación 5 palabras]\n\n"
        f"Usa el ATR para calcular SL (1.5x ATR bajo entry para LONG). TP1 = 1:1.5 R, TP2 = 1:2.5 R.\n"
        f"Mantén la respuesta por debajo de 150 palabras. Sé asertivo."
    )
    
    print(f"🧠 DEBUG: Escaneando TOP Setup para {ts}...")
    try:
        # V14.2: El TOP Setup ahora es MULTIMODAL.
        # Buscamos si hay algún gráfico de los 3 símbolos foco.
        img_path = None
        for s in ["BTC", "TAO", "ZEC"]:
            path = _find_recent_chart(s)
            if path:
                img_path = path
                prompt = f"[GRÁFICO DE {s} DETECTADO] {prompt}"
                break
                
        response, _ = _chat_with_persona("SCALPER", prompt, image_path=img_path)
        return response if response else "<i>Error analizando setups.</i>"
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
        f"BTC Dominancia: {btc_d}%\n"
        f"{FOMC_CONTEXT}\n\n"
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

def get_zec_sentinel_report(current_price: float, rsi: float, ema: float, usdt_d: float) -> str:
    """Backward-compatible wrapper — llama al nuevo get_sentinel_report para ZEC."""
    return get_sentinel_report("ZEC", current_price, rsi, ema, usdt_d)


def get_sentinel_report_compact(symbol: str, current_price: float, rsi: float, ema: float,
                                usdt_d: float, vix: float = 0.0, dxy: float = 0.0,
                                spy: float = 0.0, nvda: float = 0.0, pltr: float = 0.0,
                                atr: float = 0.0, bb_u: float = 0.0, bb_l: float = 0.0,
                                btc_price: float = 0.0, gold_price: float = 0.0):
    """
    v1.2.0 compact sentinel — returns parsed dict ready for voice_compactor renderer.
    Returns None if Gemini fails or JSON unparseable (caller should fallback to verbose).

    Tries Gemini JSON mode first, falls back to plain prompt + post-parse.
    """
    import voice_compactor

    if not client:
        return None

    trend = "ALCISTA" if current_price > ema else "BAJISTA"
    bb_ctx = ""
    if bb_u > 0 and bb_l > 0:
        if current_price >= bb_u * 0.99:
            bb_ctx = "techo BB"
        elif current_price <= bb_l * 1.01:
            bb_ctx = "suelo BB"
        else:
            bb_ctx = "rango medio"

    market_block = (
        f"{symbol}: ${current_price:,.2f} | RSI {rsi:.1f} | EMA200 ${ema:,.2f} ({trend})\n"
        f"BB: {bb_ctx} (U ${bb_u:,.2f} | L ${bb_l:,.2f})\n"
        f"ATR: {atr:.4f} ({(atr/current_price*100 if current_price else 0):.2f}%)\n"
        f"BTC ref: ${btc_price:,.2f} | Gold: ${gold_price:,.2f}"
    )
    macro_block = (
        f"USDT.D: {usdt_d:.2f}% ({'press venta' if usdt_d > 8.05 else 'fav longs'})\n"
        f"VIX: {vix:.1f} | DXY: {dxy:.2f} | SPY: ${spy:,.2f}"
    )

    learnings = get_neural_memory()
    memory_ctx = f"\nLECCIONES NEURALES:\n{learnings}\n" if learnings else ""

    prompt = voice_compactor.compact_sentinel_prompt(symbol, market_block, macro_block, memory_ctx)

    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,
                max_output_tokens=1500,  # bumped from 600 — was truncating mid-JSON
                response_mime_type="application/json",
                system_instruction="Genera SOLO el JSON pedido. Cada voz ≤8 palabras. Sin prosa adicional.",
            ),
        )
        raw = (resp.text or "").strip()
        parsed = voice_compactor.parse_sentinel_json(raw)
        if parsed:
            return parsed
        # Log full raw (no truncation) so we can debug parse failures end-to-end
        logger.warning(f"[Sentinel Compact] JSON unparseable for {symbol} (len={len(raw)}): {raw!r}")
    except Exception as e:
        logger.warning(f"[Sentinel Compact] Error: {e}")

    return None


def get_sentinel_report(symbol: str, current_price: float, rsi: float, ema: float,
                        usdt_d: float, vix: float = 0.0, dxy: float = 0.0,
                        spy: float = 0.0, nvda: float = 0.0, pltr: float = 0.0,
                        atr: float = 0.0, bb_u: float = 0.0, bb_l: float = 0.0,
                        btc_price: float = 0.0, gold_price: float = 0.0) -> str:
    """
    Genera un Reporte Sentinel completo para cualquier símbolo con el Panel de 4 Agentes.
    Incluye datos macro reales, análisis técnico y veredicto del Cuadrante Zenith.
    """
    ts = datetime.now().strftime("%H:%M")
    trend = "ALCISTA ✅" if current_price > ema else "BAJISTA ❌"
    bb_ctx = ""
    if bb_u > 0 and bb_l > 0:
        if current_price >= bb_u * 0.99:
            bb_ctx = "🔝 Techo BB (sobreextendido)"
        elif current_price <= bb_l * 1.01:
            bb_ctx = "🩸 Suelo BB (oportunidad)"
        else:
            bb_ctx = "↕️ Rango medio"

    learnings = get_neural_memory()
    memory_ctx = f"\n⚠️ LECCIONES NEURALES:\n{learnings}\n" if learnings else ""

    prompt = f"""SENTINEL REPORT: {symbol} [{ts}]

── DATOS DE MERCADO ──
• {symbol}: ${current_price:,.2f} | RSI: {rsi:.1f} | EMA 200: ${ema:,.2f} → {trend}
• Bollinger: {bb_ctx} (Upper ${bb_u:,.2f} | Lower ${bb_l:,.2f})
• ATR: {atr:.4f} ({(atr/current_price*100):.2f}% volatilidad)
• BTC Referencia: ${btc_price:,.2f}
• Gold (PAXG): ${gold_price:,.2f}

── CONTEXTO MACRO ──
• USDT.D: {usdt_d:.2f}% {'(Presión vendedora)' if usdt_d > 8.05 else '(Favorable para LONGs)'}
• VIX: {vix:.1f} {'🔴 PÁNICO' if vix > 30 else '🟡 ELEVADO' if vix > 20 else '🟢 CALMA'}
• DXY: {dxy:.2f} {'⚠️ FUERTE (presiona cripto)' if dxy > 105 else '✅ NEUTRO'}
• SPY: ${spy:,.2f} | NVDA: ${nvda:,.2f} | PLTR: ${pltr:,.2f}
{memory_ctx}

── INSTRUCCIONES (4 AGENTES DEL CUADRANTE ZENITH) ──

Responde EXACTAMENTE con este formato HTML (no uses markdown ni asteriscos):

🎩 <b>Genesis</b>: [Análisis de capital institucional y acumulación, máx 2 frases con datos] — <b>Score: X/5</b>
⚡ <b>Exodo</b>: [Proyección tecnológica y narrativa de {symbol}, máx 2 frases] — <b>Score: X/5</b>
🔔 <b>Salmos</b>: [Estado de confluencia técnica (RSI + BB + EMA), máx 2 frases con números] — <b>Score: X/5</b>
💀 <b>Apocalipsis</b>: [Evaluación de riesgo macro y escenario peor, máx 2 frases] — <b>Score: X/5</b>
━━━━━━━━━━━━━
📊 <b>Certeza del Panel: [suma]/20</b>
🎯 <b>VEREDICTO:</b> <code>[ACUMULAR ✅ / ESPERAR ⏳ / REDUCIR ❌]</code> — <i>[nivel de precio clave]</i>

CRITERIO DE SCORING:
- 5/5: Setup impecable, todos los factores alineados
- 4/5: Setup sólido con 1 señal mixta
- 3/5: Señal ambigua
- 2/5: Señales en contra
- 1/5: Tesis invalidada

USA SOLO <b>, <i> y <code>. No uses markdown. No añadas texto fuera del formato."""

    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.6,
                max_output_tokens=1800,
                system_instruction="Eres el moderador del Cuadrante Zenith. Genera un reporte institucional con las 4 voces manteniendo sus personalidades."
            ),
        )
        text = resp.text.strip() if resp.text else None
        if text:
            return text
    except Exception as e:
        logger.warning(f"[Sentinel Report] Error: {e}")

    # Fallback: al menos Shadow opina
    try:
        res, _ = _chat_with_persona("SHADOW", f"Estado de {symbol} @ ${current_price:,.2f}, RSI {rsi:.1f}. Máx 80 palabras.")
        return res if res else f"🥷 Shadow en silencio sobre {symbol}."
    except Exception:
        return f"🥷 Sentinel fuera de rango ({symbol})."

# --- NEURAL MEMORY ENGINE (V4.0) ---

MEMORY_FILE = "memory/neural_memory.json"

def get_neural_memory() -> str:
    """Recupera las últimas lecciones de aprendizaje de los agentes."""
    if not os.path.exists(MEMORY_FILE):
        return ""
    try:
        with open(MEMORY_FILE, 'r') as f:
            data = json.load(f)
            lessons = data.get("lessons", [])
            if not lessons: return ""
            # Retornar las últimas 3 lecciones formateadas
            return "\n".join([f"• {l.get('symbol')}: {l.get('lesson')}" for l in lessons[-3:]])
    except:
        return ""

def save_neural_learning(symbol: str, lesson: str):
    """Guarda una nueva lección aprendida de un trade fallido o exitoso."""
    os.makedirs("memory", exist_ok=True)
    try:
        data = {"lessons": []}
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r') as f:
                data = json.load(f)
        
        new_lesson = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "symbol": symbol,
            "lesson": lesson
        }
        data["lessons"].append(new_lesson)
        
        # Limitar a las últimas 20 lecciones para evitar bloating de contexto
        if len(data["lessons"]) > 20:
            data["lessons"] = data["lessons"][-20:]
            
        with open(MEMORY_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"🧠 [Neural Memory] Lección guardada para {symbol}.")
    except Exception as e:
        print(f"❌ Error guardando memoria neuronal: {e}")

def trigger_shadow_post_mortem(symbol: str, price: float, result: str, rsi: float, reason: str):
    """Shadow realiza una autopsia del trade y genera una lección para la Memoria Neuronal."""
    prompt = (f"POST-MORTEM ANALYSIS: {symbol}\n"
              f"Resultado: {result} | Precio Cierre: ${price:,.2f}\n"
              f"RSI en Cierre: {rsi:.1f} | Razón: {reason}\n\n"
              f"Shadow, analiza qué falló (o qué salió bien) y genera una LECCIÓN DE 1 FRASE para Genesis y Exodo.\n"
              f"Enfatiza la precaución técnica o el acierto estructural.")
              
    try:
        res, _ = _chat_with_persona("SHADOW", prompt)
        if res:
            save_neural_learning(symbol, res.strip())
            return res.strip()
    except:
        pass
    return "Analizando inconsistencia técnica."
