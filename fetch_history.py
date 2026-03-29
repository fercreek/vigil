import ccxt
import pandas as pd
import time
import os
from datetime import datetime, timedelta

def fetch_historical_data(symbol: str, exchange_id: str = 'binance', timeframe: str = '1h', days: int = 365, cache_dir: str = 'data'):
    # Crear directorio local si no existe
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
        
    safe_symbol = symbol.replace("/", "_")
    filename = f"{cache_dir}/{safe_symbol}_{timeframe}_{days}d.csv"
    
    # Si ya lo descargamos hoy, saltar
    if os.path.exists(filename):
        print(f"[CACHE] {filename} ya existe, leyéndolo de memoria...")
        return pd.read_csv(filename, parse_dates=['timestamp'], index_col='timestamp')

    print(f"[API] Descargando {days} días de {symbol} ({timeframe}) desde {exchange_id}...")
    
    # Configurar exchange
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({'enableRateLimit': True})
    
    # Calcular marcas de tiempo (offset to avoid ccxt timezone issues)
    now = int(time.time() * 1000)
    since = now - (days * 24 * 60 * 60 * 1000)
    
    all_ohlcv = []
    
    while since < now:
        try:
            # Paginación (1000 velas por llamada es el límite común)
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, limit=1000)
            if not ohlcv:
                break
                
            all_ohlcv += ohlcv
            
            # El último timestamp recolectado se convierte en el nuevo 'since'
            # Sumamos 1 milisegundo para no pedir la misma vela dos veces
            since = ohlcv[-1][0] + 1
            
            print(f"  ... recolectadas {len(all_ohlcv)} velas. Llegando a: {pd.to_datetime(since, unit='ms')}")
            time.sleep(exchange.rateLimit / 1000) # Respetar rate limit instucional
            
        except Exception as e:
            print(f"[ERROR API] {e}")
            break
            
    # Guardar en DataFrame
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Guardar localmente
    df.to_csv(filename)
    print(f"[EXITO] Guardado {filename} | Total Velas: {len(df)}")
    return df

if __name__ == "__main__":
    # Prueba de descarga: 1 Año en Velas de 1H (Ideal para calcular Soportes y Resistencias macro)
    fetch_historical_data("ETH/USDT", "binance", "1h", 365)
    fetch_historical_data("BTC/USDT", "binance", "1h", 365)
    
    # TAO no lleva 1 año en binance, lo bajamos de Gate.io o recortamos a los días que lleve
    try:
        fetch_historical_data("TAO/USDT", "binance", "1h", 365) # Si falla, intenta bajando menos tiempo
    except Exception as e:
        print(f"Advertencia TAO Binance: {e}")
