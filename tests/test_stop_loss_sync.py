"""
Sincronizacion del stop con Binance.

El bot movia el SL solo en su tabla: `tracker.update_sl` / `mark_be` hacian UPDATE y
la STOP_MARKET que dejo `execute_bracket_order` (trading_executor.py) se quedaba donde
estaba. En LIVE eso es el bot reportando "SL en BE" con el stop real todavia a 2 ATR.

Lo que mas se cuida aqui no es mover el stop — es NO tocar posiciones que el bot no
abrio. De ahi la guarda de propiedad `exchange_order_id`.
"""
import os
import sys
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _stop_order(oid="SL-1", amount=2.0):
    return {"id": oid, "type": "stop_market", "reduceOnly": True, "amount": amount,
            "info": {"type": "STOP_MARKET", "reduceOnly": "true", "origQty": str(amount)}}


def _limit_order(oid="TP-1"):
    return {"id": oid, "type": "limit", "reduceOnly": True, "amount": 1.0,
            "info": {"type": "LIMIT", "reduceOnly": "true"}}


@pytest.fixture
def executor(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "LIVE")
    with patch("ccxt.binance"):
        from trading_executor import ZenithExecutor
        ex = ZenithExecutor()
        ex.mode = "LIVE"
        ex.exchange = MagicMock()
        return ex


# ── reconocer la orden correcta ─────────────────────────────────────────────

def test_reconoce_stop_market_reduce_only():
    from trading_executor import ZenithExecutor
    assert ZenithExecutor._is_bot_stop_order(_stop_order()) is True


def test_ignora_las_limit_de_tp():
    """Los TP1/TP2/TP3 tambien son reduceOnly — cancelarlos seria destruir el scale-out."""
    from trading_executor import ZenithExecutor
    assert ZenithExecutor._is_bot_stop_order(_limit_order()) is False


def test_ignora_stop_que_no_es_reduce_only():
    """Un stop de entrada no se toca."""
    from trading_executor import ZenithExecutor
    o = _stop_order()
    o["reduceOnly"] = False
    o["info"]["reduceOnly"] = "false"
    assert ZenithExecutor._is_bot_stop_order(o) is False


def test_reconoce_aunque_ccxt_no_normalice_el_tipo():
    """Con `type` vacio se cae al crudo de info — ccxt cambia esto entre versiones."""
    from trading_executor import ZenithExecutor
    o = {"id": "x", "type": None, "reduceOnly": None,
         "info": {"type": "STOP_MARKET", "reduceOnly": "true", "origQty": "1"}}
    assert ZenithExecutor._is_bot_stop_order(o) is True


# ── el camino feliz ─────────────────────────────────────────────────────────

def test_cancela_la_vieja_y_crea_la_nueva(executor):
    executor.exchange.fetch_open_orders.return_value = [_limit_order(), _stop_order("SL-9", 2.5)]
    executor.exchange.create_order.return_value = {"id": "SL-NEW"}

    res = executor.sync_stop_loss("ZEC", "LONG", 100.1)

    assert res["status"] == "SYNCED"
    executor.exchange.cancel_order.assert_called_once_with("SL-9", "ZEC/USDT")

    _, kwargs = executor.exchange.create_order.call_args
    assert kwargs["type"] == "STOP_MARKET"
    assert kwargs["side"] == "sell"                    # cerrar un LONG es vender
    assert kwargs["params"]["stopPrice"] == 100.1
    assert kwargs["params"]["reduceOnly"] is True
    assert kwargs["amount"] == 2.5                     # hereda la cantidad de la cancelada


def test_short_invierte_el_lado_de_salida(executor):
    executor.exchange.fetch_open_orders.return_value = [_stop_order()]
    executor.exchange.create_order.return_value = {"id": "SL-NEW"}

    executor.sync_stop_loss("ZEC", "SHORT", 99.9)

    _, kwargs = executor.exchange.create_order.call_args
    assert kwargs["side"] == "buy"


# ── lo que NO debe pasar ────────────────────────────────────────────────────

def test_sin_stop_viva_no_crea_nada(executor):
    """La orden ya no esta (se lleno o la cancelaron a mano) → no se inventa una."""
    executor.exchange.fetch_open_orders.return_value = [_limit_order()]

    res = executor.sync_stop_loss("ZEC", "LONG", 100.1)

    assert res["status"] == "NOT_FOUND"
    executor.exchange.create_order.assert_not_called()
    executor.exchange.cancel_order.assert_not_called()


def test_paper_no_toca_el_exchange(executor, monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "PAPER")
    res = executor.sync_stop_loss("ZEC", "LONG", 100.1)
    assert res["status"] == "SKIPPED_PAPER"
    executor.exchange.fetch_open_orders.assert_not_called()


def test_fetch_caido_no_lanza_y_deja_el_stop_viejo(executor):
    """Si falla antes de cancelar, la posicion sigue protegida por el stop original."""
    executor.exchange.fetch_open_orders.side_effect = Exception("network")

    res = executor.sync_stop_loss("ZEC", "LONG", 100.1)

    assert res["status"] == "FAILED"
    assert not res.get("unprotected")
    executor.exchange.create_order.assert_not_called()


