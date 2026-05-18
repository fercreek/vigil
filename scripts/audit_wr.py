#!/usr/bin/env python3
"""
audit_wr.py — Genera una entrada de auditoría de Win Rate y la appendea a _AUDIT_LOG.md.

Uso:
    python scripts/audit_wr.py              # audit de los últimos 14 días
    python scripts/audit_wr.py --days 7    # últimos 7 días
    python scripts/audit_wr.py --no-push   # sin git commit/push

Cron ejemplo (cada domingo 09:00):
    0 9 * * 0 cd /ruta/vigil && python scripts/audit_wr.py >> logs/audit.log 2>&1
"""

import sqlite3
import os
import sys
import argparse
import subprocess
from datetime import datetime, timedelta, timezone

REPO_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE     = os.getenv("TRACKER_DB", os.path.join(REPO_ROOT, "trades.db"))
AUDIT_LOG   = os.path.join(REPO_ROOT, "_AUDIT_LOG.md")
BASELINE_WR = 18.7
BASELINE_N  = 91

WIN_STATUSES  = ("FULL_WON", "PARTIAL_WON", "PARTIAL_CLOSED")
LOSE_STATUS   = "LOST"
OPEN_STATUS   = "OPEN"
CLOSED_STATUSES = WIN_STATUSES + (LOSE_STATUS,)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def _conn():
    if not os.path.exists(DB_FILE):
        return None
    return sqlite3.connect(DB_FILE)


def _since_dt(days: int) -> str:
    """Devuelve ISO timestamp del hace N días (UTC)."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def query_global(conn, since: str):
    """WR global REAL (is_sim=0) en la ventana de tiempo."""
    c = conn.cursor()
    c.execute("""
        SELECT
            SUM(CASE WHEN status IN ('FULL_WON','PARTIAL_WON','PARTIAL_CLOSED') THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'LOST' THEN 1 ELSE 0 END),
            COUNT(*)
        FROM trades
        WHERE status IN ('FULL_WON','PARTIAL_WON','PARTIAL_CLOSED','LOST')
          AND (is_sim = 0 OR is_sim IS NULL)
          AND open_time >= ?
    """, (since,))
    row = c.fetchone()
    wins, losses, total = row[0] or 0, row[1] or 0, row[2] or 0
    wr = round(wins / total * 100, 1) if total > 0 else None
    return {"wins": wins, "losses": losses, "total": total, "wr": wr}


def query_by_strategy(conn, since: str) -> list:
    """WR por strategy_version + alert_type. Solo trades REALES en la ventana."""
    c = conn.cursor()
    c.execute("""
        SELECT
            strategy_version,
            alert_type,
            SUM(CASE WHEN status IN ('FULL_WON','PARTIAL_WON','PARTIAL_CLOSED') THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN status = 'LOST' THEN 1 ELSE 0 END) AS losses,
            COUNT(*) AS total
        FROM trades
        WHERE status IN ('FULL_WON','PARTIAL_WON','PARTIAL_CLOSED','LOST')
          AND (is_sim = 0 OR is_sim IS NULL)
          AND open_time >= ?
        GROUP BY strategy_version, alert_type
        ORDER BY total DESC
    """, (since,))
    rows = c.fetchall()
    result = []
    for version, alert_type, wins, losses, total in rows:
        wr = round(wins / total * 100, 1) if total > 0 else 0.0
        result.append({
            "version": version or "—",
            "alert_type": alert_type or "—",
            "wins": wins or 0,
            "losses": losses or 0,
            "total": total or 0,
            "wr": wr,
        })
    return result


def query_sim_comparison(conn, since: str) -> dict:
    """Compara WR REAL vs SIM en la ventana."""
    c = conn.cursor()
    def _calc(is_sim):
        c.execute("""
            SELECT
                SUM(CASE WHEN status IN ('FULL_WON','PARTIAL_WON','PARTIAL_CLOSED') THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'LOST' THEN 1 ELSE 0 END),
                COUNT(*)
            FROM trades
            WHERE status IN ('FULL_WON','PARTIAL_WON','PARTIAL_CLOSED','LOST')
              AND is_sim = ?
              AND open_time >= ?
        """, (is_sim, since))
        row = c.fetchone()
        wins, losses, total = row[0] or 0, row[1] or 0, row[2] or 0
        wr = round(wins / total * 100, 1) if total > 0 else None
        return {"wins": wins, "losses": losses, "total": total, "wr": wr}
    return {"real": _calc(0), "sim": _calc(1)}


def query_stuck_open(conn) -> int:
    """Trades en OPEN hace más de 7 días (candidatos a stuck)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN' AND open_time < ?", (cutoff,))
    return c.fetchone()[0]


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def _wr_str(wr) -> str:
    if wr is None:
        return "N/D"
    return f"{wr:.1f}%"


