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
import ccxt

# Cargar variables de entorno
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "35")) # Aumentamos ligeramente para proteger CoinGecko
PHASE_FILE = "phase.txt"

# ─── CONFIGURACIÓN DE NIVELES ──────────────────────────────────────────────
LEVELS = {
    "ETH": {"short_entry_high": 2037, "sl_short": 2045, "target1": 1960, "target2": 1930, "long_zone": 1905},
    "TAO": {"resistance": 320, "target1": 290, "target2": 270, "long_zone": 265, "long_sl": 238},
    "BTC": {"resistance": 68283, "support1": 65000, "support2": 62987}
}

def get_phase() -> str:
    if not os.path.exists(PHASE_FILE): return "SHORT"
    with open(PHASE_FILE, "r") as f: return f.read().strip()

def set_phase(phase: str):
    with open(PHASE_FILE, "w") as f: f.write(phase)
    send_telegram(f"🔄 *CAMBIO DE ESTRATEGIA*: Fase actualizada a `{phase}`")

def update_dynamic_levels():
    """Calcula Soportes/Resistencias Diarios basados en ayer (Pivot Points)."""
    print("\n🔄 Actualizando niveles dinámicos (Pivot Points)...")
    binance = ccxt.binance()
    gateio = ccxt.gateio()
    symbols = {"ETH": (binance, "ETH/USDT"), "BTC": (binance, "BTC/USDT"), "TAO": (gateio, "TAO/USDT")}
    
    for key, (exchange, sym) in symbols.items():
        try:
            ohlcv = exchange.fetch_ohlcv(sym, timeframe='1d', limit=2)
            if len(ohlcv) < 2: continue
            ayer = ohlcv[0] # Vela cerrada
            h, l, c = ayer[2], ayer[3], ayer[4]
            p = (h + l + c) / 3
            r1 = (2 * p) - l
            s1 = (2 * p) - h
            
            if key == "ETH":
                LEVELS["ETH"]["short_entry_high"] = round(r1, 2)
                LEVELS["ETH"]["target1"] = round(p, 2)
                LEVELS["ETH"]["long_zone"] = round(s1, 2)
                LEVELS["ETH"]["sl_short"] = round(r1 * 1.01, 2)
            elif key == "TAO":
                LEVELS["TAO"]["resistance"] = round(r1, 1)
                LEVELS["TAO"]["target1"] = round(p, 1)
                LEVELS["TAO"]["long_zone"] = round(s1, 1)
                LEVELS["TAO"]["long_sl"] = round(s1 * 0.98, 1)
            elif key == "BTC":
                LEVELS["BTC"]["resistance"] = round(r1, 0)
                LEVELS["BTC"]["support2"] = round(s1, 0)
            
            print(f"✅ {key} R1: ${r1:,.2f} | S1: ${s1:,.2f}")
        except Exception as e: print(f"❌ Error levels {key}: {e}")

fired = {}

def send_telegram(msg: str, reply_to: str = None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    if reply_to: payload["reply_to_message_id"] = reply_to
    try:
        r = requests.post(url, json=payload, timeout=10)
        return str(r.json()["result"]["message_id"]) if r.json().get("ok") else None
    except: return None

def alert(key: str, msg: str, version: str = "V1-TECH", cooldown: int = 300, reply_to: str = None):
    now = time.time()
    if fired.get(key, 0) + cooldown < now:
        fired[key] = now
        ts = datetime.now().strftime("%H:%M")
        header = "🛡️ *[V1-TECH]*" if version == "V1-TECH" else "🤖 *[V2-AI-GEMINI]*"
        full = f"{header} — `{ts}`\n{msg}"
        print(f"[{version}] {key} alert sent.")
        return send_telegram(full, reply_to)
    return None

def calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side="LONG"):
    """Calcula un score de confluencia técnica (0-5 puntos)."""
    score = 0
    # 1. RSI (Max 2 pt)
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
        
    return score

def get_confluence_badge(score):
    if score >= 4: return "💎 DIAMANTE (MAX CONFLUENCIA) 💎"
    if score == 3: return "🔥 ALTA CONVICCIÓN (CONFLUENTE) 🔥"
    return "⚡ SEÑAL ESTÁNDAR ⚡"

