"""Lo mismo en cripto, con el feed del propio bot. Si el SHORT tampoco aporta
alla, el cambio es una regla del sistema y no un parche para acciones.
"""
import sys, math, statistics, pickle, time, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
sys.path.insert(0, "/private/tmp/claude-501/-Users-fernandocastaneda-Documents-ideas-scalp-bot/0acb6807-3a0d-4478-820e-4d398ce00750/scratchpad")
from instrument.feed import fetch_ohlcv
from instrument.resolver import resolve
from geom_lab import signals, geometry
from instrument import ta, rules

SYMS = ["ZEC", "TAO", "BTC", "ETH", "SOL", "BNB"]
H = 72
PAGES = 12            # 12 x 1000 velas ~ 500 dias

series = {}
for s in SYMS:
    got, since = [], int((time.time() - 1000 * PAGES * 3600) * 1000)
    for _ in range(PAGES):
        try:
            page = fetch_ohlcv(s, "1h", limit=1000, since_ms=since)
        except Exception as e:
            print(f"  {s}: {e}"); break
        if not page: break
        got.extend(page)
        since = int(time.mktime(time.strptime(page[-1].ts, "%Y-%m-%dT%H:%M:%SZ")) * 1000) + 3600000
    seen, uniq = set(), []
    for c in got:
        if c.ts not in seen:
            seen.add(c.ts); uniq.append(c)
    if len(uniq) > 400:
        series[s] = uniq
    print(f"  {s}: {len(uniq)} velas")

pickle.dump(series, open("/private/tmp/claude-501/-Users-fernandocastaneda-Documents-ideas-scalp-bot/0acb6807-3a0d-4478-820e-4d398ce00750/scratchpad/crypto.pkl", "wb"))

def show(tag, rs):
    n = len(rs)
    if not n:
        print(f"  {tag:<30} sin senales"); return
    m = sum(rs)/n
    se = (statistics.stdev(rs)/math.sqrt(n)) if n > 1 else 0.0
    flag = "" if (m-1.96*se) > 0 else "   <- el IC cruza cero"
    print(f"  {tag:<30} n={n:<5} {m:+.3f}R  IC[{m-1.96*se:+.3f},{m+1.96*se:+.3f}]  "
          f"aciertos {sum(1 for x in rs if x>0)/n*100:4.1f}%{flag}")

sig_all = {s: signals(c) for s, c in series.items()}
def collect(side_filter=None):
    rs = []
    for sym, candles in series.items():
        last = {"LONG": -10**9, "SHORT": -10**9}
        for s in sig_all[sym]:
            i, sd = s["i"], s["side"]
            if i - last[sd] < H: continue
            last[sd] = i
            if side_filter and sd != side_filter: continue
            rs.append(resolve(geometry(s, "V0_actual"), candles[i+1:i+1+H], H).r_realized)
    return rs

print(f"\nCRIPTO, {sum(len(v) for v in series.values()):,} velas, {len(series)} simbolos\n")
show("Regla, ambos lados", collect())
show("Regla LONG", collect("LONG"))
show("Regla SHORT", collect("SHORT"))
