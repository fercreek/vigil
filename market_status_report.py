"""
market_status_report.py — Reporte de estatus de mercado 2x/día + ZEC pulse 4H.

Reportes diarios:
  - 10:00 AM CST = 16:00 UTC
  - 03:00 PM CST = 21:00 UTC

ZEC pulse: cada 4H sin importar score (monitor manual ZEC/TAO/TON).
"""
import time
import os
import requests
from datetime import datetime, timedelta, timezone
from logger_core import logger
import thread_health

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 10am CST = 16:00 UTC | 3pm CST = 21:00 UTC
REPORT_TIMES_UTC = [(16, 0), (21, 0)]

# ZEC pulse interval
ZEC_PULSE_SEC = 4 * 3600   # 4H
ZEC_SL_LEVEL  = 521.0      # Fernando SL definido 2026-05-27 (doble techo chart)

_last_zec_pulse = 0.0
_zec_sl_alerted = False    # solo alertar una vez hasta que rebote

# HYPE level monitor (Fernando 2026-06-01 — descubrimiento de precio cerca de ATH)
HYPE_BREAKOUT_LEVEL = 74.31   # ATH 120d · ruptura → corre a $84 (fib 1.272)
HYPE_REENTRY_LEVEL  = 67.0    # soporte pullback → zona reentrada
HYPE_PULSE_SEC      = 4 * 3600  # update cada 4H mientras se vigila de cerca
_hype_breakout_alerted = False
_hype_reentry_alerted = False
_last_hype_pulse = 0.0


# ── Telegram ─────────────────────────────────────────────────────────────────

def _send(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"
        }, timeout=15)
        if not r.ok:
            logger.warning("[MarketReport] Telegram error %d", r.status_code)
    except Exception as e:
        logger.warning("[MarketReport] send failed: %s", e)


# ── Data helpers ──────────────────────────────────────────────────────────────

def _prices_and_rsi():
    """Pull from GLOBAL_CACHE (already updated by scalp_bot thread)."""
    try:
        from scalp_alert_bot import GLOBAL_CACHE, get_prices
        prices = GLOBAL_CACHE.get("prices") or {}
        if not prices.get("BTC"):
            prices = get_prices()
        inds = GLOBAL_CACHE.get("indicators", {})
        return prices, inds
    except Exception as e:
        logger.warning("[MarketReport] prices error: %s", e)
        return {}, {}


def _fear_greed():
    try:
        from scalp_alert_bot import GLOBAL_CACHE
        fg = GLOBAL_CACHE.get("fear_greed", {})
        if fg.get("value"):
            return fg
    except Exception:
        pass
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=5).json()
        d = r["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"]}
    except Exception:
        return {"value": 0, "label": "—"}


def _zec_intel():
    """CVD + HMM regime + last signal for ZEC."""
    intel = {}
    try:
        import cvd_segmented
        cvd = cvd_segmented.get_cvd_signal("ZEC/USDT")
        intel["cvd"] = cvd.get("signal", "NEUTRAL")
        intel["cvd_retail"] = cvd.get("retail_cvd", 0)
        intel["cvd_whale"] = cvd.get("whale_cvd", 0)
    except Exception:
        pass
    try:
        import regime_hmm
        reg = regime_hmm.detect_regime("ZEC")
        intel["regime"] = reg.get("regime", "UNKNOWN")
    except Exception:
        pass
    try:
        import signal_logger
        rows = signal_logger.get_recent_signals(n=20, symbol="ZEC")
        if rows:
            last = rows[-1]
            ts_naive = datetime.fromisoformat(last["ts"].replace("Z", "")).replace(tzinfo=None)
            age_min = int((datetime.utcnow() - ts_naive).total_seconds() / 60)
            intel["last_signal"] = f"{last['decision']} {last.get('reason','?')} hace {age_min}min"
    except Exception:
        pass
    return intel


