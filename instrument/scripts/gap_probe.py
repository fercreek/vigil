"""El hueco de apertura: cuanto salta el precio entre el cierre de una vela y la
apertura de la siguiente. Importa porque el stop del bot asume precio continuo --
si el mercado abre del otro lado, el stop no cuesta 1R, cuesta lo que el hueco diga.
"""
import sys, statistics, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
import yfinance as yf

STOCKS = ["NVDA","TSLA","AAPL","COIN","HOOD","IONQ","OKLO","SMR","RKLB","IREN","MP","CRWV"]

print(f"{'TICKER':<8}{'gap medio':>11}{'gap p95':>10}{'gaps >1R*':>11}")
print("-" * 42)
allg, allbig = [], 0
alln = 0
for s in STOCKS:
    df = yf.download(s, period="120d", interval="1h", progress=False, auto_adjust=False)
    if df is None or len(df) < 50:
        continue
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)
    o = df["Open"].tolist(); c = df["Close"].tolist(); h = df["High"].tolist(); l = df["Low"].tolist()
    # ATR simple de 14 para expresar el hueco en unidades de R (stop = 1.5*ATR)
    trs = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, len(c))]
    atr = statistics.mean(trs[-200:]) if len(trs) >= 200 else statistics.mean(trs)
    r_unit = 1.5 * atr
    gaps = [abs(o[i] - c[i-1]) for i in range(1, len(c))]
    big = sum(1 for g in gaps if g > r_unit)
    gaps_pct = sorted(g / c[i] * 100 for i, g in enumerate(gaps))
    allg += gaps_pct; allbig += big; alln += len(gaps)
    p95 = gaps_pct[int(len(gaps_pct) * 0.95)]
    print(f"{s:<8}{statistics.mean(gaps_pct):>10.2f}%{p95:>9.2f}%{big/len(gaps)*100:>10.2f}%")
print("-" * 42)
print(f"{'TOTAL':<8}{statistics.mean(allg):>10.2f}%{sorted(allg)[int(len(allg)*0.95)]:>9.2f}%{allbig/alln*100:>10.2f}%")
print("\n* gaps mayores que 1R completo (1.5xATR). Cada uno es un stop que no se")
print("  ejecuta donde el bot cree, sino peor.")
