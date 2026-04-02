"""
test_swing_targets.py — Specs para swing_bot.py

PROBLEMA QUE PREVIENE:
  El swing bot enviaba 1 solo target fijo (3%).
  Ahora debe enviar siempre TP1/TP2/TP3 basados en ATR.
  Estos tests fallan si alguien cambia los targets a porcentaje fijo.
"""
import math
import sys
import os
import pandas as pd
import numpy as np
import pytest

# Importar módulo bajo test directamente (sin red)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from swing_bot import calc_atr, build_alert, ATR_SL, ATR_TP1, ATR_TP2, ATR_TP3


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_df(n=50, atr_approx=8.0):
    """DataFrame mínimo con ATR controlado."""
    rng = np.random.default_rng(0)
    base = 300.0
    closes = base + np.cumsum(rng.normal(0, atr_approx * 0.5, n))
    highs  = closes + rng.uniform(atr_approx * 0.3, atr_approx * 0.7, n)
    lows   = closes - rng.uniform(atr_approx * 0.3, atr_approx * 0.7, n)
    df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
    return df


# ─── Tests: calc_atr ─────────────────────────────────────────────────────────

def test_calc_atr_returns_positive():
    """ATR debe ser siempre un número positivo."""
    df = _make_df(atr_approx=8.0)
    result = calc_atr(df)
    assert result > 0, "ATR debe ser positivo"


def test_calc_atr_scales_with_volatility():
    """ATR alto en mercado volátil, bajo en mercado quieto."""
    df_volatile = _make_df(n=50, atr_approx=20.0)
    df_quiet    = _make_df(n=50, atr_approx=2.0)
    assert calc_atr(df_volatile) > calc_atr(df_quiet), \
        "ATR debe ser mayor en mercado volátil"


def test_calc_atr_minimum_rows():
    """Con datos insuficientes (< 15 filas) debe seguir retornando un número."""
    df = _make_df(n=10, atr_approx=5.0)
    result = calc_atr(df)
    assert isinstance(result, float)
    assert not math.isnan(result)


# ─── Tests: build_alert ──────────────────────────────────────────────────────

DUMMY_ANALYSIS = "Análisis institucional sintético para testing."
KUMO = {"top": 310.0, "bottom": 295.0}


def _call_build(side="LONG", price=300.0, atr=8.0):
    return build_alert(
        symbol="ZEC/USDT", side=side, price=price, atr=atr,
        ai_bias="BULL" if side == "LONG" else "BEAR",
        kumo_status="BULL" if side == "LONG" else "BEAR",
        tk_cross="GOLDEN" if side == "LONG" else "DEAD",
        kumo_cloud=KUMO,
        analysis=DUMMY_ANALYSIS
    )


class TestBuildAlertReturnsThreeTargets:
    """El mensaje SIEMPRE debe contener TP1, TP2 y TP3."""

    def test_has_tp1(self):
        msg, *_ = _call_build()
        assert "TP1" in msg, "Falta TP1 en el mensaje"

    def test_has_tp2(self):
        msg, *_ = _call_build()
        assert "TP2" in msg, "Falta TP2 en el mensaje"

    def test_has_tp3(self):
        msg, *_ = _call_build()
        assert "TP3" in msg, "Falta TP3 en el mensaje"

    def test_has_sl(self):
        msg, *_ = _call_build()
        assert "SL" in msg, "Falta SL en el mensaje"

    def test_returns_five_values(self):
        result = _call_build()
        assert len(result) == 5, \
            "build_alert debe retornar (msg, sl, tp1, tp2, tp3)"


class TestTargetCalculationsLong:
    """Para LONG: TP1 < TP2 < TP3 y SL < entry."""

    def setup_method(self):
        self.price = 300.0
        self.atr   = 10.0
        self.msg, self.sl, self.tp1, self.tp2, self.tp3 = _call_build(
            side="LONG", price=self.price, atr=self.atr
        )

    def test_tp1_above_entry(self):
        assert self.tp1 > self.price, "TP1 debe estar por encima del precio de entrada"

    def test_tp2_above_tp1(self):
        assert self.tp2 > self.tp1, "TP2 debe estar por encima de TP1"

    def test_tp3_above_tp2(self):
        assert self.tp3 > self.tp2, "TP3 debe estar por encima de TP2"

    def test_sl_below_entry(self):
        assert self.sl < self.price, "SL debe estar por debajo del precio de entrada"

    def test_tp1_equals_atr_formula(self):
        expected_tp1 = round(self.price + self.atr * ATR_TP1, 4)
        assert abs(self.tp1 - expected_tp1) < 0.01, \
            f"TP1 esperado {expected_tp1}, obtenido {self.tp1}"

    def test_tp2_equals_atr_formula(self):
        expected_tp2 = round(self.price + self.atr * ATR_TP2, 4)
        assert abs(self.tp2 - expected_tp2) < 0.01, \
            f"TP2 esperado {expected_tp2}, obtenido {self.tp2}"

    def test_tp3_equals_atr_formula(self):
        expected_tp3 = round(self.price + self.atr * ATR_TP3, 4)
        assert abs(self.tp3 - expected_tp3) < 0.01, \
            f"TP3 esperado {expected_tp3}, obtenido {self.tp3}"

    def test_sl_respects_minimum_pct(self):
        min_sl = self.price * (1 - 0.01)  # MIN_SL_PCT = 1%
        assert self.sl <= self.price - (self.price * 0.005), \
            "SL debe ser al menos 0.5% abajo del entry"

    def test_no_fixed_percentage(self):
        """Verifica que los targets NO son porcentajes fijos (3%, 6%, etc.)."""
        tp1_pct = (self.tp1 - self.price) / self.price * 100
        tp2_pct = (self.tp2 - self.price) / self.price * 100
        # Con ATR=10 y price=300, un 3% fijo daría exactamente 9.0 — no debe pasar
        assert abs(tp1_pct - 3.0) > 0.5, \
            "TP1 parece ser un porcentaje fijo (3%) en lugar de basado en ATR"
        assert abs(tp2_pct - 6.0) > 0.5, \
            "TP2 parece ser un porcentaje fijo (6%) en lugar de basado en ATR"


