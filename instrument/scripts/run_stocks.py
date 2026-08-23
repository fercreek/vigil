from pathlib import Path
import sys, warnings, pickle
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import yfinance as yf
from instrument.resolver import Candle
from geom_lab import run, report

# El cache vive junto a estos scripts, no en un directorio de la maquina que los
# escribio. La version anterior guardaba rutas absolutas del scratchpad: los
# scripts se commitearon diciendo que servian para re-correr los numeros, y no
# corrian en ninguna otra maquina.
_HERE = Path(__file__).resolve().parent
_CACHE = _HERE / "_cache"
_CACHE.mkdir(exist_ok=True)


STOCKS = ["NVDA","TSLA","AAPL","COIN","HOOD","IONQ","OKLO","SMR","RKLB","IREN","XLE","SOFI",
          "MP","CRWV","AMD","PLTR","MSTR","SOUN","RGTI","UUUU","ASTS","CLSK","CORZ","XOM",
          "VST","AVGO","META","MSFT","AMZN","GOOGL"]

series, dayof = {}, {}
for s in STOCKS:
    try:
        df = yf.download(s, period="730d", interval="1h", progress=False, auto_adjust=False)
        if df is None or len(df) < 400:
            continue
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)
        series[s] = [Candle(ts=str(t), open=float(a), high=float(b), low=float(c), close=float(d))
                     for t, a, b, c, d in zip(df.index, df["Open"], df["High"], df["Low"], df["Close"])]
        dayof[s] = [t.date() for t in df.index]
    except Exception as e:
        print(f"  {s}: {e}")

pickle.dump((series, dayof), open(str(_CACHE / "stocks.pkl"), "wb"))
total = sum(len(v) for v in series.values())
print(f"ACCIONES: {len(series)} tickers, {total:,} velas horarias (2 anios)\n")
for v in ("V0_actual", "V1_gap", "V2_intradia"):
    report(v, run(series, v, 72, dayof))
