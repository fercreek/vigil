"""
Scale-out en TP1 (P1.1) — el 50% se cierra en TP1 y el resto corre con SL en BE.

Lo que blindan estas pruebas es el bug que hacia que el feed de Telegram saliera
~80% rojo: un trade que tocaba TP1 y volvia al breakeven se guardaba como LOST,
con el PnL de la pata que quedaba en vez del resultado real de las dos.
"""
import os
import sys
import sqlite3
import tempfile
import importlib

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def db(monkeypatch):
    """tracker apuntado a una DB temporal — nunca toca trades.db real."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    import tracker
    monkeypatch.setattr(tracker, "DB_FILE", path)
    tracker.init_db()
    yield tracker, path
    os.unlink(path)


def _row(path, trade_id, *cols):
    conn = sqlite3.connect(path)
    r = conn.execute(f"SELECT {', '.join(cols)} FROM trades WHERE id = ?", (trade_id,)).fetchone()
    conn.close()
    return r


# ── blended_pnl_pct: la aritmetica sola ─────────────────────────────────────

def test_blended_long_be_after_partial():
    """LONG: 50% en TP1 (+10%) + 50% en BE (0%) = +5%, no 0% y menos aun -1R."""
    import trade_monitor as tm
    t = {"type": "LONG", "entry_price": 100.0, "tp1_price": 110.0, "partial_pct": 50}
    assert tm.blended_pnl_pct(t, 100.0) == pytest.approx(5.0)


def test_blended_short_be_after_partial():
    """SHORT: el signo se invierte — 50% en TP1 ($90 desde $100) + 50% plano = +5%."""
    import trade_monitor as tm
    t = {"type": "SHORT", "entry_price": 100.0, "tp1_price": 90.0, "partial_pct": 50}
    assert tm.blended_pnl_pct(t, 100.0) == pytest.approx(5.0)


def test_blended_sin_parcial_es_el_pnl_de_siempre():
    """Sin parcial (w=0) devuelve el PnL de la salida — cero cambio de conducta."""
    import trade_monitor as tm
    t = {"type": "LONG", "entry_price": 100.0, "tp1_price": 110.0, "partial_pct": 0}
    assert tm.blended_pnl_pct(t, 95.0) == pytest.approx(-5.0)


def test_blended_runner_perdedor_sigue_siendo_ganancia_neta():
    """El runner puede salir peor que BE y el trade completo seguir en verde."""
    import trade_monitor as tm
    t = {"type": "LONG", "entry_price": 100.0, "tp1_price": 112.0, "partial_pct": 50}
    # 50% a +12% + 50% a -2% = +5%
    assert tm.blended_pnl_pct(t, 98.0) == pytest.approx(5.0)


def test_blended_respeta_un_parcial_distinto_de_50():
    """El peso sale de partial_pct, no de un 0.5 hardcodeado."""
    import trade_monitor as tm
    t = {"type": "LONG", "entry_price": 100.0, "tp1_price": 110.0, "partial_pct": 25}
    # 25% a +10% + 75% a 0% = +2.5%
    assert tm.blended_pnl_pct(t, 100.0) == pytest.approx(2.5)


# ── tracker: los flags que nunca se habian escrito ──────────────────────────

def test_mark_be_respeta_el_offset(db):
    """mark_be con precio explicito no aplasta el SL al entry pelado."""
    tracker, path = db
    tid = tracker.log_trade("ZEC", "LONG", 100.0, 110.0, 120.0, 92.0, "m1")
    tracker.mark_be(tid, sl_price=100.1)
    be_moved, sl = _row(path, tid, "be_moved", "sl_price")
    assert be_moved == 1
    assert sl == pytest.approx(100.1)


def test_mark_be_sin_precio_conserva_conducta_original(db):
    """La firma vieja (sin sl_price) sigue mandando el SL exacto al entry."""
    tracker, path = db
    tid = tracker.log_trade("ZEC", "LONG", 100.0, 110.0, 120.0, 92.0, "m1")
    tracker.mark_be(tid)
    be_moved, sl = _row(path, tid, "be_moved", "sl_price")
    assert be_moved == 1
    assert sl == pytest.approx(100.0)


def test_mark_partial_deja_rastro(db):
    """partial_pct dejo de ser 0 en las 92 filas del historico."""
    tracker, path = db
    tid = tracker.log_trade("ZEC", "LONG", 100.0, 110.0, 120.0, 92.0, "m1")
    tracker.mark_partial(tid, 50)
    pct, status = _row(path, tid, "partial_pct", "status")
    assert pct == 50
    assert status == "PARTIAL_WON"


def test_partial_won_sigue_siendo_trade_abierto(db):
    """Tras TP1 el trade se sigue monitoreando — si no, el runner queda huerfano."""
    tracker, path = db
    tid = tracker.log_trade("ZEC", "LONG", 100.0, 110.0, 120.0, 92.0, "m1")
    tracker.mark_partial(tid, 50)
    assert tid in [t["id"] for t in tracker.get_open_trades()]


def test_partial_closed_cierra_con_close_time(db):
    """PARTIAL_CLOSED es estado terminal y estampa close_time."""
    tracker, path = db
    tid = tracker.log_trade("ZEC", "LONG", 100.0, 110.0, 120.0, 92.0, "m1")
    tracker.update_trade_status(tid, "PARTIAL_CLOSED")
    status, close_time = _row(path, tid, "status", "close_time")
    assert status == "PARTIAL_CLOSED"
    assert close_time is not None
    assert tid not in [t["id"] for t in tracker.get_open_trades()]


# ── ciclo completo contra monitor_open_trades ───────────────────────────────

class _Recorder:
    """Doble de circuit_breaker: guarda como se clasifico cada cierre."""
    def __init__(self):
        self.calls = []

    def record_outcome(self, is_win, pnl_pct):
        self.calls.append({"is_win": is_win, "pnl_pct": pnl_pct})


@pytest.fixture
def monitor(db, monkeypatch):
    """monitor_open_trades con todo lo externo stubbeado menos tracker."""
    import types
    tracker, path = db
    import trade_monitor as tm

    alerts = []
    cb = _Recorder()

    fake_bot = types.ModuleType("scalp_alert_bot")
    fake_bot.send_telegram = lambda *a, **k: None
    fake_bot.safe_html = lambda x: x
    fake_bot.GLOBAL_CACHE = {"episode_ids": {}}
    fake_bot.alert = lambda key, msg, **k: alerts.append({"key": key, "msg": msg})

    fake_gemini = types.ModuleType("gemini_analyzer")
    fake_gemini.log_result_to_context = lambda *a, **k: None

    fake_risk = types.ModuleType("risk_manager")
    fake_risk.circuit_breaker = cb
    fake_risk.trailing_stop_mgr = types.SimpleNamespace(
        calculate_trailing_updates=lambda *a, **k: [],
        cleanup_closed=lambda *a, **k: None,
    )

    monkeypatch.setitem(sys.modules, "scalp_alert_bot", fake_bot)
    monkeypatch.setitem(sys.modules, "gemini_analyzer", fake_gemini)
    monkeypatch.setitem(sys.modules, "risk_manager", fake_risk)

    fake_ind = types.SimpleNamespace(
        get_df=lambda *a, **k: None,
        calculate_rvol=lambda *a, **k: 1.0,
        calculate_atr=lambda *a, **k: 1.0,
        calculate_atr_trailing_stop=lambda *a, **k: 0.0,
    )
    monkeypatch.setattr(tm, "indicators", fake_ind)
    monkeypatch.setattr(tm, "_em", types.SimpleNamespace(fill_outcome=lambda *a, **k: None))

    return tm, tracker, path, alerts, cb


def test_ciclo_tp1_y_vuelta_a_be_no_es_perdida(monitor):
    """
    El caso exacto que inflaba el 81% rojo:
    LONG entra en 100, toca TP1 en 110, regresa al BE.

    Antes:  status LOST, circuit_breaker cuenta derrota.
    Ahora:  status PARTIAL_CLOSED, +5% real, el breaker cuenta victoria.
    """
    tm, tracker, path, alerts, cb = monitor
    tid = tracker.log_trade("ZEC", "LONG", 100.0, 110.0, 130.0, 92.0, "m1", version="SWING")

    # 1) el precio toca TP1
    tm.monitor_open_trades({"ZEC": 110.5})
    status, pct, be, sl = _row(path, tid, "status", "partial_pct", "be_moved", "sl_price")
    assert status == "PARTIAL_WON"
    assert pct == 50
    assert be == 1
    assert sl == pytest.approx(100.1)          # BE con offset, no el SL original de 92
    assert any("TP1 HIT" in a["msg"] for a in alerts)

    # 2) el precio regresa y toca el BE
    tm.monitor_open_trades({"ZEC": 100.0})
    status, close_time = _row(path, tid, "status", "close_time")
    assert status == "PARTIAL_CLOSED", "un runner cerrado en BE no es un stop loss"
    assert close_time is not None

    ultimo = cb.calls[-1]
    assert ultimo["is_win"] is True
    assert ultimo["pnl_pct"] == pytest.approx(5.0)   # 50% a +10% + 50% plano

    cierre = [a for a in alerts if a["key"].endswith("_l")][-1]
    assert "SL HIT" not in cierre["msg"]
    assert "RUNNER CERRADO" in cierre["msg"]


def test_stop_sin_parcial_sigue_siendo_perdida(monitor):
    """Sin regresion: un stop de riesgo completo se guarda LOST y avisa en rojo."""
    tm, tracker, path, alerts, cb = monitor
    tid = tracker.log_trade("ZEC", "LONG", 100.0, 110.0, 130.0, 92.0, "m2", version="SWING")

    tm.monitor_open_trades({"ZEC": 91.0})
    status, pct = _row(path, tid, "status", "partial_pct")
    assert status == "LOST"
    assert pct == 0

    ultimo = cb.calls[-1]
    assert ultimo["is_win"] is False
    assert ultimo["pnl_pct"] == pytest.approx(-9.0)
    assert any("SL HIT" in a["msg"] for a in alerts)


def test_tp2_despues_de_parcial_reporta_pnl_mezclado(monitor):
    """Llegar a TP2 con parcial tomado NO paga el 30% completo: paga la mezcla."""
    tm, tracker, path, alerts, cb = monitor
    tid = tracker.log_trade("ZEC", "LONG", 100.0, 110.0, 130.0, 92.0, "m3", version="SWING")

    tm.monitor_open_trades({"ZEC": 110.5})    # TP1
    tm.monitor_open_trades({"ZEC": 130.5})    # TP2
    assert _row(path, tid, "status")[0] == "FULL_WON"

    ultimo = cb.calls[-1]
    # 50% a +10% + 50% a +30.5% = +20.25%, no +30.5%
    assert ultimo["pnl_pct"] == pytest.approx(20.25)


def test_tp1_no_se_dispara_dos_veces(monitor):
    """Segundo ciclo con el precio aun sobre TP1 no vuelve a tomar parcial."""
    tm, tracker, path, alerts, cb = monitor
    tid = tracker.log_trade("ZEC", "LONG", 100.0, 110.0, 130.0, 92.0, "m4", version="SWING")

    tm.monitor_open_trades({"ZEC": 111.0})
    tm.monitor_open_trades({"ZEC": 112.0})
    assert _row(path, tid, "partial_pct")[0] == 50
    assert len([a for a in alerts if "TP1 HIT" in a["msg"]]) == 1


def test_short_completo_tp1_a_be(monitor):
    """El lado SHORT tambien: entra en 100, TP1 en 90, regresa al BE."""
    tm, tracker, path, alerts, cb = monitor
    tid = tracker.log_trade("ZEC", "SHORT", 100.0, 90.0, 80.0, 108.0, "m5", version="SWING")

    tm.monitor_open_trades({"ZEC": 89.5})
    status, pct, sl = _row(path, tid, "status", "partial_pct", "sl_price")
    assert status == "PARTIAL_WON"
    assert pct == 50
    assert sl == pytest.approx(99.9)          # BE con offset hacia abajo

    tm.monitor_open_trades({"ZEC": 100.0})
    assert _row(path, tid, "status")[0] == "PARTIAL_CLOSED"
    assert cb.calls[-1]["pnl_pct"] == pytest.approx(5.0)
