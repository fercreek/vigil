"""
test_suite.py — Suite canónica de períodos para iterar estrategias.

Uso:
    python test_suite.py                  # baseline con config actual
    python test_suite.py --label "iter1"  # tag para comparar runs
    python test_suite.py --json out.json  # exporta raw para diffing

Métrica principal: PnL agregado total + PF agregado + n_trades.
Una iteración mejora si: (PnL_total sube) AND (PF no baja > 0.1) AND (n no cae > 30%).
"""
import sys
import json
import argparse
from datetime import datetime
from backtester import Backtester

SYMBOLS = ["BTC", "ETH", "TAO", "ZEC"]
STRATEGIES = ["V1", "V3", "V4", "V5"]

# Suite canónica — los 7 períodos oficiales para iterar
PERIODS = [
    ("2025_FULL",  "2025-04-01", "2025-12-31"),
    ("2025_Q2",    "2025-04-01", "2025-06-30"),
    ("2025_Q3",    "2025-07-01", "2025-09-30"),
    ("2025_Q4",    "2025-10-01", "2025-12-31"),
    ("2026_M01",   "2026-01-01", "2026-01-31"),
    ("2026_M02",   "2026-02-01", "2026-02-28"),
    ("2026_M03",   "2026-03-01", "2026-03-29"),
]

# Pesos por símbolo (default 1.0 = sin sizing diferencial)
SYMBOL_WEIGHTS = {"BTC": 1.0, "ETH": 1.0, "TAO": 1.0, "ZEC": 1.0}


def aggregate(trades, weight=1.0):
    if not trades:
        return None
    n = len(trades)
    wins = sum(1 for t in trades if t["result"] in ("FULL_WON", "WIN_FULL", "PARTIAL_WON", "WIN_PARTIAL"))
    loss = sum(1 for t in trades if t["result"] == "LOST")
    pnl_raw = sum(t["pnl_pct"] for t in trades)
    pnl = pnl_raw * weight
    pf_num = sum(t["pnl_pct"] for t in trades if t["pnl_pct"] > 0) * weight
    pf_den = abs(sum(t["pnl_pct"] for t in trades if t["pnl_pct"] < 0)) * weight
    pf = pf_num / pf_den if pf_den > 0 else (float("inf") if pf_num > 0 else 0)
    wr = wins / n * 100 if n > 0 else 0
    return {
        "n": n, "w": wins, "l": loss, "wr": round(wr, 1),
        "pnl": round(pnl, 2), "pf": pf if pf == float("inf") else round(pf, 2),
        "pf_num": pf_num, "pf_den": pf_den,
    }


def run_suite(label="baseline", verbose=True):
    """Corre la suite completa. Retorna dict con resultados + agregado total."""
    results = {}
    total_pnl = 0.0
    total_pf_num = 0.0
    total_pf_den = 0.0
    total_n = 0
    total_w = 0

    for sym in SYMBOLS:
        weight = SYMBOL_WEIGHTS.get(sym, 1.0)
        for period_name, start, end in PERIODS:
            try:
                bt = Backtester()
                bt.load_data(sym, start=start, end=end)
                if len(bt.df) < 250:
                    continue
                for strat in STRATEGIES:
                    try:
                        trades = bt.run(strategy=strat)
                        r = aggregate(trades, weight=weight)
                        if r:
                            results[(period_name, sym, strat)] = r
                            total_pnl += r["pnl"]
                            total_pf_num += r["pf_num"]
                            total_pf_den += r["pf_den"]
                            total_n += r["n"]
                            total_w += r["w"]
                    except Exception:
                        pass
            except Exception:
                pass

    total_pf = (total_pf_num / total_pf_den) if total_pf_den > 0 else (float("inf") if total_pf_num > 0 else 0)
    total_wr = (total_w / total_n * 100) if total_n > 0 else 0

    summary = {
        "label": label,
        "ts": datetime.utcnow().isoformat(),
        "weights": SYMBOL_WEIGHTS,
        "total_n": total_n,
        "total_wins": total_w,
        "total_wr": round(total_wr, 1),
        "total_pnl": round(total_pnl, 2),
        "total_pf": total_pf if total_pf == float("inf") else round(total_pf, 2),
    }

    if verbose:
        print(f"\n╔══ TEST SUITE [{label}] ══════════════════════════════════════════╗")
        print(f"║ trades total:   {total_n:>6d}")
        print(f"║ wins:           {total_w:>6d}")
        print(f"║ WR global:      {total_wr:>6.1f}%")
        print(f"║ PnL total:      {total_pnl:>+7.2f}%")
        print(f"║ PF global:      {('∞' if total_pf == float('inf') else f'{total_pf:.2f}'):>6s}")
        print(f"║ Pesos:          {SYMBOL_WEIGHTS}")
        print(f"╚══════════════════════════════════════════════════════════════════╝")

    return {"summary": summary, "details": {f"{p}|{s}|{st}": r for (p, s, st), r in results.items()}}


def compare(baseline, candidate):
    """Compara dos runs. Retorna dict con deltas + verdict."""
    b = baseline["summary"]
    c = candidate["summary"]
    d_pnl = c["total_pnl"] - b["total_pnl"]
    d_n = c["total_n"] - b["total_n"]
    n_pct = (d_n / b["total_n"] * 100) if b["total_n"] > 0 else 0
    d_pf = (c["total_pf"] - b["total_pf"]) if (c["total_pf"] != float("inf") and b["total_pf"] != float("inf")) else 0

    # Reglas de "improvement"
    improved = (d_pnl > 0) and (d_pf > -0.1 or b["total_pf"] == float("inf")) and (n_pct > -30)
    # Edge case: si n cae a cero, no es mejora aunque PnL sea 0
    if c["total_n"] == 0 and b["total_n"] > 0:
        improved = False

    verdict = "✅ MEJORA" if improved else "❌ no mejora"

    print(f"\n┌─── DELTA: {b['label']} → {c['label']} ───────────────────────")
    print(f"│ PnL:       {b['total_pnl']:>+7.2f}% → {c['total_pnl']:>+7.2f}%   (Δ {d_pnl:+.2f}%)")
    print(f"│ trades:    {b['total_n']:>6d}  → {c['total_n']:>6d}     (Δ {n_pct:+.1f}%)")
    print(f"│ WR:        {b['total_wr']:>6.1f}% → {c['total_wr']:>6.1f}%")
    pf_b = '∞' if b['total_pf'] == float('inf') else f"{b['total_pf']:.2f}"
    pf_c = '∞' if c['total_pf'] == float('inf') else f"{c['total_pf']:.2f}"
    print(f"│ PF:        {pf_b:>6s} → {pf_c:>6s}")
    print(f"│ Veredicto: {verdict}")
    print(f"└────────────────────────────────────────────────────────────")
    return {"d_pnl": d_pnl, "d_n": d_n, "n_pct": n_pct, "d_pf": d_pf, "improved": improved, "verdict": verdict}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="run", help="tag para este run")
    parser.add_argument("--json", default=None, help="exportar JSON")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    res = run_suite(label=args.label, verbose=not args.quiet)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(res, f, indent=2, default=str)
        print(f"\nGuardado: {args.json}")
