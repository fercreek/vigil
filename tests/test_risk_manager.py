"""
test_risk_manager.py — Tests para Circuit Breaker, Dynamic Risk, Trailing Stop
"""

import os
import sys
import json
import pytest

# Asegurar imports desde raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CIRCUIT BREAKER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCircuitBreaker:
    """Tests para el sistema de circuit breaker."""

    def _make_cb(self, tmp_path):
        """Crea un CB limpio con state file en tmp."""
        import risk_manager
        # Parchear archivo de estado para aislamiento
        risk_manager._STATE_FILE = str(tmp_path / "risk_state.json")
        cb = risk_manager.CircuitBreaker()
        cb.force_reset()
        return cb

    def test_initial_state_is_normal(self, tmp_path):
        cb = self._make_cb(tmp_path)
        assert cb.state == "NORMAL"
        can, reason, mult = cb.can_trade()
        assert can is True
        assert mult == 1.0

    def test_one_loss_stays_normal(self, tmp_path):
        cb = self._make_cb(tmp_path)
        cb.record_outcome(is_win=False, pnl_pct=-1.0)
        assert cb.state == "NORMAL"
        assert cb.consecutive_losses == 1

    def test_two_losses_go_cautious(self, tmp_path):
        cb = self._make_cb(tmp_path)
        cb.record_outcome(is_win=False, pnl_pct=-1.0)
        cb.record_outcome(is_win=False, pnl_pct=-1.0)
        assert cb.state == "CAUTIOUS"
        can, reason, mult = cb.can_trade()
        assert can is True
        assert mult == 0.5

    def test_three_losses_go_halted(self, tmp_path):
        cb = self._make_cb(tmp_path)
        for _ in range(3):
            cb.record_outcome(is_win=False, pnl_pct=-1.0)
        assert cb.state == "HALTED"
        can, reason, mult = cb.can_trade()
        assert can is False
        assert mult == 0.0

    def test_win_after_cautious_resets_to_normal(self, tmp_path):
        cb = self._make_cb(tmp_path)
        cb.record_outcome(is_win=False, pnl_pct=-1.0)
        cb.record_outcome(is_win=False, pnl_pct=-1.0)
        assert cb.state == "CAUTIOUS"
        cb.record_outcome(is_win=True, pnl_pct=2.0)
        assert cb.state == "NORMAL"
        assert cb.consecutive_losses == 0

    def test_drawdown_triggers_halt(self, tmp_path):
        cb = self._make_cb(tmp_path)
        # Simular ganancia seguida de pérdida grande
        cb.record_outcome(is_win=True, pnl_pct=2.0)
        cb.record_outcome(is_win=False, pnl_pct=-7.0)  # DD > 5%
        assert cb.state == "HALTED"

    def test_force_reset(self, tmp_path):
        cb = self._make_cb(tmp_path)
        for _ in range(3):
            cb.record_outcome(is_win=False, pnl_pct=-1.0)
        assert cb.state == "HALTED"
        cb.force_reset()
        assert cb.state == "NORMAL"
        assert cb.consecutive_losses == 0

    def test_state_persists_to_file(self, tmp_path):
        import risk_manager
        risk_manager._STATE_FILE = str(tmp_path / "risk_state.json")
        cb1 = risk_manager.CircuitBreaker()
        cb1.force_reset()
        cb1.record_outcome(is_win=False, pnl_pct=-1.0)
        cb1.record_outcome(is_win=False, pnl_pct=-1.0)

        # Crear nueva instancia que carga del archivo
        cb2 = risk_manager.CircuitBreaker()
        assert cb2.consecutive_losses == 2
        assert cb2.state == "CAUTIOUS"

    def test_trades_counter(self, tmp_path):
        cb = self._make_cb(tmp_path)
        cb.record_outcome(is_win=True, pnl_pct=1.0)
        cb.record_outcome(is_win=False, pnl_pct=-1.0)
        cb.record_outcome(is_win=True, pnl_pct=2.0)
        assert cb.trades_today == 3
        assert cb.wins_today == 2
        assert cb.losses_today == 1

    def test_html_status_contains_state(self, tmp_path):
        cb = self._make_cb(tmp_path)
        html = cb.get_status_html()
        assert "NORMAL" in html
        assert "CIRCUIT BREAKER" in html


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DYNAMIC RISK SIZING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDynamicRisk:
    """Tests para el position sizing dinámico."""

    def test_high_volatility_reduces_risk(self):
        from risk_manager import calculate_dynamic_risk
        # ATR/price = 4% (>3% threshold)
        risk = calculate_dynamic_risk(atr=40, price=1000, vix=15)
        assert risk == 0.005  # 0.5%

    def test_low_volatility_increases_risk(self):
        from risk_manager import calculate_dynamic_risk
        # ATR/price = 1% (<1.5% threshold) y VIX < 20
        risk = calculate_dynamic_risk(atr=10, price=1000, vix=15)
        assert risk == 0.015  # 1.5%

    def test_normal_volatility_base_risk(self):
        from risk_manager import calculate_dynamic_risk
        # ATR/price = 2% (between thresholds)
        risk = calculate_dynamic_risk(atr=20, price=1000, vix=22)
        assert risk == 0.01  # 1.0%

    def test_high_vix_reduces_risk(self):
        from risk_manager import calculate_dynamic_risk
        risk = calculate_dynamic_risk(atr=20, price=1000, vix=30)
        assert risk == 0.005  # VIX > 25 → 0.5%

    def test_rapida_caps_risk(self):
        from risk_manager import calculate_dynamic_risk
        # Low vol would give 1.5%, but RAPIDA caps at 0.75%
        risk = calculate_dynamic_risk(atr=10, price=1000, vix=15, trade_type="RAPIDA")
        assert risk == 0.0075

    def test_cb_multiplier_halves_risk(self):
        from risk_manager import calculate_dynamic_risk
        risk_normal = calculate_dynamic_risk(atr=20, price=1000, vix=22, cb_multiplier=1.0)
        risk_cautious = calculate_dynamic_risk(atr=20, price=1000, vix=22, cb_multiplier=0.5)
        assert risk_cautious == risk_normal * 0.5

    def test_zero_price_returns_base(self):
        from risk_manager import calculate_dynamic_risk
        risk = calculate_dynamic_risk(atr=0, price=0, vix=20)
        assert risk == 0.01  # Base risk

    def test_risk_never_negative(self):
        from risk_manager import calculate_dynamic_risk
        risk = calculate_dynamic_risk(atr=20, price=1000, vix=30, cb_multiplier=0.0)
        assert risk >= 0.0

    def test_risk_summary_html(self):
        from risk_manager import get_risk_summary_html
        html = get_risk_summary_html(atr=20, price=1000, vix=22,
                                      trade_type="SWING", cb_multiplier=1.0)
        assert "RISK MANAGER" in html
        assert "%" in html


