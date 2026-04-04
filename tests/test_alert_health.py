"""
test_alert_health.py — Specs de salud del sistema de alertas

PROBLEMA QUE PREVIENE:
  Las alertas dejan de llegar sin ningún error visible.
  Causas conocidas: cooldown atascado, filtro demasiado estricto,
  posición abierta bloqueando nuevas señales, Telegram silencioso.

Estos tests verifican:
  1. Que el cooldown no bloquee alertas legítimas después de su tiempo
  2. Que position guard libere posiciones correctamente
  3. Que el mensaje de Telegram tiene formato HTML válido
  4. Que tracker registra la alerta con alert_type correcto
  5. Que confluence_score produce valores en rango válido
"""
import sys
import os
import time
import sqlite3
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ─── Test: Cooldown del Swing Bot ─────────────────────────────────────────────

class TestSwingCooldown:
    """El cooldown debe liberar el símbolo después de 4H."""

    def setup_method(self):
        # Importar con estado limpio
        import importlib
        import swing_bot
        importlib.reload(swing_bot)
        self.bot = swing_bot

    def test_no_cooldown_on_fresh_start(self):
        """Un símbolo nunca enviado no debe estar en cooldown."""
        assert not self.bot._in_cooldown("ZEC/USDT"), \
            "ZEC no debería estar en cooldown al iniciar"

    def test_cooldown_active_after_alert(self):
        """Después de enviar, el símbolo debe estar bloqueado."""
        self.bot._set_cooldown("ZEC/USDT")
        assert self.bot._in_cooldown("ZEC/USDT"), \
            "ZEC debe estar en cooldown justo después de enviar alerta"

    def test_cooldown_expires(self):
        """Simulamos que el cooldown ya pasó manipulando el timestamp."""
        import swing_bot
        swing_bot._last_alert["ZEC/USDT"] = time.time() - (3600 * 5)  # 5H atrás
        assert not swing_bot._in_cooldown("ZEC/USDT"), \
            "El cooldown de 4H ya expiró — ZEC debe estar libre"

    def test_different_symbols_independent(self):
        """El cooldown de TAO no debe afectar a ZEC."""
        self.bot._set_cooldown("TAO/USDT")
        assert not self.bot._in_cooldown("ZEC/USDT"), \
            "Cooldown de TAO no debe bloquear ZEC"


# ─── Test: Position Guard (scalp_alert_bot) ───────────────────────────────────

class TestPositionGuard:
    """is_position_open / open_position / close_position deben funcionar."""

    def setup_method(self):
        import scalp_alert_bot
        # Limpiar posiciones antes de cada test
        scalp_alert_bot.OPEN_POSITIONS.clear()
        self.bot = scalp_alert_bot

    def test_no_position_on_start(self):
        assert not self.bot.is_position_open("BTC", "LONG"), \
            "No debe haber posición abierta al inicio"

    def test_open_registers_position(self):
        self.bot.open_position("BTC", "LONG")
        assert self.bot.is_position_open("BTC", "LONG"), \
            "Después de open_position debe detectarse como abierta"

    def test_close_releases_position(self):
        self.bot.open_position("BTC", "LONG")
        self.bot.close_position("BTC", "LONG")
        assert not self.bot.is_position_open("BTC", "LONG"), \
            "Después de close_position debe estar libre"

    def test_position_ttl_expires(self):
        """Una posición abierta hace más de 1H debe considerarse expirada."""
        import scalp_alert_bot
        key = "TAO_LONG"
        scalp_alert_bot.OPEN_POSITIONS[key] = time.time() - (3600 + 60)  # 1H + 1min
        assert not self.bot.is_position_open("TAO", "LONG"), \
            "Posición con TTL expirado debe reportar como cerrada"

    def test_different_symbols_independent(self):
        self.bot.open_position("ZEC", "LONG")
        assert not self.bot.is_position_open("BTC", "LONG"), \
            "Posición de ZEC no debe bloquear BTC"

    def test_different_sides_independent(self):
        self.bot.open_position("BTC", "LONG")
        assert not self.bot.is_position_open("BTC", "SHORT"), \
            "Posición LONG no debe bloquear SHORT del mismo símbolo"


# ─── Test: Confluence Score ────────────────────────────────────────────────────

class TestConfluenceScore:
    """El score debe estar siempre entre 0 y 6."""

    def setup_method(self):
        from scalp_alert_bot import calculate_confluence_score
        self.score = calculate_confluence_score

    def _score(self, **kwargs):
        defaults = dict(p=300, rsi=35, bb_u=320, bb_l=285,
                        ema_200=290, usdt_d=8.0, side="LONG",
                        elliott="", spy=0.0, oil=0.0, ob_detected=False)
        defaults.update(kwargs)
        return self.score(**defaults)

    def test_score_in_valid_range(self):
        s = self._score()
        assert 0 <= s <= 7, f"Score fuera de rango: {s}"

    def test_extreme_bull_case(self):
        """Condiciones perfectas para LONG deben dar score alto (>= 4)."""
        s = self._score(rsi=28, p=286, ema_200=280, bb_l=287,
                        usdt_d=7.9, elliott="Onda 3 alcista")
        assert s >= 4, f"Condiciones perfectas LONG deben dar >=4, obtuvo {s}"

    def test_correction_penalizes_score(self):
        """Corrección Elliott debe reducir el score."""
        s_normal    = self._score(rsi=35)
        s_correction = self._score(rsi=35, elliott="Corrección ABC")
        assert s_correction <= s_normal, \
            "Elliott Corrección debe penalizar el score"

    def test_score_never_negative(self):
        """Score nunca debe ser negativo aunque todas las condiciones fallen."""
        s = self._score(rsi=65, p=250, ema_200=300, usdt_d=8.2,
                        elliott="Corrección Correctiva profunda")
        assert s >= 0, f"Score no puede ser negativo: {s}"

    def test_score_never_above_7(self):
        """Score nunca debe superar 7 (Phase 2: +1 funding signal)."""
        s = self._score(rsi=20, p=284, ema_200=280, bb_l=285,
                        usdt_d=7.5, elliott="Onda 3 alcista",
                        ob_detected=True, spy=500.0, funding_signal=1)
        assert s <= 7, f"Score no puede superar 7: {s}"

    def test_rsi_extreme_gives_bonus(self):
        """RSI <= 30 debe dar más puntos que RSI 35-40."""
        s_extreme = self._score(rsi=25)
        s_mild    = self._score(rsi=38)
        assert s_extreme > s_mild, "RSI más extremo debe dar score más alto"


