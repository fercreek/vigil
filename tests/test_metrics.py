"""
test_metrics.py — Tests para Phase 3: Metricas Avanzadas

Cubre: Sharpe, Sortino, Max Drawdown, SQN, Calmar, Profit Factor,
Win Rate, Avg R:R, Equity Curve Builder, Full Report.
"""

import os
import sys
import math
import pytest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SHARPE RATIO
# ═════════════════════════════════════════════════════════��═════════════════════

class TestSharpe:
    def test_positive_returns_positive_sharpe(self):
        from metrics import calculate_sharpe
        returns = [2.0, 1.5, 3.0, -1.0, 2.5]
        sharpe = calculate_sharpe(returns)
        assert sharpe > 0

    def test_negative_returns_negative_sharpe(self):
        from metrics import calculate_sharpe
        returns = [-2.0, -1.5, -3.0, -1.0, -2.5]
        sharpe = calculate_sharpe(returns)
        assert sharpe < 0

    def test_empty_returns_zero(self):
        from metrics import calculate_sharpe
        assert calculate_sharpe([]) == 0.0

    def test_single_return_zero(self):
        from metrics import calculate_sharpe
        assert calculate_sharpe([2.0]) == 0.0

    def test_all_same_returns_zero(self):
        from metrics import calculate_sharpe
        # Std = 0 → Sharpe = 0
        assert calculate_sharpe([1.0, 1.0, 1.0, 1.0]) == 0.0


# ════���══════════════════════════════════════════════════════════════════════════
# 2. SORTINO RATIO
# ═��═══════════���═══════════════════════════════════���═════════════════════════════

class TestSortino:
    def test_no_downside_returns_inf(self):
        from metrics import calculate_sortino
        returns = [2.0, 1.5, 3.0, 0.5]
        sortino = calculate_sortino(returns)
        assert sortino == float('inf')

    def test_mixed_returns_positive(self):
        from metrics import calculate_sortino
        returns = [2.0, -1.0, 3.0, -0.5, 2.5]
        sortino = calculate_sortino(returns)
        assert sortino > 0

    def test_empty_returns_zero(self):
        from metrics import calculate_sortino
        assert calculate_sortino([]) == 0.0

    def test_sortino_higher_than_sharpe_for_skewed(self):
        """Sortino should be >= Sharpe for positively skewed returns."""
        from metrics import calculate_sharpe, calculate_sortino
        returns = [5.0, 3.0, 2.0, -0.5, 4.0, -0.3, 3.5]
        sharpe = calculate_sharpe(returns)
        sortino = calculate_sortino(returns)
        assert sortino >= sharpe


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MAX DRAWDOWN
# ════════════════════════════════════════════��══════════════════════════════════

class TestMaxDrawdown:
    def test_simple_drawdown(self):
        from metrics import calculate_max_drawdown
        equity = [1000, 1100, 1050, 900, 950, 1200]
        dd = calculate_max_drawdown(equity)
        # Peak at 1100, trough at 900 → -18.18%
        assert dd < 0
        assert abs(dd - (-18.18)) < 0.1

    def test_monotonic_up_no_drawdown(self):
        from metrics import calculate_max_drawdown
        equity = [1000, 1010, 1020, 1030, 1040]
        dd = calculate_max_drawdown(equity)
        assert dd == 0.0

    def test_monotonic_down_full_drawdown(self):
        from metrics import calculate_max_drawdown
        equity = [1000, 900, 800, 700]
        dd = calculate_max_drawdown(equity)
        assert dd == -30.0

    def test_empty_curve(self):
        from metrics import calculate_max_drawdown
        assert calculate_max_drawdown([]) == 0.0

    def test_single_value(self):
        from metrics import calculate_max_drawdown
        assert calculate_max_drawdown([1000]) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SQN (System Quality Number)
# ═════════���═════════════════════════════════════════════════════════════════════

class TestSQN:
    def test_excellent_system(self):
        from metrics import calculate_sqn
        # 20 trades con retorno medio alto y baja dispersión
        returns = [2.0] * 15 + [-1.0] * 5
        sqn = calculate_sqn(returns)
        assert sqn > 2.0  # At least "average"

    def test_poor_system(self):
        from metrics import calculate_sqn
        returns = [1.0, -1.0, 0.5, -0.5, 0.2, -0.8]
        sqn = calculate_sqn(returns)
        assert sqn < 2.0

    def test_empty_returns_zero(self):
        from metrics import calculate_sqn
        assert calculate_sqn([]) == 0.0

    def test_sqn_label(self):
        from metrics import get_sqn_label
        assert get_sqn_label(7.5) == "Santo Grial"
        assert get_sqn_label(5.5) == "Superb"
        assert get_sqn_label(3.5) == "Excelente"
        assert get_sqn_label(2.7) == "Bueno"
        assert get_sqn_label(2.2) == "Promedio"
        assert get_sqn_label(1.7) == "Debajo del promedio"
        assert get_sqn_label(1.0) == "Pobre"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CALMAR RATIO