def get_prices() -> dict:
    """Consolida llamadas para proteger límites de CoinGecko extendiendo el contexto Macro."""
    ids = "ethereum,bittensor,bitcoin,pax-gold"
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
    try:
        r = requests.get(url, timeout=10)
        d = r.json()
        usdt_d, btc_d = indicators.get_global_metrics()
        
        res = {
            "ETH": d["ethereum"]["usd"], 
            "TAO": d["bittensor"]["usd"], 
            "BTC": d["bitcoin"]["usd"], 
            "GOLD": d.get("pax-gold", {}).get("usd", 2200.0),
            "USDT_D": usdt_d,
            "BTC_D": btc_d
        }
        
        for sym in ["ETH", "TAO", "BTC"]:
            rsi, bb_u, bb_m, bb_l, ema_200, atr, vol_sma = indicators.get_indicators(sym, "15m")
            macro_trend = indicators.get_macro_trend(sym)
            res[f"{sym}_RSI"] = rsi
            res[f"{sym}_BB_U"] = bb_u
            res[f"{sym}_BB_L"] = bb_l
            res[f"{sym}_EMA_200"] = ema_200
            res[f"{sym}_ATR"] = atr
            res[f"{sym}_VOL_SMA"] = vol_sma
            res[f"{sym}_MACRO"] = macro_trend
        return res
    except Exception as e:
        print(f"❌ Error fetching prices: {e}")
        return None

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
    
    for sym in ["ETH", "BTC"]:
        p, rsi = prices[sym], prices[f"{sym}_RSI"]
        bb_u, bb_l = prices[f"{sym}_BB_U"], prices[f"{sym}_BB_L"]
        ema_200 = prices[f"{sym}_EMA_200"]
        atr = prices[f"{sym}_ATR"]
        usdt_d = prices["USDT_D"]
        
        analysis = gemini_analyzer.get_market_pulse_analysis(
            sym, p, "Neutral", rsi, bb_u, bb_l, ema_200, atr, usdt_d
        )
        
        msg = (f"📡 *PULSO DE MERCADO (NYSE {event})*\n\n"
               f"🪙 *{sym}* @ ${p:,.2f}\n"
               f"📊 RSI: {rsi:.1f} | EMA: {'ALCISTA' if p > ema_200 else 'BAJISTA'}\n"
               f"💰 Volatilidad: {atr:,.2f} USD\n\n"
               f"🤖 *ANÁLISIS HÍBRIDO AI:*\n_{analysis}_")
        
        # Enviamos alerta única (no trackeamos como trade)
        alert(f"pulse_{sym}_{event}_{now.date()}", msg)

