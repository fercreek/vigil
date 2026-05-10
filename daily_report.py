"""
daily_report.py — Reporte diario automatizado a Telegram

Corre en thread propio. Cada día a HH:MM (default 08:00 local server) envía:
  - WR últimas 24h vs baseline pre-fixes (18.7%)
  - WR últimos 7 días con tendencia
  - Trades activados / skipeados / abiertos
  - Top símbolo perdedor / ganador
  - Costo IA del mes
  - Estado de circuit breaker

Sin interacción del usuario. Solo lectura — no muta DB.
"""

import time
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from logger_core import logger
import tracker
import thread_health

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Hora local del server para enviar reporte (UTC en Railway)
REPORT_HOUR_UTC = int(os.getenv("DAILY_REPORT_HOUR_UTC", "13"))  # 13 UTC = 8 AM EST aprox
REPORT_MIN_UTC  = int(os.getenv("DAILY_REPORT_MIN_UTC",  "0"))

# Baseline histórico pre-fixes (auditoría May-2026)
BASELINE_WR     = 18.7
BASELINE_LABEL  = "pre-fixes May-2026"


def _send_telegram(msg: str):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"
        }, timeout=15)
        if not r.ok:
            logger.warning("DailyReport Telegram error %d: %s", r.status_code, r.text[:120])
    except Exception as e:
        logger.error("DailyReport Telegram send failed: %s", e)


