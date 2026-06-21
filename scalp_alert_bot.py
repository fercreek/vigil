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
import indicators_swing
import trading_executor
import ccxt
import yfinance as yf
import social_analyzer
from config import (V4_EMA_PROXIMITY_MAX, V4_EMA_PROXIMITY_MIN, V4_RSI_LOW,
                    V4_RSI_HIGH, V4_RSI_HIGH_ZEC, V4_MIN_CONFLUENCE,
                    V4_ATR_SL_MULT, V4_COOLDOWN, SYMBOLS)
import alert_manager

# Cargar variables de entorno
load_dotenv(override=True)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "35")) # Aumentamos ligeramente para proteger CoinGecko
PHASE_FILE = "phase.txt"
OFFSET_FILE = "last_update_id.txt"

# --- RESILIENCE ENGINE (CACHE) ---
GLOBAL_CACHE = {
    "prices": {},
    "indicators": {},
    "global_metrics": {"usdt_d": 8.08, "btc_d": 52.0},
    "macro_metrics": {"spy": 0.0, "oil": 0.0, "nvda": 0.0, "pltr": 0.0, "tlt": 0.0, "hyg": 0.0, "dxy": 0.0, "vix": 0.0},
    "last_update": {
        "prices": 0,
        "indicators": {},
        "global_metrics": 0,
        "macro_metrics": 0,
        "fail_count": 0
    },
    "last_rsi": {"SOL": 50.0, "BTC": 50.0, "TAO": 50.0, "ZEC": 50.0, "TON": 50.0},
    "social_intel": {},  # {sym: {"score": 0.0, "last_update": 0}}
    "executor": None, # V5.0 Instance
    "shadow_messages": [], # V15.0 Real Shadow Intel
    "fear_greed": {"value": 50, "label": "Neutral"},
    "paused": False,  # F2 runtime flag (set via /pause, /resume)
}

# Hydrate runtime flags from disk (survive restarts)
try:
    import runtime_state as _rs
    _persisted = _rs.load()
    GLOBAL_CACHE["paused"] = bool(_persisted.get("paused", False))
    if _persisted.get("execution_mode") in ("PAPER", "LIVE"):
        os.environ["EXECUTION_MODE"] = _persisted["execution_mode"]
except Exception as _e:
    print(f"WARN runtime_state hydrate: {_e}")

# --- POSITION TRACKER: evita alertas duplicadas para la misma posición abierta ---
# Clave: "{sym}_{side}" → timestamp de cuando se abrió
# Se limpia cuando llega confirmación de TP/SL o manualmente via Telegram
OPEN_POSITIONS = {}
POSITION_TTL = 3600  # 1 hora: posición se considera expirada si no hay TP/SL en ese tiempo
# Tiempos de Vida (TTL) en segundos
TTL_PRICES = 20      # Precio: 20s (Fallback si falla la red)
TTL_INDICATORS = 600 # Indicadores: 10 min — antes 5min, reducido para bajar Binance API calls ~50%
TTL_GLOBAL = 600     # Métricas Globales: 10 min
TTL_MACRO = 900      # Macro (SPY/Oil): 15 min (Lento)
TTL_SOCIAL = 1800    # Inteligencia Social: 30 min (sin Twitter API, reducir tokens)

# ─── Pending Signals Store ───────────────────────────────────────────────────
# Señales detectadas esperando decisión de Fernando (Activar / Skip).
# NO se loguean en DB hasta que Fernando elija. GC automático cada ciclo.
_PENDING_SIGNALS: dict[int, dict] = {}  # {signal_id: {...params}}
_PENDING_SIG_COUNTER: int = 0
_PENDING_SIG_TTL: float = 14400.0      # 4h: señal expira si no se decide

def _store_pending(sym, side, entry, tp1, tp2, sl, atr, rsi, score,
                   alert_type, version, trigger_conditions, macro_regime="") -> int:
    """Guarda parámetros de señal. Retorna signal_id para callback_data.
    Auto-crea SIM trade al momento de la señal — independiente de si Fernando activa o skipea.
    """
    global _PENDING_SIG_COUNTER
    _PENDING_SIG_COUNTER += 1
    sid = _PENDING_SIG_COUNTER

    # Auto-SIM: loguear inmediatamente como simulación para tracking automático SL/TP
    try:
        sim_id = tracker.log_simulated(
            sym, side, entry, tp1, tp2, sl, msg_id=0,
            version=version, rsi=rsi, score=score,
            alert_type=alert_type, trigger_conditions=trigger_conditions,
            macro_regime=macro_regime,
        )
    except Exception as _e:
        print(f"⚠️ [AutoSIM] Error creando SIM para {sym}: {_e}")
        sim_id = None

    _PENDING_SIGNALS[sid] = {
        "sym": sym, "side": side, "entry": entry,
        "tp1": tp1, "tp2": tp2, "sl": sl, "atr": atr,
        "rsi": rsi, "score": score, "alert_type": alert_type,
        "version": version, "trigger_conditions": trigger_conditions,
        "macro_regime": macro_regime, "ts": time.time(),
        "sim_id": sim_id,  # SIM ya corriendo — monitor_open_trades lo cierra en SL/TP
    }
    if sim_id:
        print(f"🎮 [AutoSIM] {sym} {side} SIM#{sim_id} iniciado @ ${entry:,.4f}")
    return sid

def _gc_pending_signals():
    """Limpia señales pendientes expiradas."""
    now = time.time()
    expired = [sid for sid, s in _PENDING_SIGNALS.items()
               if now - s.get("ts", 0) > _PENDING_SIG_TTL]
    for sid in expired:
        _PENDING_SIGNALS.pop(sid, None)

# ─── Multi-Symbol Event Detector ─────────────────────────────────────────────
# Detecta cuando varios símbolos disparan señales simultáneamente → market scan
_SIGNAL_EVENTS: dict = {}   # {symbol: timestamp}
_MULTI_SIG_WINDOW  = 300    # 5 min: ventana de detección
_MULTI_SIG_TRIGGER = 2      # señales simultáneas para activar scan (2 de 3 símbolos)
_LAST_SCAN_TS      = 0.0    # evita scans duplicados en la misma ventana

import ai_budget as _ai_budget

def register_signal_event(sym: str, prices: dict) -> None:
    """
    Registra que el símbolo disparó una señal ahora.
    Si >= _MULTI_SIG_TRIGGER símbolos reaccionaron en los últimos 5 min,
    lanza get_market_scan() con un único call de IA (no N calls).
    """
    global _LAST_SCAN_TS
    now = time.time()
    _SIGNAL_EVENTS[sym] = now

    # Purgar eventos viejos
    active = {s: t for s, t in _SIGNAL_EVENTS.items() if now - t <= _MULTI_SIG_WINDOW}
    _SIGNAL_EVENTS.clear()
    _SIGNAL_EVENTS.update(active)

    if len(active) < _MULTI_SIG_TRIGGER:
        return  # No hay suficientes señales simultáneas

    # Evitar scan duplicado en la misma ventana
    if now - _LAST_SCAN_TS < _MULTI_SIG_WINDOW:
        return

    symbols_firing = [f"{s}/USDT" for s in active.keys()]
    _LAST_SCAN_TS = now
    try:
        scan = gemini_analyzer.get_market_scan(symbols_firing, prices)
        ts_str = datetime.now().strftime("%H:%M")
        msg = (f"⚡ <b>EVENTO MULTI-SÍMBOLO [{ts_str}]</b>\n"
               f"Señales en: <code>{', '.join(symbols_firing)}</code>\n\n"
               f"{safe_html(scan)}")
        send_telegram(msg)
        print(f"[Multi-Signal] Scan enviado para {symbols_firing}")
        add_shadow_intel("MULTI", f"Análisis unificado para {', '.join(symbols_firing)} completado.")
    except Exception as e:
        print(f"❌ Error en Multi-Signal scan: {e}")

