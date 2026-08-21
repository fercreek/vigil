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

    def calculate_amount(self, symbol, entry, sl, balance, dynamic_risk_pct=None):
        """Calcula el tamaño de la posición basado en el riesgo dinámico."""
        try:
            risk_pct = dynamic_risk_pct if dynamic_risk_pct is not None else self.risk_pct
            risk_amount = balance * risk_pct
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

    # ── Sincronizacion del stop con el exchange ──────────────────────────────
    # El bot movia el SL solo en su tabla (tracker.update_sl / mark_be) y la orden
    # STOP_MARKET seguia en Binance donde se dejo al abrir el bracket. En LIVE eso
    # significaba que el bot reportaba "SL en BE" con el stop real todavia a 2 ATR.

    @staticmethod
    def _is_bot_stop_order(order: dict) -> bool:
        """True si la orden es una STOP_MARKET reduceOnly — las que pone el bracket.

        ccxt normaliza el tipo de forma distinta segun version, asi que se mira el
        campo normalizado Y el crudo de `info`. Se exige reduceOnly para no tocar
        una orden de entrada.
        """
        if not isinstance(order, dict):
            return False
        info = order.get("info") or {}
        raw_type = str(info.get("type") or order.get("type") or "")
        if "STOP" not in raw_type.upper().replace("_", ""):
            return False
        reduce_only = order.get("reduceOnly")
        if reduce_only is None:
            reduce_only = str(info.get("reduceOnly", "")).lower() == "true"
        return bool(reduce_only)

    def sync_stop_loss(self, symbol: str, side: str, new_sl: float) -> dict:
        """Reemplaza la STOP_MARKET viva por una nueva en `new_sl`.

        NO crea un stop donde no habia. Si la orden desaparecio (se lleno, la
        cancelaste a mano, o la posicion ya cerro) devuelve NOT_FOUND y no toca
        nada: crear una orden a ciegas sobre una posicion que el bot no abrio es
        justo lo que hay que evitar. El unico lugar del repo que crea STOP_MARKET
        es execute_bracket_order, asi que lo que se cancela aqui siempre es propio.

        Nunca lanza: el ciclo de monitoreo no se cae porque el exchange falle.
        """
        self.mode = os.getenv("EXECUTION_MODE", "PAPER")
        if self.mode != "LIVE":
            return {"status": "SKIPPED_PAPER"}

        exchange_symbol = f"{symbol}/USDT"
        exit_side = "sell" if side == "LONG" else "buy"
        try:
            open_orders = self.exchange.fetch_open_orders(exchange_symbol) or []
            stops = [o for o in open_orders if self._is_bot_stop_order(o)]
            if not stops:
                print(f"⚠️ [SL Sync] {symbol}: sin STOP_MARKET viva — nada que mover")
                return {"status": "NOT_FOUND"}

            amount = None
            cancelled = []
            for o in stops:
                try:
                    self.exchange.cancel_order(o["id"], exchange_symbol)
                    cancelled.append(o["id"])
                    amount = amount or o.get("amount") or (o.get("info") or {}).get("origQty")
                except Exception as e:
                    # Carrera clasica: se lleno entre el fetch y el cancel.
                    print(f"⚠️ [SL Sync] {symbol}: no se pudo cancelar {o.get('id')}: {e}")

            if not cancelled:
                return {"status": "NOT_FOUND"}
            if not amount:
                print(f"❌ [SL Sync] {symbol}: stop cancelado pero sin cantidad — POSICION SIN STOP")
                return {"status": "FAILED", "reason": "sin amount", "unprotected": True}

            # A partir de aqui la posicion esta SIN STOP hasta que el alta confirme.
            try:
                new_order = self.exchange.create_order(
                    symbol=exchange_symbol, type="STOP_MARKET", side=exit_side,
                    amount=float(amount), params={"stopPrice": new_sl, "reduceOnly": True})
            except Exception as e:
                print(f"🚨 [SL Sync] {symbol}: stop viejo CANCELADO y el nuevo NO entro "
                      f"({e}) — POSICION SIN STOP")
                return {"status": "FAILED", "reason": str(e), "unprotected": True}

            print(f"🛑 [SL Sync] {symbol}: stop movido a {new_sl} (cancelada {cancelled})")
            return {"status": "SYNCED", "id": new_order.get("id"),
                    "cancelled": cancelled, "new_sl": new_sl, "amount": float(amount)}

        except Exception as e:
            # Fallo antes de cancelar nada (fetch_open_orders): el stop viejo sigue
            # puesto. Malo pero no peligroso — la posicion sigue protegida.
            print(f"❌ [SL Sync] {symbol}: {e}")
            return {"status": "FAILED", "reason": str(e)}

    def execute_bracket_order(self, symbol, side, entry, tp1, tp2, sl, tp3=None,
                              dynamic_leverage=None, dynamic_risk_pct=None):
        """Ejecuta una orden Bracket (Entrada + 3 TPs + SL) en Binance."""
        # F2 runtime pause check
        try:
            import runtime_state
            if runtime_state.is_paused():
                print(f"[Zenith Executor] Paused — skip {symbol} {side}")
                return {"status": "SKIPPED", "reason": "Bot paused (/pause)"}
        except Exception as _e:
            print(f"WARN pause check: {_e}")

        # Re-read mode in case /mode switched it at runtime
        self.mode = os.getenv("EXECUTION_MODE", "PAPER")

        print(f"💸 [Zenith Executor] Iniciando ciclo de ejecución V6 (3 TPs) para {symbol} ({side})...")

        balance = self.get_balance()
        if balance < self.min_balance:
            return {"status": "FAILED", "reason": f"Saldo insuficiente (${balance:.2f} < $10)"}

        amount = self.calculate_amount(symbol, entry, sl, balance, dynamic_risk_pct=dynamic_risk_pct)
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
            leverage_to_use = dynamic_leverage if dynamic_leverage else self.leverage
            try:
                self.exchange.set_leverage(leverage_to_use, exchange_symbol)
                print(f"✅ [Executor] Leverage x{leverage_to_use} configurado para {exchange_symbol}")
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
