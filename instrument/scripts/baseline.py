"""La pregunta que decide: los cuatro gates, aportan algo?

Baseline = mismas entradas espaciadas, mismo lado (EMA200), misma geometria, SIN
ningun gate. Si el baseline da lo mismo, el filtro no esta haciendo nada y lo que
se ve es la deriva del mercado. Es la comparacion que rules.py ya documenta haber
hecho en cripto, aplicada aqui.
"""
from pathlib import Path
import sys, math, statistics, pickle, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from instrument import ta, rules
from instrument.geometry import Geometry
from instrument.resolver import resolve
from geom_lab import signals, geometry, run

# El cache vive junto a estos scripts, no en un directorio de la maquina que los
# escribio. La version anterior guardaba rutas absolutas del scratchpad: los
# scripts se commitearon diciendo que servian para re-correr los numeros, y no
# corrian en ninguna otra maquina.
_HERE = Path(__file__).resolve().parent
_CACHE = _HERE / "_cache"
_CACHE.mkdir(exist_ok=True)


series, dayof = pickle.load(open(str(_CACHE / "stocks.pkl"), "rb"))
MAX_HOLD = 72

def stats(rs):
    n = len(rs)
    if not n: return None
    m = sum(rs)/n
    se = (statistics.stdev(rs)/math.sqrt(n)) if n > 1 else 0.0
    return n, m, m-1.96*se, m+1.96*se, sum(1 for x in rs if x > 0)/n*100

def show(tag, rs):
    s = stats(rs)
    print(f"  {tag:<24} n={s[0]:<5} {s[1]:+.3f}R  IC[{s[2]:+.3f},{s[3]:+.3f}]  aciertos {s[4]:4.1f}%" if s else f"  {tag:<24} sin datos")

# --- baseline: sin gates, entradas cada MAX_HOLD velas, lado por EMA200 ---
base = []
for sym, candles in series.items():
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]; lows = [c.low for c in candles]
    ema = ta.ema(closes, rules.EMA_PERIOD)
    atr = ta.atr(highs, lows, closes, rules.ATR_PERIOD)
    for i in range(260, len(candles) - 1, MAX_HOLD):
        if ema[i] is None or atr[i] is None or closes[i] == ema[i]:
            continue
        side = "LONG" if closes[i] > ema[i] else "SHORT"
        sig = {"i": i, "side": side, "entry": closes[i], "atr": atr[i], "gap_p": 0.0}
        res = resolve(geometry(sig, "V0_actual"), candles[i+1:i+1+MAX_HOLD], MAX_HOLD)
        base.append(res.r_realized)

rows = run(series, "V0_actual", MAX_HOLD, dayof)
print("ACCIONES, 2 anios, 29 tickers\n")
show("Regla (4 gates)", [r[3] for r in rows])
show("Baseline SIN gates", base)

# --- mitades temporales: el signo aguanta? ---
half = {s: len(c)//2 for s, c in series.items()}
prim = [r for sym, c in series.items() for r in [] ]
sig_all = {sym: signals(c) for sym, c in series.items()}
for tag, sel in (("Primera mitad", lambda i, h: i < h), ("Segunda mitad", lambda i, h: i >= h)):
    rs = []
    for sym, candles in series.items():
        h = half[sym]; last = {"LONG": -10**9, "SHORT": -10**9}
        for s in sig_all[sym]:
            i, side = s["i"], s["side"]
            if i - last[side] < MAX_HOLD: continue
            last[side] = i
            if not sel(i, h): continue
            rs.append(resolve(geometry(s, "V0_actual"), candles[i+1:i+1+MAX_HOLD], MAX_HOLD).r_realized)
    show(tag, rs)

# --- por lado ---
for side in ("LONG", "SHORT"):
    show(f"Solo {side}", [r[3] for r in rows if r[1] == side])
