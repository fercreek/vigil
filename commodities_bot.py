"""
commodities_bot.py — Zenith Commodities Bot (Conservador)
Instrumentos: Gold (GCM6 / GC=F) + Oil (CLK6 / CLM26.NYM)
Timeframe: 1H (signal) + 15m (timing)
Estrategia: EMA Cross + RSI + DXY Filter + ATR Confirmation
Confluencia minima: 4/5

Targets ATR (conservador):
  TP1 (50%): 2.0x ATR -> mover SL a BE
  TP2 (30%): 3.5x ATR
  TP3 (20%): 5.0x ATR
  SL       : 1.5x ATR (GOLD) | 2.5x ATR (OIL — news-driven volatility)

Cambios May-2026:
  - Fix RSI SHORT condition: rsi > 62 (era 45-65, zona bullish incorrecta)
  - Post-rally filter OIL: si +15% en 10d, requiere RSI < 45 para LONG
  - OPEC suppression: suprime señales OIL 24h antes/después reuniones OPEC
  - SL más amplio en OIL: ATR_SL = 2.5x (era 1.5x)
  - MIN_SL_PCT: SL mínimo 2.0% del precio para OIL (protección vs news spikes 1H)
  - Signal keyboard (Activar/Skip) en lugar de log_trade inmediato
"""
import time
import os
import math
import pandas as pd
import yfinance as yf
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dotenv import load_dotenv
from logger_core import logger
import tracker
import thread_health

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Instruments ---
INSTRUMENTS = {
    "GOLD": {"yf": "GC=F",      "name": "Gold Jun-2026",  "decimals": 2},
    "OIL":  {"yf": "CLM26.NYM", "name": "Crude Jun-2026", "decimals": 2},
}

# --- ATR Multipliers (por instrumento) ---
ATR_TP1 = 2.0
ATR_TP2 = 3.5
ATR_TP3 = 5.0
ATR_SL_BY_KEY = {
    "GOLD": 1.5,   # Gold: menos volátil en 1H
    "OIL":  2.5,   # OIL: news spikes de $3-4 en una sola vela 1H (OPEC, geopolítica)
}

# --- Strategy thresholds ---
MIN_CONFLUENCE     = 4       # Raised 3→4 (Apr-29: 3/5 generated too many false signals)
MIN_ATR_PCT        = 0.003   # ATR > 0.3% del precio
MIN_SL_PCT_OIL     = 0.020   # SL mínimo 2.0% del precio en OIL (protección vs news spikes)
DXY_GOLD_LONG_MAX  = 103.0   # DXY < 103 favorece gold LONG
DXY_GOLD_SHORT_MIN = 103.0   # DXY > 103 favorece gold SHORT (ignored if GOLD_BULL_LOCK active)

# --- Post-rally filter (OIL) ---
OIL_RALLY_DAYS     = 10      # ventana para medir rally
OIL_RALLY_PCT      = 0.15    # si OIL sube >15% en 10d, endurecer filtro LONG
OIL_RALLY_RSI_MAX  = 45.0    # RSI max para LONG en modo post-rally (normal: 55)

# --- Gold bull market lock ---
GOLD_BULL_THRESHOLD = 2500.0  # Gold > $2,500 = PHY alcista activo → LONG only, no shorts
                               # DXY/Gold correlation broke in 2026 (gold ATH despite DXY strength)
SP500_VERDE_MIN     = 7000    # SP500 > this → no OIL SHORT (bull regime, oil upward bias)

# --- OPEC Meeting suppression (OIL signals suprimidas ±24h) ---
# Actualizar antes de cada reunión OPEC+. Formato: "YYYY-MM-DD"
OPEC_MEETING_DATES = [
    "2026-05-05",  # OPEC+ meeting May 2026 → dump post-decisión May 6
    "2026-06-01",  # próxima reunión estimada
    "2026-09-01",  # Q3 2026 (estimado)
]

# --- Cooldowns ---
ALERT_COOLDOWN       = 3600       # 1h entre alertas del mismo instrumento
DIRECTION_FLIP_CD    = 3600 * 12  # 12h antes de flipear direccion
CHECK_INTERVAL       = 900        # 15 min entre ciclos

_last_alert: dict = {}
_last_direction: dict = {}  # {key: (side, timestamp)}
_last_status: dict = {}     # for /commodities command


# --- Telegram ---
def send_telegram(msg: str):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"
        }, timeout=10)
        if not r.ok:
            logger.warning("Telegram error %d: %s", r.status_code, r.text[:120])
    except Exception as e:
        logger.error("Telegram send failed: %s", e)


