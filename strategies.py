"""
strategies.py — Lógica de estrategias V1-V4 + USDT.D Institucional

Extraído de scalp_alert_bot.py para mantener archivos < 600 líneas.
Contiene: check_strategies(), calculate_confluence_score(), classify_trade(),
build_trigger_conditions(), get_confluence_badge(), format_confidence()
"""

import time
from config import (
    V4_EMA_PROXIMITY_MAX, V4_EMA_PROXIMITY_MIN, V4_RSI_LOW,
    V4_RSI_HIGH, V4_RSI_HIGH_ZEC, V4_MIN_CONFLUENCE,
    V4_ATR_SL_MULT, V4_COOLDOWN,
)


# ─── Confluence Score ───────────────────────────────────────────────────────

def calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d=8.0,
                               side="LONG", elliott="", spy=0.0, oil=0.0,
                               ob_detected=False):
    """
    Calcula un score de confluencia técnica + Macro (0-6 puntos).
    V3.0: Añadido SMC (Order Block Detection).
    """
    # Lazy imports para evitar circularidad
    from scalp_alert_bot import GLOBAL_CACHE

    score = 0
    # 1. RSI (2 pts)
    if side == "LONG":
        if rsi <= 30: score += 2
        elif rsi <= 40: score += 1
    else:  # SHORT
        if rsi >= 70: score += 2
        elif rsi >= 60: score += 1

    # 2. EMA 200 Trend (1 pt)
    if (side == "LONG" and p > ema_200) or (side == "SHORT" and p < ema_200):
        score += 1

    # 3. Bollinger (1 pt)
    if (side == "LONG" and p <= bb_l * 1.01) or (side == "SHORT" and p >= bb_u * 0.99):
        score += 1

    # 4. USDT.D Bias (1 pt)
    if (side == "LONG" and usdt_d < 8.05) or (side == "SHORT" and usdt_d > 8.05):
        score += 1

    # 5. Elliott Wave Bonus/Penalización
    if "Onda 3" in elliott:
        score += 1
    elif "Corrección" in elliott or "Correctiva" in elliott:
        score -= 1

    # --- 6. MACRO BONUS (V2.1 - LONG ONLY BIAS) ---
    if side == "LONG":
        if spy > 0:
            if usdt_d < 8.05:
                score += 1

        # Bonus Institucional Tech (NVDA + PLTR)
        nvda = GLOBAL_CACHE["macro_metrics"].get("nvda", 0)
        pltr = GLOBAL_CACHE["macro_metrics"].get("pltr", 0)
        if nvda > 0 and pltr > 0:
            score += 1

    # --- 7. SMC BONUS (V3.0 - SMART MONEY) ---
    if ob_detected:
        score += 1

    return min(6, score)


def get_confluence_badge(score):
    if score >= 4:
        return "💎 DIAMANTE (MAX CONFLUENCIA) 💎"
    if score == 3:
        return "🔥 ALTA CONVICCIÓN (CONFLUENTE) 🔥"
    return "⚡ SEÑAL ESTÁNDAR ⚡"


def format_confidence(score):
    """Mapea score 0-5 a porcentaje 60-100% para UX."""
    pct = 50 + (score * 10)
    return f"{pct}%"


def classify_trade(vix: float, dxy: float, macro_status: str) -> str:
    """
    Clasifica el trade como RAPIDA o SWING basado en contexto macro (metodología PTS).
    - RAPIDA: alta volatilidad, incertidumbre, usar posición 50% del normal
    - SWING: condiciones favorables, posición normal
    """
    if vix > 35:
        return "RAPIDA"
    if vix > 25:
        return "RAPIDA"
    if dxy > 105 and macro_status != "BULL":
        return "RAPIDA"
    return "SWING"


