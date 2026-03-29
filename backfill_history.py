"""
Script de relleno histórico: genera y guarda en BD el backtest
de los últimos N días para todas las monedas y versiones.
Ejecutar una vez: python backfill_history.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
import analysis_science
import tracker

SYMBOLS = ["ETH/USDT", "BTC/USDT", "TAO/USDT"]
VERSIONS = ["V1-TECH", "V2-AI"]
DAYS_BACK = 14  # Generar últimas 2 semanas

def backfill(force=False):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    results_summary = []

    for day_offset in range(1, DAYS_BACK + 1):
        target = today - timedelta(days=day_offset)
        date_str = target.strftime('%Y-%m-%d')

        # Verificar si ya existe (sin force)
        existing = tracker.get_backtest_session(date_str, version="V1-TECH")
        if existing and not force:
            print(f"⏭️  {date_str} — Ya existe en BD ({len(existing)} trades). Saltando.")
            # Aun así lo incluimos en el resumen
            v1 = tracker.get_backtest_session(date_str, version="V1-TECH")
            v2 = tracker.get_backtest_session(date_str, version="V2-AI")
            if v1:
                results_summary.append({
                    "date": date_str,
                    "v1_trades": len(v1),
                    "v2_trades": len(v2),
                    "v1_balance": v1[-1]['balance_after'] if v1 else 1000,
                    "v2_balance": v2[-1]['balance_after'] if v2 else 1000,
                    "source": "existing"
                })
            continue

        print(f"🔄 Generando {date_str}...", end=" ", flush=True)
        all_trades = {"V1-TECH": [], "V2-AI": []}

        for v in VERSIONS:
            for s in SYMBOLS:
                trades = analysis_science.run_detailed_backtest(
                    symbol=s,
                    target_date_str=date_str,
                    version=v
                )
                all_trades[v].extend(trades)

            # Guardar en BD
            tracker.save_backtest_session(date_str, v, all_trades[v])

        v1_cnt = len(all_trades["V1-TECH"])
        v2_cnt = len(all_trades["V2-AI"])

        # Obtener balances finales
        v1_saved = tracker.get_backtest_session(date_str, version="V1-TECH")
        v2_saved = tracker.get_backtest_session(date_str, version="V2-AI")
        v1_bal = v1_saved[-1]['balance_after'] if v1_saved else 1000.0
        v2_bal = v2_saved[-1]['balance_after'] if v2_saved else 1000.0

        results_summary.append({
            "date": date_str,
            "v1_trades": v1_cnt,
            "v2_trades": v2_cnt,
            "v1_balance": v1_bal,
            "v2_balance": v2_bal,
            "source": "generated"
        })

        v1_pnl = f"+${v1_bal-1000:.2f}" if v1_bal >= 1000 else f"-${1000-v1_bal:.2f}"
        v2_pnl = f"+${v2_bal-1000:.2f}" if v2_bal >= 1000 else f"-${1000-v2_bal:.2f}"
        print(f"V1: {v1_cnt} trades ({v1_pnl}) | V2: {v2_cnt} trades ({v2_pnl})")

    print("\n" + "=" * 60)
    print("RESUMEN HISTÓRICO (últimas 2 semanas)")
    print("=" * 60)
    print(f"{'Día':<12} {'V1 Trades':>10} {'V1 Balance':>12} {'V2 Trades':>10} {'V2 Balance':>12}")
    print("-" * 60)
    for r in results_summary:
        v1_b = f"${r['v1_balance']:.2f}" if r['v1_trades'] > 0 else "sin datos"
        v2_b = f"${r['v2_balance']:.2f}" if r['v2_trades'] > 0 else "sin datos"
        print(f"{r['date']:<12} {r['v1_trades']:>10} {v1_b:>12} {r['v2_trades']:>10} {v2_b:>12}")

    print(f"\n✅ Total días procesados: {len(results_summary)}")
    print(f"📦 BD actualizada: trades.db")

if __name__ == "__main__":
    force = "--force" in sys.argv
    if force:
        print("⚠️  Modo forzado: recalculando todos los días existentes\n")
    backfill(force=force)
