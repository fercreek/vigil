"""
run_backtest.py — Backtest completo Zenith V1-TECH / V2-AI (365 días, 1H)

Correcciones vs analysis_science.py original:
  - Indicadores calculados sobre el historial COMPLETO (no solo 24 velas/día)
  - Elliott Wave como penalización de score (no hard-block)
  - Una posición por símbolo a la vez (no una por día)
  - RSI threshold igual al bot real (≤42, ZEC ≤48)

Corre: python run_backtest.py
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os, sys

# ── Indicadores (inline para no depender de Binance live) ─────────────────────
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_bb(series, period=20, std=2):
    sma = series.rolling(period).mean()
    sd  = series.rolling(period).std(ddof=0)
    return sma + std*sd, sma - std*sd

def calc_ema(series, period=200):
    return series.ewm(span=period, adjust=False).mean()

def calc_atr(df, period=14):
    hl  = df['high'] - df['low']
    hc  = (df['high'] - df['close'].shift()).abs()
    lc  = (df['low']  - df['close'].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def confluence_score(price, rsi, bb_u, bb_l, ema200, side="LONG",
                     elliott="", usdt_d=8.0):
    """Replica exacta de calculate_confluence_score() del bot."""
    score = 0
    if side == "LONG":
        if rsi <= 30:  score += 2
        elif rsi <= 40: score += 1
    else:
        if rsi >= 70:  score += 2
        elif rsi >= 60: score += 1

    if (side == "LONG" and price > ema200) or (side == "SHORT" and price < ema200):
        score += 1
    if (side == "LONG" and price <= bb_l * 1.01) or (side == "SHORT" and price >= bb_u * 0.99):
        score += 1
    if (side == "LONG" and usdt_d < 8.05) or (side == "SHORT" and usdt_d > 8.05):
        score += 1
    if "Onda 3" in elliott:   score += 1
    if "Corrección" in elliott or "Correctiva" in elliott: score -= 1
    return max(0, min(6, score))

# ── Backtest por símbolo ──────────────────────────────────────────────────────
WARMUP = 250        # velas de calentamiento (para EMA 200 estabilizada)
MIN_CONF = 4        # score mínimo para disparar señal
ATR_SL   = 2.0
ATR_TP1  = 2.0
ATR_TP2  = 3.5
ATR_TP3  = 7.0
MIN_SL_PCT = 0.007  # SL mínimo 0.7%

RSI_ENTRY = {"default": 42.0, "ZEC": 48.0}

def backtest_symbol(csv_path: str, sym: str, version: str = "V1-TECH"):
    if not os.path.exists(csv_path):
        print(f"  ⚠️  No se encontró {csv_path}")
        return []

    df = pd.read_csv(csv_path, parse_dates=['timestamp'], index_col='timestamp')

    # Calcular todos los indicadores sobre el dataset COMPLETO
    df['rsi']     = calc_rsi(df['close'])
    df['ema_200'] = calc_ema(df['close'], 200)
    df['ema_4h']  = df['close'].resample('4h').last() \
                        .ewm(span=200, adjust=False).mean() \
                        .reindex(df.index, method='ffill')
    df['bb_u'], df['bb_l'] = calc_bb(df['close'])
    df['atr']     = calc_atr(df)
    df['vol_sma'] = df['volume'].rolling(20).mean()
    df['rsi_prev'] = df['rsi'].shift(1)   # Para filtro "RSI rising"
    df = df.dropna()

    rsi_thresh = RSI_ENTRY.get(sym, RSI_ENTRY["default"])
    trades = []
    active = None

    for ts, row in df.iloc[WARMUP:].iterrows():
        price   = row['close']
        rsi     = row['rsi']
        rsi_prv = row['rsi_prev']
        bb_u    = row['bb_u']
        bb_l    = row['bb_l']
        ema200  = row['ema_200']
        ema4h   = row['ema_4h']
        atr     = row['atr']
        vol     = row['volume']
        vsma    = row['vol_sma']

        # Macro trend
        t1h = "UP" if price > ema200 else "DOWN"
        t4h = "UP" if price > ema4h  else "DOWN"
        macro = "BULL" if (t1h == "UP" and t4h == "UP") else \
                "BEAR" if (t1h == "DOWN" and t4h == "DOWN") else "NEUTRAL"

        # ── Gestionar trade activo ────────────────────────────────────────
        if active:
            dur = int((ts - active['open_ts']).total_seconds() / 60)
            side = active['type']

            def close_t(result, cp):
                mult = 1 if side == "LONG" else -1
                pnl_pct = round((cp - active['entry_price']) / active['entry_price'] * 100 * mult, 3)
                sl_dist = abs(active['entry_price'] - active['sl'])
                # PnL en USD asumiendo riesgo fijo $10 (1% de $1000)
                risk_usd = 10.0
                pnl_usd = round(pnl_pct / (sl_dist / active['entry_price'] * 100) * risk_usd, 2)
                trades.append({
                    "symbol": sym, "version": version,
                    "type": side,
                    "entry_price": active['entry_price'],
                    "close_price": round(cp, 4),
                    "open_ts": active['open_ts'],
                    "close_ts": ts,
                    "duration_h": round(dur / 60, 1),
                    "sl": active['sl'], "tp1": active['tp1'], "tp2": active['tp2'],
                    "rsi_entry": active['rsi_entry'],
                    "conf_score": active['conf_score'],
                    "macro": active['macro'],
                    "result": result,
                    "pnl_pct": pnl_pct,
                    "pnl_usd": pnl_usd,
                    "tp1_hit": active.get('tp1_hit', False),
                })

            if side == "LONG":
                if price <= active['sl']:
                    close_t("LOST", price); active = None
                elif price >= active['tp2']:
                    close_t("WIN_FULL", price); active = None
                elif price >= active['tp1'] and not active.get('tp1_hit'):
                    active['tp1_hit'] = True  # parcial, seguimos en trade
            else:  # SHORT
                if price >= active['sl']:
                    close_t("LOST", price); active = None
                elif price <= active['tp2']:
                    close_t("WIN_FULL", price); active = None
                elif price <= active['tp1'] and not active.get('tp1_hit'):
                    active['tp1_hit'] = True
            continue  # si hay posición activa, no buscar nueva

        # ── Buscar entrada LONG ───────────────────────────────────────────
        if macro != "BEAR" and price > ema200:
            if rsi <= rsi_thresh and rsi > rsi_prv:   # RSI oversold + rising (bot real)
                near_bb_l = price <= bb_l * 1.015
                vol_ok    = vol > vsma * 0.8           # volumen levemente relajado
                elliott   = ""                         # sin Elliott live en backtest

                conf = confluence_score(price, rsi, bb_u, bb_l, ema200,
                                        "LONG", elliott)

                if conf >= MIN_CONF and near_bb_l:
                    sl_dist = max(atr * ATR_SL, price * MIN_SL_PCT)
                    sl  = round(price - sl_dist, 6)
                    tp1 = round(price + sl_dist * ATR_TP1, 6)
                    tp2 = round(price + sl_dist * ATR_TP2, 6)
                    active = {
                        "type": "LONG", "entry_price": price,
                        "open_ts": ts, "sl": sl, "tp1": tp1, "tp2": tp2,
                        "rsi_entry": round(rsi, 1), "conf_score": conf,
                        "macro": macro, "tp1_hit": False
                    }

        # ── Buscar entrada SHORT (desactivado como en el bot) ─────────────
        # elif macro != "BULL" and price < ema200:
        #   ... (disabled per bot config - LONG FOCUS)

    # Cerrar posición abierta al final del dataset
    if active and len(df) > 0:
        last = df.iloc[-1]
        side = active['type']
        cp   = last['close']
        mult = 1 if side == "LONG" else -1
        pnl_pct = round((cp - active['entry_price']) / active['entry_price'] * 100 * mult, 3)
        sl_dist = abs(active['entry_price'] - active['sl'])
        risk_usd = 10.0
        pnl_usd = round(pnl_pct / (sl_dist / active['entry_price'] * 100) * risk_usd, 2)
        trades.append({
            "symbol": sym, "version": version, "type": side,
            "entry_price": active['entry_price'],
            "close_price": round(cp, 4),
            "open_ts": active['open_ts'], "close_ts": df.index[-1],
            "duration_h": 0, "sl": active['sl'],
            "tp1": active['tp1'], "tp2": active['tp2'],
            "rsi_entry": active['rsi_entry'], "conf_score": active['conf_score'],
            "macro": active['macro'], "result": "OPEN_EOD",
            "pnl_pct": pnl_pct, "pnl_usd": pnl_usd, "tp1_hit": active.get('tp1_hit', False)
        })

    return trades

# ── Métricas ──────────────────────────────────────────────────────────────────
def print_metrics(trades, label, sym=None):
    if not trades:
        print(f"  {label}: Sin señales")
        return

    decided  = [t for t in trades if t['result'] in ("WIN_FULL", "LOST")]
    wins     = [t for t in decided if t['result'] == "WIN_FULL"]
    losses   = [t for t in decided if t['result'] == "LOST"]
    open_eod = [t for t in trades  if t['result'] == "OPEN_EOD"]
    tp1_hit  = [t for t in trades  if t.get('tp1_hit')]

    win_rate = len(wins) / len(decided) * 100 if decided else 0
    total_pnl = sum(t['pnl_usd'] for t in trades)
    gross_w   = sum(t['pnl_usd'] for t in wins)
    gross_l   = abs(sum(t['pnl_usd'] for t in losses))
    pf        = round(gross_w / gross_l, 2) if gross_l > 0 else float('inf')
    avg_dur   = sum(t['duration_h'] for t in decided) / len(decided) if decided else 0
    avg_conf  = sum(t['conf_score'] for t in trades) / len(trades)

    icon = "🟢" if win_rate >= 55 else ("🟡" if win_rate >= 45 else "🔴")
    print(f"\n  ── {label} ──")
    print(f"  Total trades    : {len(trades)}  (Ganados: {len(wins)}  Perdidos: {len(losses)}  Abiertos EOD: {len(open_eod)})")
    print(f"  TP1 alcanzado   : {len(tp1_hit)} trades ({len(tp1_hit)/len(trades)*100:.0f}%)")
    print(f"  Win Rate        : {icon} {win_rate:.1f}%  (sobre {len(decided)} cerrados)")
    print(f"  Profit Factor   : {pf}")
    print(f"  PnL Total       : ${total_pnl:+.2f}  (desde $1000 → ${1000+total_pnl:.2f})")
    print(f"  Duración media  : {avg_dur:.1f}h por trade")
    print(f"  Conf Score med  : {avg_conf:.2f}/6")

    # Breakdown por macro
    for m in ["BULL", "NEUTRAL"]:
        mt = [t for t in decided if t['macro'] == m]
        mw = [t for t in mt if t['result'] == "WIN_FULL"]
        if mt:
            mwr = len(mw)/len(mt)*100
            mic = "🟢" if mwr >= 55 else ("🟡" if mwr >= 45 else "🔴")
            print(f"  WR en {m:8s}  : {mic} {mwr:.1f}%  ({len(mt)} trades)")

    # Breakdown por RSI bucket
    print(f"  {'RSI entrada':12s}  {'Trades':>6}  {'WR':>7}  {'PnL':>8}")
    for lo, hi in [(0,30),(30,35),(35,40),(40,43),(43,50)]:
        bt = [t for t in decided if lo < t['rsi_entry'] <= hi]
        bw = [t for t in bt if t['result'] == "WIN_FULL"]
        bp = sum(t['pnl_usd'] for t in bt)
        bwr = len(bw)/len(bt)*100 if bt else 0
        bic = "🟢" if bwr>=55 else ("🟡" if bwr>=45 else "🔴")
        if bt:
            print(f"  RSI {lo:2d}-{hi:2d}       : {len(bt):6d}  {bic}{bwr:5.1f}%  ${bp:+7.2f}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    configs = [
        ("BTC/USDT", "BTC", "data/BTC_USDT_1h_365d.csv"),
        ("TAO/USDT", "TAO", "data/TAO_USDT_1h_365d.csv"),
        ("ETH/USDT", "ETH", "data/ETH_USDT_1h_365d.csv"),
    ]

    print("\n" + "="*60)
    print("  ZENITH — BACKTEST REAL 365 DÍAS (V1-TECH LONG FOCUS)")
    print("  Período: 2025-03-29 → 2026-03-29 | Timeframe: 1H")
    print("  Condiciones: RSI≤42 rising + EMA200 + BB_lower + Conf≥4")
    print("="*60)

    all_trades = []
    for pair, sym, csv in configs:
        trades = backtest_symbol(csv, sym, "V1-TECH")
        all_trades.extend(trades)
        print_metrics(trades, f"{pair}")

    print("\n" + "="*60)
    print("  RESULTADO CONSOLIDADO (BTC + TAO + ETH)")
    print("="*60)
    print_metrics(all_trades, "TODOS LOS SÍMBOLOS")

    # Tabla mensual de PnL
    if all_trades:
        print("\n  DESGLOSE MENSUAL (trades cerrados):")
        print(f"  {'Mes':8s}  {'Trades':>6}  {'WR':>7}  {'PnL':>8}  {'Balance':>10}")
        monthly = {}
        for t in all_trades:
            if t['result'] in ("WIN_FULL", "LOST"):
                m = t['open_ts'].strftime("%Y-%m")
                monthly.setdefault(m, []).append(t)

        bal = 1000.0
        for m in sorted(monthly.keys()):
            mt    = monthly[m]
            wins  = sum(1 for t in mt if t['result']=="WIN_FULL")
            pnl   = sum(t['pnl_usd'] for t in mt)
            bal  += pnl
            wr    = wins/len(mt)*100
            ic    = "🟢" if wr>=55 else ("🟡" if wr>=45 else "🔴")
            print(f"  {m}    {len(mt):6d}  {ic}{wr:5.1f}%  ${pnl:+7.2f}  ${bal:9.2f}")

    print("\n" + "="*60)
    print("  ✅ Backtest completo")
    print("="*60 + "\n")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