def check_strategies(prices: dict):
    if not prices: return
    phase = get_phase()
    usdt_d = prices.get("USDT_D", 8.0)
    
    for sym in ["ETH", "TAO", "BTC"]:
        p, rsi = prices[sym], prices[f"{sym}_RSI"]
        atr = prices[f"{sym}_ATR"]
        vol_sma = prices[f"{sym}_VOL_SMA"]
        macro_dict = prices.get(f"{sym}_MACRO", {"consensus": "NEUTRAL", "1H": "UNKNOWN", "4H": "UNKNOWN"})
        macro_status = macro_dict.get("consensus", "NEUTRAL")
        gold_price = prices.get("GOLD", 0.0)
        btc_d = prices.get("BTC_D", 50.0)
        
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
        
        # --- ESTRATEGIA V1.5.0: CONFLUENCE MASTER (TREND + ATR + VOL) ---
        # Short V1 (Trend Bajista + Near BB + RSI 62 + Vol Filter)
        if phase == "SHORT" and p < ema_200 and rsi >= 62 and "BB" in bb_ctx:
            # Puntuación de Confluencia
            side = "SHORT"
            conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side)
            badge = get_confluence_badge(conf_score)
            
            # Gestión ATR: SL a 1.5 * ATR (puesto en V1.4.0)
            sl_dist = max(atr * 1.5, p * 0.005)
            sl = round(p + sl_dist, 2)
            tp1 = round(p - (sl_dist * 2.0), 2)
            tp2 = round(p - (sl_dist * 3.0), 2)
            
            msg = (f"{badge}\n\n"
                   f"🔥 *SEÑAL V1.6.0 MACRO-ALIGNED (SHORT)*\n\n"
                   f"{macro_ctx}\n"
                   f"📉 15m Trend: {trend_ctx}\n"
                   f"💰 Volatilidad: {atr:,.2f} USD\n\n"
                   f"📊 *ESTADO TÉCNICO:*\n"
                   f"• RSI: {rsi:.1f}\n"
                   f"• BB: {bb_ctx}\n"
                   f"• EMA 200: ${ema_200:,.2f}\n\n"
                   f"🌍 *CONTEXTO MACRO:*\n"
                   f"• USDT.D: {usdt_d}%\n"
                   f"• BTC.D: {btc_d}%\n"
                   f"• ORO: ${gold_price:,.2f}\n\n"
                   f"🪙 *{sym}* @ ${p:,.2f}\n"
                   f"🎯 TP1: *${tp1:,.2f}* (2:1)\n"
                   f"🛑 SL: *${sl:,.2f}*")
            mid = alert(f"{sym}_v1_short", msg, version="V1-TECH")
            if mid:
                tracker.log_trade(sym, "SHORT", p, tp1, tp2, sl, mid, "V1-TECH")
                gemini_analyzer.log_alert_to_context(sym, "SHORT", p, rsi, tp1, sl, "V1-TECH")

            # --- ESTRATEGIA V2-AI: CONSENSUS MASTER (HYBRID) ---
            # Solo se dispara si V1-TECH ya dio una señal o si Gemini confirma alta probabilidad
            decision, reason = gemini_analyzer.get_ai_decision(sym, p, phase, rsi, bb_u, bb_l, "V2-AI", usdt_d, conf_score)
            
            if decision == "CONFIRM":
                badge = get_confluence_badge(conf_score + 1) # Plus point for AI confirmation
                msg = (f"{badge}\n\n"
                       f"🤖 *SEÑAL V2-AI CONSENSUS (HYBRID)*\n\n"
                       f"📊 *ESTADO TÉCNICO:*\n"
                       f"• Score Confluencia: {conf_score}/5\n"
                       f"• RSI: {rsi:.1f} | BB: {bb_ctx}\n\n"
                       f"💡 *RAZÓN IA:* {reason}\n\n"
                       f"🪙 *{sym}* @ ${p:,.2f}\n"
                       f"🎯 TP1: *${tp1:,.2f}* (2:1)\n"
                       f"🛑 SL: *${sl:,.2f}*")
                mid = alert(f"{sym}_v2_ai_{phase}", msg, version="V2-AI")
                if mid:
                    tracker.log_trade(sym, phase, p, tp1, tp2, sl, mid, "V2-AI")
                    gemini_analyzer.log_alert_to_context(sym, "SHORT", p, rsi, tp1, sl, "V1-TECH")

        # Long V1 (Trend Alcista + Near BB + RSI 38)
        elif phase == "LONG" and p > ema_200 and "BB" in bb_ctx:
            if rsi <= 38:
                sl_dist = max(atr * 1.5, p * 0.005)
                sl = round(p - sl_dist, 2)
                tp1 = round(p + (sl_dist * 2.0), 2)
                tp2 = round(p + (sl_dist * 3.0), 2)
                caution = "⚠️ *PRECAUCIÓN: USDT.D ALTO*\n" if usdt_d > 8.05 else ""
                # 3. Puntuación de Confluencia
                side = "LONG"
                conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side)
                badge = get_confluence_badge(conf_score)
                
                msg = (f"{badge}\n\n"
                       f"🚀 *SEÑAL V1.6.0 MACRO-ALIGNED (LONG)*\n\n"
                       f"{macro_ctx}\n"
                       f"📈 15m Trend: {trend_ctx}\n"
                       f"💰 Volatilidad: {atr:,.2f} USD\n\n"
                       f"📊 *ESTADO TÉCNICO:*\n"
                       f"• RSI: {rsi:.1f}\n"
                       f"• BB: {bb_ctx}\n"
                       f"• EMA 200: ${ema_200:,.2f}\n\n"
                       f"🌍 *CONTEXTO MACRO:*\n"
                       f"• USDT.D: {usdt_d}%\n"
                       f"• BTC.D: {btc_d}%\n"
                       f"• ORO: ${gold_price:,.2f}\n\n"
                       f"🪙 *{sym}* @ ${p:,.2f}\n"
                       f"🎯 TP1: *${tp1:,.2f}* (2:1)\n"
                       f"🛑 SL: *${sl:,.2f}*")
                mid = alert(f"{sym}_v1_long", msg, version="V1-TECH")
                if mid:
                    tracker.log_trade(sym, "LONG", p, tp1, tp2, sl, mid, "V1-TECH")
                    gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")

                # --- ESTRATEGIA V2-AI: CONSENSUS MASTER (HYBRID) ---
                decision, reason = gemini_analyzer.get_ai_decision(sym, p, phase, rsi, bb_u, bb_l, "V2-AI", usdt_d, conf_score)
                
                if decision == "CONFIRM":
                    badge = get_confluence_badge(conf_score + 1)
                    msg = (f"{badge}\n\n"
                           f"🤖 *SEÑAL V2-AI CONSENSUS (HYBRID)*\n\n"
                           f"📊 *ESTADO TÉCNICO:*\n"
                           f"• Score Confluencia: {conf_score}/5\n"
                           f"• RSI: {rsi:.1f} | BB: {bb_ctx}\n\n"
                           f"💡 *RAZÓN IA:* {reason}\n\n"
                           f"🪙 *{sym}* @ ${p:,.2f}\n"
                           f"🎯 TP1: *${tp1:,.2f}* (2:1)\n"
                           f"🛑 SL: *${sl:,.2f}*")
                    mid = alert(f"{sym}_v2_ai_{phase}", msg, version="V2-AI")
                    if mid:
                        tracker.log_trade(sym, phase, p, tp1, tp2, sl, mid, "V2-AI")

        # --- ESTRATEGIA V2: AI ENHANCED (CON CONSENSU) ---
        if (rsi >= 60 or rsi <= 40):
            side = "SHORT" if rsi >= 60 else "LONG"
            
            # 1. Consultamos a ambos agentes para buscar CONSENSO
            # El filtro EMA es global: no confirmamos si va contra tendencia
            is_valid_trend = (side == "LONG" and p > ema_200) or (side == "SHORT" and p < ema_200)
            
            if is_valid_trend:
                dec_cons, reason_cons = gemini_analyzer.get_ai_decision(sym, p, side, rsi, bb_u, bb_l, version="V1-TECH", usdt_d=usdt_d)
                dec_scalp, reason_scalp = gemini_analyzer.get_ai_decision(sym, p, side, rsi, bb_u, bb_l, version="V2-AI", usdt_d=usdt_d)
            else:
                dec_cons, dec_scalp = "REJECT", "Contra tendencia mayor"

            if dec_cons == "CONFIRM" or dec_scalp == "CONFIRM":
                is_consensus = (dec_cons == "CONFIRM" and dec_scalp == "CONFIRM")
                # Cálculo de gestión de riesgo dinámico (R:R 2:1)
                sl = L.get('sl_short', p*1.01) if side == "SHORT" else L.get('long_sl', p*0.99)
                dist_sl = abs(p - sl)
                tp1 = round(p - (dist_sl * 2.0) if side == "SHORT" else p + (dist_sl * 2.0), 2)
                tp2 = round(p - (dist_sl * 3.0) if side == "SHORT" else p + (dist_sl * 3.0), 2)
                
                header = "🔹💎🔹 *CONSENSO IA*" if is_consensus else "🤖 *IA CONFIRMADA*"
                icon = "💎" if side == "LONG" else "💀"
                caution = "⚠️ *CONTEXTO TENSO*\n" if side == "LONG" and usdt_d > 8.05 else ""
                
                # Razón combinada si hay consenso
                final_reason = reason_scalp if dec_scalp == "CONFIRM" else reason_cons
                if is_consensus: final_reason = f"Acuerdo Total: {reason_cons} + {reason_scalp}"

                msg = (f"{header} ({side})\n"
                       f"{caution}"
                       f"💬 _{final_reason}_\n\n"
                       f"🪙 *{sym}* @ ${p:,.2f}\n"
                       f"📊 RSI: {rsi:.1f} | {bb_ctx}\n"
                       f"📉 USDT.D: {usdt_d}%\n"
                       f"🎯 TP1: *${tp1:,.2f}* (2:1)\n"
                       f"🛑 SL: *${sl:,.2f}*")
                
                mid = alert(f"{sym}_v2_ai_{side}", msg, version="V2-AI")
                if mid:
                    tracker.log_trade(sym, side, p, tp1, tp2, sl, mid, "V2-AI")
                    gemini_analyzer.log_alert_to_context(sym, side, p, rsi, tp1, sl, "V2-AI")

        # --- ALERTAS ESTRATÉGICAS: USDT.D BREAKOUT ---
        for level in [8.08, 8.044, 7.953]:
            # Alerta si cruzamos nivel (con tolerancia de 0.005)
            if abs(usdt_d - level) < 0.005:
                alert(f"usdtd_break_{level}", f"🚨 *BREAKOUT USDT.D*: Nivel `{level}%` alcanzado.\nContexto: {bb_ctx}", version="MACRO", cooldown=3600)

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

        if tipo == "SHORT":
            if curr_p >= t["sl_price"]:
                tracker.update_trade_status(t["id"], "LOST")
                msg = (f"🔴 *STOP LOSS TOCADO (POST-MORTEM)*\n\n"
                       f"🪙 {sym} SHORT\n"
                       f"💸 PnL: *{pnl_pct:+.2f}%*\n"
                       f"📊 *Contexto de Cierre:*\n"
                       f"• RSI: {t['rsi_entry']:.1f} (Inicio) → {rsi:.1f} (Actual)\n"
                       f"• Bollinger: {bb_ctx}\n"
                       f"• Motivo: El precio superó el techo proyectado.")
                alert(f"t_{t['id']}_l", msg, version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "LOST", t["entry_price"], curr_p)
            elif curr_p <= t["tp2_price"]:
                tracker.update_trade_status(t["id"], "FULL_WON")
                msg = (f"🟢 *TP2 ALCANZADO (STRIKE!)*\n\n"
                       f"🪙 {sym} SHORT\n"
                       f"💰 PnL: *{pnl_pct:+.2f}%*\n"
                       f"📊 *Resumen:*\n"
                       f"• RSI Entrada: {t['rsi_entry']:.1f}\n"
                       f"• RSI Cierre: {rsi:.1f}\n"
                       f"✨ El indicador predijo el retroceso correctamente.")
                alert(f"t_{t['id']}_w", msg, version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "WIN_FULL", t["entry_price"], curr_p)
            elif curr_p <= t["tp1_price"] and t["status"] == "OPEN":
                tracker.update_trade_status(t["id"], "PARTIAL_WON")
                tracker.update_sl(t["id"], t["entry_price"]) # BE
                alert(f"t_{t['id']}_p", f"🟡 *TP1 ASEGURADO*\nBE Activado | Riesgo eliminado.", version=t["version"], reply_to=reply)
        elif tipo == "LONG":
            if curr_p <= t["sl_price"]:
                tracker.update_trade_status(t["id"], "LOST")
                msg = (f"🔴 *STOP LOSS TOCADO (POST-MORTEM)*\n\n"
                       f"🪙 {sym} LONG\n"
                       f"💸 PnL: *{pnl_pct:+.2f}%*\n"
                       f"📊 *Contexto de Cierre:*\n"
                       f"• RSI: {t['rsi_entry']:.1f} (Inicio) → {rsi:.1f} (Actual)\n"
                       f"• Bollinger: {bb_ctx}\n"
                       f"• Motivo: Soporte perforado, el impulso falló.")
                alert(f"t_{t['id']}_l", msg, version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "LOST", t["entry_price"], curr_p)
            elif curr_p >= t["tp2_price"]:
                tracker.update_trade_status(t["id"], "FULL_WON")
                msg = (f"🟢 *TP2 ALCANZADO (STRIKE!)*\n\n"
                       f"🪙 {sym} LONG\n"
                       f"💰 PnL: *{pnl_pct:+.2f}%*\n"
                       f"📊 *Resumen:*\n"
                       f"• RSI Entrada: {t['rsi_entry']:.1f}\n"
                       f"• RSI Cierre: {rsi:.1f}\n"
                       f"✨ Rebote técnico capturado con éxito.")
                alert(f"t_{t['id']}_w", msg, version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "WIN_FULL", t["entry_price"], curr_p)
            elif curr_p >= t["tp1_price"] and t["status"] == "OPEN":
                tracker.update_trade_status(t["id"], "PARTIAL_WON")
                tracker.update_sl(t["id"], t["entry_price"]) # BE
                alert(f"t_{t['id']}_p", f"🟡 *TP1 ASEGURADO*\nBE Activado | Riesgo eliminado.", version=t["version"], reply_to=reply)