def _grounded_news(symbol: str = "ZEC") -> str:
    """Quick Gemini grounded search for recent news on symbol (uses daily cap)."""
    try:
        import grounded_search
        result = grounded_search.search_market_context(f"{symbol} crypto price analysis today")
        if result and len(result) > 20:
            # Trim to 2 sentences max
            sentences = result.replace('\n', ' ').split('. ')
            return '. '.join(sentences[:2]).strip()[:200]
    except Exception:
        pass
    return ""


def _sym_line(sym: str, prices: dict, inds: dict) -> str:
    """One-liner for a symbol: emoji price RSI trend."""
    price = prices.get(sym, 0)
    rsi   = prices.get(f"{sym}_RSI") or inds.get(sym, {}).get("rsi") or 0
    ema   = inds.get(sym, {}).get("ema_200") or price
    if price <= 0:
        return f"  {sym}: no data"
    trend = "↗" if price > ema else "↘"
    rsi_str = f"RSI {rsi:.0f}" if rsi else "RSI ?"
    # Price format
    if price > 1000:
        price_str = f"${price:,.0f}"
    elif price > 1:
        price_str = f"${price:,.2f}"
    else:
        price_str = f"${price:.4f}"
    # Color emoji by RSI zone
    if rsi > 70:   emoji = "🔴"
    elif rsi > 55: emoji = "🟡"
    elif rsi < 30: emoji = "🟢"
    elif rsi < 45: emoji = "🟡"
    else:          emoji = "⚪"
    return f"  {emoji} {sym} {price_str} {rsi_str} {trend}"


# ── Report builders ───────────────────────────────────────────────────────────

def build_market_status(label: str = "") -> str:
    prices, inds = _prices_and_rsi()
    fg = _fear_greed()
    zec_intel = _zec_intel()

    now_str = datetime.now(timezone.utc).strftime("%H:%M UTC")
    if not label:
        label = now_str

    # Fear & Greed emoji
    fgv = fg.get("value", 0)
    if fgv >= 75:   fg_emoji = "🤑"
    elif fgv >= 55: fg_emoji = "😀"
    elif fgv >= 45: fg_emoji = "😐"
    elif fgv >= 25: fg_emoji = "😰"
    else:           fg_emoji = "😱"

    usdt_d = prices.get("USDT_D", 0)
    usdt_d_str = f"{usdt_d:.2f}%" if usdt_d else "?"
    usdt_d_dir = "↘ (favorece alts)" if usdt_d and usdt_d < 4.5 else "↗ (precaución alts)" if usdt_d and usdt_d > 5.5 else "→"

    vix = prices.get("VIX", 0)
    dxy = prices.get("DXY", 0)
    spy = prices.get("SPY", 0)

    lines = [
        f"📊 <b>MARKET STATUS — {label}</b>",
        "",
        "<b>── Crypto ──────────────────</b>",
    ]
    for sym in ["BTC", "ETH", "ZEC", "TON", "HYPE"]:  # Fénix: TAO jubilado (3% WR, disabled). Fuera del reporte.
        lines.append(_sym_line(sym, prices, inds))

    lines += [
        "",
        "<b>── Macro ───────────────────</b>",
        f"  USDT.D: <b>{usdt_d_str}</b> {usdt_d_dir}",
    ]
    if vix: lines.append(f"  VIX: {vix:.1f}")
    if dxy: lines.append(f"  DXY: {dxy:.2f}")
    if spy: lines.append(f"  SP500: ${spy:,.0f}")

    lines += [
        "",
        f"  {fg_emoji} Fear &amp; Greed: <b>{fgv}</b> — {fg.get('label','?')}",
        "",
        "<b>── ZEC Monitor ─────────────</b>",
    ]

    # ZEC intel block
    if zec_intel.get("cvd"):
        retail = zec_intel.get("cvd_retail", 0)
        whale  = zec_intel.get("cvd_whale", 0)
        lines.append(f"  CVD: {zec_intel['cvd']} | retail {retail:+,.0f} whale {whale:+,.0f}")
    if zec_intel.get("regime"):
        lines.append(f"  Regime (HMM): {zec_intel['regime']}")
    if zec_intel.get("last_signal"):
        lines.append(f"  Última señal: {zec_intel['last_signal']}")

    # Key ZEC levels from inds
    zec_ind = inds.get("ZEC", {})
    bb_u = zec_ind.get("bb_u")
    bb_l = zec_ind.get("bb_l")
    ema200 = zec_ind.get("ema_200")
    if bb_u and bb_l:
        lines.append(f"  BB: ${bb_l:,.0f} — ${bb_u:,.0f}")
    if ema200:
        zec_price = prices.get("ZEC", 0)
        pos = "↑ sobre" if zec_price > ema200 else "↓ bajo"
        lines.append(f"  EMA200: ${ema200:,.0f} ({pos})")

    lines.append("")
    lines.append("<i>/sentinel zec /pos /budget</i>")

    return "\n".join(lines)


