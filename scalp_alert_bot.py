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

# Cargar variables de entorno
load_dotenv()

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
    "macro_metrics": {"spy": 0.0, "oil": 0.0, "nvda": 0.0, "pltr": 0.0},
    "last_update": {
        "prices": 0,
        "indicators": {},
        "global_metrics": 0,
        "macro_metrics": 0,
        "fail_count": 0
    },
    "last_rsi": {"SOL": 50.0, "BTC": 50.0, "TAO": 50.0, "ZEC": 50.0},
    "executor": None # V5.0 Instance
}
# Tiempos de Vida (TTL) en segundos
TTL_PRICES = 20      # Precio: 20s (Fallback si falla la red)
TTL_INDICATORS = 120 # Indicadores: 2 min (Reducción de carga)
TTL_GLOBAL = 600     # Métricas Globales: 10 min
TTL_MACRO = 900      # Macro (SPY/Oil): 15 min (Lento)

def safe_html(text: str) -> str:
    """Refinado V1.6.7: Maneja bullets de Markdown y preserva entidades HTML."""
    if not text: return ""
    
    # 1. Convertir bullets de Markdown (* o -) a viñetas circulares
    import re
    t = re.sub(r"^\s*[\*\-]\s+", "• ", text, flags=re.MULTILINE)
    
    # 2. Pre-procesar etiquetas HTML comunes (Gemini a veces las mezcla)
    t = t.replace("<ul>", "").replace("</ul>", "")
    t = t.replace("<li>", "• ").replace("</li>", "\n")
    for i in range(1, 6): 
        t = t.replace(f"<h{i}>", "<b>").replace(f"</h{i}>", "</b>\n")
    t = t.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    t = t.replace("<p>", "").replace("</p>", "\n")
    t = t.replace("---", "──────────────")
    
    # 3. Protección de símbolos matemáticos y escape balanceado
    allowed = ["b", "i", "u", "s", "code", "pre", "a"]
    
    # Escapamos < y > que NO sean etiquetas permitidas
    for tag in allowed:
        t = re.sub(rf"<{tag}>", f"__LT__{tag}__GT__", t, flags=re.IGNORECASE)
        t = re.sub(rf"</{tag}>", f"__LT__/{tag}__GT__", t, flags=re.IGNORECASE)
    
    t = t.replace("<", "&lt;").replace(">", "&gt;")
    t = t.replace("__LT__", "<").replace("__GT__", ">")
    
    # 4. Escape de & SOLO si no parece ser una entidad HTML existente (como &#x...; o &lt;)
    # Esto evita el problema de &amp;#x1F6A8;
    t = re.sub(r"&(?!(?:[a-zA-Z]+|#[0-9]+|#x[0-9a-fA-F]+);)", "&amp;", t)
    
    return t
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
            
            print(f"✅ {key} R1: ${(r1 or 0.0):,.2f} | S1: ${(s1 or 0.0):,.2f}")
        except Exception as e:
            # Error silencioso de red para evitar spam en logs
            if "NameResolutionError" in str(e) or "Max retries exceeded" in str(e):
                print(f"⚠️ [Network] Error niveles {key} (DNS/Conexión)")
            else:
                print(f"❌ Error niveles {key}: {e}")

fired = {}

def get_main_menu(symbol="ZEC"):
    """Genera el teclado de botones para Telegram (Contextual V1.6.8)."""
    last_trade = tracker.get_last_open_trade(symbol)
    
    keyboard = [
        [{"text": "📊 Mercado"}, {"text": "📈 Acciones"}, {"text": "🎯 Setup"}],
        [{"text": "🛡️ Macro"}, {"text": "🏦 PnL HOY"}, {"text": "🏛️ Audit"}],
        [{"text": "🐦 Intel ZEC"}, {"text": "🐦 Intel TAO"}]
    ]

    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "persistent": True
    }