class TestTargetCalculationsShort:
    """Para SHORT: TP1 > TP2 > TP3 (todos por debajo del entry) y SL > entry."""

    def setup_method(self):
        self.price = 300.0
        self.atr   = 10.0
        self.msg, self.sl, self.tp1, self.tp2, self.tp3 = _call_build(
            side="SHORT", price=self.price, atr=self.atr
        )

    def test_tp1_below_entry(self):
        assert self.tp1 < self.price, "TP1 SHORT debe estar por debajo del entry"

    def test_tp2_below_tp1(self):
        assert self.tp2 < self.tp1, "TP2 SHORT debe ser más bajo que TP1"

    def test_tp3_below_tp2(self):
        assert self.tp3 < self.tp2, "TP3 SHORT debe ser más bajo que TP2"

    def test_sl_above_entry(self):
        assert self.sl > self.price, "SL SHORT debe estar por encima del entry"


class TestAlertContent:
    """El mensaje debe incluir información operacional clara."""

    def setup_method(self):
        self.msg, *_ = _call_build(side="LONG", price=248.08, atr=8.24)

    def test_contains_symbol(self):
        assert "ZEC/USDT" in self.msg

    def test_contains_entry_price(self):
        assert "248" in self.msg, "El precio de entrada debe aparecer en el mensaje"

    def test_contains_position_sizing_instructions(self):
        """Debe indicar qué porcentaje cerrar en cada target."""
        assert "50%" in self.msg, "Falta instrucción de 50% en TP1"
        assert "30%" in self.msg, "Falta instrucción de 30% en TP2"
        assert "20%" in self.msg, "Falta instrucción de 20% en TP3 (runner)"

    def test_contains_breakeven_instruction(self):
        assert "breakeven" in self.msg.lower() or "BE" in self.msg, \
            "Debe indicar mover SL a breakeven en TP1"

    def test_contains_rr_ratio(self):
        assert "R:R" in self.msg, "Debe mostrar el ratio R:R para cada target"

    def test_contains_atr_value(self):
        assert "ATR" in self.msg, "Debe mostrar el ATR usado"

    def test_analysis_truncated_at_600_chars(self):
        """Análisis largo no debe desbordarse."""
        long_analysis = "X " * 400  # 800 chars
        msg, *_ = build_alert(
            "ZEC/USDT", "LONG", 300.0, 8.0,
            "BULL", "BULL", "GOLDEN", KUMO, long_analysis
        )
        # El análisis en el msg no debe superar 650 chars (600 + "..." + margen)
        analysis_start = msg.find("RACIONAL") + len("RACIONAL INSTITUCIONAL:</b>\n")
        analysis_end   = msg.find("\n\n" + "─")
        if analysis_start > 0 and analysis_end > analysis_start:
            extracted = msg[analysis_start:analysis_end]
            assert len(extracted) <= 650, \
                f"Análisis demasiado largo en el mensaje: {len(extracted)} chars"

    def test_contains_vix_risk_warning(self):
        assert "VIX" in self.msg, "Debe incluir aviso de gestión VIX/DXY"


class TestRiskRewardRatios:
    """R:R debe ser consistente con los multiplicadores definidos en config."""

    def test_long_rr1_matches_config(self):
        _, sl, tp1, _, _ = _call_build(side="LONG", price=300.0, atr=10.0)
        rr1_actual = (tp1 - 300.0) / (300.0 - sl)
        rr1_expected = ATR_TP1 / ATR_SL
        assert abs(rr1_actual - rr1_expected) < 0.05, \
            f"R:R TP1 esperado {rr1_expected:.2f}, obtenido {rr1_actual:.2f}"

    def test_long_rr2_matches_config(self):
        _, sl, _, tp2, _ = _call_build(side="LONG", price=300.0, atr=10.0)
        rr2_actual = (tp2 - 300.0) / (300.0 - sl)
        rr2_expected = ATR_TP2 / ATR_SL
        assert abs(rr2_actual - rr2_expected) < 0.05

    def test_long_rr3_matches_config(self):
        _, sl, _, _, tp3 = _call_build(side="LONG", price=300.0, atr=10.0)
        rr3_actual = (tp3 - 300.0) / (300.0 - sl)
        rr3_expected = ATR_TP3 / ATR_SL
        assert abs(rr3_actual - rr3_expected) < 0.05
