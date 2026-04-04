"""
test_market_intel.py — Tests para Phase 2: Market Intelligence

Cubre: ADX, BB Width, Regime Detection, Funding Rates, Liquidation Levels,
y la integracion de funding signal en calculate_confluence_score().

Todos los tests son self-contained (sin API calls reales).
"""

import os
import sys
import time
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

# Asegurar imports desde raiz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════════════════════════
# 1. ADX TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestADX:
    """Tests para calculate_adx en indicators.py."""

    def test_trending_data_high_adx(self, df_bull):
        from indicators import calculate_adx
        adx = calculate_adx(df_bull)
        assert adx > 15  # Trending data deberia mostrar ADX elevado

    def test_flat_data_lower_adx(self, df_flat):
        from indicators import calculate_adx
        adx = calculate_adx(df_flat)
        # Flat data deberia tener ADX mas bajo que trending
        adx_bull = calculate_adx(
            pd.DataFrame({
                'high': df_flat['high'].values * np.linspace(1, 1.5, len(df_flat)),
                'low': df_flat['low'].values * np.linspace(1, 1.5, len(df_flat)),
                'close': df_flat['close'].values * np.linspace(1, 1.5, len(df_flat)),
            })
        )
        # Strong trend should have higher ADX than flat
        assert adx < adx_bull

    def test_insufficient_data_returns_zero(self):
        from indicators import calculate_adx
        df = pd.DataFrame({'high': [1, 2, 3], 'low': [0.5, 1.5, 2.5], 'close': [0.8, 1.8, 2.8]})
        assert calculate_adx(df) == 0.0

    def test_adx_returns_float(self, df_bull):
        from indicators import calculate_adx
        adx = calculate_adx(df_bull)
        assert isinstance(adx, float)
        assert 0 <= adx <= 100

    def test_adx_with_different_periods(self, df_bull):
        from indicators import calculate_adx
        adx_14 = calculate_adx(df_bull, period=14)
        adx_28 = calculate_adx(df_bull, period=28)
        # Both should be valid positive numbers
        assert adx_14 > 0
        assert adx_28 > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. BB WIDTH TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBBWidth:
    """Tests para calculate_bb_width en indicators.py."""

    def test_bb_width_positive(self, df_bull):
        from indicators import calculate_bb_width
        width = calculate_bb_width(df_bull['close'])
        assert width > 0

    def test_bb_width_flat_is_smaller(self, df_flat):
        from indicators import calculate_bb_width
        width_flat = calculate_bb_width(df_flat['close'])
        # Flat data deberia tener bandas mas estrechas
        assert width_flat > 0
        assert width_flat < 0.50  # No deberia ser absurdamente grande

    def test_bb_width_insufficient_data(self):
        from indicators import calculate_bb_width
        short_prices = pd.Series([100, 101, 102])
        width = calculate_bb_width(short_prices)
        assert width == 0.0

    def test_bb_width_returns_float(self, df_bull):
        from indicators import calculate_bb_width
        width = calculate_bb_width(df_bull['close'])
        assert isinstance(width, float)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. REGIME DETECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegimeDetection:
    """Tests para detect_regime en market_intel.py."""

    def _reset_cache(self):
        import market_intel
        market_intel._CACHE["regime"] = {}

    def _mock_indicators(self, df, adx, bb_width, atr, ema):
        """Helper: crea mock de indicators para inyectar en sys.modules."""
        mock_ind = MagicMock()
        mock_ind.get_df.return_value = df
        mock_ind.calculate_adx.return_value = adx
        mock_ind.calculate_bb_width.return_value = bb_width
        mock_ind.calculate_atr.return_value = atr
        mock_ind.calculate_ema.return_value = ema
        return mock_ind

    def test_trending_up_regime(self, df_bull):
        self._reset_cache()
        ema_val = df_bull['close'].iloc[-1] * 0.95  # Price > EMA
        mock_ind = self._mock_indicators(df_bull, adx=30.0, bb_width=0.05, atr=5.0, ema=ema_val)

        import market_intel
        with patch.dict(sys.modules, {'indicators': mock_ind}):
            result = market_intel.detect_regime("TAO")
        assert result["regime"] == "TRENDING_UP"
        assert result["adx"] == 30.0

    def test_trending_down_regime(self, df_bear):
        self._reset_cache()
        ema_val = df_bear['close'].iloc[-1] * 1.20  # Price < EMA
        mock_ind = self._mock_indicators(df_bear, adx=28.0, bb_width=0.05, atr=5.0, ema=ema_val)

        import market_intel
        with patch.dict(sys.modules, {'indicators': mock_ind}):
            result = market_intel.detect_regime("TAO")
        assert result["regime"] == "TRENDING_DOWN"

    def test_ranging_regime(self, df_flat):
        self._reset_cache()
        ema_val = df_flat['close'].iloc[-1]
        mock_ind = self._mock_indicators(df_flat, adx=15.0, bb_width=0.015, atr=1.0, ema=ema_val)

        import market_intel
        with patch.dict(sys.modules, {'indicators': mock_ind}):
            result = market_intel.detect_regime("TAO")
        assert result["regime"] == "RANGING"

    def test_regime_caching(self, df_bull):
        self._reset_cache()
        ema_val = df_bull['close'].iloc[-1] * 0.95
        mock_ind = self._mock_indicators(df_bull, adx=30.0, bb_width=0.05, atr=5.0, ema=ema_val)

        import market_intel
        with patch.dict(sys.modules, {'indicators': mock_ind}):
            result1 = market_intel.detect_regime("TAO")
            result2 = market_intel.detect_regime("TAO")
        # Second call should return cached result
        assert result1["regime"] == result2["regime"]
        # get_df called only once due to cache
        assert mock_ind.get_df.call_count == 1

    def test_regime_error_returns_safe_default(self):
        self._reset_cache()
        mock_ind = MagicMock()
        mock_ind.get_df.side_effect = Exception("network error")

        import market_intel
        with patch.dict(sys.modules, {'indicators': mock_ind}):
            result = market_intel.detect_regime("TAO")
        assert result["regime"] == "TRENDING_UP"  # Safe default

    def test_regime_empty_df_returns_default(self):
        self._reset_cache()
        mock_ind = MagicMock()
        mock_ind.get_df.return_value = pd.DataFrame()

        import market_intel
        with patch.dict(sys.modules, {'indicators': mock_ind}):
            result = market_intel.detect_regime("TAO")
        assert result["regime"] == "TRENDING_UP"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. FUNDING RATES TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFundingRates:
    """Tests para funding rates en market_intel.py."""

    def _reset_cache(self):
        import market_intel
        market_intel._CACHE["funding"] = {"data": {}, "last_update": 0}

    def test_extreme_long_funding_confirms_short(self):
        """Rate > 0.05% con side SHORT → +1 (contrarian confirma)."""
        import market_intel
        funding_data = {"TAO": {"rate": 0.001, "annualized": 109.5}}
        signal = market_intel.get_funding_signal("TAO", "SHORT", funding_data)
        assert signal == 1

    def test_extreme_long_funding_penalizes_long(self):
        """Rate > 0.05% con side LONG → -1 (contrarian contradice)."""
        import market_intel
        funding_data = {"TAO": {"rate": 0.001, "annualized": 109.5}}
        signal = market_intel.get_funding_signal("TAO", "LONG", funding_data)
        assert signal == -1

    def test_extreme_short_funding_confirms_long(self):
        """Rate < -0.05% con side LONG → +1 (contrarian confirma)."""
        import market_intel
        funding_data = {"TAO": {"rate": -0.001, "annualized": -109.5}}
        signal = market_intel.get_funding_signal("TAO", "LONG", funding_data)
        assert signal == 1

    def test_extreme_short_funding_penalizes_short(self):
        """Rate < -0.05% con side SHORT → -1."""
        import market_intel
        funding_data = {"TAO": {"rate": -0.001, "annualized": -109.5}}
        signal = market_intel.get_funding_signal("TAO", "SHORT", funding_data)
        assert signal == -1

    def test_neutral_funding_returns_zero(self):
        """Rate normal → 0 (sin ajuste)."""
        import market_intel
        funding_data = {"TAO": {"rate": 0.0001, "annualized": 10.95}}
        signal = market_intel.get_funding_signal("TAO", "LONG", funding_data)
        assert signal == 0

    def test_missing_symbol_returns_zero(self):
        """Symbol no encontrado → 0."""
        import market_intel
        funding_data = {"BTC": {"rate": 0.001}}
        signal = market_intel.get_funding_signal("TAO", "LONG", funding_data)
        assert signal == 0

    def test_empty_funding_data_returns_zero(self):
        """Funding data vacio → 0."""
        import market_intel
        signal = market_intel.get_funding_signal("TAO", "LONG", {})
        assert signal == 0

    def test_funding_api_failure_returns_cached(self):
        """Error de API retorna cache anterior."""
        self._reset_cache()
        import market_intel
        # Pre-fill cache with old data
        market_intel._CACHE["funding"]["data"] = {"TAO": {"rate": 0.0001}}
        market_intel._CACHE["funding"]["last_update"] = 0  # Expired

        with patch.object(market_intel._binance_futures, 'fetch_funding_rates', side_effect=Exception("timeout")):
            result = market_intel.get_funding_rates(["TAO"])
            # Should return cached data
            assert "TAO" in result

    def test_funding_cache_hit(self):
        """Cache valido no hace API call."""
        self._reset_cache()
        import market_intel
        market_intel._CACHE["funding"]["data"] = {"TAO": {"rate": 0.0002}}
        market_intel._CACHE["funding"]["last_update"] = time.time()  # Fresh cache

        with patch.object(market_intel._binance_futures, 'fetch_funding_rates') as mock_fetch:
            result = market_intel.get_funding_rates(["TAO"])
            mock_fetch.assert_not_called()
            assert result["TAO"]["rate"] == 0.0002


