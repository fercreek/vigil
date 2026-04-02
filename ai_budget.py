"""
ai_budget.py — Rastreador de consumo de APIs de IA y presupuesto mensual.

Responsabilidades:
  - Registrar cada llamada a Claude/Gemini con tokens y costo estimado
  - Bloquear llamadas cuando se alcanza el límite mensual ($10) o diario (15 decisiones)
  - Exponer métricas para el dashboard y Telegram
  - Detectar cuando múltiples símbolos reaccionan para agrupar el análisis

Precios aproximados (2025):
  - Claude Haiku 4.5:  $0.80/MTok input  |  $4.00/MTok output
  - Gemini 2.5 Flash:  free tier / negligible
"""

import sqlite3
import os
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

# Ruta de la misma BD que tracker para no dispersar archivos
DB_FILE = os.getenv("TRACKER_DB", "data/trades.db")

# ─── Límites ──────────────────────────────────────────────────────────────────
MAX_MONTHLY_USD      = float(os.getenv("AI_MAX_MONTHLY_USD", "10.0"))
MAX_DAILY_DECISIONS  = int(os.getenv("AI_MAX_DAILY_DECISIONS", "15"))

# Warn al 80% del presupuesto mensual
BUDGET_WARN_PCT = 80

# ─── Costos por token (USD) ───────────────────────────────────────────────────
COST_PER_TOKEN = {
    "claude-haiku-4-5-20251001": {"in": 0.80 / 1_000_000, "out": 4.00 / 1_000_000},
    "claude-haiku-4-5":          {"in": 0.80 / 1_000_000, "out": 4.00 / 1_000_000},
    "gemini-2.5-flash":          {"in": 0.0,               "out": 0.0},
}

# call_type que cuentan para el límite diario de "decisiones críticas"
CRITICAL_CALL_TYPES = {"decision", "bias"}


