import os
import json
import requests
from datetime import datetime
from logger_core import logger, log_ai_decision
from google import genai
from google.genai import types

# Configuración
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "") # Opcional
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "") # Opcional

def get_social_intel(ticker: str, current_price: float = 0.0):
    """
    Combina Inteligencia de Noticias (CryptoPanic/Web) y Twitter (API opcional)
    para un reporte de sentimiento preciso.

    Retorna: (report_html: str, sentiment_score: float)
      sentiment_score: -1.0 (muy bajista) a +1.0 (muy alcista), 0.0 si neutral/error
    """
    logger.info(f"🔍 Iniciando Inteligencia Social para {ticker}...")

    news_context = ""
    twitter_context = ""

    # 1. FETCH NOTICIAS (Híbrido)
    try:
        url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&currencies={ticker}&kind=news"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            posts = data.get('results', [])[:5]
            for p in posts:
                news_context += f"- {p['title']} (URL: {p['url']})\n"
        else:
            news_context = "No se pudieron obtener noticias en vivo por API. Usando motor de búsqueda de IA..."
    except Exception as e:
        logger.error(f"Error en CryptoPanic API: {e}")
        news_context = "Error en API de noticias."

    # 2. FETCH TWITTER (Si hay Bearer Token)
    if TWITTER_BEARER_TOKEN:
        try:
            headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
            url = f"https://api.twitter.com/2/tweets/search/recent?query=%24{ticker}&max_results=10"
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                tweets = res.json().get('data', [])
                for t in tweets:
                    twitter_context += f"- {t['text']}\n"
            else:
                twitter_context = "API de Twitter denegó el acceso (posible límite o token inválido)."
        except Exception as e:
            logger.error(f"Error en Twitter API: {e}")
            twitter_context = "Error técnico en Twitter API."
    else:
        twitter_context = "⚠️ API Key de Twitter faltante en .env. Mode: Search Intelligence Only."

    # 3. ANÁLISIS GEMINI (retorna report + score numérico)
    report, score = _analyze_sentiment_with_gemini(ticker, news_context, twitter_context, current_price=current_price)
    return report, score

def check_altcoin_narratives(tickers: list):
    """Escanea varias monedas y solo retorna reporte si hay algo 'Bomba' (High Impact)."""
    results = []
    for t in tickers:
        logger.info(f"📡 Sentinel: Escaneando narrativa de {t}...")
        news_text = ""
        try:
            url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&currencies={t}&kind=news"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                posts = res.json().get('results', [])[:3]
                for p in posts: news_text += f"- {p['title']}\n"
        except: pass
        
        if news_text:
            report = _analyze_sentiment_with_gemini(t, news_text, "Passive Scan", sentinel_mode=True)
            if report and "🚨" in report: # Usamos el emoji como disparador de alta importancia
                results.append(report)
    return results

    return results

def get_global_risk_pulse():
    """
    Escanea noticias globales buscando 'Black Swans' (guerras, aranceles, colapsos).
    Específicamente para alimentar a Apocalipsis (💀).
    """
    logger.info("💀 Apocalipsis: Escaneando Pulso de Riesgo Global...")
    risk_context = ""
    keywords = ["war", "tariffs", "crash", "recession", "fed", "inflation", "geopolitical"]
    
    try:
        # Buscamos noticias generales de alto impacto
        url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&kind=news&filter=hot"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            posts = res.json().get('results', [])[:8]
            for p in posts:
                title = p['title'].lower()
                if any(k in title for k in keywords):
                    risk_context += f"⚠️ {p['title']}\n"
        
        if not risk_context:
            risk_context = "No se detectan amenazas macro inmediatas (Guerras/Aranceles) en el radar de noticias hot."
            
    except Exception as e:
        logger.error(f"Error en Risk Pulse: {e}")
        risk_context = "Error al conectar con el radar de riesgo global."
        
    return risk_context

def _analyze_sentiment_with_gemini(ticker: str, news: str, social: str, sentinel_mode: bool = False, current_price: float = 0.0):
    """
    Procesa el contexto social para dar un veredicto institucional.
    Retorna: (report_html: str, sentiment_score: float)
      sentiment_score: -1.0 a +1.0
    """
    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

    extra_instr = ""
    if sentinel_mode:
        extra_instr = "ESTÁS EN MODO SENTINEL: Solo si la noticia es de impacto institucional masivo (>80% importancia), comienza tu respuesta con el emoji 🚨. Si es ruido normal, responde con 'IGNORE'."

    prompt = f"""
    Eres un Agente de Inteligencia Social (Social Sentinel). Tu misión es analizar el ruido mediático sobre {ticker}.
    {extra_instr}

    DATOS RECOLECTADOS (Noticias):
    {news}

    DATOS RECOLECTADOS (Twitter/Social):
    {social}

    PRECIO ACTUAL:
    - {ticker}: ${current_price:,.2f} (Usar como referencia para targets si es mayor a 0)

    INSTRUCCIONES DE AUDITORÍA:
    1. Si no hay datos frescos, usa tu conocimiento interno sobre la narrativa actual de {ticker}.
    2. Identifica si la información parece un RUMOR, una NOTICIA OFICIAL o FAKE NEWS.
    3. Determina el SENTIMIENTO (BULLISH, BEARISH, NEUTRAL).
    4. Identifica el CATALIZADOR (News, Hype, Panic).
    5. Da un consejo institucional: ¿Es seguro entrar o hay mucho FOMO/Trampa?

    FORMATO DE RESPUESTA (HTML + JSON al final):
    🐦 <b>INTELIGENCIA SOCIAL: {ticker}</b>

    📊 <b>Sentimiento:</b> [Emoji] [Veredicto]
    🛡️ <b>Veracidad:</b> [Emoji] [Score 0-100%]
    🔥 <b>Catalizador:</b> [Narrativa principal]

    💡 <b>Análisis:</b> [Breve explicación de 2-3 párrafos]

    ⚠️ <b>Riesgo:</b> [Bajo/Medio/Alto/EXTREMO]

    🎯 <b>Objetivos Tentativos (Narrativa):</b>
    • TP 1: [Precio sugerido por sentimiento]
    • TP 2: [Precio sugerido por hype]

    Al final, añade en una línea aparte:
    {{"sentiment": "BULLISH"|"BEARISH"|"NEUTRAL", "score": <número entre -1.0 y 1.0>}}
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=600
            )
        )
        result = response.text.strip()
        log_ai_decision("SOCIAL_SENTINEL", prompt, result)

        # Extraer score numérico del JSON al final
        score = 0.0
        import re
        clean = re.sub(r"```(?:json)?\s*", "", result).replace("```", "")
        all_matches = list(re.finditer(r"\{[^{}]*\}", clean))
        for m in reversed(all_matches):
            try:
                candidate = json.loads(m.group(0))
                if "score" in candidate:
                    raw_score = float(candidate["score"])
                    score = max(-1.0, min(1.0, raw_score))  # clamp
                    break
            except (json.JSONDecodeError, ValueError):
                continue

        return result, score
    except Exception as e:
        logger.error(f"Error Gemini en Social Sentinel: {e}")
        return "❌ Error al generar reporte social de IA.", 0.0

if __name__ == "__main__":
    print(get_social_intel("ZEC"))
