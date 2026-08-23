"""Lo que se rompe si el cableado de acciones se hace a la ligera."""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from instrument import equities, main, watch


class TestUniverso:
    def test_las_acciones_se_reconocen_y_la_cripto_no(self):
        assert equities.is_equity("NVDA")
        assert equities.is_equity("nvda")          # el simbolo puede llegar en minusculas
        assert not equities.is_equity("ZEC")
        assert not equities.is_equity("BTC")

    def test_ningun_simbolo_esta_en_los_dos_universos(self):
        assert not set(main.SYMBOLS) & set(main.EQUITY_SYMBOLS)


class TestReloj:
    """72 velas no son 72 horas cuando la bolsa cierra de noche y en fin de semana."""

    def test_en_cripto_una_vela_es_una_hora(self):
        assert equities.cooldown_hours("ZEC", 72) == 72.0

    def test_en_acciones_72_velas_pasan_de_dos_semanas(self):
        horas = equities.cooldown_hours("NVDA", 72)
        assert horas > 360, f"72 velas de bolsa son ~15 dias, no {horas/24:.1f}"
        assert horas < 400

    def test_el_bug_que_esto_evita(self):
        """Con la version vieja -- 72 horas fijas para todo -- el enfriamiento en
        acciones se quedaba en ~14 velas, y la misma subida se avisaba cinco veces."""
        velas_con_72_horas = 72 / 24 * (equities.SESSIONS_PER_WEEK / equities.DAYS_PER_WEEK) * equities.BARS_PER_SESSION
        assert velas_con_72_horas < 20, "el bug ya no se reproduce, revisar la aritmetica"
        assert equities.cooldown_hours("NVDA", 72) / 72 > 5, "la correccion no esta aplicada"


class TestLado:
    def test_short_en_acciones_no_se_opera(self):
        assert not equities.side_allowed("NVDA", "SHORT")

    def test_long_en_acciones_si(self):
        assert equities.side_allowed("NVDA", "LONG")

    def test_cripto_conserva_los_dos_lados(self):
        """n=26 por lado en cripto no alcanza para recortar nada."""
        assert equities.side_allowed("ZEC", "SHORT")
        assert equities.side_allowed("ZEC", "LONG")

    def test_el_motivo_del_rechazo_trae_su_denominador(self):
        motivo = equities.side_rejection_reason("NVDA", "SHORT")
        assert "n=130" in motivo and "n=138" in motivo


class TestBarridoResiliente:
    def _conn(self):
        from instrument.store import connect
        return connect(":memory:")

    def test_un_feed_muerto_no_se_lleva_el_resto_del_barrido(self, monkeypatch):
        """Con 35 simbolos, que uno falle es rutina. Que ese fallo cancele los otros
        34 convierte una incidencia puntual en un dia sin vigilancia."""
        from instrument.feed import FeedUnavailable
        vistos = []

        def feed_falso(symbol, timeframe="1h", limit=300, since_ms=None):
            vistos.append(symbol)
            if symbol == "TAO":
                raise FeedUnavailable("simulado")
            return []                                  # <2 velas: se salta sin evaluar

        monkeypatch.setattr(main, "fetch_ohlcv", feed_falso)
        with self._conn() as conn:
            main.scan_once(conn, symbols=["ZEC", "TAO", "BTC"], send=False)
        assert vistos == ["ZEC", "TAO", "BTC"], "el barrido se detuvo en el simbolo caido"

    def test_el_feed_caido_queda_registrado_y_no_pasa_por_silencio(self, monkeypatch):
        from instrument.feed import FeedUnavailable

        def feed_falso(symbol, timeframe="1h", limit=300, since_ms=None):
            raise FeedUnavailable("simulado")

        monkeypatch.setattr(main, "fetch_ohlcv", feed_falso)
        with self._conn() as conn:
            main.scan_once(conn, symbols=["NVDA"], send=False)
            estado = watch._last_status(conn, "scan:NVDA")
        assert estado == "down", f"el feed caido quedo como {estado!r}, no como 'down'"


class TestGateDeLadoCableado:
    """Los tests de arriba prueban la funcion. Este prueba que main.py la LLAME --
    que es donde un gate correcto se queda sin conectar y nadie se entera."""

    def _conn(self):
        from instrument.store import connect
        return connect(":memory:")

    def _estrategia_que_dispara(self, side):
        class Falsa:
            @staticmethod
            def evaluate(symbol, timeframe, candles, index, suppressions=None):
                bar = candles[index]
                e = bar.close
                r = e * 0.02
                sl = e - r if side == "LONG" else e + r
                tp1 = e + 0.7 * r if side == "LONG" else e - 0.7 * r
                tp2 = e + 1.3 * r if side == "LONG" else e - 1.3 * r
                return {"ruleset_version": "test", "emitted_at": bar.ts, "bar_ts": bar.ts,
                        "symbol": symbol, "timeframe": timeframe, "side": side,
                        "decision": "SENT", "decision_reason": "prueba",
                        "gates_passed": ["rsi_extreme"], "gates_failed": [],
                        "trigger": {"rsi": 28.0, "close": e}, "regime": "TREND_PULLBACK",
                        "entry_price": e, "sl_price": sl, "tp1_price": tp1, "tp2_price": tp2,
                        "r_unit": r, "rr_tp1": 0.7, "rr_tp2": 1.3, "breakeven_wr": 0.74}
        return Falsa

    def _velas(self):
        from instrument.resolver import Candle
        return [Candle(ts=f"2026-08-2{i}T10:00:00Z", open=100, high=101, low=99, close=100)
                for i in (0, 1)]

    @pytest.mark.parametrize("symbol,side,esperado", [
        ("NVDA", "SHORT", "SUPPRESSED"),   # la medicion lo descarto
        ("NVDA", "LONG", "SENT"),
        ("ZEC", "SHORT", "SENT"),          # cripto conserva los dos lados
    ])
    def test_el_lado_se_aplica_al_guardar(self, symbol, side, esperado):
        with self._conn() as conn:
            main._evaluate_and_store(conn, self._estrategia_que_dispara(side),
                                     symbol, self._velas(), None, send=False)
            fila = conn.execute("SELECT decision, decision_reason FROM signals").fetchone()
        assert fila["decision"] == esperado, f"{symbol} {side} quedo como {fila['decision']}"
        if esperado == "SUPPRESSED":
            assert "n=130" in fila["decision_reason"], "el motivo no trae su denominador"
