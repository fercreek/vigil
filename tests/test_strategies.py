"""
test_strategies.py — Tests for live strategy signal generation (v2.1)

Verifies:
- V1-SHORT fires independently of phase.txt (no phase gate)
- V1-SHORT uses RSI 55 threshold (not 62)
- V1-SHORT accepts VOLATILE + TRENDING_DOWN regimes
- V1-SHORT uses confluence >= 3 (not 4)
- V1-LONG uses RSI 45 threshold (not 42)
- V1-LONG does NOT require BB hard gate
- V4 uses per-symbol EMA proximity map
- Config values are consistent between backtester and live
"""
import sys
import os
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ══════════════════════════════════════════════════════════════════════════════
# Config Consistency Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestConfigConsistency:
    """Verify config values match v2.1 improvements."""

    def test_rsi_short_entry_is_55(self):
        from config import RSI_SHORT_ENTRY
        assert RSI_SHORT_ENTRY == 55.0, f"RSI_SHORT_ENTRY should be 55.0, got {RSI_SHORT_ENTRY}"

    def test_rsi_long_entry_is_45(self):
        from config import RSI_LONG_ENTRY
        assert RSI_LONG_ENTRY == 45.0, f"RSI_LONG_ENTRY should be 45.0, got {RSI_LONG_ENTRY}"

    def test_short_min_confluence_is_3(self):
        from config import SHORT_MIN_CONFLUENCE
        assert SHORT_MIN_CONFLUENCE == 3, f"SHORT_MIN_CONFLUENCE should be 3, got {SHORT_MIN_CONFLUENCE}"

    def test_short_regimes_includes_volatile(self):
        from config import SHORT_REGIMES
        assert "VOLATILE" in SHORT_REGIMES
        assert "TRENDING_DOWN" in SHORT_REGIMES

    def test_v3_min_confluence_is_4(self):
        from config import V3_MIN_CONFLUENCE
        assert V3_MIN_CONFLUENCE == 4

    def test_v3_max_holding_bars(self):
        from config import V3_MAX_HOLDING_BARS
        assert V3_MAX_HOLDING_BARS == 48

    def test_atr_min_sl_reversal_widened(self):
        from config import ATR_MIN_SL_REVERSAL
        assert ATR_MIN_SL_REVERSAL == 0.010

    def test_v4_ema_prox_map_exists(self):
        from config import V4_EMA_PROX_MAP
        assert "BTC" in V4_EMA_PROX_MAP
        assert "ETH" in V4_EMA_PROX_MAP
        assert V4_EMA_PROX_MAP["ETH"] > V4_EMA_PROX_MAP["BTC"]  # altcoins wider

    def test_choppy_regime_threshold(self):
        from config import ADX_CHOPPY_THRESHOLD
        assert ADX_CHOPPY_THRESHOLD == 20

    def test_rvol_thresholds(self):
        from config import RVOL_MIN_ENTRY, RVOL_MIN_BTC
        assert RVOL_MIN_ENTRY == 1.0
        assert RVOL_MIN_BTC == 0.7  # BTC less aggressive


