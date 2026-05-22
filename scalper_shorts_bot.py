"""
scalper_shorts_bot.py — Zenith Scalper Shorts Agent

Instrumentos: DOGE, FIL, TAO (Binance Futures perpetuos)
Timeframe: 1H señal + 1D EMA200 macro guard
Estrategia: SHORT scalper — 5 condiciones, mínimo 4/5

Condiciones de entrada SHORT:
  1. RSI >= 65                          (sobrecompra)
  2. Precio >= BB_upper * 0.99          (toca banda superior)
  3. Precio > EMA200 (1H)               (sobre tendencia — zona de distribución)
  4. EMA9 < EMA21 (1H)                  (cruce bajista reciente)
  5. Funding rate > 0.03% (longs crowded) (+1 contrarian)

Macro guard:
  - Si precio_1D < EMA200_1D → bloquea SHORT (ya en tendencia bajista, no scalp)

ATR targets (SHORT):
  SL : entry + 2.0×ATR
  TP1: entry - 1.5×ATR (50% cierre → mover SL a BE)
  TP2: entry - 3.0×ATR
  TP3: entry - 5.0×ATR
"""

import time
import os
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from logger_core import logger
import tracker
import thread_health

load_dotenv()

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Instruments ---
INSTRUMENTS = {
    "DOGE": {"ccxt": "DOGE/USDT:USDT", "name": "Dogecoin",  "decimals": 5},
    "FIL":  {"ccxt": "FIL/USDT:USDT",  "name": "Filecoin",  "decimals": 3},
    "TAO":  {"ccxt": "TAO/USDT:USDT",  "name": "Bittensor", "decimals": 2},
}

# --- Strategy thresholds ---
RSI_SHORT_ENTRY   = 65.0    # RSI mínimo para considerar short (scalper — más exigente que V1-SHORT)
BB_PROXIMITY      = 0.99    # Precio debe estar >= 99% de banda superior
EMA200_ABOVE      = True    # Solo SHORT si precio > EMA200 (distribución desde arriba)
FUNDING_THRESHOLD = 0.0003  # >0.03% = longs crowded → contrarian SHORT bonus
MIN_CONFLUENCE    = 4       # Mínimo 4/5 para emitir señal
MIN_ATR_PCT       = 0.003   # ATR > 0.3% del precio

# --- ATR multipliers ---
ATR_SL  = 2.0   # SL arriba: entry + 2.0×ATR
ATR_TP1 = 1.5   # TP1: entry - 1.5×ATR
ATR_TP2 = 3.0   # TP2: entry - 3.0×ATR
ATR_TP3 = 5.0   # TP3: entry - 5.0×ATR

# --- Cooldowns ---
ALERT_COOLDOWN       = 3600       # 1h entre alertas del mismo instrumento
DIRECTION_FLIP_CD    = 3600 * 12  # 12h antes de flipear dirección
CHECK_INTERVAL       = 900        # 15 min entre ciclos

_last_alert: dict     = {}
_last_direction: dict = {}  # {key: (side, timestamp)}
_last_status: dict    = {}  # para /scalper_shorts

# --- Exchange (Binance Futures, solo lectura) ---
_exchange = ccxt.binance({
    "timeout": 15000,
    "options": {"defaultType": "future"},
    "enableRateLimit": True,
})


# --- Telegram ---
def _send_telegram(msg: str):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"
        }, timeout=10)
        if not r.ok:
            logger.warning("Scalper Shorts Telegram error %d: %s", r.status_code, r.text[:120])
    except Exception as e:
        logger.error("Scalper Shorts Telegram send failed: %s", e)


