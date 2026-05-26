# Spec 017.5 — INTEL Injection a Todas las Strategies (V1/V2/V3/V4/SWING)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — extender Spec 017 al resto de strategies
> **Origen:** Spec 017 backlog

## Contexto

Spec 017 cableó INTEL injection (HMM+CVD+Social+Whale) solo en V3-REVERSAL. Otras 3 callsites de `get_ai_consensus` quedaron sin contexto en vivo:
- Line ~812 — V1-LONG (cuando V1_LONG_ENABLED=True)
- Line ~876 — V4 (LONG/SHORT)
- Line ~1000 — SWING strategy

Spec 017.5 extiende. Cuadrilla Zenith ahora ve INTEL block en TODAS las strategies.

## Goals

1. Helper `_build_extra_intel(sym) -> dict` arriba en `strategies.py` (post `_is_fomc_proximity`).
2. Helper llama los 4 módulos intel (regime_hmm + cvd_segmented + social_quant + onchain ETH only).
3. Cada módulo tiene su propio cache TTL → llamadas repetidas dentro del mismo ciclo son cache hits.
4. Cada strategy callsite usa `extra_intel=_build_extra_intel(sym)` inline.

## Non-goals

- Cachear el extra_intel a nivel de strategies (cada módulo ya cachea)
- Cambiar el comportamiento de los gates Spec 016 (V3-REVERSAL específico, queda igual)
- Wire boost Spec 021 a otras strategies — solo V3 boost por ahora

## Dependencias

- `regime_hmm.detect_regime` ✅
- `cvd_segmented.compute_cvd_segmented` ✅
- `social_quant.get_social_sentiment` ✅
- `onchain.get_whale_netflow` ✅
- `gemini_analyzer.get_ai_consensus(extra_intel=...)` ✅ (Spec 017)

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| 4 modulos × 4 strategies × N símbolos = overhead | Cache TTL: CVD 60s, Social 30min, Whale 5min. HMM sin cache (Spec 009.6 candidato) |
| HMM fit 100-500ms × 4 strategies = 1.6s/symbol | HMM se llama 1x por strategy callsite. Si misma sym/timeframe, fit determinista — Spec 009.6 LRU cache resolverá |
| Etherscan rate limit si todos strategies llaman whale | Filtro `if sym_base == "ETH"` solo aplica ETH. Cache 5min absorbe |
| _extra_intel dict vacío → bloque INTEL vacío en prompt | OK, comportamiento previo Spec 017. Cero impact |
| Helper falla en uno de los 4 módulos → toda strategy skip | Try/except por módulo → keys parciales OK |

## Criterio de aceptación

1. `python3 -m py_compile strategies.py` → OK
2. `_build_extra_intel(sym)` definido en strategies.py top
3. 4/4 callsites de `get_ai_consensus` tienen `extra_intel=_build_extra_intel(sym)` (V3 ya inline, otros 3 via helper)
4. Si todos módulos disponibles → dict completo con HMM/CVD/Social/Whale keys
5. Si algún módulo missing → dict parcial sin crash
6. Producción pendiente 7d: medir tokens consumidos (más prompts grandes con INTEL block en TODAS strategies)
