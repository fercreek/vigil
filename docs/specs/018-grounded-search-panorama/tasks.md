# Tasks 018 — Grounded Search en Panorama

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] Wire `grounded_search.query_grounded_search` en `get_hourly_panorama`
- [x] Query macro genérica única (FOMC + CPI + geopolítica)
- [x] Intent label `"apocalipsis_panorama"` para tracking
- [x] Daily cap 5 (default del módulo)
- [x] Cache 1h interno → 1 query real/day (12 panoramas)
- [x] Bloque `📡 MACRO NEWS HOY (grounded search):` inyectado al prompt
- [x] Try/except graceful — sin SDK, sin key, cap exhausted → bloque vacío
- [x] py_compile gemini_analyzer.py OK
- [x] Smoke: grounded_search funciona end-to-end (1/5 cap usado en dev)
- [ ] Commit `feat(macro): spec-018 grounded search en panorama`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Próximo panorama 2h en Railway → log `[grounded_search] OK (apocalipsis_panorama)`
- [ ] Voces panorama mencionan "FOMC", "CPI", "tariff", "FED", etc (señal que usan el bloque)
- [ ] Daily counter exactly 1/5 al final del día
- [ ] Si counter >1/5 → investigar (cache miss?)

## Backlog Spec 018.5

- [ ] Persist daily counter SQLite (sobrevive Railway restart)
- [ ] Query parametrizable por hour (mañana EU, tarde US)
- [ ] A/B test: voces ignoran o usan MACRO NEWS
- [ ] Telegram `/news QUERY` cap separado
