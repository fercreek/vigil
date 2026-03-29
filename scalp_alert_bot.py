#!/usr/bin/env python3
"""
Scalp Alert Bot — ETH / TAO / BTC
Envía alertas a Telegram cuando los precios tocan niveles clave del plan.
Requiere: pip install requests
"""

import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# ─── CONFIGURACIÓN — edita estos valores ───────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))
PHASE_FILE = "phase.txt"
# ───────────────────────────────────────────────────────────────────────────

def get_phase() -> str:
    if not os.path.exists(PHASE_FILE):
        return "SHORT" # Fase por defecto
    with open(PHASE_FILE, "r") as f:
        return f.read().strip()

def set_phase(phase: str):
    with open(PHASE_FILE, "w") as f:
        f.write(phase)
    send_telegram(f"🔄 *CAMBIO DE ESTRATEGIA*: Fase actualizada a `{phase}`")
    print(f"[*] Fase actualizada a: {phase}")

import indicators
import ccxt

# ─── NIVELES DEL PLAN ──────────────────────────────────────────────────────
LEVELS = {
    "ETH": {"short_entry_high": 2037, "sl_short": 2045, "target1": 1960, "target2": 1930, "long_zone": 1905},
    "TAO": {"resistance": 320, "target1": 290, "target2": 270, "long_zone": 265, "long_sl": 238},
    "BTC": {"resistance": 68283, "support1": 65000, "support2": 62987}
}

def update_dynamic_levels():
    """Calcula Soportes/Resistencias Diarios basados en ayer (Pivot Points)."""
    print("\n🔄 Actualizando niveles dinámicos del día (Pivot Points)...")
    binance = ccxt.binance()
    gateio = ccxt.gateio()
    
    symbols = {
        "ETH": (binance, "ETH/USDT"),
        "BTC": (binance, "BTC/USDT"),
        "TAO": (gateio, "TAO/USDT")
    }
    
    for key, (exchange, sym) in symbols.items():
        try:
            # Obtener vela diaria de "ayer"
            ohlcv = exchange.fetch_ohlcv(sym, timeframe='1d', limit=2)
            if len(ohlcv) < 2: continue
            
            # La vela anterior es la cerrada ([0] si limit=2)
            ayer = ohlcv[0]
            h, l, c = ayer[2], ayer[3], ayer[4]
            
            # Pivot (P) = (H + L + C) / 3
            p = (h + l + c) / 3
            r1 = (2 * p) - l
            s1 = (2 * p) - h
            
            # Actualizar LEVELS
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
                
            print(f"✅ {key} actualizado: Resistencia(R1) ${r1:,.2f} | Soporte(S1) ${s1:,.2f}")
        except Exception as e:
            print(f"❌ Error actualizando {key}: {e}")
    
    send_telegram("📌 *Niveles dinámicos actualizados* basándonos en el cierre de ayer. Consultar Dashboard para ver los valores exactos.")
# ───────────────────────────────────────────────────────────────────────────

fired = {}   # evita repetir la misma alerta

