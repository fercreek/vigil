"""
swing_bot.py — Zenith Institutional Swing Bot V3.0
Estrategia: Ichimoku Kumo Breakout + Bias Semanal IA + ATR Targets

Targets basados en ATR (no porcentaje fijo):
  TP1 (50%): 2.5×ATR  → primera parcial, mover SL a BE
  TP2 (30%): 5.0×ATR  → extensión swing
  TP3 (20%): 8.0×ATR  → objetivo macro
  SL       : 2.0×ATR  → stop técnico

Ciclo: cada 4H (cierre de vela)
Símbolos: ZEC/USDT, TAO/USDT
"""
import time
import os
import ccxt
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import indicators_swing
import gemini_analyzer
import tracker

load_dotenv()

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SYMBOLS   = ["ZEC/USDT", "TAO/USDT", "BTC/USDT", "ETH/USDT", "SOL/USDT"]
TIMEFRAME = "4h"

# ATR multipliers (validados en backtest)
ATR_SL  = 2.0
ATR_TP1 = 2.5   # 50% de la posición — mover SL a BE al alcanzar
ATR_TP2 = 5.0   # 30% de la posición
ATR_TP3 = 8.0   # 20% de la posición — objetivo macro
MIN_SL_PCT = 0.01  # SL mínimo 1% del precio

# Cooldown entre alertas del mismo símbolo (segundos)
ALERT_COOLDOWN = 3600 * 4
_last_alert: dict = {}

# Anti-whipsaw: no flipear dirección (LONG→SHORT) en menos de 24h
DIRECTION_FLIP_COOLDOWN = 3600 * 24
_last_direction: dict = {}  # {symbol: ("LONG"|"SHORT", timestamp)}

# Minimum ATR filter: señal solo si ATR > 0.5% del precio
MIN_ATR_PCT = 0.005

binance = ccxt.binance({'timeout': 15000})


def send_telegram(msg: str):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
        if not r.ok:
            print(f"  ⚠️  Telegram error {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"  ❌ Telegram send failed: {e}")


def calc_atr(df: pd.DataFrame, period: int = 14) -> float:
    hl  = df["high"] - df["low"]
    hc  = (df["high"] - df["close"].shift()).abs()
    lc  = (df["low"]  - df["close"].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1 / period, adjust=False).mean().iloc[-1])


def _in_cooldown(symbol: str) -> bool:
    last = _last_alert.get(symbol, 0)
    return (time.time() - last) < ALERT_COOLDOWN


def _set_cooldown(symbol: str):
    _last_alert[symbol] = time.time()


def _can_flip_direction(symbol: str, new_side: str) -> bool:
    """Return False if trying to flip direction within 24h cooldown."""
    prev = _last_direction.get(symbol)
    if prev is None:
        return True
    old_side, ts = prev
    if old_side == new_side:
        return True  # Same direction → always OK
    elapsed = time.time() - ts
    return elapsed >= DIRECTION_FLIP_COOLDOWN


def _set_direction(symbol: str, side: str):
    _last_direction[symbol] = (side, time.time())


