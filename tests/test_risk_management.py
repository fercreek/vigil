import pytest
from unittest.mock import MagicMock, patch
from trading_executor import ZenithExecutor

@pytest.fixture
def executor():
    """Configura una instancia de ZenithExecutor en modo PAPER para pruebas."""
    with patch('ccxt.binance'):
        ex = ZenithExecutor()
        ex.mode = "PAPER"
        ex.risk_pct = 0.01  # 1% de riesgo por trade
        return ex

def test_calculate_amount_long(executor):
    """Verifica el cálculo de cantidad para una posición LONG."""
    # Riesgo = 1000 * 0.01 = $10
    # Distancia SL = 100 - 90 = $10
    # Cantidad = 10 / 10 = 1.0
    balance = 1000.0
    entry = 100.0
    sl = 90.0
    amount = executor.calculate_amount("BTC", entry, sl, balance)
    assert amount == 1.0

def test_calculate_amount_short(executor):
    """Verifica el cálculo de cantidad para una posición SHORT."""
    # Riesgo = 2000 * 0.01 = $20
    # Distancia SL = 105 - 100 = $5
    # Cantidad = 20 / 5 = 4.0
    balance = 2000.0
    entry = 100.0
    sl = 105.0
    amount = executor.calculate_amount("ETH", entry, sl, balance)
    assert amount == 4.0

def test_calculate_amount_zero_sl_distance(executor):
    """Verifica que no hay división por cero si el SL es igual a la entrada."""
    balance = 1000.0
    entry = 100.0
    sl = 100.0
    amount = executor.calculate_amount("BTC", entry, sl, balance)
    assert amount == 0.1  # Fallback definido en el código

def test_get_balance_paper_mode(executor):
    """Verifica que el balance en modo PAPER siempre retorna 1000.0."""
    assert executor.get_balance() == 1000.0

def test_risk_percentage_init(executor):
    """Verifica que el porcentaje de riesgo se inicializa correctamente."""
    assert executor.risk_pct == 0.01
