"""Cuantas veces dispararia la regla del pullback en ACCIONES, contra cripto.

No opina: baja 1h real de yfinance y corre rules.py sobre cada vela cerrada,
usando ta.py -- las mismas funciones que decide el bot, no una reimplementacion.
"""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
import yfinance as yf
from instrument import ta, rules
from instrument.resolver import Candle

STOCKS = ["NVDA","TSLA","AAPL","COIN","HOOD","IONQ","OKLO","SMR","RKLB","IREN","XLE","SOFI","MP","CRWV"]

def probe(sym):
    df = yf.download(sym, period="60d", interval="1h", progress=False, auto_adjust=False)
    if df is None or len(df) < 300:
        return None
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)
    o = df["Open"].tolist(); h = df["High"].tolist()
    l = df["Low"].tolist();  c = df["Close"].tolist()
    candles = [Candle(ts=str(t), open=float(a), high=float(b), low=float(d), close=float(e))
               for t,a,b,d,e in zip(df.index, o, h, l, c)]
    n = len(candles)
    counts = {"rsi":0,"bb":0,"adx":0,"atr":0,"todas":0,"evaluadas":0}
    atrs = []
    for i in range(260, n):
        row = rules.evaluate(sym, "1h", candles, i)
        if row is None:
            continue
        counts["evaluadas"] += 1
        if row.get("atr_pct") is not None:
            atrs.append(row["atr_pct"])
        passed = set(row.get("gates_passed") or [])
        for k, g in (("rsi","rsi_extreme"),("bb","bb_confluence"),("adx","adx_trending"),("atr","atr_min")):
            if g in passed:
                counts[k] += 1
        if row.get("decision") == "SENT":
            counts["todas"] += 1
    atrs.sort()
    med = atrs[len(atrs)//2] if atrs else 0.0
    return counts, med

print(f"{'TICKER':<8}{'velas':>7}{'ATR% med':>10}{'RSI':>7}{'banda':>8}{'ADX':>7}{'ATR':>7}{'LAS 4':>8}")
print("-" * 62)
tot = {"evaluadas":0,"rsi":0,"bb":0,"adx":0,"atr":0,"todas":0}
for s in STOCKS:
    try:
        r = probe(s)
    except Exception as exc:
        print(f"{s:<8}  error: {exc}")
        continue
    if r is None:
        print(f"{s:<8}  sin datos suficientes")
        continue
    cc, med = r
    e = cc["evaluadas"] or 1
    for k in tot:
        tot[k] += cc[k]
    print(f"{s:<8}{cc['evaluadas']:>7}{med*100:>9.2f}%{cc['rsi']*100//e:>6.0f}%{cc['bb']*100//e:>7.0f}%"
          f"{cc['adx']*100//e:>6.0f}%{cc['atr']*100//e:>6.0f}%{cc['todas']:>8}")
e = tot["evaluadas"] or 1
print("-" * 62)
print(f"{'TOTAL':<8}{tot['evaluadas']:>7}{'':>10}{tot['rsi']*100//e:>6.0f}%{tot['bb']*100//e:>7.0f}%"
      f"{tot['adx']*100//e:>6.0f}%{tot['atr']*100//e:>6.0f}%{tot['todas']:>8}")
print(f"\nGate de ATR: rules.ATR_MIN_PCT = {rules.ATR_MIN_PCT*100:.2f}%")