# --- Data Fetching ---
def _fetch_ohlcv(ccxt_symbol: str, timeframe: str = "1h", limit: int = 250) -> pd.DataFrame:
    """Fetch OHLCV via ccxt. Returns DataFrame con columnas Open/High/Low/Close/Volume."""
    try:
        raw = _exchange.fetch_ohlcv(ccxt_symbol, timeframe=timeframe, limit=limit)
        if not raw:
            return pd.DataFrame()
        df = pd.DataFrame(raw, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df
    except Exception as e:
        logger.error("Scalper Shorts fetch %s %s failed: %s", ccxt_symbol, timeframe, e)
        return pd.DataFrame()


# --- Indicators (self-contained) ---
def _calc_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return float((100 - (100 / (1 + rs))).iloc[-1])


def _calc_bb(series: pd.Series, period: int = 20, std: float = 2.0):
    """Returns (upper, lower, mid)."""
    mid   = series.rolling(period).mean()
    sigma = series.rolling(period).std()
    return float((mid + std * sigma).iloc[-1]), float((mid - std * sigma).iloc[-1])


def _calc_ema(series: pd.Series, span: int) -> float:
    return float(series.ewm(span=span, adjust=False).mean().iloc[-1])


def _calc_atr(df: pd.DataFrame, period: int = 14) -> float:
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"]  - df["Close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1 / period, adjust=False).mean().iloc[-1])


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


def _has_open_short(key: str) -> bool:
    for t in tracker.get_open_trades():
        if t["symbol"] == key and t.get("version") == "SCALPER_SHORTS":
            return True
    return False


def _get_funding_signal(sym: str) -> float:
    """Fetch funding rate for sym. Returns rate (float), or 0.0 on error."""
    try:
        import market_intel
        data = market_intel.get_funding_rates([sym])
        return data.get(sym, {}).get("rate", 0.0)
    except Exception as e:
        logger.warning("Scalper Shorts funding fetch %s failed: %s", sym, e)
        return 0.0


# --- Macro guard: 1D EMA200 ---
def _daily_bias(ccxt_symbol: str) -> str:
    """Returns 'BEAR' si precio_1D < EMA200_1D, 'BULL' si sobre."""
    try:
        df_1d = _fetch_ohlcv(ccxt_symbol, timeframe="1d", limit=210)
        if df_1d.empty or len(df_1d) < 201:
            return "UNKNOWN"
        price_1d = float(df_1d["Close"].iloc[-1])
        ema200_1d = _calc_ema(df_1d["Close"], 200)
        return "BULL" if price_1d > ema200_1d else "BEAR"
    except Exception as e:
        logger.warning("Scalper Shorts daily bias %s error: %s", ccxt_symbol, e)
        return "UNKNOWN"


# --- Monitor open SHORT trades ---
def _monitor_open_short(key: str, ccxt_symbol: str, dec: int):
    open_trades = [t for t in tracker.get_open_trades()
                   if t["symbol"] == key and t.get("version") == "SCALPER_SHORTS"]
    if not open_trades:
        return

    try:
        ticker = _exchange.fetch_ticker(ccxt_symbol)
        price = float(ticker.get("last") or ticker.get("close") or 0)
    except Exception as e:
        logger.warning("Scalper Shorts monitor price %s error: %s", key, e)
        return
    if not price:
        return

    for t in open_trades:
        tid   = t.get("id")
        sl    = float(t.get("sl_price")  or 0)
        tp1   = float(t.get("tp1_price") or 0)
        entry = float(t.get("entry_price") or 0)
        status = t.get("status", "OPEN")

        if status == "OPEN" and sl and price >= sl:
            tracker.update_trade_status(tid, "LOST", price)
            tracker.append_event(tid, f"SL HIT @ ${price:.{dec}f} (scalper_shorts auto)")
            _send_telegram(f"🔴 <b>SCALPER SHORT SL</b> {key}\nEntrada ${entry:.{dec}f} → SL ${price:.{dec}f}")
            logger.info("Scalper Shorts %s SL hit @ %s", key, f"{price:.{dec}f}")
        elif status == "OPEN" and tp1 and price <= tp1:
            tracker.update_trade_status(tid, "PARTIAL_WON", price)
            tracker.append_event(tid, f"TP1 HIT @ ${price:.{dec}f} (scalper_shorts auto) → mover SL a BE")
            _send_telegram(
                f"🟢 <b>SCALPER SHORT TP1</b> {key}\n"
                f"Entrada ${entry:.{dec}f} → TP1 ${price:.{dec}f}\n"
                f"Mover SL a breakeven ({entry:.{dec}f})"
            )
            logger.info("Scalper Shorts %s TP1 hit @ %f", key, price)


