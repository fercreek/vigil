# Spec 009.6 — HMM TTL Cache (LRU-ish)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P0 — performance critical post Spec 017.5
> **Origen:** Spec 009 backlog + Spec 017.5 overhead

## Contexto

Spec 017.5 cableó INTEL injection a las 4 strategies → `regime_hmm.detect_regime` se llama 4x por símbolo por ciclo. Sin cache, cada call hace HMM fit (100-500ms) + score + predict.

Cost en producción: 8 símbolos × 4 strategies × 200ms = 6.4s overhead por ciclo SOLO de HMM.

Spec 009.6 agrega cache TTL 15min por `(symbol, timeframe, lookback)`. Resultado: 1 fit/15min/sym → ~95% cache hits durante operación normal.

## Goals

1. Agregar `_CACHE: dict` module-level + `HMM_CACHE_TTL = 900` (15min)
2. Helpers `_cache_get(key)` y `_cache_set(key, data)` con TTL check
3. En `detect_regime`:
   - Cache hit antes del fit → return cached
   - Tras fit exitoso → cache set
   - Cache key = tuple `(symbol, timeframe, lookback)`
4. LRU-ish eviction: max 64 entries, evict 8 oldest cuando llega al límite
5. Misma signature, retornable retrocompatible

## Non-goals

- Usar `functools.lru_cache` (no soporta TTL nativo)
- Persistencia SQLite (cache in-memory suficiente)
- Cache global cross-symbol/timeframe — keys aislados
- Invalidación selectiva (TTL natural)

## Dependencias

- `regime_hmm.py` ✅ (Spec 009)
- `time.time()` para TTL

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Cache TTL 15min vs régimen cambia rápido | 15min suficiente — HMM regime es slow-moving por construcción. Tunable post-7d. |
| Cache memory grow si bot opera N símbolos × N timeframes | LRU-ish eviction max 64 entries |
| Stale cache durante FOMC / eventos macro | TTL 15min → recovery en <15min. Aceptable. Manual flush no en scope. |
| Race condition multi-thread cache writes | dict.setitem es thread-safe en CPython. Sin lock necesario. |

## Criterio de aceptación

1. `python3 -m py_compile regime_hmm.py` → OK
2. Smoke: `_cache_get(key)` None → set → get retorna data
3. Smoke: `HMM_CACHE_TTL == 900`
4. Producción post-deploy: medir tiempo 4 llamadas mismo sym
   - 1ra: ~200-500ms (cache miss + fit)
   - 2da/3ra/4ta: <10ms (cache hit)
5. Cache size estabiliza ≤64 entries en operación normal