def build_zec_pulse() -> str:
    """Mini ZEC update — siempre se envía, sin filtro de score."""
    prices, inds = _prices_and_rsi()
    zec_intel = _zec_intel()

    zec_p   = prices.get("ZEC", 0)
    zec_rsi = prices.get("ZEC_RSI") or inds.get("ZEC", {}).get("rsi") or 0
    zec_ind = inds.get("ZEC", {})
    ema200  = zec_ind.get("ema_200") or zec_p
    bb_u    = zec_ind.get("bb_u", 0)
    bb_l    = zec_ind.get("bb_l", 0)
    atr     = zec_ind.get("atr", 0)

    trend = "↗ sobre EMA200" if zec_p > ema200 else "↘ bajo EMA200"
    rsi_ctx = "sobrecomprado" if zec_rsi > 70 else "sobrevendido" if zec_rsi < 30 else "neutral"

    now_str = datetime.now(timezone.utc).strftime("%H:%M UTC")
    lines = [
        f"🔬 <b>ZEC PULSE — {now_str}</b>",
        f"  ${zec_p:,.2f} | RSI {zec_rsi:.0f} ({rsi_ctx}) | {trend}",
    ]

    if bb_u and bb_l:
        dist_upper = (bb_u - zec_p) / zec_p * 100
        dist_lower = (zec_p - bb_l) / zec_p * 100
        lines.append(f"  BB: ${bb_l:,.0f} ↔ ${bb_u:,.0f} | dist sup {dist_upper:.1f}% / inf {dist_lower:.1f}%")

    if atr:
        sl_est  = round(zec_p - 2 * atr, 2)
        tp1_est = round(zec_p + 2.5 * atr, 2)
        lines.append(f"  ATR ${atr:,.2f} → SL est ${sl_est:,.2f} | TP1 est ${tp1_est:,.2f}")

    if zec_intel.get("cvd"):
        lines.append(f"  CVD: {zec_intel['cvd']} (retail {zec_intel.get('cvd_retail',0):+,.0f})")
    if zec_intel.get("regime"):
        lines.append(f"  Regime: {zec_intel['regime']}")
    if zec_intel.get("last_signal"):
        lines.append(f"  Último: {zec_intel['last_signal']}")

    # BTC + USDT.D context
    btc_p  = prices.get("BTC", 0)
    usdt_d = prices.get("USDT_D") or prices.get("usdt_d") or 0
    try:
        from scalp_alert_bot import GLOBAL_CACHE
        usdt_d = usdt_d or GLOBAL_CACHE.get("prices", {}).get("USDT_D", 0)
    except Exception:
        pass
    if btc_p:
        ud_str = f"{usdt_d:.2f}%" if usdt_d else "?"
        lines.append(f"  BTC ${btc_p:,.0f} | USDT.D {ud_str}")

    lines.append("<i>ZEC monitoring — no es señal de trade</i>")
    return "\n".join(lines)


# ── Runner ────────────────────────────────────────────────────────────────────

