# Tasks 017.5 — INTEL a Todas las Strategies

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] Helper `_build_extra_intel(sym)` agregado top de `strategies.py`
- [x] Llama 4 módulos intel: regime_hmm + cvd_segmented + social_quant + onchain (ETH only)
- [x] Try/except por módulo — intel parcial OK
- [x] Wire callsite V1-LONG (line ~812): `extra_intel=_build_extra_intel(sym)`
- [x] Wire callsite V4 (line ~876): idem
- [x] Wire callsite SWING (line ~1000): idem
- [x] V3-REVERSAL inline build mantiene Spec 017 original
- [x] py_compile strategies.py OK
- [x] grep: 4 `extra_intel=` en strategies.py
- [ ] Commit `feat(zenith): spec-017.5 INTEL injection a V1/V4/SWING`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Próxima alerta V2-AI/V4/SWING → Telegram muestra debate con bloque INTEL
- [ ] Cuadrilla Zenith voces refieren a HMM/CVD/Social/Whale en V2/V4/SWING también
- [ ] Tokens Gemini consumidos por debate: comparar pre vs post Spec 017.5
- [ ] Si overhead HMM excesivo → activar Spec 009.6 LRU cache

## Backlog Spec 017.6

- [ ] Spec 009.6: LRU cache HMM por (sym, timeframe)
- [ ] Refactor V3-REVERSAL inline → helper (cuando gates puedan reusar refs)
- [ ] Confluence boost Spec 021 también en V1/V4/SWING (+0.5 conservador)
- [ ] Métricas tokens consumidos pre vs post
