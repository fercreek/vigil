"""
blackrock_intel.py — BlackRock Intelligence Layer

Fuentes:
  1. BlackRock Investment Institute (BII) Weekly Commentary
     → bias macro semanal de los asset managers más grandes del mundo
  2. iShares ETF signals (TLT, HYG, IVV, LQD)
     → flows y precios como proxy de risk-on/risk-off

Integración:
  - blackrock_intel.get_bii_summary() → texto para contexto Gemini
  - blackrock_intel.get_ishares_signals() → dict con bias de mercado
  - blackrock_intel.get_macro_context() → resumen combinado para prompts

Cache: BII se actualiza 1x/día (scraped). iShares cada 15 min via yfinance.
"""

import os
import time
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from logger_core import logger

# ── Cache ──────────────────────────────────────────────────────────────────────
_CACHE = {
    "bii":     {"text": "", "title": "", "last_update": 0},
    "ishares": {"data": {}, "last_update": 0},
}

TTL_BII     = 86400   # 24h — el commentary es semanal
TTL_ISHARES = 900     # 15 min

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# ETFs iShares clave como indicadores macro
ISHARES_ETFS = {
    "TLT": {
        "name": "iShares 20+ Year Treasury Bond",
        "signal": "safe_haven",   # TLT ↑ = risk-off, dinero en bonds
        "invert": True,            # TLT ↑ es BEARISH para cripto/acciones
    },
    "HYG": {
        "name": "iShares High Yield Corporate Bond",
        "signal": "risk_appetite", # HYG ↑ = risk-on, mercado asume riesgo
        "invert": False,
    },
    "IVV": {
        "name": "iShares Core S&P 500",
        "signal": "broad_market",  # IVV = broad market proxy
        "invert": False,
    },
    "LQD": {
        "name": "iShares Investment Grade Corporate Bond",
        "signal": "credit_quality", # LQD ↑ = crédito corporativo saludable
        "invert": False,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. BII WEEKLY COMMENTARY
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_bii_commentary() -> dict:
    """
    Scrapea el weekly commentary de BlackRock Investment Institute.
    Retorna {"title": str, "paragraphs": [str], "raw_text": str}.
    """
    url = "https://www.blackrock.com/us/individual/insights/blackrock-investment-institute/weekly-commentary"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')

        # Extraer título del artículo más reciente (H2 principal)
        title = ""
        for tag in soup.find_all(['h2', 'h3']):
            t = tag.get_text(strip=True)
            if len(t) > 15 and t != "Weekly market commentary":
                title = t
                break

        # Extraer párrafos con contenido real (>80 chars, no boilerplate)
        paragraphs = []
        skip_phrases = ["please enable JavaScript", "cookie", "privacy", "terms of use",
                        "register", "sign in", "loading", "subscribe"]
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) > 80:
                lower = text.lower()
                if not any(skip in lower for skip in skip_phrases):
                    paragraphs.append(text[:400])
                    if len(paragraphs) >= 8:
                        break

        raw_text = f"{title}\n\n" + "\n\n".join(paragraphs)
        return {"title": title, "paragraphs": paragraphs, "raw_text": raw_text}

    except Exception as e:
        logger.warning(f"[BII] Error scraping commentary: {e}")
        return {"title": "", "paragraphs": [], "raw_text": ""}


def get_bii_summary() -> str:
    """
    Retorna el resumen del BII commentary actual (con cache 24h).
    Listo para insertar en un prompt de Gemini/Claude.
    """
    now = time.time()
    if now - _CACHE["bii"]["last_update"] < TTL_BII and _CACHE["bii"]["text"]:
        return _CACHE["bii"]["text"]

    logger.info("[BII] Actualizando BlackRock Investment Institute commentary...")
    data = fetch_bii_commentary()

    if data["raw_text"].strip():
        summary = (
            f"[FUENTE: BlackRock Investment Institute — Weekly Commentary]\n"
            f"Título: {data['title']}\n\n"
            f"{data['raw_text'][:1200]}"
        )
        _CACHE["bii"]["text"] = summary
        _CACHE["bii"]["title"] = data["title"]
        _CACHE["bii"]["last_update"] = now
        logger.info(f"[BII] Commentary cargado: '{data['title']}'")
    else:
        summary = "[BII] Commentary no disponible (error de red o página vacía)"

    return summary


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ISHARES ETF SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════

def get_ishares_signals() -> dict:
    """
    Obtiene precios y cambio % de los ETFs iShares clave.
    Retorna dict con bias macro derivado.

    Ejemplo de retorno:
    {
        "TLT":  {"price": 87.07, "change_pct": +0.92, "signal": "safe_haven", "bearish_crypto": True},
        "HYG":  {"price": 80.65, "change_pct": +0.37, "signal": "risk_appetite", "bullish_crypto": True},
        "IVV":  {"price": 713.36, "change_pct": +1.22, "signal": "broad_market"},
        "LQD":  {"price": 110.04, "change_pct": +0.56, "signal": "credit_quality"},
        "macro_bias": "RISK_ON" | "RISK_OFF" | "NEUTRAL",
        "summary": "HYG +0.4% (risk-on) | TLT +0.9% (safe haven demand)"
    }
    """
    now = time.time()
    if now - _CACHE["ishares"]["last_update"] < TTL_ISHARES and _CACHE["ishares"]["data"]:
        return _CACHE["ishares"]["data"]

    result = {}
    tickers = list(ISHARES_ETFS.keys())

    try:
        for sym in tickers:
            try:
                hist = yf.Ticker(sym).history(period="2d")
                if hist is None or hist.empty:
                    continue
                price = float(hist['Close'].iloc[-1])
                prev  = float(hist['Close'].iloc[-2]) if len(hist) > 1 else price
                chg   = (price - prev) / prev * 100 if prev > 0 else 0.0
                result[sym] = {
                    "price": round(price, 2),
                    "change_pct": round(chg, 2),
                    "name": ISHARES_ETFS[sym]["name"],
                    "signal": ISHARES_ETFS[sym]["signal"],
                }
            except Exception as e:
                logger.debug(f"[iShares] Error fetching {sym}: {e}")

    except Exception as e:
        logger.warning(f"[iShares] Error general: {e}")

    # Derivar macro_bias
    # TLT ↑ fuerte = risk-off (malo para crypto)
    # HYG ↑ = risk-on (bueno para crypto)
    tlt_chg = result.get("TLT", {}).get("change_pct", 0)
    hyg_chg = result.get("HYG", {}).get("change_pct", 0)

    if hyg_chg > 0.3 and tlt_chg < 0.5:
        macro_bias = "RISK_ON"
    elif tlt_chg > 0.5 and hyg_chg < 0.2:
        macro_bias = "RISK_OFF"
    else:
        macro_bias = "NEUTRAL"

    # Summary line para logs/Telegram
    parts = []
    for sym, data in result.items():
        arrow = "↑" if data["change_pct"] > 0 else "↓"
        parts.append(f"{sym} {arrow}{abs(data['change_pct']):.1f}%")
    summary = " | ".join(parts) if parts else "Sin datos"

    result["macro_bias"] = macro_bias
    result["summary"] = summary

    _CACHE["ishares"]["data"] = result
    _CACHE["ishares"]["last_update"] = now
    logger.info(f"[iShares] {summary} → Bias: {macro_bias}")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MACRO CONTEXT COMBINADO (para Gemini prompts)
# ═══════════════════════════════════════════════════════════════════════════════

def get_macro_context(include_bii: bool = True) -> str:
    """
    Retorna contexto macro completo de BlackRock para insertar en prompts de IA.
    include_bii=False → solo iShares (más rápido, no hace scraping).

    Uso:
        context = blackrock_intel.get_macro_context()
        prompt = f"Analiza BTC con este contexto:\n{context}\n\nPrecio actual: ..."
    """
    parts = []

    # iShares signals (siempre)
    ishares = get_ishares_signals()
    bias = ishares.get("macro_bias", "NEUTRAL")
    summary = ishares.get("summary", "")
    parts.append(
        f"[BlackRock iShares ETF Signals]\n"
        f"Macro bias: {bias}\n"
        f"{summary}\n"
        f"TLT (safe haven bonds): ${ishares.get('TLT', {}).get('price', 0):.2f} "
        f"({ishares.get('TLT', {}).get('change_pct', 0):+.2f}%)\n"
        f"HYG (high yield / risk appetite): ${ishares.get('HYG', {}).get('price', 0):.2f} "
        f"({ishares.get('HYG', {}).get('change_pct', 0):+.2f}%)"
    )

    # BII commentary (1x/día)
    if include_bii:
        bii = get_bii_summary()
        if bii and "no disponible" not in bii:
            parts.append(bii)

    return "\n\n---\n\n".join(parts)


def get_ishares_bias_score() -> int:
    """
    Retorna un score de confluencia para estrategias:
      +1 = RISK_ON (bullish crypto/stocks)
       0 = NEUTRAL
      -1 = RISK_OFF (bearish, reducir exposure)
    """
    ishares = get_ishares_signals()
    bias = ishares.get("macro_bias", "NEUTRAL")
    if bias == "RISK_ON":
        return 1
    elif bias == "RISK_OFF":
        return -1
    return 0


if __name__ == "__main__":
    print("=== TEST blackrock_intel.py ===\n")
    print("--- iShares Signals ---")
    sig = get_ishares_signals()
    for k, v in sig.items():
        if isinstance(v, dict):
            print(f"  {k}: ${v.get('price', 0):.2f} ({v.get('change_pct', 0):+.2f}%) — {v.get('signal', '')}")
    print(f"  Macro Bias: {sig.get('macro_bias')}")
    print(f"  Summary: {sig.get('summary')}")
    print()
    print("--- BII Commentary ---")
    print(get_bii_summary()[:600])
    print()
    print("--- Macro Context (para Gemini) ---")
    print(get_macro_context()[:800])
