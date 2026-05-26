# Tasks 005 — Pydantic Structured Output

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26 — pending commit + prod verification

## Esta sesión (2026-05-26)

- [x] `models/__init__.py` — paquete con re-export de `SentinelResponse`, `SentinelVoices`
- [x] `models/sentinel.py` — Pydantic v2 schema (105 líneas)
  - `SentinelVoices` sub-model (4 voces + max_length=120)
  - `SentinelResponse` main model (bias Literal + score 1-5 + verdict Literal + voices + action)
  - `field_validator` para sinónimos bias/verdict
  - `has_real_voices()` method (regla Spec 003 fix encapsulada)
  - `to_renderer_dict()` retrocompatibilidad con `voice_compactor.render_sentinel_compact`
- [x] `gemini_analyzer.py:get_sentinel_report_compact` migrado:
  - Import condicional `SentinelResponse` (graceful fallback si import falla)
  - `response_schema=SentinelResponse` en `GenerateContentConfig`
  - Path primario: `resp.parsed → to_renderer_dict()`
  - Fallback legacy: `voice_compactor.parse_sentinel_json(raw)` intacto
- [x] Smoke tests pasados:
  - py_compile ✓
  - Import ✓
  - Default/real voices ✓
  - Sinónimo bias ✓
  - Validation score=10 raise ✓
  - Renderer end-to-end produce mensaje completo ✓
- [ ] Commit `feat(ai): spec-005 Pydantic Structured Output`
- [ ] Push origin/main

## Verificación post-deploy (próxima alerta sentinel ZEC)

- [ ] Log `[Sentinel Compact]` NO muestra warning "voices empty"
- [ ] Telegram alert ZEC muestra 4 voces pobladas (no "—")
- [ ] Log `parse_sentinel_json` fallback NO se ejecuta (Pydantic primary path activo)
- [ ] `[AI Router] SDK anthropic no instalado` sigue normal (no afecta Gemini)
- [ ] Latencia Sentinel Compact <2s típico

## Próximos specs roadmap (NotebookLM 4)

- [ ] **Spec 006** — Context Caching (Gemini cache 80% boilerplate) — 1 día, $0
- [ ] **Spec 007** — Funding Rate Filter (Apocalipsis) — 1h, $0
- [ ] **Spec 008** — Liquidity Sweeps (FVG matemático) — 1 día, $0

## Backlog spec-005.5

- [ ] Migrar `get_weekly_bias` a Pydantic (post-QA Spec 005 producción 7d)
- [ ] Migrar `get_panorama` a Pydantic
- [ ] Migrar `get_multi_symbol_event` a Pydantic
- [ ] Deprecate `voice_compactor.parse_sentinel_json` + `_repair_partial` + `_validate`
  cuando Pydantic primary path > 95% success en 30d
