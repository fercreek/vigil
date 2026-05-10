"""
iterate.py — Iterador de mejoras sobre test_suite.py.

Para cada candidate config:
1. Backup config.py actual
2. Apply patch
3. Run test_suite
4. Compare vs baseline
5. Si mejora → keep + log. Si no → revert.

Cada iter genera un row en _ITERATION_LOG.md
"""
import json
import re
import shutil
import os
import subprocess
import sys
from datetime import datetime

CONFIG_PATH = "config.py"
LOG_PATH = "_ITERATION_LOG.md"
BASELINE_PATH = "/tmp/baseline.json"


def patch_config(patches: dict, dry_run=False):
    """patches = {"RSI_LONG_TAO_EXTREME": 25, ...}. Retorna dict de valores originales."""
    with open(CONFIG_PATH, "r") as f:
        content = f.read()

    originals = {}
    for key, new_val in patches.items():
        # Match "VAR_NAME = <something>" preservando comentarios al final
        pattern = rf"^({re.escape(key)}\s*=\s*)([^\s#]+)(\s*#.*)?$"
        m = re.search(pattern, content, flags=re.MULTILINE)
        if not m:
            print(f"  ⚠️  {key} no encontrado en config.py — skip")
            continue
        prefix = m.group(1)
        old_val = m.group(2).strip()
        suffix = m.group(3) or ""
        originals[key] = old_val
        new_str = f"{prefix}{new_val}{suffix}"
        content = re.sub(pattern, new_str, content, count=1, flags=re.MULTILINE)

    if not dry_run:
        with open(CONFIG_PATH, "w") as f:
            f.write(content)
    return originals