def _seconds_until_next_slot() -> int:
    """Seconds to next REPORT_TIMES_UTC slot or ZEC_PULSE, whichever is sooner."""
    global _last_zec_pulse
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Next ZEC pulse
    zec_due_in = ZEC_PULSE_SEC - (time.time() - _last_zec_pulse)
    zec_due_in = max(0, zec_due_in)

    # Next market report
    report_due = float("inf")
    for h, m in REPORT_TIMES_UTC:
        t = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if t <= now:
            t += timedelta(days=1)
        diff = (t - now).total_seconds()
        report_due = min(report_due, diff)

    return int(min(zec_due_in, report_due, 60))  # check at most every 60s


def _check_zec_sl():
    """Alert if ZEC breaks below SL_LEVEL. One alert per breach."""
    global _zec_sl_alerted
    try:
        from scalp_alert_bot import GLOBAL_CACHE
        zec_p = GLOBAL_CACHE.get("prices", {}).get("ZEC", 0)
        if not zec_p:
            return
        if zec_p < ZEC_SL_LEVEL and not _zec_sl_alerted:
            msg = (
                f"🚨 <b>ZEC SL ALERT</b>\n"
                f"  Precio: <b>${zec_p:,.2f}</b> bajo SL ${ZEC_SL_LEVEL:.0f}\n"
                f"  ⚠️ Revisar posición — salida si confirma cierre 4H bajo nivel"
            )
            _send(msg)
            logger.warning("[MarketReport] ZEC SL breach: $%.2f < $%.0f", zec_p, ZEC_SL_LEVEL)
            _zec_sl_alerted = True
        elif zec_p > ZEC_SL_LEVEL + 10:
            _zec_sl_alerted = False  # reset si rebota $10 sobre SL
    except Exception as e:
        logger.debug("[MarketReport] ZEC SL check error: %s", e)


def build_hype_pulse() -> str:
    """Mini HYPE update cada 4H — vigilancia de descubrimiento de precio."""
    prices, inds = _prices_and_rsi()
    p   = prices.get("HYPE", 0)
    rsi = prices.get("HYPE_RSI") or inds.get("HYPE", {}).get("rsi") or 0
    ind = inds.get("HYPE", {})
    ema200 = ind.get("ema_200") or p
    bb_u   = ind.get("bb_u", 0)
    bb_l   = ind.get("bb_l", 0)
    atr    = ind.get("atr", 0)

    trend   = "↗ sobre EMA200" if p > ema200 else "↘ bajo EMA200"
    rsi_ctx = "sobrecomprado" if rsi > 70 else "sobrevendido" if rsi < 30 else "neutral"
    now_str = datetime.now(timezone.utc).strftime("%H:%M UTC")

    lines = [
        f"🔬 <b>HYPE PULSE — {now_str}</b>",
        f"  ${p:,.2f} | RSI {rsi:.0f} ({rsi_ctx}) | {trend}",
    ]
    # distancia a niveles clave
    if p:
        gap_bo = (HYPE_BREAKOUT_LEVEL - p) / p * 100
        if p > HYPE_BREAKOUT_LEVEL:
            lines.append(f"  🚀 sobre ATH ${HYPE_BREAKOUT_LEVEL:.2f} — targets $84 / $97 / $110")
        else:
            lines.append(f"  Breakout ${HYPE_BREAKOUT_LEVEL:.2f} ({gap_bo:+.1f}%) | reentrada ${HYPE_REENTRY_LEVEL:.0f}")
    if bb_u and bb_l:
        lines.append(f"  BB: ${bb_l:,.1f} ↔ ${bb_u:,.1f}")
    if atr:
        lines.append(f"  ATR ${atr:,.2f} → SL est ${p-2*atr:,.2f} | TP1 est ${p+2.5*atr:,.2f}")

    lines.append("<i>HYPE monitoring — no es señal de trade</i>")
    return "\n".join(lines)


