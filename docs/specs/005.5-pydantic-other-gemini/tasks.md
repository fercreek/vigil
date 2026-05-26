# Tasks 005.5 — Pydantic Panorama Structured Output

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26 — pending commit + prod verification

## Esta sesión (2026-05-26)

- [x] `models/panorama.py` — Pydantic v2 schema (~100 líneas)
  - `PanoramaPersonaResponse` flat model (bias Literal + clave + accion, max_length=200 + trim)
  - `field_validator` sinónimos bias (bull/bear/long/short/neutral)
  - `field_validator` trim/placeholder clave/accion
  - `has_real_content()` para skip de respuestas vacías
  - `to_telegram_format()` retrocompat con renderer existente
- [x] `models/__init__.py` — re-export `PanoramaPersonaResponse`
- [x] `gemini_analyzer.py:_call_persona_task_structured` nuevo worker:
  - Import condicional `PanoramaPersonaResponse` (graceful fallback)
  - `response_schema=PanoramaPersonaResponse` via `client.models.generate_content`
  - System prompt de la persona preservado
  - Memoria persona replicada (_load_memory + _add_to_memory + log_ai_decision)
  - Fallback automático a `_call_persona_task` en cualquier error
- [x] `gemini_analyzer.py:get_hourly_panorama` — 1 línea cambiada (submit al executor usa el worker structured)
- [x] Smoke tests (8/8 pasados):
  - py_compile ✓
  - Import ✓
  - Canonical formato ✓
  - Sinónimo bull → ALCISTA ✓
  - Sinónimos bear/short → BAJISTA ✓
  - Bias inválido → NEUTRAL default ✓
  - max_length=200 raise ValidationError ✓
  - Trim + placeholder ✓
  - has_real_content() default/real ✓
- [ ] Commit `feat(ai): spec-005.5 Pydantic Panorama`
- [ ] Push origin/main

## Verificación post-deploy (próximo Panorama horario)

- [ ] Log `[Panorama Structured]` NO muestra warning "response.parsed vacío"
- [ ] Log `[Panorama Structured]` NO muestra warning "fallback chat" en >5% de las llamadas
- [ ] Telegram Panorama muestra las 4 personas con `BIAS:`, `CLAVE:`, `ACCIÓN:` exactos
- [ ] Memoria de cada persona registra el panorama (verificar `agent_memory_*.json`)
- [ ] Latencia <3s típico para 4 personas en paralelo

## Próximos specs candidatos (Pydantic continuación)

- [ ] **Spec 005.6** — Pydantic para `get_top_setup` (multi-symbol event detector)
  - Schema con conditional fields: entry/SL/TP solo si verdict != ESPERAR
  - Literal symbol enum: BTC/TAO/ZEC/HBAR/DOGE
  - Racional como `list[str]` con max_items=3
- [ ] **Spec 005.7** — Pydantic para `get_expert_advice` (análisis Elliott Waves)
  - Schema con secciones: analisis_elliott / niveles_clave / psicologia
  - Cada sección con max_length=300
- [ ] **Spec 005.8** — Pydantic para `get_macro_shield` (Estratega Macro)
  - bias: Literal["AGRESIVO", "DEFENSIVO"]
  - sentimiento_riesgo: Literal["ON", "OFF"]
  - veredicto: str max_length=300
- [ ] **Spec 005.9** — Deprecate `voice_compactor.parse_sentinel_json` cuando Pydantic >95% success en 30d

## Backlog Pydantic

- [ ] `get_zec_sentinel_report` legacy wrapper (probablemente ya cubierto por Spec 005)
- [ ] `get_sentinel_report` (texto narrativo completo) — más complejo, schema con muchas secciones
- [ ] `analyze_social_sentiment` en `social_analyzer.py` (fuera de gemini_analyzer.py pero usa Gemini)
- [ ] `bitlobo_agent.py` Gemini Vision calls — schema con zonas verde/roja como sub-models
