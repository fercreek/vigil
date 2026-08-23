"""Antes de creerle un solo numero al evaluador rapido: que produzca EXACTAMENTE
los mismos disparos que rules.evaluate vela por vela. Si difiere en uno, no sirve.
"""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
sys.path.insert(0, "/private/tmp/claude-501/-Users-fernandocastaneda-Documents-ideas-scalp-bot/0acb6807-3a0d-4478-820e-4d398ce00750/scratchpad")
import yfinance as yf
from instrument import rules
from instrument.resolver import Candle
from geom_lab import signals

for sym in ["NVDA", "IONQ", "RKLB", "MP", "CRWV"]:
    df = yf.download(sym, period="60d", interval="1h", progress=False, auto_adjust=False)
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)
    candles = [Candle(ts=str(t), open=float(a), high=float(b), low=float(c), close=float(d))
               for t, a, b, c, d in zip(df.index, df["Open"], df["High"], df["Low"], df["Close"])]
    lento = {i for i in range(len(candles))
             if (r := rules.evaluate(sym, "1h", candles, i)) and r.get("decision") == "SENT"}
    rapido = {s["i"] for s in signals(candles)}
    estado = "IDENTICO" if lento == rapido else f"DIFIERE: solo-lento={sorted(lento-rapido)} solo-rapido={sorted(rapido-lento)}"
    print(f"  {sym:<7} lento={len(lento):<4} rapido={len(rapido):<4} {estado}")