def main():
    print("🚀 Scalp Alert Bot V3 (AI Panorama) - INICIANDO")
    update_dynamic_levels()
    
    # Control de tiempo para insights horarios
    last_insight_time = 0 
    
    send_telegram("🤖 *Scalp Bot Multi-Estrategia Online*\n🛡️ V1-TECH: Activa\n🤖 V2-AI: Activa\n📡 CoinGecko Guard: Activo")
    
    while True:
        try:
            prices = get_prices()
            if prices:
                check_strategies(prices)
                monitor_open_trades(prices)
                
                # Insights Horarios: AMBAS PERSONALIDADES (cada 3600 segundos)
                now = time.time()
                if now - last_insight_time > 3600:
                    print("[Robot] Generando panorama horario (Conservador + Scalper)...")
                    panoramas = gemini_analyzer.get_hourly_panorama(prices)
                    # Enviar ambas perspectivas por separado
                    send_telegram(f"🤖 *PANORAMA DEL ROBOT*\n\n{panoramas.get('conservador', 'Sin datos')}")
                    send_telegram(f"🤖 *PANORAMA DEL ROBOT*\n\n{panoramas.get('scalper', 'Sin datos')}")
                    last_insight_time = now
                    
        except Exception as e: print(f"❌ Main Loop Error: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