def add_shadow_intel(sym: str, msg: str):
    """Añade un mensaje real a la cola de Shadow Intel para el dashboard."""
    ts = datetime.now().strftime("%H:%M")
    new_msg = {"ts": ts, "msg": f"🥷 <b>{sym}</b>: {msg}"}
    msgs = GLOBAL_CACHE.get("shadow_messages", [])
    msgs.insert(0, new_msg)
    GLOBAL_CACHE["shadow_messages"] = msgs[:10] # Mantener los últimos 10

def safe_html(text: str) -> str:
    """Delegado a alert_manager.safe_html — ver ese módulo."""
    import alert_manager
    return alert_manager.safe_html(text)
def sanitize_dict(d: dict) -> dict:
    """Asegura que todos los valores numéricos en el diccionario sean válidos."""
    if not d or not isinstance(d, dict): return {}
    for k in list(d.keys()):
        if d[k] is None:
            if "RSI" in k: d[k] = 50.0
            elif "USDT_D" in k: d[k] = 8.08
            elif "BTC_D" in k: d[k] = 52.0
            else: d[k] = 0.0
    return d

# ─── CONFIGURACIÓN DE NIVELES ──────────────────────────────────────────────
LEVELS = {
    "SOL": {"short_entry_high": 182, "sl_short": 188, "target1": 165, "target2": 160, "long_zone": 158},
    "TAO": {"resistance": 320, "target1": 290, "target2": 270, "long_zone": 265, "long_sl": 238},
    "BTC": {"resistance": 68283, "support1": 65000, "support2": 62987}
}

# ─── CONECTORES DE INTERCAMBIO (REUTILIZABLES) ──────────────────────────
# Inicializamos una vez para evitar latencia de conexión
from exchange_singleton import binance_spot as binance_ex

def get_phase() -> str:
    if not os.path.exists(PHASE_FILE): return "SHORT"
    with open(PHASE_FILE, "r") as f: return f.read().strip()

def set_phase(phase: str):
    with open(PHASE_FILE, "w") as f: f.write(phase)
    send_telegram(f"🔄 <b>CAMBIO DE ESTRATEGIA</b>: Fase actualizada a <code>{phase}</code>")

def update_dynamic_levels():
    """Calcula Soportes/Resistencias Diarios basados en ayer (Pivot Points)."""
    print("\n🔄 Actualizando niveles dinámicos (Pivot Points)...")
    symbols = {
        "BTC": (binance_ex, "BTC/USDT"),
        "TAO": (binance_ex, "TAO/USDT"),
        "ZEC": (binance_ex, "ZEC/USDT"),
        "ETH": (binance_ex, "ETH/USDT"),
        "SOL": (binance_ex, "SOL/USDT"),
        "HBAR": (binance_ex, "HBAR/USDT"),
        "DOGE": (binance_ex, "DOGE/USDT"),
        "TON":  (binance_ex, "TON/USDT"),
    }

    for key, (exchange, sym) in symbols.items():
        try:
            ohlcv = exchange.fetch_ohlcv(sym, timeframe='1d', limit=2)
            if len(ohlcv) < 2: continue
            ayer = ohlcv[0] # Vela cerrada
            h, l, c = ayer[2], ayer[3], ayer[4]
            p = (h + l + c) / 3
            r1 = (2 * p) - l
            s1 = (2 * p) - h
            
            # Pivot points genéricos para todos los símbolos
            if key not in LEVELS:
                LEVELS[key] = {}
            _dec = 0 if key == "BTC" else (4 if key in ("HBAR", "DOGE") else 2)
            LEVELS[key]["resistance"] = round(r1, _dec)
            LEVELS[key]["target1"] = round(p, _dec)
            LEVELS[key]["long_zone"] = round(s1, _dec)
            LEVELS[key]["long_sl"] = round(s1 * 0.98, _dec)
            LEVELS[key]["short_entry_high"] = round(r1, _dec)
            LEVELS[key]["sl_short"] = round(r1 * 1.01, _dec)
            
            print(f"✅ {key} R1: ${(r1 or 0.0):,.2f} | S1: ${(s1 or 0.0):,.2f}")
        except Exception as e:
            # Error silencioso de red para evitar spam en logs
            if "NameResolutionError" in str(e) or "Max retries exceeded" in str(e):
                print(f"⚠️ [Network] Error niveles {key} (DNS/Conexión)")
            else:
                print(f"❌ Error niveles {key}: {e}")

fired = {}

def get_alert_inline_keyboard(sym: str, side: str = "LONG") -> dict:
    """Delegado a alert_manager.get_alert_inline_keyboard — ver ese módulo."""
    import alert_manager
    return alert_manager.get_alert_inline_keyboard(sym, side)


def _answer_callback(callback_id: str, text: str = ""):
    """Delegado a alert_manager.answer_callback — ver ese módulo."""
    import alert_manager
    alert_manager.answer_callback(callback_id, text)