def _check_hype_levels():
    """Alert on HYPE breakout above ATH or pullback into reentry zone."""
    global _hype_breakout_alerted, _hype_reentry_alerted
    try:
        from scalp_alert_bot import GLOBAL_CACHE
        p = GLOBAL_CACHE.get("prices", {}).get("HYPE", 0)
        if not p:
            return
        # Breakout sobre ATH → corre a targets
        if p > HYPE_BREAKOUT_LEVEL and not _hype_breakout_alerted:
            _send(
                f"🚀 <b>HYPE BREAKOUT</b>\n"
                f"  Precio: <b>${p:,.2f}</b> rompió ATH ${HYPE_BREAKOUT_LEVEL:.2f}\n"
                f"  🎯 Targets: $84 (T1) · $97 (T2) · $110 (T3)\n"
                f"  ⚠️ Confirmar con volumen — RSI diario sobrecomprado"
            )
            logger.warning("[MarketReport] HYPE breakout: $%.2f > $%.2f", p, HYPE_BREAKOUT_LEVEL)
            _hype_breakout_alerted = True
        elif p < HYPE_BREAKOUT_LEVEL - 2:
            _hype_breakout_alerted = False  # reset si vuelve bajo ATH
        # Pullback a zona reentrada
        if p <= HYPE_REENTRY_LEVEL and not _hype_reentry_alerted:
            _send(
                f"🟢 <b>HYPE REENTRADA</b>\n"
                f"  Precio: <b>${p:,.2f}</b> tocó soporte ${HYPE_REENTRY_LEVEL:.0f}\n"
                f"  💡 Zona de reentrada si sostiene — invalida bajo $67"
            )
            logger.warning("[MarketReport] HYPE reentry zone: $%.2f <= $%.0f", p, HYPE_REENTRY_LEVEL)
            _hype_reentry_alerted = True
        elif p > HYPE_REENTRY_LEVEL + 3:
            _hype_reentry_alerted = False  # reset si rebota
    except Exception as e:
        logger.debug("[MarketReport] HYPE level check error: %s", e)


def run_market_status_reports():
    global _last_zec_pulse, _last_hype_pulse
    logger.info("[MarketReport] Iniciado — reportes %s UTC | ZEC+HYPE pulse cada 4H | SL $%.0f",
                ", ".join(f"{h:02d}:{m:02d}" for h, m in REPORT_TIMES_UTC), ZEC_SL_LEVEL)

    _last_zec_pulse = time.time()   # don't fire immediately on boot
    _last_hype_pulse = time.time()

    while True:
        try:
            thread_health.heartbeat("market_report")
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            # Check market report slots
            for h, m in REPORT_TIMES_UTC:
                target = now.replace(hour=h, minute=m, second=0, microsecond=0)
                diff = abs((now - target).total_seconds())
                if diff < 90:  # within 90s window
                    label = f"{h:02d}:{m:02d} UTC"
                    logger.info("[MarketReport] Enviando reporte %s", label)
                    msg = build_market_status(label)
                    _send(msg)
                    time.sleep(120)  # avoid double-fire
                    break

            # ZEC SL watchdog — runs every loop (~30-60s)
            _check_zec_sl()

            # HYPE breakout/reentry watchdog
            _check_hype_levels()

            # Check ZEC pulse
            if time.time() - _last_zec_pulse >= ZEC_PULSE_SEC:
                logger.info("[MarketReport] ZEC pulse 4H")
                msg = build_zec_pulse()
                _send(msg)
                _last_zec_pulse = time.time()

            # Check HYPE pulse
            if time.time() - _last_hype_pulse >= HYPE_PULSE_SEC:
                logger.info("[MarketReport] HYPE pulse 4H")
                _send(build_hype_pulse())
                _last_hype_pulse = time.time()

            wait = _seconds_until_next_slot()
            time.sleep(max(wait, 30))

        except Exception as e:
            logger.error("[MarketReport] loop error: %s", e, exc_info=True)
            time.sleep(300)


if __name__ == "__main__":
    # Test mode — print to stdout
    print(build_market_status("TEST"))
    print()
    print(build_zec_pulse())