def send_telegram(msg: str, reply_to: str = None, keyboard: dict = None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # Usamos HTML para mayor robustez con el texto de Gemini
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    if reply_to: payload["reply_to_message_id"] = reply_to
    
    # Si no se pasa teclado, usamos el principal por defecto
    kb = keyboard if keyboard is not None else get_main_menu()
    payload["reply_markup"] = kb
    try:
        r = requests.post(url, json=payload, timeout=10)
        res = r.json()
        if res.get("ok"):
            return str(res["result"]["message_id"])
        else:
            print(f"❌ Error en Telegram (HTML): {res.get('description')}")
            print(f"🔍 DEBUG: payload sent: {payload}")
            return None
    except Exception as e:
        if "NameResolutionError" in str(e) or "Max retries exceeded" in str(e):
            print(f"⚠️ [Network] Error enviando Telegram (DNS/Conexión)")
        else:
            print(f"❌ Error enviando Telegram: {e}")
        return None

def alert(key: str, msg: str, version: str = "V1-TECH", cooldown: int = 300, reply_to: str = None):
    now = time.time()
    if fired.get(key, 0) + cooldown < now:
        fired[key] = now
        ts = datetime.now().strftime("%H:%M")
        header = "🛡️ <b>[V1-TECH]</b>" if version == "V1-TECH" else "🤖 <b>[V2-AI-GEMINI]</b>"
        full = f"{header} — <code>{ts}</code>\n{msg}"
        print(f"[{version}] {key} alert sent.")
        return send_telegram(full, reply_to)
    return None

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

    # 5. Elliott Wave Impulse Bonus
    if "Onda 3" in elliott:
        score += 1
        
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
        symbols = ['ETH/USDT', 'BTC/USDT', 'TAO/USDT', 'ZEC/USDT', 'PAXG/USDT']
        try:
            # OPTIMIZACIÓN V3.2: fetch_tickers (Plural) es más eficiente que 4 llamadas separadas
            tickers = binance_ex.fetch_tickers(symbols)
            
            res["ETH"] = tickers.get('ETH/USDT', {}).get('last', res.get("ETH"))
            res["BTC"] = tickers.get('BTC/USDT', {}).get('last', res.get("BTC"))
            res["TAO"] = tickers.get('TAO/USDT', {}).get('last', res.get("TAO"))
            res["ZEC"] = tickers.get('ZEC/USDT', {}).get('last', res.get("ZEC"))
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

    # --- 2.5 MACRO SENTIMENT (SPY / OIL) ---
    if now - GLOBAL_CACHE["last_update"]["macro_metrics"] > TTL_MACRO:
        try:
            # S&P 500, Petróleo, Nvidia y Palantir
            macro_symbols = ["SPY", "CL=F", "NVDA", "PLTR"]
            macro_data = yf.download(macro_symbols, period="1d", interval="1m", progress=False)['Close']
            
            spy_p = macro_data['SPY'].iloc[-1] if not macro_data['SPY'].empty else GLOBAL_CACHE["macro_metrics"]["spy"]
            oil_p = macro_data['CL=F'].iloc[-1] if not macro_data['CL=F'].empty else GLOBAL_CACHE["macro_metrics"]["oil"]
            nvda_p = macro_data['NVDA'].iloc[-1] if not macro_data['NVDA'].empty else GLOBAL_CACHE["macro_metrics"]["nvda"]
            pltr_p = macro_data['PLTR'].iloc[-1] if not macro_data['PLTR'].empty else GLOBAL_CACHE["macro_metrics"]["pltr"]
            
            GLOBAL_CACHE["macro_metrics"] = {
                "spy": float(spy_p), "oil": float(oil_p), 
                "nvda": float(nvda_p), "pltr": float(pltr_p)
            }
            GLOBAL_CACHE["last_update"]["macro_metrics"] = now
            print(f"🌍 [Macro Update] SPY: ${spy_p:.2f} | NVDA: ${nvda_p:.2f} | PLTR: ${pltr_p:.2f}")
        except Exception as e:
            print(f"⚠️ Error Macro (Yahoo): {e}")

    res["SPY"] = GLOBAL_CACHE["macro_metrics"]["spy"]
    res["OIL"] = GLOBAL_CACHE["macro_metrics"]["oil"]

    # 3. Datos Técnicos (TTL_INDICATORS para reducir carga)
    for sym in ["TAO", "BTC", "ZEC"]:
        last_ind_update = GLOBAL_CACHE["last_update"]["indicators"].get(sym, 0)
        
        if now - last_ind_update > TTL_INDICATORS:
            try:
                # V12.1: Guardamos el previo para la inercia (Hook)
                GLOBAL_CACHE["last_rsi"][sym] = (prices.get(f"{sym}_RSI") or 50.0)
                
                rsi = indicators.get_rsi(sym, timeframe='15m')
                vals = indicators.get_indicators(sym, "15m")
                macro = indicators.get_macro_trend(sym)
                
                GLOBAL_CACHE["indicators"][sym] = {
                    "rsi": vals[0], "bb_u": vals[1], "bb_l": vals[3], 
                    "ema_200": vals[4], "atr": vals[5], "vol_sma": vals[6], 
                    "elliott": vals[7], "macro": macro
                }
                GLOBAL_CACHE["last_update"]["indicators"][sym] = now
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
    
    for sym in ["ZEC", "TAO"]:
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

        # --- FILTRO V1.6.1 AUDIT: REDUCCIÓN DE RUIDO (CALIDAD > CANTIDAD) ---
        if "Corrección" in elliott or "Correctiva" in elliott:
            # Bloqueamos para mejorar el win rate, evitando zonas de indecisión
            continue
        
        # --- ESTRATEGIA V12.1: CONFLUENCE + RSI HOOK ---
        prev_rsi = GLOBAL_CACHE["last_rsi"].get(sym, 50.0)
        
        # (V12.1 SHORT Logic Disabled - Institutional LONG FOCUS)
        if False and phase == "SHORT": # and p < ema_200 and rsi >= 62 and "BB" in bb_ctx:
            if rsi > prev_rsi: # RSI sigue subiendo, no entramos
                continue
                
            side = "SHORT"
            # SMC Filter: Check for Order Blocks
            df = indicators.get_df(sym, "1h")
            obs = indicators_swing.find_order_blocks(df)
            ob_detected = any(ob["type"] == "BEAR_OB" and p >= ob["low"] * 0.99 and p <= ob["high"] * 1.01 for ob in obs)

            conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"), ob_detected=ob_detected)
            badge = get_confluence_badge(conf_score)
            
            # Gestión ATR: SL a 2.0 * ATR (puesto en V12.0)
            sl_dist = max(atr * 2.0, p * 0.007)
            sl = round(p + sl_dist, 2)
            tp1 = round(p - (sl_dist * 2.0), 2)
            tp2 = round(p - (sl_dist * 3.5), 2)
            
            if conf_score < 4:
                print(f"⏩ [V12-Audit] Señal {sym} ignorada (Score {conf_score} < 4)")
                continue

            msg = (f"{badge}\n\n"
                   f"🔥 <b>SEÑAL V1.6.2 SCALP (15m)</b> 🔥\n\n"
                   f"🌍 {macro_ctx}\n"
                   f"🌊 {elliott_ctx}\n"
                   f"🛡️ <b>SMC SHIELD:</b> {'🟢 DETECTED' if (ob_detected if 'ob_detected' in locals() else False) else '⚪ NONE'}\n\n"
                   f"📊 <b>ESTADO TÉCNICO:</b>\n"
                   f"• RSI: {(rsi or 0.0):.1f} | BB: {bb_ctx}\n"
                   f"• EMA 200: ${(ema_200 or 0.0):,.2f}\n"
                   f"⭐ <b>Confiabilidad: {format_confidence(conf_score)}</b>\n\n"
                   f"🌍 <b>CONTEXTO MACRO:</b>\n"
                   f"• USDT.D: {usdt_d}%\n"
                   f"• BTC.D: {btc_d}%\n"
                   f"• ORO: ${(gold_price or 0.0):,.2f}\n\n"
                   f"🎯 TP1: <b>${(tp1 or 0.0):,.2f}</b> (2:1)\n"
                   f"🎯 TP2: <b>${(tp2 or 0.0):,.2f}</b> (3:1)\n"
                   f"🛑 SL: <b>${(sl or 0.0):,.2f}</b>\n\n"
                   f"🎙️ <b>DEBATE DE CONSENSO:</b>\n"
                   f"{gemini_analyzer.get_ai_consensus(sym, p, 'SHORT', rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'))}")
            mid = alert(f"{sym}_v1_short", msg, version="V1-TECH")
            if mid:
                tracker.log_trade(sym, "SHORT", p, tp1, tp2, sl, mid, "V1-TECH", rsi, bb_ctx, atr, elliott, conf_score)
                gemini_analyzer.log_alert_to_context(sym, "SHORT", p, rsi, tp1, sl, "V1-TECH")

            # --- ESTRATEGIA V2-AI: CONSENSUS MASTER (HYBRID) ---
            # Solo se dispara si V1-TECH ya dio una señal o si Gemini confirma alta probabilidad
            decision, reason, full_analysis = gemini_analyzer.get_ai_decision(sym, p, phase, rsi, bb_u, bb_l, "V2-AI", usdt_d, conf_score)
            
            if decision == "CONFIRM":
                badge = get_confluence_badge(conf_score + 1) # Plus point for AI confirmation
                msg = (f"{badge}\n\n"
                       f"🔥 <b>SEÑAL V3 REVERSAL AGRESIVA</b> 🔥\n\n"
                       f"📊 <b>ESTADO TÉCNICO:</b>\n"
                       f"• Score Confluencia: {conf_score}/5\n"
                       f"⭐ <b>Confiabilidad: {format_confidence(conf_score + 1)}</b>\n\n"
                       f"🪙 <b>{sym}</b> @ ${(p or 0.0):,.2f}\n"
                       f"🎯 TP1: <b>${(tp1 or 0.0):,.2f}</b> (2:1)\n"
                       f"🎯 TP2: <b>${(tp2 or 0.0):,.2f}</b> (3:1)\n"
                       f"🛑 SL: <b>${(sl or 0.0):,.2f}</b>\n\n"
                       f"🎙️ <b>DEBATE DE CONSENSO:</b>\n"
                       f"{gemini_analyzer.get_ai_consensus(sym, p, phase, rsi, usdt_d, spy=prices.get('SPY'), nvda=prices.get('NVDA'))}")
                mid = alert(f"{sym}_v2_ai_{phase}", msg, version="V2-AI")
                if mid:
                    tracker.log_trade(sym, phase, p, tp1, tp2, sl, mid, "V2-AI", rsi, bb_ctx, atr, elliott, conf_score, ai_analysis=full_analysis, macro_bias=macro_status)

        # --- ESTRATEGIA V3: REVERSAL / INTRADIA (AGRESIVA) ---
        elif phase == "LONG" and p < ema_200:
            # --- MODO RESCATE TAO ---
            reversal_rsi = 28.0 if sym == "TAO" else 26.0
            if rsi <= reversal_rsi: # Umbral más bajo para "Hook"
                side = "LONG"
                conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"))
                
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
                       f"🎙️ <b>DEBATE DE CONSENSO:</b>\n"
                       f"{gemini_analyzer.get_ai_consensus(sym, p, 'LONG', rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'))}")
                mid = alert(f"{sym}_v3_reversal", msg, version="V1-TECH")
                if mid:
                    tracker.log_trade(sym, "LONG", p, tp1, tp2, sl, mid, "V1-TECH", rsi, bb_ctx, atr, elliott, conf_score)
                    gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")

        # Long V1 (Trend Alcista + Near BB + RSI 42 + RSI Rising)
        elif phase == "LONG" and p > ema_200 and "BB" in bb_ctx:
            # --- MODO PROACTIVO ZEC ---
            entry_rsi = 48.0 if sym == "ZEC" else 42.0
            if rsi <= entry_rsi:
                if rsi < prev_rsi: # RSI sigue cayendo, no entramos (Falling Knife)
                    continue
                # Gestión ATR: SL a 2.0 * ATR (V12.0)
                sl_dist = max(atr * 2.0, p * 0.007)
                sl = round(p - sl_dist, 2)
                tp1 = round(p + (sl_dist * 2.0), 2)
                tp2 = round(p + (sl_dist * 3.5), 2)
                caution = "⚠️ *PRECAUCIÓN: USDT.D ALTO*\n" if usdt_d > 8.05 else ""

                side = "LONG"
                conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"))

                if conf_score < 4:
                    print(f"⏩ [V12-Audit] Señal {sym} ignorada (Score {conf_score} < 4)")
                    continue

                badge = get_confluence_badge(conf_score)
                
                msg = (f"{badge}\n\n"
                       f"🚀 <b>SEÑAL V1.6.2 SCALP (15m)</b> 🚀\n\n"
                       f"🌍 {macro_ctx}\n"
                       f"🌊 {elliott_ctx}\n"
                       f"🛡️ <b>SMC SHIELD:</b> {'🟢 DETECTED' if (ob_detected if 'ob_detected' in locals() else False) else '⚪ NONE'}\n\n"
                       f"📈 15m Trend: {trend_ctx}\n"
                       f"💰 Volatilidad: {atr:,.2f} USD\n\n"
                       f"📊 <b>ESTADO TÉCNICO:</b>\n"
                       f"• RSI: {(rsi or 0.0):.1f} | BB: {bb_ctx}\n"
                       f"• EMA 200: ${(ema_200 or 0.0):,.2f}\n"
                       f"⭐ <b>Confiabilidad: {format_confidence(conf_score)}</b>\n\n"
                       f"🌍 <b>CONTEXTO MACRO:</b>\n"
                       f"• USDT.D: {usdt_d}% | BTC.D: {btc_d}%\n\n"
                       f"🪙 <b>{sym}</b> @ ${(p or 0.0):,.2f}\n"
                       f"🎯 TP1: <b>${(tp1 or 0.0):,.2f}</b> (2:1)\n"
                       f"🎯 TP2: <b>${(tp2 or 0.0):,.2f}</b> (3:1)\n"
                       f"🛑 SL: <b>${(sl or 0.0):,.2f}</b>\n\n"
                       f"🎙️ <b>DEBATE DE CONSENSO:</b>\n"
                       f"{gemini_analyzer.get_ai_consensus(sym, p, 'LONG', rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'))}")
                mid = alert(f"{sym}_v1_long", msg, version="V1-TECH")
                if mid:
                    tracker.log_trade(sym, "LONG", p, tp1, tp2, sl, mid, "V1-TECH", rsi, bb_ctx, atr, elliott, conf_score)
                    gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")

                # --- ESTRATEGIA V2-AI: CONSENSUS MASTER (HYBRID) ---
                decision, reason, full_analysis = gemini_analyzer.get_ai_decision(sym, p, phase, rsi, bb_u, bb_l, "V2-AI", usdt_d, conf_score)
                
                if decision == "CONFIRM":
                    conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"), ob_detected=ob_detected)
                    badge = get_confluence_badge(conf_score)
                    
                    # --- V5.0 EXECUTION LAYER (BINANCE) ---
                    exec_report = "⚪ NO EJECUTADO (Bajo Conf_Score)"
                    if conf_score >= 4:
                        if not GLOBAL_CACHE["executor"]:
                            GLOBAL_CACHE["executor"] = trading_executor.ZenithExecutor()
                        
                        res = GLOBAL_CACHE["executor"].execute_bracket_order(sym, side, p, tp1, tp2, sl)
                        exec_report = f"💸 <b>BINANCE STATUS:</b> {res.get('status')} (ID: {res.get('id')})"

                    msg = (f"{badge}\n\n"
                           f"🚀 <b>ESTRATEGIA V5: EXECUTIVE MODE</b>\n"
                           f"🛡️ <b>SMC SHIELD:</b> {'🟢 DETECTED' if (ob_detected if 'ob_detected' in locals() else False) else '⚪ NONE'}\n"
                           f"{exec_report}\n\n"
                           f"📊 <b>ESTADO TÉCNICO:</b>\n"
                           f"• Score Confluencia: {conf_score}/5\n"
                           f"⭐ <b>Confiabilidad: {format_confidence(conf_score + 1)}</b>\n\n"
                           f"💡 <b>RAZÓN IA:</b> {safe_html(reason)}\n\n"
                           f"🪙 <b>{sym}</b> @ ${(p or 0.0):,.2f}\n"
                           f"🎯 TP1: <b>${(tp1 or 0.0):,.2f}</b> (2:1)\n"
                           f"🎯 TP2: <b>${(tp2 or 0.0):,.2f}</b> (3:1)\n"
                           f"🛑 SL: <b>${(sl or 0.0):,.2f}</b>\n\n"
                           f"🎙️ <b>DEBATE DE CONSENSO:</b>\n"
                           f"{gemini_analyzer.get_ai_consensus(sym, p, phase, rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'))}")
                    mid = alert(f"{sym}_v2_ai_{phase}", msg, version="V2-AI")
                    if mid:
                        tracker.log_trade(sym, phase, p, tp1, tp2, sl, mid, "V2-AI", rsi, bb_ctx, atr, elliott, conf_score, ai_analysis=full_analysis, macro_bias=macro_status)

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
                dec_cons, reason_cons, full_cons = gemini_analyzer.get_ai_decision(sym, p, side, rsi, bb_u, bb_l, version="V1-TECH", usdt_d=usdt_d)
                dec_scalp, reason_scalp, full_scalp = gemini_analyzer.get_ai_decision(sym, p, side, rsi, bb_u, bb_l, version="V2-AI", usdt_d=usdt_d)
                full_analysis = f"Consenso:\n{full_cons}\n\n{full_scalp}"
            else:
                dec_cons, dec_scalp, full_analysis = "REJECT", "Contra tendencia mayor", ""

            if dec_cons == "CONFIRM" or dec_scalp == "CONFIRM":
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
                       f"🎙️ <b>DEBATE DE CONSENSO:</b>\n"
                       f"{gemini_analyzer.get_ai_consensus(sym, p, side, rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'))}")
                
                mid = alert(f"{sym}_v2_short", msg, version="V2-AI")
                if mid:
                    tracker.log_trade(sym, phase, p, tp1, tp2, sl, mid, "V2-AI", rsi, bb_ctx, atr, elliott, 5 if is_consensus else 4, ai_analysis=full_analysis, macro_bias=macro_status)
                    gemini_analyzer.log_alert_to_context(sym, side, p, rsi, tp1, sl, "V2-AI")

        # --- ALERTAS ESTRATÉGICAS: USDT.D BREAKOUT ---
        for level in [8.08, 8.044, 7.953]:
            # Alerta si cruzamos nivel (con tolerancia de 0.005)
            if abs(usdt_d - level) < 0.005:
                if level == 8.08:
                    desc = "Pánico y Alta Presión Vendedora (Precaución con los LONGs)"
                elif level == 8.044:
                    desc = "Tensión e Incertidumbre (Riesgo de corrección)"
                else:
                    desc = "Euforia y Dinero Entrando (Zona óptima para LONGs)"
                    
                alert(f"usdtd_break_{level}", f"🚨 *BREAKOUT USDT.D*: Nivel `{level}%` alcanzado.\n\n📖 *Significado*: {desc}\nContexto: {bb_ctx}", version="MACRO", cooldown=3600)