def build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200,
                              usdt_d, vix, dxy, macro_dict, macro_status,
                              atr, elliott, ob_detected, social_adj,
                              trade_type, phy_bias, conf_score,
                              strategy, side, rsi_threshold=42.0):
    """
    Construye un dict estructurado con exactamente qué condiciones dispararon la alerta.
    Se persiste como JSON en trigger_conditions para trazabilidad completa.
    """
    rsi_rising = rsi >= prev_rsi
    bb_zone = "lower" if p <= bb_l * 1.01 else "upper" if p >= bb_u * 0.99 else "range"
    above_ema200 = p > ema_200

    score_breakdown = {}
    if side == "LONG":
        score_breakdown["rsi_pts"] = 2 if rsi <= 30 else (1 if rsi <= 40 else 0)
    else:
        score_breakdown["rsi_pts"] = 2 if rsi >= 70 else (1 if rsi >= 60 else 0)
    score_breakdown["ema200_pt"] = 1 if ((side == "LONG" and above_ema200) or (side == "SHORT" and not above_ema200)) else 0
    score_breakdown["bb_pt"] = 1 if bb_zone in ("lower" if side == "LONG" else ("upper",)) else 0
    score_breakdown["usdt_d_pt"] = 1 if ((side == "LONG" and usdt_d < 8.05) or (side == "SHORT" and usdt_d > 8.05)) else 0
    score_breakdown["elliott_pt"] = 1 if "Onda 3" in elliott else (-1 if ("Corrección" in elliott or "Correctiva" in elliott) else 0)
    score_breakdown["ob_pt"] = 1 if ob_detected else 0
    score_breakdown["social_adj"] = round(social_adj, 3)

    return {
        "strategy": strategy,
        "side": side,
        "symbol": sym,
        "price": round(p, 4),
        "rsi": round(rsi, 2),
        "rsi_threshold": rsi_threshold,
        "rsi_ok": rsi <= rsi_threshold if side == "LONG" else rsi >= rsi_threshold,
        "rsi_rising": rsi_rising,
        "bb_zone": bb_zone,
        "bb_upper": round(bb_u, 4),
        "bb_lower": round(bb_l, 4),
        "bb_touch_ok": bb_zone == "lower" if side == "LONG" else bb_zone == "upper",
        "ema200": round(ema_200, 4),
        "above_ema200": above_ema200,
        "ema200_ok": above_ema200 if side == "LONG" else not above_ema200,
        "usdt_d": round(usdt_d, 3),
        "usdt_d_ok": usdt_d < 8.05 if side == "LONG" else usdt_d > 8.05,
        "atr": round(atr, 4),
        "atr_pct": round(atr / p * 100, 2) if p else 0,
        "elliott": elliott,
        "ob_detected": ob_detected,
        "social_adj": round(social_adj, 3),
        "macro_status": macro_status,
        "macro_1h": macro_dict.get("1H", "UNKNOWN"),
        "macro_4h": macro_dict.get("4H", "UNKNOWN"),
        "macro_1d": macro_dict.get("1D", "UNKNOWN"),
        "vix": round(vix, 2),
        "dxy": round(dxy, 2),
        "trade_type": trade_type,
        "phy_bias": phy_bias,
        "conf_score": round(conf_score, 2),
        "score_breakdown": score_breakdown,
    }


# ─── Main Strategy Router ──────────────────────────────────────────────────

