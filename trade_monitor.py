"""
trade_monitor.py — Monitoreo de trades abiertos (TP1/TP2/SL tracking)

Extraído de scalp_alert_bot.py para mantener archivos < 600 líneas.
"""

import config
import indicators
import episode_memory as _em
from datetime import datetime

# SWING trades open > 36h without hitting TP1 = signal failed; close at market
SWING_TIME_EXIT_HOURS = 36
# GLOBAL_CACHE importado lazy dentro de monitor_open_trades para evitar circularidad


def _leg_pnl_pct(entry: float, exit_p: float, side: str) -> float:
    """PnL % de una pata, con el signo correcto segun el lado."""
    if not entry:
        return 0.0
    return ((exit_p - entry) / entry * 100) if side == "LONG" else ((entry - exit_p) / entry * 100)


def blended_pnl_pct(t: dict, exit_price: float) -> float:
    """PnL % real de un trade que ya tomo parcial en TP1.

    Un trade con partial_pct=50 que vuelve al BE NO perdio 1R: cerro la mitad en
    TP1 y la otra mitad plana. Antes de esto el cierre se guardaba como LOST con
    el PnL de la pata que quedaba, que es la mitad de la historia.

        blended = w * pnl(TP1) + (1-w) * pnl(salida)      con w = partial_pct/100

    Sin parcial (w=0) devuelve el PnL de la salida — mismo numero de siempre.
    """
    w = (t.get("partial_pct") or 0) / 100.0
    side = t["type"]
    entry = t["entry_price"]
    exit_leg = _leg_pnl_pct(entry, exit_price, side)
    if w <= 0:
        return exit_leg
    tp1_leg = _leg_pnl_pct(entry, t["tp1_price"], side)
    return w * tp1_leg + (1 - w) * exit_leg


def sync_exchange_stop(trade: dict, new_sl: float, alert_fn=None) -> dict:
    """Mueve el stop en Binance para que coincida con el que acaba de escribirse en la DB.

    Guarda de PROPIEDAD: solo corre si la fila trae `exchange_order_id`, que solo se
    setea cuando el bracket LIVE puso ordenes de verdad. SWING, manual, stocks y SIM
    no lo traen y se saltan — el bot no tiene ordenes suyas ahi y no debe inventarlas.

    Nunca lanza. Si el stop queda descubierto (se cancelo el viejo y no entro el
    nuevo) manda alerta, porque ese estado no se puede quedar callado.
    """
    if not trade.get("exchange_order_id"):
        return {"status": "SKIPPED_NOT_OWNED"}
    import os
    if os.getenv("EXECUTION_MODE", "PAPER") != "LIVE":
        return {"status": "SKIPPED_PAPER"}

    try:
        from scalp_alert_bot import GLOBAL_CACHE
        import trading_executor
        if not GLOBAL_CACHE.get("executor"):
            GLOBAL_CACHE["executor"] = trading_executor.ZenithExecutor()
        res = GLOBAL_CACHE["executor"].sync_stop_loss(trade["symbol"], trade["type"], new_sl)
    except Exception as e:
        print(f"❌ [SL Sync] {trade.get('symbol')}: {e}")
        res = {"status": "FAILED", "reason": str(e)}

    if res.get("unprotected") and alert_fn:
        try:
            alert_fn(f"slsync_{trade['id']}",
                     f"🚨 <b>POSICION SIN STOP</b>: {trade['symbol']} {trade['type']}\n"
                     f"Se cancelo el stop viejo y el nuevo (${new_sl}) NO entro.\n"
                     f"<i>{res.get('reason')}</i>\n"
                     f"Revisar en Binance A MANO.",
                     version="RISK")
        except Exception:
            pass
    return res


