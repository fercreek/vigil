#!/usr/bin/env python3
"""Cuenta cuantas barras pasa cada gate de rules.py, y cuantas pasan los cuatro.

Responde a "por que el instrumento suprime todo": el scoreboard del 21-ago-2026
reportaba 18 emitidas / 18 SUPPRESSED, y la pregunta era si estaba roto o calibrado
estrecho. Resulto lo segundo — `rsi_extreme` pasa el 0.4% de las barras — y este
script existe para que ese numero se pueda volver a medir en vez de citarse.

La medicion vive en instrument/HYPOTHESES.md, seccion "Por que el pullback casi no
dispara". Si vuelves a correr esto y da distinto, el doc esta viejo: actualizalo ahi.

    python3 instrument/scripts/measure_gate_rates.py
    python3 instrument/scripts/measure_gate_rates.py --sweep      # sensibilidad del RSI
    python3 instrument/scripts/measure_gate_rates.py --days 120

Usa yfinance, NO el feed de produccion: es una aproximacion deliberada para poder
medir sin credenciales. Las decimas se mueven; el orden de magnitud no.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from instrument import ta
from instrument.rules import (ADX_MIN, ATR_MIN_PCT, BB_PCTB_HIGH, BB_PCTB_LOW,
                              RSI_OVERBOUGHT, RSI_OVERSOLD)

SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "ZEC"]  # TAO no esta en yfinance


def load(symbols: list[str], days: int) -> dict:
    import yfinance as yf

    out = {}
    for sym in symbols:
        df = yf.download(f"{sym}-USD", period=f"{days}d", interval="1h",
                         progress=False, auto_adjust=True)
        if df.empty:
            print(f"  {sym}: sin datos, se omite", file=sys.stderr)
            continue
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.droplevel(1)
        h, l, c = df["High"].tolist(), df["Low"].tolist(), df["Close"].tolist()
        bu, _, bl = ta.bbands(c)
        out[sym] = (c, ta.rsi(c), ta.atr(h, l, c), ta.ema(c, 200), bu, bl, ta.adx(h, l, c))
    return out


def tally(series: dict, rsi_oversold: float, use_bb: bool) -> dict:
    """Cuenta pases por gate sobre las barras con warmup completo."""
    t = dict(bars=0, rsi=0, bb=0, adx=0, atr=0, all=0)
    for c, R, A, E, BU, BL, D in series.values():
        for i in range(len(c)):
            if None in (R[i], A[i], E[i], BU[i], BL[i], D[i]):
                continue
            close = c[i]
            if close == E[i]:  # el empate degenerado que rules.py suprime aparte
                continue
            long_side = close > E[i]
            pctb = (close - BL[i]) / (BU[i] - BL[i]) if BU[i] > BL[i] else None
            t["bars"] += 1

            g_rsi = R[i] <= rsi_oversold if long_side else R[i] >= (100 - rsi_oversold)
            g_bb = (not use_bb) or (pctb is not None and (
                pctb <= BB_PCTB_LOW if long_side else pctb >= BB_PCTB_HIGH))
            g_adx = D[i] >= ADX_MIN
            g_atr = bool(close) and (A[i] / close) >= ATR_MIN_PCT

            t["rsi"] += g_rsi
            t["bb"] += g_bb
            t["adx"] += g_adx
            t["atr"] += g_atr
            t["all"] += g_rsi and g_bb and g_adx and g_atr
    return t


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=60, help="ventana de velas 1h")
    ap.add_argument("--sweep", action="store_true", help="barre RSI_OVERSOLD 30..50")
    args = ap.parse_args()

    print(f"descargando {args.days}d de velas 1h · {', '.join(SYMBOLS)}", file=sys.stderr)
    series = load(SYMBOLS, args.days)
    if not series:
        sys.exit("ningun simbolo devolvio datos")

    t = tally(series, RSI_OVERSOLD, use_bb=True)
    n = t["bars"]
    pc = lambda k: f"{t[k]:>6} ({t[k] / n * 100:>5.1f}%)"

    print(f"\n{len(series)} simbolos · {n} barras evaluables tras el warmup de EMA200\n")
    print(f"  rsi_extreme    {pc('rsi')}   RSI<={RSI_OVERSOLD:g} LONG / >={RSI_OVERBOUGHT:g} SHORT")
    print(f"  bb_confluence  {pc('bb')}   %B<={BB_PCTB_LOW} / >={BB_PCTB_HIGH}")
    print(f"  adx_trending   {pc('adx')}   ADX>={ADX_MIN:g}")
    print(f"  atr_min        {pc('atr')}   ATR/close>={ATR_MIN_PCT:.1%}")
    print(f"\n  LOS CUATRO     {pc('all')}  <- lo que hace falta para un SENT")
    if t["all"]:
        semanas = args.days / 7
        print(f"  = 1 cada {n // t['all']} barras · {t['all'] / semanas:.1f} señales/semana")

    if args.sweep:
        print(f"\n{'RSI oversold':>13} {'con bb':>10} {'sin bb':>10}")
        print("-" * 35)
        for r in (30, 35, 40, 45, 50):
            con = tally(series, r, use_bb=True)["all"]
            sin = tally(series, r, use_bb=False)["all"]
            marca = "  <- hoy" if r == RSI_OVERSOLD else ""
            print(f"{r:>13} {con:>10} {sin:>10}{marca}")
        print("\nsi las dos columnas coinciden, bb_confluence no esta filtrando nada")


if __name__ == "__main__":
    main()
