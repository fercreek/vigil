"""
metrics.py — Phase 3: Metricas Avanzadas de Trading

Calcula metricas institucionales sobre la base de trades cerrados:
Sharpe, Sortino, Max Drawdown, SQN, Calmar, Profit Factor.

Todas las funciones operan sobre listas de PnL% o equity curves,
sin dependencia de APIs externas.
"""

import math
import numpy as np
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CORE METRICS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_sharpe(returns, risk_free=0.0, periods_per_year=365):
    """
    Sharpe Ratio = (mean_return - risk_free) / std_return * sqrt(N)

    returns: lista de retornos porcentuales por trade (ej: [2.1, -1.0, 3.5])
    risk_free: tasa libre de riesgo anualizada (default 0%)
    periods_per_year: trades estimados por ano (para anualizar)

    SaintQuant benchmark: 1.8
    """
    if not returns or len(returns) < 2:
        return 0.0
    arr = np.array(returns, dtype=float)
    mean_r = arr.mean()
    std_r = arr.std(ddof=1)
    if std_r == 0:
        return 0.0
    rf_per_trade = risk_free / periods_per_year if periods_per_year > 0 else 0.0
    return float((mean_r - rf_per_trade) / std_r * math.sqrt(min(len(returns), periods_per_year)))


def calculate_sortino(returns, risk_free=0.0, periods_per_year=365):
    """
    Sortino Ratio = (mean_return - risk_free) / downside_std * sqrt(N)

    Solo penaliza volatilidad negativa (mas justo para estrategias asimetricas).
    """
    if not returns or len(returns) < 2:
        return 0.0
    arr = np.array(returns, dtype=float)
    mean_r = arr.mean()
    downside = arr[arr < 0]
    if len(downside) < 1:
        return float('inf') if mean_r > 0 else 0.0
    downside_std = downside.std(ddof=1)
    if downside_std == 0:
        return float('inf') if mean_r > 0 else 0.0
    rf_per_trade = risk_free / periods_per_year if periods_per_year > 0 else 0.0
    return float((mean_r - rf_per_trade) / downside_std * math.sqrt(min(len(returns), periods_per_year)))


