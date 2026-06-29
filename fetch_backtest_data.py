"""
fetch_backtest_data.py — Descarga 1 año de datos horarios para símbolos extra
Usa yfinance. Guarda en data/{SYM}_1h_365d.csv con mismo formato que los CSVs existentes.
"""
import yfinance as yf
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# Símbolo yfinance → nombre corto para el archivo
TARGETS = {
    "GC=F":   "GOLD",    # Gold futures
    "SOL-USD": "SOL",
    "BNB-USD": "BNB",
    "COIN":    "COIN",
    "NVDA":    "NVDA",
    "GLD":     "GLD",    # Gold ETF (diario — más estable que futures)
    "BTC-USD": "BTC_YF", # BTC via yfinance para cross-check
}

for ticker, name in TARGETS.items():
    out = DATA_DIR / f"{name}_1h_365d.csv"
    print(f"  Descargando {ticker} ({name})...", end=" ", flush=True)
    try:
        df = yf.download(ticker, period="1y", interval="1h", auto_adjust=True, progress=False)
        if df.empty:
            print("vacío — skipping")
            continue
        df = df.reset_index()
        # Normalizar columnas al formato estándar
        df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
        ts_col = "datetime" if "datetime" in df.columns else "date"
        df = df.rename(columns={ts_col: "timestamp"})
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        df = df.dropna()
        df.to_csv(out, index=False)
        print(f"{len(df)} filas → {out.name}")
    except Exception as e:
        print(f"ERROR: {e}")

print("\nListo.")
