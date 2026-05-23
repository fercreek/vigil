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

# Símbolos donde se bloquean señales SHORT (WR < 10% históricamente)
# TAO: 4% WR en SHORT (27 pérdidas consecutivas, tendencia alcista dominante)
NO_SHORT = {"TAO/USDT"}

from exchange_singleton import binance_spot as binance


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

    # Template simplificado (ronda 5 Telegram cleanup) — 9 líneas, sin redundancia
    msg = (
        f"🏛️ <b>SWING {side_icon}</b> {symbol}  ·  Bias: {ai_bias} · Kumo: {kumo_status}\n"
        f"Entry: <code>${price:,.4f}</code>  ATR: ${atr:,.2f}\n"
        f"🎯 TP1: <code>${tp1:,.4f}</code> +{tp1_pct}% (R:R {rr1}:1) — 50% pos\n"
        f"🎯 TP2: <code>${tp2:,.4f}</code> +{tp2_pct}% (R:R {rr2}:1) — 30%\n"
        f"🎯 TP3: <code>${tp3:,.4f}</code> +{tp3_pct}% (R:R {rr3}:1) — runner\n"
        f"🛑 SL: <code>${sl:,.4f}</code> -{sl_pct}%\n"
        f"<i>{tk_icon} · Kumo ${kumo_bot:.0f}-${kumo_top:.0f} · {datetime.now().strftime('%H:%M')}</i>"
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

    # 0b. Consecutive-loss guard — pausa 24h tras 2 pérdidas seguidas en el mismo símbolo
    # Previene entrar en downtrend sostenido (p.ej. ZEC Apr 10-15)
    _recent = tracker.get_recent_closed_trades_by_symbol(sym, limit=4, strategy="SWING")
    _consec_losses = 0
    for _t in _recent:
        if _t["status"] == "LOST":
            _consec_losses += 1
        else:
            break  # si encontramos un win, la racha termina
    if _consec_losses >= 2:
        print(f"    ⏸️  [{sym}] {_consec_losses} pérdidas SWING consecutivas — cooldown 24h activo")
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

    # 4b. EMA50 trend filter — solo entrar con la tendencia de medio plazo (4H)
    # Detectado en análisis de 77 trades: todas las pérdidas post-Apr-9 ocurrieron
    # cuando ZEC estaba bajando. EMA50 en 4H actúa como filtro de tendencia sostenida.
    _ema50_4h = float(df["close"].ewm(span=50, adjust=False).mean().iloc[-1])
    _entry_side = "LONG" if ai_bias == "BULL" else "SHORT"
    if _entry_side == "LONG" and price < _ema50_4h:
        print(f"    ⏩ [EMA50 Trend] {sym} ${price:.2f} < EMA50-4H ${_ema50_4h:.2f} — downtrend, skip")
        return
    if _entry_side == "SHORT" and price > _ema50_4h:
        print(f"    ⏩ [EMA50 Trend] {sym} ${price:.2f} > EMA50-4H ${_ema50_4h:.2f} — uptrend, skip SHORT")
        return

    print(f"    Kumo: {kumo_status} | AI Bias: {ai_bias} | ATR: {atr:.2f} | EMA50: ${_ema50_4h:.2f} ✅")

    # 5. Consenso: técnico + IA deben coincidir, no NEUTRAL
    if ai_bias != kumo_status or ai_bias == "NEUTRAL":
        print(f"    ⏩ Sin consenso ({kumo_status} vs {ai_bias}) — omitiendo")
        return

    side = "LONG" if ai_bias == "BULL" else "SHORT"

    # 5b. NO_SHORT filter — block SHORT signals for chronically losing symbols
    if side == "SHORT" and symbol in NO_SHORT:
        print(f"    ⛔ {symbol} SHORT bloqueado (NO_SHORT list — WR < 10%)")
        return

    # 6. Direction flip guard — no LONG→SHORT within 24h
    if not _can_flip_direction(symbol, side):
        print(f"    ⏸️  Direction flip blocked ({side}) — 24h cooldown activo")
        return

    # 7. Construir alerta
    msg, sl, tp1, tp2, tp3 = build_alert(
        symbol, side, price, atr,
        ai_bias, kumo_status, tk_cross, kumo_cloud, analysis
    )

    # 8. Cooldown check (memoria local + DIRECTION_FLIP_CD ya cubre reinicios)
    if _in_cooldown(symbol):
        print(f"    ⏸️  En cooldown — omitiendo")
        return

    # 9. Enviar con keyboard Activar/Skip (mismo flujo que commodities/scalper_shorts)
    #    Antes: tracker.log_trade() automático sin pedir confirmación → contaminaba WR.
    try:
        from scalp_alert_bot import _store_pending
        import alert_manager as _am
        import requests as _req

        _sid = _store_pending(symbol, side, price, tp1, tp2, sl, atr, 50.0, 4,
                              "swing_institutional", "SWING", None,
                              macro_regime=f"KUMO:{kumo_status}|AI:{ai_bias}")
        _kb = _am.get_signal_keyboard(_sid, symbol, side)

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        _payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
        try:
            from config import ENABLE_TELEGRAM_BUTTONS as _BTN
        except Exception:
            _BTN = True
        if _BTN:
            _payload["reply_markup"] = _kb
        r = _req.post(url, json=_payload, timeout=10)
        if not r.ok or not r.json().get("ok"):
            raise RuntimeError(f"Telegram send failed: {r.status_code}")

        _set_cooldown(symbol)
        _set_direction(symbol, side)
        print(f"    ✅ SWING alerta con keyboard — {side} @ ${price:,.2f} | TP3: ${tp3:,.2f}")
    except Exception as _e:
        # Fallback: send sin keyboard (preserva alerta visible) — NO auto-log a DB
        # User decide manualmente vía /open o /manual_add si quiere registrar
        print(f"    ⚠️ Keyboard fallback ({_e}) — enviando sin botones (sin auto-log)")
        send_telegram(msg)
        _set_cooldown(symbol)
        _set_direction(symbol, side)


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