# ══════════════════════════════════════════════════════════════════��════════════

class TestCalmar:
    def test_positive_calmar(self):
        from metrics import calculate_calmar
        returns = [2.0, 1.5, -1.0, 3.0, -0.5]
        calmar = calculate_calmar(returns, max_dd=-5.0)
        assert calmar > 0

    def test_zero_drawdown_returns_zero(self):
        from metrics import calculate_calmar
        assert calculate_calmar([1.0, 2.0], max_dd=0) == 0.0

    def test_empty_returns_zero(self):
        from metrics import calculate_calmar
        assert calculate_calmar([], max_dd=-5.0) == 0.0


# ════════════════════════════════════════════════════════��══════════════════════
# 6. PROFIT FACTOR
# ═══════════════════════════════════════════════════════════════════════════════

class TestProfitFactor:
    def test_profitable_system(self):
        from metrics import calculate_profit_factor
        returns = [3.0, 2.0, -1.0, -0.5]
        pf = calculate_profit_factor(returns)
        # gains=5.0, losses=1.5 → PF=3.33
        assert abs(pf - 3.33) < 0.01

    def test_no_losses_returns_inf(self):
        from metrics import calculate_profit_factor
        pf = calculate_profit_factor([2.0, 1.0, 3.0])
        assert pf == float('inf')

    def test_no_gains_returns_zero(self):
        from metrics import calculate_profit_factor
        pf = calculate_profit_factor([-2.0, -1.0])
        assert pf == 0.0

    def test_empty_returns_zero(self):
        from metrics import calculate_profit_factor
        assert calculate_profit_factor([]) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 7. WIN RATE & AVG R:R
# ════════════════════════════��════════════════════════════════���═════════════════

class TestWinRateAndRR:
    def test_win_rate_calculation(self):
        from metrics import calculate_win_rate
        returns = [2.0, -1.0, 3.0, -0.5, 1.5]
        wr = calculate_win_rate(returns)
        assert wr == 60.0  # 3/5 = 60%

    def test_win_rate_all_wins(self):
        from metrics import calculate_win_rate
        assert calculate_win_rate([1.0, 2.0, 3.0]) == 100.0

    def test_avg_rr(self):
        from metrics import calculate_avg_rr
        returns = [3.0, 2.0, -1.0, -1.0]
        rr = calculate_avg_rr(returns)
        # avg win = 2.5, avg loss = 1.0 → R:R = 2.5
        assert rr == 2.5

    def test_avg_rr_empty(self):
        from metrics import calculate_avg_rr
        assert calculate_avg_rr([]) == 0.0


# ═════════════════════════════════════════════════════════════════════════��═════
# 8. EQUITY CURVE & FULL REPORT
# ═���══════════════════════════════════════��═══════════════════════��══════════════

class TestEquityCurve:
    def test_equity_grows_with_wins(self):
        from metrics import build_equity_curve
        trades = [
            {"pnl_pct": 2.0, "id": 1},
            {"pnl_pct": 3.0, "id": 2},
        ]
        curve = build_equity_curve(trades, starting_balance=1000)
        assert len(curve) == 3  # start + 2 trades
        assert curve[-1]["balance"] > 1000

    def test_equity_shrinks_with_losses(self):
        from metrics import build_equity_curve
        trades = [
            {"pnl_pct": -5.0, "id": 1},
            {"pnl_pct": -3.0, "id": 2},
        ]
        curve = build_equity_curve(trades, starting_balance=1000)
        assert curve[-1]["balance"] < 1000

    def test_full_report_structure(self):
        from metrics import generate_full_report
        trades = [
            {"pnl_pct": 2.0, "id": 1},
            {"pnl_pct": -1.0, "id": 2},
            {"pnl_pct": 3.0, "id": 3},
        ]
        report = generate_full_report(trades)
        assert "total_trades" in report
        assert "sharpe" in report
        assert "sortino" in report
        assert "max_drawdown" in report
        assert "sqn" in report
        assert "calmar" in report
        assert "profit_factor" in report
        assert "equity_curve" in report
        assert report["total_trades"] == 3
        assert report["win_rate"] > 0

    def test_full_report_empty_trades(self):
        from metrics import generate_full_report
        report = generate_full_report([])
        assert report["total_trades"] == 0
        assert report["sharpe"] == 0.0


class TestMetricsHTML:
    def test_html_has_all_metrics(self):
        from metrics import get_metrics_html
        trades = [
            {"pnl_pct": 2.0, "id": 1},
            {"pnl_pct": -1.0, "id": 2},
            {"pnl_pct": 3.0, "id": 3},
        ]
        html = get_metrics_html(trades)
        assert "ZENITH PERFORMANCE METRICS" in html
        assert "Sharpe" in html
        assert "Sortino" in html
        assert "Max Drawdown" in html
        assert "SQN" in html
        assert "Profit Factor" in html

    def test_html_empty_trades(self):
        from metrics import get_metrics_html
        html = get_metrics_html([])
        assert "Sin trades cerrados" in html