def _handle_callback(callback: dict, prices: dict):
    """Procesa inline keyboard callbacks de alertas de trading."""
    cb_id   = callback.get("id")
    data    = callback.get("data", "")
    msg_obj = callback.get("message", {})
    msg_id  = str(msg_obj.get("message_id", ""))
    chat_id = str(callback.get("from", {}).get("id", ""))

    if chat_id != str(TELEGRAM_CHAT_ID):
        return

    _gc_pending_signals()  # limpia señales expiradas en cada callback

    parts = data.split(":")
    action = parts[0]

    # ── Budget ──────────────────────────────────────────────────────────────
    if action == "budget":
        import ai_budget
        summary = ai_budget.get_budget_summary_html()
        send_telegram(summary)
        _answer_callback(cb_id, "💰 Budget actualizado")
        return

    # ── Open flow (inline picker /open) ──────────────────────────────────────
    if action.startswith("open_"):
        import requests as _req
        import telegram_commands as _tc

        def _edit_msg(text: str, kb: dict = None):
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID, "message_id": int(msg_id),
                "text": text, "parse_mode": "HTML",
            }
            if kb is not None:
                payload["reply_markup"] = kb
            try:
                _req.post(url, json=payload, timeout=10)
            except Exception as e:
                print(f"❌ editMessageText: {e}")

        if action == "open_cancel":
            _edit_msg("❌ Apertura cancelada.")
            _answer_callback(cb_id, "Cancelado")
            return

        if action == "open_sym" and len(parts) >= 2:
            sym = parts[1].upper()
            _edit_msg(
                f"➕ <b>{sym}</b> seleccionado. Side?",
                _tc.open_side_keyboard(sym),
            )
            _answer_callback(cb_id, sym)
            return

        if action == "open_side" and len(parts) >= 3:
            sym = parts[1].upper()
            side = parts[2].upper()
            p = prices.get(sym) or 0.0
            atr = prices.get(f"{sym}_ATR") or p * 0.01
            if p <= 0:
                _edit_msg(f"❌ Sin precio para {sym}. Aborta.")
                _answer_callback(cb_id, "Sin precio")
                return
            lv = _tc.compute_levels(side, p, atr)
            text = (
                f"➕ <b>{sym} {side} MANUAL</b>\n"
                f"Entrada: <code>${p:,.4f}</code>\n"
                f"🎯 TP1: <b>${lv['tp1']:,.4f}</b> | TP2: <b>${lv['tp2']:,.4f}</b>\n"
                f"🛑 SL: <b>${lv['sl']:,.4f}</b>\n\n"
                f"Confirmar apertura?"
            )
            _edit_msg(text, _tc.open_confirm_keyboard(sym, side, p))
            _answer_callback(cb_id, f"{sym} {side}")
            return

        if action == "open_confirm" and len(parts) >= 4:
            sym = parts[1].upper()
            side = parts[2].upper()
            try:
                entry = float(parts[3])
            except ValueError:
                _edit_msg("❌ Entry inválido.")
                _answer_callback(cb_id, "Entry inválido")
                return
            atr = prices.get(f"{sym}_ATR") or entry * 0.01
            lv = _tc.compute_levels(side, entry, atr)
            tid = tracker.log_trade(
                sym, side, entry, lv["tp1"], lv["tp2"], lv["sl"], msg_id,
                version="MANUAL", rsi=prices.get(f"{sym}_RSI", 50),
                is_manual=1,
            )
            tracker.append_event(tid, f"OPENED {side} @ ${entry:.4f} via /open")
            import alert_manager as _am
            _edit_msg(
                f"✅ <b>{sym} {side} ABIERTO</b> (id {tid})\n"
                f"Entrada: <code>${entry:,.4f}</code>\n"
                f"🎯 TP1: ${lv['tp1']:,.4f} | TP2: ${lv['tp2']:,.4f}\n"
                f"🛑 SL: ${lv['sl']:,.4f}",
                kb=_am.get_management_keyboard(tid, sym, side),
            )
            _answer_callback(cb_id, "✅ Abierto")
            return

    # ── Activate signal (Fernando decide operar) ────────────────────────────
    if action == "activate" and len(parts) >= 4:
        try:
            sid, sym, side = int(parts[1]), parts[2].upper(), parts[3].upper()
        except (ValueError, IndexError):
            _answer_callback(cb_id, "❌ Formato inválido")
            return
        sig = _PENDING_SIGNALS.pop(sid, None)
        if not sig:
            _answer_callback(cb_id, "⚠️ Señal expirada o ya procesada")
            return

        # Stocks: fetch precio LIVE al momento de activar (no el precio cuando sonó la alerta)
        if sig.get("version") == "STOCK":
            try:
                import yfinance as _yf
                live_p = float(_yf.Ticker(sym).fast_info.last_price or 0)
                if live_p > 0:
                    _atr = sig.get("atr", live_p * 0.02)
                    sig["entry"] = live_p
                    if side == "LONG":
                        sig["sl"]  = round(live_p - _atr * 2.5, 4)
                        sig["tp1"] = sig.get("tp1") or round(live_p + _atr * 2.0, 4)
                        sig["tp2"] = sig.get("tp2") or round(live_p + _atr * 3.5, 4)
                    else:
                        sig["sl"]  = round(live_p + _atr * 2.5, 4)
                        sig["tp1"] = sig.get("tp1") or round(live_p - _atr * 2.0, 4)
                        sig["tp2"] = sig.get("tp2") or round(live_p - _atr * 3.5, 4)
            except Exception as _ex:
                print(f"WARN: stock live price {sym}: {_ex}")

        entry = sig["entry"]
        tid = tracker.log_trade(
            sym, side, entry, sig["tp1"], sig["tp2"], sig["sl"], msg_id,
            version=sig["version"], rsi=sig["rsi"], score=sig["score"],
            alert_type=sig["alert_type"], trigger_conditions=sig["trigger_conditions"],
            is_manual=0,
        )
        tracker.append_event(tid, f"ACTIVATED via Telegram @ ${entry:.4f}")
        # Wire episode_id from pending → episode_ids (for fill_outcome at close)
        _ep = GLOBAL_CACHE.get("pending_ep_ids", {}).pop(sid, None)
        if _ep:
            GLOBAL_CACHE.setdefault("episode_ids", {})[tid] = _ep
        import alert_manager as _am
        _edit_msg(
            f"✅ <b>ACTIVADO — {sym} {side}</b> (id {tid})\n"
            f"Entrada: <code>${entry:,.4f}</code>\n"
            f"🎯 TP1: ${sig['tp1']:,.4f} | TP2: ${sig['tp2']:,.4f}\n"
            f"🛑 SL: ${sig['sl']:,.4f}",
            kb=_am.get_management_keyboard(tid, sym, side),
        )
        _answer_callback(cb_id, f"✅ {sym} {side} activado")
        # Confirmación separada — mensaje nuevo en el chat como backup visible
        send_telegram(
            f"🎯 <b>TRADE ABIERTO #{tid}</b>\n"
            f"<b>{sym} {side}</b> @ <code>${entry:,.4f}</code>\n"
            f"TP1 ${sig['tp1']:,.4f} | TP2 ${sig['tp2']:,.4f} | SL ${sig['sl']:,.4f}"
        )
        return

    # ── Skip signal (Fernando pasa, pero bot trackea outcome sim) ────────────
    if action == "skip" and len(parts) >= 4:
        try:
            sid, sym, side = int(parts[1]), parts[2].upper(), parts[3].upper()
        except (ValueError, IndexError):
            _answer_callback(cb_id, "❌ Formato inválido")
            return
        sig = _PENDING_SIGNALS.pop(sid, None)
        if sig:
            # SIM ya fue creado en _store_pending (AutoSIM). Evitar duplicado.
            if not sig.get("sim_id"):
                tracker.log_simulated(
                    sym, side, sig["entry"], sig["tp1"], sig["tp2"], sig["sl"],
                    msg_id, version=sig["version"], rsi=sig["rsi"],
                    score=sig["score"], alert_type=sig["alert_type"],
                    trigger_conditions=sig["trigger_conditions"],
                    macro_regime=sig.get("macro_regime", ""),
                )
        _edit_msg(f"⏭️ <b>{sym} {side}</b> skiada. SIM#{sig['sim_id'] if sig else '?'} corriendo.")
        _answer_callback(cb_id, "⏭️ Skiada — SIM activo")
        return

    # ── Cerrar posición al precio actual ────────────────────────────────────
    if action == "close_now" and len(parts) >= 4:
        try:
            trade_id, sym, side = int(parts[1]), parts[2].upper(), parts[3].upper()
        except (ValueError, IndexError):
            _answer_callback(cb_id, "❌ Formato inválido")
            return
        trade = tracker.get_trade_by_id(trade_id)
        if not trade:
            _answer_callback(cb_id, f"❌ Trade {trade_id} no encontrado")
            return
        p = prices.get(sym, 0.0)
        if p <= 0:
            _answer_callback(cb_id, f"⚠️ Sin precio para {sym}")
            return
        entry = trade["entry_price"] or 0.0
        pnl_pct = ((p - entry) / entry * 100) if entry else 0.0
        if side == "SHORT":
            pnl_pct = -pnl_pct
        status = "FULL_WON" if pnl_pct >= 0 else "LOST"
        tracker.update_trade_status(trade_id, status)
        tracker.append_event(trade_id, f"CLOSED @ ${p:.4f} ({pnl_pct:+.2f}%) via Telegram")
        close_position(sym, side)
        color = "🟢" if pnl_pct >= 0 else "🔴"
        _edit_msg(
            f"🏁 <b>CERRADO {sym} {side}</b> (id {trade_id})\n"
            f"${entry:,.4f} → <code>${p:,.4f}</code>\n"
            f"{color} PnL: <b>{pnl_pct:+.2f}%</b> | Estado: <code>{status}</code>"
        )
        _answer_callback(cb_id, f"Cerrado {pnl_pct:+.2f}%")
        return

    # ── P&L flotante por trade_id ────────────────────────────────────────────
    if action == "pnl" and len(parts) >= 3:
        try:
            trade_id, sym = int(parts[1]), parts[2].upper()
        except (ValueError, IndexError):
            _answer_callback(cb_id, "❌ Formato inválido")
            return
        trade = tracker.get_trade_by_id(trade_id)
        if not trade:
            _answer_callback(cb_id, f"❌ Trade {trade_id} no encontrado")
            return
        p = prices.get(sym, 0.0)
        entry = trade["entry_price"] or 0.0
        pnl_pct = ((p - entry) / entry * 100) if entry else 0.0
        if trade["type"] == "SHORT":
            pnl_pct = -pnl_pct
        color = "🟢" if pnl_pct > 0 else "🔴"
        send_telegram(
            f"{color} <b>{sym} {trade['type']}</b> (id {trade_id})\n"
            f"Entrada: ${entry:,.4f} → Precio: <code>${p:,.4f}</code>\n"
            f"PnL: <b>{pnl_pct:+.2f}%</b>",
            reply_to=msg_id,
        )
        _answer_callback(cb_id, f"PnL: {pnl_pct:+.2f}%")
        return

    # ── Status de posición ───────────────────────────────────────────────────
    if action == "status" and len(parts) >= 2:
        sym = parts[1]
        trade = tracker.get_last_open_trade(sym)
        if trade:
            p = prices.get(sym, 0.0)
            entry = trade["entry_price"]
            pnl_pct = ((p - entry) / entry * 100) if entry else 0.0
            if trade.get("type") == "SHORT":
                pnl_pct = -pnl_pct
            color = "🟢" if pnl_pct > 0 else "🔴"
            send_telegram(
                f"{color} <b>{sym} {trade['type']}</b> — Entrada: ${entry:,.2f}\n"
                f"Precio actual: <code>${p:,.2f}</code>\n"
                f"PnL flotante: <b>{pnl_pct:+.2f}%</b>",
                reply_to=msg_id,
            )
            _answer_callback(cb_id, f"PnL: {pnl_pct:+.2f}%")
        else:
            _answer_callback(cb_id, f"Sin posición abierta en {sym}")
        return

    # ── TP/SL outcome ────────────────────────────────────────────────────────
    # Formato nuevo (management keyboard): tp1:TRADE_ID:SYM:SIDE  → 4 parts
    # Formato viejo (legacy alerts):       tp1:SYM:SIDE            → 3 parts
    if action in ("tp1", "tp2", "tp3", "sl") and len(parts) >= 3:
        if len(parts) >= 4 and parts[1].isdigit():
            # Nuevo formato: lookup preciso por trade_id
            trade_id_int = int(parts[1])
            sym  = parts[2].upper()
            side = parts[3].upper()
            trade = tracker.get_trade_by_id(trade_id_int)
        else:
            # Formato legacy: lookup por símbolo (last open)
            sym  = parts[1].upper()
            side = parts[2].upper()
            trade = tracker.get_last_open_trade(sym)

        if not trade:
            _answer_callback(cb_id, f"No hay trade abierto en {sym}")
            return

        entry = trade["entry_price"]
        p     = prices.get(sym, 0.0)

        if action == "tp1":
            status = "PARTIAL_WON"
            label  = "TP1 (50% cerrado)"
            emoji  = "✅"
        elif action == "tp2":
            status = "PARTIAL_WON"
            label  = "TP2 (80% cerrado)"
            emoji  = "✅"
        elif action == "tp3":
            status = "FULL_WON"
            label  = "TP3 COMPLETO"
            emoji  = "🏆"
        else:  # sl
            status = "LOST"
            label  = "SL tocado"
            emoji  = "🛑"

        pnl_pct = ((p - entry) / entry * 100) if entry else 0.0
        if side == "SHORT":
            pnl_pct = -pnl_pct

        tracker.update_trade_status(trade["id"], status)
        close_position(sym, side)

        send_telegram(
            f"{emoji} <b>{label} — {sym} {side}</b>\n"
            f"Entrada: ${entry:,.2f} → Precio: <code>${p:,.2f}</code>\n"
            f"PnL registrado: <b>{pnl_pct:+.2f}%</b>\n"
            f"Estado: <code>{status}</code>",
            reply_to=msg_id,
        )
        _answer_callback(cb_id, f"{emoji} {label} registrado")
        print(f"[Callback] {sym} {side} → {status} ({pnl_pct:+.2f}%)")


