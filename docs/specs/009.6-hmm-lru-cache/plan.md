# Plan 009.6 — HMM TTL Cache

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Patrón cache TTL en lugar de functools.lru_cache

`functools.lru_cache` NO soporta TTL. Patrón implementado:
```python
_CACHE: dict = {}
def _cache_get(key):
    entry = _CACHE.get(key)
    if entry is None: return None
    if time.time() - entry["ts"] > HMM_CACHE_TTL:
        del _CACHE[key]
        return None
    return entry["data"]
```

Mismo patrón ya usado en `cvd_segmented.py`, `market_intel.py`, `grounded_search.py`. Consistencia.

### 2. TTL 15 min (900s)

Justificación:
- HMM regime es slow-moving — STRONG_TREND no cambia a RANGE en 5min
- 15min cubre múltiples ciclos del bot loop (cada 5-10min)
- Suficientemente fresco para reaccionar a régimen change post-evento macro

### 3. LRU-ish eviction max 64

Implementación simple:
```python
if len(_CACHE) > 64:
    oldest = sorted(_CACHE.items(), key=lambda x: x[1]["ts"])[:8]
    for k, _ in oldest: del _CACHE[k]
```

No es LRU clásico (no trackea access time, solo insert time). Pero TTL natural elimina entries stale, así que efecto es similar.

8 símbolos × 3 timeframes posibles × 1 lookback = 24 entries max razonables. 64 da margen.

### 4. Cache key = tuple `(symbol, timeframe, lookback)`

`lookback` en el key porque distintos lookbacks producen distintos modelos. Si llamas con 100 y 200, son fits diferentes.

### 5. Cache miss en error → no se cachea

Errors devuelven `{}` y NO entran al cache. Razón: error transitorio (API hiccup) no debería bloquear el retry siguiente con cache hit del error.

## Verificación

- ✅ py_compile regime_hmm.py
- ✅ Cache get/set funciona
- ✅ HMM_CACHE_TTL = 900s
- Producción pendiente: medir cache hit ratio

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `perf(regime): spec-009.6 HMM TTL cache 15min — reduce overhead 4x post Spec 017.5` |

## Backlog Spec 009.7

- Telegram `/regime SYMBOL` command para inspección manual
- Persistir cache a SQLite si Railway restarts frequent
- Métricas cache hit ratio expuestas en `/api/metrics/hmm_cache_stats`
- Background thread que pre-cache regimen for hot symbols c/15min