def _delta_str(wr) -> str:
    if wr is None:
        return "—"
    delta = wr - BASELINE_WR
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f}pp"


def _regime(wr) -> str:
    if wr is None:
        return "⬜ Sin datos"
    if wr >= 35:
        return "✅ ≥35% — pagar TradingView Essential, ronda 6"
    if wr >= 25:
        return "🟡 25-35% — atacar _BACKLOG.md (D1 trigger_conditions)"
    if wr >= 18:
        return "🔴 <25% — investigar gap backtest vs prod"
    return "🔴 <18% — por debajo de baseline, urgente"


def _pf_regime(pf) -> str:
    if pf is None:
        return "⬜ Sin datos"
    if pf >= 1.5:
        return "✅"
    if pf >= 1.0:
        return "🟡"
    return "🔴"


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def run_audit(days: int, push: bool) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    since = _since_dt(days)

    conn = _conn()
    db_ok = conn is not None

    if db_ok:
        global_data  = query_global(conn, since)
        by_strategy  = query_by_strategy(conn, since)
        sim_cmp      = query_sim_comparison(conn, since)
        stuck        = query_stuck_open(conn)
        conn.close()
    else:
        global_data  = {"wins": 0, "losses": 0, "total": 0, "wr": None}
        by_strategy  = []
        sim_cmp      = {"real": {"total": 0, "wr": None}, "sim": {"total": 0, "wr": None}}
        stuck        = 0

    wr     = global_data["wr"]
    total  = global_data["total"]
    wins   = global_data["wins"]
    losses = global_data["losses"]

    # Profit Factor (aproximado si no hay PnL en USD: wins/losses ponderado 2:1 R:R)
    pf = round((wins * 2) / losses, 2) if losses > 0 else None

    # Tabla por estrategia
    if by_strategy:
        strat_rows = "\n".join(
            f"| {r['alert_type']} | {r['version']} | {r['wins']} | {r['losses']} | {r['total']} | {_wr_str(r['wr'])} |"
            for r in by_strategy
        )
        strat_table = f"""\
| Estrategia | Version | Wins | Losses | Total | WR |
|------------|---------|------|--------|-------|-----|
{strat_rows}"""
    else:
        strat_table = "_Sin trades cerrados en la ventana._"

    # SIM vs REAL
    real_wr = _wr_str(sim_cmp["real"]["wr"])
    sim_wr  = _wr_str(sim_cmp["sim"]["wr"])
    real_n  = sim_cmp["real"]["total"]
    sim_n   = sim_cmp["sim"]["total"]

    if not db_ok:
        db_status = f"⛔ DB no encontrada en `{DB_FILE}` — sin Railway Volume o TRACKER_DB no seteada"
    elif total == 0:
        db_status = f"⚠️ DB presente pero 0 trades cerrados en {days}d — DB posiblemente reseteada por redeploy"
    else:
        db_status = f"✅ `{DB_FILE}` — {total} trades cerrados en {days}d"

    stuck_flag = f"🔴 {stuck} trades OPEN >7d (posible stuck)" if stuck > 0 else "✅ Sin trades stuck"

    vol_flag = ""
    if total < 10:
        vol_flag = f"\n> ⚠️ Volumen <10 trades — considerar relajar `MIN_CONFLUENCE_SCORE` 5→4 o `RVOL_MIN_ENTRY` 0.8→0.7"

    entry = f"""
---

## Audit {today} — Checkpoint {days}d

**DB:** {db_status}
**Trades stuck:** {stuck_flag}
{vol_flag}

### WR Global {days}d

| Métrica | Valor | vs Baseline 18.7% |
|---------|-------|-------------------|
| WR global | {_wr_str(wr)} | {_delta_str(wr)} |
| Trades cerrados | {total} | — |
| Wins | {wins} | — |
| Losses | {losses} | — |
| PF estimado (2:1 R:R) | {f"{pf:.2f}" if pf else "N/D"} | {_pf_regime(pf)} |

**Régimen:** {_regime(wr)}

### WR por Estrategia

{strat_table}

### REAL vs SIM

| Tipo | WR | Trades |
|------|----|--------|
| REAL (activados) | {real_wr} | {real_n} |
| SIM (skiados) | {sim_wr} | {sim_n} |

### Acciones

"""

    # Acciones automáticas según régimen
    actions = []
    if not db_ok:
        actions.append("🔴 **1** — Configurar Railway Volume + env var `TRACKER_DB=/app/data/trades.db` (ver `docs/VOLUME_SETUP.md`)")
    elif total < 10:
        actions.append(f"🟡 **1** — Volumen bajo ({total} trades). Relajar `MIN_CONFLUENCE_SCORE` 5→4 en config.py")
        actions.append("🟡 **2** — Reactivar commodities_bot si RAM lo permite (actualmente comentado en main.py)")
    elif wr is not None and wr >= 35:
        actions.append("✅ **1** — WR ≥ 35%: pagar TradingView Essential ($14.95/mo), iniciar ronda 6 Hyperopt")
        actions.append("✅ **2** — Acumular data adicional 14d antes de cambiar parámetros")
    elif wr is not None and wr >= 25:
        actions.append("🟡 **1** — Atacar `_BACKLOG.md D1`: poblar `trigger_conditions` en todos los `log_trade()` calls")
        actions.append("🟡 **2** — Revisar D5 near_miss logging para entender señales perdidas")
    else:
        actions.append("🔴 **1** — WR por debajo de threshold. Auditar slippage real vs backtest con backtester.py")
        actions.append("🔴 **2** — Comparar parámetros live vs walk-forward. ¿Cambió algo desde el último backtest?")

    if stuck > 0:
        actions.append(f"🔴 **{len(actions)+1}** — Cerrar {stuck} trade(s) stuck OPEN >7d via `/pos` en Telegram")

    entry += "\n".join(f"- {a}" for a in actions)
    entry += "\n"

    return entry