# --- Data Fetching ---
def _fetch_ohlcv(yf_ticker: str, interval: str = "1h", period: str = "30d") -> pd.DataFrame:
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(yf.download, yf_ticker, period=period, interval=interval, progress=False)
        df = future.result(timeout=20)
    except (FuturesTimeout, Exception) as e:
        logger.error("yfinance fetch %s failed: %s", yf_ticker, e)
        return pd.DataFrame()
    finally:
        pool.shutdown(wait=False)
    if df is None or df.empty:
        return pd.DataFrame()
    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df


def _get_dxy() -> float:
    try:
        import indicators
        dxy, _ = indicators.get_dxy_vix()
        return dxy
    except Exception:
        return 0.0


# --- Indicators (self-contained, no ccxt dependency) ---
def _calc_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def _calc_atr(df: pd.DataFrame, period: int = 14) -> float:
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"]  - df["Close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1/period, adjust=False).mean().iloc[-1])


def _calc_ema(series: pd.Series, span: int) -> float:
    return float(series.ewm(span=span, adjust=False).mean().iloc[-1])


# --- Guards ---
def _in_cooldown(key: str) -> bool:
    return (time.time() - _last_alert.get(key, 0)) < ALERT_COOLDOWN


def _can_flip(key: str, new_side: str) -> bool:
    prev = _last_direction.get(key)
    if prev is None:
        return True
    old_side, ts = prev
    if old_side == new_side:
        return True
    return (time.time() - ts) >= DIRECTION_FLIP_CD


def _has_open_commodity(key: str) -> bool:
    for t in tracker.get_open_trades():
        if t["symbol"] == key and t.get("version") == "COMMODITY":
            return True
    return False


def _monitor_open_commodity(key: str, inst: dict):
    """Check SL/TP on open COMMODITY trades using the correct futures price."""
    open_trades = [t for t in tracker.get_open_trades()
                   if t["symbol"] == key and t.get("version") == "COMMODITY"]
    if not open_trades:
        return

    try:
        raw = yf.Ticker(inst["yf"]).fast_info.last_price
        price = float(raw or 0)
    except Exception as e:
        logger.warning("    %s: monitor price fetch error: %s", key, e)
        return
    if not price:
        # fast_info returns None for some futures tickers; fall back to history
        try:
            df_fb = _fetch_ohlcv(inst["yf"], interval="1h", period="2d")
            price = float(df_fb["Close"].iloc[-1]) if not df_fb.empty else 0.0
        except Exception as e:
            logger.warning("    %s: monitor fallback price fetch error: %s", key, e)
        if not price:
            logger.warning("    %s: monitor skip — could not resolve price (fast_info=None, history empty)", key)
            return

    dec = inst["decimals"]
    for t in open_trades:
        entry = t["entry_price"]
        sl    = t["sl_price"]
        tp1   = t["tp1_price"]
        tp2   = t["tp2_price"]
        side  = t["type"]

        if side == "LONG":
            pnl_pct = (price - entry) / entry * 100
            if price <= sl:
                tracker.update_trade_status(t["id"], "LOST")
                send_telegram(
                    f"🛑 <b>COMMODITY SL HIT: {key}</b>\n"
                    f"{side} @ ${entry:,.{dec}f}\n"
                    f"Precio: <code>${price:,.{dec}f}</code> ≤ SL <code>${sl:,.{dec}f}</code>\n"
                    f"💸 PnL: <b>{pnl_pct:+.2f}%</b>"
                )
                logger.info("    %s LOST (SL hit) @ %.{dec}f", key, price)
            elif tp2 and price >= tp2:
                tracker.update_trade_status(t["id"], "FULL_WON")
                send_telegram(
                    f"🟢 <b>COMMODITY TP2 HIT: {key}</b>\n"
                    f"{side} @ ${entry:,.{dec}f}\n"
                    f"Precio: <code>${price:,.{dec}f}</code>\n"
                    f"💰 PnL: <b>{pnl_pct:+.2f}%</b>"
                )
            elif tp1 and price >= tp1 and t["status"] == "OPEN":
                tracker.update_trade_status(t["id"], "PARTIAL_WON")
                new_sl = entry  # move to breakeven
                tracker.update_sl(t["id"], new_sl)
                send_telegram(
                    f"🎯 <b>COMMODITY TP1 HIT: {key}</b>\n"
                    f"{side} | SL movido a BE: <code>${new_sl:,.{dec}f}</code>\n"
                    f"💰 Parcial: <b>{pnl_pct:+.2f}%</b>"
                )
        else:  # SHORT
            pnl_pct = (entry - price) / entry * 100
            if price >= sl:
                tracker.update_trade_status(t["id"], "LOST")
                send_telegram(
                    f"🛑 <b>COMMODITY SL HIT: {key}</b>\n"
                    f"{side} @ ${entry:,.{dec}f}\n"
                    f"Precio: <code>${price:,.{dec}f}</code> ≥ SL <code>${sl:,.{dec}f}</code>\n"
                    f"💸 PnL: <b>{pnl_pct:+.2f}%</b>"
                )
            elif tp2 and price <= tp2:
                tracker.update_trade_status(t["id"], "FULL_WON")
                send_telegram(
                    f"🟢 <b>COMMODITY TP2 HIT: {key}</b>\n"
                    f"{side} @ ${entry:,.{dec}f}\n"
                    f"Precio: <code>${price:,.{dec}f}</code>\n"
                    f"💰 PnL: <b>{pnl_pct:+.2f}%</b>"
                )
            elif tp1 and price <= tp1 and t["status"] == "OPEN":
                tracker.update_trade_status(t["id"], "PARTIAL_WON")
                new_sl = entry
                tracker.update_sl(t["id"], new_sl)
                send_telegram(
                    f"🎯 <b>COMMODITY TP1 HIT: {key}</b>\n"
                    f"{side} | SL movido a BE: <code>${new_sl:,.{dec}f}</code>\n"
                    f"💰 Parcial: <b>{pnl_pct:+.2f}%</b>"
                )