def build_alert(symbol: str, side: str, price: float, atr: float,
                ai_bias: str, kumo_status: str, tk_cross: str,
                kumo_cloud: dict, analysis: str) -> str:
    """Construye el mensaje de alerta con 3 targets basados en ATR."""
    sl_dist = max(atr * ATR_SL, price * MIN_SL_PCT)

    if side == "LONG":
        sl   = price - sl_dist
        tp1  = price + atr * ATR_TP1
        tp2  = price + atr * ATR_TP2
        tp3  = price + atr * ATR_TP3
        rr1  = round(ATR_TP1 / ATR_SL, 1)
        rr2  = round(ATR_TP2 / ATR_SL, 1)
        rr3  = round(ATR_TP3 / ATR_SL, 1)
        tp1_pct = round((tp1 - price) / price * 100, 1)
        tp2_pct = round((tp2 - price) / price * 100, 1)
        tp3_pct = round((tp3 - price) / price * 100, 1)
        sl_pct  = round((price - sl)  / price * 100, 1)
    else:
        sl   = price + sl_dist
        tp1  = price - atr * ATR_TP1
        tp2  = price - atr * ATR_TP2
        tp3  = price - atr * ATR_TP3
        rr1  = round(ATR_TP1 / ATR_SL, 1)
        rr2  = round(ATR_TP2 / ATR_SL, 1)
        rr3  = round(ATR_TP3 / ATR_SL, 1)
        tp1_pct = round((price - tp1) / price * 100, 1)
        tp2_pct = round((price - tp2) / price * 100, 1)
        tp3_pct = round((price - tp3) / price * 100, 1)
        sl_pct  = round((sl - price)  / price * 100, 1)

    kumo_top = round(kumo_cloud.get("top", 0), 2)
    kumo_bot = round(kumo_cloud.get("bottom", 0), 2)
    tk_icon  = "🟢 Golden Cross" if tk_cross == "GOLDEN" else ("🔴 Dead Cross" if tk_cross == "DEAD" else "⚪ Sin cruce")
    side_icon = "🚀 LONG" if side == "LONG" else "🩸 SHORT"

    # Truncar análisis IA a 600 chars limpio
    analysis_short = analysis[:600].rsplit(" ", 1)[0] + "..." if len(analysis) > 600 else analysis

    msg = (
        f"🏛️ <b>ZENITH INSTITUTIONAL ALERT ({symbol})</b>\n\n"
        f"🌌 <b>ESTRATEGIA</b>: Swing Trend Follower (4H)\n"
        f"📊 <b>BIAS SEMANAL (IA)</b>: {ai_bias} ({side})\n"
        f"☁️ <b>KUMO STATUS</b>: {kumo_status}\n"
        f"   Nube: ${kumo_bot:,.2f} — ${kumo_top:,.2f}\n"
        f"📐 <b>Tenkan/Kijun</b>: {tk_icon}\n\n"
        f"💡 <b>RACIONAL INSTITUCIONAL:</b>\n"
        f"{analysis_short}\n\n"
        f"{'─' * 30}\n"
        f"🪙 <b>Entrada {side_icon}</b>: <code>${price:,.2f}</code>\n"
        f"📏 <b>ATR (14p)</b>: <code>${atr:,.2f}</code>\n\n"
        f"🎯 <b>TP1 (50% posición)</b>: <code>${tp1:,.2f}</code>  +{tp1_pct}%  R:R {rr1}:1\n"
        f"   └ Al alcanzar: mover SL a breakeven\n"
        f"🎯 <b>TP2 (30% posición)</b>: <code>${tp2:,.2f}</code>  +{tp2_pct}%  R:R {rr2}:1\n"
        f"   └ Al alcanzar: tomar parcial, dejar runner\n"
        f"🎯 <b>TP3 (20% runner)</b>: <code>${tp3:,.2f}</code>  +{tp3_pct}%  R:R {rr3}:1\n"
        f"   └ Objetivo macro — dejar correr con BE\n\n"
        f"🛑 <b>SL</b>: <code>${sl:,.2f}</code>  -{sl_pct}%  (ATR × {ATR_SL})\n\n"
        f"⚠️ <i>Gestión: SWING normal si VIX &lt; 25. "
        f"RAPIDA (50% tamaño) si VIX &gt; 25 o DXY &gt; 105</i>\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC"
    )
    return msg, round(sl, 4), round(tp1, 4), round(tp2, 4), round(tp3, 4)


def _has_open_swing(symbol_short: str) -> bool:
    """Check if there's already an open SWING trade for this symbol."""
    open_trades = tracker.get_open_trades()
    for t in open_trades:
        if t["symbol"] == symbol_short and t.get("version") == "SWING":
            return True
    return False