def calculate_max_drawdown(equity_curve):
    """
    Max Drawdown = max peak-to-trough decline en la equity curve.

    equity_curve: lista de valores de equity (ej: [1000, 1020, 980, 1050])
    Retorna porcentaje negativo (ej: -3.92)

    SaintQuant benchmark: -11%
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    arr = np.array(equity_curve, dtype=float)
    peak = arr[0]
    max_dd = 0.0
    for val in arr:
        if val > peak:
            peak = val
        dd = (val - peak) / peak * 100 if peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd
    return float(round(max_dd, 2))


def calculate_sqn(returns):
    """
    System Quality Number (Van Tharp) = mean(R) / std(R) * sqrt(N)

    Clasificacion:
    < 1.6: Pobre
    1.6-1.9: Debajo del promedio
    2.0-2.4: Promedio
    2.5-2.9: Bueno
    3.0-5.0: Excelente
    5.0-6.9: Superb
    >= 7.0: Santo Grial
    """
    if not returns or len(returns) < 2:
        return 0.0
    arr = np.array(returns, dtype=float)
    std_r = arr.std(ddof=1)
    if std_r == 0:
        return 0.0
    return float(arr.mean() / std_r * math.sqrt(len(arr)))


def calculate_calmar(returns, max_dd, periods_per_year=365):
    """
    Calmar Ratio = retorno_anualizado / |max_drawdown|

    returns: lista de retornos porcentuales por trade
    max_dd: max drawdown en porcentaje (valor negativo)
    """
    if not returns or max_dd == 0:
        return 0.0
    total_return = sum(returns)
    n_trades = len(returns)
    annualized = total_return * (periods_per_year / n_trades) if n_trades > 0 else 0.0
    return float(round(annualized / abs(max_dd), 2)) if max_dd != 0 else 0.0


def calculate_profit_factor(returns):
    """
    Profit Factor = sum(ganancias) / |sum(perdidas)|

    PF > 1.5 = bueno, PF > 2.0 = excelente
    """
    if not returns:
        return 0.0
    arr = np.array(returns, dtype=float)
    gains = arr[arr > 0].sum()
    losses = abs(arr[arr < 0].sum())
    if losses == 0:
        return float('inf') if gains > 0 else 0.0
    return float(round(gains / losses, 2))


def calculate_win_rate(returns):
    """Win rate como porcentaje."""
    if not returns:
        return 0.0
    wins = sum(1 for r in returns if r > 0)
    return round(wins / len(returns) * 100, 1)


def calculate_avg_rr(returns):
    """Promedio Risk:Reward efectivo."""
    if not returns:
        return 0.0
    arr = np.array(returns, dtype=float)
    avg_win = arr[arr > 0].mean() if len(arr[arr > 0]) > 0 else 0.0
    avg_loss = abs(arr[arr < 0].mean()) if len(arr[arr < 0]) > 0 else 1.0
    if avg_loss == 0:
        return 0.0
    return round(float(avg_win / avg_loss), 2)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. EQUITY CURVE BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_equity_curve(trades, starting_balance=1000.0):
    """
    Construye equity curve a partir de trades cerrados.

    trades: lista de dicts con campos 'pnl_pct' y opcionalmente 'close_time'
    Retorna: lista de dicts [{"balance": float, "time": str, "trade_id": int}]
    """
    curve = [{"balance": starting_balance, "time": "start", "trade_id": 0}]
    balance = starting_balance

    for t in trades:
        pnl_pct = t.get("pnl_pct", 0.0)
        balance = balance * (1 + pnl_pct / 100)
        curve.append({
            "balance": round(balance, 2),
            "time": t.get("close_time", ""),
            "trade_id": t.get("id", 0),
        })

    return curve


# ═══════════════════════════════════════════════════════════════════════════════
# 3. COMPREHENSIVE REPORT
# ═════���═════════════════════════════════════════════════════════════════════════

def generate_full_report(trades, starting_balance=1000.0):
    """
    Genera reporte completo de metricas a partir de trades cerrados.

    trades: lista de dicts de tracker.get_recent_outcomes() con 'pnl_pct'
    Retorna dict con todas las metricas.
    """
    if not trades:
        return {
            "total_trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
            "sharpe": 0.0, "sortino": 0.0, "max_drawdown": 0.0,
            "sqn": 0.0, "calmar": 0.0, "avg_rr": 0.0,
            "total_return_pct": 0.0, "equity_curve": [],
        }

    returns = [t.get("pnl_pct", 0.0) for t in trades]
    equity_curve = build_equity_curve(trades, starting_balance)
    equity_values = [e["balance"] for e in equity_curve]
    max_dd = calculate_max_drawdown(equity_values)

    return {
        "total_trades": len(trades),
        "win_rate": calculate_win_rate(returns),
        "profit_factor": calculate_profit_factor(returns),
        "sharpe": round(calculate_sharpe(returns), 2),
        "sortino": round(calculate_sortino(returns), 2),
        "max_drawdown": max_dd,
        "sqn": round(calculate_sqn(returns), 2),
        "calmar": calculate_calmar(returns, max_dd),
        "avg_rr": calculate_avg_rr(returns),
        "total_return_pct": round(sum(returns), 2),
        "equity_curve": equity_curve,
    }


def get_sqn_label(sqn):
    """Clasificacion textual del SQN."""
    if sqn >= 7.0: return "Santo Grial"
    if sqn >= 5.0: return "Superb"
    if sqn >= 3.0: return "Excelente"
    if sqn >= 2.5: return "Bueno"
    if sqn >= 2.0: return "Promedio"
    if sqn >= 1.6: return "Debajo del promedio"
    return "Pobre"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TELEGRAM HTML
# ═══════════��═══════════════════════════════════════════════════════════════════

def get_metrics_html(trades, starting_balance=1000.0):
    """HTML formateado de metricas para Telegram /metrics."""
    report = generate_full_report(trades, starting_balance)

    if report["total_trades"] == 0:
        return "📊 <b>METRICS</b>\n\n<i>Sin trades cerrados para analizar.</i>"

    sqn_label = get_sqn_label(report["sqn"])

    lines = [
        "📊 <b>ZENITH PERFORMANCE METRICS</b>\n",
        f"📈 Trades: <b>{report['total_trades']}</b>",
        f"🎯 Win Rate: <b>{report['win_rate']}%</b>",
        f"💰 Profit Factor: <b>{report['profit_factor']}</b>",
        f"📐 Avg R:R: <b>{report['avg_rr']}:1</b>",
        f"💵 Retorno Total: <b>{report['total_return_pct']:+.2f}%</b>\n",
        "<b>Risk Metrics:</b>",
        f"📉 Max Drawdown: <b>{report['max_drawdown']:.2f}%</b>",
        f"📊 Sharpe Ratio: <b>{report['sharpe']}</b>",
        f"📊 Sortino Ratio: <b>{report['sortino']}</b>",
        f"🏆 SQN: <b>{report['sqn']}</b> ({sqn_label})",
        f"⚖️ Calmar Ratio: <b>{report['calmar']}</b>",
    ]

    return "\n".join(lines)
