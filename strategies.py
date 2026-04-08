"""
strategies.py — Lógica de estrategias V1-V4 + V1-SHORT + USDT.D Institucional

Extraído de scalp_alert_bot.py para mantener archivos < 600 líneas.
Contiene: check_strategies(), calculate_confluence_score(), classify_trade(),
build_trigger_conditions(), get_confluence_badge(), format_confidence(),
_check_usdtd_breakout()
"""

import time
import episode_memory as _em
from config import (
    V4_EMA_PROXIMITY_MAX, V4_EMA_PROXIMITY_MIN, V4_RSI_LOW,
    V4_RSI_HIGH, V4_RSI_HIGH_ZEC, V4_MIN_CONFLUENCE,
    V4_ATR_SL_MULT, V4_COOLDOWN, V4_EMA_PROX_MAP,
    RSI_SHORT_ENTRY, SHORT_MIN_CONFLUENCE, SHORT_REGIMES,
    SHORT_EMA_SLOPE_MIN, RVOL_MIN_ENTRY,
)


# ─── Confluence Score ───────────────────────────────────────────────────────

def calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d=8.0,
                               side="LONG", elliott="", spy=0.0, oil=0.0,
                               ob_detected=False, funding_signal=0):
    """
    Calcula un score de confluencia técnica + Macro (0-7 puntos).
    V3.0: SMC (Order Block Detection).
    V4.0 Phase 2: Funding Rate Contrarian signal.
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

    # --- 8. FUNDING RATE CONTRARIAN (Phase 2) ---
    score += funding_signal

    return min(7, score)


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
    from risk_manager import circuit_breaker
    import market_intel
    import indicators_swing
    import tracker
    import gemini_analyzer
    import trading_executor
    import alert_manager

    if not prices:
        return

    # ── Circuit Breaker Gate ─────────────────────────────────────────────
    can_trade, cb_reason, cb_multiplier = circuit_breaker.can_trade()
    if not can_trade:
        print(f"🚨 [CircuitBreaker] {cb_reason} — Estrategias bloqueadas")
        return

    phase = get_phase()
    usdt_d = prices.get("USDT_D", 8.0)

    # ── Phase 2: Market Intelligence — Funding rates (batch, 1 call) ───
    try:
        funding_data = market_intel.get_funding_rates(["ZEC", "TAO", "ETH", "HBAR", "DOGE"])
    except Exception:
        funding_data = {}

    for sym in ["ZEC", "TAO", "ETH", "HBAR", "DOGE"]:
        p = prices.get(sym, 0.0)
        rsi = prices.get(f"{sym}_RSI", 50.0)

        if not p or p == 0:
            continue

        bb_u = prices.get(f"{sym}_BB_U", p * 1.01)
        bb_l = prices.get(f"{sym}_BB_L", p * 0.99)
        ema_200 = prices.get(f"{sym}_EMA_200", p)
        atr = prices.get(f"{sym}_ATR", 0.0)
        vol_sma = prices.get(f"{sym}_VOL_SMA", 0.0)
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

        # --- SOCIAL INTELLIGENCE (TTL controlado por TTL_SOCIAL en scalp_alert_bot) ---
        now_ts = time.time()
        cached_social = GLOBAL_CACHE["social_intel"].get(sym, {"score": 0.0, "last_update": 0})
        from scalp_alert_bot import TTL_SOCIAL

        if now_ts - cached_social["last_update"] > TTL_SOCIAL:
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

        # ── Phase 2: Regime Detection ─────────────────────────────────────
        try:
            regime_info = market_intel.detect_regime(sym)
            regime = regime_info.get("regime", "TRENDING_UP")
        except Exception:
            regime = "TRENDING_UP"  # Safe default: no suprime senales

        if regime == "RANGING":
            print(f"⏸️ [Regime] {sym} en RANGING — suprimiendo senales")
            continue

        # ═══════════════════════════════════════════════════════════════════
        # ESTRATEGIA V1-SHORT: Trend Bajista (v2.1 — siempre activa)
        # NO depende de phase.txt — shorts operan independientemente
        # Filtros: RSI >= 55, EMA200 declining, regime TRENDING_DOWN/VOLATILE
        # Risk SHORT: RAPIDA forzado (max 0.75% via risk_manager)
        # ═══════════════════════════════════════════════════════════════════
        if p < ema_200 and regime in SHORT_REGIMES:
            short_rsi = RSI_SHORT_ENTRY  # 55.0 (was 62)
            if rsi >= short_rsi and rsi < prev_rsi:  # RSI falling = confirma presión bajista
                if is_position_open(sym, "SHORT"):
                    print(f"⏸️ [Position Guard] {sym} SHORT ya está abierto")
                else:
                    # EMA200 slope check (must be declining)
                    ema_slope_ok = True
                    try:
                        df_1h = indicators.get_df(sym, "1h")
                        if df_1h is not None and len(df_1h) > 5:
                            ema_vals = df_1h['close'].ewm(span=200, adjust=False).mean()
                            slope = (ema_vals.iloc[-1] - ema_vals.iloc[-6]) / ema_vals.iloc[-6]
                            ema_slope_ok = slope < SHORT_EMA_SLOPE_MIN
                    except Exception:
                        pass

                    if not ema_slope_ok:
                        print(f"⏩ [V1-SHORT] {sym}: EMA200 no declina — skip")
                    else:
                        side = "SHORT"
                        funding_signal = market_intel.get_funding_signal(sym, side, funding_data)

                        # Funding: bonus en confluencia, NO hard gate
                        fr_data = funding_data.get(sym, {})
                        fr_rate = fr_data.get("rate", 0.0)

                        conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"), ob_detected=ob_detected, funding_signal=funding_signal)
                        conf_score = round(conf_score + social_adj, 2)

                        if conf_score < SHORT_MIN_CONFLUENCE:  # 3 (was 4)
                            print(f"⏩ [V1-SHORT] {sym} ignorada (Score {conf_score} < {SHORT_MIN_CONFLUENCE})")
                        else:
                            register_signal_event(sym.replace("/USDT", ""), prices)
                            badge = get_confluence_badge(conf_score)
                            trade_type_short = "RAPIDA"

                            sl_dist = max(atr * 2.0, p * 0.007)
                            sl = round(p + sl_dist, 2)
                            tp1 = round(p - (sl_dist * 2.0), 2)
                            tp2 = round(p - (sl_dist * 3.5), 2)

                            funding_info = f"\n🏦 Funding: {fr_rate*100:+.4f}%" if fr_rate != 0 else ""

                            msg = (f"{badge}\n\n"
                                   f"🔻 <b>SEÑAL V1-SHORT v2.1 (15m)</b> 🔻\n\n"
                                   f"🌍 {macro_ctx}\n"
                                   f"🌊 {elliott_ctx}{funding_info}\n\n"
                                   f"📊 <b>ESTADO TÉCNICO:</b>\n"
                                   f"• RSI: {rsi:.1f} (cayendo) | BB: {bb_ctx}\n"
                                   f"• EMA 200: ${ema_200:,.2f} (declinando)\n"
                                   f"• Régimen: {regime}\n"
                                   f"⭐ <b>Confiabilidad: {format_confidence(conf_score)}</b>\n\n"
                                   f"🪙 <b>{sym}</b> @ ${p:,.2f}\n"
                                   f"🎯 TP1: <b>${tp1:,.2f}</b> (2:1)\n"
                                   f"🎯 TP2: <b>${tp2:,.2f}</b> (3.5:1)\n"
                                   f"🛑 SL: <b>${sl:,.2f}</b>\n"
                                   f"⚡ Tipo: RAPIDA (SHORT = 75% risk)")

                            mid = alert(f"{sym}_v1_short", msg, version="V1-TECH",
                                        inline_keyboard=get_alert_inline_keyboard(sym, "SHORT"))
                            if mid:
                                open_position(sym, "SHORT")
                                _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type_short, phy_bias, conf_score, "v1_short", "SHORT", rsi_threshold=short_rsi)
                                tracker.log_trade(sym, "SHORT", p, tp1, tp2, sl, mid, "V1-TECH", rsi, bb_ctx, atr, elliott, conf_score, alert_type="v1_short", trigger_conditions=_tc)
                                gemini_analyzer.log_alert_to_context(sym, "SHORT", p, rsi, tp1, sl, "V1-TECH")
                                register_signal_event(sym.replace("/USDT", ""), prices)

        # ═══════════════════════════════════════════════════════════════════
        # ESTRATEGIA V3: REVERSAL / INTRADIA (AGRESIVA)
        # ═══════════════════════════════════════════════════════════════════
        if phase == "LONG" and p < ema_200 and regime in ("VOLATILE", "TRENDING_DOWN"):
            reversal_rsi = 28.0 if sym == "TAO" else 26.0
            if rsi <= reversal_rsi:
                register_signal_event(sym.replace("/USDT", ""), prices)
                side = "LONG"
                funding_signal = market_intel.get_funding_signal(sym, side, funding_data)
                conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"), funding_signal=funding_signal)
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
        # ESTRATEGIA V1: Long V1 (Trend Alcista + RSI 45 + RSI Rising)
        # v2.1: BB touch ahora es bonus en confluencia, no hard gate
        # ═══════════════════════════════════════════════════════════════════
        elif phase == "LONG" and p > ema_200 and regime in ("TRENDING_UP", "VOLATILE"):
            entry_rsi = 48.0 if sym == "ZEC" else 45.0  # was 42
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
                funding_signal = market_intel.get_funding_signal(sym, side, funding_data)
                conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"), funding_signal=funding_signal)
                conf_score = round(conf_score + social_adj, 2)

                if conf_score < 4:
                    # Log episodio filtrado (para near-miss análisis)
                    _bb_pos = "LOWER" if p <= bb_l * 1.01 else "UPPER" if p >= bb_u * 0.99 else "MID"
                    _ema_trend = "ABOVE" if p > ema_200 else "BELOW"
                    _atr_pct = round((atr / p * 100) if p else 0, 3)
                    _em.log_episode(sym, "V1-TECH", "FILTERED", rsi, usdt_d, _bb_pos, _ema_trend, int(conf_score), _atr_pct)
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
                    _trade_db_id = tracker.log_trade(sym, "LONG", p, tp1, tp2, sl, mid, "V1-TECH", rsi, bb_ctx, atr, elliott, conf_score, alert_type="v1_long", trigger_conditions=_tc)
                    # Log episodio vinculando con el ID real del trade en BD
                    _bb_pos = "LOWER" if p <= bb_l * 1.01 else "UPPER" if p >= bb_u * 0.99 else "MID"
                    _ema_trend = "ABOVE" if p > ema_200 else "BELOW"
                    _atr_pct = round((atr / p * 100) if p else 0, 3)
                    _ep_id = _em.log_episode(sym, "V1-TECH", "LONG", rsi, usdt_d, _bb_pos, _ema_trend, int(conf_score), _atr_pct)
                    # Guardar ep_id en caché para fill_outcome al cerrar
                    GLOBAL_CACHE.setdefault("episode_ids", {})[_trade_db_id] = _ep_id
                    gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")
                    register_signal_event(sym.replace("/USDT", ""), prices)

                # --- ESTRATEGIA V2-AI: CONSENSUS MASTER (HYBRID) ---
                decision, reason, full_analysis = gemini_analyzer.get_ai_decision(sym, p, phase, rsi, bb_u, bb_l, "V2-AI", usdt_d, conf_score, vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, fib_levels=fib_levels)

                if decision == "CONFIRM":
                    if is_position_open(sym, side):
                        print(f"⏸️ [Position Guard] {sym} {side} (V2-AI) ya está abierto — omitiendo ejecución binance")
                        continue

                    conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"), ob_detected=ob_detected, funding_signal=funding_signal)
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
        elif phase == "LONG" and p > ema_200 * V4_EMA_PROXIMITY_MIN and p <= ema_200 * V4_EMA_PROX_MAP.get(sym, V4_EMA_PROXIMITY_MAX) and regime == "TRENDING_UP":
            rsi_high = V4_RSI_HIGH_ZEC if sym == "ZEC" else V4_RSI_HIGH
            if V4_RSI_LOW <= rsi <= rsi_high and rsi > prev_rsi:
                if is_position_open(sym, "LONG"):
                    print(f"⏸️ [Position Guard] {sym} LONG (V4-EMA) ya abierto")
                    continue

                side = "LONG"
                funding_signal = market_intel.get_funding_signal(sym, side, funding_data)
                conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"), ob_detected=ob_detected, funding_signal=funding_signal)
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
        # ESTRATEGIA V5: MOMENTUM BREAKOUT (RSI Midline Cross)
        # Dispara cuando el RSI cruza arriba de 50 desde abajo → cambio de momentum.
        # Más activo que V1 (no requiere RSI < 45): opera en mercados normales.
        # Confluencia mínima: 3 (vs 4 de V1). Cooldown: 20 min.
        # ═══════════════════════════════════════════════════════════════════
        from config import V5_MOMENTUM_MIN_CONF, V5_MOMENTUM_COOLDOWN
        if (phase == "LONG" and p > ema_200 and
                regime != "RANGING" and
                prev_rsi < 50.0 <= rsi):
            if is_position_open(sym, "LONG"):
                print(f"⏸️ [Position Guard] {sym} LONG (V5-MOMENTUM) ya abierto")
            else:
                side = "LONG"
                funding_signal = market_intel.get_funding_signal(sym, side, funding_data)
                conf_score = calculate_confluence_score(
                    p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott,
                    spy=prices.get("SPY"), oil=prices.get("OIL"),
                    ob_detected=ob_detected, funding_signal=funding_signal)
                conf_score = round(conf_score + social_adj, 2)

                if conf_score < V5_MOMENTUM_MIN_CONF:
                    print(f"⏩ [V5-MOMENTUM] {sym} ignorada (Score {conf_score} < {V5_MOMENTUM_MIN_CONF})")
                else:
                    register_signal_event(sym.replace("/USDT", ""), prices)
                    badge = get_confluence_badge(conf_score)
                    trade_label = "⚡ RAPIDA" if trade_type == "RAPIDA" else "📈 SWING"

                    # Volume confirmation (informativo, no bloquea)
                    current_vol = prices.get(f"{sym}_VOL", 0.0)
                    rvol = (current_vol / vol_sma) if (vol_sma and vol_sma > 0) else 1.0
                    vol_confirm = f"🔥 VOLUMEN CONFIRMADO ({rvol:.1f}x)" if rvol >= 1.2 else f"↔️ Vol normal ({rvol:.1f}x)"

                    sl_dist = max(atr * 2.0, p * 0.007)
                    sl  = round(p - sl_dist, 2)
                    tp1 = round(p + (sl_dist * 2.0), 2)
                    tp2 = round(p + (sl_dist * 3.5), 2)

                    msg = (f"{badge}\n\n"
                           f"⚡ <b>SEÑAL V5: MOMENTUM BREAKOUT</b> ⚡\n"
                           f"<i>RSI cruzó el nivel 50 → momentum girando alcista</i>\n\n"
                           f"📈 RSI: {prev_rsi:.1f} → <b>{rsi:.1f}</b> (cruce de 50)\n"
                           f"📊 {vol_confirm}\n"
                           f"🌍 {macro_ctx}\n"
                           f"🌊 {elliott_ctx}\n\n"
                           f"📊 <b>ESTADO TÉCNICO:</b>\n"
                           f"• RSI: {rsi:.1f} | BB: {bb_ctx}\n"
                           f"• EMA 200: ${ema_200:,.2f} | Régimen: {regime}\n"
                           f"• USDT.D: {usdt_d:.2f}% | VIX: {vix:.1f}\n"
                           f"⭐ <b>Confiabilidad: {format_confidence(conf_score)}</b>\n\n"
                           f"🪙 <b>{sym}</b> @ ${p:,.2f}\n"
                           f"🎯 TP1: <b>${tp1:,.2f}</b> (2:1)\n"
                           f"🎯 TP2: <b>${tp2:,.2f}</b> (3.5:1)\n"
                           f"🛑 SL: <b>${sl:,.2f}</b>\n"
                           f"⚡ Tipo: {trade_label}")

                    mid = alert(f"{sym}_v5_momentum", msg, version="V1-TECH",
                                cooldown=V5_MOMENTUM_COOLDOWN,
                                inline_keyboard=get_alert_inline_keyboard(sym, "LONG"))
                    if mid:
                        open_position(sym, "LONG")
                        _tc = build_trigger_conditions(
                            sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d,
                            vix, dxy, macro_dict, macro_status, atr, elliott,
                            ob_detected, social_adj, trade_type, phy_bias, conf_score,
                            "v5_momentum", "LONG", rsi_threshold=50.0)
                        tracker.log_trade(sym, "LONG", p, tp1, tp2, sl, mid, "V1-TECH",
                                          rsi, bb_ctx, atr, elliott, conf_score,
                                          alert_type="v5_momentum", trigger_conditions=_tc)
                        gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")
                        register_signal_event(sym.replace("/USDT", ""), prices)

        # USDT.D Breakout (extracted to usdtd_alerts.py)
        import usdtd_alerts
        usdtd_alerts.check_usdtd_breakout(usdt_d, btc_d, vix, dxy, bb_ctx,
                                           prices, alert, alert_manager,
                                           GLOBAL_CACHE)