def analyze_symbol(symbol: str):
    """Analiza un símbolo y envía alerta si hay setup válido."""
    sym = symbol.replace("/USDT", "")
    print(f"  🔍 Analizando {symbol} (Swing 4H)...")

    # 0. Position guard — no abrir duplicados
    if _has_open_swing(sym):
        print(f"    ⏸️  Ya hay swing abierto para {sym} — omitiendo")
        return

    # 1. Datos OHLCV
    ohlcv = binance.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=300)
    df    = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)

    # 2. ATR 4H
    atr = calc_atr(df)
    price_now = float(df["close"].iloc[-1])

    # 2b. ATR minimum filter — skip if volatility too low (noisy cloud)
    if atr < price_now * MIN_ATR_PCT:
        print(f"    ⏸️  ATR too low ({atr:.2f} < {price_now * MIN_ATR_PCT:.2f}) — omitiendo")
        return

    # 3. Ichimoku + bias técnico
    technical   = indicators_swing.analyze_swing_signals(df)
    kumo_status = technical["bias"]       # BULL / BEAR / NEUTRAL
    tk_cross    = technical.get("tk_cross", "NONE")
    kumo_cloud  = technical.get("kumo_cloud", {})
    price       = float(technical["price"])

    # 4. Bias semanal IA
    price_ctx = {
        sym: price,
        f"{sym}_RSI": 50.0,
        f"{sym}_EMA_200": float(df["close"].ewm(span=200, adjust=False).mean().iloc[-1]),
        "USDT_D": 8.08
    }
    ai_report = gemini_analyzer.get_weekly_bias(sym, price_ctx)
    ai_bias   = ai_report.get("bias", "NEUTRAL")
    analysis  = ai_report.get("analysis", "Sin análisis disponible.")

    print(f"    Kumo: {kumo_status} | AI Bias: {ai_bias} | ATR: {atr:.2f}")

    # 5. Consenso: técnico + IA deben coincidir, no NEUTRAL
    if ai_bias != kumo_status or ai_bias == "NEUTRAL":
        print(f"    ⏩ Sin consenso ({kumo_status} vs {ai_bias}) — omitiendo")
        return

    side = "LONG" if ai_bias == "BULL" else "SHORT"

    # 6. Direction flip guard — no LONG→SHORT within 24h
    if not _can_flip_direction(symbol, side):
        print(f"    ⏸️  Direction flip blocked ({side}) — 24h cooldown activo")
        return

    # 7. Construir alerta
    msg, sl, tp1, tp2, tp3 = build_alert(
        symbol, side, price, atr,
        ai_bias, kumo_status, tk_cross, kumo_cloud, analysis
    )

    # 8. Enviar via alert_manager (cooldown persistente ante reinicios del hilo)
    import alert_manager as _am
    if _am.alert(f"swing_{sym}_{side}", msg, version="V2-AI-GEMINI", cooldown=ALERT_COOLDOWN) is None:
        print(f"    ⏸️  En cooldown — omitiendo")
        return
    _set_direction(symbol, side)
    tracker.log_trade(sym, side, price, tp1, tp2, sl, None,
                      version="SWING", rsi=50.0, bb="Ichimoku",
                      atr=atr, score=4, alert_type="swing_institutional")
    print(f"    ✅ Alerta SWING enviada — {side} @ ${price:,.2f} | TP3: ${tp3:,.2f}")


def run_zenith_swing():
    print(f"🏛️ ZENITH SWING BOT V3.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    send_telegram(
        "🏛️ <b>ZENITH SWING BOT V3.0 ACTIVADO</b>\n"
        "Estrategia: Ichimoku + Bias IA | 3 Targets ATR\n"
        "Símbolos: " + ", ".join(SYMBOLS)
    )

    while True:
        try:
            import thread_health
            thread_health.heartbeat("swing")
            now = datetime.now().strftime("%H:%M")
            print(f"\n{'─'*40}\n🕐 Ciclo Swing [{now}]")

            for symbol in SYMBOLS:
                try:
                    analyze_symbol(symbol)
                except Exception as e:
                    print(f"  ❌ Error en {symbol}: {e}")

            print("⏳ Próximo ciclo en 4H...")
            for _ in range(240):   # 240 × 60s = 4 horas
                time.sleep(60)
                thread_health.heartbeat("swing")

        except Exception as e:
            import logging
            logging.getLogger("ScalpBot").error("❌ Swing Bot Error: %s", e, exc_info=True)
            time.sleep(300)


if __name__ == "__main__":
    run_zenith_swing()
