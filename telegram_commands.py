"""
telegram_commands.py — Dispatcher de comandos de Telegram

Extrae check_user_queries de scalp_alert_bot.py para reducir tamaño.
Usa lazy imports para evitar circularidad con scalp_alert_bot.
"""

import os
import time
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


# ── Helpers compartidos: cálculo de niveles y pickers ─────────────────────────

def compute_levels(side: str, price: float, atr: float = 0.0) -> dict:
    """Calcula SL/TP1/TP2 via ATR (mismo método que el flujo LONG/SHORT free-text).

    Args:
        side: 'LONG' o 'SHORT'
        price: precio de entrada
        atr: ATR del símbolo (si 0, usa 1% del precio como floor)

    Returns dict con keys sl, tp1, tp2.
    """
    sl_d = max(atr * 1.5, price * 0.005)
    if side == "LONG":
        sl = round(price - sl_d, 4)
        tp1 = round(price + sl_d * 2.0, 4)
        tp2 = round(price + sl_d * 3.5, 4)
    else:
        sl = round(price + sl_d, 4)
        tp1 = round(price - sl_d * 2.0, 4)
        tp2 = round(price - sl_d * 3.5, 4)
    return {"sl": sl, "tp1": tp1, "tp2": tp2}


def open_picker_keyboard() -> dict:
    """Keyboard inline con MANUAL_SYMBOLS para elegir símbolo. Usado por /open."""
    from config import MANUAL_SYMBOLS
    rows = []
    for i in range(0, len(MANUAL_SYMBOLS), 3):
        row = [{"text": s, "callback_data": f"open_sym:{s}"} for s in MANUAL_SYMBOLS[i:i+3]]
        rows.append(row)
    rows.append([{"text": "❌ Cancel", "callback_data": "open_cancel"}])
    return {"inline_keyboard": rows}


def open_side_keyboard(sym: str) -> dict:
    """Keyboard inline con LONG/SHORT después de elegir símbolo."""
    return {
        "inline_keyboard": [[
            {"text": "🟢 LONG", "callback_data": f"open_side:{sym}:LONG"},
            {"text": "🔴 SHORT", "callback_data": f"open_side:{sym}:SHORT"},
        ], [
            {"text": "❌ Cancel", "callback_data": "open_cancel"},
        ]]
    }


def open_confirm_keyboard(sym: str, side: str, entry: float) -> dict:
    """Keyboard inline para confirmar apertura con precio precalculado."""
    return {
        "inline_keyboard": [[
            {"text": "✅ Confirmar", "callback_data": f"open_confirm:{sym}:{side}:{entry}"},
        ], [
            {"text": "❌ Cancel", "callback_data": "open_cancel"},
        ]]
    }