# ─── Test: Tracker DB ────────────────────────────────────────────────────────

class TestTrackerAlertType:
    """alert_type debe guardarse y recuperarse correctamente."""

    def setup_method(self):
        # Base de datos temporal para tests
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        import tracker as t
        self._orig_db = t.DB_FILE
        t.DB_FILE = self.tmp.name
        t.init_db()
        self.tracker = t

    def teardown_method(self):
        self.tracker.DB_FILE = self._orig_db
        os.unlink(self.tmp.name)

    def test_log_trade_saves_alert_type(self):
        self.tracker.log_trade(
            "BTC", "LONG", 50000, 52500, 55000, 48000,
            None, "V1-TECH", 38.0, "BB Lower", 800.0, "", 4,
            alert_type="v1_long"
        )
        conn = sqlite3.connect(self.tmp.name)
        row  = conn.execute("SELECT alert_type FROM trades WHERE symbol='BTC'").fetchone()
        conn.close()
        assert row is not None, "Trade no fue guardado"
        assert row[0] == "v1_long", f"alert_type incorrecto: {row[0]}"

    def test_get_alert_stats_aggregates_correctly(self):
        for i in range(3):
            self.tracker.log_trade(
                "TAO", "LONG", 300+i, 330, 360, 280,
                None, "V1-TECH", 40.0, "", 5.0, "", 4,
                alert_type="v1_long"
            )
            # Simular resultado
            conn = sqlite3.connect(self.tmp.name)
            status = "FULL_WON" if i < 2 else "LOST"
            conn.execute(f"UPDATE trades SET status='{status}' WHERE symbol='TAO' AND entry_price={300+i}")
            conn.commit()
            conn.close()

        stats = self.tracker.get_alert_stats()
        tao_stat = next((s for s in stats if s["alert_type"] == "v1_long"), None)
        assert tao_stat is not None, "No se encontró estadística para v1_long"
        assert tao_stat["wins"] == 2
        assert tao_stat["losses"] == 1
        assert tao_stat["win_rate"] == pytest.approx(66.7, abs=0.2)

    def test_unknown_alert_type_still_saved(self):
        """Trades sin alert_type explícito deben guardarse como 'unknown'."""
        self.tracker.log_trade(
            "ZEC", "LONG", 250, 270, 290, 235, None
        )
        conn = sqlite3.connect(self.tmp.name)
        row  = conn.execute("SELECT alert_type FROM trades WHERE symbol='ZEC'").fetchone()
        conn.close()
        assert row[0] == "unknown", f"Debería ser 'unknown', obtuvo: {row[0]}"


# ─── Test: Mensaje Telegram ───────────────────────────────────────────────────

class TestTelegramMessageFormat:
    """El HTML del mensaje no debe tener tags sin cerrar."""

    def _check_balanced(self, msg: str):
        """Verifica que cada <b> tenga su </b> y cada <code> su </code>."""
        for tag in ["b", "code", "i"]:
            opens  = msg.count(f"<{tag}>")
            closes = msg.count(f"</{tag}>")
            assert opens == closes, \
                f"Tag <{tag}> desbalanceado: {opens} abiertos, {closes} cerrados"

    def test_swing_alert_html_balanced(self):
        from swing_bot import build_alert
        msg, *_ = build_alert(
            "ZEC/USDT", "LONG", 300.0, 8.0,
            "BULL", "BULL", "GOLDEN",
            {"top": 310.0, "bottom": 295.0},
            "Análisis de prueba para verificar HTML."
        )
        self._check_balanced(msg)

    def test_no_empty_price_tags(self):
        """No debe haber <code></code> vacíos."""
        from swing_bot import build_alert
        msg, *_ = build_alert(
            "TAO/USDT", "SHORT", 300.0, 10.0,
            "BEAR", "BEAR", "DEAD",
            {"top": 310.0, "bottom": 295.0},
            "Test SHORT."
        )
        assert "<code></code>" not in msg, "Hay tags <code> vacíos en el mensaje"

    def test_price_values_not_zero(self):
        """TP1/TP2/TP3/SL en el mensaje no deben ser 0.00."""
        from swing_bot import build_alert
        msg, sl, tp1, tp2, tp3 = build_alert(
            "ZEC/USDT", "LONG", 300.0, 8.0,
            "BULL", "BULL", "GOLDEN",
            {"top": 310.0, "bottom": 295.0}, "Test"
        )
        for label, val in [("SL", sl), ("TP1", tp1), ("TP2", tp2), ("TP3", tp3)]:
            assert val > 0, f"{label} es cero o negativo: {val}"
