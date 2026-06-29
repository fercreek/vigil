"""
backtest_sim.py — Simulador offline de estrategia V3-REVERSAL y V4-EMA
Corre sobre los CSV históricos (1 año de datos horarios).
No toca la DB live ni el bot en producción.

Uso:
  python3 backtest_sim.py                    # todas las estrategias y símbolos
  python3 backtest_sim.py --symbol ZEC       # solo ZEC V3
  python3 backtest_sim.py --strategy v4      # solo V4-EMA BTC
"""

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

# RSI thresholds por símbolo
RSI_REVERSAL_THRESHOLD = {
    # Crypto
    "ZEC":   20.0,   # tune Jun-2026: 20 → 60% WR +8.38R
    "BTC":   32.0,
    "BTC_YF":32.0,
    "ETH":   32.0,
    "TAO":   28.0,
    "SOL":   30.0,
    "BNB":   30.0,
    # Commodities
    "GOLD":  32.0,   # Gold futures — mean-reversion fuerte
    "GLD":   32.0,   # Gold ETF
    # Stocks — RSI rara vez baja de 30 en 1H, usar 35
    "COIN":  35.0,
    "NVDA":  35.0,
}

# V3 symbols activos
V3_SYMBOLS = ["ZEC", "BTC", "ETH"]

# ATR multiples
V3_TP1_ATR = 2.0
V3_TP2_ATR = 3.5
V3_SL_ATR  = 1.5  # tune Jun-2026: 1.5 > 2.0 en todos los símbolos

V4_TP1_ATR = 2.0
V4_TP2_ATR = 3.0
V4_SL_ATR  = 1.5

COOLDOWN_BARS = 4     # mínimo 4h entre señales
TIMEOUT_BARS  = 48    # cierre forzado si no hay hit en 48h


# ── Indicadores (sin pandas_ta — puro pandas/numpy) ──────────────────────────

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def calc_bb(close: pd.Series, period: int = 20, std_dev: float = 2.0):
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    return mid + std_dev * std, mid, mid - std_dev * std


def load_symbol(symbol: str) -> pd.DataFrame:
    # Buscar en orden: USDT pair → genérico
    for pattern in (f"{symbol}_USDT_1h_365d.csv", f"{symbol}_1h_365d.csv"):
        path = DATA_DIR / pattern
        if path.exists():
            break
    else:
        raise FileNotFoundError(f"No CSV para {symbol} en {DATA_DIR}")
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    df["rsi"]   = calc_rsi(close)
    df["ema200"] = close.ewm(span=200, min_periods=200).mean()
    df["atr"]   = calc_atr(high, low, close)
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = calc_bb(close)
    return df


# ── Lógica de trade: simular TP/SL en velas siguientes ───────────────────────

def simulate_trade(df: pd.DataFrame, signal_bar: int, entry_bar: int,
                   tp1: float, tp2: float, sl: float, sl_r: float) -> dict:
    """
    Recorre velas desde entry_bar hasta timeout.
    Devuelve dict con status y pnl_r.
    1R = sl_r (distancia al SL).
    """
    entry_price = df.at[entry_bar, "open"]
    tp1_hit = False
    be_sl = entry_price  # SL mueve a BE tras TP1

    for j in range(entry_bar, min(entry_bar + TIMEOUT_BARS, len(df))):
        high_j = df.at[j, "high"]
        low_j  = df.at[j, "low"]
        close_j = df.at[j, "close"]

        if not tp1_hit:
            # Chequear SL antes que TP (conservador)
            if low_j <= sl:
                pnl = -sl_r / sl_r  # -1R
                return {"status": "LOST", "pnl_r": -1.0, "hold": j - entry_bar,
                        "entry": entry_price, "exit": sl}
            if high_j >= tp1:
                tp1_hit = True
                # Cerrar 50% en TP1
                tp1_r = (tp1 - entry_price) / sl_r
                # Resto en BE
        else:
            # TP1 ya hit — SL efectivo es BE (entry_price)
            if low_j <= be_sl:
                pnl_r = 0.5 * (tp1 - entry_price) / sl_r  # 50% cerrado en TP1 + 50% en BE
                return {"status": "PARTIAL_WON", "pnl_r": round(pnl_r, 2),
                        "hold": j - entry_bar, "entry": entry_price, "exit": be_sl}
            if high_j >= tp2:
                tp1_piece = 0.5 * (tp1 - entry_price) / sl_r
                tp2_piece = 0.5 * (tp2 - entry_price) / sl_r
                return {"status": "FULL_WON", "pnl_r": round(tp1_piece + tp2_piece, 2),
                        "hold": j - entry_bar, "entry": entry_price, "exit": tp2}

    # Timeout — cerrar al close de la última vela
    last = min(entry_bar + TIMEOUT_BARS, len(df)) - 1
    close_exit = df.at[last, "close"]
    if tp1_hit:
        pnl_r = 0.5 * (tp1 - entry_price) / sl_r + 0.5 * (close_exit - entry_price) / sl_r
        status = "TIMEOUT_PARTIAL"
    else:
        pnl_r = (close_exit - entry_price) / sl_r
        status = "TIMEOUT"
    return {"status": status, "pnl_r": round(pnl_r, 2),
            "hold": TIMEOUT_BARS, "entry": entry_price, "exit": close_exit}


