# Tasks 012 — Spot CVD Segmentado

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26 — pending wire + producción

## Esta sesión

- [x] `cvd_segmented.py` nuevo módulo (~170 LoC)
  - `compute_cvd_segmented(symbol, lookback_trades=1000)`
  - `format_cvd_summary(cvd)` helper para AI prompts
  - `_classify_bucket`, `_classify_divergence`
  - Cache 60s
- [x] py_compile OK
- [x] Dispatcher tests: 3 buckets + 3 signals BEARISH/BULLISH/NEUTRAL
- [x] format helper produce string compacto legible
- [x] Empty dict graceful sin exchange_singleton
- [ ] Commit `feat(intel): spec-012 spot CVD segmented`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Llamada real BTC/USDT desde Railway: trades_processed > 100
- [ ] whale_cvd_usd varies (no constant 0)
- [ ] Si tradeo activo cripto + V3 reversal candidate, log signal CVD junto al alert
- [ ] Cache 60s evita rate limit fetch_trades

## Backlog Spec 012.5

- [ ] Wire en gemini_analyzer voz Genesis: inyectar `format_cvd_summary` al prompt
- [ ] Wire en V3-REVERSAL:
  * BEARISH divergence + V3 LONG candidate → skip
  * BULLISH divergence + V3 LONG candidate → boost confluence +1
- [ ] Telegram /cvd SYMBOL command
- [ ] Mover thresholds a config.py si validado

## Backlog Spec 012.6

- [ ] Multi-window CVD (1h vs 4h tendencia)
- [ ] CVD por exchange (Binance vs Coinbase)
- [ ] Alerta compuesta CVD whale + RSI extremo
