"""
trade_monitor.py — Monitoreo de trades abiertos (TP1/TP2/SL tracking)

Extraído de scalp_alert_bot.py para mantener archivos < 600 líneas.
"""

import indicators


def monitor_open_trades(prices: dict):
    """Monitorea posiciones abiertas, ejecuta TP/SL automático, y trailing stops."""
    # Lazy imports para evitar circularidad
    from scalp_alert_bot import send_telegram, alert, safe_html
    import tracker
    import gemini_analyzer
    from risk_manager import circuit_breaker, trailing_stop_mgr

    open_trades = tracker.get_open_trades()
    for t in open_trades:
        sym = t["symbol"]
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

        if tipo == "SHORT":
            if curr_p >= t["sl_price"]:
                tracker.update_trade_status(t["id"], "LOST")
                lesson = gemini_analyzer.trigger_shadow_post_mortem(sym, curr_p, "LOST", rsi, "Post-Mortem SL (Short)")
                if lesson:
                    send_telegram(f"🧠 <b>NEURAL LEARNING (V4.0)</b>\n<i>{lesson}</i>", reply_to=reply)
                msg = (f"🔴 <b>STOP LOSS TOCADO (POST-MORTEM)</b>\n\n"
                       f"🪙 {sym} SHORT\n"
                       f"💸 PnL: <b>{(pnl_pct or 0.0):+.2f}%</b>\n"
                       f"📊 <b>Contexto de Cierre:</b>\n"
                       f"• RSI: {(t.get('rsi_entry') or 50.0):.1f} (Inicio) → {(rsi or 0.0):.1f} (Actual)\n"
                       f"• Bollinger: {bb_ctx}\n"
                       f"• Motivo: El precio superó el techo proyectado.")
                alert(f"t_{t['id']}_l", msg, version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "LOST", t["entry_price"], curr_p)
                circuit_breaker.record_outcome(is_win=False, pnl_pct=-abs(pnl_pct))
            elif t["tp2_price"] > 0 and curr_p <= t["tp2_price"]:
                tracker.update_trade_status(t["id"], "FULL_WON")
                msg = (f"🟢 <b>TP2 ALCANZADO (STRIKE!)</b>\n\n"
                       f"🪙 {sym} SHORT\n"
                       f"💰 PnL: <b>{(pnl_pct or 0.0):+.2f}%</b>\n"
                       f"📊 <b>Resumen:</b>\n"
                       f"• RSI Entrada: {(t.get('rsi_entry') or 50.0):.1f}\n"
                       f"• RSI Cierre: {(rsi or 0.0):.1f}\n"
                       f"✨ El indicador predijo el retroceso correctamente.")
                alert(f"t_{t['id']}_w", msg, version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "WIN_FULL", t["entry_price"], curr_p)
                circuit_breaker.record_outcome(is_win=True, pnl_pct=abs(pnl_pct))
            elif t["tp1_price"] > 0 and curr_p <= t["tp1_price"] and t["status"] == "OPEN":
                tracker.update_trade_status(t["id"], "PARTIAL_WON")
                new_sl = round(t["entry_price"] * 0.999, 2)
                tracker.update_sl(t["id"], new_sl)
                alert(f"t_{t['id']}_p", f"🟡 <b>TP1 ASEGURADO</b>\nTrailing BE (0.1%) Activado. Riesgo eliminado.", version=t["version"], reply_to=reply)
                circuit_breaker.record_outcome(is_win=True, pnl_pct=abs(pnl_pct) * 0.5)
        elif tipo == "LONG":
            if curr_p <= t["sl_price"]:
                tracker.update_trade_status(t["id"], "LOST")
                lesson = gemini_analyzer.trigger_shadow_post_mortem(sym, curr_p, "LOST", rsi, "Post-Mortem SL (Long)")
                if lesson:
                    send_telegram(f"🧠 <b>NEURAL LEARNING (V4.0)</b>\n<i>{lesson}</i>", reply_to=reply)
                msg = (f"🔴 <b>STOP LOSS TOCADO (POST-MORTEM)</b>\n\n"
                       f"🪙 {sym} LONG\n"
                       f"💸 PnL: <b>{(pnl_pct or 0.0):+.2f}%</b>\n"
                       f"📊 <b>Contexto de Cierre:</b>\n"
                       f"• RSI: {(t.get('rsi_entry') or 50.0):.1f} (Inicio) → {(rsi or 0.0):.1f} (Actual)\n"
                       f"• Bollinger: {bb_ctx}\n"
                       f"• Motivo: Soporte perforado, el impulso falló.")
                alert(f"t_{t['id']}_l", msg, version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "LOST", t["entry_price"], curr_p)
                circuit_breaker.record_outcome(is_win=False, pnl_pct=-abs(pnl_pct))
            elif t["tp2_price"] > 0 and curr_p >= t["tp2_price"]:
                tracker.update_trade_status(t["id"], "FULL_WON")
                msg = (f"🟢 <b>TP2 ALCANZADO (STRIKE!)</b>\n\n"
                       f"🪙 {sym} LONG\n"
                       f"💰 PnL: <b>{(pnl_pct or 0.0):+.2f}%</b>\n"
                       f"📊 <b>Resumen:</b>\n"
                       f"• RSI Entrada: {(t.get('rsi_entry') or 50.0):.1f}\n"
                       f"• RSI Cierre: {(rsi or 0.0):.1f}\n"
                       f"✨ Rebote técnico capturado con éxito.")
                alert(f"t_{t['id']}_w", msg, version=t["version"], reply_to=reply)
                gemini_analyzer.log_result_to_context(sym, "WIN_FULL", t["entry_price"], curr_p)
                circuit_breaker.record_outcome(is_win=True, pnl_pct=abs(pnl_pct))
            elif t["tp1_price"] > 0 and curr_p >= t["tp1_price"] and t["status"] == "OPEN":
                tracker.update_trade_status(t["id"], "PARTIAL_WON")
                new_sl = round(t["entry_price"] * 1.001, 2)
                tracker.update_sl(t["id"], new_sl)
                alert(f"t_{t['id']}_p", f"🚀 <b>TP1 ASEGURADO</b>\nTrailing BE (0.1%) Activado. Fondos protegidos.", version=t["version"], reply_to=reply)
                circuit_breaker.record_outcome(is_win=True, pnl_pct=abs(pnl_pct) * 0.5)

    # ── Trailing Stop Updates ────────────────────────────────────────────
    tsl_updates = trailing_stop_mgr.calculate_trailing_updates(open_trades, prices)
    for upd in tsl_updates:
        tracker.update_sl(upd["trade_id"], upd["new_sl"])
        print(f"📐 [TrailingStop] {upd['reason']}")
        alert(f"tsl_{upd['trade_id']}",
              f"📐 <b>TRAILING STOP ACTUALIZADO</b>\n"
              f"🪙 {upd['symbol']} {upd['side']}\n"
              f"🛑 SL: ${upd['old_sl']:,.2f} → <b>${upd['new_sl']:,.2f}</b>\n"
              f"📊 Precio: ${upd['current_price']:,.2f} | ATR: {upd['atr']:.2f}",
              version="RISK", cooldown=120)

    # Cleanup trailing tracking para trades cerrados
    open_ids = {t["id"] for t in open_trades}
    trailing_stop_mgr.cleanup_closed(open_ids)