# --- Core Analysis ---
def analyze_commodity(key: str, inst: dict):
    yf_ticker = inst["yf"]
    dec = inst["decimals"]
    logger.info("  Commodities: analizando %s (%s)...", key, yf_ticker)

    # Position guard
    if _has_open_commodity(key):
        logger.info("    %s: ya hay posicion abierta, omitiendo", key)
        return

    # Cooldown
    if _in_cooldown(key):
        logger.info("    %s: en cooldown, omitiendo", key)
        return

    # Fetch 1H data
    df_1h = _fetch_ohlcv(yf_ticker, interval="1h", period="30d")
    if df_1h.empty or len(df_1h) < 200:
        logger.warning("    %s: datos insuficientes 1H (%d bars)", key, len(df_1h) if not df_1h.empty else 0)
        return

    # Indicators on 1H
    price = float(df_1h["Close"].iloc[-1])
    rsi   = _calc_rsi(df_1h["Close"])
    atr   = _calc_atr(df_1h)
    ema50 = _calc_ema(df_1h["Close"], 50)
    ema200 = _calc_ema(df_1h["Close"], 200)
    dxy = _get_dxy()

    # ATR minimum filter
    if atr < price * MIN_ATR_PCT:
        logger.info("    %s: ATR too low (%.2f < %.2f)", key, atr, price * MIN_ATR_PCT)
        _last_status[key] = {"price": price, "rsi": rsi, "atr": atr, "signal": "ATR bajo", "time": datetime.now()}
        return

    # --- OPEC suppression (OIL only) ---
    if key == "OIL":
        from datetime import date, timedelta
        today_str = date.today().isoformat()
        for meeting_date in OPEC_MEETING_DATES:
            try:
                md = date.fromisoformat(meeting_date)
                if abs((date.today() - md).days) <= 1:
                    logger.info("    OIL: OPEC meeting ±24h (%s) — señal suprimida", meeting_date)
                    _last_status[key] = {"price": price, "rsi": round(rsi, 1), "atr": round(atr, 2),
                                         "signal": f"SUPRIMIDA (OPEC {meeting_date})", "time": datetime.now()}
                    return
            except ValueError:
                pass

    # --- Post-rally filter (OIL LONG): si rally >15% en 10d, exigir RSI < 45 ---
    post_rally_active = False
    if key == "OIL" and len(df_1h) >= OIL_RALLY_DAYS * 24:
        price_10d_ago = float(df_1h["Close"].iloc[-(OIL_RALLY_DAYS * 24)])
        rally_10d = (price - price_10d_ago) / price_10d_ago if price_10d_ago > 0 else 0
        if rally_10d > OIL_RALLY_PCT:
            post_rally_active = True
            logger.info("    OIL: post-rally activo (%.1f%% en %dd) — RSI max %.0f para LONG",
                        rally_10d * 100, OIL_RALLY_DAYS, OIL_RALLY_RSI_MAX)

    # --- Confluence Scoring ---
    long_score = 0
    short_score = 0

    # 1. EMA Cross
    if ema50 > ema200:
        long_score += 1
    else:
        short_score += 1

    # 2. RSI
    # LONG: RSI en zona moderada-baja (no comprar overbought)
    # SHORT: RSI overbought (> 62 = señal clara de sobrecompra)
    rsi_long_max = OIL_RALLY_RSI_MAX if (key == "OIL" and post_rally_active) else 55.0
    if 30 < rsi < rsi_long_max:
        long_score += 1
    if rsi > 62:
        short_score += 1

    # 3. Price vs EMA200
    if price > ema200:
        long_score += 1
    else:
        short_score += 1

    # 4. DXY Filter
    if dxy > 0:
        if key == "GOLD":
            if dxy < DXY_GOLD_LONG_MAX:
                long_score += 1
            if dxy > DXY_GOLD_SHORT_MIN:
                short_score += 1
        else:  # OIL — DXY inverse correlation less strong
            if dxy < 104:
                long_score += 1
            if dxy > 104:
                short_score += 1

    # 5. ATR confirmation (already passed min filter, counts as +1)
    long_score += 1
    short_score += 1

    # --- Macro regime guards ---
    # Gold bull lock
    if key == "GOLD" and price > GOLD_BULL_THRESHOLD:
        short_score = 0
        logger.info("    GOLD: bull lock active (price $%.0f > $%.0f) — shorts suppressed", price, GOLD_BULL_THRESHOLD)

    # SP500 VERDE: no oil shorts in bull equities regime
    if key == "OIL":
        try:
            import yfinance as _yf
            spy_price = float(_yf.Ticker("SPY").fast_info.last_price or 0)
            sp500_approx = spy_price * 10
            if sp500_approx > SP500_VERDE_MIN:
                short_score = 0
                logger.info("    OIL: SP500 VERDE (%.0f > %d) — oil shorts suppressed", sp500_approx, SP500_VERDE_MIN)
        except Exception:
            pass

    # --- Determine signal ---
    side = None
    score = 0
    if long_score >= MIN_CONFLUENCE and long_score > short_score:
        side = "LONG"
        score = long_score
    elif short_score >= MIN_CONFLUENCE and short_score > long_score:
        side = "SHORT"
        score = short_score

    status_info = {
        "price": price, "rsi": round(rsi, 1), "atr": round(atr, 2),
        "ema50": round(ema50, 2), "ema200": round(ema200, 2), "dxy": dxy,
        "long_score": long_score, "short_score": short_score,
        "signal": f"{side} ({score}/5)" if side else "Sin senal",
        "time": datetime.now(),
    }
    _last_status[key] = status_info

    if not side:
        logger.info("    %s: sin confluencia (L:%d S:%d)", key, long_score, short_score)
        return

    # Direction flip guard
    if not _can_flip(key, side):
        logger.info("    %s: direction flip blocked (%s), 12h cooldown", key, side)
        return

    # --- Build alert ---
    atr_sl_mult = ATR_SL_BY_KEY.get(key, 1.5)
    sl_dist = atr * atr_sl_mult

    # Ensure minimum SL distance for OIL (news spikes can exceed 1H ATR in one candle)
    if key == "OIL":
        min_sl_dist = price * MIN_SL_PCT_OIL
        if sl_dist < min_sl_dist:
            logger.info("    OIL: SL ampliado ATR (%.2f) < MIN_SL_PCT (%.2f)", sl_dist, min_sl_dist)
            sl_dist = min_sl_dist

    if side == "LONG":
        sl  = round(price - sl_dist, dec)
        tp1 = round(price + atr * ATR_TP1, dec)
        tp2 = round(price + atr * ATR_TP2, dec)
        tp3 = round(price + atr * ATR_TP3, dec)
    else:
        sl  = round(price + sl_dist, dec)
        tp1 = round(price - atr * ATR_TP1, dec)
        tp2 = round(price - atr * ATR_TP2, dec)
        tp3 = round(price - atr * ATR_TP3, dec)

    rr1 = round(ATR_TP1 / atr_sl_mult, 1)
    rr2 = round(ATR_TP2 / atr_sl_mult, 1)
    rr3 = round(ATR_TP3 / atr_sl_mult, 1)
    side_icon = "LONG" if side == "LONG" else "SHORT"
    strength = "FUERTE" if score >= 4 else "VALIDA"

    msg = (
        f"<b>COMMODITIES ALERT ({key})</b>\n"
        f"{inst['name']}\n\n"
        f"<b>ESTRATEGIA</b>: Conservadora 1H\n"
        f"<b>Confluencia</b>: {score}/5 ({strength})\n"
        f"  EMA50 {'&gt;' if ema50 > ema200 else '&lt;'} EMA200\n"
        f"  RSI: {rsi:.1f}\n"
        f"  DXY: {dxy:.2f}\n"
        f"  ATR: ${atr:,.2f}\n\n"
        f"{'─' * 28}\n"
        f"<b>Entrada {side_icon}</b>: <code>${price:,.{dec}f}</code>\n\n"
        f"TP1 (50%): <code>${tp1:,.{dec}f}</code>  R:R {rr1}:1\n"
        f"  Mover SL a breakeven\n"
        f"TP2 (30%): <code>${tp2:,.{dec}f}</code>  R:R {rr2}:1\n"
        f"TP3 (20%): <code>${tp3:,.{dec}f}</code>  R:R {rr3}:1\n\n"
        f"SL: <code>${sl:,.{dec}f}</code>  (ATR x {atr_sl_mult})\n\n"
        f"<i>Bot conservador. Confluencia minima 3/5.</i>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')} UTC"
    )

    # Wire signal keyboard (Activar / Skip) — mismo flujo que strategies.py
    try:
        from scalp_alert_bot import _store_pending
        import alert_manager as _am
        import requests as _req

        _sid = _store_pending(key, side, price, tp1, tp2, sl, atr, rsi, score,
                              "commodity_conservative", "COMMODITY", None,
                              macro_regime=f"OIL_RALLY:{post_rally_active}" if key == "OIL" else "")
        _kb = _am.get_signal_keyboard(_sid, key, side)

        # Send with inline keyboard
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = _req.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": _kb,
        }, timeout=10)
        mid = str(r.json().get("result", {}).get("message_id", "")) if r.ok else None
        if not mid:
            logger.warning("    %s: Telegram send failed, logging trade direct", key)
            raise RuntimeError("send failed")
    except Exception as _e:
        # Fallback: log directamente si falla el import o el send
        logger.warning("    %s: signal keyboard fallback (%s)", key, _e)
        send_telegram(msg)
        tracker.log_trade(key, side, price, tp1, tp2, sl, None,
                          version="COMMODITY", rsi=rsi, bb="EMA_Cross",
                          atr=atr, score=score, alert_type="commodity_conservative")

    _last_alert[key] = time.time()
    _last_direction[key] = (side, time.time())
    logger.info("    %s: alerta enviada — %s @ $%s | Score %d/5 | post_rally=%s",
                key, side, f"{price:,.{dec}f}", score, post_rally_active)