def check_strategies(prices: dict):
    """Evalúa todas las estrategias (V1-V4 + USDT.D) para cada símbolo."""
    # Lazy imports para evitar circularidad
    from scalp_alert_bot import (
        get_phase, GLOBAL_CACHE, LEVELS,
        is_position_open, open_position, close_position,
        register_signal_event, send_telegram, safe_html,
        alert, get_alert_inline_keyboard, get_main_menu,
    )
    import indicators
    import indicators_swing
    import tracker
    import gemini_analyzer
    import trading_executor
    import alert_manager

    if not prices:
        return

    phase = get_phase()
    usdt_d = prices.get("USDT_D", 8.0)

    for sym in ["ZEC", "TAO", "ETH"]:
        p = prices.get(sym, 0.0)
        rsi = prices.get(f"{sym}_RSI", 50.0)

        if not p or p == 0:
            continue

        bb_u = prices.get(f"{sym}_BB_U", p * 1.01)
        bb_l = prices.get(f"{sym}_BB_L", p * 0.99)
        ema_200 = prices.get(f"{sym}_EMA_200", p)
        atr = prices[f"{sym}_ATR"]
        vol_sma = prices[f"{sym}_VOL_SMA"]
        macro_raw = prices.get(f"{sym}_MACRO")
        if isinstance(macro_raw, dict):
            macro_dict = macro_raw
        else:
            macro_dict = {"consensus": "NEUTRAL", "1H": "UNKNOWN", "4H": "UNKNOWN"}

        macro_status = macro_dict.get("consensus", "NEUTRAL")
        gold_price = prices.get("GOLD", 0.0)
        btc_d = prices.get("BTC_D", 50.0)
        elliott = prices.get(f"{sym}_ELLIOTT", "Analizando...")

        L = LEVELS.get(sym)

        # Bloqueo Institucional (Alineación Macro)
        if phase == "SHORT" and macro_status == "BULL":
            continue
        if phase == "LONG" and macro_status == "BEAR":
            continue

        # Contexto visual de indicadores
        bb_ctx = "🔝 Techo BB" if p >= bb_u * 0.99 else "🩸 Suelo BB" if p <= bb_l * 1.01 else "↕️ Rango"
        trend_ctx = "📈 TENDENCIA ALCISTA" if p > ema_200 else "📉 TENDENCIA BAJISTA"
        macro_ctx = f"🌍 MACRO: {macro_status} (1H:{macro_dict['1H']} | 4H:{macro_dict['4H']})"
        elliott_ctx = f"🌊 ONDA ELLIOTT: {elliott}"

        # --- GUARDIÁN ZEC (ANTI-VOLATILIDAD) ---
        if sym == "ZEC" and phase == "LONG":
            vol_ratio = (atr / p) * 100
            if vol_ratio > 3.5:
                print(f"⚠️ [ZEC Guard] Volatilidad extrema ({vol_ratio:.1f}%). Ignorando Long por seguridad.")
                continue

        # Elliott correction flag (penaliza pero no bloquea)
        elliott_is_correction = "Corrección" in elliott or "Correctiva" in elliott

        # Inicializar SMC variables
        ob_detected = False
        obs = []
        social_adj = 0.0

        vix = prices.get("VIX", 0.0)
        dxy = prices.get("DXY", 0.0)
        trade_type = classify_trade(vix, dxy, macro_status)

        # --- PHY BIAS & FIBONACCI (PTS Intelligence) ---
        phy_bias = indicators.detect_head_and_shoulders(sym)
        fib_levels = indicators.get_fibonacci_levels(sym)

        if phy_bias != "NONE":
            trade_type = "RAPIDA"
            print(f"👁️ [PHY ALERT] {sym} detectó {phy_bias} — forzando modo RAPIDA")

        # --- SOCIAL INTELLIGENCE (con TTL de 600s) ---
        now_ts = time.time()
        cached_social = GLOBAL_CACHE["social_intel"].get(sym, {"score": 0.0, "last_update": 0})

        if now_ts - cached_social["last_update"] > 600:
            try:
                import social_analyzer
                _, score_num = social_analyzer.get_social_intel(sym, p)
                social_adj = round(score_num * 0.5, 2)
                GLOBAL_CACHE["social_intel"][sym] = {"score": social_adj, "last_update": now_ts}
            except Exception as e:
                print(f"⚠️ Error Social Analyzer: {e}")
                social_adj = cached_social["score"]
        else:
            social_adj = cached_social["score"]

        # --- RSI Hook (inercia) ---
        prev_rsi = GLOBAL_CACHE["last_rsi"].get(sym, 50.0)

        # SHORT logic disabled — bot en modo LONG FOCUS institucional

        # ═══════════════════════════════════════════════════════════════════
        # ESTRATEGIA V3: REVERSAL / INTRADIA (AGRESIVA)
        # ═══════════════════════════════════════════════════════════════════
        if phase == "LONG" and p < ema_200:
            reversal_rsi = 28.0 if sym == "TAO" else 26.0
            if rsi <= reversal_rsi:
                register_signal_event(sym.replace("/USDT", ""), prices)
                side = "LONG"
                conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"))
                conf_score = round(conf_score + social_adj, 2)

                sl_dist = max(atr * 2.0, p * 0.008)
                sl = round(p - sl_dist, 2)
                tp1 = round(p + (sl_dist * 2.0), 2)
                tp2 = round(p + (sl_dist * 3.5), 2)

                msg = (f"🏛️ <b>SEÑAL V3: INTRADÍA REVERSAL (15m-1H)</b> 🏛️\n\n"
                       f"🌊 Onda: {elliott}\n"
                       f"⭐ <b>Confiabilidad: {format_confidence(conf_score)}</b>\n\n"
                       f"💬 <i>Buscando el rebote a la media (EMA 200) tras agotamiento.</i>\n\n"
                       f"🪙 <b>{sym}</b> @ ${p:,.2f}\n"
                       f"🎯 TP1: <b>${tp1:,.2f}</b> (2:1)\n"
                       f"🎯 TP2: <b>${tp2:,.2f}</b> (3.5:1)\n"
                       f"🛑 SL: <b>${sl:,.2f}</b>\n\n"
                       f"🎙️ <b>DEBATE DEL CUADRANTE ZENITH:</b>\n"
                       f"{gemini_analyzer.get_ai_consensus(sym, p, 'LONG', rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'), vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias)}")

                if is_position_open(sym, "LONG"):
                    print(f"⏸️ [Position Guard] {sym} LONG (Reversal) ya está abierto — omitiendo señal duplicada")
                    continue

                mid = alert(f"{sym}_v3_reversal", msg, version="V1-TECH",
                            inline_keyboard=get_alert_inline_keyboard(sym, "LONG"))
                if mid:
                    open_position(sym, "LONG")
                    _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, conf_score, "v3_reversal", "LONG", rsi_threshold=reversal_rsi)
                    tracker.log_trade(sym, "LONG", p, tp1, tp2, sl, mid, "V1-TECH", rsi, bb_ctx, atr, elliott, conf_score, alert_type="v3_reversal", trigger_conditions=_tc)
                    gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")
                    register_signal_event(sym.replace("/USDT", ""), prices)

        # ═══════════════════════════════════════════════════════════════════
        # ESTRATEGIA V1: Long V1 (Trend Alcista + Near BB + RSI 42 + RSI Rising)
        # ═══════════════════════════════════════════════════════════════════
        elif phase == "LONG" and p > ema_200 and "BB" in bb_ctx:
            entry_rsi = 48.0 if sym == "ZEC" else 42.0
            if rsi <= entry_rsi:
                if rsi < prev_rsi:
                    continue

                if is_position_open(sym, "LONG"):
                    print(f"⏸️ [Position Guard] {sym} LONG ya está abierto — omitiendo señal duplicada")
                    continue

                sl_dist = max(atr * 2.0, p * 0.007)
                sl = round(p - sl_dist, 2)
                tp1 = round(p + (sl_dist * 2.0), 2)
                tp2 = round(p + (sl_dist * 3.5), 2)
                caution = "⚠️ *PRECAUCIÓN: USDT.D ALTO*\n" if usdt_d > 8.05 else ""

                side = "LONG"
                conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"))
                conf_score = round(conf_score + social_adj, 2)

                if conf_score < 4:
                    print(f"⏩ [V12-Audit] Señal {sym} ignorada (Score {conf_score} < 4)")
                    continue

                badge = get_confluence_badge(conf_score)
                trade_label = "⚡ RAPIDA (VIX alto)" if trade_type == "RAPIDA" else "📈 SWING"

                msg = (f"{badge}\n\n"
                       f"🚀 <b>SEÑAL V1.6.2 SCALP (15m)</b> 🚀\n\n"
                       f"🌍 {macro_ctx}\n"
                       f"🌊 {elliott_ctx}\n"
                       f"🛡️ <b>SMC SHIELD:</b> {'🟢 DETECTED' if ob_detected else '⚪ NONE'}\n\n"
                       f"📈 15m Trend: {trend_ctx}\n"
                       f"💰 Volatilidad: {atr:,.2f} USD\n\n"
                       f"📊 <b>ESTADO TÉCNICO:</b>\n"
                       f"• RSI: {(rsi or 0.0):.1f} | BB: {bb_ctx}\n"
                       f"• EMA 200: ${(ema_200 or 0.0):,.2f}\n"
                       f"⭐ <b>Confiabilidad: {format_confidence(conf_score)}</b>\n\n"
                       f"🌍 <b>CONTEXTO MACRO:</b>\n"
                       f"• USDT.D: {usdt_d}% | BTC.D: {btc_d}%\n"
                       f"• DXY: {dxy:.2f} | VIX: {vix:.1f}\n"
                       f"• Tipo Operación: {trade_label}\n\n"
                       f"🪙 <b>{sym}</b> @ ${(p or 0.0):,.2f}\n"
                       f"🎯 TP1: <b>${(tp1 or 0.0):,.2f}</b> (2:1)\n"
                       f"🎯 TP2: <b>${(tp2 or 0.0):,.2f}</b> (3:1)\n"
                       f"🛑 SL: <b>${(sl or 0.0):,.2f}</b>\n\n"
                       f"🎙️ <b>DEBATE DEL CUADRANTE ZENITH:</b>\n"
                       f"{gemini_analyzer.get_ai_consensus(sym, p, 'LONG', rsi, usdt_d, spy=prices.get('SPY', 0), oil=prices.get('OIL', 0), nvda=prices.get('NVDA', 0), pltr=prices.get('PLTR', 0), vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias)}")
                mid = alert(f"{sym}_v1_long", msg, version="V1-TECH",
                            inline_keyboard=get_alert_inline_keyboard(sym, "LONG"))
                if mid:
                    open_position(sym, "LONG")
                    _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, conf_score, "v1_long", "LONG", rsi_threshold=entry_rsi)
                    tracker.log_trade(sym, "LONG", p, tp1, tp2, sl, mid, "V1-TECH", rsi, bb_ctx, atr, elliott, conf_score, alert_type="v1_long", trigger_conditions=_tc)
                    gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")
                    register_signal_event(sym.replace("/USDT", ""), prices)

                # --- ESTRATEGIA V2-AI: CONSENSUS MASTER (HYBRID) ---
                decision, reason, full_analysis = gemini_analyzer.get_ai_decision(sym, p, phase, rsi, bb_u, bb_l, "V2-AI", usdt_d, conf_score, vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, fib_levels=fib_levels)

                if decision == "CONFIRM":
                    if is_position_open(sym, side):
                        print(f"⏸️ [Position Guard] {sym} {side} (V2-AI) ya está abierto — omitiendo ejecución binance")
                        continue

                    conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"), ob_detected=ob_detected)
                    conf_score = round(conf_score + social_adj, 2)
                    badge = get_confluence_badge(conf_score)

                    # --- V6.0 MULTI-TP CALCULATION ---
                    dist_sl = abs(p - sl)
                    tp1 = round(p + (dist_sl * 2.0) if side == "LONG" else p - (dist_sl * 2.0), 2)
                    tp2 = round(p + (dist_sl * 4.0) if side == "LONG" else p - (dist_sl * 4.0), 2)
                    tp3 = round(p + (dist_sl * 7.0) if side == "LONG" else p - (dist_sl * 7.0), 2)

                    # --- V6.0 EXECUTION LAYER (BINANCE) ---
                    exec_report = "⚪ NO EJECUTADO (Bajo Conf_Score)"
                    if conf_score >= 4:
                        if not GLOBAL_CACHE["executor"]:
                            GLOBAL_CACHE["executor"] = trading_executor.ZenithExecutor()

                        res_exec = GLOBAL_CACHE["executor"].execute_bracket_order(sym, side, p, tp1, tp2, sl, tp3=tp3)
                        exec_report = f"💸 <b>BINANCE V6:</b> {res_exec.get('status')} (ID: {res_exec.get('id')})"

                    msg = (f"{badge}\n\n"
                           f"🚀 <b>ZENITH V6: THE VOLUME PROPHET</b>\n"
                           f"🛡️ <b>SMC SHIELD:</b> {'🟢 DETECTED' if (ob_detected if 'ob_detected' in locals() else False) else '⚪ NONE'}\n"
                           f"🧲 <b>POC MAGNET:</b> ${prices.get(f'{sym}_POC', 0.0):,.2f}\n"
                           f"{exec_report}\n\n"
                           f"📊 <b>ESTADO TÉCNICO:</b>\n"
                           f"• Score Confluencia: {conf_score}/5\n"
                           f"⭐ <b>Confiabilidad: {format_confidence(conf_score + 1)}</b>\n\n"
                           f"💡 <b>RAZÓN IA:</b> {safe_html(reason)}\n\n"
                           f"🪙 <b>{sym}</b> @ ${(p or 0.0):,.2f}\n"
                           f"🎯 TP1 (50%): <b>${(tp1 or 0.0):,.2f}</b>\n"
                           f"🎯 TP2 (25%): <b>${(tp2 or 0.0):,.2f}</b>\n"
                           f"🎯 TP3 (25%): <b>${(tp3 or 0.0):,.2f}</b>\n"
                           f"🛑 SL: <b>${(sl or 0.0):,.2f}</b>\n\n"
                           f"🎙️ <b>DEBATE DEL CUADRANTE ZENITH:</b>\n"
                           f"{gemini_analyzer.get_ai_consensus(sym, p, phase, rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'), vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias)}")
                    mid = alert(f"{sym}_v2_ai_{phase}", msg, version="V2-AI",
                                inline_keyboard=get_alert_inline_keyboard(sym, phase))
                    if mid:
                        open_position(sym, phase)
                        _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, conf_score, "v2_ai_long", phase, rsi_threshold=entry_rsi)
                        tracker.log_trade(sym, phase, p, tp1, tp2, sl, mid, "V2-AI", rsi, bb_ctx, atr, elliott, conf_score, ai_analysis=full_analysis, macro_bias=macro_status, alert_type="v2_ai_long", trigger_conditions=_tc)
                        register_signal_event(sym.replace("/USDT", ""), prices)

        # ═══════════════════════════════════════════════════════════════════
        # ESTRATEGIA V4: EMA 200 BOUNCE (MEAN REVERSION)
        # ═══════════════════════════════════════════════════════════════════
        elif phase == "LONG" and p > ema_200 * V4_EMA_PROXIMITY_MIN and p <= ema_200 * V4_EMA_PROXIMITY_MAX:
            rsi_high = V4_RSI_HIGH_ZEC if sym == "ZEC" else V4_RSI_HIGH
            if V4_RSI_LOW <= rsi <= rsi_high and rsi > prev_rsi:
                if is_position_open(sym, "LONG"):
                    print(f"⏸️ [Position Guard] {sym} LONG (V4-EMA) ya abierto")
                    continue

                side = "LONG"
                conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"), ob_detected=ob_detected)
                conf_score = round(conf_score + social_adj, 2)

                if conf_score < V4_MIN_CONFLUENCE:
                    print(f"⏩ [V4-EMA] {sym} ignorada (Score {conf_score} < {V4_MIN_CONFLUENCE})")
                    continue

                register_signal_event(sym.replace("/USDT", ""), prices)
                badge = get_confluence_badge(conf_score)
                trade_label = "⚡ RAPIDA" if trade_type == "RAPIDA" else "📈 SWING"
                ema_dist_pct = ((p - ema_200) / ema_200) * 100

                sl_dist = max(atr * V4_ATR_SL_MULT, p * 0.007)
                sl = round(p - sl_dist, 2)
                tp1 = round(p + (sl_dist * 2.0), 2)
                tp2 = round(p + (sl_dist * 3.0), 2)

                msg = (f"{badge}\n\n"
                       f"📐 <b>SEÑAL V4: EMA 200 BOUNCE (15m-1H)</b> 📐\n\n"
                       f"🌊 {elliott_ctx}\n"
                       f"📈 Proximidad EMA200: {ema_dist_pct:.2f}%\n"
                       f"{macro_ctx}\n"
                       f"🛡️ <b>SMC SHIELD:</b> {'🟢 DETECTED' if ob_detected else '⚪ NONE'}\n\n"
                       f"📊 <b>ESTADO TECNICO:</b>\n"
                       f"• RSI: {rsi:.1f} (prev: {prev_rsi:.1f}) | {bb_ctx}\n"
                       f"• EMA 200: ${ema_200:,.2f}\n"
                       f"⭐ <b>Confiabilidad: {format_confidence(conf_score)}</b>\n\n"
                       f"🌍 <b>CONTEXTO MACRO:</b>\n"
                       f"• USDT.D: {usdt_d}% | BTC.D: {btc_d}%\n"
                       f"• DXY: {dxy:.2f} | VIX: {vix:.1f}\n"
                       f"• Tipo: {trade_label}\n\n"
                       f"🪙 <b>{sym}</b> @ ${p:,.2f}\n"
                       f"🎯 TP1: <b>${tp1:,.2f}</b> (2:1)\n"
                       f"🎯 TP2: <b>${tp2:,.2f}</b> (3:1)\n"
                       f"🛑 SL: <b>${sl:,.2f}</b>")

                mid = alert(f"{sym}_v4_ema_bounce", msg, version="V1-TECH",
                            cooldown=V4_COOLDOWN,
                            inline_keyboard=get_alert_inline_keyboard(sym, "LONG"))
                if mid:
                    open_position(sym, "LONG")
                    _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, conf_score, "v4_ema_bounce", "LONG", rsi_threshold=rsi_high)
                    tracker.log_trade(sym, "LONG", p, tp1, tp2, sl, mid, "V1-TECH", rsi, bb_ctx, atr, elliott, conf_score, alert_type="v4_ema_bounce", trigger_conditions=_tc)
                    gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")
                    register_signal_event(sym.replace("/USDT", ""), prices)

        # ═══════════════════════════════════════════════════════════════════
        # ESTRATEGIA V2: AI ENHANCED (LONG ONLY)
        # ═══════════════════════════════════════════════════════════════════
        if rsi <= 40:
            side = "LONG"
            df = indicators.get_df(sym, "1h")
            obs = indicators_swing.find_order_blocks(df)
            ob_detected = any(ob["type"] == "BULL_OB" and p >= ob["low"] * 0.99 and p <= ob["high"] * 1.01 for ob in obs)

            is_valid_trend = (side == "LONG" and p > ema_200) or (side == "SHORT" and p < ema_200)

            if is_valid_trend:
                dec_cons, reason_cons, full_cons = gemini_analyzer.get_ai_decision(sym, p, side, rsi, bb_u, bb_l, version="V1-TECH", usdt_d=usdt_d, vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, fib_levels=fib_levels)
                dec_scalp, reason_scalp, full_scalp = gemini_analyzer.get_ai_decision(sym, p, side, rsi, bb_u, bb_l, version="V2-AI", usdt_d=usdt_d, vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, fib_levels=fib_levels)
                full_analysis = f"Consenso:\n{full_cons}\n\n{full_scalp}"
            else:
                dec_cons, dec_scalp, full_analysis = "REJECT", "Contra tendencia mayor", ""

            if dec_cons == "CONFIRM" or dec_scalp == "CONFIRM":
                if is_position_open(sym, side):
                    print(f"⏸️ [Position Guard] {sym} {side} (Consenso IA) ya está abierto — omitiendo señal duplicada")
                    continue

                is_consensus = (dec_cons == "CONFIRM" and dec_scalp == "CONFIRM")
                sl = L.get('sl_short', p * 1.01) if side == "SHORT" else L.get('long_sl', p * 0.99)
                dist_sl = abs(p - sl)
                tp1 = round(p - (dist_sl * 2.0) if side == "SHORT" else p + (dist_sl * 2.0), 2)
                tp2 = round(p - (dist_sl * 3.0) if side == "SHORT" else p + (dist_sl * 3.0), 2)

                header = "🔹💎🔹 <b>CONSENSO IA</b>" if is_consensus else "🤖 <b>IA CONFIRMADA</b>"
                icon = "💎" if side == "LONG" else "💀"
                caution = "⚠️ <b>CONTEXTO TENSO</b>\n" if side == "LONG" and usdt_d > 8.05 else ""

                final_reason = reason_scalp if dec_scalp == "CONFIRM" else reason_cons
                if is_consensus:
                    final_reason = f"Acuerdo Total: {reason_cons} + {reason_scalp}"

                msg = (f"{header} ({side})\n"
                       f"{caution}"
                       f"🛡️ <b>SMC SHIELD:</b> {'🟢 DETECTED' if (ob_detected if 'ob_detected' in locals() else False) else '⚪ NONE'}\n\n"
                       f"💬 <i>{safe_html(final_reason)}</i>\n\n"
                       f"🪙 <b>{sym}</b> @ ${(p or 0.0):,.2f}\n"
                       f"📊 RSI: {(rsi or 0.0):.1f} | {bb_ctx}\n"
                       f"📉 USDT.D: {(usdt_d or 0.0):.2f}%\n"
                       f"🎯 TP1: <b>${(tp1 or 0.0):,.2f}</b> (2:1)\n"
                       f"🎯 TP2: <b>${(tp2 or 0.0):,.2f}</b> (3:1)\n"
                       f"🛑 SL: <b>${(sl or 0.0):,.2f}</b>\n\n"
                       f"🎙️ <b>DEBATE DEL CUADRANTE ZENITH:</b>\n"
                       f"{gemini_analyzer.get_ai_consensus(sym, p, side, rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'), vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias)}")

                mid = alert(f"{sym}_v2_short", msg, version="V2-AI")
                if mid:
                    _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, 5 if is_consensus else 4, "v2_ai_consensus", side, rsi_threshold=40.0)
                    tracker.log_trade(sym, phase, p, tp1, tp2, sl, mid, "V2-AI", rsi, bb_ctx, atr, elliott, 5 if is_consensus else 4, ai_analysis=full_analysis, macro_bias=macro_status, alert_type="v2_ai_consensus", trigger_conditions=_tc)
                    gemini_analyzer.log_alert_to_context(sym, side, p, rsi, tp1, sl, "V2-AI")

        # ═══════════════════════════════════════════════════════════════════
        # ALERTAS ESTRATÉGICAS: USDT.D BREAKOUT (V15: Institutional Grade)
        # ═══════════════════════════════════════════════════════════════════
        for level in [8.08, 8.044, 7.953]:
            if abs(usdt_d - level) < 0.005:
                alert_key = f"usdtd_break_{level}"
                hit_count = alert_manager.get_alert_hit_count(alert_key) + 1

                prev_usdt_d = GLOBAL_CACHE["prices"].get("USDT_D_PREV", usdt_d)
                direction = "🔺 SUBIENDO" if usdt_d >= prev_usdt_d else "🔻 CAYENDO"

                if level == 8.08:
                    nivel_nombre = "🚨 ZONA DE PÁNICO"
                    desc_corta = "Presión vendedora institucional máxima"
                    impacto = "BEAR para crypto. Capital huyendo a stablecoins."
                    accion_zec = "⛔ EVITAR longs. Esperar rechazo confirmado en este nivel."
                    accion_btc = "👀 BTC puede rebotear si este nivel actúa como resistencia de USDT.D."
                    emoji_nivel = "🔴"
                elif level == 8.044:
                    nivel_nombre = "⚠️ ZONA DE TENSIÓN"
                    desc_corta = "Incertidumbre y probable rotación"
                    impacto = "NEUTRAL/BEAR. Mercado buscando dirección."
                    accion_zec = "⏳ Reducir tamaño de posición. Esperar confirmación macro."
                    accion_btc = "📊 BTC Dominancia clave: si sube junto a USDT.D, hedge activo."
                    emoji_nivel = "🟡"
                else:
                    nivel_nombre = "✅ ZONA DE EUFORIA"
                    desc_corta = "Capital fluyendo hacia activos de riesgo"
                    impacto = "BULL para crypto. Instituciones entrando al mercado."
                    accion_zec = "🚀 OPORTUNIDAD: Buscar setups de acumulación en ZEC/TAO."
                    accion_btc = "💎 BTC en zona de acumulación. Alerta V1 probable en próximas horas."
                    emoji_nivel = "🟢"

                if hit_count == 1:
                    recurrence_ctx = ""
                    urgency_prefix = ""
                elif hit_count == 2:
                    recurrence_ctx = (
                        f"\n\n🔁 <b>PERSISTENCIA DETECTADA</b> (2ª vez en sesión)\n"
                        f"<i>El nivel {level}% se mantiene como zona clave. "
                        f"Mercado indeciso — confirmar ruptura antes de actuar.</i>"
                    )
                    urgency_prefix = "⚡ "
                elif hit_count == 3:
                    recurrence_ctx = (
                        f"\n\n🧠 <b>NIVEL DEFENDIDO 3 VECES — ALERTA NIVEL 2</b>\n"
                        f"<i>Este nivel ha sido tocado {hit_count}x. Esto indica que "
                        f"{'las instituciones están ABSORBIENDO la venta' if direction == '🔻 CAYENDO' else 'existe RESISTENCIA INSTITUCIONAL REAL en este nivel'}. "
                        f"Probabilidad de breakout definitivo aumenta con cada toque.</i>"
                    )
                    urgency_prefix = "🚨🚨 "
                else:
                    recurrence_ctx = (
                        f"\n\n🔥 <b>TOQUE #{hit_count} — NIVEL CRÍTICO INSTITUCIONAL</b>\n"
                        f"<i>Recurrencia extrema. Este nivel ha actuado como imán de precio. "
                        f"El siguiente movimiento será de alta magnitud. "
                        f"{'SHORT activo si rompe al alza definitivamente.' if level == 8.08 else 'LONG de alta conviction si rompe a la baja confirmado.'}</i>"
                    )
                    urgency_prefix = "🔥🔥 "

                zec_rsi = prices.get("ZEC_RSI", 50.0)
                tao_rsi = prices.get("TAO_RSI", 50.0)
                btc_rsi = prices.get("BTC_RSI", 50.0)

                msg = (
                    f"{urgency_prefix}{emoji_nivel} <b>USDT.D INSTITUCIONAL: {nivel_nombre}</b>\n\n"
                    f"📍 Nivel: <b>{level}%</b> {direction}\n"
                    f"📊 Actual: <b>{usdt_d:.3f}%</b> | BTC.D: <b>{btc_d:.1f}%</b>\n"
                    f"💨 VIX: {vix:.1f} | DXY: {dxy:.2f}\n\n"
                    f"🔬 <b>DIAGNÓSTICO:</b>\n"
                    f"<i>{desc_corta}</i>\n"
                    f"📈 Impacto: {impacto}\n\n"
                    f"📊 <b>PULSO DE ACTIVOS:</b>\n"
                    f"• BTC RSI: {btc_rsi:.1f} | BB: {bb_ctx}\n"
                    f"• ZEC RSI: {zec_rsi:.1f}\n"
                    f"• TAO RSI: {tao_rsi:.1f}\n\n"
                    f"🎯 <b>PLAYBOOK INSTITUCIONAL:</b>\n"
                    f"• {accion_zec}\n"
                    f"• {accion_btc}"
                    f"{recurrence_ctx}"
                )
                alert(alert_key, msg, version="MACRO", cooldown=3600)
