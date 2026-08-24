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


class TestEsperaAdaptativa:
    """La bolsa abre el 19% de la semana. Preguntar cada cinco minutos el otro 81%
    son ~6,600 peticiones diarias por velas que no pueden existir -- y Yahoo no
    contesta a eso con un error, contesta con vacio."""

    def _conn(self):
        from instrument.store import connect
        return connect(":memory:")

    def _feed_pegado(self, ts):
        from instrument.resolver import Candle
        def feed(symbol, timeframe="1h", limit=300, since_ms=None):
            return [Candle(ts=ts, open=100, high=101, low=99, close=100)] * 2
        return feed

    def test_repetir_la_misma_vela_alarga_la_espera(self, monkeypatch):
        main._reset_backoff()
        monkeypatch.setattr(main, "fetch_ohlcv", self._feed_pegado("2026-08-21T20:00:00Z"))
        with self._conn() as conn:
            main.scan_once(conn, symbols=["NVDA"], send=False)      # primera: la registra
            assert main._idle_wait["NVDA"] == 0.0
            main._skip_until["NVDA"] = 0.0                          # dejar pasar el guard
            main.scan_once(conn, symbols=["NVDA"], send=False)      # segunda: misma vela
            assert main._idle_wait["NVDA"] == main.SCAN_SLEEP_SECONDS
            main._skip_until["NVDA"] = 0.0
            main.scan_once(conn, symbols=["NVDA"], send=False)      # tercera: se dobla
            assert main._idle_wait["NVDA"] == main.SCAN_SLEEP_SECONDS * 2

    def test_la_espera_tiene_tope(self, monkeypatch):
        main._reset_backoff()
        monkeypatch.setattr(main, "fetch_ohlcv", self._feed_pegado("2026-08-21T20:00:00Z"))
        with self._conn() as conn:
            for _ in range(12):
                main._skip_until["NVDA"] = 0.0
                main.scan_once(conn, symbols=["NVDA"], send=False)
        assert main._idle_wait["NVDA"] == main.IDLE_BACKOFF_MAX_SECONDS

    def test_una_vela_nueva_devuelve_el_ritmo_normal(self, monkeypatch):
        main._reset_backoff()
        with self._conn() as conn:
            monkeypatch.setattr(main, "fetch_ohlcv", self._feed_pegado("2026-08-21T20:00:00Z"))
            main.scan_once(conn, symbols=["NVDA"], send=False)
            main._skip_until["NVDA"] = 0.0
            main.scan_once(conn, symbols=["NVDA"], send=False)
            assert main._idle_wait["NVDA"] > 0
            monkeypatch.setattr(main, "fetch_ohlcv", self._feed_pegado("2026-08-21T21:00:00Z"))
            main._skip_until["NVDA"] = 0.0
            main.scan_once(conn, symbols=["NVDA"], send=False)
        assert main._idle_wait["NVDA"] == 0.0, "una vela nueva debe reiniciar la espera"

    def test_mientras_espera_no_se_pide_el_feed(self, monkeypatch):
        main._reset_backoff()
        pedidos = []
        from instrument.resolver import Candle
        def feed(symbol, timeframe="1h", limit=300, since_ms=None):
            pedidos.append(symbol)
            return [Candle(ts="2026-08-21T20:00:00Z", open=100, high=101, low=99, close=100)] * 2
        monkeypatch.setattr(main, "fetch_ohlcv", feed)
        with self._conn() as conn:
            main.scan_once(conn, symbols=["NVDA"], send=False)
            main._skip_until["NVDA"] = 0.0
            main.scan_once(conn, symbols=["NVDA"], send=False)   # deja la espera puesta
            main.scan_once(conn, symbols=["NVDA"], send=False)   # este debe saltarse
        assert len(pedidos) == 2, f"se pidio el feed {len(pedidos)} veces, esperaba 2"