# ── V3-REVERSAL ───────────────────────────────────────────────────────────────

def run_v3(symbol: str) -> list[dict]:
    df = load_symbol(symbol)
    rsi_thresh = RSI_REVERSAL_THRESHOLD.get(symbol, 30.0)
    trades = []
    last_signal_bar = -COOLDOWN_BARS - 1

    # Warmup: necesitamos 200 velas para EMA200
    for i in range(200, len(df) - 1):
        if i - last_signal_bar < COOLDOWN_BARS:
            continue

        row = df.iloc[i]
        if pd.isna(row["rsi"]) or pd.isna(row["ema200"]) or pd.isna(row["atr"]):
            continue

        rsi    = row["rsi"]
        close  = row["close"]
        ema200 = row["ema200"]
        atr    = row["atr"]
        bb_lo  = row["bb_lower"]

        # Gate 1: RSI
        if rsi > rsi_thresh:
            continue

        # Gate 2: BB touch
        if close > bb_lo * 1.01:
            continue

        # Gate 3: confluencia mínima
        rsi_pts = 2 if rsi <= 30 else 1
        ema_pt  = 1 if close < ema200 else 0
        bb_pt   = 1 if close <= bb_lo * 1.01 else 0
        conf    = rsi_pts + ema_pt + bb_pt
        if conf < 3:
            continue

        # Gate 4: cooldown
        last_signal_bar = i

        # Entrada en open de la vela siguiente
        entry_bar   = i + 1
        entry_price = df.at[entry_bar, "open"]
        sl_dist     = atr * V3_SL_ATR
        tp1 = entry_price + atr * V3_TP1_ATR
        tp2 = entry_price + atr * V3_TP2_ATR
        sl  = entry_price - sl_dist

        result = simulate_trade(df, i, entry_bar, tp1, tp2, sl, sl_dist)
        result.update({
            "symbol": symbol,
            "strategy": "V3-REVERSAL",
            "signal_ts": str(df.at[i, "timestamp"]),
            "rsi": round(rsi, 1),
            "conf": conf,
        })
        trades.append(result)

    return trades


# ── V4-EMA (solo BTC) ─────────────────────────────────────────────────────────