# ═══════════════════════════════════════════════════════════════════════════════
# 3. TRAILING STOP TESTS
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# 2b. DYNAMIC LEVERAGE TESTS (Phase 5)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDynamicLeverage:
    """Tests para leverage dinamico."""

    def test_extreme_vix_gives_2x(self):
        from risk_manager import calculate_leverage
        assert calculate_leverage(vix=40, atr_pct=2.0) == 2

    def test_volatile_regime_gives_2x(self):
        from risk_manager import calculate_leverage
        assert calculate_leverage(vix=15, atr_pct=2.0, regime="VOLATILE") == 2

    def test_high_vix_gives_3x(self):
        from risk_manager import calculate_leverage
        assert calculate_leverage(vix=28, atr_pct=2.0) == 3

    def test_rapida_gives_3x(self):
        from risk_manager import calculate_leverage
        assert calculate_leverage(vix=15, atr_pct=2.0, trade_type="RAPIDA") == 3

    def test_normal_gives_5x(self):
        from risk_manager import calculate_leverage
        assert calculate_leverage(vix=18, atr_pct=2.0, regime="TRENDING_UP") == 5

    def test_low_vol_trending_gives_7x(self):
        from risk_manager import calculate_leverage
        assert calculate_leverage(vix=15, atr_pct=1.0, regime="TRENDING_UP") == 7

    def test_low_vol_trending_down_gives_7x(self):
        from risk_manager import calculate_leverage
        assert calculate_leverage(vix=15, atr_pct=1.0, regime="TRENDING_DOWN") == 7

    def test_low_vol_ranging_gives_5x(self):
        """RANGING no califica para max leverage aunque vol sea baja."""
        from risk_manager import calculate_leverage
        assert calculate_leverage(vix=15, atr_pct=1.0, regime="RANGING") == 5

    def test_leverage_html_output(self):
        from risk_manager import get_leverage_html
        html = get_leverage_html(vix=20, atr_pct=2.0, regime="TRENDING_UP",
                                 trade_type="SWING")
        assert "DYNAMIC LEVERAGE" in html
        assert "5x" in html


