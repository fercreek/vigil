import ccxt
import os
import time
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class ZenithExecutor:
    def __init__(self):
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.mode = os.getenv("EXECUTION_MODE", "PAPER") # PAPER o LIVE
        self.risk_pct = float(os.getenv("RISK_PER_TRADE", "0.01")) # 1% del balance
        
        # Conectamos con Binance (Futures por defecto para capital institucional)
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'options': {'defaultType': 'future'} # Usamos Futuros
        })

    def get_balance(self):
        """Obtiene el balance de USDT en la cuenta de Futuros."""
        if self.mode == "PAPER":
            return 1000.0 # Balance simulado para Paper Trading
        try:
            balance = self.exchange.fetch_balance()
            # En Futuros el balance total está en 'total'
            return float(balance['total'].get('USDT', 0))
        except Exception as e:
            print(f"❌ Error obteniendo balance: {e}")
            return 0.0

    def calculate_amount(self, symbol, entry, sl, balance):
        """Calcula el tamaño de la posición basado en el riesgo (1% balance)."""
        try:
            risk_amount = balance * self.risk_pct
            sl_distance = abs(entry - sl)
            if sl_distance == 0: return 0.1 # Fallback mínimo
            
            # Cantidad = Riesgo / Distancia SL
            raw_amount = risk_amount / sl_distance
            
            # Formatear según los límites de Binance (load_markets)
            # symbol para Binance CCXT en futuros es como 'TAO/USDT' o 'ZEC/USDT'
            m_sym = f"{symbol}/USDT"
            
            # Cargamos mercados para precisiones
            self.exchange.load_markets()
            amount = self.exchange.amount_to_precision(m_sym, raw_amount)
            
            # Verificación de costo mínimo ($5.1 USDT en Binance)
            if float(amount) * entry < 5.1:
                # Ajustamos al mínimo permitido si es necesario
                min_amount = 5.2 / entry
                amount = self.exchange.amount_to_precision(m_sym, min_amount)
                
            return float(amount)
        except Exception as e:
            print(f"⚠️ Error calculando cantidad: {e}")
            return 0.0

    def execute_bracket_order(self, symbol, side, entry, tp1, tp2, sl):
        """Ejecuta una orden Bracket (Entrada + TP + SL) en Binance."""
        print(f"💸 [Zenith Executor] Iniciando ciclo de ejecución para {symbol} ({side})...")
        
        balance = self.get_balance()
        if balance < 10:
            return {"status": "FAILED", "reason": f"Saldo insuficiente (${balance:.2f} < $10)"}

        amount = self.calculate_amount(symbol, entry, sl, balance)
        if amount <= 0:
            return {"status": "FAILED", "reason": "Error en cálculo de tamaño (Size=0)"}

        exchange_symbol = f"{symbol}/USDT"
        
        if self.mode == "PAPER":
            report = (f"🛡️ [PAPER_MODE] Simulación de orden {side} en {symbol}\n"
                      f"💰 Cantidad: {amount} {symbol} (~${(amount * entry):.2f})\n"
                      f"🎯 TP1: {tp1} | 🎯 TP2: {tp2}\n"
                      f"🛑 SL: {sl}")
            print(report)
            return {"status": "PAPER_EXECUTED", "id": f"PAPER_{int(time.time())}", "amount": amount}

        # --- LIVE EXECUTION MODE (REAL TRADING) ---
        try:
            # 1. Configurar Apalancamiento (Aislado 5x por seguridad)
            try:
                self.exchange.fapiPrivatePostMarginType({
                    'symbol': symbol + 'USDT',
                    'marginType': 'ISOLATED'
                })
            except: pass # Ya está configurado
            
            try:
                self.exchange.set_leverage(5, exchange_symbol)
            except: pass

            # 2. Orden de Entrada (MARKET para rapidez institucional)
            order_side = 'buy' if side == 'LONG' else 'sell'
            entry_order = self.exchange.create_order(
                symbol=exchange_symbol,
                type='market',
                side=order_side,
                amount=amount
            )
            
            entry_id = entry_order['id']
            print(f"✅ Entrada ejecutada: ID {entry_id}")

            # 3. Órdenes de Protección (Reduce-Only)
            exit_side = 'sell' if side == 'LONG' else 'buy'
            
            # 3a. Take Profit 1 (70% de la posición)
            self.exchange.create_order(
                symbol=exchange_symbol,
                type='limit',
                side=exit_side,
                amount=amount * 0.7,
                price=tp1,
                params={'reduceOnly': True}
            )

            # 3b. Stop Loss (Total)
            self.exchange.create_order(
                symbol=exchange_symbol,
                type='STOP_MARKET',
                side=exit_side,
                amount=amount,
                params={'stopPrice': sl, 'reduceOnly': True}
            )

            return {
                "status": "LIVE_EXECUTED",
                "id": entry_id,
                "amount": amount,
                "msg": f"✅ Orden Ejecutada en Binance. ID: {entry_id}"
            }

        except Exception as e:
            err_msg = str(e)
            print(f"❌ Error Crítico en Ejecución: {err_msg}")
            return {"status": "FAILED", "reason": err_msg}