def _handle_user_question(text: str, prices: dict):
    """
    Responde mensajes libres del usuario (saludos o preguntas sobre cripto)
    con un panel de 4 agentes, cada uno con score 1-5.
    """
    greetings = ["hola", "hi", "hello", "hey", "buenas", "buenos", "buen día", "saludos", "ola"]
    is_greeting = any(g in text.lower() for g in greetings)

    sym_map = {
        "btc": "BTC/USDT", "bitcoin": "BTC/USDT",
        "tao": "TAO/USDT", "bittensor": "TAO/USDT",
        "zec": "ZEC/USDT", "zcash": "ZEC/USDT",
        "hbar": "HBAR/USDT", "hedera": "HBAR/USDT",
        "doge": "DOGE/USDT", "dogecoin": "DOGE/USDT",
        "eth": "ETH/USDT", "ethereum": "ETH/USDT",
        "ton": "TON/USDT", "toncoin": "TON/USDT",
    }
    detected_sym = None
    for k, v in sym_map.items():
        if k in text.lower():
            detected_sym = v
            break

    if is_greeting and not detected_sym:
        lines = ["👋 <b>¡Hola! Soy Zenith.</b> Aquí el pulso del mercado:\n"]
        for sym in ["BTC/USDT", "TAO/USDT", "ZEC/USDT"]:
            p   = prices.get(sym, 0)
            rsi = prices.get(f"{sym}_RSI", 50)
            arrow = "📈" if rsi < 45 else ("📉" if rsi > 55 else "↔️")
            lines.append(f"{arrow} <b>{sym.replace('/USDT','')}</b>: ${p:,.2f} | RSI {rsi:.1f}")
        lines.append("\n💬 Puedes preguntarme sobre BTC, TAO, ZEC o cualquier tema del mercado.")
        send_telegram("\n".join(lines), keyboard=get_main_menu("TAO"))
        return

    panel = gemini_analyzer.get_qa_panel(text, detected_sym, prices)
    sym_label = detected_sym.replace("/USDT", "") if detected_sym else "TAO"
    send_telegram(panel, keyboard=get_main_menu(sym_label))


def get_main_menu(symbol="ZEC"):
    """Delegado a alert_manager.get_main_menu — ver ese módulo."""
    import alert_manager
    return alert_manager.get_main_menu(symbol)

def send_telegram(msg: str, reply_to: str = None, keyboard: dict = None):
    """Delegado a alert_manager.send_telegram — ver ese módulo."""
    import alert_manager
    return alert_manager.send_telegram(msg, reply_to, keyboard)

def alert(key: str, msg: str, version: str = "V1-TECH", cooldown: int = 300,
          reply_to: str = None, inline_keyboard: dict = None):
    """Delegado a alert_manager.alert — ver ese módulo."""
    import alert_manager
    return alert_manager.alert(key, msg, version, cooldown, reply_to, inline_keyboard)

def calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d=8.0, side="LONG", elliott="", spy=0.0, oil=0.0, ob_detected=False, funding_signal=0):
    """Delegado a strategies.py — ver ese módulo."""
    import strategies
    return strategies.calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy, oil, ob_detected, funding_signal=funding_signal)

def get_confluence_badge(score):
    """Delegado a strategies.py — ver ese módulo."""
    import strategies
    return strategies.get_confluence_badge(score)

def build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy,
                              macro_dict, macro_status, atr, elliott, ob_detected,
                              social_adj, trade_type, phy_bias, conf_score,
                              strategy, side, rsi_threshold=42.0):
    """Delegado a strategies.py — ver ese módulo."""
    import strategies
    return strategies.build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, conf_score, strategy, side, rsi_threshold)

def classify_trade(vix: float, dxy: float, macro_status: str) -> str:
    """Delegado a strategies.py — ver ese módulo."""
    import strategies
    return strategies.classify_trade(vix, dxy, macro_status)

def is_position_open(sym: str, side: str) -> bool:
    """Verifica si ya existe una posición abierta para este símbolo+dirección."""
    key = f"{sym}_{side}"
    if key not in OPEN_POSITIONS:
        return False
    # Verificar TTL: si expiró, limpiar
    if time.time() - OPEN_POSITIONS[key] > POSITION_TTL:
        del OPEN_POSITIONS[key]
        return False
    return True

def open_position(sym: str, side: str):
    """Registra una posición como abierta."""
    OPEN_POSITIONS[f"{sym}_{side}"] = time.time()

def close_position(sym: str, side: str):
    """Marca una posición como cerrada."""
    OPEN_POSITIONS.pop(f"{sym}_{side}", None)

def format_confidence(score):
    """Mapea score 0-5 a porcentaje 60-100% para UX."""
    # 5 -> 100%, 4 -> 90%, 3 -> 80%, 2 -> 70%, 1 -> 60%, 0 -> 50%
    pct = 50 + (score * 10)
    return f"{pct}%"