# ═══════════════════════════════════════════════════════════════════════════════
# 2c. PORTFOLIO RISK TESTS (Phase 5)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPortfolioRisk:
    """Tests para gestion de riesgo de portafolio."""

    def _make_pr(self):
        from risk_manager import PortfolioRisk
        return PortfolioRisk(max_positions=3, max_exposure=3.0)

    def test_empty_portfolio_can_open(self):
        pr = self._make_pr()
        can, reason = pr.can_open_position([], {}, balance=1000)
        assert can is True

    def test_max_positions_blocks(self):
        pr = self._make_pr()
        trades = [
            {"symbol": "TAO", "entry_price": 300, "amount": 1, "type": "LONG"},
            {"symbol": "ZEC", "entry_price": 50, "amount": 5, "type": "LONG"},
            {"symbol": "ETH", "entry_price": 3000, "amount": 0.1, "type": "SHORT"},
        ]
        can, reason = pr.can_open_position(trades, {}, balance=1000)
        assert can is False
        assert "Max posiciones" in reason

    def test_excess_exposure_blocks(self):
        pr = self._make_pr()
        # 2 trades con exposure total > 3x balance
        trades = [
            {"symbol": "TAO", "entry_price": 300, "amount": 10, "type": "LONG"},
            # 300 * 10 = 3000, balance=1000, ratio=3.0 → >= max
        ]
        can, reason = pr.can_open_position(trades, {"TAO": 300}, balance=1000)
        assert can is False
        assert "Exposure" in reason

    def test_moderate_exposure_allows(self):
        pr = self._make_pr()
        trades = [
            {"symbol": "TAO", "entry_price": 300, "amount": 1, "type": "LONG"},
        ]
        can, reason = pr.can_open_position(trades, {"TAO": 300}, balance=1000)
        assert can is True

    def test_exposure_calculation(self):
        pr = self._make_pr()
        trades = [
            {"symbol": "TAO", "entry_price": 300, "amount": 2, "type": "LONG"},
            {"symbol": "ZEC", "entry_price": 50, "amount": 10, "type": "SHORT"},
        ]
        # TAO: 2*300=600, ZEC: 10*50=500 → total = 1100
        exposure = pr.get_total_exposure(trades, {"TAO": 300, "ZEC": 50})
        assert exposure == 1100.0

    def test_exposure_uses_current_price(self):
        """Usa precio actual en vez de entry si disponible."""
        pr = self._make_pr()
        trades = [
            {"symbol": "TAO", "entry_price": 300, "amount": 1, "type": "LONG"},
        ]
        # Precio actual 350 (subio)
        exposure = pr.get_total_exposure(trades, {"TAO": 350})
        assert exposure == 350.0

    def test_portfolio_html_output(self):
        pr = self._make_pr()
        trades = [
            {"symbol": "TAO", "entry_price": 300, "amount": 1, "type": "LONG"},
        ]
        html = pr.get_portfolio_html(trades, {"TAO": 310}, balance=1000)
        assert "PORTFOLIO RISK" in html
        assert "1/3" in html
        assert "TAO" in html

    def test_portfolio_html_empty(self):
        pr = self._make_pr()
        html = pr.get_portfolio_html([], {}, balance=1000)
        assert "PORTFOLIO RISK" in html
        assert "0/3" in html

    def test_zero_balance_no_crash(self):
        pr = self._make_pr()
        can, reason = pr.can_open_position([], {}, balance=0)
        assert can is True  # No exposure check si balance=0


