"""report_text.py — turns scoreboard.build_report()'s dict into the message
Fernando actually reads on his phone, in Spanish, without ever putting a raw
Python structure (a dict/list literal) in front of him.

Split out of scoreboard.py on 2026-08-21 -- scoreboard.py owns the math and
the invariants documented in its own docstring (every figure keeps its n);
this file owns only the words, and inherits that invariant rather than
re-deciding it: nothing here drops a denominator scoreboard.py computed.

No import of scoreboard at module level, on purpose: scoreboard.py imports
render_report from here, so importing scoreboard back at the top would be a
real circular import depending on which module loads first. render_report()
pulls scoreboard's threshold constants with a local import instead -- by the
time anyone calls it, both modules have already finished loading.
"""
from __future__ import annotations

from typing import Any

_DECISION_ES = {
    "SENT": "mandadas como alerta",
    "SUPPRESSED": "descartadas",
    "BLOCKED": "bloqueadas por error",
}

_OUTCOME_ES = {
    "SL": "se fue a stop",
    "TP2": "llegó directo a TP2",
    "TP1_THEN_TP2": "tocó TP1 y luego TP2",
    "TP1_THEN_BE": "tocó TP1 y cerró en breakeven",
    "VOID": "se anuló",
}


def _decision_breakdown(counts: dict[str, int]) -> str:
    parts = [f"{n} {_DECISION_ES.get(k, k.lower())}" for k, n in counts.items() if n]
    return ", ".join(parts) if parts else "0"


def _outcome_breakdown(counts: dict[str, int]) -> str:
    return ", ".join(f"{n} {_OUTCOME_ES.get(k, k.lower())}" for k, n in counts.items())


_UNIVERSE_LABEL = {"crypto": "cripto", "equities": "acciones"}


def _header(ruleset: str | None, empty: bool, universe: str | None = None) -> str:
    """El universo va en el encabezado porque las dos poblaciones no comparten
    evidencia: la regla se midio sobre n=138 y solo LONG en acciones, y sobre n=26
    con los dos lados en cripto. Un marcador sin etiqueta invita a leer la cifra de
    uno como si valiera para el otro."""
    tag = f" ({ruleset})" if ruleset else ""
    quien = _UNIVERSE_LABEL.get(universe)
    tag = f" · {quien}{tag}" if quien else tag
    return f"📊 Marcador{tag} — todavía sin resultados" if empty else f"📊 Marcador{tag}"


def _empty_summary(r: dict[str, Any], min_n: int, max_hold_hours: float) -> list[str]:
    counts, total, n_resolved = r["emitted_by_decision"], r["total_emitted"], r["n_resolved"]
    sent = counts.get("SENT", 0)
    if total == 0:
        body = "Todavía no he evaluado ninguna señal."
    elif sent == 0:
        body = f"Llevo {total} señales revisadas y ninguna llegó a ser alerta."
    else:
        body = (f"Llevo {total} señales revisadas, {sent} se mandaron como alerta "
                "y ninguna se ha resuelto todavía.")
    goal = f"Cuando haya {min_n} resueltas te puedo decir si esto sirve o no; hoy son {n_resolved}."
    lines = [f"{body} {goal}"]
    if r["orphans"]:
        lines.append(f"{r['orphans']} de las mandadas llevan más de {max_hold_hours:.0f}h "
                     "sin resolverse — se dan por perdidas.")
    return lines


def _summary_lines(r: dict[str, Any], max_hold_hours: float) -> list[str]:
    line = f"{r['total_emitted']} señales revisadas: {_decision_breakdown(r['emitted_by_decision'])}."
    note = f"De las mandadas, {r['n_resolved']} ya se resolvieron"
    if r["orphans"]:
        note += f" ({r['orphans']} llevan más de {max_hold_hours:.0f}h sin resolverse, se dan por perdidas)"
    return [line, note + "."]