def get_prices() -> dict:
    """Consolida llamadas priorizando Binance con Fallback a Caché y CoinGecko (Optimización V3.2)."""
    now = time.time()
    res = GLOBAL_CACHE["prices"].copy() 
    
    # 1. ¿Necesitamos actualizar precios? (Optimizado: 1 sola llamada)
    if now - GLOBAL_CACHE["last_update"]["prices"] > TTL_PRICES:
        symbols = ['ETH/USDT', 'BTC/USDT', 'TAO/USDT', 'ZEC/USDT', 'SOL/USDT', 'PAXG/USDT', 'HBAR/USDT', 'DOGE/USDT', 'TON/USDT', 'SUI/USDT', 'FIL/USDT']
        try:
            # OPTIMIZACIÓN V3.2: fetch_tickers (Plural) es más eficiente que 4 llamadas separadas
            tickers = binance_ex.fetch_tickers(symbols)

            res["ETH"] = tickers.get('ETH/USDT', {}).get('last', res.get("ETH"))
            res["BTC"] = tickers.get('BTC/USDT', {}).get('last', res.get("BTC"))
            res["TAO"] = tickers.get('TAO/USDT', {}).get('last', res.get("TAO"))
            res["ZEC"] = tickers.get('ZEC/USDT', {}).get('last', res.get("ZEC"))
            res["SOL"] = tickers.get('SOL/USDT', {}).get('last', res.get("SOL"))
            res["GOLD"] = tickers.get('PAXG/USDT', {}).get('last', res.get("GOLD"))
            res["HBAR"] = tickers.get('HBAR/USDT', {}).get('last', res.get("HBAR"))
            res["DOGE"] = tickers.get('DOGE/USDT', {}).get('last', res.get("DOGE"))
            res["TON"]  = tickers.get('TON/USDT',  {}).get('last', res.get("TON"))
            res["SUI"]  = tickers.get('SUI/USDT',  {}).get('last', res.get("SUI"))
            res["FIL"]  = tickers.get('FIL/USDT',  {}).get('last', res.get("FIL"))

            # Monitoreo de Carga (Opcional: X-MBX-USED-WEIGHT)
            weight = binance_ex.last_response_headers.get('X-MBX-USED-WEIGHT-1M', 'N/A')
            if weight != 'N/A' and int(weight) > 1000:
                print(f"⚠️ [API Alert] Binance Weight elevado: {weight}/1200")
            
            GLOBAL_CACHE["prices"].update(res)
            GLOBAL_CACHE["last_update"]["prices"] = now
            GLOBAL_CACHE["last_update"]["fail_count"] = 0 
        except Exception:
            # Silencioso: Fallback a CoinGecko o Caché
            GLOBAL_CACHE["last_update"]["fail_count"] += 1
            if GLOBAL_CACHE["last_update"]["fail_count"] > 10:
                print("⚠️ [Resilience Mode] Red inestable detectada. Usando datos previos.")
                GLOBAL_CACHE["last_update"]["fail_count"] = 0 

            try:
                # Fallback a CoinGecko
                ids = "ethereum,bittensor,bitcoin,pax-gold,zcash,hedera-hashgraph,dogecoin,the-open-network"
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
                cg_r = requests.get(url, timeout=10).json()
                res["ETH"] = cg_r.get("ethereum", {}).get("usd", res.get("ETH", 0.0))
                res["BTC"] = cg_r.get("bitcoin", {}).get("usd", res.get("BTC", 0.0))
                res["TAO"] = cg_r.get("bittensor", {}).get("usd", res.get("TAO", 0.0))
                res["SOL"] = cg_r.get("solana", {}).get("usd", res.get("SOL", 0.0))
                res["ZEC"] = cg_r.get("zcash", {}).get("usd", res.get("ZEC", 0.0))
                res["GOLD"] = cg_r.get("pax-gold", {}).get("usd", res.get("GOLD", 0.0))
                res["HBAR"] = cg_r.get("hedera-hashgraph", {}).get("usd", res.get("HBAR", 0.0))
                res["DOGE"] = cg_r.get("dogecoin", {}).get("usd", res.get("DOGE", 0.0))
                res["TON"]  = cg_r.get("the-open-network", {}).get("usd", res.get("TON", 0.0))
                res["SUI"]  = cg_r.get("sui", {}).get("usd", res.get("SUI", 0.0))
                res["FIL"]  = cg_r.get("filecoin", {}).get("usd", res.get("FIL", 0.0))
                
                GLOBAL_CACHE["prices"].update(res)
                GLOBAL_CACHE["last_update"]["prices"] = now
            except:
                pass 

    # 2. Métricas Globales (TTL_GLOBAL)
    if now - GLOBAL_CACHE["last_update"]["global_metrics"] > TTL_GLOBAL:
        usdt_d, btc_d = indicators.get_global_metrics()
        GLOBAL_CACHE["global_metrics"] = {"usdt_d": usdt_d, "btc_d": btc_d}
        GLOBAL_CACHE["last_update"]["global_metrics"] = now
        
    res["USDT_D"] = GLOBAL_CACHE["global_metrics"]["usdt_d"]
    res["BTC_D"] = GLOBAL_CACHE["global_metrics"]["btc_d"]
    
    # 2.2 FEAR & GREED INDEX (Optimizado: 1x/10min)
    if now - GLOBAL_CACHE["last_update"]["global_metrics"] > TTL_GLOBAL:
        try:
            fg_r = requests.get("https://api.alternative.me/fng/", timeout=5).json()
            if fg_r.get("data"):
                val = fg_r["data"][0]
                GLOBAL_CACHE["fear_greed"] = {"value": int(val["value"]), "label": val["value_classification"]}
                # Mensaje Shadow si hay extrema miedo
                if int(val["value"]) < 20:
                    add_shadow_intel("BTC", f"EXTREMO MIEDO ({val['value']}). Oportunidad de acumulación institucional detectada.")
        except: pass
    
    res["FEAR_GREED"] = GLOBAL_CACHE["fear_greed"]

    # --- 2.5 MACRO SENTIMENT (SPY / OIL / DXY / VIX) ---
    if now - GLOBAL_CACHE["last_update"]["macro_metrics"] > TTL_MACRO:
        try:
            import math
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
            # S&P 500, Petróleo, Nvidia y Palantir — descargar individualmente para evitar MultiIndex
            # SPY, OIL, NVDA, PLTR + iShares BlackRock ETFs (TLT=safe haven, HYG=risk appetite)
            macro_symbols = {
                "SPY":   "spy",
                "CL=F":  "oil",
                "NVDA":  "nvda",
                "PLTR":  "pltr",
                "TLT":   "tlt",   # iShares 20yr Treasury — TLT↑ = risk-off
                "HYG":   "hyg",   # iShares High Yield — HYG↑ = risk-on
            }
            macro_vals = {}
            _yf_pool = ThreadPoolExecutor(max_workers=1)
            for yf_sym, key in macro_symbols.items():
                try:
                    _future = _yf_pool.submit(yf.download, yf_sym, period="1d", interval="1m", progress=False)
                    _df = _future.result(timeout=20)
                    if _df is not None and not _df.empty and 'Close' in _df.columns:
                        val = float(_df['Close'].iloc[-1])
                        macro_vals[key] = val if not math.isnan(val) else GLOBAL_CACHE["macro_metrics"].get(key, 0.0)
                    else:
                        macro_vals[key] = GLOBAL_CACHE["macro_metrics"].get(key, 0.0)
                except (FuturesTimeout, Exception):
                    macro_vals[key] = GLOBAL_CACHE["macro_metrics"].get(key, 0.0)
            _yf_pool.shutdown(wait=False)

            spy_p  = macro_vals.get("spy",  GLOBAL_CACHE["macro_metrics"].get("spy", 0.0))
            oil_p  = macro_vals.get("oil",  GLOBAL_CACHE["macro_metrics"].get("oil", 0.0))
            nvda_p = macro_vals.get("nvda", GLOBAL_CACHE["macro_metrics"].get("nvda", 0.0))
            pltr_p = macro_vals.get("pltr", GLOBAL_CACHE["macro_metrics"].get("pltr", 0.0))
            tlt_p  = macro_vals.get("tlt",  GLOBAL_CACHE["macro_metrics"].get("tlt", 0.0))
            hyg_p  = macro_vals.get("hyg",  GLOBAL_CACHE["macro_metrics"].get("hyg", 0.0))

            # DXY + VIX (indicadores clave para clasificar trades como RAPIDA/SWING)
            dxy_p, vix_p = indicators.get_dxy_vix()

            # BlackRock iShares bias (risk-on/off) — actualiza score en cache
            try:
                import blackrock_intel as _bri
                _ishares_bias = _bri.get_ishares_bias_score()
            except Exception:
                _ishares_bias = 0

            from config import OIL_INFLATION_THRESHOLD
            _oil_pressure = float(oil_p) > OIL_INFLATION_THRESHOLD
            GLOBAL_CACHE["macro_metrics"] = {
                "spy": float(spy_p), "oil": float(oil_p),
                "nvda": float(nvda_p), "pltr": float(pltr_p),
                "tlt": float(tlt_p), "hyg": float(hyg_p),
                "ishares_bias": _ishares_bias,  # +1 risk-on | 0 neutral | -1 risk-off
                "dxy": dxy_p, "vix": vix_p,
                "oil_inflation_pressure": _oil_pressure,
            }
            GLOBAL_CACHE["last_update"]["macro_metrics"] = now
            _oil_tag = " | ⛽ OIL INFLATION PRESSURE" if _oil_pressure else ""
            from config import MACRO_FEED_ENABLED as _macro_on
            _bri_label = ('+1 RISK_ON' if _ishares_bias > 0 else ('-1 RISK_OFF' if _ishares_bias < 0 else '0 NEUTRAL')) if _macro_on else 'OFF'
            _ishares_tag = f" | TLT: ${tlt_p:.2f} | HYG: ${hyg_p:.2f} | BRI: {_bri_label}"
            print(f"🌍 [Macro Update] SPY: ${spy_p:.2f} | DXY: {dxy_p:.2f} | VIX: {vix_p:.1f}{_oil_tag}{_ishares_tag}")
        except Exception as e:
            print(f"⚠️ Error Macro (Yahoo): {e}")

    res["SPY"] = GLOBAL_CACHE["macro_metrics"]["spy"]
    res["OIL"] = GLOBAL_CACHE["macro_metrics"]["oil"]
    res["DXY"] = GLOBAL_CACHE["macro_metrics"].get("dxy", 0.0)
    res["VIX"] = GLOBAL_CACHE["macro_metrics"].get("vix", 0.0)

    # 3. Datos Técnicos (TTL_INDICATORS para reducir carga)
    # Símbolos cuyo PRECIO ya viene del batch Binance/CoinGecko (arriba).
    # Los que no (ej. HYPE) se precian aquí vía OKX (fetch_ohlcv_with_fallback).
    _BATCH_PRICED = {"TAO", "BTC", "ZEC", "SOL", "ETH", "HBAR", "DOGE", "TON", "GOLD", "SUI", "FIL"}
    for sym in SYMBOLS:
        last_ind_update = GLOBAL_CACHE["last_update"]["indicators"].get(sym, 0)

        if now - last_ind_update > TTL_INDICATORS:
            try:
                # V12.1: Guardamos el previo para la inercia (Hook)
                GLOBAL_CACHE["last_rsi"][sym] = (res.get(f"{sym}_RSI") or 50.0)

                rsi = indicators.get_rsi(sym, timeframe='15m')
                vals = indicators.get_indicators(sym, "15m")
                macro = indicators.get_macro_trend(sym)
                
                GLOBAL_CACHE["indicators"][sym] = {
                    "rsi": vals[0], "bb_u": vals[1], "bb_l": vals[3], 
                    "ema_200": vals[4], "atr": vals[5], "vol_sma": vals[6], 
                    "elliott": vals[7], "poc": vals[8], "macro": macro
                }
                GLOBAL_CACHE["last_update"]["indicators"][sym] = now
                try:
                    _df_rvol = indicators.get_df(sym, '15m', limit=50)
                    if _df_rvol is not None and not _df_rvol.empty:
                        if len(_df_rvol) >= 24:
                            GLOBAL_CACHE["indicators"][sym]["rvol"] = indicators.calculate_rvol(_df_rvol, period=24)
                        # Precio para símbolos fuera del batch Binance (ej. HYPE) — vía OKX
                        if sym not in _BATCH_PRICED:
                            _px = float(_df_rvol['close'].iloc[-1])
                            res[sym] = _px
                            GLOBAL_CACHE["prices"][sym] = _px
                except Exception:
                    pass

                # V15: Real Shadow Intel — Reportar POC al sidebar
                if vals[8] > 0:
                    add_shadow_intel(sym, f"POC detectado en ${vals[8]:,.2f}. Zona de interés institucional.")
            except Exception:
                # Silencioso: Se mantiene la caché previa
                pass

        # Inyectar desde caché (sea nueva o vieja)
        ind = GLOBAL_CACHE["indicators"].get(sym, {})
        res[f"{sym}_RSI"] = ind.get("rsi") or 50.0
        res[f"{sym}_BB_U"] = ind.get("bb_u")
        res[f"{sym}_BB_L"] = ind.get("bb_l")
        res[f"{sym}_EMA_200"] = ind.get("ema_200", 0.0)
        res[f"{sym}_ATR"] = ind.get("atr", 0.0)
        res[f"{sym}_VOL_SMA"] = ind.get("vol_sma", 0.0)
        res[f"{sym}_MACRO"] = ind.get("macro", {"consensus": "NEUTRAL", "1H": "UNKNOWN", "4H": "UNKNOWN"})
        res[f"{sym}_ELLIOTT"] = ind.get("elliott", "")
        res[f"{sym}_POC"] = ind.get("poc", 0.0)
        res[f"{sym}_RVOL"] = ind.get("rvol", 1.0)

    return res

