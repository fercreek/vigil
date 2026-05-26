# Tasks 023.6 — Options OI Volume Profile (stocks)

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] `options_oi.py`: lazy import `yfinance` con `_YFINANCE_AVAILABLE` flag (patrón Spec 023.5)
- [x] `options_oi._classify_signal(ratio)` mapea ratio → CALL_HEAVY / PUT_HEAVY / BALANCED
- [x] `options_oi._cache_get` / `_cache_set` con TTL 1800s (30min) + max 32 entries eviction
- [x] `options_oi.get_options_oi_ratio(ticker, expirations_lookback=2)` core function
- [x] Lógica: `yf.Ticker(t).options` → primeras N expirations → sum OI calls + puts
- [x] Defensive parsing: `getattr(chain, 'calls', None)` + `if 'openInterest' in columns` check
- [x] Try/except per-expiration → skip a la siguiente si falla, no abort total
- [x] Guard `max(total_put_oi, 1)` contra div by zero
- [x] Return dict completo: ticker, total_call_oi, total_put_oi, call_put_ratio, signal, expirations_analyzed, last_update_ts
- [x] Empty dict `{}` graceful on failure (caller decide fallback)
- [x] Wire `stock_analyzer.py:stock_watchdog` ENTRY_ALERT: tag `📈 Options OI: CALL_HEAVY (ratio Xx)` o `📉 PUT_HEAVY`
- [x] Tag posicionado entre `_hmm_tag` (Spec 023.5) y header `🚨 ALERTA DE ENTRADA`
- [x] BALANCED → no emite tag (evita ruido visual)
- [x] Try/except wrap stock_analyzer — sin yfinance o fallo = skip tag, alert continúa
- [x] `python3 -m py_compile options_oi.py stock_analyzer.py` → OK
- [x] Smoke local: `_classify_signal` boundaries correct (2.5/0.4/1.5)
- [x] Spec docs: spec.md / plan.md / tasks.md
- [ ] Commit `feat(options): spec-023.6 OI volume profile stocks via yfinance + wire stock_analyzer tag`
- [ ] Push origin/main

## Verificación post-deploy Railway

- [ ] Logs muestran `[OPTIONS_OI]` con tickers NVDA/TSLA/OKLO sin errores
- [ ] Próxima ENTRY_ALERT stock con OI extremo muestra tag `📈 CALL_HEAVY` o `📉 PUT_HEAVY`
- [ ] Cache TTL 30min funcional: logs no muestran refetch yfinance dentro 30min mismo ticker
- [ ] yfinance rate-limit OK: no Yahoo 429 errors
- [ ] No regression Spec 023 / 023.5 / 002.5: social + HMM + EXPLOSIVE tags siguen apareciendo
- [ ] Alerts BALANCED (mayoría) NO muestran tag OI — confirmar silencio cuando no hay edge

## Backlog Spec 023.7

- [ ] IV rank percentile via yfinance — histórico IV snapshots para percentile real
- [ ] Unusual options activity scanner — OI delta vs N días atrás (DB persistence)
- [ ] Strike-level analysis — max pain, gamma exposure (GEX) calculation
- [ ] Gate logic por OI signal (block long si PUT_HEAVY ≤ 0.3) — requires backtest validation
- [ ] Inyectar OI signal a Cuadrilla Zenith Salmos (analog Spec 017.5)
- [ ] Endpoint `/api/metrics/options_oi` para dashboard
- [ ] `min_total_oi` gate — descartar signals si total OI < 1000 (low liquidity)
- [ ] Soporte cripto via Deribit options chain (BTC/ETH OI)
- [ ] Skew analysis — call/put OI weighted by strike distance to spot
- [ ] Backtest histórico: precision/recall OI signal stocks vs price action 24h forward