def send_telegram(msg: str, reply_to: str = None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    try:
        r = requests.post(url, json=payload, timeout=10)
        d = r.json()
        if d.get("ok"):
            return str(d["result"]["message_id"])
        print(f"[Telegram error] {r.text}")
    except Exception as e:
        print(f"[Telegram error] {e}")
    return None

def alert(key: str, msg: str, cooldown: int = 300, reply_to: str = None):
    """Dispara alerta una sola vez cada `cooldown` segundos."""
    now = time.time()
    if fired.get(key, 0) + cooldown < now:
        fired[key] = now
        ts = datetime.now().strftime("%H:%M:%S")
        full = f"⚡ *SCALP ALERT* `{ts}`\n{msg}"
        print(full)
        return send_telegram(full, reply_to)
    return None

def clear(key: str):
    fired.pop(key, None)

import indicators

def get_prices() -> dict:
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=ethereum,bittensor,bitcoin&vs_currencies=usd&include_24hr_change=true"
    )
    r = requests.get(url, timeout=10)
    d = r.json()
    
    # Obtener indicadores (RSI + Bollinger Bands)
    usdt_d = indicators.get_usdt_dominance()
    
    # Pack de indicadores por moneda
    eth_rsi, eth_bb_u, eth_bb_m, eth_bb_l = indicators.get_indicators("ETH", "15m") # Usamos 15m para gatillo rápido
    tao_rsi, tao_bb_u, tao_bb_m, tao_bb_l = indicators.get_indicators("TAO", "15m")
    btc_rsi, btc_bb_u, btc_bb_m, btc_bb_l = indicators.get_indicators("BTC", "15m")
    
    # También necesitamos RSI 1h para la tendencia macro
    eth_rsi_1h = indicators.get_rsi("ETH", "1h")
    tao_rsi_1h = indicators.get_rsi("TAO", "1h")
    return {
        "ETH": d["ethereum"]["usd"],
        "TAO": d["bittensor"]["usd"],
        "BTC": d["bitcoin"]["usd"],
        "ETH_chg": d["ethereum"]["usd_24h_change"],
        "TAO_chg": d["bittensor"]["usd_24h_change"],
        "BTC_chg": d["bitcoin"]["usd_24h_change"],
        "USDT_D": usdt_d,
        "ETH_RSI_15M": eth_rsi, "ETH_BB_U": eth_bb_u, "ETH_BB_L": eth_bb_l,
        "TAO_RSI_15M": tao_rsi, "TAO_BB_U": tao_bb_u, "TAO_BB_L": tao_bb_l,
        "BTC_RSI_15M": btc_rsi, "BTC_BB_U": btc_bb_u, "BTC_BB_L": btc_bb_l
    }

import tracker

def check_eth(p: float, rsi_15m: float, usdt_d: float, bb_u: float, bb_l: float):
    L = LEVELS["ETH"]
    phase = get_phase()

    if phase == "SHORT":
        # ESTRATEGIA V2: Resistencia Dinámica + RSI 60 + Rotura BB Superior
        if p >= L["sl_short"]:
            alert("eth_sl", f"🔴 ETH SL SHORT ACTIVADO — ${p:.2f}")
        elif p >= L["short_entry_high"] and rsi_15m >= 60 and (bb_u and p >= bb_u):
            msg_id = alert("eth_short", f"🔴 ETH — V2 SHORT CONFIRMADO\nPrecio: ${p:.2f} | RSI: {rsi_15m:.1f} | BB: Rotura Superior\n✅ Trade registrado.")
            if msg_id:
                tracker.log_trade("ETH", "SHORT", p, L["target1"], L["target2"], L["sl_short"], msg_id)
        
        if p <= L["long_zone"] and usdt_d < 8.00:
            msg = f"🟢 ETH ZONA LONG ALCANZADA — ${p:.2f}\nUSDT.D: {usdt_d:.2f}% (Bajando)\nCambiando a *MODO LONG*."
            alert("eth_long_switch", msg)
            set_phase("LONG")
    
    elif phase == "LONG":
        # Gatillo LONG: RSI 15m cruza arriba de 30 mientras 1h está abajo
        if rsi_15m >= 30 and p <= L["long_zone"] + 10:
             msg_id = alert("eth_long_trigger", f"🚀 ETH — Cruce alcista RSI 15m detectado ({rsi_15m:.1f}). ¡ENTRADA LONG!\n✅ Trade registrado en sistema.")
             if msg_id:
                 tracker.log_trade("ETH", "LONG", p, p + 50, L["short_entry_high"], p - 50, msg_id)

def check_tao(p: float, rsi_15m: float, usdt_d: float, bb_u: float, bb_l: float):
    L = LEVELS["TAO"]
    phase = get_phase()

    if phase == "SHORT":
        if p >= L["resistance"] and rsi_15m >= 60 and (bb_u and p >= bb_u):
            msg_id = alert("tao_res", f"🔴 TAO — V2 SHORT CONFIRMADO\nPrecio: ${p:.1f} | RSI: {rsi_15m:.1f}\n✅ Trade registrado.")
            if msg_id:
                tracker.log_trade("TAO", "SHORT", p, L["target1"], L["target2"], p + 10, msg_id)
        
        if p <= L["long_zone"] and usdt_d < 8.00:
            msg = f"🟢 TAO ZONA LONG ALCANZADA — ${p:.1f}\nCambiando a *MODO LONG*."
            alert("tao_long_switch", msg)
            set_phase("LONG")

    elif phase == "LONG":
        if rsi_15m <= 40 and (bb_l and p <= bb_l) and p <= L["long_zone"] + 5:
            msg_id = alert("tao_long_trigger", f"🚀 TAO — V2 LONG CONFIRMADO\nPrecio: ${p:.1f} | RSI: {rsi_15m:.1f}\n✅ Trade registrado.")
            if msg_id:
                tracker.log_trade("TAO", "LONG", p, p + 15, L["resistance"], L["long_sl"], msg_id)

