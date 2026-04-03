#!/usr/bin/env python3
"""
Scalp Alert Bot — ETH / TAO / BTC (Multi-Strategy V1-Tech vs V2-AI)
Envía alertas a Telegram cuando los precios tocan niveles clave del plan.
"""

import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv
import indicators
import tracker
import gemini_analyzer
import indicators_swing
import trading_executor
import ccxt
import yfinance as yf
import social_analyzer

# Cargar variables de entorno
load_dotenv(override=True)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "35")) # Aumentamos ligeramente para proteger CoinGecko
PHASE_FILE = "phase.txt"
OFFSET_FILE = "last_update_id.txt"

# --- RESILIENCE ENGINE (CACHE) ---
GLOBAL_CACHE = {
    "prices": {},
    "indicators": {},
    "global_metrics": {"usdt_d": 8.08, "btc_d": 52.0},
    "macro_metrics": {"spy": 0.0, "oil": 0.0, "nvda": 0.0, "pltr": 0.0, "dxy": 0.0, "vix": 0.0},
    "last_update": {
        "prices": 0,
        "indicators": {},
        "global_metrics": 0,
        "macro_metrics": 0,
        "fail_count": 0
    },
    "last_rsi": {"SOL": 50.0, "BTC": 50.0, "TAO": 50.0, "ZEC": 50.0},
    "social_intel": {},  # {sym: {"score": 0.0, "last_update": 0}}
    "executor": None, # V5.0 Instance
    "shadow_messages": [], # V15.0 Real Shadow Intel
    "fear_greed": {"value": 50, "label": "Neutral"}
}

# --- POSITION TRACKER: evita alertas duplicadas para la misma posición abierta ---
# Clave: "{sym}_{side}" → timestamp de cuando se abrió
# Se limpia cuando llega confirmación de TP/SL o manualmente via Telegram
OPEN_POSITIONS = {}
POSITION_TTL = 3600  # 1 hora: posición se considera expirada si no hay TP/SL en ese tiempo
# Tiempos de Vida (TTL) en segundos
TTL_PRICES = 20      # Precio: 20s (Fallback si falla la red)
TTL_INDICATORS = 120 # Indicadores: 2 min (Reducción de carga)
TTL_GLOBAL = 600     # Métricas Globales: 10 min
TTL_MACRO = 900      # Macro (SPY/Oil): 15 min (Lento)
TTL_SOCIAL = 600     # Inteligencia Social: 10 min

# ─── Multi-Symbol Event Detector ─────────────────────────────────────────────
# Detecta cuando varios símbolos disparan señales simultáneamente → market scan
_SIGNAL_EVENTS: dict = {}   # {symbol: timestamp}
_MULTI_SIG_WINDOW  = 300    # 5 min: ventana de detección
_MULTI_SIG_TRIGGER = 2      # señales simultáneas para activar scan (2 de 3 símbolos)
_LAST_SCAN_TS      = 0.0    # evita scans duplicados en la misma ventana

import ai_budget as _ai_budget

def register_signal_event(sym: str, prices: dict) -> None:
    """
    Registra que el símbolo disparó una señal ahora.
    Si >= _MULTI_SIG_TRIGGER símbolos reaccionaron en los últimos 5 min,
    lanza get_market_scan() con un único call de IA (no N calls).
    """
    global _LAST_SCAN_TS
    now = time.time()
    _SIGNAL_EVENTS[sym] = now

    # Purgar eventos viejos
    active = {s: t for s, t in _SIGNAL_EVENTS.items() if now - t <= _MULTI_SIG_WINDOW}
    _SIGNAL_EVENTS.clear()
    _SIGNAL_EVENTS.update(active)

    if len(active) < _MULTI_SIG_TRIGGER:
        return  # No hay suficientes señales simultáneas

    # Evitar scan duplicado en la misma ventana
    if now - _LAST_SCAN_TS < _MULTI_SIG_WINDOW:
        return

    symbols_firing = [f"{s}/USDT" for s in active.keys()]
    _LAST_SCAN_TS = now
    try:
        scan = gemini_analyzer.get_market_scan(symbols_firing, prices)
        ts_str = datetime.now().strftime("%H:%M")
        msg = (f"⚡ <b>EVENTO MULTI-SÍMBOLO [{ts_str}]</b>\n"
               f"Señales en: <code>{', '.join(symbols_firing)}</code>\n\n"
               f"{safe_html(scan)}")
        _send_telegram(msg)
        print(f"[Multi-Signal] Scan enviado para {symbols_firing}")
        add_shadow_intel("MULTI", f"Análisis unificado para {', '.join(symbols_firing)} completado.")
    except Exception as e:
        print(f"❌ Error en Multi-Signal scan: {e}")

def add_shadow_intel(sym: str, msg: str):
    """Añade un mensaje real a la cola de Shadow Intel para el dashboard."""
    ts = datetime.now().strftime("%H:%M")
    new_msg = {"ts": ts, "msg": f"🥷 <b>{sym}</b>: {msg}"}
    msgs = GLOBAL_CACHE.get("shadow_messages", [])
    msgs.insert(0, new_msg)
    GLOBAL_CACHE["shadow_messages"] = msgs[:10] # Mantener los últimos 10

def safe_html(text: str) -> str:
    """Delegado a alert_manager.safe_html — ver ese módulo."""
    import alert_manager
    return alert_manager.safe_html(text)
def sanitize_dict(d: dict) -> dict:
    """Asegura que todos los valores numéricos en el diccionario sean válidos."""
    if not d or not isinstance(d, dict): return {}
    for k in list(d.keys()):
        if d[k] is None:
            if "RSI" in k: d[k] = 50.0
            elif "USDT_D" in k: d[k] = 8.08
            elif "BTC_D" in k: d[k] = 52.0
            else: d[k] = 0.0
    return d

# ─── CONFIGURACIÓN DE NIVELES ──────────────────────────────────────────────
LEVELS = {
    "SOL": {"short_entry_high": 182, "sl_short": 188, "target1": 165, "target2": 160, "long_zone": 158},
    "TAO": {"resistance": 320, "target1": 290, "target2": 270, "long_zone": 265, "long_sl": 238},
    "BTC": {"resistance": 68283, "support1": 65000, "support2": 62987}
}

# ─── CONECTORES DE INTERCAMBIO (REUTILIZABLES) ──────────────────────────
# Inicializamos una vez para evitar latencia de conexión
binance_ex = ccxt.binance()

def get_phase() -> str:
    if not os.path.exists(PHASE_FILE): return "SHORT"
    with open(PHASE_FILE, "r") as f: return f.read().strip()

def set_phase(phase: str):
    with open(PHASE_FILE, "w") as f: f.write(phase)
    send_telegram(f"🔄 <b>CAMBIO DE ESTRATEGIA</b>: Fase actualizada a <code>{phase}</code>")

def update_dynamic_levels():
    """Calcula Soportes/Resistencias Diarios basados en ayer (Pivot Points)."""
    print("\n🔄 Actualizando niveles dinámicos (Pivot Points)...")
    symbols = {
        "BTC": (binance_ex, "BTC/USDT"),
        "TAO": (binance_ex, "TAO/USDT"),
        "ZEC": (binance_ex, "ZEC/USDT")
    }
    
    for key, (exchange, sym) in symbols.items():
        try:
            ohlcv = exchange.fetch_ohlcv(sym, timeframe='1d', limit=2)
            if len(ohlcv) < 2: continue
            ayer = ohlcv[0] # Vela cerrada
            h, l, c = ayer[2], ayer[3], ayer[4]
            p = (h + l + c) / 3
            r1 = (2 * p) - l
            s1 = (2 * p) - h
            
            if key == "SOL":
                LEVELS["SOL"]["short_entry_high"] = round(r1, 2)
                LEVELS["SOL"]["target1"] = round(p, 2)
                LEVELS["SOL"]["long_zone"] = round(s1, 2)
                LEVELS["SOL"]["sl_short"] = round(r1 * 1.01, 2)
            elif key == "TAO":
                LEVELS["TAO"]["resistance"] = round(r1, 1)
                LEVELS["TAO"]["target1"] = round(p, 1)
                LEVELS["TAO"]["long_zone"] = round(s1, 1)
                LEVELS["TAO"]["long_sl"] = round(s1 * 0.98, 1)
            elif key == "ZEC":
                if "ZEC" not in LEVELS: LEVELS["ZEC"] = {}
                LEVELS["ZEC"]["resistance"] = round(r1, 2)
                LEVELS["ZEC"]["target1"] = round(p, 2)
                LEVELS["ZEC"]["long_zone"] = round(s1, 2)
                LEVELS["ZEC"]["long_sl"] = round(s1 * 0.98, 2)
            elif key == "BTC":
                LEVELS["BTC"]["resistance"] = round(r1, 0)
                LEVELS["BTC"]["support2"] = round(s1, 0)
            elif key == "ETH":
                if "ETH" not in LEVELS: LEVELS["ETH"] = {}
                LEVELS["ETH"]["long_zone"] = round(s1, 2)
                LEVELS["ETH"]["resistance"] = round(r1, 2)
                LEVELS["ETH"]["target1"] = round(p, 2)
                LEVELS["ETH"]["long_sl"] = round(s1 * 0.98, 2)
            
            print(f"✅ {key} R1: ${(r1 or 0.0):,.2f} | S1: ${(s1 or 0.0):,.2f}")
        except Exception as e:
            # Error silencioso de red para evitar spam en logs
            if "NameResolutionError" in str(e) or "Max retries exceeded" in str(e):
                print(f"⚠️ [Network] Error niveles {key} (DNS/Conexión)")
            else:
                print(f"❌ Error niveles {key}: {e}")