_LAST_MARKET_PULSE_TS = 0.0  # epoch — set when PULSO fires; PANORAMA suprime si <600s

def check_market_pulse(prices):
    """Detecta apertura/cierre NYSE y envía análisis híbrido."""
    global _LAST_MARKET_PULSE_TS
    now = datetime.now()
    # NYSE: 9:30 AM / 4:00 PM EST (Aproximado según servidor del usuario)
    # 09:30 Local (Apertura) | 16:00 Local (Cierre)
    is_open = now.hour == 9 and now.minute == 30
    is_close = now.hour == 16 and now.minute == 0

    if not (is_open or is_close):
        return

    event = "APERTURA" if is_open else "CIERRE"
    print(f"📡 [Market Pulse] Detectado evento de {event}")
    _LAST_MARKET_PULSE_TS = time.time()
    # Audit D (2026-05-23): PULSO no accionable. Modo quiet → skip envío.
    try:
        from config import ANALYSIS_MODE_QUIET as _QUIET
    except Exception:
        _QUIET = False
    if _QUIET:
        print("[PULSO] suprimido — ANALYSIS_MODE_QUIET=True")
        return
    
    for sym in ["SOL", "BTC"]:
        p, rsi = prices[sym], prices[f"{sym}_RSI"]
        bb_u, bb_l = prices[f"{sym}_BB_U"], prices[f"{sym}_BB_L"]
        ema_200 = prices[f"{sym}_EMA_200"]
        atr = prices[f"{sym}_ATR"]
        usdt_d = prices["USDT_D"]
        
        analysis = gemini_analyzer.get_market_pulse_analysis(
            sym, p, "Neutral", rsi, bb_u, bb_l, ema_200, atr, usdt_d
        )
        
        msg = (f"📡 <b>PULSO DE MERCADO (NYSE {event})</b>\n\n"
               f"🪙 <b>{sym}</b> @ ${(p or 0.0):,.2f}\n"
               f"📊 RSI: {(rsi or 0.0):.1f} | EMA: {'ALCISTA' if (p or 0.0) > (ema_200 or 0.0) else 'BAJISTA'}\n"
               f"💰 Volatilidad: {(atr or 0.0):,.2f} USD\n\n"
               f"🤖 <b>ANÁLISIS HÍBRIDO AI:</b>\n{safe_html(analysis)}")
        
        # Enviamos alerta única (no trackeamos como trade)
        alert(f"pulse_{sym}_{event}_{now.date()}", msg)

def check_strategies(prices: dict):
    """Delegado a strategies.py — ver ese módulo."""
    import strategies
    strategies.check_strategies(prices)