# ═══════════════════════════════════════════════════════════════════════════════
# 3. TRAILING STOP TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrailingStop:
    """Tests para el trailing stop manager."""

    def _make_tsl(self):
        from risk_manager import TrailingStopManager
        return TrailingStopManager()

    def _make_trade(self, trade_id=1, sym="TAO", tipo="LONG",
                     entry=300, sl=290, tp1=310, tp2=320, status="OPEN"):
        return {
            "id": trade_id, "symbol": sym, "type": tipo,
            "entry_price": entry, "sl_price": sl,
            "tp1_price": tp1, "tp2_price": tp2, "status": status,
        }

    def test_no_update_before_1rr(self):
        tsl = self._make_tsl()
        trade = self._make_trade(entry=300, sl=290)  # SL dist = 10
        prices = {"TAO": 305, "TAO_ATR": 5}  # R:R = 0.5 (< 1.0)
        updates = tsl.calculate_trailing_updates([trade], prices)
        assert len(updates) == 0

    def test_update_after_1rr_long(self):
        tsl = self._make_tsl()
        trade = self._make_trade(entry=300, sl=290)  # SL dist = 10
        prices = {"TAO": 315, "TAO_ATR": 5}  # R:R = 1.5, new SL = 315 - 12.5 = 302.5
        updates = tsl.calculate_trailing_updates([trade], prices)
        assert len(updates) == 1
        assert updates[0]["new_sl"] > trade["sl_price"]
        assert updates[0]["new_sl"] == 302.5

    def test_no_update_if_new_sl_lower_than_current(self):
        tsl = self._make_tsl()
        # SL ya movido a 305 (BE), price at 312 with ATR 5 → proposed SL = 299.5 < 305
        trade = self._make_trade(entry=300, sl=305)
        prices = {"TAO": 312, "TAO_ATR": 5}  # proposed SL = 312 - 12.5 = 299.5
        updates = tsl.calculate_trailing_updates([trade], prices)
        assert len(updates) == 0  # 299.5 < 305, no update

    def test_update_short_trailing(self):
        tsl = self._make_tsl()
        trade = self._make_trade(tipo="SHORT", entry=300, sl=310)  # SL dist = 10
        prices = {"TAO": 285, "TAO_ATR": 5}  # R:R = 1.5, new SL = 285 + 12.5 = 297.5
        updates = tsl.calculate_trailing_updates([trade], prices)
        assert len(updates) == 1
        assert updates[0]["new_sl"] < trade["sl_price"]
        assert updates[0]["new_sl"] == 297.5

    def test_partial_won_also_trails(self):
        tsl = self._make_tsl()
        trade = self._make_trade(entry=300, sl=295, status="PARTIAL_WON")
        prices = {"TAO": 320, "TAO_ATR": 5}  # R:R = 5, new SL = 320 - 12.5 = 307.5
        updates = tsl.calculate_trailing_updates([trade], prices)
        assert len(updates) == 1
        assert updates[0]["new_sl"] == 307.5

    def test_cleanup_removes_closed_trades(self):
        tsl = self._make_tsl()
        tsl._activated = {1, 2, 3}
        tsl.cleanup_closed({1, 3})
        assert tsl._activated == {1, 3}

    def test_multiple_trades_independent(self):
        tsl = self._make_tsl()
        trade1 = self._make_trade(trade_id=1, entry=300, sl=290)
        trade2 = self._make_trade(trade_id=2, sym="ZEC", entry=50, sl=48)
        prices = {
            "TAO": 315, "TAO_ATR": 5,    # R:R 1.5, update
            "ZEC": 51, "ZEC_ATR": 1,      # R:R 0.5, no update
        }
        updates = tsl.calculate_trailing_updates([trade1, trade2], prices)
        assert len(updates) == 1
        assert updates[0]["symbol"] == "TAO"
