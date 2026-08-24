"""
test_exit_alerts.py — Specs de las alertas de salida (stop y target)

PROBLEMA QUE PREVIENE:
  El 21-ago-2026 el bot mando "STOP LOSS HIT: IREN" 26 veces seguidas, una cada
  15 minutos, reportando -26.05% en un trade que habria cerrado GANANDO.

  Eran tres defectos encadenados:
    1. `_clear_alert(t)` corria justo despues de `_mark_alert(t, "SL_ALERT")` y
       borraba la marca recien puesta -> el guard volvia a pasar cada ciclo.
    2. El PnL se calculaba con `-abs(sl - entry) / entry`, que fuerza el signo a
       negativo: un stop ARRIBA de la entrada en LONG salia como perdida.
    3. Nada distinguia un stop movido a ganancia de un stop de proteccion, asi que
       una salida en verde se anunciaba como "STOP LOSS HIT" y contaba LOSS.

  RKLB vive hoy en STOCK_WATCHLIST con exactamente ese perfil (LONG, entrada
  74.90, stop 91.0 movido a T1), asi que esto no es historia: es el proximo caso.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import stock_analyzer as sa


@pytest.fixture(autouse=True)
def _clean_cache(tmp_path, monkeypatch):
    """Cada test arranca con el cache vacio y persistiendo a un archivo temporal."""
    monkeypatch.setattr(sa, "_ALERT_CACHE_PATH", str(tmp_path / "alert_cache.json"))
    monkeypatch.setattr(sa, "_alert_cache", {})
    yield


# ─── El PnL de salida lleva su signo real ─────────────────────────────────────

class TestExitPnl:
    def test_long_stop_de_proteccion_es_perdida(self):
        # entrada 100, stop 90: cerrar ahi pierde 10%
        assert sa._exit_pnl_pct("LONG", 100.0, 90.0) == -10.0

    def test_long_stop_en_ganancia_es_ganancia(self):
        # IREN tal como salio: LONG entrada 45.22, stop 57.00
        # La formula vieja daba -26.05%. El trade cerraba +26.05%.
        assert sa._exit_pnl_pct("LONG", 45.22, 57.00) == 26.05

    def test_rklb_el_caso_que_sigue_vivo_en_el_config(self):
        # LONG entrada 74.90 con el stop movido a T1 (91.0) tras +30%
        assert sa._exit_pnl_pct("LONG", 74.90, 91.0) == 21.5

    def test_short_invierte_el_sentido(self):
        # en SHORT se gana cuando el precio BAJA
        assert sa._exit_pnl_pct("SHORT", 100.0, 90.0) == 10.0
        assert sa._exit_pnl_pct("SHORT", 100.0, 110.0) == -10.0

    def test_sin_entrada_no_inventa_un_numero(self):
        assert sa._exit_pnl_pct("LONG", 0, 91.0) == 0.0


# ─── El guard sobrevive al cierre del trade ───────────────────────────────────

class TestGuardSobreviveAlCierre:
    def test_close_alert_conserva_la_marca_terminal(self):
        sa._mark_alert("IREN", "ENTRY_ALERT")
        sa._mark_alert("IREN", "SL_ALERT")
        sa._close_alert("IREN", "SL_ALERT")

        # la intermedia se va, la terminal se queda
        assert sa._alert_cache["IREN"] == ["SL_ALERT"]

    def test_el_guard_bloquea_la_segunda_alerta(self):
        """La regresion exacta: tras cerrar, el ticker NO vuelve a pasar el guard."""
        sa._mark_alert("IREN", "SL_ALERT")
        sa._close_alert("IREN", "SL_ALERT")

        paso_de_nuevo = "SL_ALERT" not in sa._alert_cache.get("IREN", [])
        assert not paso_de_nuevo, "el guard dejo pasar una 2a alerta — esto son las 26 de IREN"

    def test_clear_alert_viejo_si_borraba_el_guard(self):
        """Deja escrito por que _clear_alert no sirve para cerrar un trade."""
        sa._mark_alert("IREN", "SL_ALERT")
        sa._clear_alert("IREN")

        assert "SL_ALERT" not in sa._alert_cache.get("IREN", [])

    def test_veinte_ciclos_emiten_una_sola_vez(self):
        """Simula el poller: 20 pasadas con el precio bajo el stop, 1 sola alerta."""
        emitidas = 0
        for _ in range(20):
            if "SL_ALERT" not in sa._alert_cache.get("IREN", []):
                emitidas += 1
                sa._mark_alert("IREN", "SL_ALERT")
                sa._close_alert("IREN", "SL_ALERT")
        assert emitidas == 1, f"emitio {emitidas} veces; IREN emitio 26"