fired = {}

def get_alert_inline_keyboard(sym: str, side: str = "LONG") -> dict:
    """Delegado a alert_manager.get_alert_inline_keyboard — ver ese módulo."""
    import alert_manager
    return alert_manager.get_alert_inline_keyboard(sym, side)


def _answer_callback(callback_id: str, text: str = ""):
    """Delegado a alert_manager.answer_callback — ver ese módulo."""
    import alert_manager
    alert_manager.answer_callback(callback_id, text)


def _handle_callback(callback: dict, prices: dict):
    """Procesa inline keyboard callbacks de alertas de trading."""
    cb_id   = callback.get("id")
    data    = callback.get("data", "")
    msg_obj = callback.get("message", {})
    msg_id  = str(msg_obj.get("message_id", ""))
    chat_id = str(callback.get("from", {}).get("id", ""))

    if chat_id != str(TELEGRAM_CHAT_ID):
        return

    parts = data.split(":")
    action = parts[0]

    # ── Budget ──────────────────────────────────────────────────────────────
    if action == "budget":
        import ai_budget
        summary = ai_budget.get_budget_summary_html()
        send_telegram(summary)
        _answer_callback(cb_id, "💰 Budget actualizado")
        return

    # ── Status de posición ───────────────────────────────────────────────────
    if action == "status" and len(parts) >= 2:
        sym = parts[1]
        trade = tracker.get_last_open_trade(sym)
        if trade:
            p = prices.get(sym, 0.0)
            entry = trade["entry_price"]
            pnl_pct = ((p - entry) / entry * 100) if entry else 0.0
            if trade.get("type") == "SHORT":
                pnl_pct = -pnl_pct
            color = "🟢" if pnl_pct > 0 else "🔴"
            send_telegram(
                f"{color} <b>{sym} {trade['type']}</b> — Entrada: ${entry:,.2f}\n"
                f"Precio actual: <code>${p:,.2f}</code>\n"
                f"PnL flotante: <b>{pnl_pct:+.2f}%</b>",
                reply_to=msg_id,
            )
            _answer_callback(cb_id, f"PnL: {pnl_pct:+.2f}%")
        else:
            _answer_callback(cb_id, f"Sin posición abierta en {sym}")
        return

    # ── TP/SL outcome ────────────────────────────────────────────────────────
    if action in ("tp1", "tp2", "tp3", "sl") and len(parts) >= 3:
        sym  = parts[1]
        side = parts[2]
        trade = tracker.get_last_open_trade(sym)

        if not trade:
            _answer_callback(cb_id, f"No hay trade abierto en {sym}")
            return

        entry = trade["entry_price"]
        p     = prices.get(sym, 0.0)

        if action == "tp1":
            status = "PARTIAL_WON"
            label  = "TP1 (50% cerrado)"
            emoji  = "✅"
        elif action == "tp2":
            status = "PARTIAL_WON"
            label  = "TP2 (80% cerrado)"
            emoji  = "✅"
        elif action == "tp3":
            status = "FULL_WON"
            label  = "TP3 COMPLETO"
            emoji  = "🏆"
        else:  # sl
            status = "LOST"
            label  = "SL tocado"
            emoji  = "🛑"

        pnl_pct = ((p - entry) / entry * 100) if entry else 0.0
        if side == "SHORT":
            pnl_pct = -pnl_pct

        tracker.update_trade_status(trade["id"], status)
        close_position(sym, side)

        send_telegram(
            f"{emoji} <b>{label} — {sym} {side}</b>\n"
            f"Entrada: ${entry:,.2f} → Precio: <code>${p:,.2f}</code>\n"
            f"PnL registrado: <b>{pnl_pct:+.2f}%</b>\n"
            f"Estado: <code>{status}</code>",
            reply_to=msg_id,
        )
        _answer_callback(cb_id, f"{emoji} {label} registrado")
        print(f"[Callback] {sym} {side} → {status} ({pnl_pct:+.2f}%)")


def _handle_user_question(text: str, prices: dict):
    """
    Responde mensajes libres del usuario (saludos o preguntas sobre cripto)
    con un panel de 4 agentes, cada uno con score 1-5.
    """
    greetings = ["hola", "hi", "hello", "hey", "buenas", "buenos", "buen día", "saludos", "ola"]
    is_greeting = any(g in text.lower() for g in greetings)

    sym_map = {
        "btc": "BTC/USDT", "bitcoin": "BTC/USDT",
        "tao": "TAO/USDT", "bittensor": "TAO/USDT",
        "zec": "ZEC/USDT", "zcash": "ZEC/USDT",
        "eth": "ETH/USDT", "ethereum": "ETH/USDT",
    }
    detected_sym = None
    for k, v in sym_map.items():
        if k in text.lower():
            detected_sym = v
            break

    if is_greeting and not detected_sym:
        lines = ["👋 <b>¡Hola! Soy Zenith.</b> Aquí el pulso del mercado:\n"]
        for sym in ["BTC/USDT", "TAO/USDT", "ZEC/USDT"]:
            p   = prices.get(sym, 0)
            rsi = prices.get(f"{sym}_RSI", 50)
            arrow = "📈" if rsi < 45 else ("📉" if rsi > 55 else "↔️")
            lines.append(f"{arrow} <b>{sym.replace('/USDT','')}</b>: ${p:,.2f} | RSI {rsi:.1f}")
        lines.append("\n💬 Puedes preguntarme sobre BTC, TAO, ZEC o cualquier tema del mercado.")
        send_telegram("\n".join(lines), keyboard=get_main_menu("TAO"))
        return

    panel = gemini_analyzer.get_qa_panel(text, detected_sym, prices)
    sym_label = detected_sym.replace("/USDT", "") if detected_sym else "TAO"
    send_telegram(panel, keyboard=get_main_menu(sym_label))


def get_main_menu(symbol="ZEC"):
    """Delegado a alert_manager.get_main_menu — ver ese módulo."""
    import alert_manager
    return alert_manager.get_main_menu(symbol)

def send_telegram(msg: str, reply_to: str = None, keyboard: dict = None):
    """Delegado a alert_manager.send_telegram — ver ese módulo."""
    import alert_manager
    return alert_manager.send_telegram(msg, reply_to, keyboard)

def alert(key: str, msg: str, version: str = "V1-TECH", cooldown: int = 300,
          reply_to: str = None, inline_keyboard: dict = None):
    """Delegado a alert_manager.alert — ver ese módulo."""
    import alert_manager
    return alert_manager.alert(key, msg, version, cooldown, reply_to, inline_keyboard)

def calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d=8.0, side="LONG", elliott="", spy=0.0, oil=0.0, ob_detected=False):
    """
    Calcula un score de confluencia técnica + Macro (0-6 puntos). 
    V3.0: Añadido SMC (Order Block Detection).
    """
    score = 0
    # 1. RSI (2 pts)
    if side == "LONG":
        if rsi <= 30: score += 2
        elif rsi <= 40: score += 1
    else: # SHORT
        if rsi >= 70: score += 2
        elif rsi >= 60: score += 1
    
    # 2. EMA 200 Trend (1 pt)
    if (side == "LONG" and p > ema_200) or (side == "SHORT" and p < ema_200):
        score += 1
        
    # 3. Bollinger (1 pt)
    if (side == "LONG" and p <= bb_l * 1.01) or (side == "SHORT" and p >= bb_u * 0.99):
        score += 1
        
    # 4. USDT.D Bias (1 pt)
    if (side == "LONG" and usdt_d < 8.05) or (side == "SHORT" and usdt_d > 8.05):
        score += 1

    # 5. Elliott Wave Bonus/Penalización
    if "Onda 3" in elliott:
        score += 1
    elif "Corrección" in elliott or "Correctiva" in elliott:
        score -= 1  # Penalización por zona de indecisión (no bloqueo hard)
        
    # --- 6. MACRO BONUS (V2.1 - LONG ONLY BIAS) ---
    # Only rewards LONGs, ignore SHORTS for scoring
    if side == "LONG":
        if spy > 0:
            if usdt_d < 8.05: score += 1
            
        # Bonus Institucional Tech (NVDA + PLTR)
        nvda = GLOBAL_CACHE["macro_metrics"].get("nvda", 0)
        pltr = GLOBAL_CACHE["macro_metrics"].get("pltr", 0)
        
        if nvda > 0 and pltr > 0:
            score += 1

    # --- 7. SMC BONUS (V3.0 - SMART MONEY) ---
    if ob_detected:
        score += 1
            
    return min(6, score)

