"""
manual_positions_monitor.py — Monitor de Posiciones Manuales

Storage unificado en trades.db (flag is_manual=1). Cada 30 min calcula P&L
actual, detecta recuperaciones/riesgos y envía recomendaciones orientadas a LONG.

Comandos Telegram (ver telegram_commands.py):
  /manual           — estado de todas las posiciones manuales
  /manual_tp SYM    — cerrar posición completa (TP hit)
  /manual_tp SYM 50 — tomar 50% de ganancias (partial)
  /manual_sl SYM    — marcar SL hit / cerrar en pérdida
  /manual_be SYM    — anotar que se movió SL a break even
  /manual_off SYM   — desactivar monitoreo (cierra el trade sin marcar W/L)
"""

import time
import ccxt
from datetime import datetime
from logger_core import logger
import thread_health
import tracker

CHECK_INTERVAL = 1800   # 30 min entre análisis
ALERT_COOLDOWN = 3600   # 1h entre alertas del mismo símbolo

_last_alert: dict = {}   # {sym: timestamp}

_binance = ccxt.binance({"timeout": 15000})


# ── Price fetch ───────────────────────────────────────────────────────────────

def _fetch_price(sym: str) -> float:
    try:
        ticker = _binance.fetch_ticker(f"{sym.upper()}/USDT")
        return float(ticker.get("last", 0) or 0)
    except Exception as e:
        logger.warning("manual_monitor: no se pudo obtener precio %s: %s", sym, e)
        return 0.0


def get_positions() -> list:
    """Lista trades manuales abiertos desde trades.db."""
    return tracker.get_open_manual_trades()


# ── Recommendation engine (LONG bias, metodología PTS) ───────────────────────

def _recommend(pos: dict, price: float) -> str:
    entry = pos["entry_price"]
    side = pos.get("type", "LONG")
    be = pos.get("be_moved", False)
    partial_pct = pos.get("partial_pct", 0)
    partial = partial_pct > 0
    sym = pos["symbol"]

    if side != "LONG" or price <= 0 or not entry:
        return ""

    pnl_pct = (price - entry) / entry * 100
    rec = []

    if pnl_pct >= 8 and not partial:
        rec.append(f"📊 +{pnl_pct:.1f}% — considera tomar 30-50% de ganancias (/manual_tp {sym} 50)")
    elif pnl_pct >= 5 and not be:
        rec.append(f"🛡️ +{pnl_pct:.1f}% — mueve SL a break even ya (/manual_be {sym})")
    elif pnl_pct >= 3 and not be:
        rec.append(f"🟡 +{pnl_pct:.1f}% — acercándose a BE zone, vigilar")
    elif pnl_pct < -15:
        rec.append(f"🔴 -{abs(pnl_pct):.1f}% — drawdown importante. Evalúa SL o cierre")
    elif pnl_pct < -8:
        rec.append(f"⚠️ -{abs(pnl_pct):.1f}% — en drawdown. Mantener si tesis sigue válida")
    elif -3 <= pnl_pct <= 3:
        rec.append(f"🔄 {pnl_pct:+.1f}% — lateral cerca de entrada, sin acción requerida")
    else:
        rec.append(f"✅ {pnl_pct:+.1f}% — posición sana, dejar correr")

    if be:
        rec.append("🛡️ SL en BE — riesgo cero")
    if partial:
        rec.append(f"📤 {partial_pct}% tomado — el resto corre libre")

    return " | ".join(rec)


def _should_alert(sym: str) -> bool:
    return (time.time() - _last_alert.get(sym, 0)) >= ALERT_COOLDOWN


def _mark_alerted(sym: str):
    _last_alert[sym] = time.time()


# ── Análisis periódico ────────────────────────────────────────────────────────

def analyze_positions(send_fn=None) -> str:
    """Analiza todas las posiciones manuales activas. Retorna HTML y envía si send_fn dado."""
    from scalp_alert_bot import send_telegram as _send
    _send_fn = send_fn or _send

    active = tracker.get_open_manual_trades()
    if not active:
        return "<b>POSICIONES MANUALES</b>\n\nSin posiciones activas."

    lines = ["<b>POSICIONES MANUALES</b>\n"]
    alert_needed = False

    for pos in active:
        sym = pos["symbol"]
        entry = pos["entry_price"]
        side = pos.get("type", "LONG")
        price = _fetch_price(sym)

        if not price:
            lines.append(f"<b>{sym}</b> — ⚠️ sin precio\n")
            continue

        pnl_pct = (price - entry) / entry * 100 if side == "LONG" else (entry - price) / entry * 100
        pnl_icon = "🟢" if pnl_pct >= 0 else "🔴"
        be_tag = " [BE]" if pos.get("be_moved") else ""
        partial_tag = f" [{pos.get('partial_pct',0)}% tomado]" if pos.get("partial_pct", 0) > 0 else ""

        rec = _recommend(pos, price)

        lines.append(
            f"<b>{sym}</b> {side}{be_tag}{partial_tag}\n"
            f"  Entry: <code>${entry:.4f}</code> → Ahora: <code>${price:.4f}</code>\n"
            f"  {pnl_icon} P&L: <b>{pnl_pct:+.2f}%</b>\n"
            f"  💡 {rec}\n"
        )

        if abs(pnl_pct) >= 5 and _should_alert(sym):
            alert_needed = True
            _mark_alerted(sym)

    msg = "\n".join(lines)
    msg += f"\n<i>Update: {datetime.now().strftime('%H:%M')} UTC</i>"

    if alert_needed or send_fn:
        _send_fn(msg)

    return msg


