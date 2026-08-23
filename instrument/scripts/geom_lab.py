"""Banco de pruebas para la geometria. Tres variantes, mismo gate, mismas velas.

Por que se puede precalcular: ta.rsi/atr/adx/ema son recursiones causales y bbands
es ventana movil, asi que ta.f(serie_completa)[i] == ta.f(serie[:i+1])[-1]. Eso hace
que evaluar de una pasada sea identico a llamar rules.evaluate vela por vela -- y se
verifica abajo contra el metodo lento antes de creerle a un solo numero.
"""
import sys, math, statistics, warnings
from collections import Counter
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
from instrument import ta, rules
from instrument.geometry import Geometry
from instrument.resolver import Candle, resolve

GAP_LOOKBACK = 60
GAP_PCTL = 0.90


def signals(candles, gap_pctl=GAP_PCTL):
    """Indices donde la regla dispararia, con el ATR y el hueco tipico de cada uno."""
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    opens = [c.open for c in candles]
    rsi = ta.rsi(closes, rules.RSI_PERIOD)
    atr = ta.atr(highs, lows, closes, rules.ATR_PERIOD)
    ema = ta.ema(closes, rules.EMA_PERIOD)
    up, _mid, lo = ta.bbands(closes, rules.BB_PERIOD, rules.BB_K)
    adx = ta.adx(highs, lows, closes, rules.ADX_PERIOD)
    gaps = [0.0] + [abs(opens[i] - closes[i - 1]) for i in range(1, len(closes))]

    out = []
    for i in range(len(candles)):
        if None in (rsi[i], atr[i], ema[i], up[i], lo[i], adx[i]):
            continue
        c = closes[i]
        if c == ema[i]:
            continue
        side = "LONG" if c > ema[i] else "SHORT"
        pctb = (c - lo[i]) / (up[i] - lo[i]) if up[i] > lo[i] else None
        if pctb is None:
            continue
        ok_rsi = rsi[i] <= rules.RSI_OVERSOLD if side == "LONG" else rsi[i] >= rules.RSI_OVERBOUGHT
        ok_bb = pctb <= rules.BB_PCTB_LOW if side == "LONG" else pctb >= rules.BB_PCTB_HIGH
        if not (ok_rsi and ok_bb and adx[i] >= rules.ADX_MIN and (atr[i] / c) >= rules.ATR_MIN_PCT):
            continue
        w = gaps[max(1, i - GAP_LOOKBACK):i + 1]
        gp = sorted(w)[int(len(w) * gap_pctl)] if w else 0.0
        out.append({"i": i, "side": side, "entry": c, "atr": atr[i], "gap_p": gp})
    return out


def geometry(sig, variant):
    e, side = sig["entry"], sig["side"]
    r = rules.SL_ATR_MULT * sig["atr"]
    if variant == "V1_gap":
        r = max(r, sig["gap_p"])          # el stop no puede ser mas angosto que el hueco tipico
    sl = e - r if side == "LONG" else e + r
    t1 = e + rules.TP1_R_MULT * r if side == "LONG" else e - rules.TP1_R_MULT * r
    t2 = e + rules.TP2_R_MULT * r if side == "LONG" else e - rules.TP2_R_MULT * r
    return Geometry(side=side, entry=e, sl=sl, tp1=t1, tp2=t2)


def run(series, variant, max_hold=72, day_of=None):
    """series: {sym: [Candle]}. day_of: lista de fechas por indice, para V2."""
    rows = []
    for sym, candles in series.items():
        last = {"LONG": -10**9, "SHORT": -10**9}
        for s in signals(candles):
            i, side = s["i"], s["side"]
            if i - last[side] < max_hold:
                continue
            last[side] = i
            hold = max_hold
            if variant == "V2_intradia" and day_of and sym in day_of:
                d = day_of[sym]
                j = i + 1
                while j < len(candles) and d[j] == d[i]:
                    j += 1
                hold = max(1, j - i - 1)          # cierra al terminar la sesion
            res = resolve(geometry(s, variant), candles[i + 1:i + 1 + hold], hold)
            rows.append((sym, side, res.outcome, res.r_realized, res.mfe_r, res.mae_r))
    return rows


def report(name, rows, extra=""):
    if not rows:
        print(f"  {name:<14} sin senales"); return
    rs = [r[3] for r in rows]
    n = len(rs); mean = sum(rs) / n
    sd = statistics.stdev(rs) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n else 0.0
    wins = sum(1 for x in rs if x > 0)
    mae = statistics.median([r[5] for r in rows])
    print(f"  {name:<14} n={n:<4} {mean:+.3f}R  IC[{mean-1.96*se:+.3f},{mean+1.96*se:+.3f}]"
          f"  aciertos {wins/n*100:4.1f}%  MAE med {mae:+.2f}R  {extra}")
