# Tasks 002.6 — Wire BARRIDA + EXPLOSIVE en V3-REVERSAL + endpoint

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] Add `get_cluster_for_symbol(sym_base)` helper en `regime_transitions.py`
- [x] V3-REVERSAL: computar `_barrida_active` post-`reversal_rsi` check
- [x] V3-REVERSAL: relax HMM STRONG_TREND gate si BARRIDA active
- [x] V3-REVERSAL: relax CVD BEARISH gate si BARRIDA active
- [x] V3-REVERSAL: boost `_boost += 1.5` si EXPLOSIVE_CORRECTION setup
- [x] Log strings nuevos (boost reason + BARRIDA relaxed)
- [x] `app.py`: endpoint `/api/metrics/regime_transitions`
- [x] py_compile strategies.py app.py regime_transitions.py OK
- [x] Smoke `get_state_summary()` + `get_cluster_for_symbol()`
- [ ] Commit `feat(macro): spec-002.6 wire BARRIDA+EXPLOSIVE V3-REVERSAL + endpoint`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Endpoint `/api/metrics/regime_transitions` retorna 200 + JSON válido
- [ ] Si SP500>7000 + VIX<22 + IREN setup → logs muestran boost EXPLOSIVE_CORRECTION
- [ ] V3-REVERSAL en cripto NO genera log BARRIDA active (esperado — dormant para cripto)

## Backlog Spec 002.7

- [ ] Wire en V2-AI/V4-EMA/SWING strategies
- [ ] intraday_drop_pct real tracking
- [ ] SP500 via yfinance ^GSPC
- [ ] EXPLOSIVE_TICKERS a config.py