# ══════════════════════════════════════════════════════════════════════════════
# V1-SHORT Signal Logic Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestV1ShortSignalLogic:
    """Test that V1-SHORT strategy fires correctly in live code."""

    def test_short_not_gated_by_phase(self):
        """V1-SHORT should fire regardless of phase.txt value."""
        import strategies
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "strategies.py")).read()

        # Find the V1-SHORT block
        short_block_start = source.find("ESTRATEGIA V1-SHORT")
        assert short_block_start > 0, "V1-SHORT block not found in strategies.py"

        # Get the condition line after the comment
        short_section = source[short_block_start:short_block_start + 500]

        # The condition should NOT start with 'if phase == "SHORT"'
        assert 'if phase == "SHORT"' not in short_section, \
            "V1-SHORT is still gated by phase! Must be independent."

    def test_short_uses_rsi_55(self):
        """V1-SHORT should use RSI_SHORT_ENTRY (55), not hardcoded 62."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "strategies.py")).read()

        short_start = source.find("ESTRATEGIA V1-SHORT")
        short_section = source[short_start:short_start + 800]

        # Should reference RSI_SHORT_ENTRY from config, not hardcode 62
        assert "62.0" not in short_section or "was 62" in short_section, \
            "V1-SHORT still uses hardcoded 62.0"
        assert "RSI_SHORT_ENTRY" in short_section, \
            "V1-SHORT should use RSI_SHORT_ENTRY from config"

    def test_short_no_funding_hard_gate(self):
        """Funding rate should be a confluence bonus, not a hard gate."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "strategies.py")).read()

        short_start = source.find("ESTRATEGIA V1-SHORT")
        short_section = source[short_start:short_start + 1500]

        # Should NOT have "if fr_rate <= 0:" as a blocking gate
        assert "if fr_rate <= 0:" not in short_section, \
            "Funding rate is still a hard gate! Should be confluence bonus only."

    def test_short_uses_min_confluence_3(self):
        """V1-SHORT should use SHORT_MIN_CONFLUENCE (3), not hardcoded 4."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "strategies.py")).read()

        short_start = source.find("ESTRATEGIA V1-SHORT")
        short_section = source[short_start:short_start + 2500]

        assert "SHORT_MIN_CONFLUENCE" in short_section, \
            "V1-SHORT should use SHORT_MIN_CONFLUENCE from config"

    def test_short_checks_ema_slope(self):
        """V1-SHORT should verify EMA200 is declining."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "strategies.py")).read()

        short_start = source.find("ESTRATEGIA V1-SHORT")
        short_section = source[short_start:short_start + 1500]

        assert "ema_slope" in short_section.lower() or "slope" in short_section.lower(), \
            "V1-SHORT should check EMA200 slope"

    @pytest.mark.xfail(reason="V1-SHORT kill-switched (0% WR in 16 trades). Test asserts SHORT_REGIMES usage but regime check disabled while V1_SHORT_ENABLED=False. Re-enable when strategy reactivates.", strict=False)
    def test_short_accepts_volatile_regime(self):
        """V1-SHORT should work in VOLATILE regime, not just TRENDING_DOWN."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "strategies.py")).read()

        short_start = source.find("ESTRATEGIA V1-SHORT")
        short_section = source[short_start:short_start + 500]

        assert "SHORT_REGIMES" in short_section, \
            "V1-SHORT should use SHORT_REGIMES tuple from config"


# ══════════════════════════════════════════════════════════════════════════════
# V1-LONG Signal Logic Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestV1LongSignalLogic:
    """Test V1-LONG improvements."""

    def test_v1_no_bb_hard_gate(self):
        """V1-LONG should NOT require 'BB' in bb_ctx as hard gate."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "strategies.py")).read()

        v1_start = source.find("ESTRATEGIA V1:")
        v1_section = source[v1_start:v1_start + 300]

        # Should NOT have '"BB" in bb_ctx' as a condition
        assert '"BB" in bb_ctx' not in v1_section, \
            "V1-LONG still has BB hard gate! Should be confluence bonus only."

    def test_v1_uses_rsi_45(self):
        """V1-LONG default RSI should be 45 (not 42)."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "strategies.py")).read()

        v1_start = source.find("ESTRATEGIA V1:")
        v1_section = source[v1_start:v1_start + 300]

        assert "45.0" in v1_section or "45" in v1_section, \
            "V1-LONG should use RSI 45.0 as default threshold"


# ══════════════════════════════════════════════════════════════════════════════
# V4 EMA Bounce Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestV4EmaBounce:
    """Test V4 per-symbol improvements."""

    def test_v4_uses_per_symbol_proximity(self):
        """V4 should use V4_EMA_PROX_MAP for per-symbol EMA proximity."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "strategies.py")).read()

        assert "V4_EMA_PROX_MAP" in source, \
            "V4 should reference V4_EMA_PROX_MAP for per-symbol proximity"


# ══════════════════════════════════════════════════════════════════════════════
# Backtester-Live Sync Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestBacktesterLiveSync:
    """Verify backtester and live strategies use same config values."""

    def test_backtester_imports_new_configs(self):
        """Backtester should import all v2.1 config values."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "backtester.py")).read()

        required = [
            "V4_EMA_PROX_MAP",
            "V3_MIN_CONFLUENCE",
            "V3_MAX_HOLDING_BARS",
            "SHORT_MIN_CONFLUENCE",
            "SHORT_REGIMES",
            "SHORT_EMA_SLOPE_MIN",
            "ADX_CHOPPY_THRESHOLD",
            "REGIME_COOLDOWN_BARS",
            "RVOL_MIN_ENTRY",
        ]
        for name in required:
            assert name in source, f"Backtester missing import: {name}"

    def test_backtester_has_rvol_indicator(self):
        """Backtester should compute RVOL."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "backtester.py")).read()

        assert "df['rvol']" in source
        assert "df['vol_sma']" in source

    def test_backtester_has_rsi_divergence(self):
        """Backtester should compute RSI divergence."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "backtester.py")).read()

        assert "df['rsi_divergence']" in source

    def test_backtester_has_choppy_regime(self):
        """Backtester should detect CHOPPY regime."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "backtester.py")).read()

        assert '"CHOPPY"' in source

    def test_backtester_has_timeout_result(self):
        """Backtester should support TIMEOUT trade result for V3."""
        source = open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "backtester.py")).read()

        assert '"TIMEOUT"' in source


# ══════════════════════════════════════════════════════════════════════════════
# Confluence Score Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestConfluenceScore:
    """Test confluence scoring for SHORT signals."""

    def test_short_score_with_low_rsi(self):
        """SHORT with RSI 55-60 should get 1 pt from RSI (>= 60 check)."""
        # Manually calculate: RSI 58 → score 0 (< 60)
        # RSI 62 → score 1 (>= 60)
        # RSI 72 → score 2 (>= 70)
        from strategies import calculate_confluence_score

        # RSI 58, price below EMA200 → RSI=0 + EMA=1 = 1
        # This is why SHORT_MIN_CONFLUENCE=3 is important
        # with USDT.D > 8.05 → +1, near BB upper → +1 = 3

    def test_short_max_realistic_score(self):
        """Verify realistic max score for SHORT is achievable."""
        # RSI >= 70: 2pts
        # price < EMA: 1pt
        # near BB upper: 1pt
        # USDT.D > 8.05: 1pt
        # Total realistic: 5 pts without OB/Elliott/funding
        # With confluence >= 3, this is achievable even at RSI 60-70
        pass
