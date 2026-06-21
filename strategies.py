"""
strategies.py — Lógica de estrategias V1-V4 + V1-SHORT + USDT.D Institucional

Extraído de scalp_alert_bot.py para mantener archivos < 600 líneas.
Contiene: check_strategies(), calculate_confluence_score(), classify_trade(),
build_trigger_conditions(), get_confluence_badge(), format_confidence(),
_check_usdtd_breakout()
"""

import time
from datetime import datetime
import episode_memory as _em

_phy_last_alert: dict = {}   # {sym: timestamp} — cooldown 30 min to stop PHY spam
PHY_ALERT_COOLDOWN = 1800    # 30 min
from config import (
    V4_EMA_PROXIMITY_MAX, V4_EMA_PROXIMITY_MIN, V4_RSI_LOW,
    V4_RSI_HIGH, V4_RSI_HIGH_ZEC, V4_MIN_CONFLUENCE,
    V4_ATR_SL_MULT, V4_COOLDOWN, V4_EMA_PROX_MAP,
    RSI_SHORT_ENTRY, SHORT_MIN_CONFLUENCE, SHORT_REGIMES,
    SHORT_EMA_SLOPE_MIN, RVOL_MIN_ENTRY, RVOL_MIN_BTC, MIN_CONFLUENCE_SCORE,
    FOMC_NEXT_MEETING, RSI_LONG_EXTREME,
    V1_LONG_ENABLED, V4_BLOCKLIST, V5_ENABLED,
    SWING_BLOCKLIST, SHORT_BLOCKED_IN_VERDE_BULL,
    VIX_DORMANT_THRESHOLD, SP500_VERDE_THRESHOLD,
)


def _is_fomc_proximity() -> bool:
    """True if within 24h of next FOMC meeting — suppress low-confidence signals."""
    try:
        meeting = datetime.strptime(FOMC_NEXT_MEETING, "%Y-%m-%d")
        return abs((datetime.now() - meeting).total_seconds()) < 86400
    except Exception:
        return False


