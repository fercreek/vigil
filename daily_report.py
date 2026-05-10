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
    """Calcula WR de los últimos N horas. Retorna dict con counts + WR."""
    cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)).isoformat()
    try:
        conn = sqlite3.connect(tracker.DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            SELECT
                SUM(CASE WHEN status IN ('FULL_WON','PARTIAL_WON','PARTIAL_CLOSED','WON') THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN status='LOST' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) as open_n,
                COUNT(*) as total
            FROM trades
            WHERE (is_sim=0 OR is_sim IS NULL)
              AND open_time >= ?
        """, (cutoff,))
        wins, losses, open_n, total = cur.fetchone()
        conn.close()
        wins = wins or 0
        losses = losses or 0
        open_n = open_n or 0
        total = total or 0
        closed = wins + losses
        wr = (wins / closed * 100) if closed > 0 else 0.0
        return {"wins": wins, "losses": losses, "open": open_n, "total": total, "closed": closed, "wr": wr}
    except Exception as e:
        logger.error("WR window error: %s", e)
        return {"wins": 0, "losses": 0, "open": 0, "total": 0, "closed": 0, "wr": 0.0}


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

    return (
        f"📊 <b>REPORTE DIARIO ZENITH</b>\n"
        f"<code>{today}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\n<b>Win Rate</b>\n"
        f"  24h:  <b>{w24['wr']:.1f}%</b> ({w24['wins']}W / {w24['losses']}L)  {_delta_emoji(w24['wr']) if w24['closed']>0 else ''}\n"
        f"  7d:   <b>{w7d['wr']:.1f}%</b> ({w7d['wins']}W / {w7d['losses']}L)  {trend}\n"
        f"  30d:  <b>{w30d['wr']:.1f}%</b> ({w30d['wins']}W / {w30d['losses']}L)\n"
        f"  Baseline ({BASELINE_LABEL}): {BASELINE_WR}%\n"
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
        f"<i>/winrate · /pos · /budget para detalle</i>"
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
