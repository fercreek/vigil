import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configuración de Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

PROMPT_BASE = """
Eres un analista experto en scalping de criptomonedas.
Tu objetivo es validar una señal técnica y decidir si es de ALTA PROBABILIDAD.

DATOS DEL MERCADO:
- Símbolo: {symbol}
- Precio Actual: ${price}
- Operación sugerida: {side}
- RSI (15m): {rsi}
- Bandas de Bollinger: {bb_status}

CRITERIOS DE VALIDACIÓN:
1. Si es SHORT: El RSI debe mostrar sobrecompra o debilidad, y el precio debe estar rechazando la banda superior.
2. Si es LONG: El RSI debe mostrar sobreventa o fuerza recuperándose, y el precio debe estar rebotando en la banda inferior.
3. Evalúa si el movimiento parece un 'fakeout' o una tendencia sólida.

RESPONDE ÚNICAMENTE EN FORMATO JSON:
{{
  "decision": "CONFIRM" o "REJECT",
  "reason": "Breve explicación de 10 palabras en español"
}}
"""

def get_ai_decision(symbol, price, side, rsi, bb_u, bb_l):
    """Consulta a Gemini para confirmar o rechazar un trade."""
    bb_status = "Cerca de Banda Superior" if bb_u and price >= bb_u * 0.99 else \
                "Cerca de Banda Inferior" if bb_l and price <= bb_l * 1.01 else "En rango medio"
    
    prompt = PROMPT_BASE.format(
        symbol=symbol,
        price=price,
        side=side,
        rsi=rsi,
        bb_status=bb_status
    )
    
    try:
        response = model.generate_content(prompt)
        # Limpiar respuesta por si trae markdown
        text = response.text.strip().replace('```json', '').replace('```', '')
        data = json.loads(text)
        return data.get("decision", "REJECT"), data.get("reason", "Error en análisis")
    except Exception as e:
        print(f"[Gemini Error] {e}")
        return "REJECT", "Fallo en conexión con IA"

def get_hourly_panorama(prices_dict):
    """Genera un análisis estratégico global cada hora."""
    # Extraer datos relevantes para el prompt
    context = ""
    for sym in ["ETH", "TAO", "BTC"]:
        p = prices_dict.get(sym, 0)
        rsi = prices_dict.get(f"{sym}_RSI", 0)
        context += f"- {sym}: ${p:,.2f} (RSI 15m: {rsi:.1f})\n"

    prompt = f"""
    Eres un Robot Analista de Scalping (Estratégico y Directo). 
    PANORAMA ACTUAL:
    {context}
    
    TAREA:
    1. Resume el sentimiento (Bullish/Bearish/Neutral) del mercado en general.
    2. Da 3 tips cortos (máx 15 palabras c/u) para operar en la próxima hora.
    3. Usa un tono futurista pero profesional.
    
    Formatea con Markdown para Telegram (Usa negritas, emojis de robot).
    """

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[Gemini Panorama Error] {e}")
        return "🤖 *ERROR DE SISTEMA*: No pude procesar el panorama en este momento."

if __name__ == "__main__":
    # Prueba rápida
    dec, reason = get_ai_decision("ETH", 2000, "SHORT", 65, 2010, 1950)
    print(f"Decisión: {dec} | Razón: {reason}")
    
    # Prueba panorama
    mock_data = {"ETH": 2000, "ETH_RSI": 65, "BTC": 65000, "BTC_RSI": 50, "TAO": 300, "TAO_RSI": 40}
    print("\n--- Panorama Test ---")
    print(get_hourly_panorama(mock_data))