def get_confluence_badge(score):
    if score >= 4: return "💎 DIAMANTE (MAX CONFLUENCIA) 💎"
    if score == 3: return "🔥 ALTA CONVICCIÓN (CONFLUENTE) 🔥"
    return "⚡ SEÑAL ESTÁNDAR ⚡"

def build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy,
                              macro_dict, macro_status, atr, elliott, ob_detected,
                              social_adj, trade_type, phy_bias, conf_score,
                              strategy, side, rsi_threshold=42.0):
    """
    Construye un dict estructurado con exactamente qué condiciones dispararon la alerta.
    Se persiste como JSON en trigger_conditions para trazabilidad completa.
    """
    rsi_rising = rsi >= prev_rsi
    bb_zone = "lower" if p <= bb_l * 1.01 else "upper" if p >= bb_u * 0.99 else "range"
    above_ema200 = p > ema_200

    # Espejo de calculate_confluence_score para desglose punto a punto
    score_breakdown = {}
    if side == "LONG":
        score_breakdown["rsi_pts"] = 2 if rsi <= 30 else (1 if rsi <= 40 else 0)
    else:
        score_breakdown["rsi_pts"] = 2 if rsi >= 70 else (1 if rsi >= 60 else 0)
    score_breakdown["ema200_pt"] = 1 if ((side == "LONG" and above_ema200) or (side == "SHORT" and not above_ema200)) else 0
    score_breakdown["bb_pt"] = 1 if bb_zone in ("lower" if side == "LONG" else ("upper",)) else 0
    score_breakdown["usdt_d_pt"] = 1 if ((side == "LONG" and usdt_d < 8.05) or (side == "SHORT" and usdt_d > 8.05)) else 0
    score_breakdown["elliott_pt"] = 1 if "Onda 3" in elliott else (-1 if ("Corrección" in elliott or "Correctiva" in elliott) else 0)
    score_breakdown["ob_pt"] = 1 if ob_detected else 0
    score_breakdown["social_adj"] = round(social_adj, 3)

    return {
        "strategy": strategy,
        "side": side,
        "symbol": sym,
        "price": round(p, 4),
        # RSI
        "rsi": round(rsi, 2),
        "rsi_threshold": rsi_threshold,
        "rsi_ok": rsi <= rsi_threshold if side == "LONG" else rsi >= rsi_threshold,
        "rsi_rising": rsi_rising,
        # Bollinger
        "bb_zone": bb_zone,
        "bb_upper": round(bb_u, 4),
        "bb_lower": round(bb_l, 4),
        "bb_touch_ok": bb_zone == "lower" if side == "LONG" else bb_zone == "upper",
        # EMA 200
        "ema200": round(ema_200, 4),
        "above_ema200": above_ema200,
        "ema200_ok": above_ema200 if side == "LONG" else not above_ema200,
        # USDT Dominance
        "usdt_d": round(usdt_d, 3),
        "usdt_d_ok": usdt_d < 8.05 if side == "LONG" else usdt_d > 8.05,
        # ATR & Volatility
        "atr": round(atr, 4),
        "atr_pct": round(atr / p * 100, 2) if p else 0,
        # Elliott Wave
        "elliott": elliott,
        # SMC Order Block
        "ob_detected": ob_detected,
        # Social
        "social_adj": round(social_adj, 3),
        # Macro
        "macro_status": macro_status,
        "macro_1h": macro_dict.get("1H", "UNKNOWN"),
        "macro_4h": macro_dict.get("4H", "UNKNOWN"),
        "macro_1d": macro_dict.get("1D", "UNKNOWN"),
        # External macro
        "vix": round(vix, 2),
        "dxy": round(dxy, 2),
        # Trade classification
        "trade_type": trade_type,
        "phy_bias": phy_bias,
        # Score
        "conf_score": round(conf_score, 2),
        "score_breakdown": score_breakdown,
    }

def classify_trade(vix: float, dxy: float, macro_status: str) -> str:
    """
    Clasifica el trade como RAPIDA o SWING basado en contexto macro (metodología PTS).
    - RAPIDA: alta volatilidad, incertidumbre, usar posición 50% del normal
    - SWING: condiciones favorables, posición normal
    """
    if vix > 35:
        return "RAPIDA"  # Pánico extremo — tamaño mínimo
    if vix > 25:
        return "RAPIDA"  # Volatilidad elevada
    if dxy > 105 and macro_status != "BULL":
        return "RAPIDA"  # DXY fuerte presiona cripto
    return "SWING"

def is_position_open(sym: str, side: str) -> bool:
    """Verifica si ya existe una posición abierta para este símbolo+dirección."""
    key = f"{sym}_{side}"
    if key not in OPEN_POSITIONS:
        return False
    # Verificar TTL: si expiró, limpiar
    if time.time() - OPEN_POSITIONS[key] > POSITION_TTL:
        del OPEN_POSITIONS[key]
        return False
    return True

def open_position(sym: str, side: str):
    """Registra una posición como abierta."""
    OPEN_POSITIONS[f"{sym}_{side}"] = time.time()

def close_position(sym: str, side: str):
    """Marca una posición como cerrada."""
    OPEN_POSITIONS.pop(f"{sym}_{side}", None)

def format_confidence(score):
    """Mapea score 0-5 a porcentaje 60-100% para UX."""
    # 5 -> 100%, 4 -> 90%, 3 -> 80%, 2 -> 70%, 1 -> 60%, 0 -> 50%
    pct = 50 + (score * 10)
    return f"{pct}%"

