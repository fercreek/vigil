"""
manual_positions_monitor.py — Monitor de Posiciones Manuales

Vigila las posiciones manuales de Fernando (TAO, ZEC, DOGE y cualquier otra
que se agregue via Telegram). Cada 30 min calcula P&L actual, detecta
recuperaciones/riesgos y envía recomendaciones orientadas a LONG.

Comandos Telegram (ver telegram_commands.py):
  /manual           — estado de todas las posiciones
  /manual_tp SYM    — cerrar posición completa (TP hit)
  /manual_tp SYM 50 — tomar 50% de ganancias (partial)
  /manual_sl SYM    — marcar SL hit / cerrar en pérdida
  /manual_be SYM    — anotar que se movió SL a break even
  /manual_off SYM   — desactivar monitoreo (sin cerrar)
"""

import os
import json
import time
import ccxt
from datetime import datetime
from logger_core import logger
import thread_health

STORE_PATH = os.path.join(os.path.dirname(__file__), "manual_positions.json")
CHECK_INTERVAL = 1800   # 30 min entre análisis
ALERT_COOLDOWN = 3600   # 1h entre alertas del mismo símbolo

_last_alert: dict = {}   # {sym: timestamp}

# ── Binance exchange (read-only, no keys needed for public prices) ───────────
_binance = ccxt.binance({"timeout": 15000})


# ── Store (JSON persistente) ─────────────────────────────────────────────────

def _load_store() -> list:
    """Carga posiciones desde JSON. Inicializa desde config si no existe."""
    if os.path.exists(STORE_PATH):
        try:
            with open(STORE_PATH) as f:
                return json.load(f)
        except Exception as e:
            logger.error("manual_positions: error cargando store: %s", e)
    # Primera vez: inicializar desde config.py
    try:
        from config import MANUAL_POSITIONS
        data = []
        for pos in MANUAL_POSITIONS:
            data.append({
                "symbol":       pos["symbol"],
                "side":         pos.get("side", "LONG"),
                "entry":        pos["entry"],
                "size_note":    pos.get("note", ""),
                "platform":     pos.get("platform", "manual"),
                "pnl_seed":     pos.get("pnl_usd", 0.0),  # P&L ya existente al iniciar
                "active":       True,
                "be_moved":     False,
                "partial_taken": False,
                "partial_pct":  0,
                "open_time":    datetime.now().isoformat(),
                "events":       [],
            })
        _save_store(data)
        logger.info("manual_positions: store inicializado desde config (%d posiciones)", len(data))
        return data
    except Exception as e:
        logger.error("manual_positions: error inicializando desde config: %s", e)
        return []