def cmd_pos(args: str, prices: dict) -> str:
    """Vista unificada de posiciones (manual + auto). Modo compact (default) o full.

    Args:
        args: string con flags (e.g. 'full' habilita modo extendido)
        prices: dict de precios actuales
    """
    import tracker as _trk
    full = "full" in (args or "").lower()
    open_trades = _trk.get_open_trades()

    if not open_trades:
        return "Sin posiciones abiertas."

    lines = [f"<b>POSICIONES ({len(open_trades)})</b>\n"]
    for t in open_trades:
        sym = t["symbol"]
        side = t["type"]
        marker = "🟡" if t.get("is_manual") else "🤖"
        ep = t.get("entry_price") or 0
        cur = prices.get(sym, 0) or 0
        pnl_str = ""
        if cur and ep:
            pnl = ((cur - ep) / ep) * 100
            if side == "SHORT":
                pnl = -pnl
            pnl_icon = "🟢" if pnl >= 0 else "🔴"
            pnl_str = f" {pnl_icon} {pnl:+.1f}%"
        be_tag = " [BE]" if t.get("be_moved") else ""
        partial_tag = f" [{t.get('partial_pct',0)}%]" if t.get("partial_pct", 0) > 0 else ""

        if not full:
            lines.append(f"{marker} <b>{sym} {side}</b>{be_tag}{partial_tag} @ ${ep:,.4f} → ${cur:,.4f}{pnl_str}")
        else:
            sl = t.get("sl_price") or 0
            tp1 = t.get("tp1_price") or 0
            tp2 = t.get("tp2_price") or 0
            ot = t.get("open_time") or ""
            lines.append(
                f"{marker} <b>{sym} {side}</b>{be_tag}{partial_tag} ({t.get('version','?')})\n"
                f"  Entry: <code>${ep:,.4f}</code> → ${cur:,.4f}{pnl_str}\n"
                f"  TP1: ${tp1:,.4f} | TP2: ${tp2:,.4f} | SL: ${sl:,.4f}\n"
                f"  Open: {ot}"
            )

    msg = "\n".join(lines)

    if full:
        # Append health + recommendations en modo full
        try:
            import thread_health
            import risk_manager as _rm
            status = thread_health.get_status()
            alive = sum(1 for s in status.values() if s.get("alive"))
            total = len(status)
            can_t, _, cb_mult = _rm.circuit_breaker.can_trade()
            cb_icon = "NORMAL" if can_t else f"BLOQUEADO (x{cb_mult})"
            msg += f"\n\n<b>BOT HEALTH</b>\nThreads: {alive}/{total} | CB: {cb_icon}"
        except Exception:
            pass

        try:
            import manual_positions_monitor as _mpm
            manual_active = _trk.get_open_manual_trades()
            if manual_active:
                msg += "\n\n" + _mpm.cmd_status()
        except Exception:
            pass

    return msg


