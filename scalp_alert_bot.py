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

def get_prices() -> dict:
    """Consolida llamadas para proteger límites de CoinGecko."""
    ids = "ethereum,bittensor,bitcoin"
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
    try:
        r = requests.get(url, timeout=10)
        d = r.json()
        res = {"ETH": d["ethereum"]["usd"], "TAO": d["bittensor"]["usd"], "BTC": d["bitcoin"]["usd"], "USDT_D": indicators.get_usdt_dominance()}
        for sym in ["ETH", "TAO", "BTC"]:
            rsi, bb_u, bb_m, bb_l = indicators.get_indicators(sym, "15m")
            res[f"{sym}_RSI"] = rsi
            res[f"{sym}_BB_U"] = bb_u
            res[f"{sym}_BB_L"] = bb_l
        return res
    except Exception as e:
        print(f"❌ Error fetching prices: {e}")
        return None

def check_strategies(prices: dict):
    if not prices: return
    phase = get_phase()
    
    for sym in ["ETH", "TAO", "BTC"]:
        p, rsi = prices[sym], prices[f"{sym}_RSI"]
        bb_u, bb_l = prices[f"{sym}_BB_U"], prices[f"{sym}_BB_L"]
        L = LEVELS.get(sym)
        
        # --- ESTRATEGIA V1: TÉCNICA ---
        # Short V1
        if phase == "SHORT" and p >= L.get("resistance", L.get("short_entry_high", 999999)) and rsi >= 62:
            tp1 = L['target1']
            sl  = L.get('sl_short', p+100)
            msg = f"📉 *ALERTA TÉCNICA*\nPrecio: ${p:,.2f} | RSI: {rsi:.1f}\n🎯 Target 1: ${tp1}"
            mid = alert(f"{sym}_v1_short", msg, version="V1-TECH")
            if mid:
                tracker.log_trade(sym, "SHORT", p, tp1, L.get('target2', p-100), sl, mid, "V1-TECH")
                gemini_analyzer.log_alert_to_context(sym, "SHORT", p, rsi, tp1, sl, "V1-TECH")

        # Long V1
        elif phase == "LONG" and p <= L.get("long_zone", L.get("support2", 0)) and rsi <= 38:
            tp1 = p + 15
            sl  = L.get('long_sl', p-50)
            msg = f"📈 *ALERTA TÉCNICA*\nPrecio: ${p:,.2f} | RSI: {rsi:.1f}\n🎯 Target 1: ${tp1}"
            mid = alert(f"{sym}_v1_long", msg, version="V1-TECH")
            if mid:
                tracker.log_trade(sym, "LONG", p, tp1, L.get('resistance', p+50), sl, mid, "V1-TECH")
                gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")

        # --- ESTRATEGIA V2: AI ENHANCED ---
        if (rsi >= 60 or rsi <= 40):
            side = "SHORT" if rsi >= 60 else "LONG"
            decision, reason = gemini_analyzer.get_ai_decision(sym, p, side, rsi, bb_u, bb_l, version="V2-AI")
            if decision == "CONFIRM":
                tp1 = L['target1'] if side == "SHORT" else p+30
                sl  = L.get('sl_short', p+100) if side == "SHORT" else L.get('long_sl', p-50)
                msg = f"💎 *IA CONFIRMADA*\n_{reason}_\nPrecio: ${p:,.2f} | RSI: {rsi:.1f}"
                mid = alert(f"{sym}_v2_ai_{side}", msg, version="V2-AI")
                if mid:
                    tracker.log_trade(sym, side, p, tp1, L.get('target2', tp1-50), sl, mid, "V2-AI")
                    gemini_analyzer.log_alert_to_context(sym, side, p, rsi, tp1, sl, "V2-AI")

def monitor_open_trades(prices: dict):
    open_trades = tracker.get_open_trades()
    for t in open_trades:
        sym = t["symbol"]
        if sym not in prices: continue
        curr_p, tipo, reply = prices[sym], t["type"], t["msg_id"]
        
        if tipo == "SHORT":
            if curr_p >= t["sl_price"]:
                tracker.update_trade_status(t["id"], "LOST")
                alert(f"t_{t['id']}_l", f"🔴 SL TOCADO: {sym} SHORT en ${curr_p:.2f}", version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "LOST", t["entry_price"], curr_p)
            elif curr_p <= t["tp2_price"]:
                tracker.update_trade_status(t["id"], "FULL_WON")
                alert(f"t_{t['id']}_w", f"🟢 TP2 ALCANZADO: {sym} SHORT. ¡Victoria!", version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "WIN_FULL", t["entry_price"], curr_p)
            elif curr_p <= t["tp1_price"] and t["status"] == "OPEN":
                tracker.update_trade_status(t["id"], "PARTIAL_WON")
                tracker.update_sl(t["id"], t["entry_price"]) # BE
                alert(f"t_{t['id']}_p", f"🟡 TP1 ASEGURADO: {sym} SHORT. BE activado.", version=t["version"], reply_to=reply)
        elif tipo == "LONG":
            if curr_p <= t["sl_price"]:
                tracker.update_trade_status(t["id"], "LOST")
                alert(f"t_{t['id']}_l", f"🔴 SL TOCADO: {sym} LONG en ${curr_p:.2f}", version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "LOST", t["entry_price"], curr_p)
            elif curr_p >= t["tp2_price"]:
                tracker.update_trade_status(t["id"], "FULL_WON")
                alert(f"t_{t['id']}_w", f"🟢 TP2 ALCANZADO: {sym} LONG. ¡Victoria!", version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "WIN_FULL", t["entry_price"], curr_p)
            elif curr_p >= t["tp1_price"] and t["status"] == "OPEN":
                tracker.update_trade_status(t["id"], "PARTIAL_WON")
                tracker.update_sl(t["id"], t["entry_price"]) # BE
                alert(f"t_{t['id']}_p", f"🟡 TP1 ASEGURADO: {sym} LONG. BE activado.", version=t["version"], reply_to=reply)

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
