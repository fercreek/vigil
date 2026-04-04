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

                elif "CERRAR " in text or "CLOSE " in text:
                    clean = text.replace("/", "").upper()
                    sym   = next((s for s in ["SOL", "BTC", "TAO", "ZEC"] if s in clean), None)
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

                elif text.lower().startswith("/wrong "):
                    raw = text.replace("/wrong ", "").strip().upper()
                    name_map = {"GENESIS": "CONSERVADOR", "EXODO": "SCALPER", "SHADOW": "SHADOW", "SALMOS": "SALMOS", "APOCALIPSIS": "APOCALIPSIS"}
                    persona = name_map.get(raw)
                    if persona:
                        gemini_analyzer.update_agent_accuracy(persona, was_correct=False)
                        send_telegram(f"❌ {raw} registrado como incorrecto.", keyboard=get_main_menu())
                    else:
                        send_telegram("❌ Agente no válido. Usa: Genesis, Exodo, Shadow, Salmos, Apocalipsis")

                else:
                    _handle_user_question(text, prices)

            except Exception as e:
                print(f"❌ Error procesando update: {e}")

    except Exception as e:
        print(f"❌ Error en check_user_queries: {e}")
