# Spec 014 — Grounding con Google Search (Apocalipsis macro)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — Mes 3 Sem 11 roadmap NotebookLM 4 (anticipado)
> **Origen:** `docs/research/notebook-lm-4/RESULTS.md` Prompt 5 + Prompt 6 Spec 015

## Contexto

NotebookLM 4 Prompt 5 sugirió: la voz **Apocalipsis** (riesgo macro) podría usar Gemini Grounding para queries en tiempo real sobre eventos FOMC, tariff news, geopolítica. Reemplaza el actual web fetch manual de PDFs FOMC + lecturas manuales de BlackRock.

Riesgo: costo extra Gemini Grounding (~$0.50/1k queries) puede comer presupuesto $10/mes. Solución: cap diario.

## Goals

1. Nuevo módulo `grounded_search.py` standalone:
   - `query_grounded_search(query, intent_label, daily_cap=5) -> str | None`
   - Cap diario 5 queries default
   - Cache 1h por query exacta (no cuenta vs cap)
   - Graceful degradation: sin SDK / sin API key → None
2. Logging a `ai_budget` cuando esté disponible
3. NO wire en Cuadrilla Zenith en este spec — Spec 014.5 hace el wire después de medir costo real

## Non-goals

- Wire a voz Apocalipsis en `gemini_analyzer.py` — Spec 014.5 candidato
- Múltiples search engines (Google only via Gemini tool)
- Multi-query batch en una call — 1 query por call
- Persistencia del daily counter en DB — in-memory por ahora (acepta reset on Railway restart). Spec 014.5 puede mover a ai_budget si hace falta.

## Dependencias

- `google.genai` SDK ✅ ya instalado (2.6.0)
- `GEMINI_API_KEY` env var ✅ ya configurada en producción
- `ai_budget.log_ai_call` ✅ opcional (graceful fallback si no disponible)

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Costo Grounding excede budget mensual | `GROUNDED_SEARCH_DAILY_CAP = 5` × 30 días = 150 queries/mes. Estimado $0.075/mes. |
| Counter in-memory se resetea con restart Railway | Aceptable — restart frecuencia baja. Spec 014.5: persistir a SQLite si hace falta. |
| Query duplicada consume cap innecesariamente | Cache 1h. Hits no cuentan vs cap. |
| Respuesta Grounding malformed | Try/except + None fallback. Caller usa contexto hardcoded como respaldo. |
| Caller olvida pasar `intent_label` | Default `"grounded_search"` — tracking menos granular pero funcional. |

## Criterio de aceptación

1. `python3 -m py_compile grounded_search.py` → OK
2. AST: funciones `query_grounded_search`, `get_daily_usage`, `_today_key`, `_get_daily_count`, `_increment_daily_count`, `_cache_get`, `_cache_set`
3. Smoke: sin `GEMINI_API_KEY` → `query_grounded_search(...)` retorna `None` + log warning
4. Smoke: `get_daily_usage()` retorna dict con `date/used/cap/cache_size`
5. Producción pendiente: wire en Apocalipsis (Spec 014.5) → verificar daily counter incrementa correctamente