def run_suite_capture(label):
    """Run test_suite.py via subprocess, return parsed summary."""
    out_path = f"/tmp/iter_{label}.json"
    res = subprocess.run(
        [sys.executable, "test_suite.py", "--label", label, "--json", out_path, "--quiet"],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        print(f"❌ ERROR run_suite {label}:\n{res.stderr[:500]}")
        return None
    with open(out_path) as f:
        return json.load(f)


def compare_summaries(baseline_sum, candidate_sum):
    d_pnl = candidate_sum["total_pnl"] - baseline_sum["total_pnl"]
    d_n = candidate_sum["total_n"] - baseline_sum["total_n"]
    n_pct = (d_n / baseline_sum["total_n"] * 100) if baseline_sum["total_n"] > 0 else 0
    pf_b = baseline_sum["total_pf"] if isinstance(baseline_sum["total_pf"], (int, float)) else 999
    pf_c = candidate_sum["total_pf"] if isinstance(candidate_sum["total_pf"], (int, float)) else 999
    d_pf = pf_c - pf_b
    improved = (
        d_pnl > 0
        and d_pf > -0.1
        and n_pct > -50  # No perder más del 50% de los trades
        and candidate_sum["total_n"] > 0
    )
    return {"d_pnl": d_pnl, "d_n": d_n, "n_pct": n_pct, "d_pf": d_pf, "improved": improved}


def log_iter(label, patches, baseline_sum, candidate_sum, delta, kept):
    line = (
        f"| {label} | `{patches}` | "
        f"{baseline_sum['total_pnl']:+.2f}% → {candidate_sum['total_pnl']:+.2f}% "
        f"({delta['d_pnl']:+.2f}) | "
        f"{baseline_sum['total_n']} → {candidate_sum['total_n']} ({delta['n_pct']:+.1f}%) | "
        f"PF {baseline_sum['total_pf']} → {candidate_sum['total_pf']} | "
        f"{'✅ KEEP' if kept else '❌ REVERT'} |\n"
    )
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w") as f:
            f.write(
                "# _ITERATION_LOG — Suite canónica iter log\n\n"
                "Métricas: PnL agregado · trades · PF global. KEEP = aplica al config. REVERT = se descarta.\n\n"
                "| Iter | Patch | PnL Δ | Trades Δ | PF | Decisión |\n"
                "|------|-------|-------|----------|-----|----------|\n"
            )
    with open(LOG_PATH, "a") as f:
        f.write(line)


def iterate(label, patches, baseline_sum):
    """Ejecuta una iteración. Si mejora, keep. Si no, revert."""
    print(f"\n{'='*70}\n🔬 ITER [{label}]: {patches}\n{'='*70}")

    originals = patch_config(patches)
    if not originals:
        print(f"  ⚠️  Sin patches aplicables — skip iter")
        return None

    cand = run_suite_capture(label)
    if not cand:
        print(f"  ❌ Run failed — revertiendo")
        patch_config(originals)
        return None

    delta = compare_summaries(baseline_sum, cand["summary"])
    print(f"  PnL: {baseline_sum['total_pnl']:+.2f}% → {cand['summary']['total_pnl']:+.2f}% (Δ {delta['d_pnl']:+.2f}%)")
    print(f"  N:   {baseline_sum['total_n']} → {cand['summary']['total_n']} ({delta['n_pct']:+.1f}%)")
    print(f"  PF:  {baseline_sum['total_pf']} → {cand['summary']['total_pf']}")

    kept = delta["improved"]
    if kept:
        print(f"  ✅ KEEP — patch aplicado al config")
        new_baseline = cand["summary"]
    else:
        print(f"  ❌ REVERT — restaurando config")
        patch_config(originals)
        new_baseline = baseline_sum

    log_iter(label, patches, baseline_sum, cand["summary"], delta, kept)
    return new_baseline


if __name__ == "__main__":
    # Cargar baseline
    with open(BASELINE_PATH) as f:
        baseline = json.load(f)["summary"]

    print(f"\n📊 BASELINE: PnL={baseline['total_pnl']:+.2f}% N={baseline['total_n']} PF={baseline['total_pf']}")

    # Lista de iteraciones a probar (cada una se evalúa, keep/revert)
    iters = [
        # ── Ronda 3: params nunca tocados ───────────────────────────────────────
        # Ahora TP1=3.0 — re-probar SL combos
        ("sl_2.5_with_tp3",    {"ATR_SL_MULT": 2.5}),
        ("sl_1.8_with_tp3",    {"ATR_SL_MULT": 1.8}),
        # TP2 / TP3 ajustes
        ("tp2_extended",       {"ATR_TP2_MULT": 5.0}),
        ("tp3_moonshot",       {"ATR_TP3_MULT": 10.0}),
        ("tp2_conservative",   {"ATR_TP2_MULT": 2.5}),
        # Min SL pct: protege de SL muy ajustados
        ("min_sl_pct_higher",  {"ATR_MIN_SL_PCT": 0.012}),
        ("min_sl_pct_lower",   {"ATR_MIN_SL_PCT": 0.005}),
        # RVOL filters
        ("rvol_strict",        {"RVOL_MIN_ENTRY": 1.3}),
        ("rvol_loose",         {"RVOL_MIN_ENTRY": 0.8}),
        ("rvol_btc_higher",    {"RVOL_MIN_BTC": 1.0}),
        # ADX regime
        ("adx_strict",         {"ADX_TRENDING_THRESHOLD": 25}),
        ("adx_loose",          {"ADX_TRENDING_THRESHOLD": 15}),
        # BB ranging detection
        ("bb_ranging_wider",   {"BB_WIDTH_RANGING_PCT": 0.025}),
        ("bb_ranging_tighter", {"BB_WIDTH_RANGING_PCT": 0.010}),
        # V3 holding bars (timeout)
        ("v3_max_bars_short",  {"V3_MAX_HOLDING_BARS": 24}),
        ("v3_max_bars_long",   {"V3_MAX_HOLDING_BARS": 96}),
        # V4 specific SL
        ("v4_atr_sl_tight",    {"V4_ATR_SL_MULT": 1.0}),
        ("v4_atr_sl_wide",     {"V4_ATR_SL_MULT": 2.0}),
        # V4 RSI low (currently 35)
        ("v4_rsi_low_lower",   {"V4_RSI_LOW": 30.0}),
        ("v4_rsi_low_higher",  {"V4_RSI_LOW": 40.0}),
    ]

    current_baseline = baseline
    for label, patches in iters:
        new = iterate(label, patches, current_baseline)
        if new:
            # Si mejoró, el siguiente baseline es este
            current_baseline = new

    print(f"\n\n🏁 FINAL después de iteraciones:")
    print(f"   PnL: {current_baseline['total_pnl']:+.2f}% (Δ vs baseline original: {current_baseline['total_pnl'] - baseline['total_pnl']:+.2f}%)")
    print(f"   N:   {current_baseline['total_n']}")
    print(f"   PF:  {current_baseline['total_pf']}")
    print(f"\nLog completo: {LOG_PATH}")