def _build_extra_intel(sym: str) -> dict:
    """Spec 017.5 (2026-05-26): helper para construir dict INTEL EN VIVO para cualquier strategy.

    Llama los 4 módulos intel (HMM/CVD/Social/Whale) — cada uno con su propio cache TTL,
    así que llamadas repetidas dentro del mismo ciclo (loop por símbolo, varias strategies)
    son cache hits, no penalizan rendimiento.

    Args:
        sym: par como "BTC/USDT", "ETH/USDT", etc.

    Returns:
        dict con keys condicionales: hmm_regime, hmm_confidence, cvd_signal,
        cvd_whale_usd, cvd_retail_usd, social_signal, social_reddit,
        social_trends_delta, whale_signal, whale_net_flow_usd.
        Si un módulo no disponible, sus keys se omiten silenciosamente.
    """
    intel = {}
    sym_base = sym.replace("/USDT", "")

    # HMM regime (Fénix F1: off por default vía config.HMM_ENABLED)
    try:
        from config import HMM_ENABLED
        if HMM_ENABLED:
            import regime_hmm
            _hmm = regime_hmm.detect_regime(sym, timeframe="1h", lookback=200) or {}
            if _hmm.get("regime"):
                intel["hmm_regime"] = _hmm.get("regime")
                intel["hmm_confidence"] = _hmm.get("confidence", 0.0)
    except Exception:
        pass

    # CVD segmentado
    try:
        import cvd_segmented
        _cvd = cvd_segmented.compute_cvd_segmented(sym, lookback_trades=1000) or {}
        if _cvd.get("divergence_signal"):
            intel["cvd_signal"] = _cvd.get("divergence_signal")
            intel["cvd_whale_usd"] = _cvd.get("whale_cvd_usd", 0)
            intel["cvd_retail_usd"] = _cvd.get("retail_cvd_usd", 0)
    except Exception:
        pass

    # Social sentiment (Reddit + Trends)
    try:
        import social_quant
        _social = social_quant.get_social_sentiment(sym_base, lookback_hours=24) or {}
        if _social.get("signal"):
            intel["social_signal"] = _social.get("signal")
            intel["social_reddit"] = _social.get("reddit_compound", 0)
            intel["social_trends_delta"] = _social.get("google_trends_delta", 0)
    except Exception:
        pass

    # Whale netflow on-chain (solo ETH por ahora)
    if sym_base == "ETH":
        try:
            import onchain
            _whale = onchain.get_whale_netflow(token_symbol="ETH", chain="eth", lookback_hours=24) or {}
            if _whale.get("signal"):
                intel["whale_signal"] = _whale.get("signal")
                intel["whale_net_flow_usd"] = _whale.get("net_flow_usd", 0)
        except Exception:
            pass

    return intel


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
        _store_pending,
    )
    import alert_manager as _alert_mgr
    import indicators
    import risk_manager
    from risk_manager import circuit_breaker
    import market_intel
    import indicators_swing
    import tracker
    import gemini_analyzer
    import trading_executor
    import alert_manager

    if not prices:
        return

    # Hour filter — basado en análisis de 91 trades reales (WR 0% confirmado por hora)
    # SIM D2 original: {1,4,6,10,11,14,15,16,17,20} — removidos 1 (14.3% WR) y 14 (25% WR)
    _utc_hour = datetime.utcnow().hour
    _BLOCKED_HOURS = {4, 6, 10, 11, 15, 16, 17, 20}
    if _utc_hour in _BLOCKED_HOURS:
        print(f"⏸️ [HourFilter] {_utc_hour:02d}:xx UTC — 0% WR histórico, entradas bloqueadas")
        return

    # ── Circuit Breaker Gate ─────────────────────────────────────────────
    can_trade, cb_reason, cb_multiplier = circuit_breaker.can_trade()
    if not can_trade:
        print(f"🚨 [CircuitBreaker] {cb_reason} — Estrategias bloqueadas")
        return

    phase = get_phase()
    usdt_d = prices.get("USDT_D", 8.0)

    # ── FOMC Proximity Filter ──────────────────────────────────────────
    _fomc_suppressed = _is_fomc_proximity()
    if _fomc_suppressed:
        print("[FOMC PROXIMITY] Reunión FOMC en <24h — solo V2-AI con confluencia >= 5")

    from config import SYMBOLS as _SYMBOLS

    # ── Phase 2: Market Intelligence — Funding rates (batch, 1 call) ───
    try:
        funding_data = market_intel.get_funding_rates(_SYMBOLS)
    except Exception:
        funding_data = {}
    # --- 1D EMA200 bias cache (computed once per cycle, all symbols) ---
    _daily_bias: dict = {}
    try:
        for _s in _SYMBOLS:
            _df1d = indicators.get_df(_s, "1d")
            if _df1d is not None and len(_df1d) >= 200:
                _ema200_1d = float(_df1d["close"].ewm(span=200, adjust=False).mean().iloc[-1])
                _price_1d = float(_df1d["close"].iloc[-1])
                _daily_bias[_s] = "BULL" if _price_1d > _ema200_1d else "BEAR"
    except Exception as _e:
        print(f"⚠️ [1D Bias] Error precalculando bias diario: {_e}")

    for sym in _SYMBOLS:
        # Spec 001 (May-22-2026): kill switch TAO. Bot-generated TAO = 0/31 WR.
        from config import TAO_TRADING_ENABLED
        if sym == "TAO" and not TAO_TRADING_ENABLED:
            continue

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

        # Filtro 1D EMA200 — bloquea LONGs en tendencia bajista diaria
        # Excepción: RSI extremo (≤ RSI_LONG_EXTREME=30) permite V3-REVERSAL incluso en BEAR
        _bias_1d = _daily_bias.get(sym, "UNKNOWN")
        if phase == "LONG" and _bias_1d == "BEAR" and rsi > RSI_LONG_EXTREME:
            print(f"⛔ [1D Filter] {sym}: BEAR diaria + RSI {rsi:.1f} > {RSI_LONG_EXTREME} — LONG bloqueado")
            continue

        # Filtro streak de pérdidas por símbolo — cooldown 4H tras 3 LOST consecutivos
        # Usa DB (no memoria) para sobrevivir reinicios del bot.
        try:
            import sqlite3 as _sqlite3
            from datetime import datetime as _dt
            _db_path = tracker.DB_FILE
            _conn = _sqlite3.connect(_db_path)
            _cur = _conn.cursor()
            _cur.execute(
                "SELECT close_time FROM trades WHERE symbol=? AND status='LOST' "
                "AND (is_sim=0 OR is_sim IS NULL) ORDER BY id DESC LIMIT 3",
                (sym,)
            )
            _losses = _cur.fetchall()
            _conn.close()
            if len(_losses) >= 3 and _losses[0][0]:
                _last_dt = _dt.fromisoformat(str(_losses[0][0]))
                _hours_since = (_dt.now() - _last_dt).total_seconds() / 3600
                if _hours_since < 4:
                    print(f"⛔ [LossStreak] {sym}: 3+ pérdidas recientes, última hace {_hours_since:.1f}h — cooldown 4H")
                    continue
        except Exception as _e:
            print(f"⚠️ [LossStreak] {sym}: error checking streak: {_e}")

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
            if time.time() - _phy_last_alert.get(sym, 0) >= PHY_ALERT_COOLDOWN:
                print(f"👁️ [PHY ALERT] {sym} detectó {phy_bias} — forzando modo RAPIDA")
                _phy_last_alert[sym] = time.time()

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
        from config import V1_SHORT_ENABLED
        if not V1_SHORT_ENABLED:
            pass  # V1-SHORT disabled — 0% WR in 16 trades — re-enable when fixed
        elif p < ema_200 and regime in SHORT_REGIMES and not _fomc_suppressed:
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

                            _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type_short, phy_bias, conf_score, "v1_short", "SHORT", rsi_threshold=short_rsi)
                            _sid = _store_pending(sym, "SHORT", p, tp1, tp2, sl, atr, rsi, conf_score, "v1_short", "V1-TECH", _tc, macro_status)
                            mid = alert(f"{sym}_v1_short", msg, version="V1-TECH",
                                        inline_keyboard=_alert_mgr.get_signal_keyboard(_sid, sym, "SHORT"))
                            if mid:
                                open_position(sym, "SHORT")
                                _ep_id = _em.log_alert_episode(sym, "V1-SHORT", "SHORT", p, sl, tp1, rsi=rsi, confluence=int(conf_score), source="CRYPTO")
                                GLOBAL_CACHE.setdefault("pending_ep_ids", {})[_sid] = _ep_id
                                gemini_analyzer.log_alert_to_context(sym, "SHORT", p, rsi, tp1, sl, "V1-TECH")
                                register_signal_event(sym.replace("/USDT", ""), prices)

        # ═══════════════════════════════════════════════════════════════════
        # ESTRATEGIA V3: REVERSAL / INTRADIA (AGRESIVA)
        # ═══════════════════════════════════════════════════════════════════
        if phase == "LONG" and p < ema_200 and regime in ("VOLATILE", "TRENDING_DOWN") and not _fomc_suppressed:
            # Per-symbol RSI threshold via config (sincronizado con backtester)
            from config import RSI_REVERSAL_BY_SYMBOL
            reversal_rsi = RSI_REVERSAL_BY_SYMBOL.get(sym, RSI_LONG_EXTREME)

            # 🥷 Ninja pre-alerta: RSI cayendo hacia zona de trigger (threshold+8 → threshold)
            _ninja_warn_key = f"ninja_warn_{sym}"
            _ninja_rsi_warn = reversal_rsi + 8  # zona de calentamiento
            if reversal_rsi < rsi <= _ninja_rsi_warn and rsi < prev_rsi:
                _last_ninja = GLOBAL_CACHE.get(_ninja_warn_key, 0)
                # Audit D (2026-05-23): Ninja pre-alerta duplica con V3 si entrada llega. Modo quiet → skip.
                try:
                    from config import ANALYSIS_MODE_QUIET as _QUIET
                except Exception:
                    _QUIET = False
                if not _QUIET and time.time() - _last_ninja > 1800:  # max 1 aviso cada 30min por símbolo
                    send_telegram(
                        f"🥷 <b>Ninja Alerta — {sym.replace('/USDT','')}</b>\n"
                        f"RSI cayendo: <code>{rsi:.1f}</code> → zona trigger en ≤{reversal_rsi}\n"
                        f"Precio: ${p:,.2f} | Régimen: {regime}\n"
                        f"⚡ Preparando entrada potencial LONG"
                    )
                    GLOBAL_CACHE[_ninja_warn_key] = time.time()
                    print(f"🥷 [Ninja] {sym} pre-alerta enviada RSI={rsi:.1f} (trigger≤{reversal_rsi})")

            if rsi <= reversal_rsi:
                # Spec 002.6 (2026-05-26): BARRIDA_OPPORTUNITY check — relaja gates si activo.
                # Cripto V3 NUNCA tendrá cluster ai_infra/nuclear (BTC/ETH/SOL/ZEC/TAO no son
                # tickers stock) → dormant para cripto. Wire ready cuando 017.5 extienda a stocks.
                _barrida_active = False
                _barrida_cluster = None
                try:
                    import regime_transitions
                    _sb = sym.replace("/USDT", "")
                    _spy = prices.get("SPY", 0.0) or 0.0
                    _sp500_proxy = _spy * 10 if _spy > 0 else 0.0
                    _barrida_cluster = regime_transitions.get_cluster_for_symbol(_sb)
                    # drop_pct=0 por ahora (Spec 002.7 backlog: tracking real)
                    # is_barrida_opportunity requiere drop≥2 → con drop=0 siempre False
                    # PERO si se extiende, este es el punto de wire.
                    _barrida_active = regime_transitions.is_barrida_opportunity(
                        _barrida_cluster, _sp500_proxy, vix, intraday_drop_pct=0.0
                    )
                    if _barrida_active:
                        print(f"⚡ [V3-Reversal] {sym}: BARRIDA_OPPORTUNITY active "
                              f"(cluster={_barrida_cluster}) — relajando HMM+CVD gates")
                except Exception as _e:
                    pass

                # Spec 006 (2026-05-26): Funding Rate gate — bloquear reversal si funding > threshold.
                # NotebookLM 4: funding annualized > 10% persistente = latigazo volatilidad inminente.
                # Apalancamiento extremo en longs = liquidaciones masivas precipitan colapso adverso.
                try:
                    from config import FUNDING_REVERSAL_BLOCK_ANNUALIZED as _FRB
                    _sym_funding = (funding_data or {}).get(sym, {})
                    _funding_ann = _sym_funding.get("annualized", 0.0)
                    if _funding_ann > _FRB:
                        print(f"⏸️ [V3-Reversal] {sym}: funding {_funding_ann:.1f}% > {_FRB}% — bloqueando (latigazo volatilidad inminente)")
                        continue
                except Exception as _e:
                    # Si funding data no disponible, no bloquear — fallback al comportamiento previo
                    pass

                # Spec 016 (2026-05-26): HMM Regime gate — bloquear V3 reversal si STRONG_TREND.
                # V3 es reversal play (RSI extremo). En STRONG_TREND el "cuchillo cayendo" suele
                # seguir cayendo. Salmos delega decisión al HMM por símbolo, no al macro gate SP500.
                # Spec 017: guardamos _hmm para inyectar en prompt Cuadrilla Zenith después.
                _hmm = {}
                try:
                    from config import HMM_ENABLED
                    if HMM_ENABLED:
                        import regime_hmm
                        _hmm = regime_hmm.detect_regime(sym, timeframe="1h", lookback=200) or {}
                    _regime = _hmm.get("regime")
                    if _regime == "STRONG_TREND":
                        _conf = _hmm.get("confidence", 0.0)
                        # Spec 002.6: BARRIDA relax — barridas verticales clasifican STRONG_TREND falso
                        if _barrida_active:
                            print(f"⚡ [V3-Reversal] {sym}: HMM STRONG_TREND (conf {_conf:.2f}) "
                                  f"override por BARRIDA_OPPORTUNITY")
                        else:
                            print(f"⏸️ [V3-Reversal] {sym}: HMM regime=STRONG_TREND (conf {_conf:.2f}) — bloqueando reversal contra tendencia")
                            continue
                except Exception as _e:
                    # HMM no disponible (hmmlearn missing) → fallback comportamiento previo
                    pass

                # Spec 016: CVD Segmented divergence gate — bloquear V3 LONG si BEARISH divergence
                # (ballenas vendiendo + retail comprando = top inminente).
                # Spec 017: guardamos _cvd para inyectar en prompt.
                _cvd = {}
                try:
                    import cvd_segmented
                    _cvd = cvd_segmented.compute_cvd_segmented(sym, lookback_trades=1000) or {}
                    _cvd_signal = _cvd.get("divergence_signal")
                    if _cvd_signal == "BEARISH":
                        _whale = _cvd.get("whale_cvd_usd", 0)
                        _retail = _cvd.get("retail_cvd_usd", 0)
                        # Spec 002.6: BARRIDA relax — venta retail panic = bottom, no top
                        if _barrida_active:
                            print(f"⚡ [V3-Reversal] {sym}: CVD BEARISH "
                                  f"(whale ${_whale:+,.0f} / retail ${_retail:+,.0f}) "
                                  f"override por BARRIDA_OPPORTUNITY")
                        else:
                            print(f"⏸️ [V3-Reversal] {sym}: CVD divergence=BEARISH (whale ${_whale:+,.0f} / retail ${_retail:+,.0f}) — top inminente, skip LONG")
                            continue
                except Exception as _e:
                    pass

                # Spec 016: Social Sentiment gate — si EUPHORIA, fade crowd (skip).
                # FEAR no skip pero se loguea (boost confluence se hace inline después).
                # Spec 017: guardamos _social para inyectar en prompt.
                _social = {}
                try:
                    import social_quant
                    _social = social_quant.get_social_sentiment(sym.replace("/USDT", ""), lookback_hours=24) or {}
                    _social_signal = _social.get("signal")
                    if _social_signal == "EUPHORIA":
                        _rc = _social.get("reddit_compound", 0)
                        _gt = _social.get("google_trends_delta", 0)
                        print(f"⏸️ [V3-Reversal] {sym}: Social=EUPHORIA (reddit {_rc:+.2f}, trends {_gt:+.0f}%) — fading crowd, top probable")
                        continue
                except Exception as _e:
                    pass

                # Spec 019 (2026-05-26): on-chain whale netflow para tokens trackeables.
                # ETH directo via Etherscan. Otros símbolos sin chain match → skip.
                _whale = {}
                _sym_base = sym.replace("/USDT", "")
                if _sym_base == "ETH":
                    try:
                        import onchain
                        _whale = onchain.get_whale_netflow(token_symbol="ETH", chain="eth", lookback_hours=24) or {}
                    except Exception as _e:
                        pass

                # Spec 017: build extra_intel dict para inyectar en Cuadrilla Zenith prompt
                _extra_intel = {}
                if _hmm.get("regime"):
                    _extra_intel["hmm_regime"] = _hmm.get("regime")
                    _extra_intel["hmm_confidence"] = _hmm.get("confidence", 0.0)
                if _cvd.get("divergence_signal"):
                    _extra_intel["cvd_signal"] = _cvd.get("divergence_signal")
                    _extra_intel["cvd_whale_usd"] = _cvd.get("whale_cvd_usd", 0)
                    _extra_intel["cvd_retail_usd"] = _cvd.get("retail_cvd_usd", 0)
                if _social.get("signal"):
                    _extra_intel["social_signal"] = _social.get("signal")
                    _extra_intel["social_reddit"] = _social.get("reddit_compound", 0)
                    _extra_intel["social_trends_delta"] = _social.get("google_trends_delta", 0)
                # Spec 019: whale netflow (solo ETH por ahora)
                if _whale.get("signal"):
                    _extra_intel["whale_signal"] = _whale.get("signal")
                    _extra_intel["whale_net_flow_usd"] = _whale.get("net_flow_usd", 0)

                register_signal_event(sym.replace("/USDT", ""), prices)
                side = "LONG"
                funding_signal = market_intel.get_funding_signal(sym, side, funding_data)
                conf_score = calculate_confluence_score(p, rsi, bb_u, bb_l, ema_200, usdt_d, side, elliott, spy=prices.get("SPY"), oil=prices.get("OIL"), funding_signal=funding_signal)
                conf_score = round(conf_score + social_adj, 2)
                _conf_score_pre = conf_score  # Spec 022: snapshot pre-boost para A/B tracking

                # Spec 021 (2026-05-26): boost confluence con signals BULLISH/FEAR del INTEL.
                # Specs 016/019 ya filtraron como gates BEARISH. Aquí premiamos los signals
                # opuestos que indican confluencia adicional para V3 LONG (bottom probable).
                _boost = 0.0
                _boost_reasons = []
                if _cvd.get("divergence_signal") == "BULLISH":
                    _boost += 1.0
                    _boost_reasons.append("CVD BULLISH (whales acumulan)")
                if _social.get("signal") == "FEAR":
                    _boost += 1.0
                    _boost_reasons.append("Social FEAR (capitulación retail)")
                if _whale.get("signal") == "BULLISH":
                    _boost += 1.0
                    _boost_reasons.append("Whale BULLISH (outflow exchange)")
                if _hmm.get("regime") == "RANGE":
                    # RANGE es ideal para V3-Reversal (mean reversion) — boost suave
                    _boost += 0.5
                    _boost_reasons.append("HMM RANGE (mean reversion ideal)")
                # Spec 002.6 (2026-05-26): EXPLOSIVE_CORRECTION boost (post AMARILLA→VERDE).
                # +1.5 (vs +1.0 del resto) porque setup raro. Cripto V3 no matches por default
                # (tickers no en EXPLOSIVE_TICKERS set), pero wire ready si se extiende.
                try:
                    import regime_transitions
                    _sb2 = sym.replace("/USDT", "")
                    _spy2 = prices.get("SPY", 0.0) or 0.0
                    _sp500_proxy2 = _spy2 * 10 if _spy2 > 0 else 0.0
                    if regime_transitions.is_explosive_correction_setup(_sb2, _sp500_proxy2, vix):
                        _boost += 1.5
                        _boost_reasons.append("EXPLOSIVE_CORRECTION (post régimen AMARILLA→VERDE)")
                except Exception:
                    pass
                if _boost > 0:
                    conf_score = round(conf_score + _boost, 2)
                    print(f"⭐ [V3-Reversal] {sym}: boost +{_boost:.1f} ({' · '.join(_boost_reasons)}) → conf_score={conf_score:.2f}")

                # Spec NB3 P0 (2026-05-26): kill conf_score >= 5 (paradoja overfit 0% WR).
                # NotebookLM 3 P2: 7 ops históricas score=5 todas LONG GOLD COMMODITY perdedoras.
                # Hasta refactor calculate_confluence_score, este gate evita repetir el bug.
                try:
                    from config import BLOCK_SCORE_5 as _B5
                    if _B5 and conf_score >= 5:
                        print(f"⏸️ [V3-Reversal] {sym}: conf_score={conf_score} ≥ 5 → kill (NotebookLM 3 paradoja overfit)")
                        continue
                except Exception:
                    pass

                sl_dist = max(atr * 2.0, p * 0.008)
                sl = round(p - sl_dist, 2)
                tp1 = round(p + (sl_dist * 2.0), 2)
                tp2 = round(p + (sl_dist * 3.5), 2)

                # Spec 008 (2026-05-26): FVG bullish nearest como imán de precio.
                # Si hay un FVG bullish por encima del precio + entre TP1 y TP2, considerarlo
                # como TP más probable (Smart Money imán). NO override TP1 (mantenemos ATR-based)
                # pero AGREGAMOS tag visual + posible target intermedio.
                _fvg_tag = ""
                _fvg_target = None
                try:
                    _fvg = indicators.detect_fair_value_gaps(sym, timeframe="1h", lookback=30, max_gaps=3)
                    _nearest_bull = _fvg.get("nearest_bullish_top")
                    if _nearest_bull is not None and tp1 <= _nearest_bull <= tp2:
                        _fvg_target = round(_nearest_bull, 2)
                        _fvg_tag = (
                            f"🎯 <b>FVG imán</b> @ ${_fvg_target:,.2f} "
                            f"(entre TP1 y TP2 — target probable)\n"
                        )
                except Exception as _e:
                    print(f"[V3-Reversal] {sym} FVG detect skip: {_e}")

                # Spec 007 (2026-05-26): liquidity sweep tag.
                # Si swept_low activo + macro VERDE_BULL_DORMANT → smart money huella en LONG.
                _sweep_tag = ""
                try:
                    _sweep = indicators.detect_liquidity_sweep(sym, timeframe="1h", lookback=20)
                    if _sweep.get("swept_low"):
                        _sweep_tag = (
                            f"🌊 <b>SWEEP LOW activo</b> — wick rompió ${_sweep['swing_low_level']:.2f} "
                            f"+ cerró arriba (huella Smart Money)\n"
                        )
                except Exception as _e:
                    print(f"[V3-Reversal] {sym} sweep detect skip: {_e}")

                # Spec 022.6.1 (2026-05-26): INTEL visible en el mensaje (antes solo
                # se inyectaba al prompt LLM, user no lo veía nunca).
                try:
                    from voice_compactor import intel_compact_line as _icl
                    _intel_visible = _icl(_extra_intel)
                except Exception:
                    _intel_visible = ""
                _intel_tag = f"{_intel_visible}\n" if _intel_visible else ""

                msg = (f"🏛️ <b>SEÑAL V3: INTRADÍA REVERSAL (15m-1H)</b> 🏛️\n\n"
                       f"{_sweep_tag}"
                       f"{_fvg_tag}"
                       f"{_intel_tag}"
                       f"🌊 Onda: {elliott}\n"
                       f"⭐ <b>Confiabilidad: {format_confidence(conf_score)}</b>\n\n"
                       f"💬 <i>Buscando el rebote a la media (EMA 200) tras agotamiento.</i>\n\n"
                       f"🪙 <b>{sym}</b> @ ${p:,.2f}\n"
                       f"🎯 TP1: <b>${tp1:,.2f}</b> (2:1)\n"
                       f"🎯 TP2: <b>${tp2:,.2f}</b> (3.5:1)\n"
                       f"🛑 SL: <b>${sl:,.2f}</b>\n\n"
                       f"🎙️ <b>DEBATE DEL CUADRANTE ZENITH:</b>\n"
                       f"{gemini_analyzer.get_ai_consensus(sym, p, 'LONG', rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'), vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, extra_intel=_extra_intel)}")

                if is_position_open(sym, "LONG"):
                    print(f"⏸️ [Position Guard] {sym} LONG (Reversal) ya está abierto — omitiendo señal duplicada")
                    continue

                _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, conf_score, "v3_reversal", "LONG", rsi_threshold=reversal_rsi)
                _sid = _store_pending(sym, "LONG", p, tp1, tp2, sl, atr, rsi, conf_score, "v3_reversal", "V1-TECH", _tc, macro_status)
                mid = alert(f"{sym}_v3_reversal", msg, version="V1-TECH",
                            inline_keyboard=_alert_mgr.get_signal_keyboard(_sid, sym, "LONG"))
                if mid:
                    open_position(sym, "LONG")
                    _ep_id = _em.log_alert_episode(sym, "V3-REV", "LONG", p, sl, tp1, rsi=rsi, confluence=int(conf_score), source="CRYPTO")
                    GLOBAL_CACHE.setdefault("pending_ep_ids", {})[_sid] = _ep_id
                    gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")
                    register_signal_event(sym.replace("/USDT", ""), prices)

                    # Spec 022 (2026-05-26): A/B test logging — capturar intel + boost para análisis posterior
                    # Fix Spec 022.5.1 (2026-05-26): usar sim_id (trade.id) en lugar de _sid (counter),
                    # para que update_trade_status pueda matchear y poblar outcome/pnl_pct.
                    try:
                        import tracker as _trk
                        from scalp_alert_bot import _PENDING_SIGNALS as _PS
                        _trade_id = _PS.get(_sid, {}).get("sim_id") or _sid
                        _trk.log_intel_event(
                            alert_id=int(_trade_id), symbol=sym, strategy="v3_reversal", side="LONG",
                            intel=_extra_intel, boost_applied=_boost,
                            boost_reasons=_boost_reasons,
                            conf_score_pre=_conf_score_pre, conf_score_post=conf_score,
                            entry=p, sl=sl, tp1=tp1, gates_blocked=[],
                        )
                    except Exception as _e:
                        print(f"[V3-Reversal] {sym} intel_log skip: {_e}")

        # ═══════════════════════════════════════════════════════════════════
        # ESTRATEGIA V1: Long V1 (Trend Alcista + RSI 45 + RSI Rising)
        # v2.1: BB touch ahora es bonus en confluencia, no hard gate
        # May-2026: V1_LONG_ENABLED kill switch (15.4% WR / -34% backtest)
        # ═══════════════════════════════════════════════════════════════════
        elif V1_LONG_ENABLED and phase == "LONG" and p > ema_200 and regime in ("TRENDING_UP", "VOLATILE"):
            entry_rsi = 49.0 if sym == "ZEC" else 47.0  # was 45/48 — widen net during ranging
            if rsi <= entry_rsi:
                if rsi < prev_rsi:
                    continue

                # RVOL filter — skip entries on low volume (noise reduction)
                rvol = prices.get(f"{sym}_RVOL", 1.0)
                rvol_min = RVOL_MIN_BTC if sym in ("BTC", "ETH") else RVOL_MIN_ENTRY
                if rvol < rvol_min:
                    print(f"⏩ [V1-LONG] {sym} RVOL {rvol:.2f} < {rvol_min} — sin volumen confirmado")
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

                if conf_score < MIN_CONFLUENCE_SCORE:
                    # Log episodio filtrado (para near-miss análisis)
                    _bb_pos = "LOWER" if p <= bb_l * 1.01 else "UPPER" if p >= bb_u * 0.99 else "MID"
                    _ema_trend = "ABOVE" if p > ema_200 else "BELOW"
                    _atr_pct = round((atr / p * 100) if p else 0, 3)
                    _em.log_episode(sym, "V1-TECH", "FILTERED", rsi, usdt_d, _bb_pos, _ema_trend, int(conf_score), _atr_pct)
                    print(f"⏩ [V12-Audit] Señal {sym} ignorada (Score {conf_score} < {MIN_CONFLUENCE_SCORE})")
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
                       f"{gemini_analyzer.get_ai_consensus(sym, p, 'LONG', rsi, usdt_d, spy=prices.get('SPY', 0), oil=prices.get('OIL', 0), nvda=prices.get('NVDA', 0), pltr=prices.get('PLTR', 0), vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, extra_intel=_build_extra_intel(sym))}")
                _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, conf_score, "v1_long", "LONG", rsi_threshold=entry_rsi)
                _sid = _store_pending(sym, "LONG", p, tp1, tp2, sl, atr, rsi, conf_score, "v1_long", "V1-TECH", _tc, macro_status)
                mid = alert(f"{sym}_v1_long", msg, version="V1-TECH",
                            inline_keyboard=_alert_mgr.get_signal_keyboard(_sid, sym, "LONG"))
                if mid:
                    open_position(sym, "LONG")
                    _bb_pos = "LOWER" if p <= bb_l * 1.01 else "UPPER" if p >= bb_u * 0.99 else "MID"
                    _ema_trend = "ABOVE" if p > ema_200 else "BELOW"
                    _atr_pct = round((atr / p * 100) if p else 0, 3)
                    _ep_id = _em.log_episode(sym, "V1-TECH", "LONG", rsi, usdt_d, _bb_pos, _ema_trend, int(conf_score), _atr_pct)
                    GLOBAL_CACHE.setdefault("pending_ep_ids", {})[_sid] = _ep_id
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

                        # Circuit breaker → dynamic risk sizing
                        dyn_risk = risk_manager.calculate_dynamic_risk(
                            atr, p, vix, trade_type, cb_multiplier
                        )
                        res_exec = GLOBAL_CACHE["executor"].execute_bracket_order(
                            sym, side, p, tp1, tp2, sl, tp3=tp3,
                            dynamic_risk_pct=dyn_risk
                        )
                        exec_report = f"💸 <b>BINANCE V6:</b> {res_exec.get('status')} (ID: {res_exec.get('id')}) | Risk: {dyn_risk*100:.2f}%"

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
                           f"{gemini_analyzer.get_ai_consensus(sym, p, phase, rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'), vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, extra_intel=_build_extra_intel(sym))}")
                    _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, conf_score, "v2_ai_long", phase, rsi_threshold=entry_rsi)
                    _sid = _store_pending(sym, phase, p, tp1, tp2, sl, atr, rsi, conf_score, "v2_ai_long", "V2-AI", _tc, macro_status)
                    mid = alert(f"{sym}_v2_ai_{phase}", msg, version="V2-AI",
                                inline_keyboard=_alert_mgr.get_signal_keyboard(_sid, sym, phase))
                    if mid:
                        open_position(sym, phase)
                        _ep_id = _em.log_alert_episode(sym, "V2-AI", phase, p, sl, tp1, rsi=rsi, confluence=int(conf_score), source="CRYPTO")
                        GLOBAL_CACHE.setdefault("pending_ep_ids", {})[_sid] = _ep_id
                        register_signal_event(sym.replace("/USDT", ""), prices)

        # ═══════════════════════════════════════════════════════════════════
        # ESTRATEGIA V4: EMA 200 BOUNCE (MEAN REVERSION)
        # ═══════════════════════════════════════════════════════════════════
        elif phase == "LONG" and sym not in V4_BLOCKLIST and not _fomc_suppressed and p > ema_200 * V4_EMA_PROXIMITY_MIN and p <= ema_200 * V4_EMA_PROX_MAP.get(sym, V4_EMA_PROXIMITY_MAX) and regime == "TRENDING_UP":
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

                _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, conf_score, "v4_ema_bounce", "LONG", rsi_threshold=rsi_high)
                _sid = _store_pending(sym, "LONG", p, tp1, tp2, sl, atr, rsi, conf_score, "v4_ema_bounce", "V1-TECH", _tc, macro_status)
                mid = alert(f"{sym}_v4_ema_bounce", msg, version="V1-TECH",
                            cooldown=V4_COOLDOWN,
                            inline_keyboard=_alert_mgr.get_signal_keyboard(_sid, sym, "LONG"))
                if mid:
                    open_position(sym, "LONG")
                    _ep_id = _em.log_alert_episode(sym, "V4-EMA", "LONG", p, sl, tp1, rsi=rsi, confluence=int(conf_score), source="CRYPTO")
                    GLOBAL_CACHE.setdefault("pending_ep_ids", {})[_sid] = _ep_id
                    gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")
                    register_signal_event(sym.replace("/USDT", ""), prices)

        # ═══════════════════════════════════════════════════════════════════
        # ESTRATEGIA V2: AI ENHANCED (LONG ONLY)
        # Spec 001 (May-22-2026): V2-AI estaba gated por p > ema_200 → en bear
        # market nunca disparaba. Ahora deja a la IA decidir; EMA pasa como
        # contexto a get_ai_decision (no como veto duro).
        # ═══════════════════════════════════════════════════════════════════
        if rsi <= 40:
            side = "LONG"

            # Skip si símbolo en SWING_BLOCKLIST (Spec 001)
            if sym in SWING_BLOCKLIST:
                print(f"⏩ [V2-AI] {sym} en SWING_BLOCKLIST — skip")
                continue

            df = indicators.get_df(sym, "1h")
            obs = indicators_swing.find_order_blocks(df)
            ob_detected = any(ob["type"] == "BULL_OB" and p >= ob["low"] * 0.99 and p <= ob["high"] * 1.01 for ob in obs)

            # EMA como contexto (no veto). La IA decide considerando trend macro.
            dec_cons, reason_cons, full_cons = gemini_analyzer.get_ai_decision(sym, p, side, rsi, bb_u, bb_l, version="V1-TECH", usdt_d=usdt_d, vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, fib_levels=fib_levels)
            dec_scalp, reason_scalp, full_scalp = gemini_analyzer.get_ai_decision(sym, p, side, rsi, bb_u, bb_l, version="V2-AI", usdt_d=usdt_d, vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, fib_levels=fib_levels)
            full_analysis = f"Consenso:\n{full_cons}\n\n{full_scalp}"

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
                       f"{gemini_analyzer.get_ai_consensus(sym, p, side, rsi, usdt_d, spy=prices.get('SPY'), oil=prices.get('OIL'), nvda=prices.get('NVDA'), pltr=prices.get('PLTR'), vix=vix, dxy=dxy, trade_type=trade_type, phy_bias=phy_bias, extra_intel=_build_extra_intel(sym))}")

                _tc = build_trigger_conditions(sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d, vix, dxy, macro_dict, macro_status, atr, elliott, ob_detected, social_adj, trade_type, phy_bias, 5 if is_consensus else 4, "v2_ai_consensus", side, rsi_threshold=40.0)
                _score_v2 = 5 if is_consensus else 4
                _sid = _store_pending(sym, phase, p, tp1, tp2, sl, atr, rsi, _score_v2, "v2_ai_consensus", "V2-AI", _tc, macro_status)
                mid = alert(f"{sym}_v2_short", msg, version="V2-AI",
                            inline_keyboard=_alert_mgr.get_signal_keyboard(_sid, sym, phase))
                if mid:
                    GLOBAL_CACHE.setdefault("pending_ep_ids", {})[_sid] = None  # no episode for V2-short
                    gemini_analyzer.log_alert_to_context(sym, side, p, rsi, tp1, sl, "V2-AI")

        # ═══════════════════════════════════════════════════════════════════
        # ESTRATEGIA V5: MOMENTUM BREAKOUT (RSI Midline Cross)
        # Dispara cuando el RSI cruza arriba de 50 desde abajo → cambio de momentum.
        # Más activo que V1 (no requiere RSI < 45): opera en mercados normales.
        # Confluencia mínima: 3 (vs 4 de V1). Cooldown: 20 min.
        # ═══════════════════════════════════════════════════════════════════
        from config import V5_MOMENTUM_MIN_CONF, V5_MOMENTUM_COOLDOWN, V5_MOMENTUM_RVOL_MIN
        if (V5_ENABLED and phase == "LONG" and p > ema_200 and not _fomc_suppressed and
                regime != "RANGING" and
                prev_rsi < 50.0 <= rsi):
            if is_position_open(sym, "LONG"):
                print(f"⏸️ [Position Guard] {sym} LONG (V5-MOMENTUM) ya abierto")
            else:
                _v5_rvol = prices.get(f"{sym}_RVOL", 1.0)
                if _v5_rvol < V5_MOMENTUM_RVOL_MIN:
                    print(f"⏩ [V5-MOMENTUM] {sym} RVOL {_v5_rvol:.2f} < {V5_MOMENTUM_RVOL_MIN} — skip")
                    continue
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
                    rvol = prices.get(f"{sym}_RVOL", 1.0)
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

                    _tc = build_trigger_conditions(
                        sym, p, rsi, prev_rsi, bb_u, bb_l, ema_200, usdt_d,
                        vix, dxy, macro_dict, macro_status, atr, elliott,
                        ob_detected, social_adj, trade_type, phy_bias, conf_score,
                        "v5_momentum", "LONG", rsi_threshold=50.0)
                    _sid = _store_pending(sym, "LONG", p, tp1, tp2, sl, atr, rsi, conf_score, "v5_momentum", "V1-TECH", _tc, macro_status)
                    mid = alert(f"{sym}_v5_momentum", msg, version="V1-TECH",
                                cooldown=V5_MOMENTUM_COOLDOWN,
                                inline_keyboard=_alert_mgr.get_signal_keyboard(_sid, sym, "LONG"))
                    if mid:
                        open_position(sym, "LONG")
                        GLOBAL_CACHE.setdefault("pending_ep_ids", {})[_sid] = None
                        gemini_analyzer.log_alert_to_context(sym, "LONG", p, rsi, tp1, sl, "V1-TECH")
                        register_signal_event(sym.replace("/USDT", ""), prices)

        # USDT.D Breakout (extracted to usdtd_alerts.py)
        import usdtd_alerts
        usdtd_alerts.check_usdtd_breakout(usdt_d, btc_d, vix, dxy, bb_ctx,
                                           prices, alert, alert_manager,
                                           GLOBAL_CACHE)