def check_btc(p: float, rsi_15m: float, bb_u: float, bb_l: float):
    L = LEVELS["BTC"]
    if rsi_15m >= 65 and (bb_u and p >= bb_u):
        alert("btc_short", f"🟠 BTC — Oportunidad SHORT V2\nPrecio: ${p:,.0f} | RSI: {rsi_15m:.1f}")
    elif rsi_15m <= 35 and (bb_l and p <= bb_l):
        alert("btc_long", f"🔵 BTC — Oportunidad LONG V2\nPrecio: ${p:,.0f} | RSI: {rsi_15m:.1f}")

def monitor_open_trades(prices_dict: dict):
    open_trades = tracker.get_open_trades()
    for t in open_trades:
        sym = t["symbol"]
        if sym not in prices_dict: continue
        
        current_p = prices_dict[sym]
        tipo = t["type"]
        status = t["status"]
        reply = t["msg_id"]
        
        if tipo == "SHORT":
            if current_p >= t["sl_price"]:
                tracker.update_trade_status(t["id"], "LOST")
                alert(f"trade_{t['id']}_lost", f"🔴🔴 SCALP CERRADO: {sym} SHORT en PÉRDIDA. SL tocado a ${current_p:.2f}", reply_to=reply)
            elif current_p <= t["tp2_price"]:
                tracker.update_trade_status(t["id"], "FULL_WON")
                alert(f"trade_{t['id']}_full", f"🟢🟢 SCALP COMPLETADO: {sym} SHORT. ¡Ambos Targets (TP2 ${t['tp2_price']:.2f}) tocados!", reply_to=reply)
            elif current_p <= t["tp1_price"] and status == "OPEN":
                tracker.update_trade_status(t["id"], "PARTIAL_WON")
                tracker.update_sl(t["id"], t["entry_price"]) # Trailing Stop a Break Even
                alert(f"trade_{t['id']}_partial", f"🟡🟢 SCALP ASEGURADO: {sym} SHORT. Target 1 (${t['tp1_price']:.2f}) tocado. Mover SL a break even.", reply_to=reply)

        elif tipo == "LONG":
            if current_p <= t["sl_price"]:
                tracker.update_trade_status(t["id"], "LOST")
                alert(f"trade_{t['id']}_lost", f"🔴🔴 SCALP CERRADO: {sym} LONG en PÉRDIDA. SL tocado a ${current_p:.2f}", reply_to=reply)
            elif current_p >= t["tp2_price"]:
                tracker.update_trade_status(t["id"], "FULL_WON")
                alert(f"trade_{t['id']}_full", f"🟢🟢 SCALP COMPLETADO: {sym} LONG. ¡Ambos Targets (TP2 ${t['tp2_price']:.2f}) tocados!", reply_to=reply)
            elif current_p >= t["tp1_price"] and status == "OPEN":
                tracker.update_trade_status(t["id"], "PARTIAL_WON")
                tracker.update_sl(t["id"], t["entry_price"]) # Trailing Stop a Break Even
                alert(f"trade_{t['id']}_partial", f"🟡🟢 SCALP ASEGURADO: {sym} LONG. Target 1 (${t['tp1_price']:.2f}) tocado. Mover SL a break even.", reply_to=reply)

def main():
    print("=" * 50)
    print("  Scalp Alert Bot — INDICADORES ACTIVOS + UI")
    print("  Revisando cada 30s")
    print("=" * 50)
    
    # Inicializar niveles dinámicos al arrancar
    update_dynamic_levels()
    
    send_telegram(
        "🤖 *Scalp Alert Bot INICIADO*\n"
        "Monitoreando: ETH · TAO · BTC\n"
        "Intervalo: 30 segundos\n\n"
        "*Plan activo:*\n"
        "FASE 1 — SHORT ETH/TAO\n"
        "Esperando fondo para LONG TAO"
    )

    while True:
        try:
            prices = get_prices()
            # Monitorear operaciones abiertas (Take Profit / Stop Loss)
            monitor_open_trades(prices)
        except Exception as e:
            print(f"[Error] {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
