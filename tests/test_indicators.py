import pytest
import pandas as pd
import numpy as np
from indicators import (
    calculate_rsi, calculate_bollinger_bands, calculate_ema,
    detect_elliott_impulse, _zigzag_pivots,
)

@pytest.fixture
def sample_prices():
    """Genera una serie de precios para pruebas."""
    return pd.Series([
        100.0, 101.0, 102.0, 101.0, 100.0, 99.0, 98.0, 99.0, 100.0, 101.0,
        102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0, 112.0
    ])

def test_calculate_rsi_length(sample_prices):
    """Verifica que el RSI retorna 50.0 si no hay suficientes datos."""
    short_prices = sample_prices.iloc[:10]
    assert calculate_rsi(short_prices, period=14) == 50.0

def test_calculate_rsi_value(sample_prices):
    """Verifica que el RSI se calcula correctamente (suavizado Wilder)."""
    rsi = calculate_rsi(sample_prices, period=14)
    # Con una tendencia alcista al final, el RSI debería ser > 50
    assert rsi > 50
    assert rsi < 100

def test_calculate_bollinger_bands(sample_prices):
    """Verifica el cálculo de las Bandas de Bollinger."""
    # Necesitamos al menos 20 periodos para BB estándar
    bands = calculate_bollinger_bands(sample_prices, period=20, std_dev=2)
    assert bands is not None
    upper, mid, lower = bands
    assert upper > mid
    assert mid > lower
    # Mid debe ser la media móvil de los últimos 20
    assert mid == pytest.approx(sample_prices.iloc[-20:].mean())

def test_calculate_ema_short_data():
    """Verifica que la EMA retorna la media simple si hay pocos datos."""
    prices = pd.Series([10.0, 20.0])
    ema = calculate_ema(prices, period=10)
    assert ema == 15.0

def test_calculate_ema_consistency(sample_prices):
    """Verifica que la EMA reaccione a los cambios de precio."""
    ema_20 = calculate_ema(sample_prices, period=20)
    last_price = sample_prices.iloc[-1]
    # En una tendencia alcista, el precio suele estar sobre la EMA
    assert ema_20 < last_price


# ─── Elliott Impulse Detector ───────────────────────────────────────────────

def _build_ohlcv(closes):
    """Construye un DF OHLCV mínimo a partir de una serie de cierres."""
    closes = list(closes)
    rows = []
    for i, c in enumerate(closes):
        prev = closes[i-1] if i > 0 else c
        h = max(prev, c) * 1.001
        l = min(prev, c) * 0.999
        rows.append({"timestamp": i, "open": prev, "high": h, "low": l, "close": c, "volume": 1000.0})
    return pd.DataFrame(rows)


def _impulse_path(p0, w1, w2_pct, w3_mult, w4_pct, w5_mult, steps_per_leg=15):
    """
    Genera un camino de precios de un impulso 1-2-3-4-5 alcista lineal por tramo.
    `w2_pct` retracement of W1, `w3_mult` extension over W1, etc.
    """
    p1 = p0 + w1
    p2 = p1 - w1 * w2_pct
    w3_len = w1 * w3_mult
    p3 = p2 + w3_len
    p4 = p3 - w3_len * w4_pct
    p5 = p4 + w1 * w5_mult
    pivots = [p0, p1, p2, p3, p4, p5]
    closes = []
    for a, b in zip(pivots[:-1], pivots[1:]):
        for k in range(steps_per_leg):
            closes.append(a + (b - a) * (k / steps_per_leg))
    closes.append(pivots[-1])
    return closes


def test_zigzag_pivots_detects_alternating_swings():
    """ZigZag debe detectar pivots alternados en una serie con swings claros."""
    closes = _impulse_path(100.0, w1=10.0, w2_pct=0.5, w3_mult=1.618,
                           w4_pct=0.382, w5_mult=1.0)
    df = _build_ohlcv(closes)
    pivots = _zigzag_pivots(df, atr_pct_threshold=2.0)
    kinds = [p[2] for p in pivots]
    # Esperamos al menos 5 pivots alternados
    assert len(pivots) >= 5
    for a, b in zip(kinds[:-1], kinds[1:]):
        assert a != b, "Pivots deben alternar high/low"


def test_elliott_impulse_returns_no_pattern_on_flat_data():
    """Datos planos no deben producir patrón de impulso."""
    df = _build_ohlcv([100.0] * 80)
    result = detect_elliott_impulse(df)
    assert result["phase"] == "no_pattern"
    assert result["score"] == 0


def test_elliott_impulse_returns_no_pattern_on_short_data():
    """Series demasiado cortas deben retornar 'Sin datos suficientes'."""
    df = _build_ohlcv([100.0, 101.0, 102.0])
    result = detect_elliott_impulse(df)
    assert result["phase"] == "no_pattern"
    assert "datos" in result["summary"].lower() or "pivots" in result["summary"].lower()


def test_elliott_impulse_detects_textbook_bullish_5_waves():
    """Un impulso alcista 1-2-3-4-5 con ratios típicos debe puntuar alto."""
    closes = _impulse_path(100.0, w1=10.0, w2_pct=0.5, w3_mult=1.618,
                           w4_pct=0.382, w5_mult=1.0)
    df = _build_ohlcv(closes)
    result = detect_elliott_impulse(df)
    # Reconoce el lado long y al menos cumple las 3 reglas Elliott (score base 60)
    assert result["side"] == "LONG"
    assert result["score"] >= 60
    assert result["phase"] in ("wave_5_complete", "wave_5_terminal")
    # Targets fib calculados
    assert result["fib_target_127"] > 0
    assert result["fib_target_161"] > result["fib_target_127"]


def test_elliott_impulse_rejects_w4_overlapping_w1():
    """Si Onda 4 entra en territorio de Onda 1 (regla 3), no debe validarse."""
    # W4 retracea 100% de W3 (entra muy abajo, más allá del top de W1)
    closes = _impulse_path(100.0, w1=10.0, w2_pct=0.3, w3_mult=1.5,
                           w4_pct=1.0, w5_mult=0.6)
    df = _build_ohlcv(closes)
    result = detect_elliott_impulse(df)
    # Debe rechazar con score 0 o no detectar el patrón
    assert result["score"] == 0 or result["phase"] == "no_pattern"
