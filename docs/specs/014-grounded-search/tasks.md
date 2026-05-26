# Tasks 014 — Grounded Search

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] `grounded_search.py` nuevo módulo (~200 LoC)
  - `query_grounded_search(query, intent_label, daily_cap=5) → str | None`
  - `get_daily_usage()` debug helper
  - Daily counter in-memory + cleanup últimas 7 entradas
  - Cache 1h por query exacta (no consume cap)
  - ai_budget logging opcional
  - Graceful degradation sin SDK / sin API key
- [x] py_compile OK
- [x] Smoke: sin API key → None + warning log
- [x] Smoke: get_daily_usage() retorna dict válido
- [ ] Commit `feat(macro): spec-014 grounded search helper`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Si manual test con API key real: query "latest FOMC decision rate" → respuesta sintética
- [ ] Verificar `get_daily_usage()` incrementa correctamente
- [ ] Confirmar log `[grounded_search] OK (intent) [N/5]` en Railway
- [ ] Confirmar cache hit log si misma query repetida

## Backlog Spec 014.5

- [ ] Wire en voz Apocalipsis (gemini_analyzer.py) — solo en Panorama 2h, NO en cada Sentinel
- [ ] Identificar trigger events específicos: FOMC dates, CPI release dates, geopolítica
- [ ] Persistir daily counter en SQLite (sobrevive restarts Railway)
- [ ] Telegram command `/news QUERY` con cap independiente
- [ ] Validar ROI: ¿queries grounding mejoran calidad alertas? → si sí, subir cap a 10/día