def prepend_to_audit_log(entry: str):
    header = "# _AUDIT_LOG — Zenith Trading Suite\n> Entradas más recientes arriba. Baseline pre-fixes: WR global = **18.7%** (91 trades).\n"

    if os.path.exists(AUDIT_LOG):
        with open(AUDIT_LOG, "r") as f:
            content = f.read()
        # Insertar después del header (primera línea que comience con ---)
        parts = content.split("---", 1)
        if len(parts) == 2:
            new_content = parts[0] + entry + "\n---" + parts[1]
        else:
            new_content = content + entry
    else:
        new_content = header + entry

    with open(AUDIT_LOG, "w") as f:
        f.write(new_content)


def git_commit_push(days: int, push: bool):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    msg = f"audit: WR checkpoint {today}"
    subprocess.run(["git", "-C", REPO_ROOT, "add", "_AUDIT_LOG.md"], check=True)
    subprocess.run(["git", "-C", REPO_ROOT, "commit", "-m", msg], check=True)
    if push:
        subprocess.run(["git", "-C", REPO_ROOT, "push"], check=True)
        print("✅ Push completo.")
    else:
        print("ℹ️  Commit hecho, sin push (--no-push).")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Audit Win Rate — Zenith Trading Suite")
    parser.add_argument("--days",    type=int, default=14, help="Ventana en días (default: 14)")
    parser.add_argument("--no-push", action="store_true",  help="Solo commit, sin push")
    parser.add_argument("--dry-run", action="store_true",  help="Solo imprime, sin escribir ni commitear")
    args = parser.parse_args()

    print(f"[audit_wr] DB: {DB_FILE}")
    print(f"[audit_wr] Ventana: {args.days}d | Push: {not args.no_push}")

    entry = run_audit(days=args.days, push=not args.no_push)

    if args.dry_run:
        print("\n--- PREVIEW ---")
        print(entry)
        return

    prepend_to_audit_log(entry)
    print(f"[audit_wr] _AUDIT_LOG.md actualizado.")

    try:
        git_commit_push(args.days, push=not args.no_push)
    except subprocess.CalledProcessError as e:
        print(f"[audit_wr] Git falló: {e} — el log fue escrito igualmente.")


if __name__ == "__main__":
    main()