# --- Main analysis per instrument ---
def analyze_scalper_short(key: str, inst: dict):
    ccxt_sym = inst["ccxt"]
    dec = inst["decimals"]
    logger.info("  ScalperShorts: analizando %s...", key)

    # Position guard
    if _has_open_short(key):
        logger.info("    %s: posicion SHORT abierta, omitiendo", key)
        return

    # Cooldown
    if _in_cooldown(key):
        logger.info("    %s: en cooldown, omitiendo", key)
        return

    # Fetch 1H data
    df_1h = _fetch_ohlcv(ccxt_sym, timeframe="1h", limit=250)
    if df_1h.empty or len(df_1h) < 210:
        logger.warning("    %s: datos insuficientes 1H (%d bars)", key, len(df_1h) if not df_1h.empty else 0)
        return

    price   = float(df_1h["Close"].iloc[-1])
    rsi     = _calc_rsi(df_1h["Close"])
    atr     = _calc_atr(df_1h)
    bb_up, _ = _calc_bb(df_1h["Close"])
    ema200  = _calc_ema(df_1h["Close"], 200)
    ema9    = _calc_ema(df_1h["Close"], 9)
    ema21   = _calc_ema(df_1h["Close"], 21)

    # ATR minimum filter
    if atr < price * MIN_ATR_PCT:
        logger.info("    %s: ATR bajo (%.5f < %.5f)", key, atr, price * MIN_ATR_PCT)
        _last_status[key] = {"price": price, "rsi": round(rsi, 1), "signal": "ATR bajo", "time": datetime.now()}
        return

    # Funding rate
    funding_rate = _get_funding_signal(key)

    # --- Confluence Scoring (SHORT only) ---
    score = 0
    cond = {}

    # 1. RSI sobrecomprado
    cond["rsi_overbought"] = rsi >= RSI_SHORT_ENTRY
    if cond["rsi_overbought"]:
        score += 1

    # 2. Precio tocando BB superior
    cond["bb_upper_touch"] = price >= bb_up * BB_PROXIMITY
    if cond["bb_upper_touch"]:
        score += 1

    # 3. Precio sobre EMA200 (distribución desde arriba — zona ideal para short)
    cond["price_above_ema200"] = price > ema200
    if cond["price_above_ema200"]:
        score += 1

    # 4. EMA9 < EMA21 (cruce bajista)
    cond["ema_bearish_cross"] = ema9 < ema21
    if cond["ema_bearish_cross"]:
        score += 1

    # 5. Funding rate > threshold (longs crowded → contrarian SHORT)
    cond["funding_longs_crowded"] = funding_rate > FUNDING_THRESHOLD
    if cond["funding_longs_crowded"]:
        score += 1

    _last_status[key] = {
        "price": price, "rsi": round(rsi, 1), "atr": round(atr, dec),
        "ema200": round(ema200, dec), "ema9": round(ema9, dec), "ema21": round(ema21, dec),
        "bb_upper": round(bb_up, dec), "funding": funding_rate,
        "score": score, "conds": cond,
        "signal": f"SHORT ({score}/5)" if score >= MIN_CONFLUENCE else f"Sin señal ({score}/5)",
        "time": datetime.now(),
    }

    logger.info("    %s: score=%d/5 RSI=%.1f funding=%.4f", key, score, rsi, funding_rate)

    if score < MIN_CONFLUENCE:
        return

    # --- Spec 001 (May-22-2026) kill switches ---
    from config import TAO_SHORT_ENABLED, SHORT_BLOCKED_IN_VERDE_BULL, VIX_DORMANT_THRESHOLD
    if key == "TAO" and not TAO_SHORT_ENABLED:
        logger.info("    %s: TAO_SHORT_ENABLED=False — 75%% de SHORT losses históricos son TAO. Skip.", key)
        return

    if SHORT_BLOCKED_IN_VERDE_BULL:
        # Si SP500 > 7000 + VIX < 22 → VERDE_BULL_DORMANT, no operar shorts crypto.
        try:
            import indicators
            _, vix_val = indicators.get_dxy_vix()
            sp500_price = indicators.get_sp500_price() if hasattr(indicators, "get_sp500_price") else None
            if sp500_price and sp500_price > 7000.0 and vix_val < VIX_DORMANT_THRESHOLD:
                logger.info("    %s: SP500 %.0f > 7000 + VIX %.1f < %.0f — VERDE_BULL_DORMANT, shorts crypto bloqueados.",
                            key, sp500_price, vix_val, VIX_DORMANT_THRESHOLD)
                return
        except Exception as _e:
            logger.debug("    %s: SHORT macro gate failed (%s) — continuing", key, _e)

    # --- Macro guard: bloquear si ya está en tendencia bajista diaria ---
    bias = _daily_bias(ccxt_sym)
    if bias == "BEAR":
        logger.info("    %s: 1D bias BEAR — precio ya bajo EMA200 diaria, no es scalp", key)
        return

    # Direction flip guard
    if not _can_flip(key, "SHORT"):
        logger.info("    %s: direction flip bloqueado, 12h cooldown", key)
        return

    # --- Build levels ---
    sl  = round(price + atr * ATR_SL,  dec)
    tp1 = round(price - atr * ATR_TP1, dec)
    tp2 = round(price - atr * ATR_TP2, dec)
    tp3 = round(price - atr * ATR_TP3, dec)

    rr1 = round(ATR_TP1 / ATR_SL, 1)
    rr2 = round(ATR_TP2 / ATR_SL, 1)
    rr3 = round(ATR_TP3 / ATR_SL, 1)

    strength = "FUERTE" if score == 5 else "VALIDA"
    cond_lines = (
        f"  {'✅' if cond['rsi_overbought'] else '❌'} RSI {rsi:.1f} ≥ {RSI_SHORT_ENTRY}\n"
        f"  {'✅' if cond['bb_upper_touch'] else '❌'} Precio toca BB superior (${bb_up:.{dec}f})\n"
        f"  {'✅' if cond['price_above_ema200'] else '❌'} Precio > EMA200 (${ema200:.{dec}f})\n"
        f"  {'✅' if cond['ema_bearish_cross'] else '❌'} EMA9 &lt; EMA21 (cruce bajista)\n"
        f"  {'✅' if cond['funding_longs_crowded'] else '❌'} Funding {funding_rate*100:.3f}% (longs crowded)"
    )

    msg = (
        f"<b>SCALPER SHORT ALERT ({key})</b>\n"
        f"{inst['name']}\n\n"
        f"<b>Confluencia</b>: {score}/5 ({strength})\n"
        f"{cond_lines}\n\n"
        f"{'─' * 28}\n"
        f"<b>Entrada SHORT</b>: <code>${price:,.{dec}f}</code>\n\n"
        f"TP1 (50%): <code>${tp1:,.{dec}f}</code>  R:R {rr1}:1\n"
        f"  → Mover SL a breakeven\n"
        f"TP2 (30%): <code>${tp2:,.{dec}f}</code>  R:R {rr2}:1\n"
        f"TP3 (20%): <code>${tp3:,.{dec}f}</code>  R:R {rr3}:1\n\n"
        f"SL: <code>${sl:,.{dec}f}</code>  (ATR x {ATR_SL})\n"
        f"ATR: ${atr:.{dec}f}\n\n"
        f"<i>Scalper SHORT. Confluencia mínima 4/5. 1D bias: {bias}.</i>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')} UTC"
    )

    # Wire signal keyboard (Activar / Skip) — mismo patrón que commodities_bot
    try:
        from scalp_alert_bot import _store_pending
        import alert_manager as _am
        import requests as _req

        _sid = _store_pending(
            key, "SHORT", price, tp1, tp2, sl, atr, rsi, score,
            "scalper_short_v1", "SCALPER_SHORTS", None,
            macro_regime=f"1D_BIAS:{bias}|FUNDING:{funding_rate:.4f}",
        )
        _kb = _am.get_signal_keyboard(_sid, key, "SHORT")

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = _req.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": _kb,
        }, timeout=10)
        mid = str(r.json().get("result", {}).get("message_id", "")) if r.ok else None
        if not mid:
            raise RuntimeError("Telegram send failed")

    except Exception as _e:
        logger.warning("    %s: signal keyboard fallback (%s)", key, _e)
        _send_telegram(msg)
        tracker.log_trade(
            key, "SHORT", price, tp1, tp2, sl, None,
            version="SCALPER_SHORTS", rsi=rsi, atr=atr, score=score,
            alert_type="scalper_short_v1",
        )

    _last_alert[key] = time.time()
    _last_direction[key] = ("SHORT", time.time())
    logger.info("    %s: SHORT alert sent (score=%d/5 @ $%s)", key, score, f"{price:.{dec}f}")


