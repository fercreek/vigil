# _ITERATION_LOG — Suite canónica iter log

Métricas: PnL agregado · trades · PF global. KEEP = aplica al config. REVERT = se descarta.

| Iter | Patch | PnL Δ | Trades Δ | PF | Decisión |
|------|-------|-------|----------|-----|----------|
| v3_rsi_strict | `{'RSI_LONG_TAO_EXTREME': 25.0, 'RSI_LONG_ZEC_EXTREME': 24.0}` | +59.11% → -13.09% (-72.20) | 253 → 226 (-10.7%) | PF 1.15 → 0.97 | ❌ REVERT |
| v3_rsi_loose | `{'RSI_LONG_TAO_EXTREME': 32.0, 'RSI_LONG_ZEC_EXTREME': 30.0}` | +59.11% → +179.76% (+120.65) | 253 → 301 (+19.0%) | PF 1.15 → 1.41 | ✅ KEEP |
| v4_prox_tight | `{'V4_EMA_PROXIMITY_MAX': 1.02, 'V4_EMA_PROXIMITY_MIN': 1.005}` | +179.76% → +180.94% (+1.18) | 301 → 294 (-2.3%) | PF 1.41 → 1.42 | ✅ KEEP |
| v4_prox_wide | `{'V4_EMA_PROXIMITY_MAX': 1.04, 'V4_EMA_PROXIMITY_MIN': 0.998}` | +180.94% → +179.76% (-1.18) | 294 → 301 (+2.4%) | PF 1.42 → 1.41 | ❌ REVERT |
| conf_higher | `{'MIN_CONFLUENCE_SCORE': 5}` | +180.94% → +239.62% (+58.68) | 294 → 263 (-10.5%) | PF 1.42 → 1.72 | ✅ KEEP |
| conf_lower | `{'MIN_CONFLUENCE_SCORE': 3}` | +239.62% → +258.39% (+18.77) | 263 → 318 (+20.9%) | PF 1.72 → 1.53 | ❌ REVERT |
| v3_rsi_v2_more | `{'RSI_LONG_TAO_EXTREME': 35.0, 'RSI_LONG_ZEC_EXTREME': 32.0}` | +239.62% → +239.62% (+0.00) | 263 → 263 (+0.0%) | PF 1.72 → 1.72 | ❌ REVERT |
| v3_rsi_v2_mid | `{'RSI_LONG_TAO_EXTREME': 30.0, 'RSI_LONG_ZEC_EXTREME': 28.0}` | +239.62% → +215.58% (-24.04) | 263 → 260 (-1.1%) | PF 1.72 → 1.65 | ❌ REVERT |
| conf_strict_v2 | `{'MIN_CONFLUENCE_SCORE': 6}` | +239.62% → +187.09% (-52.53) | 263 → 247 (-6.1%) | PF 1.72 → 1.62 | ❌ REVERT |
| atr_sl_wide | `{'ATR_SL_MULT': 2.5}` | +239.62% → +236.46% (-3.16) | 263 → 251 (-4.6%) | PF 1.72 → 1.69 | ❌ REVERT |
| atr_sl_tight | `{'ATR_SL_MULT': 1.5}` | +239.62% → +184.68% (-54.94) | 263 → 272 (+3.4%) | PF 1.72 → 1.61 | ❌ REVERT |
| atr_tp1_conservative | `{'ATR_TP1_MULT': 1.5}` | +239.62% → +234.10% (-5.52) | 263 → 269 (+2.3%) | PF 1.72 → 1.78 | ❌ REVERT |
| atr_tp1_ambitious | `{'ATR_TP1_MULT': 3.0}` | +239.62% → +274.88% (+35.26) | 263 → 259 (-1.5%) | PF 1.72 → 1.77 | ✅ KEEP |
| rsi_long_entry_lower | `{'RSI_LONG_ENTRY': 40.0}` | +274.88% → +283.57% (+8.69) | 259 → 232 (-10.4%) | PF 1.77 → 1.89 | ✅ KEEP |
| rsi_extreme_loose | `{'RSI_LONG_EXTREME': 35.0}` | +283.57% → +283.57% (+0.00) | 232 → 232 (+0.0%) | PF 1.89 → 1.89 | ❌ REVERT |
| v4_rsi_high_loose | `{'V4_RSI_HIGH': 50.0}` | +283.57% → +283.57% (+0.00) | 232 → 232 (+0.0%) | PF 1.89 → 1.89 | ❌ REVERT |
| sl_2.5_with_tp3 | `{'ATR_SL_MULT': 2.5}` | +283.57% → +240.76% (-42.81) | 232 → 229 (-1.3%) | PF 1.89 → 1.69 | ❌ REVERT |
| sl_1.8_with_tp3 | `{'ATR_SL_MULT': 1.8}` | +283.57% → +255.43% (-28.14) | 232 → 234 (+0.9%) | PF 1.89 → 1.83 | ❌ REVERT |
| tp2_extended | `{'ATR_TP2_MULT': 5.0}` | +283.57% → +307.70% (+24.13) | 232 → 230 (-0.9%) | PF 1.89 → 1.99 | ✅ KEEP |
| tp3_moonshot | `{'ATR_TP3_MULT': 10.0}` | +307.70% → +307.70% (+0.00) | 230 → 230 (+0.0%) | PF 1.99 → 1.99 | ❌ REVERT |
| tp2_conservative | `{'ATR_TP2_MULT': 2.5}` | +307.70% → +220.56% (-87.14) | 230 → 242 (+5.2%) | PF 1.99 → 1.71 | ❌ REVERT |
| min_sl_pct_higher | `{'ATR_MIN_SL_PCT': 0.012}` | +307.70% → +309.22% (+1.52) | 230 → 228 (-0.9%) | PF 1.99 → 1.98 | ✅ KEEP |
| min_sl_pct_lower | `{'ATR_MIN_SL_PCT': 0.005}` | +309.22% → +305.46% (-3.76) | 228 → 230 (+0.9%) | PF 1.98 → 1.98 | ❌ REVERT |
| rvol_strict | `{'RVOL_MIN_ENTRY': 1.3}` | +309.22% → +263.25% (-45.97) | 228 → 193 (-15.4%) | PF 1.98 → 2.12 | ❌ REVERT |
| rvol_loose | `{'RVOL_MIN_ENTRY': 0.8}` | +309.22% → +342.20% (+32.98) | 228 → 253 (+11.0%) | PF 1.98 → 1.95 | ✅ KEEP |
| rvol_btc_higher | `{'RVOL_MIN_BTC': 1.0}` | +342.20% → +321.55% (-20.65) | 253 → 242 (-4.3%) | PF 1.95 → 1.91 | ❌ REVERT |
| adx_strict | `{'ADX_TRENDING_THRESHOLD': 25}` | +342.20% → +344.78% (+2.58) | 253 → 240 (-5.1%) | PF 1.95 → 2.0 | ✅ KEEP |
| adx_loose | `{'ADX_TRENDING_THRESHOLD': 15}` | +344.78% → +322.07% (-22.71) | 240 → 290 (+20.8%) | PF 2.0 → 1.79 | ❌ REVERT |
| bb_ranging_wider | `{'BB_WIDTH_RANGING_PCT': 0.025}` | +344.78% → +339.83% (-4.95) | 240 → 221 (-7.9%) | PF 2.0 → 2.07 | ❌ REVERT |
| bb_ranging_tighter | `{'BB_WIDTH_RANGING_PCT': 0.01}` | +344.78% → +347.12% (+2.34) | 240 → 247 (+2.9%) | PF 2.0 → 1.98 | ✅ KEEP |
| v3_max_bars_short | `{'V3_MAX_HOLDING_BARS': 24}` | +347.12% → +223.02% (-124.10) | 247 → 247 (+0.0%) | PF 1.98 → 1.64 | ❌ REVERT |
| v3_max_bars_long | `{'V3_MAX_HOLDING_BARS': 96}` | +347.12% → +361.01% (+13.89) | 247 → 246 (-0.4%) | PF 1.98 → 1.95 | ✅ KEEP |
| v4_atr_sl_tight | `{'V4_ATR_SL_MULT': 1.0}` | +361.01% → +361.01% (+0.00) | 246 → 246 (+0.0%) | PF 1.95 → 1.95 | ❌ REVERT |
| v4_atr_sl_wide | `{'V4_ATR_SL_MULT': 2.0}` | +361.01% → +361.01% (+0.00) | 246 → 246 (+0.0%) | PF 1.95 → 1.95 | ❌ REVERT |
| v4_rsi_low_lower | `{'V4_RSI_LOW': 30.0}` | +361.01% → +359.71% (-1.30) | 246 → 254 (+3.3%) | PF 1.95 → 1.92 | ❌ REVERT |
| v4_rsi_low_higher | `{'V4_RSI_LOW': 40.0}` | +361.01% → +295.55% (-65.46) | 246 → 242 (-1.6%) | PF 1.95 → 1.8 | ❌ REVERT |
| tao_rsi_28 | `{'RSI_REVERSAL_BY_SYMBOL.TAO': 28.0}` | +361.01% → +407.89% (+46.88) | 246 → 238 (-3.3%) | PF 1.95 → 2.13 | ✅ KEEP |
| tao_rsi_25 | `{'RSI_REVERSAL_BY_SYMBOL.TAO': 25.0}` | +407.89% → +384.37% (-23.52) | 238 → 225 (-5.5%) | PF 2.13 → 2.14 | ❌ REVERT |
| tao_rsi_30 | `{'RSI_REVERSAL_BY_SYMBOL.TAO': 30.0}` | +407.89% → +361.01% (-46.88) | 238 → 246 (+3.4%) | PF 2.13 → 1.95 | ❌ REVERT |
| eth_rsi_35 | `{'RSI_REVERSAL_BY_SYMBOL.ETH': 35.0}` | +407.89% → +407.89% (+0.00) | 238 → 238 (+0.0%) | PF 2.13 → 2.13 | ❌ REVERT |
| eth_rsi_30 | `{'RSI_REVERSAL_BY_SYMBOL.ETH': 30.0}` | +407.89% → +407.89% (+0.00) | 238 → 238 (+0.0%) | PF 2.13 → 2.13 | ❌ REVERT |
| btc_rsi_28 | `{'RSI_REVERSAL_BY_SYMBOL.BTC': 28.0}` | +407.89% → +393.58% (-14.31) | 238 → 225 (-5.5%) | PF 2.13 → 2.11 | ❌ REVERT |
| btc_rsi_35 | `{'RSI_REVERSAL_BY_SYMBOL.BTC': 35.0}` | +407.89% → +407.89% (+0.00) | 238 → 238 (+0.0%) | PF 2.13 → 2.13 | ❌ REVERT |
| zec_rsi_33 | `{'RSI_REVERSAL_BY_SYMBOL.ZEC': 33.0}` | +407.89% → +407.89% (+0.00) | 238 → 238 (+0.0%) | PF 2.13 → 2.13 | ❌ REVERT |
| zec_rsi_27 | `{'RSI_REVERSAL_BY_SYMBOL.ZEC': 27.0}` | +407.89% → +389.04% (-18.85) | 238 → 233 (-2.1%) | PF 2.13 → 2.08 | ❌ REVERT |
