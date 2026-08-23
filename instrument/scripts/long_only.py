"""El hallazgo apunta a LONG. Antes de creerselo hay que exigirle dos cosas:
que aguante en las DOS mitades del periodo, y que le gane a un baseline que
tambien es solo-LONG -- porque en dos anios de mercado alcista, comprar
cualquier cosa tambien sube.
"""
from pathlib import Path
import sys, math, statistics, pickle, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from instrument import ta, rules
from instrument.resolver import resolve
from geom_lab import signals, geometry

# El cache vive junto a estos scripts, no en un directorio de la maquina que los
# escribio. La version anterior guardaba rutas absolutas del scratchpad: los
# scripts se commitearon diciendo que servian para re-correr los numeros, y no
# corrian en ninguna otra maquina.
_HERE = Path(__file__).resolve().parent
_CACHE = _HERE / "_cache"
_CACHE.mkdir(exist_ok=True)


series, dayof = pickle.load(open(str(_CACHE / "stocks.pkl"), "rb"))
H = 72

def show(tag, rs):
    n = len(rs)
    if not n:
        print(f"  {tag:<30} sin senales"); return
    m = sum(rs)/n
    se = (statistics.stdev(rs)/math.sqrt(n)) if n > 1 else 0.0
    w = sum(1 for x in rs if x > 0)/n*100
    flag = "" if (m-1.96*se) > 0 else "   <- el IC cruza cero"
    print(f"  {tag:<30} n={n:<5} {m:+.3f}R  IC[{m-1.96*se:+.3f},{m+1.96*se:+.3f}]  aciertos {w:4.1f}%{flag}")

sig_all = {s: signals(c) for s, c in series.items()}

def collect(side_filter, first_half=None):
    rs = []
    for sym, candles in series.items():
        h = len(candles)//2
        last = {"LONG": -10**9, "SHORT": -10**9}
        for s in sig_all[sym]:
            i, sd = s["i"], s["side"]
            if i - last[sd] < H: continue
            last[sd] = i
            if side_filter and sd != side_filter: continue
            if first_half is True and i >= h: continue
            if first_half is False and i < h: continue
            rs.append(resolve(geometry(s, "V0_actual"), candles[i+1:i+1+H], H).r_realized)
    return rs

base_long = []
for sym, candles in series.items():
    closes = [c.close for c in candles]
    ema = ta.ema(closes, rules.EMA_PERIOD)
    atr = ta.atr([c.high for c in candles], [c.low for c in candles], closes, rules.ATR_PERIOD)
    for i in range(260, len(candles)-1, H):
        if ema[i] is None or atr[i] is None or closes[i] <= ema[i]: continue
        sig = {"i": i, "side": "LONG", "entry": closes[i], "atr": atr[i], "gap_p": 0.0}
        base_long.append(resolve(geometry(sig, "V0_actual"), candles[i+1:i+1+H], H).r_realized)

print("ACCIONES, 2 anios, 29 tickers -- SOLO LONG\n")
show("Regla LONG, periodo entero", collect("LONG"))
show("Regla LONG, 1a mitad", collect("LONG", True))
show("Regla LONG, 2a mitad", collect("LONG", False))
show("Baseline LONG sin gates", base_long)
print()
show("Regla SHORT, periodo entero", collect("SHORT"))