def init_db():
    """Crea la tabla ai_calls si no existe. Llamar al inicio de la app."""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True) if os.path.dirname(DB_FILE) else None
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_calls (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT NOT NULL,
            provider    TEXT NOT NULL,
            model       TEXT NOT NULL,
            call_type   TEXT NOT NULL,
            tokens_in   INTEGER DEFAULT 0,
            tokens_out  INTEGER DEFAULT 0,
            cost_usd    REAL DEFAULT 0.0,
            symbol      TEXT DEFAULT '',
            approved    INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


def log_ai_call(provider: str, model: str, call_type: str,
                tokens_in: int = 0, tokens_out: int = 0,
                symbol: str = "", approved: bool = True) -> float:
    """
    Registra una llamada de IA con su costo estimado.
    Retorna el costo en USD de la llamada.
    """
    rates = COST_PER_TOKEN.get(model, {"in": 0.0, "out": 0.0})
    cost_usd = tokens_in * rates["in"] + tokens_out * rates["out"]

    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("""
            INSERT INTO ai_calls
                (ts, provider, model, call_type, tokens_in, tokens_out, cost_usd, symbol, approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now().isoformat(), provider, model, call_type,
              tokens_in, tokens_out, round(cost_usd, 8), symbol, int(approved)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ai_budget] Error logging call: {e}")

    return round(cost_usd, 6)


def get_monthly_cost(month: str = None) -> dict:
    """
    Retorna el costo y métricas del mes indicado (formato YYYY-MM).
    Por defecto usa el mes actual.
    """
    if not month:
        month = datetime.now().strftime("%Y-%m")
    try:
        conn = sqlite3.connect(DB_FILE)
        row = conn.execute("""
            SELECT
                COALESCE(SUM(cost_usd), 0.0)                                          AS total,
                COUNT(*)                                                               AS calls,
                COALESCE(SUM(CASE WHEN provider='claude' THEN cost_usd ELSE 0 END), 0) AS claude_cost,
                COALESCE(SUM(CASE WHEN provider='gemini' THEN cost_usd ELSE 0 END), 0) AS gemini_cost,
                COALESCE(SUM(tokens_in),  0)                                           AS t_in,
                COALESCE(SUM(tokens_out), 0)                                           AS t_out
            FROM ai_calls
            WHERE ts LIKE ? AND approved = 1
        """, (f"{month}%",)).fetchone()
        conn.close()
        total, calls, claude_cost, gemini_cost, t_in, t_out = row
    except Exception as e:
        print(f"[ai_budget] Error getting monthly cost: {e}")
        total = calls = claude_cost = gemini_cost = t_in = t_out = 0

    used_pct = round(total / MAX_MONTHLY_USD * 100, 1)
    return {
        "month":            month,
        "total_usd":        round(total, 4),
        "calls":            calls,
        "claude_usd":       round(claude_cost, 4),
        "gemini_usd":       round(gemini_cost, 4),
        "tokens_in":        t_in,
        "tokens_out":       t_out,
        "budget_used_pct":  used_pct,
        "remaining_usd":    round(max(0.0, MAX_MONTHLY_USD - total), 4),
        "max_monthly_usd":  MAX_MONTHLY_USD,
    }


def get_daily_decisions(today: str = None) -> int:
    """Cuenta las decisiones críticas de IA del día (decision + bias)."""
    if not today:
        today = date.today().isoformat()
    try:
        conn = sqlite3.connect(DB_FILE)
        row = conn.execute("""
            SELECT COUNT(*) FROM ai_calls
            WHERE ts LIKE ? AND call_type IN ('decision', 'bias') AND approved = 1
        """, (f"{today}%",)).fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        print(f"[ai_budget] Error getting daily decisions: {e}")
        return 0


def can_use_ai(call_type: str = "decision") -> tuple:
    """
    Verifica si se puede hacer una llamada de IA.
    Retorna (True, "") si OK, o (False, "razón bloqueada") si no.
    """
    # Verificar presupuesto mensual
    monthly = get_monthly_cost()
    if monthly["total_usd"] >= MAX_MONTHLY_USD:
        return False, f"Presupuesto mensual agotado (${monthly['total_usd']:.2f} / ${MAX_MONTHLY_USD:.0f})"

    if monthly["budget_used_pct"] >= BUDGET_WARN_PCT:
        print(f"[ai_budget] ⚠️  Presupuesto al {monthly['budget_used_pct']:.0f}% — ${monthly['remaining_usd']:.4f} restantes")

    # Verificar límite diario solo para llamadas críticas
    if call_type in CRITICAL_CALL_TYPES:
        daily = get_daily_decisions()
        if daily >= MAX_DAILY_DECISIONS:
            return False, f"Límite diario alcanzado ({daily}/{MAX_DAILY_DECISIONS} decisiones)"

    return True, ""


def get_recent_calls(limit: int = 20) -> list:
    """Retorna las últimas N llamadas para el dashboard."""
    try:
        conn = sqlite3.connect(DB_FILE)
        rows = conn.execute("""
            SELECT ts, provider, model, call_type, tokens_in, tokens_out, cost_usd, symbol, approved
            FROM ai_calls
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [
            {
                "ts": r[0][:16],   # YYYY-MM-DDTHH:MM
                "provider":   r[1],
                "model":      r[2],
                "call_type":  r[3],
                "tokens_in":  r[4],
                "tokens_out": r[5],
                "cost_usd":   round(r[6], 6),
                "symbol":     r[7],
                "approved":   bool(r[8]),
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[ai_budget] Error getting recent calls: {e}")
        return []


def get_budget_summary_html() -> str:
    """Resumen formateado para Telegram o dashboard."""
    m = get_monthly_cost()
    daily = get_daily_decisions()
    filled = int(m["budget_used_pct"] / 10)
    bar = "█" * filled + "░" * (10 - filled)

    status_emoji = "🟢" if m["budget_used_pct"] < 60 else ("🟡" if m["budget_used_pct"] < 85 else "🔴")
    return (
        f"💰 <b>Presupuesto IA — {m['month']}</b> {status_emoji}\n"
        f"[{bar}] {m['budget_used_pct']:.1f}%\n"
        f"Gastado: <code>${m['total_usd']:.4f}</code> / <code>${m['max_monthly_usd']:.0f}</code>\n"
        f"├ Claude: <code>${m['claude_usd']:.4f}</code>\n"
        f"└ Gemini: <code>${m['gemini_usd']:.4f}</code>\n"
        f"Decisiones hoy: <code>{daily} / {MAX_DAILY_DECISIONS}</code>\n"
        f"Restante: <code>${m['remaining_usd']:.4f}</code>"
    )


# ─── Auto-init al importar ────────────────────────────────────────────────────
try:
    init_db()
except Exception:
    pass  # Si la BD no está lista aún, tracker.py la inicializará primero
