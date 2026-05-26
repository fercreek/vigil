# Tasks 021 — V3 Confluence Boost

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] Boost block en V3-REVERSAL post-conf_score, pre-msg build
- [x] +1.0 si CVD BULLISH (whales acumulan)
- [x] +1.0 si Social FEAR (capitulación retail)
- [x] +1.0 si Whale BULLISH (ETH outflow exchange)
- [x] +0.5 si HMM RANGE (mean reversion ideal)
- [x] Log único `⭐ [V3-Reversal] sym: boost +X.X (reasons) → conf_score=Y.YY` solo si boost > 0
- [x] py_compile strategies.py OK
- [ ] Commit `feat(v3): spec-021 confluence boost`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Próxima alerta V3 con signals BULLISH/FEAR/RANGE → log ⭐ visible
- [ ] Telegram msg muestra conf_score boosted (más estrellas)
- [ ] Conteo alerts con boost > 0 vs total alerts V3

## Tuning post-7d

- [ ] Distribución conf_score V3 (baseline vs post-boost)
- [ ] WR V3 alerts boost > 0 vs WR V3 alerts boost = 0
- [ ] Si boost helps → mantener
- [ ] Si no diff → ajustar pesos
- [ ] Si max +3.5 nunca alcanzado → relajar conditions

## Backlog Spec 021.5

- [ ] Penalty signals (CVD/Social/Whale NEUTRAL = -0.5)
- [ ] Boost selectivo por símbolo
- [ ] Boost dinámico ML (RL pesos)
- [ ] Wire a V2-AI/V4/SWING (+0.5 conservador)
- [ ] Dashboard /api/metrics/boost_stats