# --- Status HTML (for /scalper_shorts command) ---
def get_status_html() -> str:
    if not _last_status:
        return (
            "<b>SCALPER SHORTS</b>\n"
            "Sin datos aún — primer ciclo en los próximos 15 min.\n\n"
            "<i>Instrumentos: DOGE, FIL, TAO</i>"
        )

    wr_data = tracker.get_win_rate("SCALPER_SHORTS")
    wins  = wr_data.get("full_won", 0) + wr_data.get("partial_won", 0)
    total = wr_data.get("total", 0)
    wr_pct = (wins / total * 100) if total > 0 else 0.0
    wr_line = f"WR: {wr_pct:.0f}% ({wins}/{total} trades)" if total > 0 else "WR: Sin trades aún"

    lines = [f"<b>🔴 SCALPER SHORTS</b>\n{wr_line}\n"]
    for key, inst in INSTRUMENTS.items():
        st = _last_status.get(key)
        if not st:
            lines.append(f"<b>{key}</b>: sin datos")
            continue
        t  = st.get("time", datetime.now())
        age_min = int((datetime.now() - t).total_seconds() / 60)
        price  = st.get("price", 0)
        rsi    = st.get("rsi", 0)
        score  = st.get("score", 0)
        sig    = st.get("signal", "—")
        funding = st.get("funding", 0)
        conds = st.get("conds", {})
        dec = inst["decimals"]
        cond_icons = "".join([
            "✅" if conds.get("rsi_overbought") else "❌",
            "✅" if conds.get("bb_upper_touch") else "❌",
            "✅" if conds.get("price_above_ema200") else "❌",
            "✅" if conds.get("ema_bearish_cross") else "❌",
            "✅" if conds.get("funding_longs_crowded") else "❌",
        ])
        lines.append(
            f"<b>{key}</b> ${price:,.{dec}f}  RSI {rsi}  F:{funding*100:.3f}%\n"
            f"  {cond_icons}  {sig}  ({age_min}m ago)"
        )

    open_shorts = [t for t in tracker.get_open_trades() if t.get("version") == "SCALPER_SHORTS"]
    if open_shorts:
        lines.append(f"\n<b>Posiciones abiertas ({len(open_shorts)})</b>")
        for t in open_shorts:
            sym   = t.get("symbol", "?")
            entry = t.get("entry_price", 0)
            sl    = t.get("sl_price", 0)
            tp1   = t.get("tp1_price", 0)
            dec   = INSTRUMENTS.get(sym, {}).get("decimals", 4)
            lines.append(f"  SHORT {sym} @ ${entry:.{dec}f}  SL ${sl:.{dec}f}  TP1 ${tp1:.{dec}f}")

    return "\n".join(lines)


