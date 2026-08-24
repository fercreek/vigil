"""scoreboard.py — the report that decides whether a ruleset lives or dies.

This is where the -18%-from-23%-of-rows incident (see docs/_MAP-instrument.md,
the "11 vendedores" retro) gets structurally impossible: every figure computed
below carries its denominator in the same dict entry, at the same weight.
A number without its n does not get computed here. render_report() -- the
Spanish, human-readable text Fernando actually reads -- lives in
report_text.py and inherits that invariant; it does not re-decide it.

Design choices this file is accountable for:
  - No win rate below n=30. At n~91 the 95% CI on a WR is roughly +/-8 points --
    that does not separate an 18% ruleset from a 26% one, so returning a bare
    percentage would be reporting noise as a verdict.
  - Bootstrap CI (not a closed-form normal CI) for expectancy: the whole point
    of this instrument is small-n honesty, and a closed-form CI is exactly as
    confident-sounding as the number it is meant to bound.
  - Taken-rate < 60% suspends conclusions about signal quality: below that
    coverage there is no way to tell a bad signal from a bad fill apart.
  - max_drawdown / profit_factor are reused from the legacy metrics.py
    (SaintQuant-benchmarked, still correct). Sharpe/Sortino/Calmar/SQN are
    deliberately NOT ported: metrics.py:39 "annualizes" with sqrt(len(returns))
    which does not annualize anything, and at n<100 those ratios are lab coats
    on noise.
"""
from __future__ import annotations

import argparse
import random
import sqlite3
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

if __package__ in (None, ""):  # `python instrument/scoreboard.py` needs the repo root on sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instrument.report_text import render_report  # noqa: F401 -- re-exported, callers import it from here
from instrument.stats import build_equity_curve, calculate_max_drawdown, calculate_profit_factor
from instrument import equities
from instrument.store import connect

MAX_HOLD_HOURS = 72.0     # a SENT signal older than this with no resolution is orphaned, not late
# ...pero 72 horas solo son 72 velas donde el mercado no cierra. En acciones son 14,
# asi que una senal viva y sana se contaria como muerta a los tres dias. El mismo
# desajuste que main.py::_in_cooldown tenia antes de cablear acciones.
MAX_HOLD_HOURS_EQUITY = equities.cooldown_hours("NVDA", 72)   # ~372 h
MIN_N_FOR_WR = 30         # below this a win rate is noise, not a verdict
KILL_RULE_N = 100         # the sample the kill-rule waits for before it can fire
TAKEN_RATE_FLOOR = 0.60   # below this, signal quality and execution quality are unseparable
RISK_PCT_PER_R = 1.0      # equity-curve convention: 1R == 1% of equity, for drawdown/PF only