def monitor_open_trades(prices: dict):
    open_trades = tracker.get_open_trades()
    for t in open_trades:
        sym = t["symbol"]
        if sym not in prices: continue
        curr_p, tipo, reply = prices[sym], t["type"], t["msg_id"]
        rsi = prices[f"{sym}_RSI"]
        bb_u, bb_l = prices[f"{sym}_BB_U"], prices[f"{sym}_BB_L"]
        
        # Contexto de salida
        bb_ctx = "🔝 Techo BB" if curr_p >= bb_u * 0.99 else "🩸 Suelo BB" if curr_p <= bb_l * 1.01 else "↕️ Rango"
        pnl_pct = ((curr_p - t["entry_price"]) / t["entry_price"]) * 100
        if tipo == "SHORT": pnl_pct = -pnl_pct
        
        # V5.0: Log PNL to console for pure trading monitor
        if abs(pnl_pct) > 1.0:
            print(f"📈 [Trade Monitor] {sym} {tipo}: {pnl_pct:+.2f}% (P: {curr_p})")

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
    """Escucha comandos del usuario en Telegram para modo interactivo."""
    offset = 0
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE, "r") as f:
            try: offset = int(f.read().strip())
            except: offset = 0
            
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset + 1, "timeout": 1} # Short polling para no bloquear
    
    try:
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        if not data.get("ok"): return
        
        for update in data.get("result", []):
            last_id = update["update_id"]
            # Guardamos el offset inmediatamente
            with open(OFFSET_FILE, "w") as f: f.write(str(last_id))
            
            msg_obj = update.get("message", {})
            text = msg_obj.get("text", "").strip()
            chat_id = str(msg_obj.get("chat", {}).get("id", ""))
            
            # Solo respondemos si es el chat autorizado (dueño del bot)
            if chat_id != str(TELEGRAM_CHAT_ID): 
                print(f"⚠️ Intento de acceso no autorizado: {chat_id} (Esperado: {TELEGRAM_CHAT_ID})")
                continue
            
            print(f"📩 [Telegram Agent] Comando: {text}")
            
            if "setup" in text.lower() or text.startswith("/setup"):
                print("🧠 Buscando el Mejor Setup...")
                send_telegram("🔍 <b>La IA está escaneando BTC, SOL, TAO y ZEC para encontrar la mejor operación...</b>")
                setup_report = gemini_analyzer.get_top_setup(prices)
                send_telegram(safe_html(setup_report))
                
            elif "macro" in text.lower() or text.startswith("/macro"):
                print("🧠 Activando Escudo Macro...")
                send_telegram("🛡️ <b>Analizando Dominancia USDT y liquidez del mercado accionario...</b>")
                stock_context = ""
                try:
                    with open("latest_report.txt", "r") as f:
                        stock_context = f.read()
                except: pass
                macro_report = gemini_analyzer.get_macro_shield(prices, stock_context)
                send_telegram(safe_html(macro_report))
                
            elif "pnl" in text.lower() or text.startswith("/pnl"):
                print("📊 Calculando PnL Diario...")
                stats = tracker.get_daily_pnl()
                msg = (f"🏦 <b>REPORTE PNL DIARIO (HOY)</b>\n\n"
                       f"🏆 Trades Cerrados: <b>{stats['total']}</b>\n"
                       f"✅ Ganados: <b>{stats['wins']}</b>\n"
                       f"🔴 Perdidos: <b>{stats['losses']}</b>\n"
                       f"⚖️ Tasa Acierto: <b>{stats['win_rate']:.1f}%</b>")
                send_telegram(msg)
                    
            elif "acciones" in text.lower() or text.startswith("/stocks"):
                print("📈 Construyendo reporte de Radar de Acciones...")
                send_telegram("⏳ Obteniendo radar de acciones y calculando precios en vivo con Yahoo Finance... (puede tardar unos segundos)")
                import stock_analyzer
                stock_report = stock_analyzer.check_stock_status()
                send_telegram(stock_report)
                
            elif "intel" in text.lower() or "social" in text.lower() or text.startswith("/intel"):
                sym = "ZEC" if "ZEC" in text.upper() else "TAO" if "TAO" in text.upper() else "BTC" if "BTC" in text.upper() else "ZEC"
                print(f"🐦 Consultando Inteligencia Social para {sym} (Ambas Estrategias)...")
                send_telegram(f"🐦 <b>Escaneando X (Twitter) y News para {sym}...</b>\nAnalizando Catalizadores y Veracidad...")
                report = social_analyzer.get_social_intel(sym, current_price=prices.get(sym, 0.0))
                send_telegram(safe_html(report))
                
            elif "mercado" in text.lower() or text.startswith("/status"):
                print("📊 Generando reporte de estado con sentimiento AI...")
                sentiment = gemini_analyzer.get_market_sentiment(prices)
                bias_emoji = "🟢" if sentiment["bias"] == "BULLISH" else "🔴" if sentiment["bias"] == "BEARISH" else "🟡"
                
                status_msg = (f"📊 <b>ESTADO DEL MERCADO</b> {bias_emoji}\n"
                              f"Sentimiento: <b>{sentiment['bias']}</b>\n\n")
                
                for s in ["SOL", "BTC", "TAO", "ZEC"]:
                    p = (prices.get(s) or 0.0)
                    rsi = (prices.get(f"{s}_RSI") or 0.0)
                    status_msg += f"• <b>{s}</b>: ${(p or 0.0):,.2f} | RSI: {(rsi or 0.0):.1f}\n"
                
                status_msg += (f"\n🎙️ <b>OPINIÓN DE EXPERTOS:</b>\n"
                               f"🎩 <b>Gordon</b>: \"{sentiment['gordon']}\"\n"
                               f"⚡ <b>Aiden</b>: \"{sentiment['aiden']}\"")
                
                send_telegram(status_msg, keyboard=get_main_menu())
                
            elif text.startswith("/audit") or "Auditoría" in text:
                print("🏛️ Generando reporte de auditoría experta...")
                metrics = tracker.get_audit_metrics()
                
                if metrics["total_trades"] == 0:
                    audit_msg = (
                        f"🏛️ <b>AUDITORÍA ZENITH (V13.5)</b>\n\n"
                        f"📈 <b>NUEVA ERA INICIADA</b>\n"
                        f"Métricas reseteadas. El bot está en modo 'Auditoría Silenciosa' acumulando datos de alta precisión.\n\n"
                        f"🎯 <i>Objetivo: Profit Factor > 1.75</i>"
                    )
                else:
                    audit_msg = (
                        f"🏛️ <b>AUDITORÍA EXPERTA ZENITH (V13.5)</b>\n\n"
                        f"• Total Trades: <b>{metrics['total_trades']}</b>\n"
                        f"• Win Rate: <b>{metrics['win_rate']}</b>\n"
                        f"• Profit Factor: <b>{metrics['profit_factor']}</b>\n"
                        f"• Status: <b>{metrics['status']}</b>\n\n"
                        f"🎯 <i>Objetivo Pro: Profit Factor > 1.75</i>"
                    )
                send_telegram(audit_msg, keyboard=get_main_menu())
            elif "LONG" in text or "SHORT" in text:
                # Soporte para formato "/BTC LONG" o simplemente "/BTC LONG" (limpieza de comando)
                clean_text = text.replace("/", "").upper()
                sym = next((s for s in ["SOL", "BTC", "TAO", "ZEC"] if s in clean_text), None)
                if sym:
                    side = "LONG" if "LONG" in clean_text else "SHORT"
                    p = (prices.get(sym) or 0.0)
                    atr = (prices.get(f"{sym}_ATR") or p * 0.01)
                    
                    # 1. Lógica de Toggle: Cerrar previa si existe
                    last_trade = tracker.get_last_open_trade(sym)
                    if last_trade:
                        entry = last_trade["entry_price"]
                        pnl_pct = ((p - entry) / entry) * 100
                        if last_trade["type"] == "SHORT": pnl_pct = -pnl_pct
                        tracker.update_trade_status(last_trade["id"], "WON" if pnl_pct > 0 else "LOST")
                        send_telegram(f"🔄 <b>Cerrando {sym} {last_trade['type']} previo</b> (PnL: {pnl_pct:+.2f}%) para abrir nueva posición.", reply_to=last_trade["msg_id"])
                    
                    # 2. Cálculo de Targets Dinámicos (1.5x ATR)
                    sl_dist = max(atr * 1.5, p * 0.005)
                    sl = round(p - sl_dist if side == "LONG" else p + sl_dist, 2)
                    tp1 = round(p + (sl_dist * 2.0) if side == "LONG" else p - (sl_dist * 2.0), 2)
                    tp2 = round(p + (sl_dist * 3.5) if side == "LONG" else p - (sl_dist * 3.5), 2)
                    
                    if p > 0:
                        msg = (f"🚀 <b>{sym} {side} MANUAL</b>\n"
                               f"Entrada: ${p:,.2f}\n\n"
                               f"🎯 <b>TARGETS SUGERIDOS:</b>\n"
                               f"• TP1: <b>${tp1:,.2f}</b> (2:1)\n"
                               f"• TP2: <b>${tp2:,.2f}</b> (3.5:1)\n"
                               f"🛑 SL: <b>${sl:,.2f}</b>\n\n"
                               f"<i>Monitoreando PnL...</i>")
                        mid = send_telegram(msg, keyboard=get_main_menu(sym))
                        tracker.log_trade(sym, side, p, tp1, tp2, sl, mid, version="MANUAL", rsi=prices.get(f"{sym}_RSI", 50))
                    else:
                        send_telegram(f"❌ No se pudo obtener el precio de {sym} para la entrada manual.")
                else:
                    send_telegram("❌ Símbolo no reconocido para trade manual. Usa BTC/SOL/TAO/ZEC.")
            
            elif "CERRAR " in text or "CLOSE " in text:
                clean_text = text.replace("/", "").upper()
                sym = next((s for s in ["SOL", "BTC", "TAO", "ZEC"] if s in clean_text), None)
                if sym:
                    last_trade = tracker.get_last_open_trade(sym)
                    if last_trade:
                        p = (prices.get(sym) or 0.0)
                        if p > 0:
                            entry = last_trade["entry_price"]
                            pnl_pct = ((p - entry) / entry) * 100
                            if last_trade["type"] == "SHORT": pnl_pct = -pnl_pct
                            
                            status = "FULL_WON" if pnl_pct > 0 else "LOST"
                            tracker.update_trade_status(last_trade["id"], status)
                            
                            msg = (f"🏁 <b>POSICIÓN CERRADA ({sym})</b>\n\n"
                                   f"• Tipo: {last_trade['type']}\n"
                                   f"• Entrada: ${entry:,.2f}\n"
                                   f"• Cierre: ${p:,.2f}\n"
                                   f"💰 PnL: <b>{pnl_pct:+.2f}%</b>")
                            send_telegram(msg, reply_to=last_trade["msg_id"], keyboard=get_main_menu(sym))
                        else:
                            send_telegram(f"❌ No se pudo obtener el precio de {sym} para cerrar la posición.")
                    else:
                        send_telegram(f"⚠️ No hay trades abiertos de {sym} para cerrar.", keyboard=get_main_menu(sym))
                else:
                    send_telegram("❌ Símbolo no reconocido para cerrar. Usa BTC/SOL/TAO/ZEC.")
            
            else:
                welcome_text = (
                    "👋 <b>¡Bienvenido al Scalp Alert Bot!</b>\n\n"
                    "Utiliza los botones de abajo o escribe comandos:\n"
                    "• <code>/status</code> - Ver precios actuales y RSI\n"
                    "• <code>/analyze [SYM]</code> - Análisis profundo con AI\n\n"
                    "🛡️ <b>V1-TECH</b> y 🤖 <b>V2-AI</b> están monitoreando el mercado 24/7."
                )
                send_telegram(welcome_text, keyboard=get_main_menu("TAO"))
                
    except Exception as e:
        print(f"❌ Error polling updates: {e}")