def get_prices() -> dict:
    """Consolida llamadas priorizando Binance con Fallback a Caché y CoinGecko (Optimización V3.2)."""
    now = time.time()
    res = GLOBAL_CACHE["prices"].copy() 
    
    # 1. ¿Necesitamos actualizar precios? (Optimizado: 1 sola llamada)
    if now - GLOBAL_CACHE["last_update"]["prices"] > TTL_PRICES:
        symbols = ['ETH/USDT', 'BTC/USDT', 'TAO/USDT', 'ZEC/USDT', 'SOL/USDT', 'PAXG/USDT']
        try:
            # OPTIMIZACIÓN V3.2: fetch_tickers (Plural) es más eficiente que 4 llamadas separadas
            tickers = binance_ex.fetch_tickers(symbols)

            res["ETH"] = tickers.get('ETH/USDT', {}).get('last', res.get("ETH"))
            res["BTC"] = tickers.get('BTC/USDT', {}).get('last', res.get("BTC"))
            res["TAO"] = tickers.get('TAO/USDT', {}).get('last', res.get("TAO"))
            res["ZEC"] = tickers.get('ZEC/USDT', {}).get('last', res.get("ZEC"))
            res["SOL"] = tickers.get('SOL/USDT', {}).get('last', res.get("SOL"))
            res["GOLD"] = tickers.get('PAXG/USDT', {}).get('last', res.get("GOLD"))
            
            # Monitoreo de Carga (Opcional: X-MBX-USED-WEIGHT)
            weight = binance_ex.last_response_headers.get('X-MBX-USED-WEIGHT-1M', 'N/A')
            if weight != 'N/A' and int(weight) > 1000:
                print(f"⚠️ [API Alert] Binance Weight elevado: {weight}/1200")
            
            GLOBAL_CACHE["prices"].update(res)
            GLOBAL_CACHE["last_update"]["prices"] = now
            GLOBAL_CACHE["last_update"]["fail_count"] = 0 
        except Exception:
            # Silencioso: Fallback a CoinGecko o Caché
            GLOBAL_CACHE["last_update"]["fail_count"] += 1
            if GLOBAL_CACHE["last_update"]["fail_count"] > 10:
                print("⚠️ [Resilience Mode] Red inestable detectada. Usando datos previos.")
                GLOBAL_CACHE["last_update"]["fail_count"] = 0 

            try:
                # Fallback a CoinGecko
                ids = "ethereum,bittensor,bitcoin,pax-gold,zcash"
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
                cg_r = requests.get(url, timeout=10).json()
                res["ETH"] = cg_r.get("ethereum", {}).get("usd", res.get("ETH", 0.0))
                res["BTC"] = cg_r.get("bitcoin", {}).get("usd", res.get("BTC", 0.0))
                res["TAO"] = cg_r.get("bittensor", {}).get("usd", res.get("TAO", 0.0))
                res["SOL"] = cg_r.get("solana", {}).get("usd", res.get("SOL", 0.0))
                res["ZEC"] = cg_r.get("zcash", {}).get("usd", res.get("ZEC", 0.0))
                res["GOLD"] = cg_r.get("pax-gold", {}).get("usd", res.get("GOLD", 0.0))
                
                GLOBAL_CACHE["prices"].update(res)
                GLOBAL_CACHE["last_update"]["prices"] = now
            except:
                pass 

    # 2. Métricas Globales (TTL_GLOBAL)
    if now - GLOBAL_CACHE["last_update"]["global_metrics"] > TTL_GLOBAL:
        usdt_d, btc_d = indicators.get_global_metrics()
        GLOBAL_CACHE["global_metrics"] = {"usdt_d": usdt_d, "btc_d": btc_d}
        GLOBAL_CACHE["last_update"]["global_metrics"] = now
        
    res["USDT_D"] = GLOBAL_CACHE["global_metrics"]["usdt_d"]
    res["BTC_D"] = GLOBAL_CACHE["global_metrics"]["btc_d"]
    
    # 2.2 FEAR & GREED INDEX (Optimizado: 1x/10min)
    if now - GLOBAL_CACHE["last_update"]["global_metrics"] > TTL_GLOBAL:
        try:
            fg_r = requests.get("https://api.alternative.me/fng/", timeout=5).json()
            if fg_r.get("data"):
                val = fg_r["data"][0]
                GLOBAL_CACHE["fear_greed"] = {"value": int(val["value"]), "label": val["value_classification"]}
                # Mensaje Shadow si hay extrema miedo
                if int(val["value"]) < 20:
                    add_shadow_intel("BTC", f"EXTREMO MIEDO ({val['value']}). Oportunidad de acumulación institucional detectada.")
        except: pass
    
    res["FEAR_GREED"] = GLOBAL_CACHE["fear_greed"]

    # --- 2.5 MACRO SENTIMENT (SPY / OIL / DXY / VIX) ---
    if now - GLOBAL_CACHE["last_update"]["macro_metrics"] > TTL_MACRO:
        try:
            import math
            # S&P 500, Petróleo, Nvidia y Palantir — descargar individualmente para evitar MultiIndex
            macro_symbols = {"SPY": "spy", "CL=F": "oil", "NVDA": "nvda", "PLTR": "pltr"}
            macro_vals = {}
            for yf_sym, key in macro_symbols.items():
                try:
                    _df = yf.download(yf_sym, period="1d", interval="1m", progress=False)
                    if _df is not None and not _df.empty and 'Close' in _df.columns:
                        val = float(_df['Close'].iloc[-1])
                        macro_vals[key] = val if not math.isnan(val) else GLOBAL_CACHE["macro_metrics"].get(key, 0.0)
                    else:
                        macro_vals[key] = GLOBAL_CACHE["macro_metrics"].get(key, 0.0)
                except Exception:
                    macro_vals[key] = GLOBAL_CACHE["macro_metrics"].get(key, 0.0)

            spy_p = macro_vals["spy"]
            oil_p = macro_vals["oil"]
            nvda_p = macro_vals["nvda"]
            pltr_p = macro_vals["pltr"]

            # DXY + VIX (indicadores clave para clasificar trades como RAPIDA/SWING)
            dxy_p, vix_p = indicators.get_dxy_vix()

            GLOBAL_CACHE["macro_metrics"] = {
                "spy": float(spy_p), "oil": float(oil_p),
                "nvda": float(nvda_p), "pltr": float(pltr_p),
                "dxy": dxy_p, "vix": vix_p
            }
            GLOBAL_CACHE["last_update"]["macro_metrics"] = now
            print(f"🌍 [Macro Update] SPY: ${spy_p:.2f} | DXY: {dxy_p:.2f} | VIX: {vix_p:.1f}")
        except Exception as e:
            print(f"⚠️ Error Macro (Yahoo): {e}")

    res["SPY"] = GLOBAL_CACHE["macro_metrics"]["spy"]
    res["OIL"] = GLOBAL_CACHE["macro_metrics"]["oil"]
    res["DXY"] = GLOBAL_CACHE["macro_metrics"].get("dxy", 0.0)
    res["VIX"] = GLOBAL_CACHE["macro_metrics"].get("vix", 0.0)

    # 3. Datos Técnicos (TTL_INDICATORS para reducir carga)
    for sym in ["TAO", "BTC", "ZEC", "SOL", "ETH"]:
        last_ind_update = GLOBAL_CACHE["last_update"]["indicators"].get(sym, 0)
        
        if now - last_ind_update > TTL_INDICATORS:
            try:
                # V12.1: Guardamos el previo para la inercia (Hook)
                GLOBAL_CACHE["last_rsi"][sym] = (res.get(f"{sym}_RSI") or 50.0)

                rsi = indicators.get_rsi(sym, timeframe='15m')
                vals = indicators.get_indicators(sym, "15m")
                macro = indicators.get_macro_trend(sym)
                
                GLOBAL_CACHE["indicators"][sym] = {
                    "rsi": vals[0], "bb_u": vals[1], "bb_l": vals[3], 
                    "ema_200": vals[4], "atr": vals[5], "vol_sma": vals[6], 
                    "elliott": vals[7], "poc": vals[8], "macro": macro
                }
                GLOBAL_CACHE["last_update"]["indicators"][sym] = now
                
                # V15: Real Shadow Intel — Reportar POC al sidebar
                if vals[8] > 0:
                    add_shadow_intel(sym, f"POC detectado en ${vals[8]:,.2f}. Zona de interés institucional.")
            except Exception:
                # Silencioso: Se mantiene la caché previa
                pass

        # Inyectar desde caché (sea nueva o vieja)
        ind = GLOBAL_CACHE["indicators"].get(sym, {})
        res[f"{sym}_RSI"] = ind.get("rsi", 50.0)
        res[f"{sym}_BB_U"] = ind.get("bb_u")
        res[f"{sym}_BB_L"] = ind.get("bb_l")
        res[f"{sym}_EMA_200"] = ind.get("ema_200", 0.0)
        res[f"{sym}_ATR"] = ind.get("atr", 0.0)
        res[f"{sym}_VOL_SMA"] = ind.get("vol_sma", 0.0)
        res[f"{sym}_MACRO"] = ind.get("macro", {"consensus": "NEUTRAL", "1H": "UNKNOWN", "4H": "UNKNOWN"})
        res[f"{sym}_ELLIOTT"] = ind.get("elliott", "")
        res[f"{sym}_POC"] = ind.get("poc", 0.0)

    return res

def check_market_pulse(prices):
    """Detecta apertura/cierre NYSE y envía análisis híbrido."""
    now = datetime.now()
    # NYSE: 9:30 AM / 4:00 PM EST (Aproximado según servidor del usuario)
    # 09:30 Local (Apertura) | 16:00 Local (Cierre)
    is_open = now.hour == 9 and now.minute == 30
    is_close = now.hour == 16 and now.minute == 0
    
    if not (is_open or is_close):
        return
        
    event = "APERTURA" if is_open else "CIERRE"
    print(f"📡 [Market Pulse] Detectado evento de {event}")
    
    for sym in ["SOL", "BTC"]:
        p, rsi = prices[sym], prices[f"{sym}_RSI"]
        bb_u, bb_l = prices[f"{sym}_BB_U"], prices[f"{sym}_BB_L"]
        ema_200 = prices[f"{sym}_EMA_200"]
        atr = prices[f"{sym}_ATR"]
        usdt_d = prices["USDT_D"]
        
        analysis = gemini_analyzer.get_market_pulse_analysis(
            sym, p, "Neutral", rsi, bb_u, bb_l, ema_200, atr, usdt_d
        )
        
        msg = (f"📡 <b>PULSO DE MERCADO (NYSE {event})</b>\n\n"
               f"🪙 <b>{sym}</b> @ ${(p or 0.0):,.2f}\n"
               f"📊 RSI: {(rsi or 0.0):.1f} | EMA: {'ALCISTA' if (p or 0.0) > (ema_200 or 0.0) else 'BAJISTA'}\n"
               f"💰 Volatilidad: {(atr or 0.0):,.2f} USD\n\n"
               f"🤖 <b>ANÁLISIS HÍBRIDO AI:</b>\n<i>{safe_html(analysis)}</i>")
        
        # Enviamos alerta única (no trackeamos como trade)
        alert(f"pulse_{sym}_{event}_{now.date()}", msg)