def bootstrap_ci(values: Sequence[float], iterations: int = 2000, alpha: float = 0.05,
                  seed: int | None = None) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean. No dependency beyond random/statistics.
    n here is always small by design -- a normal-approximation CI would claim a
    precision the sample does not have."""
    if len(values) < 2:
        only = values[0] if values else 0.0
        return (only, only)
    rng = random.Random(seed)
    n = len(values)
    means = [statistics.fmean(values[rng.randrange(n)] for _ in range(n)) for _ in range(iterations)]
    means.sort()
    lo = max(0, int((alpha / 2) * iterations))
    hi = min(iterations - 1, int((1 - alpha / 2) * iterations))
    return (means[lo], means[hi])


def win_rate(r_values: Sequence[float], min_n: int = MIN_N_FOR_WR) -> tuple[float | None, int]:
    """Refuses to answer below min_n. Returns (None, n) rather than a number
    dressed up with an asterisk -- the asterisk gets dropped when the report
    is quoted three docs downstream, the None cannot be."""
    n = len(r_values)
    if n < min_n:
        return None, n
    wins = sum(1 for r in r_values if r > 0)
    return round(wins / n * 100, 1), n


def kill_rule_verdict(n_resolved: int, ci_upper: float, threshold: int = KILL_RULE_N) -> str:
    if n_resolved < threshold:
        return f"EN OBSERVACIÓN (n={n_resolved}/{threshold})"
    return "RETIRAR" if ci_upper < 0 else "VIVO"


UNIVERSES = ("crypto", "equities")


def _where(ruleset: str | None, universe: str | None = None) -> tuple[str, list[Any]]:
    """Clausula AND acumulada. `universe` parte la tabla en dos poblaciones que no
    deben promediarse: en acciones la regla se midio sobre n=138 y solo LONG; en
    cripto sobre n=26 y los dos lados. Una sola cifra sobre las dos no describe
    ninguna -- y el numero resultante se lee como si describiera ambas."""
    clauses, params = [], []
    if ruleset:
        clauses.append("s.ruleset_version = ?")
        params.append(ruleset)
    if universe in UNIVERSES:
        marks = ",".join("?" * len(equities.EQUITY_SYMBOLS))
        op = "IN" if universe == "equities" else "NOT IN"
        clauses.append(f"s.symbol {op} ({marks})")
        params.extend(equities.EQUITY_SYMBOLS)
    elif universe is not None:
        raise ValueError(f"universe debe ser uno de {UNIVERSES} o None, no {universe!r}")
    return ("".join(f" AND {c}" for c in clauses), params)


def _counts_by_decision(conn: sqlite3.Connection, ruleset: str | None,
                        universe: str | None = None) -> dict[str, int]:
    clause, params = _where(ruleset, universe)
    clause = ("WHERE 1=1" + clause) if clause else ""
    rows = conn.execute(f"SELECT decision, COUNT(*) AS n FROM signals s {clause} "
                        "GROUP BY decision", params).fetchall()
    return {row["decision"]: row["n"] for row in rows}


def _fetch_resolved(conn: sqlite3.Connection, ruleset: str | None,
                    universe: str | None = None) -> list[sqlite3.Row]:
    clause, params = _where(ruleset, universe)
    sql = ("SELECT s.id, s.breakeven_wr, r.r_realized, r.mfe_r, r.mae_r FROM signals s "
          "JOIN resolutions r ON r.signal_id = s.id WHERE s.decision = 'SENT'" + clause)
    return conn.execute(sql, params).fetchall()


def _count_orphans(conn: sqlite3.Connection, ruleset: str | None,
                    max_hold_hours: float | None = None, now: datetime | None = None,
                    universe: str | None = None) -> int:
    """SENT, unresolved, and older than the max-hold: not late, dead."""
    now = now or datetime.now(timezone.utc)
    if max_hold_hours is None:
        max_hold_hours = MAX_HOLD_HOURS_EQUITY if universe == "equities" else MAX_HOLD_HOURS
    cutoff = (now - timedelta(hours=max_hold_hours)).isoformat()
    clause, params = _where(ruleset, universe)
    sql = ("SELECT COUNT(*) AS n FROM signals s LEFT JOIN resolutions r ON r.signal_id = s.id "
          "WHERE s.decision = 'SENT' AND r.signal_id IS NULL AND s.emitted_at < ?" + clause)
    return conn.execute(sql, [cutoff] + params).fetchone()["n"]


def _taken_rate(conn: sqlite3.Connection, resolved_rows: Sequence[sqlite3.Row]) -> tuple[int, int]:
    total = len(resolved_rows)
    if total == 0:
        return 0, 0
    ids = [row["id"] for row in resolved_rows]
    placeholders = ",".join("?" for _ in ids)
    marked = conn.execute(
        f"SELECT COUNT(DISTINCT signal_id) AS n FROM manual_fills WHERE signal_id IN ({placeholders})",
        ids).fetchone()["n"]
    return marked, total


def _taken_feedback(conn: sqlite3.Connection, resolved_rows: Sequence[sqlite3.Row]) -> list[sqlite3.Row]:
    """What happened to the signals a human marked TOMADA. Without this loop
    back to the person who pressed the button, marking stops within a couple
    of weeks -- and that is precisely what drives taken-rate under the 60%
    floor this same report enforces above: a guard the system itself causes."""
    ids = [row["id"] for row in resolved_rows]
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    return conn.execute(
        f"SELECT r.outcome, r.r_realized, m.r_realized_human FROM signals s "
        f"JOIN resolutions r ON r.signal_id = s.id JOIN manual_fills m ON m.signal_id = s.id "
        f"WHERE s.id IN ({placeholders}) AND m.taken = 1", ids).fetchall()


def build_report(conn: sqlite3.Connection, ruleset: str | None = None,
                 universe: str | None = None) -> dict[str, Any]:
    emitted = _counts_by_decision(conn, ruleset, universe)
    total_emitted = sum(emitted.values())
    resolved = _fetch_resolved(conn, ruleset, universe)
    n_resolved = len(resolved)
    orphans = _count_orphans(conn, ruleset, universe=universe)

    r_values = [row["r_realized"] for row in resolved]
    mfe_values = [row["mfe_r"] for row in resolved]
    mae_values = [row["mae_r"] for row in resolved]
    breakeven_values = [row["breakeven_wr"] for row in resolved if row["breakeven_wr"] is not None]

    expectancy = statistics.fmean(r_values) if r_values else 0.0
    ci_lo, ci_hi = bootstrap_ci(r_values) if r_values else (0.0, 0.0)
    wr, wr_n = win_rate(r_values)

    marked, taken_total = _taken_rate(conn, resolved)
    taken_rate_value = marked / taken_total if taken_total else 0.0
    suspended = taken_total > 0 and taken_rate_value < TAKEN_RATE_FLOOR

    taken_rows = _taken_feedback(conn, resolved)
    taken_by_outcome: dict[str, int] = {}
    taken_r_values = []
    for row in taken_rows:
        taken_by_outcome[row["outcome"]] = taken_by_outcome.get(row["outcome"], 0) + 1
        taken_r_values.append(row["r_realized_human"] if row["r_realized_human"] is not None
                              else row["r_realized"])

    trades = [{"pnl_pct": r * RISK_PCT_PER_R} for r in r_values]
    equity = build_equity_curve(trades) if trades else []
    max_dd = calculate_max_drawdown([e["balance"] for e in equity]) if equity else 0.0
    profit_factor = calculate_profit_factor(r_values) if r_values else 0.0

    return {
        "ruleset": ruleset, "universe": universe,
        "max_hold_hours": MAX_HOLD_HOURS_EQUITY if universe == "equities" else MAX_HOLD_HOURS,
        "emitted_by_decision": emitted, "total_emitted": total_emitted,
        "n_resolved": n_resolved, "orphans": orphans,
        "expectancy_r": expectancy, "expectancy_ci": (ci_lo, ci_hi),
        "win_rate": wr, "win_rate_n": wr_n,
        "breakeven_wr": statistics.fmean(breakeven_values) if breakeven_values else None,
        "breakeven_wr_n": len(breakeven_values),
        "median_mfe_r": statistics.median(mfe_values) if mfe_values else None,
        "median_mae_r": statistics.median(mae_values) if mae_values else None,
        "mfe_mae_n": len(resolved),
        "taken_rate": taken_rate_value, "taken_marked": marked, "taken_total": taken_total,
        "conclusions_suspended": suspended,
        "taken_feedback_n": len(taken_rows), "taken_feedback_by_outcome": taken_by_outcome,
        "taken_feedback_mean_r": statistics.fmean(taken_r_values) if taken_r_values else None,
        "kill_rule_verdict": kill_rule_verdict(n_resolved, ci_hi),
        "max_drawdown_pct": max_dd, "profit_factor": profit_factor,
    }


def build_reports_by_universe(conn: sqlite3.Connection,
                              ruleset: str | None = None) -> list[dict[str, Any]]:
    """Un marcador por universo, nunca uno solo encima de los dos.

    Devuelve solo los universos que tienen algo que contar: al arrancar acciones
    el 2026-08-23 su marcador esta vacio durante semanas, y una seccion vacia al
    lado de una llena invita a leerlas juntas."""
    reportes = [build_report(conn, ruleset, u) for u in UNIVERSES]
    vivos = [r for r in reportes if r["total_emitted"] > 0]
    return vivos or reportes[:1]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Scoreboard for the Zenith instrument.")
    parser.add_argument("--db", required=True, help="path to the sqlite instrument db")
    parser.add_argument("--ruleset", default=None, help="filter to one ruleset_version")
    parser.add_argument("--universe", default=None, choices=[*UNIVERSES, "all"],
                        help="crypto | equities | all (por defecto: cada uno por separado)")
    args = parser.parse_args(argv)

    with connect(args.db) as conn:
        if args.universe == "all":
            print(render_report(build_report(conn, args.ruleset)))
        elif args.universe:
            print(render_report(build_report(conn, args.ruleset, args.universe)))
        else:
            print("\n\n".join(render_report(r)
                               for r in build_reports_by_universe(conn, args.ruleset)))


if __name__ == "__main__":
    main()