def _save_store(data: list):
    try:
        with open(STORE_PATH, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("manual_positions: error guardando store: %s", e)


def get_positions() -> list:
    return _load_store()


def _log_event(sym: str, event: str):
    data = _load_store()
    for pos in data:
        if pos["symbol"].upper() == sym.upper():
            pos.setdefault("events", []).append({
                "time": datetime.now().isoformat(), "event": event
            })
            break
    _save_store(data)


# ── Price fetch ───────────────────────────────────────────────────────────────

def _fetch_price(sym: str) -> float:
    try:
        ticker = _binance.fetch_ticker(f"{sym.upper()}/USDT")
        return float(ticker.get("last", 0) or 0)
    except Exception as e:
        logger.warning("manual_monitor: no se pudo obtener precio %s: %s", sym, e)
        return 0.0


# ── Recommendation engine (LONG bias, metodología PTS) ───────────────────────

def _recommend(pos: dict, price: float) -> str:
    entry  = pos["entry"]
    side   = pos.get("side", "LONG")
    be     = pos.get("be_moved", False)
    partial = pos.get("partial_taken", False)
    sym    = pos["symbol"]

    if side != "LONG" or price <= 0:
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
        pct = pos.get("partial_pct", 0)
        rec.append(f"📤 {pct}% tomado — el resto corre libre")

    return " | ".join(rec)


def _should_alert(sym: str) -> bool:
    return (time.time() - _last_alert.get(sym, 0)) >= ALERT_COOLDOWN


def _mark_alerted(sym: str):
    _last_alert[sym] = time.time()


# ── Análisis periódico ────────────────────────────────────────────────────────

def analyze_positions(send_fn=None) -> str:
    """Analiza todas las posiciones activas. Retorna HTML y envía si send_fn dado."""
    from scalp_alert_bot import send_telegram as _send
    _send_fn = send_fn or _send

    data = _load_store()
    active = [p for p in data if p.get("active", True)]
    if not active:
        return "<b>POSICIONES MANUALES</b>\n\nSin posiciones activas."

    lines = ["<b>POSICIONES MANUALES</b>\n"]
    alert_needed = False

    for pos in active:
        sym    = pos["symbol"]
        entry  = pos["entry"]
        side   = pos.get("side", "LONG")
        price  = _fetch_price(sym)

        if not price:
            lines.append(f"<b>{sym}</b> — ⚠️ sin precio\n")
            continue

        pnl_pct = (price - entry) / entry * 100 if side == "LONG" else (entry - price) / entry * 100
        pnl_icon = "🟢" if pnl_pct >= 0 else "🔴"
        be_tag = " [BE]" if pos.get("be_moved") else ""
        partial_tag = f" [{pos.get('partial_pct',0)}% tomado]" if pos.get("partial_taken") else ""

        rec = _recommend(pos, price)

        lines.append(
            f"<b>{sym}</b> {side}{be_tag}{partial_tag}\n"
            f"  Entry: <code>${entry:.4f}</code> → Ahora: <code>${price:.4f}</code>\n"
            f"  {pnl_icon} P&L: <b>{pnl_pct:+.2f}%</b>\n"
            f"  💡 {rec}\n"
        )

        # Alert on sharp moves or critical levels
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
    """Retorna HTML con estado actual (sin enviar por Telegram)."""
    return analyze_positions(send_fn=lambda _: None)


def cmd_tp(sym: str, partial_pct: int = 100) -> str:
    sym = sym.upper()
    data = _load_store()
    for pos in data:
        if pos["symbol"] == sym and pos.get("active", True):
            price = _fetch_price(sym)
            entry = pos["entry"]
            pnl_pct = (price - entry) / entry * 100 if pos.get("side","LONG") == "LONG" else (entry - price) / entry * 100

            if partial_pct >= 100:
                pos["active"] = False
                _log_event(sym, f"CLOSED TP @ ${price:.4f} ({pnl_pct:+.2f}%)")
                _save_store(data)
                return f"✅ <b>{sym} CERRADO</b> @ <code>${price:.4f}</code> | P&L {pnl_pct:+.2f}%"
            else:
                pos["partial_taken"] = True
                pos["partial_pct"] = partial_pct
                _log_event(sym, f"PARTIAL {partial_pct}% @ ${price:.4f} ({pnl_pct:+.2f}%)")
                _save_store(data)
                return (
                    f"📤 <b>{sym} PARCIAL {partial_pct}%</b> @ <code>${price:.4f}</code>\n"
                    f"P&L parcial: {pnl_pct:+.2f}% | Resto sigue corriendo"
                )
    return f"⚠️ {sym}: sin posición activa."


def cmd_sl(sym: str) -> str:
    sym = sym.upper()
    data = _load_store()
    for pos in data:
        if pos["symbol"] == sym and pos.get("active", True):
            price = _fetch_price(sym)
            entry = pos["entry"]
            pnl_pct = (price - entry) / entry * 100 if pos.get("side","LONG") == "LONG" else (entry - price) / entry * 100

            pos["active"] = False
            _log_event(sym, f"CLOSED SL @ ${price:.4f} ({pnl_pct:+.2f}%)")
            _save_store(data)
            return f"🛑 <b>{sym} SL HIT</b> @ <code>${price:.4f}</code> | P&L {pnl_pct:+.2f}%"
    return f"⚠️ {sym}: sin posición activa."


def cmd_be(sym: str) -> str:
    sym = sym.upper()
    data = _load_store()
    for pos in data:
        if pos["symbol"] == sym and pos.get("active", True):
            pos["be_moved"] = True
            _log_event(sym, f"BE moved @ {datetime.now().strftime('%H:%M')}")
            _save_store(data)
            return f"🛡️ <b>{sym}</b> SL movido a break even <code>${pos['entry']:.4f}</code>"
    return f"⚠️ {sym}: sin posición activa."


def cmd_off(sym: str) -> str:
    sym = sym.upper()
    data = _load_store()
    for pos in data:
        if pos["symbol"] == sym and pos.get("active", True):
            pos["active"] = False
            _log_event(sym, "MONITORING OFF (manual)")
            _save_store(data)
            return f"🔕 <b>{sym}</b> monitoreo desactivado (posición sigue abierta manualmente)"
    return f"⚠️ {sym}: sin posición activa."


def cmd_add(sym: str, entry: float, side: str = "LONG", note: str = "") -> str:
    sym = sym.upper()
    data = _load_store()
    # Remove existing inactive entry for same symbol
    data = [p for p in data if not (p["symbol"] == sym and not p.get("active", True))]
    data.append({
        "symbol": sym, "side": side.upper(), "entry": entry,
        "size_note": note, "platform": "manual",
        "pnl_seed": 0.0, "active": True,
        "be_moved": False, "partial_taken": False, "partial_pct": 0,
        "open_time": datetime.now().isoformat(), "events": [],
    })
    _save_store(data)
    return f"➕ <b>{sym} {side.upper()}</b> agregado @ <code>${entry:.4f}</code>"


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_manual_monitor():
    logger.info("MANUAL POSITIONS MONITOR ACTIVADO")
    while True:
        try:
            thread_health.heartbeat("manual_monitor")
            data = _load_store()
            active = [p for p in data if p.get("active", True)]
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
