# Spec 005 — Pydantic Structured Output para Cuadrilla Zenith

> **Status:** IN PROGRESS 2026-05-26
> **Created:** 2026-05-26
> **Owner:** Fernando
> **Severity:** P0 — quick win semana 1 del roadmap NotebookLM 4
> **Origen:** `docs/research/notebook-lm-4/RESULTS.md` Prompt 5 + Prompt 6 Mes 1 Semana 1

## Contexto

Bot usa Gemini JSON mode con `response_mime_type="application/json"` + parsing manual via `voice_compactor.parse_sentinel_json` + `_repair_partial`. Cuando Gemini trunca el JSON (Spec del fix de hoy `7d306a7`), parser cae a regex recovery que rescata bias/score/verdict pero pierde `voices`, generando alertas inútiles como "🟢 ZEC 4/5 LONG · 🎩 — · ⚡ —".

NotebookLM 4 Prompt 5 recomendó migrar a **Pydantic Structured Output**: el SDK google-genai 2.6 soporta `response_schema=PydanticModel` que fuerza al modelo a respetar tipos exactos (bias=Enum, score=int 1-5, voices=4 strings non-empty).

## Problema raíz

1. **JSON malformado silencioso:** Gemini a veces devuelve markdown fences (` ```json `), comillas curvas, o claves faltantes. `parse_sentinel_json` tiene 3 fallbacks pero todos manuales (regex + try/except).

2. **`_repair_partial` rescata datos parciales:** cuando hay truncación a media `voices`, el rescue devuelve `voices={}`. Aunque el fix `7d306a7` ya filtra alertas vacías, el bot pierde la señal entera en lugar de recibir voices válidas.

3. **Sin enforcement de tipos:** `score` puede llegar como string `"4"` o `4.5`. `bias` puede ser `"long"` lowercase o `"BULL"` synonym. Cada fallback en `_validate()` es manual + frágil.

4. **Boilerplate parser:** voice_compactor.py tiene ~80 líneas dedicadas a parsing. Reemplazables por 1 línea: `response.parsed`.

## Goals

1. Definir Pydantic v2 `SentinelResponse` model en `models/sentinel.py`:
   - `bias: Literal["LONG", "SHORT", "NEUTRAL"]`
   - `score: int` con constraint 1-5
   - `verdict: Literal["ACUMULAR", "ESPERAR", "REDUCIR"]`
   - `voices: SentinelVoices` (sub-model con genesis/exodo/salmos/apocalipsis como `str` con max_length=120)
   - `action: str` max 160 chars

2. Reemplazar Gemini call en `get_sentinel_report_compact`:
   - Pasar `response_schema=SentinelResponse` a `GenerateContentConfig`
   - Usar `response.parsed` (Pydantic instance) directamente
   - Si `response.parsed` es None → fallback al parser manual existente

3. Renderer `voice_compactor.render_sentinel_compact` compatible con dict actual:
   - Mantener interfaz dict (`voices.get('genesis')`) — `model_dump()` lo cumple

4. `parse_sentinel_json` queda como FALLBACK legacy (no eliminar, solo deprecate).

5. `_validate` queda como FALLBACK del fallback (solo si parsed Pydantic falla).

## Non-goals

- Migrar otras llamadas Gemini (Panorama, weekly_bias, multi-symbol) — Spec 005.5+ candidato.
- Refactor de voice_compactor.py — solo deprecate parser viejo.
- Reentrenar prompts — el prompt actual ya pide JSON, Pydantic solo enforza shape.
- Migrar a Anthropic — fuera de scope (Spec 006+ candidato).

## Dependencias

- `pydantic==2.13.3` ✅ ya instalado
- `google-genai==2.6.0` ✅ ya instalado, soporta `response_schema=BaseModel`
- `models/sentinel.py` — nuevo archivo
- `gemini_analyzer.py:get_sentinel_report_compact` — modificar
- `voice_compactor.py` — sin cambios (interfaz dict preservada)

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Gemini Flash 2.5 no soporta `response_schema` con todos los campos Literal | Probar primero con smoke test; fallback al parser manual si falla |
| `response.parsed` puede ser None aunque la API devuelva JSON válido | Mantener fallback `parse_sentinel_json(raw)` si `response.parsed` falta |
| Pydantic validation falla por edge case (ej. voice=None) | `voices` con default value `"—"` evita raise en validation |
| Latencia adicional por structured output | Estimado 5-10% más; aceptable vs gain de robustez |

## Criterio de aceptación

1. `python3 -m py_compile models/sentinel.py gemini_analyzer.py voice_compactor.py` → OK
2. Smoke test: crear `SentinelResponse` con voices válidas + `.model_dump()` retorna dict con shape igual al actual
3. Smoke test: crear `SentinelResponse(score=10)` → raise ValidationError (constraint 1-5)
4. Mock Gemini call: response.parsed devuelve Pydantic instance → render_sentinel_compact funciona sin cambios
5. Production deploy: alerta ZEC sentinel se ve con voices pobladas (verificar en logs siguiente sesión NYSE)
