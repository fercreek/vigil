import ccxt
import pandas as pd
import requests

# Configuración de exchanges
# Binance para BTC y ETH
binance = ccxt.binance()
# Gate.io para TAO (Bittensor) suele tener más liquidez y disponibilidad
gateio = ccxt.gateio()

def calculate_rsi(prices, period=14):
    """Calcula el RSI (Relative Strength Index) estándar."""
    if len(prices) < period:
        return 50.0  # Retornar neutral si no hay suficientes datos
    
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def get_rsi(symbol, timeframe='1h'):
    """Obtiene el RSI para un símbolo y temporalidad dados."""
    try:
        # Mapeo de símbolos para los exchanges
        exchange = binance
        exchange_symbol = symbol
        
        if "TAO" in symbol:
            exchange = gateio
            exchange_symbol = "TAO/USDT"
        elif "ETH" in symbol:
            exchange_symbol = "ETH/USDT"
        elif "BTC" in symbol:
            exchange_symbol = "BTC/USDT"
            
        ohlcv = exchange.fetch_ohlcv(exchange_symbol, timeframe=timeframe, limit=50)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return calculate_rsi(df['close'])
    except Exception as e:
        print(f"[Error RSI {symbol} {timeframe}] {e}")
        return 50.0

def get_usdt_dominance():
    """Obtiene la dominancia de USDT desde CoinGecko Global."""
    try:
        url = "https://api.coingecko.com/api/v3/global"
        r = requests.get(url, timeout=10)
        data = r.json()
        return data['data']['market_cap_percentage'].get('usdt', 8.0)
    except Exception as e:
        print(f"[Error USDT.D] {e}")
        return 8.0 # Retornar neutral/alto si falla
