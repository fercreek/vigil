# Tasks 009.6 — HMM TTL Cache

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] `_CACHE` dict module-level + `HMM_CACHE_TTL = 900`
- [x] Helpers `_cache_get(key)` + `_cache_set(key, data)` con TTL check
- [x] LRU-ish eviction max 64 entries
- [x] En `detect_regime`: cache hit antes del fit → return cached
- [x] Tras fit exitoso → cache set
- [x] Cache key = `(symbol, timeframe, lookback)`
- [x] Error NO se cachea (transient)
- [x] py_compile + smoke cache get/set OK
- [ ] Commit `perf(regime): spec-009.6 HMM TTL cache`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] 1ra llamada `detect_regime("BTC/USDT")` → ~200-500ms
- [ ] 2da llamada misma key → <10ms (cache hit)
- [ ] Cache size estabiliza ≤64 entries
- [ ] Después de 15min → cache miss + re-fit
- [ ] No memory leak en operación 24h

## Backlog Spec 009.7

- [ ] Telegram `/regime SYMBOL` command
- [ ] SQLite persist cache si restarts frequent
- [ ] `/api/metrics/hmm_cache_stats` endpoint
- [ ] Background pre-cache para hot symbols