def monitor_open_trades(prices: dict):
    """Delegado a trade_monitor.py — ver ese módulo."""
    import trade_monitor
    trade_monitor.monitor_open_trades(prices)

def check_user_queries(prices: dict):
    """Delegado a telegram_commands.py — ver ese archivo para la lógica de comandos."""
    import telegram_commands
    telegram_commands.check_user_queries(prices)


def trigger_salmos_prophecy(prices):
    """Salmos analiza el mercado buscando la confluencia perfecta (Wave 3/5 + RSI)."""
    try:
        print("🔔 Salmos: Buscando profecía de tendencia...")
        setup = gemini_analyzer.get_top_setup(prices)

        # Detectar dirección SOLO desde la línea VEREDICTO para evitar falsos positivos
        veredicto_line = ""
        for line in setup.splitlines():
            if "VEREDICTO" in line.upper():
                veredicto_line = line.upper()
                break

        is_long  = "LONG"  in veredicto_line
        is_short = "SHORT" in veredicto_line

        if not (is_long or is_short):
            print(f"🔕 Salmos: Sin setup accionable — omitiendo alerta.")
            return

        ts = datetime.now().strftime("%H:%M")
        btc_p   = prices.get("BTC", 0)
        btc_rsi = prices.get("BTC_RSI", 0)
        usdt_d  = prices.get("USDT_D", 0)

        direction = "🟢 LONG" if is_long else "🔴 SHORT"
        header = (
            f"🔔 <b>PROFÉCIA DE SALMOS [{ts}]</b>\n"
            f"<code>BTC ${btc_p:,.0f} | RSI {btc_rsi:.0f} | USDT.D {usdt_d:.2f}%</code>\n"
            f"━━━━━━━━━━━━━\n"
            f"⚡ <b>SEÑAL: {direction}</b>\n"
            f"━━━━━━━━━━━━━\n\n"
        )
        full_msg = f"{header}{safe_html(setup)}"

        # Pasar por SignalCoordinator antes de enviar
        import signal_coordinator as _sc
        direction_str = "LONG" if is_long else "SHORT"
        _sc.submit("SALMOS", "BTC", direction_str, 0.7, full_msg)
        _sc.resolve_and_send("BTC", send_telegram)
    except Exception as e:
        print(f"❌ Error en profecía de Salmos: {e}")

