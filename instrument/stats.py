"""Portfolio statistics, ported into the package so it owes the legacy bot nothing.

These three came from the old repo's `metrics.py` (lines 63, 123, 163). They are
copied rather than imported on purpose: the legacy bot is going to be archived, and
an instrument that stops reporting the day that happens is not self-contained.

What did NOT come across, deliberately: Sharpe, Sortino, Calmar and SQN. With fewer
than ~100 resolved signals they are noise wearing a lab coat, and the original
`metrics.py:39` "annualises" with sqrt(len(returns)), which annualises nothing.

numpy is dropped too -- these are three loops over a list.
"""
from __future__ import annotations

from typing import Any, Sequence


def calculate_max_drawdown(equity_curve: Sequence[float]) -> float:
    """Largest peak-to-trough decline, as a negative percentage."""
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    peak = float(equity_curve[0])
    max_drawdown = 0.0
    for value in equity_curve:
        value = float(value)
        if value > peak:
            peak = value
        drawdown = (value - peak) / peak * 100 if peak > 0 else 0.0
        max_drawdown = min(max_drawdown, drawdown)
    return round(max_drawdown, 2)


def calculate_profit_factor(returns: Sequence[float]) -> float:
    """Gross wins over gross losses. Infinite when nothing lost, 0.0 when nothing won."""
    if not returns:
        return 0.0
    gains = sum(r for r in returns if r > 0)
    losses = abs(sum(r for r in returns if r < 0))
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return round(gains / losses, 2)


def build_equity_curve(trades: Sequence[dict[str, Any]],
                       starting_balance: float = 1000.0) -> list[dict[str, Any]]:
    """Compound a starting balance through closed trades.

    Each trade contributes `pnl_pct`. Callers working in R units convert first --
    the risk-per-trade assumption belongs to the caller, not buried in here.
    """
    balance = starting_balance
    curve = [{"balance": starting_balance, "time": "start", "trade_id": 0}]
    for trade in trades:
        balance *= 1 + trade.get("pnl_pct", 0.0) / 100
        curve.append({
            "balance": round(balance, 2),
            "time": trade.get("close_time", ""),
            "trade_id": trade.get("id", 0),
        })
    return curve
