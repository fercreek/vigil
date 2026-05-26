# Tasks 009 — HMM Regime Classifier

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE (module only) 2026-05-26

## Esta sesión

- [x] `regime_hmm.py` creado con:
  - `detect_regime(symbol, timeframe, lookback)` función pública
  - `_build_features(df)` — log_ret + rolling_vol + range_pct
  - `_map_states_to_regimes(model, features, states)` — mapeo determinista
  - Lazy import de `indicators.get_df`
  - Flag `_HMMLEARN_AVAILABLE` para importabilidad sin hmmlearn
  - Try/except a 3 niveles (build_features, fit, predict) → empty dict on failure
- [x] `hmmlearn>=0.3.0` añadido a `requirements.txt`
- [x] py_compile + AST verification
- [ ] Commit `feat(regime): spec-009 HMM regime classifier (standalone)`
- [ ] Push origin/main (Railway instala hmmlearn en deploy)

## Verificación post-deploy

- [ ] Railway build OK (hmmlearn instalado sin errores de gcc)
- [ ] `python3 -c "from regime_hmm import detect_regime; print(detect_regime('BTC/USDT'))"` en Railway shell devuelve dict válido
- [ ] Log NO error `[HMM ERROR]` ni `[HMM FIT ERROR]` por símbolo principal
- [ ] Distribución de regímenes por símbolo: log de 24h → ¿está dominado por uno solo?

## Spec 009.5 — Wire-in pendiente

- [ ] Hook a `strategies.py:V3-REVERSAL`: gate por `regime != "STRONG_TREND"`
- [ ] Logging por símbolo: `[REGIME] BTC/USDT: STRONG_TREND (conf=0.87)`
- [ ] Cache LRU 15min por (symbol, timeframe) para reducir overhead
- [ ] Inyección de regime actual a voz Salmos en `gemini_analyzer.py:FOMC_CONTEXT`
- [ ] Comando Telegram `/regime SYMBOL` para inspect manual
- [ ] Alert si `training_loss` muy negativo 3 días (régimen inestable)

## Tuning post-7d (en Spec 009.5)

- [ ] Si V3+gate WR ≥5pp mejor → mantener gate firme
- [ ] Si V3+gate WR igual → suavizar a "reducir tamaño 50%" en lugar de bloquear
- [ ] Si HMM convergence falla > 10% símbolos → reducir features a 2 (log_ret + vol)
- [ ] Si > 70% del tiempo = RANGE → probar 4 estados

## Backlog Spec 009.6+

- [ ] NHHMM (non-homogeneous) con factores macro exógenos (DXY, VIX) como inputs
- [ ] Multi-timeframe regime fusion (1h + 4h + 1d agreement)
- [ ] HMM en stocks NYSE para gate de stock_watchdog
- [ ] A/B `covariance_type="full"` vs `"diag"` si convergence estable 30d
- [ ] Spec 011: LSTM híbrido con HMM como feature

## Próximos specs roadmap

- [ ] **Spec 009.5** — Wire-in V3-REVERSAL + cache + Salmos injection (1-2 días)
- [ ] **Spec 010** — Whale Netflows on-chain Etherscan (2 días)
- [ ] **Spec 011** — Multi-image BitLobo Gemini (1 día)
- [ ] **Spec 012** — Spot CVD Segmentado (3-4 días, Mes 3)
