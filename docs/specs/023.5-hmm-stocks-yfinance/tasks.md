# Tasks 023.5 — HMM Regime Classifier para Stocks vía yfinance

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] `regime_hmm.py`: lazy import `yfinance` con `_YFINANCE_AVAILABLE` flag
- [x] `regime_hmm._yf_interval_period(timeframe, lookback)` mapper ccxt → yfinance
- [x] `regime_hmm._fetch_ohlcv_stock(ticker, timeframe, lookback_candles)` adapter
- [x] Normalización columnas yfinance → schema `open/high/low/close/volume` lowercase
- [x] `auto_adjust=False` para precio raw consistente
- [x] `regime_hmm.detect_regime`: branch por `"/" in symbol` (cripto vs stock)
- [x] Backwards compat: cripto path intacto, usa `indicators.get_df` igual
- [x] Cache TTL 15min compartido entre cripto y stocks (Spec 009.6)
- [x] Graceful degradation: sin yfinance → `_fetch_ohlcv_stock` retorna `None`, `detect_regime` retorna `{}`
- [x] Wire `stock_analyzer.py:stock_watchdog` ENTRY_ALERT: tag `📊 HMM régimen: REGIME (conf X%)`
- [x] Tag posicionado después de `_explosive_tag`, antes de header `🚨 ALERTA DE ENTRADA`
- [x] Try/except wrap — yfinance error o hmmlearn missing = skip tag, alert continúa
- [x] `python3 -m py_compile regime_hmm.py stock_analyzer.py` → OK
- [x] Smoke local sin libs: `_YFINANCE_AVAILABLE=False`, fetch retorna None graceful
- [x] Smoke local: `_yf_interval_period` mapper OK para 1m/15m/1h/4h/1d
- [x] Spec docs: spec.md / plan.md / tasks.md
- [ ] Commit `feat(hmm): spec-023.5 yfinance adapter para stocks regime + wire stock_analyzer tag`
- [ ] Push origin/main

## Verificación post-deploy Railway

- [ ] Logs muestran HMM fits para stocks sin errores yfinance (ej. `[HMM]` con ticker NVDA/TSLA)
- [ ] Próxima ENTRY_ALERT NVDA/TSLA/OKLO/etc muestra tag `📊 HMM régimen: REGIME (conf X%)`
- [ ] Cache TTL 15min funcional: logs no muestran refetch yfinance dentro de 15min para mismo ticker
- [ ] yfinance rate-limit OK: no Yahoo 429 errors en logs
- [ ] Cripto V3-REVERSAL sigue recibiendo regime via Spec 017.5 (no regression)

## Backlog Spec 023.6

- [ ] Inyectar HMM regime stocks a Cuadrilla Zenith Salmos (analog a Spec 017.5 cripto)
- [ ] Gate stocks alerts por HMM regime (block long si STRONG_TREND bajista) — requires backtest
- [ ] CVD-like volume profile stocks vía yfinance options open interest
- [ ] Override `lookback` por strategy (V3-REVERSAL 200, scalper 50)
- [ ] Soporte `4h` timeframe real vía resample 1h→4h
- [ ] Endpoint `/api/metrics/hmm_stocks` para dashboard
- [ ] Backtest histórico: precision/recall HMM regime stocks vs price action 24h fwd
- [ ] EXPLOSIVE_TICKERS-aware: si HMM=VOLATILE_SQUEEZE + ticker explosive + setup activo → boost confluence Spec 021
