import os
import json
import yfinance as yf
from google import genai
from google.genai import types
from dotenv import load_dotenv
from logger_core import logger, log_ai_decision
from config import STOCK_WATCHLIST
import episode_memory as _em

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
                max_output_tokens=256,
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
    for sym in yf_symbols:
        display = _YF_ALIAS.get(sym, sym)
        try:
            price = yf.Ticker(sym).fast_info.last_price
            prices[display] = float(price) if price is not None else 0.0
        except Exception as e:
            logger.warning(f"yfinance error for {sym}: {e}")
            prices[display] = 0.0
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

def _send_alert(msg: str) -> str | None:
    """Envía alerta sin inline keyboard. Retorna msg_id o None."""
    import requests
    url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage"
    payload = {"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "text": msg, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=5)
        return str(r.json().get("result", {}).get("message_id", "")) if r.ok else None
    except:
        return None


def _send_alert_with_kb(msg: str, keyboard: dict) -> str | None:
    """Envía alerta con inline keyboard. Retorna msg_id o None."""
    import requests
    url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage"
    payload = {
        "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
        "text": msg, "parse_mode": "HTML",
        "reply_markup": keyboard,
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
        return str(r.json().get("result", {}).get("message_id", "")) if r.ok else None
    except:
        return None


def _fetch_live_price_stock(ticker: str) -> float:
    """Precio live via yfinance para stocks/ETFs (no crypto)."""
    try:
        p = yf.Ticker(ticker).fast_info.last_price
        return float(p or 0)
    except Exception:
        return 0.0

_alert_cache = {}

def stock_watchdog():
    """Bucle infinito para checkeos en segundo plano de las acciones (cada 15 min)."""
    import time
    from datetime import datetime
    
    _send_alert("👁️ <b>CENTINELA DE ACCIONES ACTIVADO</b>\nVigilando niveles de entrada, Break Even y Take Profit automáticamente desde el último reporte cargado.")
    
    while True:
        try:
            import thread_health
            thread_health.heartbeat("stock")
            logger.info("👁️ Centinela: Analizando Reporte de Acciones + Watchlist estática...")
            report_signals, _ = extract_stock_signals()
            signals = _merge_signals(report_signals)
            if not signals:
                time.sleep(900)
                continue

            current_prices = _fetch_prices(signals)

            # Spec 001 (May-22-2026): earnings suppression 24h (NVDA, OKLO, TSLA, etc.)
            from config import EARNINGS_SUPPRESS_24H, EARNINGS_CALENDAR
            from datetime import datetime as _dt
            _suppressed_today = set()
            _today = _dt.now()
            for _t, _date in EARNINGS_CALENDAR.items():
                try:
                    _ed = _dt.strptime(_date, "%Y-%m-%d")
                    if _t in EARNINGS_SUPPRESS_24H and abs((_today - _ed).total_seconds()) < 86400:
                        _suppressed_today.add(_t)
                except Exception:
                    pass
            if _suppressed_today:
                logger.info("👁️ Centinela: earnings suppression activa para %s", _suppressed_today)

            for s in signals:
                t = s.get('ticker')
                if not t:
                    continue

                # Spec 001: skip si dentro de ventana 24h de earnings
                if t in _suppressed_today:
                    continue

                p = current_prices.get(t, 0.0)
                if not p:
                    continue

                direction = s.get('direction', 'HOLD')
                entry = s.get('entry')
                be = s.get('break_even')
                tp = s.get('take_profit_1')
                sl = s.get('stop_loss')
                
                # Check 0: ZONA VERDE (BitLobo-style) — precio entra al rango [SL, entry]
                ctx_note = s.get("context", "")
                is_bitlobo = "BitLobo" in ctx_note
                if is_bitlobo and entry and sl and direction == "LONG":
                    in_zone = sl <= p <= entry
                    if in_zone and "ZONE_ALERT" not in _alert_cache.get(t, []):
                        _send_alert(
                            f"🐺 <b>ZONA VERDE ACTIVADA: {t}</b>\n"
                            f"Precio actual: <b>${p:.2f}</b> — dentro de zona acumulación\n"
                            f"🟢 Zona: ${sl:.2f} – ${entry:.2f}\n"
                            f"🛑 Stop Loss: ${sl:.2f}\n"
                            f"📌 <i>{ctx_note[:100]}</i>"
                        )
                        _alert_cache.setdefault(t, []).append("ZONE_ALERT")
                        _em.log_alert_episode(t, "STOCK", direction, entry, sl, tp, source="BITLOBO")

                # Check 1: NEAR ENTRY — usa Activate/Skip en lugar de log inmediato
                if entry and "ENTRY_ALERT" not in _alert_cache.get(t, []):
                    dist = abs(p - entry) / entry
                    if dist <= 0.005:  # 0.5%
                        sl_line = f"🛑 Stop Loss: <b>${sl:.2f}</b>\n" if sl else ""
                        tp_line = f"🎯 Target: <b>${tp:.2f}</b>\n" if tp else ""
                        be_line = f"🔒 Break Even: ${be:.2f}\n" if be else ""
                        msg = (
                            f"🚨 <b>ALERTA DE ENTRADA: {t}</b>\n"
                            f"📌 {direction} — Precio actual: <b>${p:.2f}</b>\n"
                            f"🎯 Entrada obj: <b>${entry:.2f}</b> (dist. {dist*100:.2f}%)\n"
                            f"{sl_line}{tp_line}{be_line}"
                            f"<i>{s.get('context', '')[:80]}</i>\n\n"
                            f"⚠️ <i>Al activar se usará precio LIVE del momento.</i>"
                        )
                        try:
                            from scalp_alert_bot import _store_pending
                            import alert_manager as _am
                            atr_est = abs(entry - (sl or entry * 0.95)) * 0.5  # ATR estimado
                            tp2_est = tp  # usar tp como tp1 y tp2
                            _sid = _store_pending(
                                t, direction, entry,
                                tp or entry * 1.05, tp2_est or entry * 1.08,
                                sl or entry * 0.95,
                                atr_est, 50.0, 4,  # atr, rsi placeholder, score
                                "stock_entry", "STOCK", None,
                                macro_regime=s.get("context", "")[:40],
                            )
                            _send_alert_with_kb(msg, _am.get_signal_keyboard(_sid, t, direction))
                        except Exception as _e:
                            logger.warning("stock_analyzer: signal keyboard fallback (%s)", _e)
                            _send_alert(msg)
                        _alert_cache.setdefault(t, []).append("ENTRY_ALERT")
                        _em.log_alert_episode(t, "STOCK", direction, entry, sl, tp,
                                              source="STOCK")

                # Helper: management keyboard si hay trade abierto en DB
                def _mgmt_kb(ticker, side):
                    try:
                        import tracker as _trk
                        import alert_manager as _am
                        trade = _trk.get_last_open_trade(ticker)
                        if trade:
                            return _am.get_management_keyboard(trade["id"], ticker, side)
                    except Exception:
                        pass
                    return None

                # Checks 2/3/4 solo si Fernando tiene trade abierto en DB para este ticker
                _open_trade = None
                try:
                    import tracker as _trk
                    _open_trade = _trk.get_last_open_trade(t)
                except Exception:
                    pass
                if not _open_trade:
                    continue  # referencia PTS — sin posición real, no alertar SL/BE/TP

                # Check 2: BREAK EVEN
                if be and entry and "BE_ALERT" not in _alert_cache.get(t, []):
                    if (direction == "SHORT" and p <= be) or (direction == "LONG" and p >= be):
                        tp_line = f"🎯 Próximo target: ${tp:.2f}\n" if tp else ""
                        msg_be = (
                            f"🛡️ <b>BREAK EVEN ALCANZADO: {t}</b>\n"
                            f"📌 {direction} — Precio: <b>${p:.2f}</b>\n"
                            f"✅ BE nivel: <b>${be:.2f}</b> superado\n"
                            f"Acción: Mover SL a entrada <b>${entry:.2f}</b> (riesgo = 0)\n"
                            f"{tp_line}"
                        )
                        kb = _mgmt_kb(t, direction)
                        if kb:
                            _send_alert_with_kb(msg_be, kb)
                        else:
                            _send_alert(msg_be)
                        _alert_cache.setdefault(t, []).append("BE_ALERT")

                # Check 3: TAKE PROFIT
                if tp and "TP_ALERT" not in _alert_cache.get(t, []):
                    if (direction == "SHORT" and p <= tp) or (direction == "LONG" and p >= tp):
                        pnl_pct = round(abs(tp - entry) / entry * 100, 2) if entry else 0
                        entry_line = f"📥 Entrada: ${entry:.2f}\n" if entry else ""
                        msg_tp = (
                            f"🎯 <b>TAKE PROFIT HIT: {t}</b>\n"
                            f"📌 {direction} — Precio: <b>${p:.2f}</b>\n"
                            f"{entry_line}"
                            f"✅ Target alcanzado: <b>${tp:.2f}</b>\n"
                            f"💰 PnL potencial: <b>+{pnl_pct:.2f}%</b>\n"
                            f"Cierra posición completa o parcial."
                        )
                        kb = _mgmt_kb(t, direction)
                        if kb:
                            _send_alert_with_kb(msg_tp, kb)
                        else:
                            _send_alert(msg_tp)
                        _alert_cache.setdefault(t, []).append("TP_ALERT")
                        _em.fill_outcome_by_symbol(t, "STOCK", "WIN", pnl_pct)
                        _alert_cache.pop(t, None)  # trade cerrado en TP, liberar memoria

                # Check 4: STOP LOSS
                if sl and "SL_ALERT" not in _alert_cache.get(t, []):
                    if (direction == "SHORT" and p >= sl) or (direction == "LONG" and p <= sl):
                        pnl_pct = round(-abs(sl - entry) / entry * 100, 2) if entry else 0
                        entry_line = f"📥 Entrada: ${entry:.2f}\n" if entry else ""
                        msg_sl = (
                            f"🛑 <b>STOP LOSS HIT: {t}</b>\n"
                            f"📌 {direction} — Precio: <b>${p:.2f}</b>\n"
                            f"{entry_line}"
                            f"❌ SL tocado: <b>${sl:.2f}</b>\n"
                            f"💸 PnL: <b>{pnl_pct:.2f}%</b>\n"
                            f"Cierra posición para proteger capital."
                        )
                        kb = _mgmt_kb(t, direction)
                        if kb:
                            _send_alert_with_kb(msg_sl, kb)
                        else:
                            _send_alert(msg_sl)
                        _alert_cache.setdefault(t, []).append("SL_ALERT")
                        _em.fill_outcome_by_symbol(t, "STOCK", "LOSS", pnl_pct)
                        _alert_cache.pop(t, None)  # trade cerrado en SL, liberar memoria

            # Safety cap: si _alert_cache crece >100 keys (no debería con cleanup TP/SL), reset
            if len(_alert_cache) > 100:
                logger.warning(f"[Centinela] _alert_cache excedió 100 keys ({len(_alert_cache)}) — reset")
                _alert_cache.clear()

        except Exception as e:
            logger.error(f"Error en Centinela Acciones (Watchdog loop): {e}")
            
        for _ in range(15):  # 15 × 60s = 15 min
            time.sleep(60)
            thread_health.heartbeat("stock")


if __name__ == "__main__":
    print(check_stock_status())
