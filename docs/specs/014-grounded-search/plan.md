# Plan 014 — Grounded Search

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Módulo standalone vs función en gemini_analyzer

Standalone. Razones:
- Mantiene `gemini_analyzer.py` limpio (ya tiene 1300+ líneas)
- Permite reutilización fuera de Cuadrilla Zenith (e.g. comando Telegram `/news SYMBOL` futuro)
- Testing aislado

### 2. Cap diario in-memory

`_DAILY_COUNTER: dict[str, int]` con key = "YYYY-MM-DD". Reset automático cuando cambia día.

Limitación: counter perdido si bot reinicia. Aceptable porque:
- Railway restarts son típicamente <1/día en bot estable
- Counter solo trackea queries del día actual
- Costo de overrun marginal ($0.50/1k queries → 5 extra queries = $0.0025)

Spec 014.5 candidate: persistir a SQLite si Spec 014 muestra restart frequency alta.

### 3. Cache 1h por query exacta

Cache key = query string literal. Hits no cuentan vs daily cap.

Razón: muchas queries son idénticas en períodos cortos (ej. "current FOMC rate decision" se pregunta cada vez que Apocalipsis se activa).

Cleanup: máx 50 entradas, evict oldest cuando llega al límite.

### 4. ai_budget logging opcional

Try/except wrap. Si `ai_budget.log_ai_call` falla por DB lock o path issue, no rompe la query. Logging es nice-to-have, no bloqueante.

### 5. Cap default = 5/día

Cálculo de costo:
- Grounding charge Google ~$0.50/1k queries
- 5/día × 30 días = 150/mes = $0.075/mes
- Bot tiene $10/mes budget AI total
- ⇒ Grounding consume <1% del budget. Safe.

Subir cap a 10/día si beneficios validados en producción.

### 6. NO wire automático a voces — Spec 014.5

Riesgo de wire antes de medir: si cada Sentinel Compact call (alta frecuencia) llamara grounding → drenaría cap en horas.

Spec 014.5 hará el wire solo donde tenga sentido (ej. solo Panorama 2h o solo en eventos macro específicos).

## Verificación

- ✅ py_compile grounded_search.py
- ✅ Smoke sin GEMINI_API_KEY → None + warning log
- ✅ get_daily_usage() retorna dict válido

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(macro): spec-014 grounded search helper — Gemini + Google Search` |

## Backlog Spec 014.5

- Wire a voz Apocalipsis en gemini_analyzer (Panorama 2h, FOMC dates, CPI dates)
- Persistir daily counter en SQLite (sobrevive restarts)
- Telegram command `/news QUERY` con cap separado
- Considerar pasar cap a 10/día si métricas validan ROI
