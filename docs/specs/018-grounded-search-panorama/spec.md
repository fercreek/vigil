# Spec 018 — Grounded Search en Panorama (Apocalipsis macro real)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — wire Spec 014 grounded_search a producción
> **Origen:** Spec 014.5 backlog + Roadmap NotebookLM 4 Prompt 5

## Contexto

Spec 014 dejó `grounded_search.py` standalone con cap diario 5 queries. Backlog 014.5 sugería wire a voz Apocalipsis, pero NO en cada Sentinel (frecuencia alta drenaría cap).

Spec 018 hace wire selectivo en `get_hourly_panorama` — el endpoint que corre cada 2h con macro view cross-asset. Apocalipsis es 1 de las 4 personas convocadas. La query macro se hace 1 vez por panorama call, cache interno 1h evita repetir.

Math: panorama c/2h × 24h = 12 calls/día. Cache 1h → 12 cache hits, 1 query real /día → bien por debajo del cap 5/día.

## Goals

1. En `get_hourly_panorama()` antes del prompt:
   - Llamar `grounded_search.query_grounded_search(query, intent_label="apocalipsis_panorama", daily_cap=5)`
   - Query genérica macro: FOMC + CPI + geopolítica
   - Si retorna texto → agregar bloque "📡 MACRO NEWS HOY" al prompt enviado a las 4 personas
   - Si None (cap exhausted, sin API key, fail) → bloque vacío + cero impact

2. Las 4 personas (Conservador, Scalper, Salmos, Apocalipsis) ven el mismo macro context. Apocalipsis lo usa más en su 12-palabra opinión (su rol = riesgo macro).

## Non-goals

- Wire en Sentinel Compact (frecuencia alta, drenaría cap) — out of scope
- Multiple queries por panorama (1 sola query macro suficiente)
- Persistir daily counter en SQLite — Spec 014.5 candidato
- Telegram command `/news` manual

## Dependencias

- `grounded_search.py` ✅ (Spec 014)
- `gemini_analyzer.get_hourly_panorama` ✅

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Cap exhausted antes de fin del día | Cache 1h del módulo → solo 1 query real/day desde panorama. ~4 calls del cap quedan disponibles para otros use cases |
| Grounded search lento bloquea panorama | `try/except` + `pass` — si falla, panorama corre sin macro block. Grounded típicamente 2-4s |
| Query "test" gastó 1/5 cap en dev | Aceptable. Production usa query real macro. Counter se resetea diario |
| Voces ignoran el bloque MACRO | Header explícito + visible al inicio del prompt. A/B tracking post-7d |
| Sin GEMINI_API_KEY en local dev | `query_grounded_search` retorna None, bloque vacío, cero crash |

## Criterio de aceptación

1. `python3 -m py_compile gemini_analyzer.py` → OK
2. Smoke: `grounded_search.query_grounded_search("test")` returna respuesta (verifica API key + flow)
3. Panorama prompt incluye bloque `📡 MACRO NEWS HOY` si query retorna texto
4. Panorama prompt SIN bloque si query retorna None (cap exhausted, fail, etc)
5. Producción pendiente: próximo panorama 2h en Railway → log `[grounded_search] OK` 1x/día