def run_v4(symbol: str = "BTC") -> list[dict]:
    df = load_symbol(symbol)
    trades = []
    last_signal_bar = -COOLDOWN_BARS - 1

    for i in range(200, len(df) - 1):
        if i - last_signal_bar < COOLDOWN_BARS:
            continue

        row = df.iloc[i]
        if pd.isna(row["rsi"]) or pd.isna(row["ema200"]) or pd.isna(row["atr"]):
            continue

        rsi    = row["rsi"]
        close  = row["close"]
        ema200 = row["ema200"]
        atr    = row["atr"]
        prev_rsi = df.at[i - 2, "rsi"] if i >= 2 else rsi

        # Gate 1: precio sobre EMA200 y dentro de 2% por arriba
        if not (ema200 * 1.0 <= close <= ema200 * 1.02):
            continue

        # Gate 2: RSI en zona media y subiendo
        if not (35 <= rsi <= 55):
            continue
        if rsi <= prev_rsi:
            continue

        # Gate 3: EMA200 trending up (slope últimas 5 velas)
        if i < 5 or df.at[i, "ema200"] <= df.at[i - 5, "ema200"]:
            continue

        last_signal_bar = i
        entry_bar   = i + 1
        entry_price = df.at[entry_bar, "open"]
        sl_dist     = atr * V4_SL_ATR
        tp1 = entry_price + atr * V4_TP1_ATR
        tp2 = entry_price + atr * V4_TP2_ATR
        sl  = entry_price - sl_dist

        result = simulate_trade(df, i, entry_bar, tp1, tp2, sl, sl_dist)
        result.update({
            "symbol": symbol,
            "strategy": "V4-EMA",
            "signal_ts": str(df.at[i, "timestamp"]),
            "rsi": round(rsi, 1),
            "conf": 3,
        })
        trades.append(result)

    return trades


# ── Estadísticas ──────────────────────────────────────────────────────────────

def calc_stats(trades: list[dict]) -> dict:
    if not trades:
        return {}
    total = len(trades)
    won   = sum(1 for t in trades if t["status"] in ("FULL_WON", "PARTIAL_WON"))
    wr    = won / total * 100

    pnl_series = [t["pnl_r"] for t in trades]
    total_r    = sum(pnl_series)
    avg_r      = total_r / total
    avg_hold   = sum(t["hold"] for t in trades) / total

    # Max drawdown en R
    equity = np.cumsum(pnl_series)
    peak   = np.maximum.accumulate(equity)
    dd     = equity - peak
    max_dd = dd.min()

    by_status = {}
    for t in trades:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1

    return {
        "trades": total,
        "win_rate": round(wr, 1),
        "total_r": round(total_r, 2),
        "avg_r": round(avg_r, 2),
        "avg_hold_h": round(avg_hold, 1),
        "max_dd_r": round(max_dd, 2),
        "by_status": by_status,
    }


# ── Reporte ───────────────────────────────────────────────────────────────────

def print_table(rows: list[dict], title: str):
    print(f"\n{'═' * 72}")
    print(f"  BACKTEST — {title}")
    print(f"{'═' * 72}")
    header = f"{'Symbol':<8} {'Trades':>6} {'WR%':>6} {'Avg R':>7} {'Total R':>8} {'Max DD':>8} {'Avg Hold':>9}"
    print(header)
    print("─" * 72)
    for r in rows:
        sym  = r.get("symbol", r.get("strategy", "?"))
        s    = r["stats"]
        if not s:
            print(f"{sym:<8}  (sin datos)")
            continue
        print(f"{sym:<8} {s['trades']:>6} {s['win_rate']:>5.1f}% "
              f"{s['avg_r']:>+7.2f}R {s['total_r']:>+7.2f}R "
              f"{s['max_dd_r']:>+7.2f}R {s['avg_hold_h']:>7.1f}h")
    print("─" * 72)
    # Totals
    all_trades = [r for r in rows if r["stats"]]
    if all_trades:
        total_t = sum(r["stats"]["trades"] for r in all_trades)
        total_r = sum(r["stats"]["total_r"] for r in all_trades)
        total_w = sum(r["stats"]["trades"] * r["stats"]["win_rate"] / 100 for r in all_trades)
        wr_total = total_w / total_t * 100 if total_t else 0
        print(f"{'TOTAL':<8} {total_t:>6} {wr_total:>5.1f}%  {'':>7} {total_r:>+7.2f}R")
    print()