def main():
    print("🚀 Scalp Alert Bot V3 (AI Panorama) - INICIANDO")
    update_dynamic_levels()
    
    # Control de tiempo para insights horarios y sentinel (V2.0 Focus)
    last_insight_time = time.time()
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
                monitor_open_trades(prices)
                
                # REVISAR CONSULTAS DEL USUARIO (Interactive Agent)
                check_user_queries(prices)
                
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
                
                # --- ZEC SENTINEL REPORT (Cada 1 Hora) ---
                if now - last_zec_sentinel_time > 3600:
                    last_zec_sentinel_time = now
                    print("🥷 Sentinel ZEC: Generando reporte estructural de Shadow...")
                    zec_p = prices.get("ZEC", 0.0)
                    zec_rsi = prices.get("ZEC_RSI", 50.0)
                    zec_ema = GLOBAL_CACHE["indicators"].get("ZEC", {}).get("ema_200", zec_p)
                    # Fetch ZEC report from Shadow
                    shadow_report = gemini_analyzer.get_zec_sentinel_report(zec_p, zec_rsi, zec_ema, prices.get("USDT_D", 8.08))
                    send_telegram(f"🥷 <b>SHADOW REPORT: ZCASH (ZEC)</b>\n\n{safe_html(shadow_report)}")
                
                # --- ALTCOIN SENTINEL (Cada 4 Horas) ---
                if now - last_sentinel_time > 14400: # 4 horas
                    last_sentinel_time = now
                    print("📡 Sentinel de Altcoins: Escaneando mercado secundario (BTC/ETH)...")
                    # Escaneamos narrativa para el resto, solo alertamos si es RELEVANTE (🚨)
                    reports = social_analyzer.check_altcoin_narratives(["BTC", "ETH"])
                    for r in reports:
                        msg = (f"🛡️ <b>ALTCOIN SENTINEL ALERT</b> 🚨\n\n"
                               f"{r}\n\n"
                               f"💡 <i>Setup detectado fuera del foco principal ZEC/TAO.</i>")
                        send_telegram(msg)
                    
        except Exception as e:
            print(f"❌ Main Loop Error: {e}")
            time.sleep(10) # Backoff de seguridad en fallos de red persistentes
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