def main():
    print("🚀 Scalp Alert Bot V3 (AI Panorama) - INICIANDO")
    update_dynamic_levels()
    
    # Control de tiempo para insights horarios y sentinel (V2.0 Focus)
    last_insight_time = time.time()
    last_salmos_time = 0
    last_sentinel_time = 0
    last_zec_sentinel_time = 0
    last_coordinator_cleanup = 0.0
    last_health_check = 0.0
    keyboard = get_main_menu()
    try:
        from config import ANALYSIS_MODE_QUIET as _QUIET
    except Exception:
        _QUIET = False
    if not _QUIET:
        send_telegram("🤖 <b>Scalp Bot Multi-Estrategia Online</b>\n🛡️ V1-TECH: Activa\n🤖 V2-AI: Activa\n📡 Expert Advisor: Escuchando", keyboard=keyboard)
    else:
        print("[Robot] Startup ONLINE msg suprimido — ANALYSIS_MODE_QUIET=True")
    
    while True:
        try:
            import thread_health
            thread_health.heartbeat("scalp_bot")
            prices = get_prices()
            if prices:
                prices = sanitize_dict(prices)
                check_strategies(prices)
                check_market_pulse(prices)
                now = time.time()
                if now - last_coordinator_cleanup > 900:
                    last_coordinator_cleanup = now
                    import signal_coordinator as _sc
                    _sc.cleanup_stale()
                # API health watchdog (cada 30min) — alerta a Telegram si una API
                # crítica (Gemini, data feed) se vence o se cae. Dedup por estado.
                if now - last_health_check > 1800:
                    last_health_check = now
                    try:
                        import api_health
                        api_health.watchdog(send_telegram)
                    except Exception as _e:
                        print(f"⚠️ [api_health] watchdog error: {_e}")
                # monitor_open_trades ya maneja el seguimiento de posiciones
                monitor_open_trades(prices)
                
                # check_user_queries ahora se ejecuta en su propio hilo (run_telegram_worker)
                
                # Insights Horarios: AMBAS PERSONALIDADES (cada 7200 segundos — 2h para reducir costo Gemini)
                now = time.time()
                _hora_panorama = datetime.now().hour
                if now - last_insight_time > 7200 and not (1 <= _hora_panorama < 8):
                    # Audit D (2026-05-23): PANORAMA no accionable. Modo quiet → skip.
                    try:
                        from config import ANALYSIS_MODE_QUIET as _QUIET
                    except Exception:
                        _QUIET = False
                    if _QUIET:
                        last_insight_time = now
                        print("[Robot] PANORAMA suprimido — ANALYSIS_MODE_QUIET=True")
                    # Gate anti-duplicado: si PULSO disparó <10min antes, saltar PANORAMA (mismo análisis AI)
                    elif now - _LAST_MARKET_PULSE_TS < 600:
                        print(f"[Robot] PANORAMA suprimido — PULSO disparó hace {int(now - _LAST_MARKET_PULSE_TS)}s")
                        last_insight_time = now  # avanzar ventana igual para evitar retry inmediato
                    else:
                        # V3.4: Actualizamos el tiempo ANTES para evitar bucles si falla la IA o Telegram
                        last_insight_time = now
                        print("[Robot] Generando panorama horario...")
                        panoramas = gemini_analyzer.get_hourly_panorama(prices)
                        ts_now = datetime.now().strftime("%H:%M")
                        btc_p   = prices.get("BTC", 0)
                        btc_rsi = prices.get("BTC_RSI", 0)
                        tao_p   = prices.get("TAO", 0)
                        tao_rsi = prices.get("TAO_RSI", 0)
                        usdt_d  = prices.get("USDT_D", 0)
                        header = (f"🤖 <b>PANORAMA [{ts_now}]</b>\n"
                                  f"<code>BTC ${btc_p:,.0f} RSI:{btc_rsi:.0f} | TAO ${tao_p:,.2f} RSI:{tao_rsi:.0f} | USDT.D {usdt_d:.2f}%</code>\n"
                                  f"━━━━━━━━━━━━━\n")
                        salmos_p  = panoramas.get('salmos', '')
                        scalper_p = panoramas.get('scalper', '')
                        if salmos_p and scalper_p:
                            panel = f"{salmos_p}\n\n━━━━━━━━━━━━━\n\n{scalper_p}"
                        elif salmos_p:
                            panel = salmos_p
                        else:
                            panel = panoramas.get('conservador', 'Sin datos')
                        send_telegram(f"{header}{safe_html(panel)}")
                
                # --- AUTO-FILL OUTCOMES (cada ciclo — resuelve señales pendientes) ---
                import episode_memory as _ep_mem
                _ep_mem.check_pending_outcomes(prices)

                # --- SALMOS PROPHECY: REMOVIDO en v1.2.0 (duplicaba PANORAMA hourly) ---
                # Para revertir: setear KILL_SALMOS_PROPHECY = False en config.py
                # y descomentar bloque (ver git tag v1.1.0 en gemini_analyzer.py).
                from config import KILL_SALMOS_PROPHECY
                if not KILL_SALMOS_PROPHECY:
                    _hora = datetime.now().hour
                    if now - last_salmos_time > 3600 and not (1 <= _hora < 8):
                        last_salmos_time = now
                        trigger_salmos_prophecy(prices)

                # --- SENTINEL REPORT v1.2.0 (compact + dedupe + score filter) ---
                # Frecuencia 4h (era 2h). Solo si NO hay posición abierta.
                # Score < 4/5 → skip. Mismo (sym, bias) en últimos 90min → skip.
                from config import SENTINEL_INTERVAL_SEC
                if now - last_zec_sentinel_time > SENTINEL_INTERVAL_SEC:
                    last_zec_sentinel_time = now
                    macro = GLOBAL_CACHE["macro_metrics"]
                    import tracker as _tracker
                    import voice_compactor as _vc
                    import runtime_state as _rs
                    _open_syms = {t["symbol"] for t in _tracker.get_open_trades()}
                    _verbose = _rs.is_verbose()
                    # Monitor manual: ZEC siempre, TAO + TON como análisis read-only
                    # (TAO_TRADING_ENABLED controla V3/V4 auto-trades, no el Sentinel)
                    _sentinel_syms = ["ZEC", "TAO", "TON"]
                    for _sym in _sentinel_syms:
                        if _sym in _open_syms:
                            print(f"⏭️ Sentinel {_sym}: Posición abierta — reporte omitido.")
                            continue
                        _p = prices.get(_sym, 0.0)
                        _rsi = prices.get(f"{_sym}_RSI", 50.0)
                        _ema = GLOBAL_CACHE["indicators"].get(_sym, {}).get("ema_200", _p)
                        _atr = prices.get(f"{_sym}_ATR", 0.0)
                        _bb_u = prices.get(f"{_sym}_BB_U", 0.0)
                        _bb_l = prices.get(f"{_sym}_BB_L", 0.0)

                        if _verbose:
                            # Verbose mode (legacy full Cuadrilla output)
                            print(f"🥷 Sentinel {_sym}: VERBOSE mode — full report.")
                            sentinel_report = gemini_analyzer.get_sentinel_report(
                                symbol=_sym, current_price=_p, rsi=_rsi, ema=_ema,
                                usdt_d=prices.get("USDT_D", 8.08),
                                vix=macro.get("vix", 0.0), dxy=macro.get("dxy", 0.0),
                                spy=macro.get("spy", 0.0), nvda=macro.get("nvda", 0.0),
                                pltr=macro.get("pltr", 0.0),
                                atr=_atr, bb_u=_bb_u, bb_l=_bb_l,
                                btc_price=prices.get("BTC", 0.0),
                                gold_price=prices.get("GOLD", 0.0),
                            )
                            _emoji = "🥷" if _sym == "ZEC" else "🏛️"
                            import alert_manager as _am
                            _sentinel_msg = f"{_emoji} <b>SENTINEL REPORT: {_sym}</b>\n\n{safe_html(sentinel_report)}"
                            _am.send_telegram_long(_sentinel_msg)
                            continue

                        # Compact mode (default v1.2.0+)
                        print(f"🥷 Sentinel {_sym}: compact mode — query Gemini JSON.")
                        parsed = gemini_analyzer.get_sentinel_report_compact(
                            symbol=_sym, current_price=_p, rsi=_rsi, ema=_ema,
                            usdt_d=prices.get("USDT_D", 8.08),
                            vix=macro.get("vix", 0.0), dxy=macro.get("dxy", 0.0),
                            spy=macro.get("spy", 0.0), nvda=macro.get("nvda", 0.0),
                            pltr=macro.get("pltr", 0.0),
                            atr=_atr, bb_u=_bb_u, bb_l=_bb_l,
                            btc_price=prices.get("BTC", 0.0),
                            gold_price=prices.get("GOLD", 0.0),
                        )
                        if not parsed:
                            print(f"🔕 Sentinel {_sym}: parse failed, skipping (use /verbose on para forzar texto).")
                            import signal_logger as _slog
                            _slog.log_signal(_sym, "SENTINEL", "ERROR", "parse failed / voices empty",
                                             price=_p, rsi=_rsi)
                            continue

                        _bias = parsed.get("bias", "NEUTRAL")
                        _score = parsed.get("score", 0)
                        # Filtro contradicción RSI vs dirección — evita LONG @ RSI overbought / SHORT @ RSI oversold
                        if _bias == "LONG" and _rsi >= 72.0:
                            print(f"🔕 Sentinel {_sym}: contradicción LONG @ RSI {_rsi:.0f} ≥72 — alerta omitida (esperar pullback).")
                            import signal_logger as _slog
                            _slog.log_signal(_sym, "SENTINEL", "SUPPRESSED", f"LONG contradicción RSI={_rsi:.0f}≥72",
                                             price=_p, rsi=_rsi, bias=_bias, score=_score)
                            continue
                        if _bias == "SHORT" and _rsi <= 28.0:
                            print(f"🔕 Sentinel {_sym}: contradicción SHORT @ RSI {_rsi:.0f} ≤28 — alerta omitida (esperar bounce).")
                            import signal_logger as _slog
                            _slog.log_signal(_sym, "SENTINEL", "SUPPRESSED", f"SHORT contradicción RSI={_rsi:.0f}≤28",
                                             price=_p, rsi=_rsi, bias=_bias, score=_score)
                            continue
                        ok, reason = _vc.should_send_sentinel(_sym, _bias, _score)
                        if not ok:
                            print(f"🔕 Sentinel {_sym}: filtered — {reason}")
                            import signal_logger as _slog
                            _slog.log_signal(_sym, "SENTINEL", "SUPPRESSED", f"voice_compactor: {reason}",
                                             price=_p, rsi=_rsi, bias=_bias, score=_score)
                            continue

                        # Spec 022.6.1 (2026-05-26): inyectar INTEL en el Sentinel.
                        # Sentinel es la strategy real que dispara alertas (V3-Reversal rara
                        # vez se cumple). Sin esto, todo el wire de HMM/CVD/Whale/Social
                        # construido en Specs 009/010/012/013/019 quedaba dormant.
                        _intel_sentinel = {}
                        try:
                            from strategies import _build_extra_intel as _bei
                            _intel_sentinel = _bei(f"{_sym}/USDT") or {}
                        except Exception as _e:
                            print(f"[sentinel intel build skip] {_e}")

                        msg = _vc.render_sentinel_compact(_sym, parsed, _p, _rsi, intel=_intel_sentinel)
                        mid = send_telegram(msg)
                        print(f"✅ Sentinel {_sym}: enviado · {_bias} {_score}/5")
                        import signal_logger as _slog
                        _slog.log_signal(_sym, "SENTINEL", "SENT", f"{_bias} score={_score}/5",
                                         price=_p, rsi=_rsi, bias=_bias, score=_score)

                        # Log al A/B framework (Spec 022) — antes solo V3-Reversal logueaba.
                        try:
                            import tracker as _trk
                            _trk.log_intel_event(
                                alert_id=int(mid) if mid and str(mid).isdigit() else 0,
                                symbol=f"{_sym}/USDT",
                                strategy="sentinel_compact",
                                side=_bias,
                                intel=_intel_sentinel,
                                boost_applied=0.0,
                                boost_reasons=[],
                                conf_score_pre=float(_score),
                                conf_score_post=float(_score),
                                entry=_p, sl=0.0, tp1=0.0,
                                gates_blocked=[],
                            )
                        except Exception as _e:
                            print(f"[sentinel intel_log skip] {_e}")
                
                # --- ALTCOIN SENTINEL: REMOVED 2026-05-09 ---
                # Audit Telegram: ruido sin acción accionable. Duplicaba info de PANORAMA.
                # Si querés narrativas BTC/ETH, usar /intel <SYM> en Telegram (handler activo).

        except Exception as e:
            from logger_core import logger as _logger
            _logger.error("❌ Main Loop Error: %s", e, exc_info=True)
            time.sleep(10) # Backoff de seguridad en fallos de red persistentes
        time.sleep(CHECK_INTERVAL)

def run_telegram_worker():
    """Bucle independiente para responder mensajes de Telegram rápidamente."""
    print("📡 Telegram Worker: Iniciando escucha activa (5s interval)...")
    while True:
        try:
            import thread_health
            thread_health.heartbeat("telegram")
            # get_prices usa caché interna, así que es rápido si los datos son frescos
            prices = get_prices()
            if prices:
                prices = sanitize_dict(prices)
                check_user_queries(prices)
        except Exception as e:
            # Evitar spam en logs si es error de red temporal
            if "Connection" not in str(e):
                from logger_core import logger as _logger
                _logger.error("❌ Telegram Worker Error: %s", e, exc_info=True)
        time.sleep(15) # Telegram poll cada 15s (antes 5s — 17280→5760 calls/día)

if __name__ == "__main__":
    main()