def print_status_breakdown(all_trades: list[dict]):
    combined: dict[str, int] = {}
    for t in all_trades:
        s = t["status"]
        combined[s] = combined.get(s, 0) + 1
    total = len(all_trades)
    print("  Breakdown de outcomes:")
    for status, count in sorted(combined.items(), key=lambda x: -x[1]):
        bar = "█" * int(count / total * 30)
        print(f"    {status:<20} {count:>4} ({count/total*100:>4.1f}%)  {bar}")
    print()


# ── Grid Search / Tune ───────────────────────────────────────────────────────

TUNE_GRID = {
    "rsi_thresh":   [20, 22, 25, 28, 30],
    "conf_min":     [3, 4],
    "sl_atr":       [1.5, 2.0, 2.5],
    "ema_required": [True, False],
    "timeout_bars": [24, 48],
}


def run_v3_tuned(symbol: str, params: dict) -> list[dict]:
    """Variante parametrizable de run_v3 para el grid search."""
    df = load_symbol(symbol)
    rsi_thresh   = params["rsi_thresh"]
    conf_min     = params["conf_min"]
    sl_atr_mult  = params["sl_atr"]
    ema_required = params["ema_required"]
    timeout      = params["timeout_bars"]
    tp1_atr      = V3_TP1_ATR
    tp2_atr      = V3_TP2_ATR

    trades = []
    last_signal_bar = -COOLDOWN_BARS - 1

    for i in range(200, len(df) - 1):
        if i - last_signal_bar < COOLDOWN_BARS:
            continue
        row = df.iloc[i]
        if pd.isna(row["rsi"]) or pd.isna(row["ema200"]) or pd.isna(row["atr"]):
            continue

        rsi    = row["rsi"]
        close  = row["close"]
        ema200 = row["ema200"]
        atr    = row["atr"]
        bb_lo  = row["bb_lower"]

        if rsi > rsi_thresh:
            continue
        if close > bb_lo * 1.01:
            continue
        if ema_required and close >= ema200:
            continue

        rsi_pts = 2 if rsi <= 30 else 1
        ema_pt  = 1 if close < ema200 else 0
        bb_pt   = 1 if close <= bb_lo * 1.01 else 0
        conf    = rsi_pts + ema_pt + bb_pt
        if conf < conf_min:
            continue

        last_signal_bar = i
        entry_bar   = i + 1
        entry_price = df.at[entry_bar, "open"]
        sl_dist     = atr * sl_atr_mult
        tp1 = entry_price + atr * tp1_atr
        tp2 = entry_price + atr * tp2_atr
        sl  = entry_price - sl_dist

        # simulate_trade usa TIMEOUT_BARS global — lo pasamos como override temporal
        result = _simulate_with_timeout(df, entry_bar, tp1, tp2, sl, sl_dist, timeout)
        result.update({"symbol": symbol, "strategy": "V3-TUNED"})
        trades.append(result)

    return trades


def _simulate_with_timeout(df: pd.DataFrame, entry_bar: int,
                            tp1: float, tp2: float, sl: float,
                            sl_r: float, timeout: int) -> dict:
    """simulate_trade con timeout configurable."""
    entry_price = df.at[entry_bar, "open"]
    tp1_hit = False
    be_sl = entry_price

    for j in range(entry_bar, min(entry_bar + timeout, len(df))):
        high_j  = df.at[j, "high"]
        low_j   = df.at[j, "low"]

        if not tp1_hit:
            if low_j <= sl:
                return {"status": "LOST", "pnl_r": -1.0, "hold": j - entry_bar,
                        "entry": entry_price, "exit": sl}
            if high_j >= tp1:
                tp1_hit = True
        else:
            if low_j <= be_sl:
                pnl_r = 0.5 * (tp1 - entry_price) / sl_r
                return {"status": "PARTIAL_WON", "pnl_r": round(pnl_r, 2),
                        "hold": j - entry_bar, "entry": entry_price, "exit": be_sl}
            if high_j >= tp2:
                tp1_piece = 0.5 * (tp1 - entry_price) / sl_r
                tp2_piece = 0.5 * (tp2 - entry_price) / sl_r
                return {"status": "FULL_WON", "pnl_r": round(tp1_piece + tp2_piece, 2),
                        "hold": j - entry_bar, "entry": entry_price, "exit": tp2}

    last = min(entry_bar + timeout, len(df)) - 1
    close_exit = df.at[last, "close"]
    if tp1_hit:
        pnl_r = 0.5 * (tp1 - entry_price) / sl_r + 0.5 * (close_exit - entry_price) / sl_r
        status = "TIMEOUT_PARTIAL"
    else:
        pnl_r = (close_exit - entry_price) / sl_r
        status = "TIMEOUT"
    return {"status": status, "pnl_r": round(pnl_r, 2),
            "hold": timeout, "entry": entry_price, "exit": close_exit}