def test_cancel_que_pierde_la_carrera_no_deja_hueco(executor):
    """La orden se lleno entre el fetch y el cancel → NOT_FOUND, sin crear nada."""
    executor.exchange.fetch_open_orders.return_value = [_stop_order()]
    executor.exchange.cancel_order.side_effect = Exception("Unknown order sent")

    res = executor.sync_stop_loss("ZEC", "LONG", 100.1)

    assert res["status"] == "NOT_FOUND"
    executor.exchange.create_order.assert_not_called()


def test_alta_fallida_tras_cancelar_se_marca_descubierta(executor):
    """El caso peligroso: stop viejo cancelado, nuevo rechazado. Tiene que gritar."""
    executor.exchange.fetch_open_orders.return_value = [_stop_order()]
    executor.exchange.create_order.side_effect = Exception("ReduceOnly Order is rejected")

    res = executor.sync_stop_loss("ZEC", "LONG", 100.1)

    assert res["status"] == "FAILED"
    assert res["unprotected"] is True


# ── la guarda de propiedad (lo que impide tocar posiciones ajenas) ──────────

class _FakeExecutor:
    def __init__(self):
        self.calls = []
        self.result = {"status": "SYNCED"}

    def sync_stop_loss(self, symbol, side, new_sl):
        self.calls.append((symbol, side, new_sl))
        return self.result


@pytest.fixture
def wired(monkeypatch):
    """trade_monitor.sync_exchange_stop con un executor falso en LIVE."""
    import types
    import trade_monitor as tm

    fake_exec = _FakeExecutor()
    fake_bot = types.ModuleType("scalp_alert_bot")
    fake_bot.GLOBAL_CACHE = {"executor": fake_exec}
    monkeypatch.setitem(sys.modules, "scalp_alert_bot", fake_bot)
    monkeypatch.setenv("EXECUTION_MODE", "LIVE")
    return tm, fake_exec


def test_trade_sin_order_id_no_toca_binance(wired):
    """Un SWING que abriste a mano NO tiene ordenes del bot — no se le tocan las suyas."""
    tm, fake_exec = wired
    trade = {"id": 1, "symbol": "ZEC", "type": "LONG", "exchange_order_id": None}

    res = tm.sync_exchange_stop(trade, 100.1)

    assert res["status"] == "SKIPPED_NOT_OWNED"
    assert fake_exec.calls == []


def test_trade_con_order_id_si_sincroniza(wired):
    tm, fake_exec = wired
    trade = {"id": 1, "symbol": "ZEC", "type": "LONG", "exchange_order_id": "ORD-77"}

    res = tm.sync_exchange_stop(trade, 100.1)

    assert res["status"] == "SYNCED"
    assert fake_exec.calls == [("ZEC", "LONG", 100.1)]


def test_paper_no_sincroniza_aunque_sea_propio(wired, monkeypatch):
    tm, fake_exec = wired
    monkeypatch.setenv("EXECUTION_MODE", "PAPER")
    trade = {"id": 1, "symbol": "ZEC", "type": "LONG", "exchange_order_id": "ORD-77"}

    assert tm.sync_exchange_stop(trade, 100.1)["status"] == "SKIPPED_PAPER"
    assert fake_exec.calls == []


def test_stop_descubierto_dispara_alerta(wired):
    tm, fake_exec = wired
    fake_exec.result = {"status": "FAILED", "reason": "rejected", "unprotected": True}
    trade = {"id": 7, "symbol": "ZEC", "type": "LONG", "exchange_order_id": "ORD-77"}

    alerts = []
    tm.sync_exchange_stop(trade, 100.1, alert_fn=lambda k, m, **kw: alerts.append(m))

    assert len(alerts) == 1
    assert "SIN STOP" in alerts[0]


def test_executor_que_revienta_no_tumba_el_monitor(wired):
    """El ciclo de monitoreo no se cae porque Binance falle."""
    tm, fake_exec = wired

    def boom(*a, **k):
        raise RuntimeError("binance down")
    fake_exec.sync_stop_loss = boom
    trade = {"id": 1, "symbol": "ZEC", "type": "LONG", "exchange_order_id": "ORD-77"}

    res = tm.sync_exchange_stop(trade, 100.1)
    assert res["status"] == "FAILED"


# ── el id de propiedad solo se setea cuando la orden fue real ──────────────

@pytest.mark.parametrize("exec_result,esperado", [
    ({"status": "LIVE_EXECUTED", "id": 12345}, "12345"),
    ({"status": "PAPER_EXECUTED", "id": "PAPER_1"}, None),
    ({"status": "FAILED", "reason": "saldo"}, None),
    ({"status": "SKIPPED", "reason": "paused"}, None),
    ({"status": "LIVE_EXECUTED"}, None),
    (None, None),
])
def test_exec_order_id_solo_para_ordenes_reales(exec_result, esperado):
    """PAPER y FAILED no dan permiso: no hay ordenes que sincronizar."""
    import scalp_alert_bot
    assert scalp_alert_bot._exec_order_id(exec_result) == esperado
