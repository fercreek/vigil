"""
risk_manager.py — Circuit Breaker, Dynamic Position Sizing, Trailing Stop Manager

Phase 1 del plan de mejoras Zenith v2.0.
Protección existencial contra pérdidas en cascada y sizing dinámico por volatilidad.
"""

import time
import json
import os
from datetime import datetime
from config import (
    RISK_PER_TRADE_PCT,
)

# ── Config de Risk Manager (centralizados aquí para Phase 1) ─────────────────
# Circuit Breaker
CB_MAX_CONSECUTIVE_LOSSES = 3       # Pérdidas seguidas → HALTED
CB_CAUTIOUS_AFTER_LOSSES = 2        # Pérdidas seguidas → CAUTIOUS (50% size)
CB_MAX_SESSION_DRAWDOWN_PCT = 5.0   # Drawdown de sesión → HALTED
CB_COOLDOWN_SECONDS = 1800          # 30 min en HALTED antes de reset automático

# Dynamic Risk Sizing
RISK_MIN_PCT = 0.005   # 0.5% — mínimo en alta volatilidad
RISK_MAX_PCT = 0.015   # 1.5% — máximo en baja volatilidad
RISK_BASE_PCT = RISK_PER_TRADE_PCT  # 1.0% default
VOL_HIGH_THRESHOLD = 3.0   # ATR/price % — por encima = reducir riesgo
VOL_LOW_THRESHOLD = 1.5    # ATR/price % — por debajo = aumentar riesgo

# Trailing Stop
TSL_ATR_MULTIPLIER = 2.5    # Trail con ATR * 2.5
TSL_ACTIVATION_RR = 1.0     # Activar trailing tras 1:1 R:R alcanzado
TSL_MIN_STEP_ATR = 0.25     # Mínimo movimiento para generar update: 25% de ATR (anti-spam)

# Persistencia del estado
_STATE_FILE = "risk_state.json"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════════════════════