def check_strategies(prices: dict):
    if not prices: return
    phase = get_phase()
    usdt_d = prices.get("USDT_D", 8.0)
    
    for sym in ["ZEC", "TAO", "ETH"]:
        p = prices.get(sym, 0.0)
        rsi = prices.get(f"{sym}_RSI", 50.0)
        
        # Validación de integridad de datos
        if not p or p == 0:
            continue
            
        bb_u = prices.get(f"{sym}_BB_U", p * 1.01)
        bb_l = prices.get(f"{sym}_BB_L", p * 0.99)
        ema_200 = prices.get(f"{sym}_EMA_200", p)
        atr = prices[f"{sym}_ATR"]
        vol_sma = prices[f"{sym}_VOL_SMA"]
        macro_raw = prices.get(f"{sym}_MACRO")
        if isinstance(macro_raw, dict):
            macro_dict = macro_raw
        else:
            macro_dict = {"consensus": "NEUTRAL", "1H": "UNKNOWN", "4H": "UNKNOWN"}
            
        macro_status = macro_dict.get("consensus", "NEUTRAL")
        gold_price = prices.get("GOLD", 0.0)
        btc_d = prices.get("BTC_D", 50.0)
        elliott = prices.get(f"{sym}_ELLIOTT", "Analizando...")
        
        L = LEVELS.get(sym)
        
        # Bloqueo Institucional (Alineación Macro)
        if phase == "SHORT" and macro_status == "BULL":
            continue
        if phase == "LONG" and macro_status == "BEAR":
            continue
            
        # Contexto visual de indicadores
        bb_ctx = "🔝 Techo BB" if p >= bb_u * 0.99 else "🩸 Suelo BB" if p <= bb_l * 1.01 else "↕️ Rango"
        trend_ctx = "📈 TENDENCIA ALCISTA" if p > ema_200 else "📉 TENDENCIA BAJISTA"
        macro_ctx = f"🌍 MACRO: {macro_status} (1H:{macro_dict['1H']} | 4H:{macro_dict['4H']})"
        elliott_ctx = f"🌊 ONDA ELLIOTT: {elliott}"

        # --- GUARDIÁN ZEC (ANTI-VOLATILIDAD) ---
        if sym == "ZEC" and phase == "LONG":
            vol_ratio = (atr / p) * 100
            if vol_ratio > 3.5:
                # Bloqueo por riesgo de manipulación o mecha de salida en news
                print(f"⚠️ [ZEC Guard] Volatilidad extrema ({vol_ratio:.1f}%). Ignorando Long por seguridad.")
                continue

        # --- FILTRO V1.6.1 AUDIT: REDUCCIÓN DE RUIDO ---
        # Wave 4 Correction es parte normal de un impulso 5-ondas.
        # Convertido a flag — penaliza confluencia pero NO bloquea el trade.
        elliott_is_correction = "Corrección" in elliott or "Correctiva" in elliott

        # Inicializar SMC variables para este ciclo (evita NameError si el path SMC no se ejecuta)
        ob_detected = False
        obs = []
        social_adj = 0.0

        vix = prices.get("VIX", 0.0)
        dxy = prices.get("DXY", 0.0)
        trade_type = classify_trade(vix, dxy, macro_status)
        
        # --- 2. PHY BIAS & FIBONACCI (PTS Intelligence) ---
        phy_bias = indicators.detect_head_and_shoulders(sym)
        fib_levels = indicators.get_fibonacci_levels(sym)
        
        # Ajustar trade_type si hay H&S detectado (Modo Alerta)
        if phy_bias != "NONE":
            trade_type = "RAPIDA"
            print(f"👁️ [PHY ALERT] {sym} detectó {phy_bias} — forzando modo RAPIDA")

        # --- 3. SOCIAL INTELLIGENCE (con TTL de 600s) ---
        now_ts = time.time()
        cached_social = GLOBAL_CACHE["social_intel"].get(sym, {"score": 0.0, "last_update": 0})
        
        if now_ts - cached_social["last_update"] > TTL_SOCIAL:
            try:
                import social_analyzer
                _, score_num = social_analyzer.get_social_intel(sym, p)
                # Normalizar: score_num suele ser 0-10 o algo así? 
                # El plan dice: ajuste conf_score (+0.5 si bullish y es LONG, -0.5 si bearish)
                # Supongamos que social_analyzer retorna score de -1 a 1 
                # El plan dice: Ajustar conf_score: +0.5 si bullish y es LONG, -0.5 si bearish
                # social_adj = round(social_score * 0.5, 2)  # máximo ±0.5 puntos
                social_adj = round(score_num * 0.5, 2)
                GLOBAL_CACHE["social_intel"][sym] = {"score": social_adj, "last_update": now_ts}
            except Exception as e:
                print(f"⚠️ Error Social Analyzer: {e}")
                social_adj = cached_social["score"]
        else:
            social_adj = cached_social["score"]

        # --- ESTRATEGIA V12.1: CONFLUENCE + RSI HOOK ---
        prev_rsi = GLOBAL_CACHE["last_rsi"].get(sym, 50.0)
        
        # SHORT logic disabled — bot en modo LONG FOCUS institucional

        # --- ESTRATEGIA V3: REVERSAL / INTRADIA (AGRESIVA) ---
        if phase == "LONG" and p < ema_200:
            # --- MODO RESCATE TAO ---
            reversal_rsi = 28.0 if sym == "TAO" else 26.0
            if rsi <= reversal_rsi: # Umbral más bajo para "Hook"
                register_signal_event(sym.replace("/USDT", ""), prices)
                side = "LONG"
                conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"))
                conf_score = round(conf_score + social_adj, 2)
                
                # Gestión más amplia para Intradía (2:1 R:R)
                sl_dist = max(atr * 2.0, p * 0.008) # SL más amplio para aguantar la base
                sl = round(p - sl_dist, 2)
                tp1 = round(p + (sl_dist * 2.0), 2)
                tp2 = round(p + (sl_dist * 3.5), 2)
                
                msg = (f"🏛️ <b>SEÑAL V3: INTRADÍA REVERSAL (15m-1H)</b> 🏛️\n\n"
                       f"🌊 Onda: {elliott}\n"
                       f"⭐ <b>Confiabilidad: {format_confidence(conf_score)}</b>\n\n"
                       f"💬 <i>Buscando el rebote a la media (EMA 200) tras agotamiento.</i>\n\n"
                       f"🪙 <b>{sym}</b> @ ${p:,.2f}\n"
                       f"🎯 TP1: <b>${tp1:,.2f}</b> (2:1)\n"
                       f"🎯 TP2: <b>${tp2:,.2f}</b> (3.5:1)\n"
                       f"🛑 SL: <b>${sl:,.2f}</b>\n\n"
                       f"🎙️ <b>DEBATE DEL CUADRANTE ZENITH:</b>\n"
                       f"{gemini_analyzer.get_ai_consensus(sym, p, 'LONG', rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'), vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias)}")
                # Guard: no disparar si ya hay posición abierta
                if is_position_open(sym, "LONG"):
                    print(f"⏸️ [Position Guard] {sym} LONG (Reversal) ya está abierto — omitiendo señal duplicada")
                    continue

                mid = alert(f"{sym}_v3_reversal", msg, version="V1-TECH",
                            inline_keyboard=get_alert_inline_keyboard(sym, "LONG"))
                if mid:
                    open_position(sym, "LONG")
                    _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, conf_score, "v3_reversal", "LONG", rsi_threshold=reversal_rsi)
                    tracker.log_trade(sym, "LONG", p, tp1, tp2, sl, mid, "V1-TECH", rsi, bb_ctx, atr, elliott, conf_score, alert_type="v3_reversal", trigger_conditions=_tc)
                    gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")
                    register_signal_event(sym.replace("/USDT", ""), prices)

        # Long V1 (Trend Alcista + Near BB + RSI 42 + RSI Rising)
        elif phase == "LONG" and p > ema_200 and "BB" in bb_ctx:
            # --- MODO PROACTIVO ZEC ---
            entry_rsi = 48.0 if sym == "ZEC" else 42.0
            if rsi <= entry_rsi:
                if rsi < prev_rsi: # RSI sigue cayendo, no entramos (Falling Knife)
                    continue

                # Guard: no disparar si ya hay posición LONG abierta para este símbolo
                if is_position_open(sym, "LONG"):
                    print(f"⏸️ [Position Guard] {sym} LONG ya está abierto — omitiendo señal duplicada")
                    continue

                # Gestión ATR: SL a 2.0 * ATR (V12.0)
                sl_dist = max(atr * 2.0, p * 0.007)
                sl = round(p - sl_dist, 2)
                tp1 = round(p + (sl_dist * 2.0), 2)
                tp2 = round(p + (sl_dist * 3.5), 2)
                caution = "⚠️ *PRECAUCIÓN: USDT.D ALTO*\n" if usdt_d > 8.05 else ""

                side = "LONG"
                conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"))
                conf_score = round(conf_score + social_adj, 2)

                if conf_score < 4:
                    print(f"⏩ [V12-Audit] Señal {sym} ignorada (Score {conf_score} < 4)")
                    continue

                badge = get_confluence_badge(conf_score)
                trade_label = "⚡ RAPIDA (VIX alto)" if trade_type == "RAPIDA" else "📈 SWING"

                msg = (f"{badge}\n\n"
                       f"🚀 <b>SEÑAL V1.6.2 SCALP (15m)</b> 🚀\n\n"
                       f"🌍 {macro_ctx}\n"
                       f"🌊 {elliott_ctx}\n"
                       f"🛡️ <b>SMC SHIELD:</b> {'🟢 DETECTED' if ob_detected else '⚪ NONE'}\n\n"
                       f"📈 15m Trend: {trend_ctx}\n"
                       f"💰 Volatilidad: {atr:,.2f} USD\n\n"
                       f"📊 <b>ESTADO TÉCNICO:</b>\n"
                       f"• RSI: {(rsi or 0.0):.1f} | BB: {bb_ctx}\n"
                       f"• EMA 200: ${(ema_200 or 0.0):,.2f}\n"
                       f"⭐ <b>Confiabilidad: {format_confidence(conf_score)}</b>\n\n"
                       f"🌍 <b>CONTEXTO MACRO:</b>\n"
                       f"• USDT.D: {usdt_d}% | BTC.D: {btc_d}%\n"
                       f"• DXY: {dxy:.2f} | VIX: {vix:.1f}\n"
                       f"• Tipo Operación: {trade_label}\n\n"
                       f"🪙 <b>{sym}</b> @ ${(p or 0.0):,.2f}\n"
                       f"🎯 TP1: <b>${(tp1 or 0.0):,.2f}</b> (2:1)\n"
                       f"🎯 TP2: <b>${(tp2 or 0.0):,.2f}</b> (3:1)\n"
                       f"🛑 SL: <b>${(sl or 0.0):,.2f}</b>\n\n"
                       f"🎙️ <b>DEBATE DEL CUADRANTE ZENITH:</b>\n"
                       f"{gemini_analyzer.get_ai_consensus(sym, p, 'LONG', rsi, usdt_d, spy=prices.get('SPY', 0), oil=prices.get('OIL', 0), nvda=prices.get('NVDA', 0), pltr=prices.get('PLTR', 0), vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias)}")
                mid = alert(f"{sym}_v1_long", msg, version="V1-TECH",
                            inline_keyboard=get_alert_inline_keyboard(sym, "LONG"))
                if mid:
                    open_position(sym, "LONG")
                    _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, conf_score, "v1_long", "LONG", rsi_threshold=entry_rsi)
                    tracker.log_trade(sym, "LONG", p, tp1, tp2, sl, mid, "V1-TECH", rsi, bb_ctx, atr, elliott, conf_score, alert_type="v1_long", trigger_conditions=_tc)
                    gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")
                    register_signal_event(sym.replace("/USDT", ""), prices)

                # --- ESTRATEGIA V2-AI: CONSENSUS MASTER (HYBRID) ---
                decision, reason, full_analysis = gemini_analyzer.get_ai_decision(sym, p, phase, rsi, bb_u, bb_l, "V2-AI", usdt_d, conf_score, vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, fib_levels=fib_levels)
                
                if decision == "CONFIRM":
                    # Guard: Re-verificar posición abierta antes de ejecutar orden real
                    if is_position_open(sym, side):
                        print(f"⏸️ [Position Guard] {sym} {side} (V2-AI) ya está abierto — omitiendo ejecución binance")
                        continue

                    conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"), ob_detected=ob_detected)
                    conf_score = round(conf_score + social_adj, 2)
                    badge = get_confluence_badge(conf_score)
                    
                    # --- V6.0 MULTI-TP CALCULATION ---
                    dist_sl = abs(p - sl)
                    tp1 = round(p + (dist_sl * 2.0) if side == "LONG" else p - (dist_sl * 2.0), 2)
                    tp2 = round(p + (dist_sl * 4.0) if side == "LONG" else p - (dist_sl * 4.0), 2)
                    tp3 = round(p + (dist_sl * 7.0) if side == "LONG" else p - (dist_sl * 7.0), 2)

                    # --- V6.0 EXECUTION LAYER (BINANCE) ---
                    exec_report = "⚪ NO EJECUTADO (Bajo Conf_Score)"
                    if conf_score >= 4:
                        if not GLOBAL_CACHE["executor"]:
                            GLOBAL_CACHE["executor"] = trading_executor.ZenithExecutor()
                        
                        res_exec = GLOBAL_CACHE["executor"].execute_bracket_order(sym, side, p, tp1, tp2, sl, tp3=tp3)
                        exec_report = f"💸 <b>BINANCE V6:</b> {res_exec.get('status')} (ID: {res_exec.get('id')})"

                    msg = (f"{badge}\n\n"
                           f"🚀 <b>ZENITH V6: THE VOLUME PROPHET</b>\n"
                           f"🛡️ <b>SMC SHIELD:</b> {'🟢 DETECTED' if (ob_detected if 'ob_detected' in locals() else False) else '⚪ NONE'}\n"
                           f"🧲 <b>POC MAGNET:</b> ${prices.get(f'{sym}_POC', 0.0):,.2f}\n"
                           f"{exec_report}\n\n"
                           f"📊 <b>ESTADO TÉCNICO:</b>\n"
                           f"• Score Confluencia: {conf_score}/5\n"
                           f"⭐ <b>Confiabilidad: {format_confidence(conf_score + 1)}</b>\n\n"
                           f"💡 <b>RAZÓN IA:</b> {safe_html(reason)}\n\n"
                           f"🪙 <b>{sym}</b> @ ${(p or 0.0):,.2f}\n"
                           f"🎯 TP1 (50%): <b>${(tp1 or 0.0):,.2f}</b>\n"
                           f"🎯 TP2 (25%): <b>${(tp2 or 0.0):,.2f}</b>\n"
                           f"🎯 TP3 (25%): <b>${(tp3 or 0.0):,.2f}</b>\n"
                           f"🛑 SL: <b>${(sl or 0.0):,.2f}</b>\n\n"
                           f"🎙️ <b>DEBATE DEL CUADRANTE ZENITH:</b>\n"
                           f"{gemini_analyzer.get_ai_consensus(sym, p, phase, rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'), vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias)}")
                    mid = alert(f"{sym}_v2_ai_{phase}", msg, version="V2-AI",
                                inline_keyboard=get_alert_inline_keyboard(sym, phase))
                    if mid:
                        open_position(sym, phase)
                        _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, conf_score, "v2_ai_long", phase, rsi_threshold=entry_rsi)
                        tracker.log_trade(sym, phase, p, tp1, tp2, sl, mid, "V2-AI", rsi, bb_ctx, atr, elliott, conf_score, ai_analysis=full_analysis, macro_bias=macro_status, alert_type="v2_ai_long", trigger_conditions=_tc)
                        register_signal_event(sym.replace("/USDT", ""), prices)

        # --- ESTRATEGIA V2: AI ENHANCED (LONG ONLY) ---
        if rsi <= 40:
            side = "LONG"
            # SMC Filter: Check for Order Blocks
            df = indicators.get_df(sym, "1h")
            obs = indicators_swing.find_order_blocks(df)
            ob_detected = any(ob["type"] == "BULL_OB" and p >= ob["low"] * 0.99 and p <= ob["high"] * 1.01 for ob in obs)
            
            # 1. Consultamos a ambos agentes para buscar CONSENSO
            # El filtro EMA es global: no confirmamos si va contra tendencia
            is_valid_trend = (side == "LONG" and p > ema_200) or (side == "SHORT" and p < ema_200)
            
            if is_valid_trend:
                dec_cons, reason_cons, full_cons = gemini_analyzer.get_ai_decision(sym, p, side, rsi, bb_u, bb_l, version="V1-TECH", usdt_d=usdt_d, vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, fib_levels=fib_levels)
                dec_scalp, reason_scalp, full_scalp = gemini_analyzer.get_ai_decision(sym, p, side, rsi, bb_u, bb_l, version="V2-AI", usdt_d=usdt_d, vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, fib_levels=fib_levels)
                full_analysis = f"Consenso:\n{full_cons}\n\n{full_scalp}"
            else:
                dec_cons, dec_scalp, full_analysis = "REJECT", "Contra tendencia mayor", ""

            if dec_cons == "CONFIRM" or dec_scalp == "CONFIRM":
                # Guard: no disparar si ya hay posición abierta
                if is_position_open(sym, side):
                    print(f"⏸️ [Position Guard] {sym} {side} (Consenso IA) ya está abierto — omitiendo señal duplicada")
                    continue

                is_consensus = (dec_cons == "CONFIRM" and dec_scalp == "CONFIRM")
                # Cálculo de gestión de riesgo dinámico (R:R 2:1)
                sl = L.get('sl_short', p*1.01) if side == "SHORT" else L.get('long_sl', p*0.99)
                dist_sl = abs(p - sl)
                tp1 = round(p - (dist_sl * 2.0) if side == "SHORT" else p + (dist_sl * 2.0), 2)
                tp2 = round(p - (dist_sl * 3.0) if side == "SHORT" else p + (dist_sl * 3.0), 2)
                
                header = "🔹💎🔹 <b>CONSENSO IA</b>" if is_consensus else "🤖 <b>IA CONFIRMADA</b>"
                icon = "💎" if side == "LONG" else "💀"
                caution = "⚠️ <b>CONTEXTO TENSO</b>\n" if side == "LONG" and usdt_d > 8.05 else ""
                
                # Razón combinada si hay consenso
                final_reason = reason_scalp if dec_scalp == "CONFIRM" else reason_cons
                if is_consensus: final_reason = f"Acuerdo Total: {reason_cons} + {reason_scalp}"

                msg = (f"{header} ({side})\n"
                       f"{caution}"
                       f"🛡️ <b>SMC SHIELD:</b> {'🟢 DETECTED' if (ob_detected if 'ob_detected' in locals() else False) else '⚪ NONE'}\n\n"
                       f"💬 <i>{safe_html(final_reason)}</i>\n\n"
                       f"🪙 <b>{sym}</b> @ ${(p or 0.0):,.2f}\n"
                       f"📊 RSI: {(rsi or 0.0):.1f} | {bb_ctx}\n"
                       f"📉 USDT.D: {(usdt_d or 0.0):.2f}%\n"
                       f"🎯 TP1: <b>${(tp1 or 0.0):,.2f}</b> (2:1)\n"
                       f"🎯 TP2: <b>${(tp2 or 0.0):,.2f}</b> (3:1)\n"
                       f"🛑 SL: <b>${(sl or 0.0):,.2f}</b>\n\n"
                       f"🎙️ <b>DEBATE DEL CUADRANTE ZENITH:</b>\n"
                       f"{gemini_analyzer.get_ai_consensus(sym, p, side, rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'), vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias)}")
                
                mid = alert(f"{sym}_v2_short", msg, version="V2-AI")
                if mid:
                    _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, 5 if is_consensus else 4, "v2_ai_consensus", side, rsi_threshold=40.0)
                    tracker.log_trade(sym, phase, p, tp1, tp2, sl, mid, "V2-AI", rsi, bb_ctx, atr, elliott, 5 if is_consensus else 4, ai_analysis=full_analysis, macro_bias=macro_status, alert_type="v2_ai_consensus", trigger_conditions=_tc)
                    gemini_analyzer.log_alert_to_context(sym, side, p, rsi, tp1, sl, "V2-AI")

        # --- ALERTAS ESTRATÉGICAS: USDT.D BREAKOUT (V15: Institutional Grade) ---
        for level in [8.08, 8.044, 7.953]:
            if abs(usdt_d - level) < 0.005:
                # Clasificar dirección del movimiento (breakout vs. rechazo)
                prev_usdt_d = GLOBAL_CACHE["prices"].get("USDT_D_PREV", usdt_d)
                direction = "🔺 SUBIENDO" if usdt_d >= prev_usdt_d else "🔻 CAYENDO"
                
                # Contexto por nivel institucional
                if level == 8.08:
                    nivel_nombre = "🚨 ZONA DE PÁNICO"
                    desc_corta = "Presión vendedora institucional máxima"
                    impacto = "BEAR para crypto. Capital huyendo a stablecoins."
                    accion_zec = "⛔ EVITAR longs. Esperar rechazo confirmado en este nivel."
                    accion_btc = "👀 BTC puede rebotear si este nivel actúa como resistencia de USDT.D."
                    emoji_nivel = "🔴"
                elif level == 8.044:
                    nivel_nombre = "⚠️ ZONA DE TENSIÓN"
                    desc_corta = "Incertidumbre y probable rotación"
                    impacto = "NEUTRAL/BEAR. Mercado buscando dirección."
                    accion_zec = "⏳ Reducir tamaño de posición. Esperar confirmación macro."
                    accion_btc = "📊 BTC Dominancia clave: si sube junto a USDT.D, hedge activo."
                    emoji_nivel = "🟡"
                else:  # 7.953
                    nivel_nombre = "✅ ZONA DE EUFORIA"
                    desc_corta = "Capital fluyendo hacia activos de riesgo"
                    impacto = "BULL para crypto. Instituciones entrando al mercado."
                    accion_zec = "🚀 OPORTUNIDAD: Buscar setups de acumulación en ZEC/TAO."
                    accion_btc = "💎 BTC en zona de acumulación. Alerta V1 probable en próximas horas."
                    emoji_nivel = "🟢"

                # Contexto de activos en tiempo real
                zec_rsi = prices.get("ZEC_RSI", 50.0)
                tao_rsi = prices.get("TAO_RSI", 50.0)
                btc_rsi = prices.get("BTC_RSI", 50.0)
                
                msg = (
                    f"{emoji_nivel} <b>USDT.D INSTITUCIONAL: {nivel_nombre}</b>\n\n"
                    f"📍 Nivel: <b>{level}%</b> {direction}\n"
                    f"📊 Actual: <b>{usdt_d:.3f}%</b> | BTC.D: <b>{btc_d:.1f}%</b>\n"
                    f"💨 VIX: {vix:.1f} | DXY: {dxy:.2f}\n\n"
                    f"🔬 <b>DIAGNÓSTICO:</b>\n"
                    f"<i>{desc_corta}</i>\n"
                    f"📈 Impacto: {impacto}\n\n"
                    f"📊 <b>PULSO DE ACTIVOS:</b>\n"
                    f"• BTC RSI: {btc_rsi:.1f} | BB: {bb_ctx}\n"
                    f"• ZEC RSI: {zec_rsi:.1f}\n"
                    f"• TAO RSI: {tao_rsi:.1f}\n\n"
                    f"🎯 <b>PLAYBOOK INSTITUCIONAL:</b>\n"
                    f"• {accion_zec}\n"
                    f"• {accion_btc}"
                )
                alert(f"usdtd_break_{level}", msg, version="MACRO", cooldown=3600)

