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

if __name__ == "__main__":
    # Prueba rápida
    dec, reason = get_ai_decision("ETH", 2000, "SHORT", 65, 2010, 1950)
    print(f"Decisión: {dec} | Razón: {reason}")