def tune_v3(symbols: list[str]) -> None:
    keys = list(TUNE_GRID.keys())
    combos = list(itertools.product(*[TUNE_GRID[k] for k in keys]))
    total_runs = len(combos) * len(symbols)
    print(f"\n  Grid search: {len(combos)} combinaciones × {len(symbols)} símbolo(s) = {total_runs} runs")

    # Precargar DataFrames una sola vez
    dfs: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            dfs[sym] = load_symbol(sym)
        except FileNotFoundError as e:
            print(f"  ⚠ {e}")

    all_runs: list[dict] = []
    done = 0

    for combo in combos:
        params = dict(zip(keys, combo))
        combo_trades: list[dict] = []
        for sym in symbols:
            if sym not in dfs:
                continue
            trades = run_v3_tuned(sym, params)
            combo_trades.extend(trades)

        stats_all  = calc_stats(combo_trades)
        stats_by_sym = {sym: calc_stats([t for t in combo_trades if t["symbol"] == sym])
                        for sym in symbols}

        all_runs.append({
            "params": params,
            "stats_all": stats_all,
            "stats_by_sym": stats_by_sym,
        })
        done += 1
        if done % 20 == 0:
            print(f"    {done}/{len(combos)} combos...", flush=True)

    # Top 10 overall
    ranked = sorted([r for r in all_runs if r["stats_all"]],
                    key=lambda x: x["stats_all"]["total_r"], reverse=True)

    _print_tune_table(ranked[:10], "TOP 10 combinaciones (ALL symbols)", symbols)

    # Top 5 ZEC
    if "ZEC" in symbols:
        ranked_zec = sorted(
            [r for r in all_runs if r["stats_by_sym"].get("ZEC")],
            key=lambda x: x["stats_by_sym"]["ZEC"]["total_r"], reverse=True
        )
        _print_tune_table_single(ranked_zec[:5], "TOP 5 solo ZEC (Plan Fénix F1)", "ZEC")

    # Guardar JSON
    best_overall = ranked[0] if ranked else {}
    best_zec = {}
    if "ZEC" in symbols:
        ranked_zec = sorted(
            [r for r in all_runs if r["stats_by_sym"].get("ZEC")],
            key=lambda x: x["stats_by_sym"]["ZEC"]["total_r"], reverse=True
        )
        best_zec = ranked_zec[0] if ranked_zec else {}

    out_path = DATA_DIR / "tune_results.json"
    with open(out_path, "w") as f:
        json.dump({
            "best_overall": best_overall,
            "best_zec": best_zec,
            "all_runs": all_runs,
        }, f, indent=2)
    print(f"\n  Resultados guardados en {out_path}")


def _print_tune_table(ranked: list[dict], title: str, symbols: list[str]) -> None:
    print(f"\n{'═' * 80}")
    print(f"  TUNE V3-REVERSAL — {title}")
    print(f"{'═' * 80}")
    print(f"  {'Rank':<4} {'RSI':>4} {'Conf':>4} {'SL':>4} {'EMA':>5} {'TOut':>5} │"
          f" {'Trades':>6} {'WR%':>6} {'Total R':>8} {'Max DD':>8}")
    print("  " + "─" * 78)
    for i, r in enumerate(ranked, 1):
        p = r["params"]
        s = r["stats_all"]
        ema_tag = "Sí" if p["ema_required"] else "No"
        print(f"  {i:<4} {p['rsi_thresh']:>4} {p['conf_min']:>4} {p['sl_atr']:>4} "
              f"{ema_tag:>5} {p['timeout_bars']:>4}h │"
              f" {s['trades']:>6} {s['win_rate']:>5.1f}%"
              f" {s['total_r']:>+8.2f}R {s['max_dd_r']:>+8.2f}R")
    print()