def _wr_window(hours: int) -> dict:
    """WR + PnL + Profit Factor + Expectancy de últimos N horas (real, no-sim).

    PnL aprox: usa entry/sl/tp1 para estimar % por trade según result.
      FULL_WON / WON: +(tp1-entry)/entry
      PARTIAL_*:      +50% del path entry→tp1 (mover SL a BE captura mitad)
      LOST:           -(entry-sl)/entry  (signo según side)
    """
    cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)).isoformat()
    try:
        conn = sqlite3.connect(tracker.DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            SELECT type, status, entry_price, sl_price, tp1_price
            FROM trades
            WHERE (is_sim=0 OR is_sim IS NULL)
              AND open_time >= ?
        """, (cutoff,))
        rows = cur.fetchall()
        conn.close()

        wins = losses = open_n = 0
        gross_profit = 0.0  # suma % de winners
        gross_loss   = 0.0  # suma % absoluto de losers
        win_pnls   = []
        loss_pnls  = []

        for side, status, entry, sl, tp1 in rows:
            entry = float(entry or 0)
            sl    = float(sl or 0)
            tp1   = float(tp1 or 0)
            if entry <= 0:
                continue
            sign = 1 if side == "LONG" else -1

            if status == "OPEN":
                open_n += 1
                continue
            if status in ("FULL_WON", "WON"):
                pnl = sign * (tp1 - entry) / entry * 100 if tp1 > 0 else 0
                wins += 1
                gross_profit += pnl
                win_pnls.append(pnl)
            elif status in ("PARTIAL_WON", "PARTIAL_CLOSED"):
                # Mitad del path al tp1 (parcial) — aprox conservadora
                pnl = sign * (tp1 - entry) / entry * 100 * 0.5 if tp1 > 0 else 0
                wins += 1
                gross_profit += pnl
                win_pnls.append(pnl)
            elif status == "LOST":
                pnl = sign * (sl - entry) / entry * 100 if sl > 0 else 0
                # sign × (sl-entry)/entry: LONG con sl<entry → negativo; SHORT con sl>entry → negativo
                losses += 1
                gross_loss += abs(pnl)
                loss_pnls.append(pnl)

        closed = wins + losses
        wr = (wins / closed * 100) if closed > 0 else 0.0
        pnl_total = gross_profit - gross_loss
        avg_win  = (sum(win_pnls) / len(win_pnls)) if win_pnls else 0.0
        avg_loss = (sum(loss_pnls) / len(loss_pnls)) if loss_pnls else 0.0  # negativo
        # Profit Factor = gross_profit / gross_loss (>1 = profitable)
        pf = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
        # Expectancy = (WR × avg_win) + (LR × avg_loss)
        wr_dec = wr / 100
        expectancy = (wr_dec * avg_win) + ((1 - wr_dec) * avg_loss) if closed > 0 else 0.0

        return {
            "wins": wins, "losses": losses, "open": open_n, "total": len(rows),
            "closed": closed, "wr": wr,
            "pnl_total": pnl_total,
            "avg_win": avg_win, "avg_loss": avg_loss,
            "pf": pf, "expectancy": expectancy,
        }
    except Exception as e:
        logger.error("WR window error: %s", e)
        return {"wins": 0, "losses": 0, "open": 0, "total": 0, "closed": 0,
                "wr": 0.0, "pnl_total": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "pf": 0.0, "expectancy": 0.0}


def _skip_count_24h() -> int:
    """Cuántas señales se skipearon en últimas 24h (botón Skip → is_sim=1)."""
    cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)).isoformat()
    try:
        conn = sqlite3.connect(tracker.DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM trades WHERE is_sim=1 AND open_time >= ?", (cutoff,))
        n = cur.fetchone()[0] or 0
        conn.close()
        return n
    except Exception:
        return 0


def _top_symbol(window_hours: int = 168, kind: str = "winner") -> str:
    """Top símbolo ganador o perdedor por count en ventana."""
    cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=window_hours)).isoformat()
    status_filter = "FULL_WON','PARTIAL_WON','PARTIAL_CLOSED','WON" if kind == "winner" else "LOST"
    try:
        conn = sqlite3.connect(tracker.DB_FILE)
        cur = conn.cursor()
        cur.execute(f"""
            SELECT symbol, COUNT(*) as n
            FROM trades
            WHERE (is_sim=0 OR is_sim IS NULL)
              AND status IN ('{status_filter}')
              AND open_time >= ?
            GROUP BY symbol ORDER BY n DESC LIMIT 1
        """, (cutoff,))
        row = cur.fetchone()
        conn.close()
        return f"{row[0]} ({row[1]})" if row else "—"
    except Exception:
        return "—"


def _ai_budget_summary() -> str:
    """Snapshot del consumo IA del mes."""
    try:
        import ai_budget
        m = ai_budget.get_monthly_cost()
        used = m.get("total_usd", 0)
        cap = m.get("max_monthly_usd", 10.0)
        pct = m.get("budget_used_pct", 0)
        calls = m.get("calls", 0)
        return f"${used:.2f} / ${cap:.0f} ({pct:.0f}%) — {calls} llamadas"
    except Exception:
        return "—"


def _circuit_status() -> str:
    """Estado del circuit breaker."""
    try:
        import risk_manager
        cb = risk_manager.get_circuit_breaker()
        state = getattr(cb, "state", "UNKNOWN")
        return state
    except Exception:
        return "UNKNOWN"


def build_daily_report() -> str:
    """Construye el HTML del reporte diario."""
    w24 = _wr_window(24)
    w7d = _wr_window(168)
    w30d = _wr_window(720)
    skips_24h = _skip_count_24h()

    # Delta vs baseline
    def _delta_emoji(wr: float) -> str:
        d = wr - BASELINE_WR
        if d >= 5:    return f"📈 +{d:.1f}pp"
        if d >= 1:    return f"🟢 +{d:.1f}pp"
        if d > -1:    return f"⚪ {d:+.1f}pp"
        if d > -5:    return f"🟡 {d:+.1f}pp"
        return f"🔴 {d:+.1f}pp"

    # Trend 7d vs 30d
    trend = "📊 sin data" if w30d["closed"] < 5 else (
        "📈 mejorando" if w7d["wr"] > w30d["wr"] + 2 else
        "📉 empeorando" if w7d["wr"] < w30d["wr"] - 2 else
        "➡️ estable"
    )

    top_winner = _top_symbol(168, "winner")
    top_loser  = _top_symbol(168, "loser")

    today = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M UTC")

    # Veredicto de profitability basado en Profit Factor
    def _verdict(pf: float, n: int) -> str:
        if n < 5:        return "📊 muestra insuficiente"
        if pf >= 2.0:    return "🟢 profitable (PF ≥ 2)"
        if pf >= 1.5:    return "🟢 profitable (PF ≥ 1.5)"
        if pf >= 1.0:    return "🟡 break-even (PF ≥ 1)"
        return "🔴 perdedor (PF < 1)"

    def _fmt_pf(pf: float) -> str:
        if pf == float("inf"): return "∞"
        return f"{pf:.2f}"

    return (
        f"📊 <b>REPORTE DIARIO ZENITH</b>\n"
        f"<code>{today}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\n<b>Win Rate</b>\n"
        f"  24h:  <b>{w24['wr']:.1f}%</b> ({w24['wins']}W / {w24['losses']}L)  {_delta_emoji(w24['wr']) if w24['closed']>0 else ''}\n"
        f"  7d:   <b>{w7d['wr']:.1f}%</b> ({w7d['wins']}W / {w7d['losses']}L)  {trend}\n"
        f"  30d:  <b>{w30d['wr']:.1f}%</b> ({w30d['wins']}W / {w30d['losses']}L)\n"
        f"  Baseline ({BASELINE_LABEL}): {BASELINE_WR}%\n"
        f"\n<b>📈 Profitability 7d</b>  ←  métrica real\n"
        f"  PnL acumulado:  <b>{w7d['pnl_total']:+.2f}%</b>\n"
        f"  Profit Factor:  <b>{_fmt_pf(w7d['pf'])}</b>  {_verdict(w7d['pf'], w7d['closed'])}\n"
        f"  Expectancy:     <b>{w7d['expectancy']:+.2f}%</b> por trade\n"
        f"  Avg Win:  +{w7d['avg_win']:.2f}%  |  Avg Loss: {w7d['avg_loss']:.2f}%\n"
        f"\n<b>📊 Profitability 30d</b>\n"
        f"  PnL: {w30d['pnl_total']:+.2f}%  |  PF: {_fmt_pf(w30d['pf'])}  |  Exp: {w30d['expectancy']:+.2f}%\n"
        f"\n<b>Actividad 24h</b>\n"
        f"  Activados:  {w24['total']}\n"
        f"  Skipeados:  {skips_24h}\n"
        f"  Abiertos:   {w24['open']}\n"
        f"\n<b>Top símbolos 7d</b>\n"
        f"  🏆 Ganador:  {top_winner}\n"
        f"  💀 Perdedor: {top_loser}\n"
        f"\n<b>Sistema</b>\n"
        f"  Circuit breaker: {_circuit_status()}\n"
        f"  Costo IA mes:    {_ai_budget_summary()}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>PF &gt; 1 = ganando · WR alone es ruido · /winrate /pos /budget</i>"
    )


def _seconds_until_next_run() -> int:
    """Segundos hasta el próximo HH:MM UTC configurado."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    target = now.replace(hour=REPORT_HOUR_UTC, minute=REPORT_MIN_UTC, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return int((target - now).total_seconds())


def run_daily_report():
    logger.info("DAILY REPORT BOT ACTIVADO — disparará %02d:%02d UTC cada día",
                REPORT_HOUR_UTC, REPORT_MIN_UTC)
    while True:
        try:
            thread_health.heartbeat("daily_report")
            wait_s = _seconds_until_next_run()
            logger.info("DailyReport esperando %dh %dm hasta próximo reporte",
                        wait_s // 3600, (wait_s % 3600) // 60)

            # Sleep en chunks de 60s para mantener heartbeat
            while wait_s > 0:
                step = min(60, wait_s)
                time.sleep(step)
                wait_s -= step
                thread_health.heartbeat("daily_report")

            # Disparo
            logger.info("DailyReport disparando reporte")
            msg = build_daily_report()
            _send_telegram(msg)
            logger.info("DailyReport enviado ✅")

            # Pequeña pausa para evitar doble disparo
            time.sleep(120)

        except Exception as e:
            logger.error("DailyReport loop error: %s", e, exc_info=True)
            time.sleep(300)


if __name__ == "__main__":
    # Modo standalone — manda el reporte una vez y sale (útil para test/cron)
    print(build_daily_report())
    if os.getenv("SEND", "0") == "1":
        _send_telegram(build_daily_report())
