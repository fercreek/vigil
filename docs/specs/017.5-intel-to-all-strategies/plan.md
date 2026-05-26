# Plan 017.5 — INTEL a Todas las Strategies

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Helper aislado vs inline duplicado

Inline 4 veces el código (HMM+CVD+Social+Whale fetch) sería repetitivo. Helper `_build_extra_intel(sym)` centraliza la lógica:
- Una única definición a mantener
- Misma data shape para todas las strategies
- Más legible en los callsites

### 2. NO refactorizar V3-REVERSAL inline → helper en este spec

V3 ya tiene los gates Spec 016 que LLAMAN los módulos individualmente (HMM kill if STRONG_TREND, CVD kill if BEARISH, etc). El INTEL builder de Spec 017 inline en V3 usa los refs `_hmm`, `_cvd`, `_social`, `_whale` que vienen de los gates.

Si refactorizo V3 a usar `_build_extra_intel`, perdemos los refs locales y haríamos doble fetch (gates Y helper). Mejor:
- V3-REVERSAL: mantiene inline build (reusa refs gates) — Spec 017 original
- V1/V4/SWING: usan `_build_extra_intel(sym)` helper (no tienen gates pre-existentes)

### 3. Cada módulo intel decide su propio cache

```python
# Dentro de _build_extra_intel:
try:
    _hmm = regime_hmm.detect_regime(sym, ...)
except Exception:
    pass
```

regime_hmm sin cache (Spec 009.6 candidato). cvd_segmented cache 60s. social_quant cache 30min. onchain cache 5min.

Si llamadas múltiples dentro mismo ciclo → cache hits, cost negligible.

### 4. Solo ETH para whale (filtro en helper)

```python
if sym_base == "ETH":
    try:
        _whale = onchain.get_whale_netflow(...)
```

Para BTC/SOL/ZEC/TAO no se llama onchain. Cero overhead innecesario.

### 5. Try/except por módulo (no global)

Permite intel parcial: si HMM falla, sigue computando CVD+Social+Whale.

## Verificación

- ✅ py_compile strategies.py
- ✅ `_build_extra_intel` definido top del archivo
- ✅ 4 callsites con `extra_intel=...`
- ✅ V3-REVERSAL mantiene su inline build (no breaks Spec 017)

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(zenith): spec-017.5 INTEL injection a V1/V4/SWING (Cuadrilla ve intel en todas strategies)` |

## Backlog Spec 017.6

- Spec 009.6: LRU cache HMM por (sym, timeframe) — reduce overhead 4x
- Refactor V3 inline build a helper (cuando V3 gates pueden reusar refs sin perderse)
- Wire confluence boost (Spec 021) a V1/V4/SWING también
- Measure tokens Gemini consumidos pre vs post Spec 017.5