def _print_tune_table_single(ranked: list[dict], title: str, sym: str) -> None:
    print(f"\n{'═' * 80}")
    print(f"  TUNE V3-REVERSAL — {title}")
    print(f"{'═' * 80}")
    print(f"  {'Rank':<4} {'RSI':>4} {'Conf':>4} {'SL':>4} {'EMA':>5} {'TOut':>5} │"
          f" {'Trades':>6} {'WR%':>6} {'Total R':>8} {'Max DD':>8}")
    print("  " + "─" * 78)
    for i, r in enumerate(ranked, 1):
        p = r["params"]
        s = r["stats_by_sym"].get(sym, {})
        if not s:
            continue
        ema_tag = "Sí" if p["ema_required"] else "No"
        print(f"  {i:<4} {p['rsi_thresh']:>4} {p['conf_min']:>4} {p['sl_atr']:>4} "
              f"{ema_tag:>5} {p['timeout_bars']:>4}h │"
              f" {s['trades']:>6} {s['win_rate']:>5.1f}%"
              f" {s['total_r']:>+8.2f}R {s['max_dd_r']:>+8.2f}R")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="ALL", help="ZEC | BTC | GOLD | ALL | ZEC,BTC,GOLD")
    parser.add_argument("--strategy", default="all", help="v3 | v4 | all")
    parser.add_argument("--tune", action="store_true", help="Grid search de parámetros V3")
    args = parser.parse_args()

    if args.tune:
        base = V3_SYMBOLS if args.symbol == "ALL" else args.symbol.upper().split(",")
        tune_v3(base)
        return

    # Resolver lista de símbolos
    if args.symbol == "ALL":
        custom_syms = None  # usa default por estrategia
    else:
        custom_syms = [s.strip().upper() for s in args.symbol.split(",")]

    all_trades: list[dict] = []
    v3_rows, v4_rows = [], []

    # V3-REVERSAL
    if args.strategy in ("v3", "all"):
        syms = (custom_syms or V3_SYMBOLS)
        for sym in syms:
            if sym not in RSI_REVERSAL_THRESHOLD:
                print(f"  ⚠ {sym} no tiene threshold definido — skipping V3")
                continue
            print(f"  Corriendo V3-REVERSAL {sym}...", end=" ", flush=True)
            try:
                trades = run_v3(sym)
                print(f"{len(trades)} señales")
                all_trades.extend(trades)
                v3_rows.append({"symbol": sym, "stats": calc_stats(trades)})
            except FileNotFoundError as e:
                print(f"⚠ {e}")

        if v3_rows:
            print_table(v3_rows, "V3-REVERSAL · 1 AÑO HORARIO")

    # V4-EMA
    if args.strategy in ("v4", "all"):
        v4_syms = custom_syms or ["BTC"]
        for sym in v4_syms:
            print(f"  Corriendo V4-EMA {sym}...", end=" ", flush=True)
            try:
                trades = run_v4(sym)
                print(f"{len(trades)} señales")
                all_trades.extend(trades)
                v4_rows.append({"symbol": sym, "stats": calc_stats(trades)})
            except FileNotFoundError as e:
                print(f"⚠ {e}")
        if v4_rows:
            print_table(v4_rows, "V4-EMA BOUNCE · 1 AÑO HORARIO")

    if all_trades:
        print_status_breakdown(all_trades)

    # Guardar JSON
    out_path = DATA_DIR / "backtest_results.json"
    results = {
        "v3": {r["symbol"]: r["stats"] for r in v3_rows},
        "v4": {r["symbol"]: r["stats"] for r in v4_rows},
        "trades_count": len(all_trades),
    }
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Resultados guardados en {out_path}\n")


if __name__ == "__main__":
    main()
