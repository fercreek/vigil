import os
import json
import yfinance as yf
from google import genai
from google.genai import types
from dotenv import load_dotenv
from logger_core import logger, log_ai_decision
from config import STOCK_WATCHLIST

load_dotenv()

REPORT_PATH = "latest_report.txt"

# Mapa yf_ticker → display ticker para los símbolos con alias (futuros)
_YF_ALIAS = {s["yf_ticker"]: s["ticker"] for s in STOCK_WATCHLIST if s["yf_ticker"] != s["ticker"]}

def extract_stock_signals():
    """Lee el latest_report.txt y usa Gemini para extraer las alertas en formato JSON estructurado."""
    if not os.path.exists(REPORT_PATH):
        return None, "❌ No se encontró el archivo latest_report.txt"
        
    with open(REPORT_PATH, "r") as f:
        content = f.read()

    if not content.strip():
        return None, "⚠️ El archivo latest_report.txt está vacío."

    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
    
    prompt = f"""
    Eres un analizador financiero extrayendo comandos de trading americanos y de NYSE/NASDAQ.
    Busca todas las acciones mencionadas en el siguiente reporte de mercado (ej: AMD, IWM, TSLA, SPY, XLC, XLF, MAGS, XOM, etc.).
    Ignora cualquier criptomoneda.
    Devuelve estrictamente UNA LISTA DE OBJETOS JSON con la siguiente estructura (uno por cada activo).
    Si un activo solo se menciona para ponerlo en break even (BE) o tomar ganancias parciales, invéntate un target o SL basado en la mención si no hay exacto.
    Si no trae dirección, asume la lógica del último tiempo o déjalo nulo.

    Estructura esperada por activo:
    {{
        "ticker": "AMD",
        "direction": "SHORT", # LONG, SHORT o HOLD
        "entry": 186.01, # Precio de entrada numérico o null
        "stop_loss": 216.80, # Stop loss numérico o null
        "take_profit_1": 149.0, # Primer target numérico o null
        "break_even": 163.0, # Nivel para mover a BE o null
        "context": "Operación bajista swing-posicional."
    }}

    Extrae sólo la lista JSON. Ningún otro texto de formato.

    REPORTE:
    ============
    {content}
    ============
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json"
            )
        )
        
        raw_text = response.text.strip()
        data = json.loads(raw_text)
        log_ai_decision("STOCK_ANALYZER", prompt, raw_text, {"status": "SUCCESS"})
        return data, None

    except Exception as e:
        err_msg = str(e)
        logger.error(f"Error extrayendo señales con IA: {err_msg}")
        log_ai_decision("STOCK_ANALYZER", prompt, "", {"status": "ERROR", "error": err_msg})
        return None, f"❌ Error extrayendo señales con IA: {err_msg}"

def _merge_signals(report_signals):
    """Combina señales del reporte con la watchlist estática. El reporte tiene prioridad si hay solapamiento."""
    report_tickers = {s["ticker"] for s in report_signals} if report_signals else set()
    static = [s for s in STOCK_WATCHLIST if s["ticker"] not in report_tickers]
    return (report_signals or []) + static

def _fetch_prices(signals):
    """Descarga precios para una lista de señales. Usa yf_ticker si existe, ticker si no."""
    yf_symbols = [s.get("yf_ticker", s["ticker"]) for s in signals if "ticker" in s]
    yf_symbols = list(dict.fromkeys(yf_symbols))  # deduplicar
    prices = {}
    try:
        yf_data = yf.Tickers(" ".join(yf_symbols))
        for sym in yf_symbols:
            display = _YF_ALIAS.get(sym, sym)
            try:
                prices[display] = yf_data.tickers[sym].fast_info.last_price
            except Exception:
                prices[display] = 0.0
    except Exception as e:
        logger.warning(f"yfinance error: {e}")
    return prices

def check_stock_status():
    """Extrae las señales del reporte + watchlist estática y revisa precios en tiempo real."""
    report_signals, err = extract_stock_signals()
    # Si hay error en el reporte, igual continuamos con la watchlist estática
    signals = _merge_signals(report_signals)

    if not signals:
        return "⚠️ No hay señales en watchlist ni en el reporte."

    current_prices = _fetch_prices(signals)
    if not current_prices:
        return "❌ Error conectando a Yahoo Finance."

    report = "📈 <b>RADAR DE ACCIONES PTS</b>\n<i>Watchlist + reporte activo</i>\n\n"

    for s in signals:
        t = s.get('ticker')
        if not t: continue

        p = current_prices.get(t, 0.0)
        direction = s.get('direction', 'HOLD')
        entry = s.get('entry')
        sl = s.get('stop_loss')
        tp = s.get('take_profit_1')
        be = s.get('break_even')
        
        # Calcular PnL si hay entry
        pnl = ""
        if entry and p > 0:
            pct_change = ((p - entry) / entry) * 100
            if direction == "SHORT": 
                pct_change = -pct_change
            emoji = "✅" if pct_change > 0 else "🔴"
            pnl = f" | Potencial PnL: {emoji} {pct_change:+.2f}%"
            
        icon = "📉" if direction == "SHORT" else "🚀" if direction == "LONG" else "🛡️"
        
        report += f"{icon} <b>{t}</b> ({direction})\n"
        report += f"• Precio Actual: <b>${p:,.2f}</b>{pnl}\n"
        if entry: report += f"• Entrada obj: ${entry:,.2f}\n"
        if be: report += f"• Nivel BE: ${be:,.2f}\n"
        if tp: report += f"• Target: ${tp:,.2f}\n"
        if sl: report += f"• Stop: ${sl:,.2f}\n"
        report += f"<i>{s.get('context', '')[:80]}...</i>\n\n"

    report += "🔄 <code>Puedes editar el latest_report.txt en el bot para actualizar este radar.</code>"
    return report

def _send_alert(msg: str):
    import requests
    url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage"
    payload = {"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

_alert_cache = {}

def stock_watchdog():
    """Bucle infinito para checkeos en segundo plano de las acciones (cada 15 min)."""
    import time
    from datetime import datetime
    
    _send_alert("👁️ <b>CENTINELA DE ACCIONES ACTIVADO</b>\nVigilando niveles de entrada, Break Even y Take Profit automáticamente desde el último reporte cargado.")
    
    while True:
        try:
            logger.info("👁️ Centinela: Analizando Reporte de Acciones + Watchlist estática...")
            report_signals, _ = extract_stock_signals()
            signals = _merge_signals(report_signals)
            if not signals:
                time.sleep(900)
                continue

            current_prices = _fetch_prices(signals)

            for s in signals:
                t = s.get('ticker')
                if not t:
                    continue
                p = current_prices.get(t, 0.0)
                if not p:
                    continue
                
                direction = s.get('direction', 'HOLD')
                entry = s.get('entry')
                be = s.get('break_even')
                tp = s.get('take_profit_1')
                sl = s.get('stop_loss')
                
                # Check 1: NEAR ENTRY
                if entry and "ENTRY_ALERT" not in _alert_cache.get(t, []):
                    dist = abs(p - entry) / entry
                    if dist <= 0.005:  # 0.5%
                        _send_alert(f"🚨 <b>ALERTA DE ACCIÓN INMINENTE: {t}</b>\nPrecio actual: ${p:.2f}\nLínea de Entrada ({direction}): ${entry:.2f}\n⚠️ ¡Prepárate, el precio está a menos de 0.5% del objetivo!")
                        _alert_cache.setdefault(t, []).append("ENTRY_ALERT")

                # Check 2: BREAK EVEN
                if be and entry and "BE_ALERT" not in _alert_cache.get(t, []):
                    if (direction == "SHORT" and p <= be) or (direction == "LONG" and p >= be):
                        _send_alert(f"🛡️ <b>MOMENTO BREAK EVEN: {t}</b>\n¡Felicidades! El precio alcanzó tu nivel objetivo de [${be:.2f}].\nMueve tu Stop Loss a ${entry:.2f} para riesgo cero.")
                        _alert_cache.setdefault(t, []).append("BE_ALERT")
                        
                # Check 3: TAKE PROFIT
                if tp and "TP_ALERT" not in _alert_cache.get(t, []):
                    if (direction == "SHORT" and p <= tp) or (direction == "LONG" and p >= tp):
                        _send_alert(f"🎯 <b>TAKE PROFIT HIT: {t}</b>\nEl precio de mercado alcanzó el Target [$ {tp:.2f}].\nCierra tu posición completa o parcial.")
                        _alert_cache.setdefault(t, []).append("TP_ALERT")

                # Check 4: STOP LOSS
                if sl and "SL_ALERT" not in _alert_cache.get(t, []):
                    if (direction == "SHORT" and p >= sl) or (direction == "LONG" and p <= sl):
                        _send_alert(f"🛑 <b>STOP LOSS HIT: {t}</b>\nEl precio alcanzó el riesgo límite [$ {sl:.2f}].\nCierra posición para proteger capital.")
                        _alert_cache.setdefault(t, []).append("SL_ALERT")
                        
        except Exception as e:
            logger.error(f"Error en Centinela Acciones (Watchdog loop): {e}")
            
        time.sleep(900) # 15 minutos de espera


if __name__ == "__main__":
    print(check_stock_status())