def get_status_html() -> str:
    """Returns HTML status for /commodities Telegram command."""
    if not _last_status:
        return "<b>COMMODITIES BOT</b>\n\nSin datos aun. Espera el primer ciclo (15 min)."

    msg = "<b>COMMODITIES BOT</b>\n\n"
    for key, st in _last_status.items():
        name = INSTRUMENTS.get(key, {}).get("name", key)
        msg += (
            f"<b>{name}</b>\n"
            f"  Precio: <code>${st['price']:,.2f}</code>\n"
            f"  RSI: {st['rsi']} | ATR: ${st['atr']:,.2f}\n"
            f"  Signal: {st['signal']}\n"
            f"  Update: {st['time'].strftime('%H:%M')}\n\n"
        )
    return msg


# --- Main Loop ---
def run_commodities_bot():
    logger.info("COMMODITIES BOT ACTIVADO — Gold (GCM6) + Oil (CLK6)")
    send_telegram(
        "<b>COMMODITIES BOT ACTIVADO</b>\n"
        "Estrategia: Conservadora 1H\n"
        "Instrumentos: Gold (GCM6), Oil (CLK6)\n"
        "Ciclo: cada 15 min"
    )

    while True:
        try:
            thread_health.heartbeat("commodities")
            now = datetime.now().strftime("%H:%M")
            logger.info("Commodities ciclo [%s]", now)

            for key, inst in INSTRUMENTS.items():
                try:
                    _monitor_open_commodity(key, inst)
                    analyze_commodity(key, inst)
                except Exception as e:
                    logger.error("Commodities %s error: %s", key, e, exc_info=True)

            _sleep_steps = max(1, CHECK_INTERVAL // 60)
            for _ in range(_sleep_steps):
                time.sleep(60)
                thread_health.heartbeat("commodities")

        except Exception as e:
            logger.error("Commodities loop error: %s", e, exc_info=True)
            time.sleep(60)


if __name__ == "__main__":
    run_commodities_bot()
