import indicators_swing
import gemini_analyzer
import pandas as pd
import ccxt

def test_consensus():
    symbol = "BTC/USDT"
    print(f"🧪 Probando Consenso Zenith Swing para {symbol}...")
    
    binance = ccxt.binance()
    ohlcv = binance.fetch_ohlcv(symbol, timeframe='4h', limit=100)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # 1. Técnica
    tech = indicators_swing.analyze_swing_signals(df)
    print(f"📡 Técnica (Ichimoku): {tech['bias']}")
    
    # 2. IA
    price_ctx = {
        "BTC": tech['price'],
        "BTC_RSI": 50.0,
        "BTC_EMA_200": df['close'].ewm(span=200, adjust=False).mean().iloc[-1],
        "USDT_D": 8.08
    }
    ai = gemini_analyzer.get_weekly_bias("BTC", price_ctx)
    print(f"🏛️ Al Bias: {ai['bias']}")
    print(f"\n--- REPORTE IA ---\n{ai['analysis'][:300]}...")
    
    if tech['bias'] == ai['bias']:
        print("\n✅ CONTEXTO ALINEADO: SEÑAL VÁLIDA")
    else:
        print("\n⏳ CONTEXTO DIVERGENTE: ESPERANDO CONFLUENCIA")

if __name__ == "__main__":
    test_consensus()