# ── Command handlers (llamados desde telegram_commands.py) ───────────────────

def cmd_status() -> str:
    return analyze_positions(send_fn=lambda _: None)


def cmd_tp(sym: str, partial_pct: int = 100) -> str:
    sym = sym.upper()
    pos = tracker.get_open_trade_by_symbol(sym, manual_only=True)
    if not pos:
        return f"⚠️ {sym}: sin posición manual activa."

    price = _fetch_price(sym)
    entry = pos["entry_price"]
    side = pos.get("type", "LONG")
    pnl_pct = (price - entry) / entry * 100 if side == "LONG" else (entry - price) / entry * 100

    if partial_pct >= 100:
        tracker.update_trade_status(pos["id"], "FULL_WON" if pnl_pct >= 0 else "LOST")
        tracker.append_event(pos["id"], f"CLOSED TP @ ${price:.4f} ({pnl_pct:+.2f}%)")
        return f"✅ <b>{sym} CERRADO</b> @ <code>${price:.4f}</code> | P&L {pnl_pct:+.2f}%"
    else:
        tracker.mark_partial(pos["id"], partial_pct)
        tracker.append_event(pos["id"], f"PARTIAL {partial_pct}% @ ${price:.4f} ({pnl_pct:+.2f}%)")
        return (
            f"📤 <b>{sym} PARCIAL {partial_pct}%</b> @ <code>${price:.4f}</code>\n"
            f"P&L parcial: {pnl_pct:+.2f}% | Resto sigue corriendo"
        )


def cmd_sl(sym: str) -> str:
    sym = sym.upper()
    pos = tracker.get_open_trade_by_symbol(sym, manual_only=True)
    if not pos:
        return f"⚠️ {sym}: sin posición manual activa."

    price = _fetch_price(sym)
    entry = pos["entry_price"]
    side = pos.get("type", "LONG")
    pnl_pct = (price - entry) / entry * 100 if side == "LONG" else (entry - price) / entry * 100

    tracker.update_trade_status(pos["id"], "LOST")
    tracker.append_event(pos["id"], f"CLOSED SL @ ${price:.4f} ({pnl_pct:+.2f}%)")
    return f"🛑 <b>{sym} SL HIT</b> @ <code>${price:.4f}</code> | P&L {pnl_pct:+.2f}%"


def cmd_be(sym: str) -> str:
    sym = sym.upper()
    pos = tracker.get_open_trade_by_symbol(sym, manual_only=True)
    if not pos:
        return f"⚠️ {sym}: sin posición manual activa."

    tracker.mark_be(pos["id"])
    tracker.append_event(pos["id"], f"BE moved @ {datetime.now().strftime('%H:%M')}")
    return f"🛡️ <b>{sym}</b> SL movido a break even <code>${pos['entry_price']:.4f}</code>"


def cmd_off(sym: str) -> str:
    """Cierra el trade en DB sin marcar W/L (status PARTIAL_CLOSED). Stop monitoring."""
    sym = sym.upper()
    pos = tracker.get_open_trade_by_symbol(sym, manual_only=True)
    if not pos:
        return f"⚠️ {sym}: sin posición manual activa."

    tracker.update_trade_status(pos["id"], "PARTIAL_CLOSED")
    tracker.append_event(pos["id"], "MONITORING OFF (manual)")
    return f"🔕 <b>{sym}</b> monitoreo desactivado (registrado como PARTIAL_CLOSED)"


def cmd_add(sym: str, entry: float, side: str = "LONG", note: str = "") -> str:
    """Agrega trade manual a trades.db. Reusa compute_levels para SL/TP via ATR."""
    sym = sym.upper()
    side = side.upper()

    existing = tracker.get_open_trade_by_symbol(sym, manual_only=True)
    if existing:
        return f"⚠️ {sym}: ya hay posición manual abierta (id {existing['id']}). Cierra antes de re-abrir."

    # SL/TP heurístico simple cuando se agrega via /manual_add (sin acceso a ATR live aquí).
    # Para entradas con niveles automáticos, usar /open o LONG SYM.
    sl_d = entry * 0.02  # 2% default
    sl = round(entry - sl_d if side == "LONG" else entry + sl_d, 6)
    tp1 = round(entry + sl_d * 2.0 if side == "LONG" else entry - sl_d * 2.0, 6)
    tp2 = round(entry + sl_d * 3.5 if side == "LONG" else entry - sl_d * 3.5, 6)

    tid = tracker.log_trade(
        sym, side, entry, tp1, tp2, sl, msg_id="manual_add",
        version="MANUAL", is_manual=1, note=note,
    )
    tracker.append_event(tid, f"ADDED @ ${entry:.4f} (default SL 2%)")
    return f"➕ <b>{sym} {side}</b> agregado @ <code>${entry:.4f}</code> (id {tid}, SL ${sl:.4f})"


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_manual_monitor():
    logger.info("MANUAL POSITIONS MONITOR ACTIVADO")
    while True:
        try:
            thread_health.heartbeat("manual_monitor")
            active = tracker.get_open_manual_trades()
            if active:
                analyze_positions()
            else:
                logger.info("manual_monitor: sin posiciones activas")

            for _ in range(CHECK_INTERVAL // 60):
                time.sleep(60)
                thread_health.heartbeat("manual_monitor")

        except Exception as e:
            logger.error("manual_monitor loop error: %s", e, exc_info=True)
            time.sleep(60)