def _expectancy_line(r: dict[str, Any]) -> str:
    lo, hi = r["expectancy_ci"]
    return (f"Gana o pierde por señal, en promedio: {r['expectancy_r']:+.2f}R "
           f"(n={r['n_resolved']}, rango probable {lo:+.2f}R a {hi:+.2f}R). "
           "R = tu unidad de riesgo por operación.")


def _win_rate_line(r: dict[str, Any], min_n: int) -> str:
    if r["win_rate"] is None:
        return f"Aciertos: no alcanza para un % (mínimo {min_n}, llevas {r['win_rate_n']})."
    return f"Aciertos: {r['win_rate']}% (n={r['win_rate_n']})."


def _suspended_line(r: dict[str, Any], floor: float) -> str | None:
    if not r["conclusions_suspended"]:
        return None
    return (f"⚠️ Solo marcaste {r['taken_marked']}/{r['taken_total']} a mano "
           f"({r['taken_rate']:.0%}), por debajo del {floor:.0%}: con menos no distingo "
           "señal mala de mal llenado, así que las conclusiones de aquí quedan en pausa.")


def _taken_rate_line(r: dict[str, Any]) -> str | None:
    if r["taken_total"] == 0:
        return None
    return f"De lo que marcaste tú a mano: {r['taken_marked']}/{r['taken_total']} ({r['taken_rate']:.0%})."


def _taken_feedback_line(r: dict[str, Any]) -> str:
    if not r["taken_feedback_n"]:
        return "De lo que marcaste TOMADA, ninguna se ha resuelto todavía."
    outcomes = _outcome_breakdown(r["taken_feedback_by_outcome"])
    return (f"De lo que sí tomaste: {r['taken_feedback_n']} resueltas — {outcomes} — "
           f"promedio {r['taken_feedback_mean_r']:+.2f}R.")


def _pf_dd_line(r: dict[str, Any], min_n: int, risk_pct: float) -> str | None:
    if r["n_resolved"] < min_n:
        return None
    pf = r["profit_factor"]
    pf_txt = ("sin pérdidas en la muestra" if pf == float("inf")
             else f"ganas {pf:.2f}R por cada 1R que pierdes")
    return (f"{pf_txt} · peor caída simulada: {r['max_drawdown_pct']:.1f}% del capital "
           f"(n={r['n_resolved']}, asumiendo {risk_pct:.0f}% de riesgo por señal).")


def render_report(report: dict[str, Any]) -> str:
    """The whole marker, in Spanish, denominators intact. Empty (n_resolved=0)
    stays 2-4 lines -- that is the normal early state, not an error. Populated
    tops out around 10 -- see the helpers above for what earns a line."""
    from .scoreboard import MAX_HOLD_HOURS, MIN_N_FOR_WR, TAKEN_RATE_FLOOR, RISK_PCT_PER_R
    r = report

    if r["n_resolved"] == 0:
        return "\n".join([_header(r["ruleset"], True, r.get("universe"))]
                         + _empty_summary(r, MIN_N_FOR_WR, r.get("max_hold_hours", MAX_HOLD_HOURS)))

    lines = [_header(r["ruleset"], False, r.get("universe"))] \
            + _summary_lines(r, r.get("max_hold_hours", MAX_HOLD_HOURS))
    warning = _suspended_line(r, TAKEN_RATE_FLOOR)
    if warning:
        lines.append(warning)
    lines.append(_expectancy_line(r))
    lines.append(_win_rate_line(r, MIN_N_FOR_WR))
    rate_line = _taken_rate_line(r)
    if rate_line:
        lines.append(rate_line)
    lines.append(_taken_feedback_line(r))
    pf_dd = _pf_dd_line(r, MIN_N_FOR_WR, RISK_PCT_PER_R)
    if pf_dd:
        lines.append(pf_dd)
    lines.append(f"Veredicto: {r['kill_rule_verdict']}.")
    return "\n".join(lines)