def monitor_open_trades(prices: dict):
    """Monitorea posiciones abiertas, ejecuta TP/SL automático, y trailing stops."""
    # Lazy imports para evitar circularidad
    from scalp_alert_bot import send_telegram, alert, safe_html, GLOBAL_CACHE
    import tracker
    import gemini_analyzer
    from risk_manager import circuit_breaker, trailing_stop_mgr

    open_trades = tracker.get_open_trades()
    for t in open_trades:
        sym = t["symbol"]
        # COMMODITY trades use yfinance futures prices (GC=F, CLM26) — not the
        # crypto price cache.  commodities_bot.py handles its own SL/TP checks.
        if t.get("version") == "COMMODITY":
            continue
        if sym not in prices:
            continue
        curr_p, tipo, reply = prices[sym], t["type"], t["msg_id"]
        rsi = prices.get(f"{sym}_RSI", 50.0)
        bb_u = prices.get(f"{sym}_BB_U", curr_p * 1.01)
        bb_l = prices.get(f"{sym}_BB_L", curr_p * 0.99)
        bb_ctx = "🔝 Techo BB" if curr_p >= bb_u * 0.99 else "🩸 Suelo BB" if curr_p <= bb_l * 1.01 else "↕️ Rango"

        # Calcular PnL flotante
        entry = t["entry_price"]
        if tipo == "LONG":
            pnl_pct = ((curr_p - entry) / entry * 100) if entry else 0.0
        else:
            pnl_pct = ((entry - curr_p) / entry * 100) if entry else 0.0

        # V5.1: High-Fidelity Intel (RVOL & ATR Trailing SL)
        df_1h = indicators.get_df(sym, '1h', 50)
        rvol = indicators.calculate_rvol(df_1h)
        atr = indicators.calculate_atr(df_1h)
        tsl = indicators.calculate_atr_trailing_stop(curr_p, atr, side=tipo, multiplier=2.5)

        # V5.0: Log PNL to console for pure trading monitor
        if abs(pnl_pct) > 1.0:
            print(f"📈 [Trade Monitor] {sym} {tipo}: {pnl_pct:+.2f}% | RVOL: {rvol} | TSL: {tsl}")

        # Templates consolidados (ronda 5 Telegram cleanup)
        # Antes: 8 mensajes distintos (4×SHORT + 4×LONG con texto único c/u)
        # Ahora: 3 templates universales (SL / TP1 / TP2) que usan side dinámico
        is_sl = (tipo == "SHORT" and curr_p >= t["sl_price"]) or \
                (tipo == "LONG"  and curr_p <= t["sl_price"])
        is_tp2 = t["tp2_price"] > 0 and (
            (tipo == "SHORT" and curr_p <= t["tp2_price"]) or
            (tipo == "LONG"  and curr_p >= t["tp2_price"]))
        is_tp1 = t["tp1_price"] > 0 and t["status"] == "OPEN" and (
            (tipo == "SHORT" and curr_p <= t["tp1_price"]) or
            (tipo == "LONG"  and curr_p >= t["tp1_price"]))

        if is_sl:
            # Si ya se tomo parcial en TP1, esto NO es una perdida de riesgo
            # completo: es el cierre del runner. El resultado del trade es la
            # mezcla de las dos patas, no la ultima.
            took_partial = (t.get("partial_pct") or 0) > 0
            real_pnl = blended_pnl_pct(t, curr_p)
            status = "PARTIAL_CLOSED" if took_partial else "LOST"

            tracker.update_trade_status(t["id"], status)
            _ep_id = GLOBAL_CACHE.get("episode_ids", {}).pop(t["id"], None)
            if _ep_id:
                _em.fill_outcome(_ep_id, "WIN" if real_pnl > 0 else "LOSS", real_pnl)

            if took_partial:
                msg = (f"🟡 <b>RUNNER CERRADO</b>: {sym} {tipo} · <b>{real_pnl:+.2f}%</b>\n"
                       f"{t.get('partial_pct')}% tomado en TP1 ${t['tp1_price']:.4f} · "
                       f"resto salio en ${curr_p:.4f}\n"
                       f"Entry ${t['entry_price']:.4f}")
            else:
                msg = (f"🔴 <b>SL HIT</b>: {sym} {tipo} · <b>{real_pnl:+.2f}%</b>\n"
                       f"Entry ${t['entry_price']:.4f} → Now ${curr_p:.4f}")
            alert(f"t_{t['id']}_l", msg, version=t["version"], reply_to=reply)
            gemini_analyzer.log_result_to_context(sym, status, t["entry_price"], curr_p)
            circuit_breaker.record_outcome(is_win=real_pnl > 0, pnl_pct=real_pnl)
        elif is_tp2:
            # Mezclado: si hubo parcial en TP1, la mitad cerro ahi y la otra aqui.
            _tp2_pnl = blended_pnl_pct(t, curr_p)
            tracker.update_trade_status(t["id"], "FULL_WON")
            _ep_id = GLOBAL_CACHE.get("episode_ids", {}).pop(t["id"], None)
            if _ep_id: _em.fill_outcome(_ep_id, "WIN", _tp2_pnl)
            msg = (f"🟢 <b>TP2 HIT</b>: {sym} {tipo} · <b>{_tp2_pnl:+.2f}%</b>\n"
                   f"Entry ${t['entry_price']:.4f} → Now ${curr_p:.4f}")
            alert(f"t_{t['id']}_w", msg, version=t["version"], reply_to=reply)
            gemini_analyzer.log_result_to_context(sym, "WIN_FULL", t["entry_price"], curr_p)
            circuit_breaker.record_outcome(is_win=True, pnl_pct=_tp2_pnl)
        elif is_tp1:
            # Scale-out en TP1. Hasta ahora el bot movia el SL a BE pero dejaba el
            # 100% puesto: si el precio regresaba, el trade salia en 0 y se
            # guardaba LOST. El backtester en cambio cierra 50% aqui
            # (backtest_sim.py:136-150) — de ahi venia la brecha entre el sim en
            # verde y el feed de Telegram en rojo.
            #
            # NO se manda ninguna orden desde aqui. En LIVE el bracket ya dejo una
            # limit reduceOnly de amount*0.5 en TP1 (trading_executor.py:130-134):
            # el exchange ya venia cerrando la mitad. Esto solo pone la DB de
            # acuerdo con lo que pasa afuera. Mandar una orden aqui seria cerrar
            # el runner dos veces.
            _pct = getattr(config, "PARTIAL_TP1_PCT", 50)
            be_offset = 0.999 if tipo == "SHORT" else 1.001
            new_sl = round(t["entry_price"] * be_offset, 6)

            tracker.update_trade_status(t["id"], "PARTIAL_WON")  # sincroniza intel_outcomes
            tracker.mark_partial(t["id"], _pct)                   # partial_pct = 50
            tracker.mark_be(t["id"], sl_price=new_sl)             # be_moved = 1 + SL al BE
            sync_exchange_stop(t, new_sl, alert_fn=alert)          # y el stop real en Binance
            tracker.append_event(
                t["id"],
                f"PARTIAL {_pct}% @ TP1 ${t['tp1_price']:.4f} ({pnl_pct:+.2f}%) · SL→BE ${new_sl:.4f}")

            alert(f"t_{t['id']}_p",
                  f"🟡 <b>TP1 HIT</b>: {sym} {tipo} · <b>{_pct}% cerrado</b> "
                  f"({pnl_pct:+.2f}%)\n"
                  f"Resto corre a TP2 ${t['tp2_price']:.4f} · SL en BE ${new_sl:.4f}",
                  version=t["version"], reply_to=reply)
            circuit_breaker.record_outcome(is_win=True, pnl_pct=abs(pnl_pct) * _pct / 100.0)

    # ── Time-Based Exit (SWING only) ───────────────────────────────────
    # Data shows losing SWING trades stay open ~40h; winners close in ~19h.
    # If a SWING hasn't hit TP1 after 36h, the thesis is invalidated — close it.
    now_dt = datetime.now()
    for t in open_trades:
        if t.get("version") != "SWING":
            continue
        if t["status"] != "OPEN":  # PARTIAL_WON already hit TP1 — let it run
            continue
        try:
            open_dt = datetime.strptime(t.get("open_time", ""), "%Y-%m-%d %H:%M:%S")
            age_h = (now_dt - open_dt).total_seconds() / 3600
        except Exception:
            continue
        if age_h < SWING_TIME_EXIT_HOURS:
            continue

        sym = t["symbol"]
        if sym not in prices:
            continue
        curr_p = prices[sym]
        entry = t["entry_price"]
        tipo = t["type"]
        pnl_pct = ((curr_p - entry) / entry * 100) if tipo == "LONG" else ((entry - curr_p) / entry * 100)

        tracker.update_trade_status(t["id"], "LOST")
        alert(
            f"t_{t['id']}_timeout",
            f"⏱️ <b>CIERRE POR TIEMPO: {sym} {tipo}</b>\n"
            f"Trade SWING sin TP1 después de {age_h:.0f}h (umbral: {SWING_TIME_EXIT_HOURS}h)\n"
            f"📥 Entrada: ${entry:,.2f} | Precio actual: ${curr_p:,.2f}\n"
            f"💸 PnL: <b>{pnl_pct:+.2f}%</b>\n"
            f"<i>Tesis invalidada — capital liberado.</i>",
            version=t.get("version", "SWING")
        )
        circuit_breaker.record_outcome(is_win=False, pnl_pct=-abs(pnl_pct))
        print(f"⏱️ [TimeExit] {sym} {tipo} cerrado por tiempo ({age_h:.0f}h) — PnL: {pnl_pct:+.2f}%")

    # ── Trailing Stop Updates ────────────────────────────────────────────
    tsl_updates = trailing_stop_mgr.calculate_trailing_updates(open_trades, prices)
    _by_id = {t["id"]: t for t in open_trades}
    for upd in tsl_updates:
        tracker.update_sl(upd["trade_id"], upd["new_sl"])
        _t = _by_id.get(upd["trade_id"])
        if _t:
            sync_exchange_stop(_t, upd["new_sl"], alert_fn=alert)
        print(f"📐 [TrailingStop] {upd['reason']}")
        # Key por trade_id — el cooldown=300s evita spam; new_sl no va en la key
        # porque oscilaciones de precio generan keys distintas y bypassean el cooldown
        tsl_key = f"tsl_{upd['trade_id']}"
        alert(tsl_key,
              f"📐 <b>TRAILING STOP ACTUALIZADO</b>\n"
              f"🪙 {upd['symbol']} {upd['side']}\n"
              f"🛑 SL: ${upd['old_sl']:,.2f} → <b>${upd['new_sl']:,.2f}</b>\n"
              f"📊 Precio: ${upd['current_price']:,.2f} | ATR: {upd['atr']:.2f}",
              version="RISK", cooldown=900)  # 15min cooldown (era 5min — Audit Telegram redujo spam)

    # Cleanup trailing tracking para trades cerrados
    open_ids = {t["id"] for t in open_trades}
    trailing_stop_mgr.cleanup_closed(open_ids)
