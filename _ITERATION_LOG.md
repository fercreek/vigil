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
