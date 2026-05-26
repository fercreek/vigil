# Tasks 016 — V3 Multi-Gate Hooks

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] HMM gate (Spec 009.5): `regime == "STRONG_TREND"` → skip V3
- [x] CVD gate (Spec 012.5): `divergence_signal == "BEARISH"` → skip V3
- [x] Social gate (Spec 013.5): `signal == "EUPHORIA"` → skip V3
- [x] Order early-exit: funding → HMM → CVD → Social
- [x] Try/except por cada gate (graceful degradation)
- [x] Logs distintivos con prefijo `⏸️ [V3-Reversal]`
- [x] py_compile strategies.py OK
- [x] Verificación src: 3 modules imported + 3 keywords matched
- [ ] Commit `feat(v3): spec-016 multi-gate hooks`
- [ ] Push origin/main

## Verificación post-deploy 7d

- [ ] Conteo bloqueos por gate (grep Railway logs)
- [ ] % V3 alerts que pasan todos los gates (esperar 30-60%)
- [ ] WR V3 con gates vs WR V3 baseline (esperar +5-15pp)
- [ ] Cero crash por import fail (graceful try/except)

## Tuning post-7d

- [ ] Si gate X bloquea >70% → tunear threshold
- [ ] Si combinación 100% en 3+ días → desactivar más restrictivo
- [ ] Si WR mejora >10pp → mantener + considerar wire V2-AI

## Backlog Spec 016.5

- [ ] Boost confluence con BULLISH CVD + FEAR social (no solo gates BEARISH)
- [ ] Métricas gate persistidas SQLite
- [ ] Dashboard Spec 015 mostrar gate stats
- [ ] Wire selectivo a V2-AI swing
