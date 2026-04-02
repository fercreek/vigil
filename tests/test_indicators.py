import pytest
import pandas as pd
import numpy as np
from indicators import calculate_rsi, calculate_bollinger_bands, calculate_ema

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
