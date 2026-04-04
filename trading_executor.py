import ccxt
import os
import time
from dotenv import load_dotenv
from config import DEFAULT_LEVERAGE, RISK_PER_TRADE_PCT, MIN_BALANCE_USD

# Cargar variables de entorno
load_dotenv()

class ZenithExecutor:
    def __init__(self):
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.mode = os.getenv("EXECUTION_MODE", "PAPER") # PAPER o LIVE
        # Config centralizada: config.py es fuente de verdad, env var como override
        self.risk_pct = float(os.getenv("RISK_PER_TRADE", str(RISK_PER_TRADE_PCT)))
        self.leverage = int(os.getenv("DEFAULT_LEVERAGE", str(DEFAULT_LEVERAGE)))
        self.min_balance = MIN_BALANCE_USD
        
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
            
            if self.mode == "PAPER":
                return round(raw_amount, 2) # Bypass precision logic for paper
                
            # Formatear según los límites de Binance (load_markets)
            exchange_symbol = f"{symbol}/USDT"
            self.exchange.load_markets()
            amount = self.exchange.amount_to_precision(exchange_symbol, raw_amount)
            
            # Verificación de costo mínimo ($5.1 USDT en Binance)
            if float(amount) * entry < 5.1:
                min_amount = 5.2 / entry
                amount = self.exchange.amount_to_precision(exchange_symbol, min_amount)
                
            return float(amount)
        except Exception as e:
            if self.mode == "PAPER": return 10.0 # Fallback Hardcoded for Paper
            print(f"⚠️ Error calculando cantidad: {e}")
            return 0.0

    def execute_bracket_order(self, symbol, side, entry, tp1, tp2, sl, tp3=None):
        """Ejecuta una orden Bracket (Entrada + 3 TPs + SL) en Binance."""
        print(f"💸 [Zenith Executor] Iniciando ciclo de ejecución V6 (3 TPs) para {symbol} ({side})...")
        
        balance = self.get_balance()
        if balance < self.min_balance:
            return {"status": "FAILED", "reason": f"Saldo insuficiente (${balance:.2f} < $10)"}

        amount = self.calculate_amount(symbol, entry, sl, balance)
        if amount <= 0:
            return {"status": "FAILED", "reason": "Error en cálculo de tamaño (Size=0)"}

        exchange_symbol = f"{symbol}/USDT"
        final_tp3 = tp3 if tp3 else round(entry * (1.1 if side == "LONG" else 0.9), 2)
        
        if self.mode == "PAPER":
            report = (f"🛡️ [PAPER_MODE V6] Simulación de orden {side} en {symbol}\n"
                      f"💰 Cantidad: {amount} {symbol} (~${(amount * entry):.2f})\n"
                      f"🎯 TP1 (50%): {tp1} | 🎯 TP2 (25%): {tp2} | 🎯 TP3 (25%): {final_tp3}\n"
                      f"🛑 SL: {sl}")
            print(report)
            return {"status": "PAPER_EXECUTED", "id": f"PAPER_{int(time.time())}", "amount": amount}

        # --- LIVE EXECUTION MODE (REAL TRADING) ---
        try:
            # 1. Configurar Apalancamiento e Isolation
            # Si falla el leverage, ABORTAMOS — operar a leverage incorrecto es inaceptable
            try:
                self.exchange.fapiPrivatePostMarginType({'symbol': symbol + 'USDT', 'marginType': 'ISOLATED'})
            except Exception as e:
                print(f"⚠️ [Executor] Margin type ya configurado o error no crítico: {e}")
            try:
                self.exchange.set_leverage(self.leverage, exchange_symbol)
                print(f"✅ [Executor] Leverage x{self.leverage} configurado para {exchange_symbol}")
            except Exception as e:
                err_msg = str(e)
                print(f"❌ [Executor] FALLO CRÍTICO: No se pudo configurar leverage para {exchange_symbol}: {err_msg}")
                return {"status": "FAILED", "reason": f"Leverage setup falló: {err_msg}"}

            # 2. Orden de Entrada (MARKET)
            order_side = 'buy' if side == 'LONG' else 'sell'
            entry_order = self.exchange.create_order(symbol=exchange_symbol, type='market', side=order_side, amount=amount)
            entry_id = entry_order['id']
            print(f"✅ Entrada ejecutada: ID {entry_id}")

            # 3. Órdenes de Protección (Reduce-Only)
            exit_side = 'sell' if side == 'LONG' else 'buy'
            
            # 3a. TP1 (50%)
            self.exchange.create_order(
                symbol=exchange_symbol, type='limit', side=exit_side, 
                amount=amount * 0.5, price=tp1, params={'reduceOnly': True}
            )

            # 3b. TP2 (25%)
            self.exchange.create_order(
                symbol=exchange_symbol, type='limit', side=exit_side, 
                amount=amount * 0.25, price=tp2, params={'reduceOnly': True}
            )
            
            # 3c. TP3 (25%)
            self.exchange.create_order(
                symbol=exchange_symbol, type='limit', side=exit_side, 
                amount=amount * 0.25, price=final_tp3, params={'reduceOnly': True}
            )

            # 3d. Stop Loss (Total)
            self.exchange.create_order(
                symbol=exchange_symbol, type='STOP_MARKET', side=exit_side, 
                amount=amount, params={'stopPrice': sl, 'reduceOnly': True}
            )

            return {
                "status": "LIVE_EXECUTED",
                "id": entry_id,
                "amount": amount,
                "msg": f"✅ Orden V6 (3 TPs) Ejecutada. ID: {entry_id}"
            }

        except Exception as e:
            err_msg = str(e)
            print(f"❌ Error Crítico en Ejecución: {err_msg}")
            return {"status": "FAILED", "reason": err_msg}
