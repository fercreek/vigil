"""
usdtd_alerts.py — Alertas USDT.D Breakout (V15: Institutional Grade)

Extraído de strategies.py para mantener archivos < 600 líneas.
Genera alertas cuando USDT.D toca niveles clave institucionales.
"""


def check_usdtd_breakout(usdt_d, btc_d, vix, dxy, bb_ctx, prices,
                          alert, alert_manager, GLOBAL_CACHE):
    """
    Verifica si USDT.D toca niveles clave y genera alertas institucionales.

    Niveles:
      - 8.08%  — Zona de Pánico (BEAR)
      - 8.044% — Zona de Tensión (NEUTRAL/BEAR)
      - 7.953% — Zona de Euforia (BULL)

    Incluye detección de persistencia (toques repetidos al mismo nivel).
    """
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
