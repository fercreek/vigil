# Tasks 002.5 — Regime Transitions

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26 (MVP)

## Esta sesión

- [x] `regime_transitions.py` nuevo módulo
- [x] `get_current_macro_state(sp500, vix) -> str` con 4 régimens + UNKNOWN
- [x] `detect_transition(sp500, vix) -> dict` con bullish/bearish flags
- [x] Persistencia JSON `data/macro_state.json`
- [x] `EXPLOSIVE_TICKERS` set (14 tickers)
- [x] `BARRIDA_CLUSTERS` set (ai_infra, nuclear)
- [x] `is_explosive_correction_setup(ticker, sp500, vix) -> bool` (24h freshness window)
- [x] `is_barrida_opportunity(cluster, sp500, vix, drop_pct) -> bool`
- [x] `get_state_summary()` para telemetría
- [x] Wire MVP: tag `⚡ EXPLOSIVE_CORRECTION` en stock_analyzer ENTRY_ALERT
- [x] py_compile regime_transitions.py + stock_analyzer.py OK
- [x] Smoke 4 régimens + transition detection + helpers
- [ ] Commit `feat(macro): spec-002.5 regime transitions`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] `data/macro_state.json` se crea en primer ciclo Railway
- [ ] Logs muestran `[regime_transitions] X_TO_Y detectado` cuando SP500 cruza thresholds
- [ ] Next entry alert RKLB/HOOD/OKLO post-transition → tag ⚡ visible
- [ ] State sobrevive Railway restart (verify file persistence)

## Backlog Spec 002.6

- [ ] Wire BARRIDA_OPPORTUNITY en V3-REVERSAL gates
- [ ] Boost confluence Spec 021 cuando EXPLOSIVE matches ticker
- [ ] Endpoint `/api/metrics/regime_transitions`
- [ ] SP500 real via yfinance ^GSPC (no SPY × 10 aproximación)
- [ ] EXPLOSIVE_TICKERS a config.py (no hardcoded)
- [ ] Backtest histórico filtros
- [ ] intraday_drop_pct tracking (5min vs hora) para BARRIDA wire