class TestMarcadorPorUniverso:
    """Las dos poblaciones no comparten evidencia -- n=138 y solo LONG en acciones,
    n=26 y los dos lados en cripto. Una sola cifra encima de ambas no describe a
    ninguna, y se lee como si describiera a las dos."""

    def _conn(self):
        from instrument.store import connect
        return connect(":memory:")

    def _senal(self, conn, symbol, r_realized):
        from instrument.store import insert_signal, insert_resolution
        sid = insert_signal(
            conn, ruleset_version="v1", emitted_at="2026-08-23T10:00:00Z",
            bar_ts=f"2026-08-23T10:00:00Z", symbol=symbol, timeframe="1h", side="LONG",
            decision="SENT", decision_reason="prueba", gates_passed=["rsi_extreme"],
            gates_failed=[], trigger={"rsi": 28.0}, regime="TREND_PULLBACK",
            entry_price=100.0, sl_price=98.0, tp1_price=101.4, tp2_price=102.6,
            r_unit=2.0, rr_tp1=0.7, rr_tp2=1.3, breakeven_wr=0.74)
        insert_resolution(conn, signal_id=sid, resolver_version="v1",
                          resolved_at="2026-08-24T10:00:00Z", outcome="TP1_THEN_TP2",
                          exit_price=102.6, exit_bar_ts="2026-08-24T10:00:00Z", bars_held=5,
                          tp1_hit=True, tp1_bar_ts="2026-08-23T14:00:00Z", mae_r=-0.2,
                          mfe_r=1.3, r_realized=r_realized, r_if_tp1_only=0.7,
                          r_if_no_partial=1.3, same_bar_ambiguous=False,
                          resolution_source="BARS")
        return sid

    def test_cada_universo_cuenta_solo_lo_suyo(self):
        from instrument import scoreboard
        with self._conn() as conn:
            self._senal(conn, "NVDA", 1.0)
            self._senal(conn, "ZEC", -1.0)
            acc = scoreboard.build_report(conn, universe="equities")
            cri = scoreboard.build_report(conn, universe="crypto")
        assert acc["n_resolved"] == 1 and acc["expectancy_r"] == 1.0
        assert cri["n_resolved"] == 1 and cri["expectancy_r"] == -1.0

    def test_la_media_conjunta_borra_a_las_dos(self):
        """Sin separar, +1R y -1R se promedian a cero: el numero no describe ni al
        universo que gano ni al que perdio."""
        from instrument import scoreboard
        with self._conn() as conn:
            self._senal(conn, "NVDA", 1.0)
            self._senal(conn, "ZEC", -1.0)
            junto = scoreboard.build_report(conn)
        assert junto["expectancy_r"] == 0.0

    def test_el_marcador_por_defecto_entrega_uno_por_universo(self):
        from instrument import scoreboard
        with self._conn() as conn:
            self._senal(conn, "NVDA", 1.0)
            self._senal(conn, "ZEC", -1.0)
            reportes = scoreboard.build_reports_by_universe(conn)
        assert {r["universe"] for r in reportes} == {"crypto", "equities"}

    def test_un_universo_sin_datos_no_ocupa_espacio(self):
        """Acciones arranca vacio y tarda semanas. Una seccion vacia al lado de una
        llena invita a leerlas juntas."""
        from instrument import scoreboard
        with self._conn() as conn:
            self._senal(conn, "ZEC", -1.0)
            reportes = scoreboard.build_reports_by_universe(conn)
        assert [r["universe"] for r in reportes] == ["crypto"]

    def test_el_encabezado_dice_de_quien_habla(self):
        from instrument import scoreboard
        with self._conn() as conn:
            self._senal(conn, "NVDA", 1.0)
            texto = scoreboard.render_report(scoreboard.build_report(conn, universe="equities"))
        assert "acciones" in texto.splitlines()[0]

    def test_una_senal_de_acciones_no_se_declara_muerta_a_las_72_horas(self):
        """El reloj otra vez: en acciones 72 horas son 14 velas, y una senal viva
        y sana quedaria contada como huerfana a los tres dias."""
        from instrument import scoreboard
        assert scoreboard.MAX_HOLD_HOURS_EQUITY > 360
        with self._conn() as conn:
            r = scoreboard.build_report(conn, universe="equities")
        assert r["max_hold_hours"] > 360

    def test_un_universo_inventado_falla_en_vez_de_devolver_todo(self):
        """Un typo que se traga el filtro devuelve la tabla entera con la etiqueta
        equivocada -- el peor resultado posible para este cambio."""
        from instrument import scoreboard
        with self._conn() as conn:
            with pytest.raises(ValueError):
                scoreboard.build_report(conn, universe="stocks")
