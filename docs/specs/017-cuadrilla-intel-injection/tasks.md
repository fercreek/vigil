# Tasks 017 — Cuadrilla Intel Injection

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] `_format_extra_intel(intel: dict) -> str` helper en gemini_analyzer.py
- [x] `get_ai_consensus` signature extendida con `extra_intel: dict | None = None`
- [x] Inyectar bloque INTEL EN VIVO entre FOMC_CONTEXT y risk_ctx
- [x] V3-REVERSAL en strategies.py:
  * Refactor gates Spec 016 para guardar `_hmm`, `_cvd`, `_social` refs
  * Build `_extra_intel` dict tras gates pasar
  * Pasar a `get_ai_consensus(..., extra_intel=_extra_intel)`
- [x] py_compile gemini_analyzer.py strategies.py OK
- [x] Smoke `_format_extra_intel`: None/{}/full/partial → outputs correctos
- [ ] Commit `feat(zenith): spec-017 cuadrilla intel injection`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Próxima alerta V3 LONG → Telegram muestra debate con bloque INTEL
- [ ] Las 4 voces refieren al INTEL (no lo ignoran completamente)
- [ ] Si HMM o CVD o Social fail → bloque parcial sin crash
- [ ] Backwards compat: V2-AI/V4/SWING alerts siguen normales sin extra_intel

## A/B test post-7d

- [ ] Conteo voces que mencionan "régimen", "whale", "retail", "FEAR", "EUPHORIA", "RANGE", etc.
- [ ] Comparar calidad debate pre vs post Spec 017 (cualitativo Fernando)
- [ ] Si voces ignoran INTEL → reforzar instrucción en prompt

## Backlog Spec 017.5

- [ ] Wire en V2-AI / V4 / SWING calls de get_ai_consensus
- [ ] Inyectar whale_netflow cuando Spec 010.5 wire fetch en V3 loop
- [ ] Inyectar funding_signal explícitamente
- [ ] Pasar extra_intel también a Sentinel Compact prompt