# --- Main loop ---
def run_scalper_shorts_bot():
    logger.info("SCALPER SHORTS BOT ACTIVADO — DOGE | FIL | TAO")
    _send_telegram(
        "<b>SCALPER SHORTS BOT ACTIVADO</b>\n"
        "Estrategia: SHORT Scalper 1H\n"
        "Instrumentos: DOGE, FIL, TAO\n"
        "Ciclo: cada 15 min"
    )

    while True:
        try:
            thread_health.heartbeat("scalper_shorts")
            now = datetime.now().strftime("%H:%M")
            logger.info("ScalperShorts ciclo [%s]", now)

            for key, inst in INSTRUMENTS.items():
                try:
                    _monitor_open_short(key, inst["ccxt"], inst["decimals"])
                    analyze_scalper_short(key, inst)
                except Exception as e:
                    logger.error("ScalperShorts %s error: %s", key, e, exc_info=True)

            _sleep_steps = max(1, CHECK_INTERVAL // 60)
            for _ in range(_sleep_steps):
                time.sleep(60)
                thread_health.heartbeat("scalper_shorts")

        except Exception as e:
            logger.error("ScalperShorts loop error: %s", e, exc_info=True)
            time.sleep(60)


if __name__ == "__main__":
    run_scalper_shorts_bot()