# ═══════════════════════════════════════════════════════════════════════════════
# 5. LIQUIDATION LEVELS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestLiquidationLevels:
    """Tests para liquidation levels en market_intel.py."""

    def test_no_api_key_returns_unavailable(self):
        """Sin COINGLASS_API_KEY → graceful degradation."""
        import market_intel
        with patch.dict(os.environ, {}, clear=False):
            # Remove key if exists
            os.environ.pop("COINGLASS_API_KEY", None)
            result = market_intel.get_liquidation_levels("TAO")
            assert result["available"] is False
            assert result["reason"] == "no_api_key"

    def test_check_sl_near_liquidation_unavailable(self):
        """Sin data de liquidacion → warning=False."""
        import market_intel
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COINGLASS_API_KEY", None)
            result = market_intel.check_sl_near_liquidation("TAO", 295.0, "LONG")
            assert result["warning"] is False

    def test_api_failure_graceful(self):
        """Error de CoinGlass API → degradacion graceful."""
        import market_intel
        market_intel._CACHE["liquidations"] = {}  # Clear cache

        with patch.dict(os.environ, {"COINGLASS_API_KEY": "fake_key"}):
            mock_requests = MagicMock()
            mock_requests.get.side_effect = Exception("connection refused")
            with patch.dict(sys.modules, {'requests': mock_requests}):
                result = market_intel.get_liquidation_levels("TAO")
                assert result["available"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 6. CONFLUENCE SCORE WITH FUNDING INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfluenceWithFunding:
    """Tests de integracion: funding_signal en calculate_confluence_score."""

    def test_funding_adds_one_point(self):
        from strategies import calculate_confluence_score
        score_base = calculate_confluence_score(
            300, 30, 310, 290, 280, 7.9, "LONG", "Onda 3",
            funding_signal=0
        )
        score_with = calculate_confluence_score(
            300, 30, 310, 290, 280, 7.9, "LONG", "Onda 3",
            funding_signal=1
        )
        assert score_with == score_base + 1

    def test_funding_subtracts_one_point(self):
        from strategies import calculate_confluence_score
        score_base = calculate_confluence_score(
            300, 30, 310, 290, 280, 7.9, "LONG", "Onda 3",
            funding_signal=0
        )
        score_with = calculate_confluence_score(
            300, 30, 310, 290, 280, 7.9, "LONG", "Onda 3",
            funding_signal=-1
        )
        assert score_with == score_base - 1

    def test_funding_zero_no_change(self):
        from strategies import calculate_confluence_score
        score_base = calculate_confluence_score(
            300, 30, 310, 290, 280, 7.9, "LONG", "",
            funding_signal=0
        )
        score_with = calculate_confluence_score(
            300, 30, 310, 290, 280, 7.9, "LONG", "",
            funding_signal=0
        )
        assert score_base == score_with

    def test_max_score_capped_at_seven(self):
        from strategies import calculate_confluence_score
        # Max possible: RSI(2) + EMA(1) + BB(1) + USDT(1) + Elliott(1) + macro + SMC + funding
        score = calculate_confluence_score(
            300, 25, 310, 301, 280, 7.5, "LONG", "Onda 3",
            spy=450, ob_detected=True, funding_signal=1
        )
        assert score <= 7


# ═══════════════════════════════════════════════════════════════════════════════
# 7. HTML GENERATORS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHTMLGenerators:
    """Tests para HTML generators de Telegram."""

    def test_funding_html_with_data(self):
        import market_intel
        market_intel._CACHE["funding"]["data"] = {
            "TAO": {"rate": 0.001, "annualized": 109.5},
            "ETH": {"rate": -0.0003, "annualized": -32.85},
        }
        market_intel._CACHE["funding"]["last_update"] = time.time()

        html = market_intel.get_funding_html(["TAO", "ETH"])
        assert "FUNDING RATES" in html
        assert "TAO" in html
        assert "LONGS CROWDED" in html

    def test_funding_html_empty(self):
        import market_intel
        market_intel._CACHE["funding"]["data"] = {}
        market_intel._CACHE["funding"]["last_update"] = time.time()

        html = market_intel.get_funding_html(["TAO"])
        assert "FUNDING RATES" in html

    def test_regime_html_output(self):
        import market_intel
        # Pre-populate regime cache
        market_intel._CACHE["regime"]["TAO"] = {
            "result": {"regime": "TRENDING_UP", "adx": 30.0, "bb_width": 0.05, "atr_percentile": 5.0, "ema_200": 290, "price": 300},
            "last_update": time.time()
        }
        html = market_intel.get_regime_html(["TAO"])
        assert "MARKET REGIME" in html
        assert "TRENDING_UP" in html
        assert "TAO" in html

    def test_liquidations_html_no_key(self):
        import market_intel
        os.environ.pop("COINGLASS_API_KEY", None)
        html = market_intel.get_liquidations_html("TAO")
        assert "LIQUIDATION" in html
        assert "COINGLASS_API_KEY" in html
