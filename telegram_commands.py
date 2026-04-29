"""
telegram_commands.py — Dispatcher de comandos de Telegram

Extrae check_user_queries de scalp_alert_bot.py para reducir tamaño.
Usa lazy imports para evitar circularidad con scalp_alert_bot.
"""

import os
import requests
from datetime import datetime
import tracker
import gemini_analyzer
import social_analyzer
import json

def _download_telegram_file(file_id: str, dest_path: str) -> bool:
    """Download a file from Telegram given its file_id and save to dest_path."""
    try:
        # Get file path from Telegram API
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile"
        resp = requests.get(url, params={"file_id": file_id}, timeout=5)
        data = resp.json()
        if not data.get("ok"):
            print(f"❌ Telegram getFile error: {data.get('description')}")
            return False
        file_path = data["result"]["file_path"]
        # Download actual file content
        dl_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        r = requests.get(dl_url, stream=True, timeout=10)
        if r.status_code == 200:
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        print(f"❌ Failed to download file {file_id}")
        return False
    except Exception as e:
        print(f"❌ Error downloading telegram file: {e}")
        return False

def _update_levels_json(symbol: str, timeframe: str, image_path: str) -> None:
    """Add or update an entry in chart_ideas/levels_2026-04-02.json."""
    levels_file = "chart_ideas/levels_2026-04-02.json"
    entry = {
        "symbol": symbol.upper(),
        "timeframe": timeframe.lower(),
        "levels": {},
        "notes": "Added via Telegram /add_chart command.",
        "image_path": image_path,
    }
    try:
        if os.path.exists(levels_file):
            with open(levels_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"levels": []}
        # Remove existing entry for same symbol+timeframe
        data["levels"] = [e for e in data.get("levels", []) if not (e.get("symbol") == entry["symbol"] and e.get("timeframe") == entry["timeframe"])]
        data["levels"].append(entry)
        with open(levels_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Levels JSON updated for {symbol} {timeframe}")
    except Exception as e:
        print(f"❌ Error updating levels JSON: {e}")

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OFFSET_FILE      = "last_update_id.txt"


def check_user_queries(prices: dict):
    """Escucha comandos del usuario en Telegram para modo interactivo."""
    # Lazy imports para evitar circularidad
    from scalp_alert_bot import (
        send_telegram, safe_html, get_main_menu,
        _handle_callback, _handle_user_question
    )

    offset = 0
    if os.path.exists(OFFSET_FILE):
        try:
            with open(OFFSET_FILE, "r") as f:
                offset = int(f.read().strip())
        except Exception as e:
            print(f"⚠️ Error leyendo offset: {e}")
            offset = 0

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset + 1, "timeout": 1}

    try:
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        if not data.get("ok"):
            print(f"❌ Telegram API error: {data.get('description', 'unknown')}")
            return

        for update in data.get("result", []):
            try:
                last_id = update["update_id"]
                with open(OFFSET_FILE, "w") as f:
                    f.write(str(last_id))

                if "callback_query" in update:
                    _handle_callback(update["callback_query"], prices)
                    continue

                msg_obj = update.get("message", {})
                text    = msg_obj.get("text") or msg_obj.get("caption", "")
                text    = text.strip()
                chat_id = str(msg_obj.get("chat", {}).get("id", ""))

                if chat_id != str(TELEGRAM_CHAT_ID):
                    print(f"⚠️ Acceso no autorizado: {chat_id}")
                    continue

                if "photo" in msg_obj and "/add_chart" in text:
                    # Expected caption: /add_chart SYMBOL TIMEFRAME
                    parts = text.split()
                    if len(parts) >= 3:
                        sym = parts[1].upper()
                        tf = parts[2].lower()
                        dest_path = f"chart_ideas/assets/image_{sym.lower()}_{tf}.png"
                        if _download_telegram_file(msg_obj["photo"][-1]["file_id"], dest_path):
                            _update_levels_json(sym, tf, dest_path)
                            send_telegram(f"✅ Imagen guardada para {sym} {tf}.")
                        else:
                            send_telegram("❌ Error al descargar la imagen.")
                    else:
                        send_telegram("⚠️ Uso: /add_chart SYMBOL TIMEFRAME en la descripción de la foto.")
                    continue

                if "photo" in msg_obj and ("/bitlobo" in text or not text):
                    # /bitlobo SYMBOL TIMEFRAME  — o foto sin caption (BitLobo analiza igual)
                    import bitlobo_agent
                    parts = text.split()
                    sym = parts[1].upper() if len(parts) >= 2 else "CHART"
                    tf  = parts[2].upper() if len(parts) >= 3 else "4H"
                    send_telegram(f"🐺 <b>BitLobo analizando {sym} {tf}...</b>")
                    # Descargar imagen
                    tmp_path = f"chart_ideas/assets/image_{sym.lower()}_{tf.lower()}_tmp.png"
                    if _download_telegram_file(msg_obj["photo"][-1]["file_id"], tmp_path):
                        with open(tmp_path, "rb") as f:
                            img_bytes = f.read()
                        result = bitlobo_agent.save_and_analyze(img_bytes, sym, tf)
                        send_telegram(safe_html(result))
                    else:
                        send_telegram("🐺 BitLobo: No pude descargar la imagen.")
                    continue
                
                if not text and "photo" not in msg_obj:
                    continue

                t = text.lower()

                if "setup" in t or text.startswith("/setup"):
                    send_telegram("🔍 <b>Escaneando BTC, TAO, ZEC para el mejor setup...</b>")
                    send_telegram(safe_html(gemini_analyzer.get_top_setup(prices)))

                elif "macro" in t or text.startswith("/macro"):
                    send_telegram("🛡️ <b>Analizando Dominancia USDT y liquidez...</b>")
                    ctx = ""
                    try:
                        with open("latest_report.txt") as f: ctx = f.read()
                    except: pass
                    send_telegram(safe_html(gemini_analyzer.get_macro_shield(prices, ctx)))

                elif "pnl" in t or text.startswith("/pnl"):
                    s = tracker.get_daily_pnl()
                    send_telegram(
                        f"🏦 <b>PNL HOY</b>\n\n"
                        f"✅ Ganados: <b>{s['wins']}</b>  🔴 Perdidos: <b>{s['losses']}</b>\n"
                        f"⚖️ Win Rate: <b>{s['win_rate']:.1f}%</b>"
                    )

                elif "acciones" in t or text.startswith("/stocks"):
                    send_telegram("⏳ Obteniendo radar de acciones con Yahoo Finance...")
                    import stock_analyzer
                    send_telegram(stock_analyzer.check_stock_status())

                elif text.startswith("/bitlobo"):
                    # /bitlobo SYMBOL [TIMEFRAME] — opinión de BitLobo sin imagen
                    import bitlobo_agent
                    from config import STOCK_WATCHLIST
                    parts = text.split()
                    if len(parts) >= 2:
                        sym = parts[1].upper()
                        tf  = parts[2].upper() if len(parts) >= 3 else "4H"
                        # Buscar en watchlist para datos de niveles
                        wl = {s["ticker"]: s for s in STOCK_WATCHLIST}
                        sig = wl.get(sym, {})
                        send_telegram(f"🐺 <b>BitLobo evaluando {sym} ({tf})...</b>")
                        opinion = bitlobo_agent.get_opinion(
                            symbol=sym,
                            direction=sig.get("direction", "LONG"),
                            price=0.0,
                            entry=sig.get("entry"),
                            sl=sig.get("stop_loss"),
                            tp1=sig.get("take_profit_1"),
                            context_note=sig.get("context", ""),
                        )
                        send_telegram(safe_html(f"🐺 <b>BitLobo — {sym}</b>\n\n{opinion}"))
                    else:
                        send_telegram("🐺 Uso: /bitlobo SYMBOL [TIMEFRAME]\nEj: /bitlobo CRCL 4H\nO manda una foto con caption /bitlobo CRCL 4H")

                elif "intel" in t or "social" in t or text.startswith("/intel"):
                    sym = "ZEC" if "ZEC" in text.upper() else "TAO" if "TAO" in text.upper() else "BTC"
                    send_telegram(f"🐦 <b>Escaneando X y News para {sym}...</b>")
                    send_telegram(safe_html(social_analyzer.get_social_intel(sym, current_price=prices.get(sym, 0.0))))

                elif "mercado" in t or text.startswith("/status"):
                    sentiment = gemini_analyzer.get_market_sentiment(prices)
                    # Detectar bias y asignar emoji
                    bias_raw = sentiment.get("bias", "NEUTRAL")
                    bias_text = bias_raw.split()[0] if bias_raw else "NEUTRAL"  # Extract "BULLISH" from "BULLISH 🐂"
                    emoji = "🟢" if "BULLISH" in bias_text else "🔴" if "BEARISH" in bias_text else "🟡"
                    msg = f"📊 <b>MERCADO</b> {emoji} — {sentiment['bias']}\n\n"
                    for s in ["SOL", "BTC", "TAO", "ZEC"]:
                        msg += f"• <b>{s}</b>: ${prices.get(s,0):,.2f} | RSI {prices.get(f'{s}_RSI',0):.1f}\n"
                    msg += f"\n🎩 Genesis: \"{sentiment.get('genesis', 'N/A')}\"\n"
                    msg += f"⚡ Exodo: \"{sentiment.get('exodo', 'N/A')}\"\n"
                    msg += f"🌊 Salmos: \"{sentiment.get('salmos', 'N/A')}\""
                    send_telegram(msg, keyboard=get_main_menu())

                elif text.startswith("/audit") or "Auditoría" in text:
                    m = tracker.get_audit_metrics()
                    if m["total_trades"] == 0:
                        audit_msg = "🏛️ <b>AUDITORÍA ZENITH</b>\n\n📈 Nueva era. Sin trades aún.\n🎯 <i>Objetivo: Profit Factor > 1.75</i>"
                    else:
                        audit_msg = (
                            f"🏛️ <b>AUDITORÍA ZENITH</b>\n\n"
                            f"• Trades: <b>{m['total_trades']}</b>  Wins: <b>{m['wins']}</b>  Losses: <b>{m['losses']}</b>\n"
                            f"• Win Rate: <b>{m['win_rate']}</b>  Profit Factor: <b>{m['profit_factor']}</b>\n"
                            f"• Status: <b>{m['status']}</b>"
                        )
                    send_telegram(audit_msg, keyboard=get_main_menu())

                elif "LONG" in text or "SHORT" in text:
                    clean = text.replace("/", "").upper()
                    sym   = next((s for s in ["SOL", "BTC", "TAO", "ZEC"] if s in clean), None)
                    if sym:
                        side = "LONG" if "LONG" in clean else "SHORT"
                        p    = prices.get(sym) or 0.0
                        atr  = prices.get(f"{sym}_ATR") or p * 0.01
                        last = tracker.get_last_open_trade(sym)
                        if last:
                            pnl = ((p - last["entry_price"]) / last["entry_price"]) * 100
                            if last["type"] == "SHORT": pnl = -pnl
                            tracker.update_trade_status(last["id"], "WON" if pnl > 0 else "LOST")
                            send_telegram(f"🔄 Cerrando {sym} {last['type']} previo (PnL: {pnl:+.2f}%)", reply_to=last["msg_id"])
                        sl_d = max(atr * 1.5, p * 0.005)
                        sl   = round(p - sl_d if side == "LONG" else p + sl_d, 2)
                        tp1  = round(p + sl_d * 2.0 if side == "LONG" else p - sl_d * 2.0, 2)
                        tp2  = round(p + sl_d * 3.5 if side == "LONG" else p - sl_d * 3.5, 2)
                        if p > 0:
                            mid = send_telegram(
                                f"🚀 <b>{sym} {side} MANUAL</b>\nEntrada: ${p:,.2f}\n"
                                f"🎯 TP1: <b>${tp1:,.2f}</b> | TP2: <b>${tp2:,.2f}</b>\n🛑 SL: <b>${sl:,.2f}</b>",
                                keyboard=get_main_menu(sym)
                            )
                            tracker.log_trade(sym, side, p, tp1, tp2, sl, mid, version="MANUAL", rsi=prices.get(f"{sym}_RSI", 50))
                        else:
                            send_telegram(f"❌ No se pudo obtener precio de {sym}.")
                    else:
                        send_telegram("❌ Símbolo no reconocido. Usa BTC/SOL/TAO/ZEC.")

                elif "CERRAR " in text or "CLOSE " in text or text.startswith("/close "):
                    from config import SYMBOLS as _all_syms
                    clean = text.replace("/", "").upper()
                    sym   = next((s for s in _all_syms if s in clean), None)
                    if sym:
                        last = tracker.get_last_open_trade(sym)
                        if last:
                            p = prices.get(sym) or 0.0
                            if p > 0:
                                pnl = ((p - last["entry_price"]) / last["entry_price"]) * 100
                                if last["type"] == "SHORT": pnl = -pnl
                                tracker.update_trade_status(last["id"], "FULL_WON" if pnl > 0 else "LOST")
                                send_telegram(
                                    f"🏁 <b>CERRADO {sym}</b> {last['type']}\n"
                                    f"${last['entry_price']:,.2f} → ${p:,.2f}  PnL: <b>{pnl:+.2f}%</b>",
                                    reply_to=last["msg_id"], keyboard=get_main_menu(sym)
                                )
                            else:
                                send_telegram(f"❌ No hay precio de {sym}.")
                        else:
                            send_telegram(f"⚠️ Sin posición abierta en {sym}.", keyboard=get_main_menu(sym))
                    else:
                        send_telegram("❌ Símbolo no reconocido.")

                elif "winrate" in t or text.startswith("/winrate"):
                    import episode_memory as _em
                    days = 30
                    parts = text.split()
                    if len(parts) > 1 and parts[-1].isdigit():
                        days = int(parts[-1])
                    send_telegram(_em.format_winrate_telegram(days), keyboard=get_main_menu())

                elif "budget" in t or text.startswith("/budget"):
                    import ai_budget
                    send_telegram(
                        ai_budget.get_budget_summary_html() + f"\n\n<i>{datetime.now().strftime('%H:%M:%S')}</i>",
                        keyboard=get_main_menu()
                    )

                elif text.startswith("/circuit"):
                    import risk_manager
                    send_telegram(
                        risk_manager.circuit_breaker.get_status_html(),
                        keyboard=get_main_menu()
                    )

                elif text.startswith("/risk"):
                    import risk_manager
                    # Obtener datos del primer símbolo activo para mostrar risk actual
                    _sym = "TAO"
                    _atr = prices.get(f"{_sym}_ATR", 0.0)
                    _price = prices.get(_sym, 0.0)
                    _vix = prices.get("VIX", 0.0)
                    _, _, cb_mult = risk_manager.circuit_breaker.can_trade()
                    send_telegram(
                        risk_manager.get_risk_summary_html(_atr, _price, _vix, "SWING", cb_mult),
                        keyboard=get_main_menu()
                    )

                elif text.startswith("/circuit_reset"):
                    import risk_manager
                    risk_manager.circuit_breaker.force_reset()
                    send_telegram(
                        "🔄 <b>Circuit Breaker reseteado manualmente.</b>\nEstado: NORMAL",
                        keyboard=get_main_menu()
                    )

                elif "flow" in t or text.startswith("/flow"):
                    send_telegram(
                        "🔀 <b>FLUJO ZENITH</b>\n\n"
                        "① APIs: Binance · yfinance · CoinGecko\n"
                        "② Indicadores: RSI · BB · EMA200 · ATR\n"
                        "③ Filtros: V1-TECH · V3 Reversal · V2-AI\n"
                        "④ Score Confluencia: 0-6 pts\n"
                        "⑤ Agentes: Claude Haiku + Gemini Flash (Bull/Bear/Quant/Macro)\n"
                        "⑥ Alertas Telegram con inline buttons\n"
                        "⑦ Tracker: trades + trigger_conditions en SQLite\n\n"
                        "💰 <code>/budget</code>  📊 <code>/agents</code>",
                        keyboard=get_main_menu()
                    )

                elif "agents" in t or text.startswith("/agents"):
                    agent_map = {
                        "CONSERVADOR": "🎩 Genesis",
                        "SCALPER": "⚡ Exodo",
                        "SHADOW": "🥷 Shadow",
                        "SALMOS": "🔔 Salmos",
                        "APOCALIPSIS": "💀 Apocalipsis",
                    }
                    msg = "<b>🏛️ Cuadrante Zenith — Historial de Agentes</b>\n\n"
                    for persona, label in agent_map.items():
                        acc   = gemini_analyzer._load_agent_accuracy(persona)
                        total = acc.get("correct", 0) + acc.get("incorrect", 0)
                        if total == 0:
                            msg += f"• {label}: Sin data\n"
                        else:
                            wr = round(acc["correct"] / total * 100, 1)
                            streak = acc.get("streak", 0)
                            hot = " 🔥" if streak >= 3 else ""
                            msg += f"• {label}: {acc['correct']}/{total} ({wr}%){hot}\n"
                    # Memoria neural
                    neural = gemini_analyzer.get_neural_memory()
                    if neural:
                        msg += f"\n🧠 <b>Memoria Neural:</b>\n<i>{neural[:300]}</i>"
                    msg += "\n\n💡 <code>/correct [Genesis|Exodo|Shadow|Salmos|Apocalipsis]</code>"
                    send_telegram(msg, keyboard=get_main_menu())

                elif text.lower().startswith("/correct "):
                    raw = text.replace("/correct ", "").strip().upper()
                    name_map = {"GENESIS": "CONSERVADOR", "EXODO": "SCALPER", "SHADOW": "SHADOW", "SALMOS": "SALMOS", "APOCALIPSIS": "APOCALIPSIS"}
                    persona = name_map.get(raw)
                    if persona:
                        gemini_analyzer.update_agent_accuracy(persona, was_correct=True)
                        send_telegram(f"✅ {raw} registrado como correcto.", keyboard=get_main_menu())
                    else:
                        send_telegram("❌ Agente no válido. Usa: Genesis, Exodo, Shadow, Salmos, Apocalipsis")

                elif text.startswith("/funding"):
                    import market_intel
                    send_telegram(
                        market_intel.get_funding_html(),
                        keyboard=get_main_menu()
                    )

                elif text.startswith("/regime"):
                    import market_intel
                    send_telegram(
                        market_intel.get_regime_html(),
                        keyboard=get_main_menu()
                    )

                elif text.startswith("/liquidations"):
                    import market_intel
                    parts = text.split()
                    _liq_sym = parts[1].upper() if len(parts) > 1 else "TAO"
                    send_telegram(
                        market_intel.get_liquidations_html(_liq_sym),
                        keyboard=get_main_menu()
                    )

                elif text.startswith("/metrics"):
                    import metrics
                    import tracker as _trk
                    trades = _trk.get_recent_outcomes(n=100)
                    send_telegram(
                        metrics.get_metrics_html(trades),
                        keyboard=get_main_menu()
                    )

                elif text.startswith("/leverage"):
                    import risk_manager
                    # Usar valores cached o defaults si no hay data live
                    try:
                        from scalp_alert_bot import _CACHE
                        vix = _CACHE.get("VIX", {}).get("v", 0)
                    except Exception:
                        vix = 0
                    send_telegram(
                        risk_manager.get_leverage_html(
                            vix=vix, atr_pct=2.0, regime="TRENDING_UP",
                            trade_type="SWING"
                        ),
                        keyboard=get_main_menu()
                    )

                elif text.startswith("/portfolio"):
                    import risk_manager
                    import tracker as _trk
                    open_trades = _trk.get_open_trades() if hasattr(_trk, 'get_open_trades') else []
                    try:
                        from scalp_alert_bot import _CACHE
                        p = {s: _CACHE.get(s, {}).get("v", 0) for s in ["TAO", "ZEC"]}
                    except Exception:
                        p = {}
                    balance = 1000.0  # Paper default
                    send_telegram(
                        risk_manager.portfolio_risk.get_portfolio_html(
                            open_trades, p, balance
                        ),
                        keyboard=get_main_menu()
                    )

                elif text.lower().startswith("/wrong "):
                    raw = text.replace("/wrong ", "").strip().upper()
                    name_map = {"GENESIS": "CONSERVADOR", "EXODO": "SCALPER", "SHADOW": "SHADOW", "SALMOS": "SALMOS", "APOCALIPSIS": "APOCALIPSIS"}
                    persona = name_map.get(raw)
                    if persona:
                        gemini_analyzer.update_agent_accuracy(persona, was_correct=False)
                        send_telegram(f"❌ {raw} registrado como incorrecto.", keyboard=get_main_menu())
                    else:
                        send_telegram("❌ Agente no válido. Usa: Genesis, Exodo, Shadow, Salmos, Apocalipsis")

                elif text.startswith("/positions") or "positions" in t or "posiciones" in t:
                    open_trades = tracker.get_open_trades()
                    if not open_trades:
                        send_telegram("Sin posiciones abiertas.", keyboard=get_main_menu())
                    else:
                        msg = f"<b>POSICIONES ABIERTAS ({len(open_trades)})</b>\n\n"
                        for trade in open_trades:
                            ep = trade.get("entry_price") or 0
                            cur_p = prices.get(trade["symbol"], 0)
                            pnl_str = ""
                            if cur_p and ep:
                                pnl = ((cur_p - ep) / ep) * 100
                                if trade["type"] == "SHORT":
                                    pnl = -pnl
                                pnl_str = f"  PnL: <b>{pnl:+.1f}%</b>"
                            msg += (
                                f"<b>{trade['symbol']} {trade['type']}</b> ({trade.get('version','?')})\n"
                                f"  Entrada: <code>${ep:,.2f}</code>{pnl_str}\n"
                                f"  TP1: ${(trade.get('tp1_price') or 0):,.2f} | SL: ${(trade.get('sl_price') or 0):,.2f}\n\n"
                            )
                        send_telegram(msg, keyboard=get_main_menu())

                elif text.startswith("/health") or "health" in t:
                    import thread_health
                    import risk_manager as _rm
                    status = thread_health.get_status()
                    alive = sum(1 for s in status.values() if s.get("alive"))
                    total = len(status)
                    can_t, cb_reason, cb_mult = _rm.circuit_breaker.can_trade()
                    cb_icon = "NORMAL" if can_t else f"BLOQUEADO (x{cb_mult})"
                    msg = f"<b>BOT HEALTH</b>\n\n"
                    msg += f"Threads: <b>{alive}/{total}</b> vivos\n"
                    msg += f"Circuit Breaker: <b>{cb_icon}</b>\n\n"
                    for name, st in status.items():
                        icon = "OK" if st.get("alive") else "DEAD"
                        age = st.get("age_seconds", 0)
                        msg += f"  {icon} {name}: {age:.0f}s ago\n"
                    send_telegram(msg, keyboard=get_main_menu())

                elif text.startswith("/commodities") or text.startswith("/gold") or text.startswith("/oil"):
                    import commodities_bot as _cb
                    send_telegram(_cb.get_status_html(), keyboard=get_main_menu())

                elif text.startswith("/manual"):
                    import manual_positions_monitor as _mpm
                    parts = text.split()
                    subcmd = parts[1].lower() if len(parts) > 1 else ""

                    # /manual_tp SYM [pct] or /manual tp SYM [pct]
                    if subcmd in ("tp", "_tp") or text.startswith("/manual_tp"):
                        raw = text.replace("/manual_tp", "").replace("/manual tp", "").strip().split()
                        if not raw:
                            send_telegram("⚠️ Uso: /manual_tp SYM [pct]\nEj: /manual_tp TAO 50", keyboard=get_main_menu())
                        else:
                            sym = raw[0].upper()
                            pct = int(raw[1]) if len(raw) > 1 else 100
                            send_telegram(_mpm.cmd_tp(sym, pct), keyboard=get_main_menu())

                    # /manual_sl SYM or /manual sl SYM
                    elif subcmd in ("sl", "_sl") or text.startswith("/manual_sl"):
                        raw = text.replace("/manual_sl", "").replace("/manual sl", "").strip().split()
                        if not raw:
                            send_telegram("⚠️ Uso: /manual_sl SYM\nEj: /manual_sl ZEC", keyboard=get_main_menu())
                        else:
                            send_telegram(_mpm.cmd_sl(raw[0].upper()), keyboard=get_main_menu())

                    # /manual_be SYM
                    elif subcmd in ("be", "_be") or text.startswith("/manual_be"):
                        raw = text.replace("/manual_be", "").replace("/manual be", "").strip().split()
                        if not raw:
                            send_telegram("⚠️ Uso: /manual_be SYM\nEj: /manual_be DOGE", keyboard=get_main_menu())
                        else:
                            send_telegram(_mpm.cmd_be(raw[0].upper()), keyboard=get_main_menu())

                    # /manual_off SYM
                    elif subcmd in ("off", "_off") or text.startswith("/manual_off"):
                        raw = text.replace("/manual_off", "").replace("/manual off", "").strip().split()
                        if not raw:
                            send_telegram("⚠️ Uso: /manual_off SYM\nEj: /manual_off TAO", keyboard=get_main_menu())
                        else:
                            send_telegram(_mpm.cmd_off(raw[0].upper()), keyboard=get_main_menu())

                    # /manual_add SYM ENTRY [LONG|SHORT] [note]
                    elif subcmd in ("add", "_add") or text.startswith("/manual_add"):
                        raw = text.replace("/manual_add", "").replace("/manual add", "").strip().split()
                        if len(raw) < 2:
                            send_telegram("⚠️ Uso: /manual_add SYM ENTRY [LONG]\nEj: /manual_add SOL 140.5 LONG", keyboard=get_main_menu())
                        else:
                            try:
                                sym = raw[0].upper()
                                entry = float(raw[1])
                                side = raw[2].upper() if len(raw) > 2 and raw[2].upper() in ("LONG","SHORT") else "LONG"
                                note = " ".join(raw[3:]) if len(raw) > 3 else ""
                                send_telegram(_mpm.cmd_add(sym, entry, side, note), keyboard=get_main_menu())
                            except ValueError:
                                send_telegram("⚠️ Entry debe ser número. Ej: /manual_add SOL 140.5", keyboard=get_main_menu())

                    # /manual — show all positions
                    else:
                        send_telegram(_mpm.cmd_status(), keyboard=get_main_menu())

                elif text.startswith("/pause"):
                    import runtime_state
                    import scalp_alert_bot as _sab
                    runtime_state.set_field("paused", True)
                    _sab.GLOBAL_CACHE["paused"] = True
                    send_telegram("⏸️ <b>Bot pausado</b>. No ejecuta señales nuevas.\nUsa /resume para reanudar.",
                                  keyboard=get_main_menu())

                elif text.startswith("/resume"):
                    import runtime_state
                    import scalp_alert_bot as _sab
                    runtime_state.set_field("paused", False)
                    _sab.GLOBAL_CACHE["paused"] = False
                    send_telegram("▶️ <b>Bot reanudado</b>. Ejecutando señales.",
                                  keyboard=get_main_menu())

                elif text.startswith("/balance"):
                    try:
                        import scalp_alert_bot as _sab
                        executor = _sab.GLOBAL_CACHE.get("executor")
                        if executor is None:
                            from trading_executor import ZenithExecutor
                            executor = ZenithExecutor()
                        bal = executor.get_balance()
                        mode = os.getenv("EXECUTION_MODE", "PAPER")
                        send_telegram(f"💰 <b>USDT Futures</b>: ${bal:.2f}\nModo: <b>{mode}</b>",
                                      keyboard=get_main_menu())
                    except Exception as e:
                        send_telegram(f"❌ Error balance: {e}", keyboard=get_main_menu())

                elif text.startswith("/mode"):
                    import runtime_state
                    parts = text.split()
                    if len(parts) < 2 or parts[1].upper() not in ("PAPER", "LIVE"):
                        cur = os.getenv("EXECUTION_MODE", "PAPER")
                        send_telegram(f"ℹ️ Modo actual: <b>{cur}</b>\nUso: /mode paper | /mode live",
                                      keyboard=get_main_menu())
                    else:
                        new_mode = parts[1].upper()
                        runtime_state.set_field("execution_mode", new_mode)
                        os.environ["EXECUTION_MODE"] = new_mode
                        # Refresh executor instance so it picks new mode
                        import scalp_alert_bot as _sab
                        try:
                            from trading_executor import ZenithExecutor
                            _sab.GLOBAL_CACHE["executor"] = ZenithExecutor()
                        except Exception as e:
                            print(f"WARN refresh executor: {e}")
                        warn = " ⚠️ <b>LIVE: dinero real</b>" if new_mode == "LIVE" else ""
                        send_telegram(f"✅ Modo cambiado a <b>{new_mode}</b>.{warn}",
                                      keyboard=get_main_menu())

                elif text.startswith("/verbose"):
                    import runtime_state
                    parts = text.split()
                    if len(parts) < 2 or parts[1].lower() not in ("on", "off"):
                        cur = "ON" if runtime_state.is_verbose() else "OFF"
                        send_telegram(
                            f"🗣️ <b>Verbose</b>: {cur}\n"
                            f"<code>/verbose on</code>  → reportes Cuadrilla full\n"
                            f"<code>/verbose off</code> → formato compacto (default)",
                            keyboard=get_main_menu())
                    else:
                        new_val = parts[1].lower() == "on"
                        runtime_state.set_field("verbose", new_val)
                        if not new_val:
                            # Limpia dedupe al volver a compact (permite ver primer reporte fresco)
                            try:
                                import voice_compactor as _vc
                                _vc.clear_dedupe()
                            except Exception:
                                pass
                        msg = "🗣️ Verbose <b>ON</b> — Cuadrilla full." if new_val else "🤐 Verbose <b>OFF</b> — formato compacto."
                        send_telegram(msg, keyboard=get_main_menu())

                elif text.startswith("/params"):
                    try:
                        from config import (
                            RSI_LONG_ENTRY, RSI_SHORT_ENTRY, SHORT_MIN_CONFLUENCE,
                            V3_MIN_CONFLUENCE, V4_EMA_PROX_MAP, ADX_TRENDING_THRESHOLD,
                            BB_WIDTH_RANGING_PCT, RVOL_MIN_ENTRY, RVOL_MIN_BTC,
                            SENTINEL_MIN_SCORE_OF_5, SENTINEL_INTERVAL_SEC,
                            SENTINEL_DEDUPE_MIN, V1_SHORT_ENABLED,
                        )
                    except Exception as e:
                        send_telegram(f"❌ Error leyendo config: {e}", keyboard=get_main_menu())
                    else:
                        sentinel_min_h = SENTINEL_INTERVAL_SEC // 3600
                        msg = (
                            "<b>⚙️ Parámetros activos</b>\n"
                            "<code>━━━━━━━━━━━━━</code>\n"
                            "<b>RSI thresholds</b>\n"
                            f"  long ≤ <b>{RSI_LONG_ENTRY}</b> · short ≥ <b>{RSI_SHORT_ENTRY}</b>\n"
                            "<b>Confluence min</b>\n"
                            f"  V1-LONG: <b>{V3_MIN_CONFLUENCE}</b> · V1-SHORT: <b>{SHORT_MIN_CONFLUENCE}</b>\n"
                            "<b>Regime</b>\n"
                            f"  ADX trending: <b>{ADX_TRENDING_THRESHOLD}</b> · BB ranging: <b>{BB_WIDTH_RANGING_PCT*100:.1f}%</b>\n"
                            "<b>RVOL min</b>\n"
                            f"  default: <b>{RVOL_MIN_ENTRY}</b> · BTC: <b>{RVOL_MIN_BTC}</b>\n"
                            "<b>EMA prox (V4)</b>\n"
                            "  " + " · ".join(f"{k}:{v:.3f}" for k, v in list(V4_EMA_PROX_MAP.items())[:4]) + "\n"
                            "<b>Kill switches</b>\n"
                            f"  V1-LONG: ✅  V1-SHORT: {'✅' if V1_SHORT_ENABLED else '❌'}\n"
                            "<b>Sentinel (compact)</b>\n"
                            f"  min score: <b>{SENTINEL_MIN_SCORE_OF_5}/5</b> · interval: <b>{sentinel_min_h}h</b> · dedupe: <b>{SENTINEL_DEDUPE_MIN}min</b>"
                        )
                        send_telegram(msg, keyboard=get_main_menu())

                elif text.startswith("/scan"):
                    try:
                        import scan_status as _scan
                        msg = _scan.build_scan_report(prices)
                        send_telegram(msg, keyboard=get_main_menu())
                    except Exception as e:
                        send_telegram(f"❌ Error /scan: {e}", keyboard=get_main_menu())

                elif text.startswith("/stocks"):
                    try:
                        import stock_watchlist as _sw
                        parts = text.split(maxsplit=1)
                        args = parts[1].strip() if len(parts) > 1 else ""
                        msg = _sw.handle_command(args)
                        send_telegram(msg, keyboard=get_main_menu())
                    except Exception as e:
                        send_telegram(f"❌ Error /stocks: {e}", keyboard=get_main_menu())

                elif text.startswith("/logs"):
                    parts = text.split()
                    try:
                        n = int(parts[1]) if len(parts) >= 2 else 30
                    except ValueError:
                        n = 30
                    n = max(1, min(n, 200))
                    log_path = "logs/bot.log"
                    if not os.path.exists(log_path):
                        log_path = "logs/app.log"
                    if os.path.exists(log_path):
                        try:
                            with open(log_path, "r", encoding="utf-8", errors="replace") as lf:
                                lines = lf.readlines()[-n:]
                            body = "".join(lines)[-3500:]
                            send_telegram(f"📜 <b>Últimas {len(lines)} líneas</b> ({log_path}):\n<pre>{safe_html(body)}</pre>",
                                          keyboard=get_main_menu())
                        except Exception as e:
                            send_telegram(f"❌ Error leyendo log: {e}", keyboard=get_main_menu())
                    else:
                        send_telegram("⚠️ No se encontró log file.", keyboard=get_main_menu())

                elif text.startswith("/setsl") or text.startswith("/settp"):
                    parts = text.split()
                    if len(parts) < 3:
                        send_telegram("⚠️ Uso: /setsl SYM PCT  o  /settp SYM PCT", keyboard=get_main_menu())
                    else:
                        try:
                            sym = parts[1].upper()
                            pct = float(parts[2])
                            field = "sl" if text.startswith("/setsl") else "tp1"
                            open_trades = tracker.get_open_trades() if hasattr(tracker, "get_open_trades") else []
                            target = next((t for t in open_trades if t.get("symbol", "").upper() == sym), None)
                            if not target:
                                send_telegram(f"⚠️ No hay trade abierto para {sym}.", keyboard=get_main_menu())
                            else:
                                entry = float(target.get("entry", 0))
                                side = target.get("side", "LONG")
                                direction = 1 if side == "LONG" else -1
                                if field == "sl":
                                    new_val = entry * (1 - direction * pct / 100)
                                else:
                                    new_val = entry * (1 + direction * pct / 100)
                                if hasattr(tracker, "update_trade_levels"):
                                    tracker.update_trade_levels(target["id"], **{field: new_val})
                                    send_telegram(f"✅ {field.upper()} de {sym} ajustado a ${new_val:.4f} ({pct}%)",
                                                  keyboard=get_main_menu())
                                else:
                                    send_telegram("⚠️ tracker.update_trade_levels no disponible — fix manual",
                                                  keyboard=get_main_menu())
                        except Exception as e:
                            send_telegram(f"❌ Error: {e}", keyboard=get_main_menu())

                else:
                    _handle_user_question(text, prices)

            except Exception as e:
                print(f"❌ Error procesando update: {e}")

    except Exception as e:
        print(f"❌ Error en check_user_queries: {e}")