def cmd_open(prices: dict) -> tuple:
    """Inicia flujo de apertura via inline keyboard. Returns (msg, keyboard)."""
    return (
        "➕ <b>Abrir posición manual</b>\n\nElige símbolo:",
        open_picker_keyboard(),
    )


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

                elif text.startswith("/bitlobomulti"):
                    # Spec 011.5 (2026-05-26): batch analiza últimas N imágenes guardadas del símbolo.
                    # Workflow: usuario manda fotos via /add_chart SYM TF1, /add_chart SYM TF2,
                    # luego /bitlobomulti SYM → bot busca image_sym_*.png reciente (<30min) y manda
                    # análisis cross-asset multimodal a Gemini.
                    import bitlobo_agent
                    import glob
                    parts = text.split()
                    if len(parts) >= 2:
                        sym = parts[1].upper()
                        # Buscar imágenes del símbolo en chart_ideas/assets — mtime ≤ 30min
                        candidates = glob.glob(f"chart_ideas/assets/image_{sym.lower()}_*.png")
                        now = time.time()
                        recent = [p for p in candidates if now - os.path.getmtime(p) < 1800]
                        recent.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                        recent = recent[:5]  # Top 5 más recientes
                        if not recent:
                            send_telegram(f"🐺 BitLobo Multi: No encontré imágenes recientes (<30min) de {sym}. Manda primero con /add_chart {sym} TF.")
                        else:
                            # Labels = TF inferido del filename si posible
                            labels = []
                            for p in recent:
                                # filename: image_sym_tf.png o image_sym_tf_timestamp.png
                                base = os.path.basename(p).replace(".png", "")
                                parts_fn = base.split("_")
                                tf_part = parts_fn[2].upper() if len(parts_fn) >= 3 else "TF"
                                labels.append(f"{sym} {tf_part}")
                            send_telegram(f"🐺 <b>BitLobo Multi analizando {sym}</b> ({len(recent)} imágenes: {', '.join(labels)})...")
                            result = bitlobo_agent.analyze_chart_multi(
                                image_paths=recent,
                                symbol=sym,
                                timeframe=labels[0].split()[-1] if labels else "MULTI",
                                extra_context=f"Análisis cross-TF de {sym}",
                                image_labels=labels,
                            )
                            send_telegram(safe_html(result))
                    else:
                        send_telegram("🐺 Uso: /bitlobomulti SYMBOL\nEj: /bitlobomulti BTC (debe haber imágenes recientes guardadas via /add_chart)")
                    continue

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

                elif "mercado" in t and not text.startswith("/status"):
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

                elif text.startswith("/help") or text.lower() == "ayuda":
                    # Help menu completo — explica botones + comandos disponibles
                    help_text = (
                        "🔥 <b>ZENITH BOT — Guía Comandos</b>\n\n"
                        "<b>📂 Menú botones (top 6):</b>\n"
                        "  📂 <b>Pos</b> — Posiciones abiertas\n"
                        "  💰 <b>PnL</b> — Profit & Loss del día\n"
                        "  📊 <b>Win Rate</b> — WR global + por símbolo\n"
                        "  🔬 <b>Intel BTC</b> — HMM+CVD+Social+Whale+OI snapshot\n"
                        "  🛡️ <b>Status</b> — Threads + módulos intel + AI budget\n"
                        "  🏛️ <b>Audit</b> — Kill switches NB3 + A/B stats\n\n"
                        "<b>🔬 Intel adicional:</b>\n"
                        "  <code>/intel SYM</code> — ej: /intel ETH, /intel NVDA\n"
                        "  <code>/regime SYM</code> — HMM regime classifier\n"
                        "  <code>/funding</code> — Funding rates cripto\n"
                        "  <code>/macro</code> — USDT.D + VIX + DXY\n"
                        "  <code>/commodities</code> — GOLD/OIL/NG/SLV status\n\n"
                        "<b>🎯 Operación manual:</b>\n"
                        "  <code>/open</code> — Picker inline\n"
                        "  <code>/close SYM</code> — Cerrar posición\n"
                        "  <code>/manual_add SYM ENTRY [LONG]</code>\n"
                        "  <code>/manual_tp SYM [pct]</code> · /manual_sl · /manual_be · /manual_off\n\n"
                        "<b>📈 BitLobo gráficas:</b>\n"
                        "  <code>/bitlobo SYM TF</code> — 1 imagen (foto + caption)\n"
                        "  <code>/bitlobomulti SYM</code> — multi-image cross-asset\n"
                        "  <code>/add_chart SYM TF</code> + foto — guardar imagen\n\n"
                        "<b>🔧 Admin:</b>\n"
                        "  <code>/budget</code> — Consumo IA mes vs $10\n"
                        "  <code>/pause</code> · <code>/resume</code> — Pausar alerts\n"
                        "  <code>/circuit</code> · <code>/risk</code> — Circuit + risk params\n"
                        "  <code>/mode</code> · <code>/verbose</code>\n"
                        "  <code>/logs</code> — Últimos logs\n\n"
                        "<b>🐛 Debug avanzado:</b>\n"
                        "  /agents /scan /stocks /metrics /liquidations\n\n"
                        "<b>📝 Quick actions (texto libre):</b>\n"
                        "  <code>BTC LONG 100k</code> — abrir manual rápido\n"
                        "  <code>CERRAR BTC</code> — cerrar manual\n"
                        "  <code>/correct ID</code> · <code>/wrong ID</code> — feedback alert\n\n"
                        "<b>💡 Tip TDAH:</b> los 6 botones cubren 80% del uso diario. "
                        "Resto vía /comando o menú slash (/)."
                    )
                    send_telegram(help_text, keyboard=get_main_menu())

                elif text.startswith("/status") or "status" in t.split():
                    # Health check completo del bot — threads, budget, último alert, módulos intel
                    import thread_health
                    health = thread_health.get_health_summary() if hasattr(thread_health, "get_health_summary") else {}
                    status_lines = ["🔥 <b>STATUS ZENITH</b>\n"]
                    # Threads
                    status_lines.append("<b>Threads:</b>")
                    for tname, ts in (thread_health._heartbeats or {}).items():
                        age = int(time.time() - ts)
                        emoji = "✅" if age < 300 else "⚠️"
                        status_lines.append(f"  {emoji} {tname}: {age}s")
                    # Módulos intel
                    status_lines.append("\n<b>Intel modules:</b>")
                    for mod_name in ["regime_hmm", "cvd_segmented", "social_quant", "onchain", "options_oi", "grounded_search", "regime_transitions"]:
                        try:
                            __import__(mod_name)
                            status_lines.append(f"  ✅ {mod_name}")
                        except ImportError:
                            status_lines.append(f"  ❌ {mod_name}")
                    # Budget
                    try:
                        import ai_budget
                        b = ai_budget.get_monthly_summary()
                        status_lines.append(f"\n<b>AI Budget:</b> ${b.get('total_cost_usd', 0):.2f} / $10.00 ({b.get('budget_used_pct', 0):.0f}%)")
                    except Exception:
                        pass
                    send_telegram("\n".join(status_lines))

                elif text.startswith("/intel"):
                    # /intel SYMBOL — snapshot intel modules para un símbolo
                    parts = text.split()
                    if len(parts) < 2:
                        send_telegram("🔬 Uso: /intel SYMBOL\nEj: /intel BTC, /intel NVDA")
                        continue
                    sym_raw = parts[1].upper()
                    sym_pair = f"{sym_raw}/USDT" if "/" not in sym_raw and sym_raw in ["BTC","ETH","SOL","ZEC","TAO","HBAR","DOGE","TON"] else sym_raw
                    lines = [f"🔬 <b>INTEL {sym_raw}</b>\n"]
                    # HMM
                    try:
                        import regime_hmm
                        r = regime_hmm.detect_regime(sym_pair, "1h", 200 if "/" in sym_pair else 100)
                        if r and r.get("regime"):
                            lines.append(f"📊 <b>HMM:</b> {r['regime']} (conf {r.get('confidence', 0)*100:.0f}%)")
                        else:
                            lines.append("📊 HMM: sin datos")
                    except Exception as _e:
                        lines.append(f"📊 HMM: error ({_e})")
                    # CVD (solo cripto)
                    if "/USDT" in sym_pair:
                        try:
                            import cvd_segmented
                            c = cvd_segmented.compute_cvd_segmented(sym_pair, 1000)
                            if c and c.get("divergence_signal"):
                                lines.append(f"🌊 <b>CVD:</b> {c['divergence_signal']} · Whale ${c.get('whale_cvd_usd', 0):+,.0f} · Retail ${c.get('retail_cvd_usd', 0):+,.0f}")
                            else:
                                lines.append("🌊 CVD: sin datos")
                        except Exception as _e:
                            lines.append(f"🌊 CVD: error")
                    # Social
                    try:
                        import social_quant
                        s = social_quant.get_social_sentiment(sym_raw, 24)
                        if s and s.get("signal"):
                            lines.append(f"💀 <b>Social:</b> {s['signal']} · Reddit {s.get('reddit_compound', 0):+.2f} · Trends {s.get('google_trends_delta', 0):+.0f}%")
                        else:
                            lines.append("💀 Social: sin datos (configura REDDIT_CLIENT_ID)")
                    except Exception:
                        lines.append("💀 Social: módulo no disponible")
                    # Whale (solo ETH)
                    if sym_raw == "ETH":
                        try:
                            import onchain
                            w = onchain.get_whale_netflow("ETH", "eth", 24)
                            if w and w.get("signal"):
                                lines.append(f"🐋 <b>Whale ETH:</b> {w['signal']} · Net ${w.get('net_flow_usd', 0):+,.0f} ({w.get('tx_count', 0)} tx)")
                            else:
                                lines.append("🐋 Whale: sin datos (configura ETHERSCAN_API_KEY)")
                        except Exception:
                            lines.append("🐋 Whale: módulo no disponible")
                    # Options OI (stocks)
                    if "/" not in sym_pair and sym_raw not in ["BTC","ETH","SOL","ZEC","TAO","HBAR","DOGE","TON"]:
                        try:
                            import options_oi
                            o = options_oi.get_options_oi_ratio(sym_raw, 2)
                            if o and o.get("signal"):
                                lines.append(f"📈 <b>Options OI:</b> {o['signal']} · ratio {o.get('call_put_ratio', 0):.2f}x")
                            else:
                                lines.append("📈 Options OI: sin datos")
                        except Exception:
                            lines.append("📈 Options OI: módulo no disponible")
                    send_telegram("\n".join(lines))

                elif text.startswith("/audit") or "Auditoría" in text or "audit" in t.split():
                    # Auditoría enhanced — incluye verificación findings NotebookLM 3
                    m = tracker.get_audit_metrics()
                    lines = ["🏛️ <b>AUDITORÍA ZENITH + NB3</b>\n"]
                    if m["total_trades"] == 0:
                        lines.append("📈 Nueva era. Sin trades aún.\n🎯 Objetivo: Profit Factor > 1.75")
                    else:
                        lines.append(f"<b>Trades:</b> {m['total_trades']} · W {m['wins']} · L {m['losses']}")
                        lines.append(f"<b>WR:</b> {m['win_rate']} · PF: {m['profit_factor']} · Status: {m['status']}")
                    # Kill switches NotebookLM 3 P0
                    lines.append("\n<b>Kill Switches NB3 P0:</b>")
                    try:
                        from config import (
                            COMMODITY_BLOCKLIST, BLOCK_SCORE_5, MIN_RSI_LONG,
                            TAO_TRADING_ENABLED, SHORT_BLOCKED_IN_VERDE_BULL,
                            SWING_BLOCKLIST, V4_BLOCKLIST,
                        )
                        lines.append(f"  {'✅' if 'GOLD' in COMMODITY_BLOCKLIST else '❌'} GOLD blocklist: {COMMODITY_BLOCKLIST}")
                        lines.append(f"  {'✅' if BLOCK_SCORE_5 else '❌'} BLOCK_SCORE_5: {BLOCK_SCORE_5}")
                        lines.append(f"  {'✅' if MIN_RSI_LONG >= 50 else '⚠️'} MIN_RSI_LONG: {MIN_RSI_LONG}")
                        lines.append(f"  {'✅' if not TAO_TRADING_ENABLED else '❌'} TAO kill: {not TAO_TRADING_ENABLED}")
                        lines.append(f"  {'✅' if SHORT_BLOCKED_IN_VERDE_BULL else '❌'} SHORT block VERDE: {SHORT_BLOCKED_IN_VERDE_BULL}")
                        lines.append(f"  SWING_BLOCKLIST: {SWING_BLOCKLIST}")
                        lines.append(f"  V4_BLOCKLIST: {V4_BLOCKLIST}")
                    except Exception as _e:
                        lines.append(f"  ❌ error leyendo config: {_e}")
                    # A/B stats si hay
                    try:
                        ab = tracker.get_intel_ab_stats()
                        if ab.get("total", 0) > 0:
                            lines.append(f"\n<b>A/B Intel (Spec 022):</b>")
                            lines.append(f"  total: {ab['total']} · with_outcome: {ab.get('with_outcome', 0)}")
                            for bk, bs in ab.get("boost_segments", {}).items():
                                lines.append(f"  {bk}: {bs.get('count', 0)} ops · WR {bs.get('wr', 0):.1f}%")
                    except Exception:
                        pass
                    send_telegram("\n".join(lines), keyboard=get_main_menu())

                elif text.startswith("/open") or "/open" in text or text.lower() == "open":
                    msg, kb = cmd_open(prices)
                    send_telegram(msg, keyboard=kb)

                elif text.startswith("/pos") or "/pos" in text or "pos" in t.split():
                    # Acepta "/pos", "/pos full", botón "📂 /pos" o "📂 Pos"
                    args = "full" if "full" in text.lower() else ""
                    send_telegram(cmd_pos(args, prices), keyboard=get_main_menu())

                elif "LONG" in text or "SHORT" in text:
                    from config import MANUAL_SYMBOLS
                    clean = text.replace("/", "").upper()
                    pool = list(set(MANUAL_SYMBOLS + ["SOL", "BTC", "TAO", "ZEC", "ETH", "DOGE"]))
                    sym = next((s for s in pool if s in clean.split()), None)
                    if not sym:
                        sym = next((s for s in pool if s in clean), None)
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
                        if p > 0:
                            lv = compute_levels(side, p, atr)
                            mid = send_telegram(
                                f"🚀 <b>{sym} {side} MANUAL</b>\nEntrada: ${p:,.4f}\n"
                                f"🎯 TP1: <b>${lv['tp1']:,.4f}</b> | TP2: <b>${lv['tp2']:,.4f}</b>\n🛑 SL: <b>${lv['sl']:,.4f}</b>",
                                keyboard=get_main_menu(sym)
                            )
                            tid = tracker.log_trade(
                                sym, side, p, lv["tp1"], lv["tp2"], lv["sl"], mid,
                                version="MANUAL", rsi=prices.get(f"{sym}_RSI", 50),
                                is_manual=1,
                            )
                            tracker.append_event(tid, f"OPENED {side} @ ${p:.4f}")
                        else:
                            send_telegram(f"❌ No se pudo obtener precio de {sym}.")
                    else:
                        send_telegram("❌ Símbolo no reconocido. Usa BTC/SOL/TAO/ZEC/DOGE/ETH.")

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

                    # Base winrate report
                    base_msg = _em.format_winrate_telegram(days)

                    # Real vs SIM comparison (nuevo — Activate/Skip tracking)
                    try:
                        cmp = tracker.get_winrate_comparison()
                        r, s = cmp["real"], cmp["sim"]
                        gap_icon = "⚠️" if cmp["gap"] > 5 else ("✅" if cmp["gap"] < -5 else "↔️")
                        sim_section = (
                            f"\n\n<b>📊 Real vs SIM (Activate/Skip)</b>\n"
                            f"<code>{'─'*28}</code>\n"
                            f"🟢 <b>Real</b>: {r['wins']}W / {r['losses']}L / {r['total']} → <b>{r['wr']}%</b>\n"
                            f"🔵 <b>SIM</b>:  {s['wins']}W / {s['losses']}L / {s['total']} → <b>{s['wr']}%</b>\n"
                            f"{gap_icon} {cmp['verdict']}\n"
                            f"<i>SIM = señales que skiaste. "
                            f"Gap {cmp['gap']:+.1f}pp.</i>"
                        ) if s["total"] > 0 else (
                            f"\n\n<b>📊 Real vs SIM</b>\n"
                            f"Sin datos SIM aún — skipea señales para ver comparación."
                        )
                        send_telegram(base_msg + sim_section, keyboard=get_main_menu())
                    except Exception:
                        send_telegram(base_msg, keyboard=get_main_menu())

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
                    _sym = "BTC"
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

                elif "apihealth" in t or text.startswith("/apihealth") or text.startswith("/health"):
                    import api_health
                    send_telegram(api_health.format_report(), keyboard=get_main_menu())

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

                elif text.startswith("/check") or t == "🔍 check":
                    import manual_positions_monitor as _mpm
                    send_telegram(_mpm.cmd_check_positions(prices), keyboard=get_main_menu())

                elif text.startswith("/commodities") or text.startswith("/gold") or text.startswith("/oil") or "commod" in t:
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