class CircuitBreaker:
    """
    Sistema de protección automática contra pérdidas en cascada.

    Estados:
      - NORMAL:   Operación normal, risk 100%
      - CAUTIOUS: 2 pérdidas consecutivas, risk reducido a 50%
      - HALTED:   3 pérdidas consecutivas o drawdown > 5%, no se opera

    Persiste estado en JSON para sobrevivir reinicios del bot.
    """

    NORMAL = "NORMAL"
    CAUTIOUS = "CAUTIOUS"
    HALTED = "HALTED"

    def __init__(self):
        self.state = self.NORMAL
        self.consecutive_losses = 0
        self.session_pnl_pct = 0.0       # PnL acumulado en sesión
        self.session_peak_pct = 0.0       # Pico de PnL en sesión (para drawdown)
        self.halted_at = 0.0              # Timestamp de cuando entró en HALTED
        self.trades_today = 0
        self.wins_today = 0
        self.losses_today = 0
        self._last_date = datetime.now().strftime("%Y-%m-%d")
        self._load_state()

    def _load_state(self):
        """Carga estado persistido de sesiones anteriores."""
        if not os.path.exists(_STATE_FILE):
            return
        try:
            with open(_STATE_FILE, "r") as f:
                data = json.load(f)
            # Solo restaurar si es del mismo día
            if data.get("date") == self._last_date:
                self.state = data.get("state", self.NORMAL)
                self.consecutive_losses = data.get("consecutive_losses", 0)
                self.session_pnl_pct = data.get("session_pnl_pct", 0.0)
                self.session_peak_pct = data.get("session_peak_pct", 0.0)
                self.halted_at = data.get("halted_at", 0.0)
                self.trades_today = data.get("trades_today", 0)
                self.wins_today = data.get("wins_today", 0)
                self.losses_today = data.get("losses_today", 0)
                print(f"🛡️ [CircuitBreaker] Estado restaurado: {self.state} "
                      f"(losses: {self.consecutive_losses}, DD: {self.session_pnl_pct:.2f}%)")
            else:
                # Nuevo día: reset
                self._reset_session()
        except Exception as e:
            print(f"⚠️ [CircuitBreaker] Error cargando estado: {e}")

    def _save_state(self):
        """Persiste estado a disco."""
        try:
            data = {
                "date": self._last_date,
                "state": self.state,
                "consecutive_losses": self.consecutive_losses,
                "session_pnl_pct": round(self.session_pnl_pct, 4),
                "session_peak_pct": round(self.session_peak_pct, 4),
                "halted_at": self.halted_at,
                "trades_today": self.trades_today,
                "wins_today": self.wins_today,
                "losses_today": self.losses_today,
            }
            with open(_STATE_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ [CircuitBreaker] Error guardando estado: {e}")

    def _reset_session(self):
        """Resetea contadores para nuevo día."""
        self.state = self.NORMAL
        self.consecutive_losses = 0
        self.session_pnl_pct = 0.0
        self.session_peak_pct = 0.0
        self.halted_at = 0.0
        self.trades_today = 0
        self.wins_today = 0
        self.losses_today = 0
        self._last_date = datetime.now().strftime("%Y-%m-%d")
        self._save_state()

    def _check_new_day(self):
        """Auto-reset si cambió el día."""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._last_date:
            print(f"🔄 [CircuitBreaker] Nuevo día detectado. Reset de sesión.")
            self._reset_session()

    def can_trade(self) -> tuple:
        """
        Verifica si se permite operar.

        Returns:
            (bool, str, float): (puede_operar, razón, multiplicador_de_risk)
              - multiplicador: 1.0 = normal, 0.5 = cautious, 0.0 = halted
        """
        self._check_new_day()

        # Auto-recovery: si HALTED y pasó el cooldown
        if self.state == self.HALTED:
            elapsed = time.time() - self.halted_at
            if elapsed >= CB_COOLDOWN_SECONDS:
                mins = CB_COOLDOWN_SECONDS // 60
                self.state = self.CAUTIOUS  # No vuelve directo a NORMAL
                self.consecutive_losses = CB_CAUTIOUS_AFTER_LOSSES  # Mantiene cautela
                print(f"🔄 [CircuitBreaker] Cooldown de {mins}min completado. Estado: CAUTIOUS")
                self._save_state()

        if self.state == self.HALTED:
            remaining = CB_COOLDOWN_SECONDS - (time.time() - self.halted_at)
            mins_left = max(0, int(remaining // 60))
            return (False, f"HALTED — {self.consecutive_losses} pérdidas consecutivas. "
                          f"Cooldown: {mins_left}min restantes", 0.0)

        if self.state == self.CAUTIOUS:
            return (True, f"CAUTIOUS — {self.consecutive_losses} pérdidas. Risk reducido 50%", 0.5)

        return (True, "NORMAL — operación estándar", 1.0)

    def record_outcome(self, is_win: bool, pnl_pct: float = 0.0):
        """
        Registra el resultado de un trade y actualiza el estado.

        Args:
            is_win: True si el trade fue ganador (FULL_WON o PARTIAL_WON)
            pnl_pct: PnL porcentual del trade (positivo o negativo)
        """
        self._check_new_day()
        self.trades_today += 1

        if is_win:
            self.wins_today += 1
            self.consecutive_losses = 0
            # Después de un win, si estábamos CAUTIOUS → NORMAL
            if self.state == self.CAUTIOUS:
                self.state = self.NORMAL
                print(f"🟢 [CircuitBreaker] Win registrado. Estado: NORMAL")
        else:
            self.losses_today += 1
            self.consecutive_losses += 1
            print(f"🔴 [CircuitBreaker] Loss #{self.consecutive_losses} registrado")

        # Actualizar PnL de sesión
        self.session_pnl_pct += pnl_pct
        if self.session_pnl_pct > self.session_peak_pct:
            self.session_peak_pct = self.session_pnl_pct

        # Calcular drawdown desde el pico
        session_dd = self.session_peak_pct - self.session_pnl_pct

        # Transiciones de estado
        if self.consecutive_losses >= CB_MAX_CONSECUTIVE_LOSSES:
            self.state = self.HALTED
            self.halted_at = time.time()
            print(f"🚨 [CircuitBreaker] HALTED! {self.consecutive_losses} pérdidas consecutivas")
        elif session_dd >= CB_MAX_SESSION_DRAWDOWN_PCT:
            self.state = self.HALTED
            self.halted_at = time.time()
            print(f"🚨 [CircuitBreaker] HALTED! Drawdown de sesión: {session_dd:.2f}% (max: {CB_MAX_SESSION_DRAWDOWN_PCT}%)")
        elif self.consecutive_losses >= CB_CAUTIOUS_AFTER_LOSSES:
            if self.state != self.HALTED:  # No degradar de HALTED a CAUTIOUS
                self.state = self.CAUTIOUS
                print(f"⚠️ [CircuitBreaker] CAUTIOUS — {self.consecutive_losses} pérdidas consecutivas")

        self._save_state()

    def force_reset(self):
        """Reset manual (via comando Telegram)."""
        self._reset_session()
        print(f"🔄 [CircuitBreaker] Reset manual ejecutado. Estado: NORMAL")

    def get_status_html(self) -> str:
        """Genera resumen HTML para Telegram."""
        self._check_new_day()
        emoji = {"NORMAL": "🟢", "CAUTIOUS": "🟡", "HALTED": "🔴"}.get(self.state, "⚪")
        session_dd = self.session_peak_pct - self.session_pnl_pct

        lines = [
            f"{emoji} <b>CIRCUIT BREAKER: {self.state}</b>",
            f"",
            f"📊 <b>Sesión de hoy:</b>",
            f"• Trades: {self.trades_today} (W:{self.wins_today} / L:{self.losses_today})",
            f"• Pérdidas consecutivas: {self.consecutive_losses}/{CB_MAX_CONSECUTIVE_LOSSES}",
            f"• PnL sesión: {self.session_pnl_pct:+.2f}%",
            f"• Drawdown sesión: {session_dd:.2f}% (max: {CB_MAX_SESSION_DRAWDOWN_PCT}%)",
        ]

        if self.state == self.HALTED:
            remaining = CB_COOLDOWN_SECONDS - (time.time() - self.halted_at)
            mins_left = max(0, int(remaining // 60))
            lines.append(f"\n⏱️ Cooldown restante: {mins_left} min")

        if self.state == self.CAUTIOUS:
            lines.append(f"\n⚠️ Risk reducido al 50%. Un win regresa a NORMAL.")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DYNAMIC POSITION SIZING
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_dynamic_risk(atr: float, price: float, vix: float = 0.0,
                           trade_type: str = "SWING",
                           cb_multiplier: float = 1.0) -> float:
    """
    Calcula el % de riesgo dinámico basado en volatilidad actual.

    Lógica:
      - ATR/price > 3% O VIX > 25  → 0.5% (alta volatilidad, proteger capital)
      - ATR/price < 1.5% Y VIX < 20 → 1.5% (baja volatilidad, aprovechar)
      - Default: 1.0%
      - RAPIDA: siempre max 0.75%
      - Circuit breaker multiplier: 0.5 si CAUTIOUS

    Args:
        atr: Average True Range actual
        price: Precio actual del activo
        vix: Índice VIX actual
        trade_type: "RAPIDA" o "SWING"
        cb_multiplier: Multiplicador del circuit breaker (1.0, 0.5, o 0.0)

    Returns:
        float: Risk percentage (e.g., 0.01 para 1%)
    """
    if price <= 0 or atr <= 0:
        return RISK_BASE_PCT * cb_multiplier

    vol_pct = (atr / price) * 100

    # Determinar risk base por volatilidad
    if vol_pct > VOL_HIGH_THRESHOLD or vix > 25:
        risk = RISK_MIN_PCT  # 0.5%
    elif vol_pct < VOL_LOW_THRESHOLD and vix < 20:
        risk = RISK_MAX_PCT  # 1.5%
    else:
        risk = RISK_BASE_PCT  # 1.0%

    # RAPIDA siempre tiene cap
    if trade_type == "RAPIDA":
        risk = min(risk, 0.0075)  # max 0.75% para operaciones rápidas

    # Aplicar multiplicador del circuit breaker
    risk *= cb_multiplier

    # Clamp final
    risk = max(0.0, min(risk, RISK_MAX_PCT))

    return round(risk, 4)


def get_risk_summary_html(atr: float, price: float, vix: float,
                          trade_type: str, cb_multiplier: float) -> str:
    """Genera resumen HTML del risk actual para Telegram."""
    risk = calculate_dynamic_risk(atr, price, vix, trade_type, cb_multiplier)
    vol_pct = (atr / price) * 100 if price > 0 else 0

    risk_label = "🟢 BAJO" if risk <= 0.005 else "🟡 MEDIO" if risk <= 0.01 else "🔴 ALTO"
    vol_label = "📉 Baja" if vol_pct < VOL_LOW_THRESHOLD else "📈 Alta" if vol_pct > VOL_HIGH_THRESHOLD else "↔️ Normal"

    return (
        f"📊 <b>RISK MANAGER</b>\n\n"
        f"• Risk actual: <b>{risk*100:.2f}%</b> por trade {risk_label}\n"
        f"• Volatilidad: {vol_pct:.2f}% {vol_label}\n"
        f"• VIX: {vix:.1f}\n"
        f"• Tipo operación: {trade_type}\n"
        f"• CB multiplicador: {cb_multiplier:.1f}x\n\n"
        f"💡 <i>Rango: {RISK_MIN_PCT*100:.1f}% - {RISK_MAX_PCT*100:.1f}%</i>"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. TRAILING STOP MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class TrailingStopManager:
    """
    Gestiona trailing stops dinámicos basados en ATR.

    Activación: Cuando el trade alcanza 1:1 R:R (precio avanza 1x la distancia SL)
    Trail: new_sl = max(current_sl, price - ATR * 2.5) para LONG
           new_sl = min(current_sl, price + ATR * 2.5) para SHORT
    """

    def __init__(self):
        # Tracking de cuáles trades ya activaron trailing
        self._activated = set()  # trade_ids que ya pasaron el umbral 1:1

    def calculate_trailing_updates(self, open_trades: list, prices: dict) -> list:
        """
        Calcula nuevos SL para trades que califican para trailing.

        Args:
            open_trades: Lista de trades abiertos del tracker
            prices: Dict con precios actuales y ATR

        Returns:
            list of dict: [{trade_id, symbol, old_sl, new_sl, reason}]
        """
        updates = []

        for t in open_trades:
            trade_id = t["id"]
            sym = t["symbol"]
            tipo = t["type"]
            entry = t["entry_price"]
            current_sl = t["sl_price"]
            status = t["status"]

            # Solo trailing en trades que ya pasaron TP1 (PARTIAL_WON) o están OPEN
            if status not in ("OPEN", "PARTIAL_WON"):
                continue

            curr_price = prices.get(sym, 0)
            atr = prices.get(f"{sym}_ATR", 0)
            if curr_price <= 0 or atr <= 0:
                continue

            sl_distance = abs(entry - current_sl)
            if sl_distance <= 0:
                continue

            # Verificar si el trade alcanzó 1:1 R:R (activación del trailing)
            if tipo == "LONG":
                current_rr = (curr_price - entry) / sl_distance if sl_distance else 0
            else:
                current_rr = (entry - curr_price) / sl_distance if sl_distance else 0

            if current_rr < TSL_ACTIVATION_RR:
                continue  # No ha alcanzado 1:1, no activar trailing

            # Marcar como activado
            if trade_id not in self._activated:
                self._activated.add(trade_id)
                print(f"📐 [TrailingStop] {sym} {tipo} #{trade_id}: "
                      f"Trailing activado (R:R {current_rr:.2f})")

            # Calcular nuevo SL
            trail_distance = atr * TSL_ATR_MULTIPLIER

            min_step = atr * TSL_MIN_STEP_ATR  # ej: ATR=4.71 → min_step=1.18

            if tipo == "LONG":
                proposed_sl = round(curr_price - trail_distance, 2)
                # Solo mover si mejora el SL Y el movimiento supera el umbral mínimo
                if proposed_sl > current_sl and (proposed_sl - current_sl) >= min_step:
                    updates.append({
                        "trade_id": trade_id,
                        "symbol": sym,
                        "side": tipo,
                        "old_sl": current_sl,
                        "new_sl": proposed_sl,
                        "current_price": curr_price,
                        "atr": atr,
                        "reason": f"Trailing LONG: SL {current_sl:.2f} → {proposed_sl:.2f} "
                                  f"(price: {curr_price:.2f}, ATR*{TSL_ATR_MULTIPLIER}: {trail_distance:.2f})"
                    })
            else:  # SHORT
                proposed_sl = round(curr_price + trail_distance, 2)
                # Solo mover si mejora el SL Y el movimiento supera el umbral mínimo
                if proposed_sl < current_sl and (current_sl - proposed_sl) >= min_step:
                    updates.append({
                        "trade_id": trade_id,
                        "symbol": sym,
                        "side": tipo,
                        "old_sl": current_sl,
                        "new_sl": proposed_sl,
                        "current_price": curr_price,
                        "atr": atr,
                        "reason": f"Trailing SHORT: SL {current_sl:.2f} → {proposed_sl:.2f} "
                                  f"(price: {curr_price:.2f}, ATR*{TSL_ATR_MULTIPLIER}: {trail_distance:.2f})"
                    })

        return updates

    def cleanup_closed(self, open_trade_ids: set):
        """Limpia tracking de trades que ya cerraron."""
        self._activated = self._activated.intersection(open_trade_ids)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. DYNAMIC LEVERAGE (Phase 5)
# ═══════════════════════════════════════════════════════════════════════════════

from config import (
    LEVERAGE_MIN, LEVERAGE_LOW, LEVERAGE_DEFAULT, LEVERAGE_MAX,
    MAX_CONCURRENT_POSITIONS, MAX_PORTFOLIO_EXPOSURE,
)


def calculate_leverage(vix: float = 0.0, atr_pct: float = 0.0,
                       regime: str = "TRENDING_UP",
                       trade_type: str = "SWING") -> int:
    """
    Calcula leverage dinamico basado en volatilidad y regimen de mercado.

    Logica:
      - VIX > 35 o regime VOLATILE:  2x (proteger capital)
      - VIX > 25 o trade RAPIDA:     3x (conservador)
      - Normal (default):             5x
      - Low vol (ATR < 1.5%) + TRENDING: 7x (aprovechar calma)

    Args:
        vix: Indice VIX actual
        atr_pct: ATR como % del precio (e.g., 2.5 = 2.5%)
        regime: Regimen de mercado ("TRENDING_UP", "TRENDING_DOWN", "VOLATILE", "RANGING")
        trade_type: "RAPIDA" o "SWING"

    Returns:
        int: Nivel de leverage (2, 3, 5, o 7)
    """
    # Caso extremo: volatilidad alta
    if vix > 35 or regime == "VOLATILE":
        return LEVERAGE_MIN  # 2x

    # Caso conservador
    if vix > 25 or trade_type == "RAPIDA":
        return LEVERAGE_LOW  # 3x

    # Caso optimista: baja volatilidad + tendencia clara
    if atr_pct < VOL_LOW_THRESHOLD and regime in ("TRENDING_UP", "TRENDING_DOWN"):
        return LEVERAGE_MAX  # 7x

    return LEVERAGE_DEFAULT  # 5x


def get_leverage_html(vix: float, atr_pct: float, regime: str,
                      trade_type: str) -> str:
    """Genera HTML informativo de leverage para Telegram."""
    lev = calculate_leverage(vix, atr_pct, regime, trade_type)
    emoji = {2: "🔴", 3: "🟡", 5: "🟢", 7: "🚀"}.get(lev, "⚪")

    return (
        f"⚙️ <b>DYNAMIC LEVERAGE</b>\n\n"
        f"{emoji} Leverage actual: <b>{lev}x</b>\n\n"
        f"📊 Inputs:\n"
        f"• VIX: {vix:.1f}\n"
        f"• ATR/Price: {atr_pct:.2f}%\n"
        f"• Regime: {regime}\n"
        f"• Tipo: {trade_type}\n\n"
        f"📐 Escala: {LEVERAGE_MIN}x (extreme) → {LEVERAGE_LOW}x → "
        f"{LEVERAGE_DEFAULT}x → {LEVERAGE_MAX}x (calm)"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. PORTFOLIO RISK MANAGER (Phase 5)
# ═══════════════════════════════════════════════════════════════════════════════

class PortfolioRisk:
    """
    Gestion de riesgo a nivel portafolio.

    Limites:
      - Max 3 posiciones simultaneas
      - Exposure total < 3x balance
      - Pre-trade check antes de abrir nueva posicion
    """

    def __init__(self, max_positions=MAX_CONCURRENT_POSITIONS,
                 max_exposure=MAX_PORTFOLIO_EXPOSURE):
        self.max_positions = max_positions
        self.max_exposure = max_exposure

    def get_total_exposure(self, open_trades: list, prices: dict) -> float:
        """
        Calcula exposure total del portafolio en USD.

        Args:
            open_trades: Lista de trades abiertos [{symbol, entry_price, amount, type, ...}]
            prices: Dict de precios actuales {symbol: price}

        Returns:
            float: Exposure total en USD (suma de notional values)
        """
        total = 0.0
        for t in open_trades:
            sym = t.get("symbol", "")
            amount = t.get("amount", 0)
            price = prices.get(sym, t.get("entry_price", 0))
            total += abs(amount * price)
        return round(total, 2)

    def can_open_position(self, open_trades: list, prices: dict,
                          balance: float) -> tuple:
        """
        Pre-trade check: verifica si se puede abrir una nueva posicion.

        Returns:
            (bool, str): (puede_abrir, razon)
        """
        # Check 1: max posiciones
        n_open = len(open_trades)
        if n_open >= self.max_positions:
            return (False,
                    f"Max posiciones alcanzado: {n_open}/{self.max_positions}")

        # Check 2: exposure
        if balance > 0:
            exposure = self.get_total_exposure(open_trades, prices)
            exposure_ratio = exposure / balance
            if exposure_ratio >= self.max_exposure:
                return (False,
                        f"Exposure excesivo: {exposure_ratio:.1f}x "
                        f"(max: {self.max_exposure}x)")

        return (True, "OK — portfolio risk check passed")

    def get_portfolio_html(self, open_trades: list, prices: dict,
                           balance: float) -> str:
        """Genera HTML de estado del portafolio para Telegram."""
        n_open = len(open_trades)
        exposure = self.get_total_exposure(open_trades, prices)
        exposure_ratio = exposure / balance if balance > 0 else 0

        can_open, reason = self.can_open_position(open_trades, prices, balance)
        status_emoji = "🟢" if can_open else "🔴"

        lines = [
            f"📋 <b>PORTFOLIO RISK</b>\n",
            f"• Posiciones abiertas: <b>{n_open}/{self.max_positions}</b>",
            f"• Exposure: <b>${exposure:,.2f}</b> ({exposure_ratio:.1f}x balance)",
            f"• Balance: ${balance:,.2f}",
            f"• Max exposure: {self.max_exposure}x",
            f"\n{status_emoji} Estado: {'Puede abrir' if can_open else 'Bloqueado'}",
            f"<i>{reason}</i>",
        ]

        if open_trades:
            lines.append(f"\n📊 <b>Posiciones:</b>")
            for t in open_trades:
                sym = t.get("symbol", "?")
                tipo = t.get("type", "?")
                entry = t.get("entry_price", 0)
                curr = prices.get(sym, entry)
                if tipo == "LONG":
                    pnl = (curr - entry) / entry * 100 if entry else 0
                else:
                    pnl = (entry - curr) / entry * 100 if entry else 0
                pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                lines.append(f"  {pnl_emoji} {sym} {tipo}: {pnl:+.2f}%")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. SINGLETON INSTANCES (importar desde otros módulos)
# ═══════════════════════════════════════════════════════════════════════════════

# Instancias globales — se crean al primer import
circuit_breaker = CircuitBreaker()
trailing_stop_mgr = TrailingStopManager()
portfolio_risk = PortfolioRisk()
