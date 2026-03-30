import time
import os
import ccxt
import pandas as pd
from datetime import datetime
import indicators_swing
import gemini_analyzer
import tracker
from dotenv import load_dotenv

load_dotenv()

# Configuración
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SYMBOLS = ["BTC/USDT", "ETH/USDT", "TAO/USDT"]
TIMEFRAME = '4h'

# Inicialización
binance = ccxt.binance()

def send_telegram(msg):
    """Enviador de alertas para el Swing Bot."""
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Error enviando Telegram (Swing): {e}")

def run_zenith_swing():
    """Bucle principal del Zenith Swing Bot."""
    print(f"🏛️ ZENITH SWING BOT V2.0 - INICIANDO [{datetime.now().strftime('%H:%M')}]")
    send_telegram("🏛️ <b>ZENITH SWING BOT ACTIVADO</b>\nEstrategia: Ichimoku + Bias Institucional (H4)")
    
    while True:
        try:
            for symbol in SYMBOLS:
                print(f"🔍 Analizando {symbol} (Swing)...")
                
                # 1. Obtener Datos H4
                ohlcv = binance.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=300)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                # 2. Análisis Técnico Swing
                technical = indicators_swing.analyze_swing_signals(df)
                bias_logic = technical['bias'] # BULL/BEAR/NEUTRAL
                
                # 3. Consultar Bias Semanal (AI)
                # Formateamos precios para Gemini
                price_context = {
                    symbol.replace('/USDT', ''): technical['price'],
                    f"{symbol.replace('/USDT', '')}_RSI": 50.0, # Placeholder o calcular real
                    f"{symbol.replace('/USDT', '')}_EMA_200": df['close'].ewm(span=200, adjust=False).mean().iloc[-1],
                    "USDT_D": 8.08
                }
                
                ai_report = gemini_analyzer.get_weekly_bias(symbol.replace('/USDT', ''), price_context)
                ai_bias = ai_report['bias']
                
                # 4. Consenso de Entrada (IA + Técnica)
                # Solo entramos si el Bias de la IA coincide con el Breakdown/Breakout técnico
                if ai_bias == bias_logic and ai_bias != "NEUTRAL":
                    side = "LONG" if ai_bias == "BULL" else "SHORT"
                    
                    msg = (f"🏛️ <b>ZENITH INSTITUTIONAL ALERT ({symbol})</b>\n\n"
                           f"🌌 <b>ESTRATEGIA</b>: Swing Trend Follower\n"
                           f"📊 <b>BIAS SEMANAL (IA)</b>: {ai_bias}\n"
                           f"☁️ <b>KUMO STATUS</b>: {bias_logic}\n\n"
                           f"💡 <b>RACIONAL INSTITUCIONAL:</b>\n"
                           f"{ai_report['analysis'][:500]}...\n\n"
                           f"🪙 {symbol} @ ${technical['price']:,.2f}\n"
                           f"🎯 TP (Swing): +3.00%\n"
                           f"🛑 SL (Swing): -1.50%")
                           
                    send_telegram(msg)
                    print(f"✅ Alerta Swing enviada para {symbol}")
                
            # Dormir 4 horas para el siguiente ciclo de velas
            print("⏳ Esperando siguiente cierre de vela (4H)...")
            time.sleep(3600 * 4) 
            
        except Exception:
            # Silencioso: Reintento en 5 minutos en lugar de 1
            time.sleep(300)

if __name__ == "__main__":
    run_zenith_swing()
