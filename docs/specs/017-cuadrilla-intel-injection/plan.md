# Plan 017 — Cuadrilla Intel Injection

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Helper aislado `_format_extra_intel`

En lugar de inline en `get_ai_consensus`, función separada. Razón:
- Testeable aislado
- Reutilizable en otras llamadas Gemini si después se decide
- Encoding del formato visual (líneas, emojis, indentación) en un solo lugar

### 2. `extra_intel: dict | None = None` default

Backwards compatible 100%. Las 3 otras callsites de `get_ai_consensus` (V2-AI, V4, SWING en strategies.py) NO necesitan modificarse — siguen funcionando igual.

### 3. Solo claves presentes se renderizan

```python
if "hmm_regime" in intel:
    lines.append(...)
if "cvd_signal" in intel:
    lines.append(...)
```

Permite intel parcial — si HMM disponible pero Social fail, solo se muestra HMM. Cero spam de placeholders.

### 4. Header explícito + instrucción

```
📡 INTEL EN VIVO (datos pasaron todos los gates, úsalos para refinar opinión):
  • HMM régimen técnico (Salmos): RANGE (conf 0.78)
  ...
```

El header indica:
- "datos pasaron todos los gates" — explica por qué la alerta existe (no fue killed)
- "úsalos para refinar opinión" — instrucción explícita a las 4 voces

Mapeo entre paréntesis ((Salmos), (Genesis), (Exodo)) — sugiere qué voz lo lee. No fuerza, pero dirige.

### 5. Refactor de Spec 016 gates para guardar refs

```python
# Antes (Spec 016):
try:
    import regime_hmm
    _hmm = regime_hmm.detect_regime(...)  # discard si no skip
    if _hmm.get("regime") == "STRONG_TREND":
        continue

# Ahora (Spec 017):
_hmm = {}  # default para uso después
try:
    import regime_hmm
    _hmm = regime_hmm.detect_regime(...) or {}
    if _hmm.get("regime") == "STRONG_TREND":
        continue
```

Variable `_hmm = {}` outside try-block para que esté accesible después del gate. Cero side effect si import falla.

### 6. Build `_extra_intel` después de los 3 gates

```python
_extra_intel = {}
if _hmm.get("regime"):
    _extra_intel["hmm_regime"] = _hmm.get("regime")
    _extra_intel["hmm_confidence"] = _hmm.get("confidence", 0.0)
# ... misma lógica CVD y Social
```

Solo claves con valor non-empty se agregan. `_format_extra_intel` retorna `""` si dict vacío.

### 7. Posición del INTEL block en el prompt

Entre `FOMC_CONTEXT` y `risk_ctx`. Razón:
- FOMC = contexto macro fijo
- INTEL EN VIVO = contexto en vivo del setup actual (lo más fresco)
- risk_ctx = pulso global (variable)
- memory_ctx = lecciones histor

Orden lógico: macro estable → estado actual → riesgo activo → memoria.

## Verificación

- ✅ py_compile gemini_analyzer.py strategies.py
- ✅ `_format_extra_intel(None)` → `""`
- ✅ `_format_extra_intel({})` → `""`
- ✅ `_format_extra_intel(full_dict)` → bloque con header + 3 líneas
- ✅ Partial dict (solo HMM) → bloque con 1 línea
- ✅ V3-REVERSAL refactor preserva `_hmm`, `_cvd`, `_social` refs

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(zenith): spec-017 cuadrilla intel injection — HMM + CVD + Social en debate prompt` |

## Backlog Spec 017.5

- Wire en V2-AI / V4 / SWING calls de get_ai_consensus
- Inyectar también whale_netflow (Spec 010.5) cuando se enchufe fetch en loop V3
- Inyectar funding_signal explícitamente (ya disponible en loop)
- Sentinel Compact prompt + Pydantic (Spec 005) — pasar extra_intel ahí también
- A/B test: medir si voces realmente refieren al INTEL block o lo ignoran