def monitor_open_trades(prices: dict):
    open_trades = tracker.get_open_trades()
    for t in open_trades:
        sym = t["symbol"]
        if sym not in prices: continue
        curr_p, tipo, reply = prices[sym], t["type"], t["msg_id"]
        rsi = prices.get(f"{sym}_RSI", 50.0)
        bb_u = prices.get(f"{sym}_BB_U", curr_p * 1.01)
        bb_l = prices.get(f"{sym}_BB_L", curr_p * 0.99)
        bb_ctx = "🔝 Techo BB" if curr_p >= bb_u * 0.99 else "🩸 Suelo BB" if curr_p <= bb_l * 1.01 else "↕️ Rango"
        
        # Calcular PnL flotante
        entry = t["entry_price"]
        if tipo == "LONG":
            pnl_pct = ((curr_p - entry) / entry * 100) if entry else 0.0
        else:
            pnl_pct = ((entry - curr_p) / entry * 100) if entry else 0.0
        
        # V5.1: High-Fidelity Intel (RVOL & ATR Trailing SL)
        df_1h = indicators.get_df(sym, '1h', 50)
        rvol = indicators.calculate_rvol(df_1h)
        atr = indicators.calculate_atr(df_1h) # Re-calcular ATR actual
        tsl = indicators.calculate_atr_trailing_stop(curr_p, atr, side=tipo, multiplier=2.5)

        # V5.0: Log PNL to console for pure trading monitor
        if abs(pnl_pct) > 1.0:
            print(f"📈 [Trade Monitor] {sym} {tipo}: {pnl_pct:+.2f}% | RVOL: {rvol} | TSL: {tsl}")

        if tipo == "SHORT":
            if curr_p >= t["sl_price"]:
                tracker.update_trade_status(t["id"], "LOST")
                # Neural Audit V4.0
                lesson = gemini_analyzer.trigger_shadow_post_mortem(sym, curr_p, "LOST", rsi, "Post-Mortem SL (Short)")
                if lesson: send_telegram(f"🧠 <b>NEURAL LEARNING (V4.0)</b>\n<i>{lesson}</i>", reply_to=reply)
                msg = (f"🔴 <b>STOP LOSS TOCADO (POST-MORTEM)</b>\n\n"
                       f"🪙 {sym} SHORT\n"
                       f"💸 PnL: <b>{(pnl_pct or 0.0):+.2f}%</b>\n"
                       f"📊 <b>Contexto de Cierre:</b>\n"
                       f"• RSI: {(t.get('rsi_entry') or 50.0):.1f} (Inicio) → {(rsi or 0.0):.1f} (Actual)\n"
                       f"• Bollinger: {bb_ctx}\n"
                       f"• Motivo: El precio superó el techo proyectado.")
                alert(f"t_{t['id']}_l", msg, version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "LOST", t["entry_price"], curr_p)
            elif t["tp2_price"] > 0 and curr_p <= t["tp2_price"]:
                tracker.update_trade_status(t["id"], "FULL_WON")
                msg = (f"🟢 <b>TP2 ALCANZADO (STRIKE!)</b>\n\n"
                       f"🪙 {sym} SHORT\n"
                       f"💰 PnL: <b>{(pnl_pct or 0.0):+.2f}%</b>\n"
                       f"📊 <b>Resumen:</b>\n"
                       f"• RSI Entrada: {(t.get('rsi_entry') or 50.0):.1f}\n"
                       f"• RSI Cierre: {(rsi or 0.0):.1f}\n"
                       f"✨ El indicador predijo el retroceso correctamente.")
                alert(f"t_{t['id']}_w", msg, version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "WIN_FULL", t["entry_price"], curr_p)
            elif t["tp1_price"] > 0 and curr_p <= t["tp1_price"] and t["status"] == "OPEN":
                tracker.update_trade_status(t["id"], "PARTIAL_WON")
                # V12.1: BE con seguro (0.1% Profit)
                new_sl = round(t["entry_price"] * 0.999, 2)
                tracker.update_sl(t["id"], new_sl) 
                alert(f"t_{t['id']}_p", f"🟡 <b>TP1 ASEGURADO</b>\nTrailing BE (0.1%) Activado. Riesgo eliminado.", version=t["version"], reply_to=reply)
        elif tipo == "LONG":
            if curr_p <= t["sl_price"]:
                tracker.update_trade_status(t["id"], "LOST")
                # Neural Audit V4.0
                lesson = gemini_analyzer.trigger_shadow_post_mortem(sym, curr_p, "LOST", rsi, "Post-Mortem SL (Long)")
                if lesson: send_telegram(f"🧠 <b>NEURAL LEARNING (V4.0)</b>\n<i>{lesson}</i>", reply_to=reply)
                msg = (f"🔴 <b>STOP LOSS TOCADO (POST-MORTEM)</b>\n\n"
                       f"🪙 {sym} LONG\n"
                       f"💸 PnL: <b>{(pnl_pct or 0.0):+.2f}%</b>\n"
                       f"📊 <b>Contexto de Cierre:</b>\n"
                       f"• RSI: {(t.get('rsi_entry') or 50.0):.1f} (Inicio) → {(rsi or 0.0):.1f} (Actual)\n"
                       f"• Bollinger: {bb_ctx}\n"
                       f"• Motivo: Soporte perforado, el impulso falló.")
                alert(f"t_{t['id']}_l", msg, version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "LOST", t["entry_price"], curr_p)
            elif t["tp2_price"] > 0 and curr_p >= t["tp2_price"]:
                tracker.update_trade_status(t["id"], "FULL_WON")
                msg = (f"🟢 <b>TP2 ALCANZADO (STRIKE!)</b>\n\n"
                       f"🪙 {sym} LONG\n"
                       f"💰 PnL: <b>{(pnl_pct or 0.0):+.2f}%</b>\n"
                       f"📊 <b>Resumen:</b>\n"
                       f"• RSI Entrada: {(t.get('rsi_entry') or 50.0):.1f}\n"
                       f"• RSI Cierre: {(rsi or 0.0):.1f}\n"
                       f"✨ Rebote técnico capturado con éxito.")
                alert(f"t_{t['id']}_w", msg, version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "WIN_FULL", t["entry_price"], curr_p)
            elif t["tp1_price"] > 0 and curr_p >= t["tp1_price"] and t["status"] == "OPEN":
                tracker.update_trade_status(t["id"], "PARTIAL_WON")
                # V12.1: BE con seguro (0.1% Profit)
                new_sl = round(t["entry_price"] * 1.001, 2)
                tracker.update_sl(t["id"], new_sl)
                alert(f"t_{t['id']}_p", f"🚀 <b>TP1 ASEGURADO</b>\nTrailing BE (0.1%) Activado. Fondos protegidos.", version=t["version"], reply_to=reply)

