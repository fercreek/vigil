"""
conftest.py — Datos sintéticos reutilizables para todos los tests.
Sin red. Sin Binance. Sin Gemini. Sin Telegram.
"""
import pandas as pd
import numpy as np
import pytest


def make_ohlcv(n: int = 300, base_price: float = 300.0, trend: str = "UP") -> pd.DataFrame:
    """
    Genera un DataFrame OHLCV sintético realista.

    trend="UP"   → precio sube gradualmente (escenario BULL)
    trend="DOWN" → precio baja gradualmente (escenario BEAR)
    trend="FLAT" → precio lateral (escenario NEUTRAL)
    """
    rng = np.random.default_rng(seed=42)
    prices = [base_price]
    for _ in range(n - 1):
        drift = {"UP": 0.003, "DOWN": -0.003, "FLAT": 0.0}[trend]
        noise = rng.normal(0, 0.015)
        prices.append(max(1.0, prices[-1] * (1 + drift + noise)))

    prices = np.array(prices)
    high   = prices * (1 + rng.uniform(0.001, 0.012, n))
    low    = prices * (1 - rng.uniform(0.001, 0.012, n))
    volume = rng.uniform(500, 5000, n)

    idx = pd.date_range("2025-01-01", periods=n, freq="1h")
    return pd.DataFrame({
        "open":   prices,
        "high":   high,
        "low":    low,
        "close":  prices,
        "volume": volume,
    }, index=idx)


def make_ohlcv_with_bb_touch(n: int = 300, base_price: float = 300.0) -> pd.DataFrame:
    """
    BULL trend que termina con precio tocando la banda inferior de BB.
    Garantiza que se cumplan las condiciones de entrada V1.
    """
    df = make_ohlcv(n, base_price, trend="UP")
    # Forzar las últimas 5 velas con precio bajo para tocar BB lower
    close_vals = df["close"].values.copy()
    bb_lower_approx = close_vals[-30:].mean() * 0.97
    close_vals[-5:] = bb_lower_approx * 0.99
    df["close"] = close_vals
    df["low"]   = df["close"] * 0.998
    df["high"]  = df["close"] * 1.005
    return df


@pytest.fixture
def df_bull():
    return make_ohlcv(300, base_price=300.0, trend="UP")


@pytest.fixture
def df_bear():
    return make_ohlcv(300, base_price=300.0, trend="DOWN")


@pytest.fixture
def df_flat():
    return make_ohlcv(300, base_price=300.0, trend="FLAT")


@pytest.fixture
def df_bull_bb_touch():
    return make_ohlcv_with_bb_touch(300, base_price=300.0)