def check_user_queries(prices: dict):
    """Delegado a telegram_commands.py — ver ese archivo para la lógica de comandos."""
    import telegram_commands
    telegram_commands.check_user_queries(prices)


def trigger_salmos_prophecy(prices):
    """Salmos analiza el mercado buscando la confluencia perfecta (Wave 3/5 + RSI)."""
    try:
        print("🔔 Salmos: Buscando profecía de tendencia...")
        # Buscamos el mejor setup para Salmos
        setup = gemini_analyzer.get_top_setup(prices)
        if "LONG" in setup or "🟢" in setup:
             msg = (f"🔔 <b>PROFÉCIA DE SALMOS: THE BULLISH PULSE</b>\n\n"
                    f"{safe_html(setup)}\n\n"
                    f"💡 <i>Salmos confirma confluencia técnica e institucional. Sesgo alcista validado por la cuadrilla.</i>")
             send_telegram(msg)
    except Exception as e:
        print(f"❌ Error en profecía de Salmos: {e}")

def main():
    print("🚀 Scalp Alert Bot V3 (AI Panorama) - INICIANDO")
    update_dynamic_levels()
    
    # Control de tiempo para insights horarios y sentinel (V2.0 Focus)
    last_insight_time = time.time()
    last_salmos_time = 0
    last_sentinel_time = 0
    last_zec_sentinel_time = 0
    keyboard = get_main_menu()
    send_telegram("🤖 <b>Scalp Bot Multi-Estrategia Online</b>\n🛡️ V1-TECH: Activa\n🤖 V2-AI: Activa\n📡 Expert Advisor: Escuchando", keyboard=keyboard)
    
    while True:
        try:
            prices = get_prices()
            if prices:
                prices = sanitize_dict(prices)
                check_strategies(prices)
                check_market_pulse(prices)
                # monitor_open_trades ya maneja el seguimiento de posiciones
                monitor_open_trades(prices)
                
                # check_user_queries ahora se ejecuta en su propio hilo (run_telegram_worker)
                
                # Insights Horarios: AMBAS PERSONALIDADES (cada 3600 segundos)
                now = time.time()
                if now - last_insight_time > 3600:
                    # V3.4: Actualizamos el tiempo ANTES para evitar bucles si falla la IA o Telegram
                    last_insight_time = now 
                    print("[Robot] Generando panorama horario (Conservador + Scalper)...")
                    panoramas = gemini_analyzer.get_hourly_panorama(prices)
                    # Enviar ambas perspectivas por separado
                    send_telegram(f"🤖 <b>PANORAMA DEL ROBOT</b>\n\n{safe_html(panoramas.get('conservador', 'Sin datos'))}")
                    send_telegram(f"🤖 <b>PANORAMA DEL ROBOT</b>\n\n{safe_html(panoramas.get('scalper', 'Sin datos'))}")
                    send_telegram(f"🤖 <b>PANORAMA DEL ROBOT</b>\n\n{safe_html(panoramas.get('salmos', 'Sin datos'))}")
                
                # --- SALMOS PROPHECY (Cada 30 Minutos) ---
                if now - last_salmos_time > 1800:
                    last_salmos_time = now
                    trigger_salmos_prophecy(prices)
                
                # --- SENTINEL REPORT (ZEC + TAO — Cada 1 Hora) ---
                if now - last_zec_sentinel_time > 3600:
                    last_zec_sentinel_time = now
                    macro = GLOBAL_CACHE["macro_metrics"]
                    for _sym in ["ZEC", "TAO"]:
                        print(f"🥷 Sentinel {_sym}: Generando reporte del Cuadrante Zenith...")
                        _p = prices.get(_sym, 0.0)
                        _rsi = prices.get(f"{_sym}_RSI", 50.0)
                        _ema = GLOBAL_CACHE["indicators"].get(_sym, {}).get("ema_200", _p)
                        _atr = prices.get(f"{_sym}_ATR", 0.0)
                        _bb_u = prices.get(f"{_sym}_BB_U", 0.0)
                        _bb_l = prices.get(f"{_sym}_BB_L", 0.0)
                        sentinel_report = gemini_analyzer.get_sentinel_report(
                            symbol=_sym,
                            current_price=_p,
                            rsi=_rsi,
                            ema=_ema,
                            usdt_d=prices.get("USDT_D", 8.08),
                            vix=macro.get("vix", 0.0),
                            dxy=macro.get("dxy", 0.0),
                            spy=macro.get("spy", 0.0),
                            nvda=macro.get("nvda", 0.0),
                            pltr=macro.get("pltr", 0.0),
                            atr=_atr,
                            bb_u=_bb_u,
                            bb_l=_bb_l,
                            btc_price=prices.get("BTC", 0.0),
                            gold_price=prices.get("GOLD", 0.0),
                        )
                        _emoji = "🥷" if _sym == "ZEC" else "🏛️"
                        send_telegram(f"{_emoji} <b>SENTINEL REPORT: {_sym}</b>\n\n{safe_html(sentinel_report)}")
                
                # --- ALTCOIN SENTINEL (Cada 4 Horas) ---
                if now - last_sentinel_time > 14400: # 4 horas
                    last_sentinel_time = now
                    print("📡 Sentinel de Altcoins: Escaneando mercado secundario (BTC/ETH)...")
                    # Escaneamos narrativa para el resto, solo alertamos si es RELEVANTE (🚨)
                    import social_analyzer as _sa
                    reports = _sa.check_altcoin_narratives(["BTC", "ETH"])
                    for r in reports:
                        msg = (f"🛡️ <b>ALTCOIN SENTINEL ALERT</b> 🚨\n\n"
                               f"{r}\n\n"
                               f"💡 <i>Setup detectado fuera del foco principal ZEC/TAO.</i>")
                        send_telegram(msg)
                    
        except Exception as e:
            print(f"❌ Main Loop Error: {e}")
            time.sleep(10) # Backoff de seguridad en fallos de red persistentes
        time.sleep(CHECK_INTERVAL)

def run_telegram_worker():
    """Bucle independiente para responder mensajes de Telegram rápidamente."""
    print("📡 Telegram Worker: Iniciando escucha activa (5s interval)...")
    while True:
        try:
            # get_prices usa caché interna, así que es rápido si los datos son frescos
            prices = get_prices()
            if prices:
                prices = sanitize_dict(prices)
                check_user_queries(prices)
        except Exception as e:
            # Evitar spam en logs si es error de red temporal
            if "Connection" not in str(e):
                print(f"❌ Telegram Worker Error: {e}")
        time.sleep(5) # Respuesta mucho más ágil

if __name__ == "__main__":
    main()
