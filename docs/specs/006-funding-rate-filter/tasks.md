# Tasks 006 — Funding Rate Filter

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26 — pending commit + prod tuning

## Esta sesión (2026-05-26)

- [x] `FUNDING_REVERSAL_BLOCK_ANNUALIZED = 30.0` en `config.py`
- [x] Gate en `strategies.py:497` (post-RSI trigger, pre-register_signal_event)
- [x] `python3 -m py_compile config.py strategies.py` → OK
- [x] Dispatcher mental 5 casos (allow/block) → ✓ todos pasan
- [ ] Commit `feat(v3): spec-006 funding rate filter`
- [ ] Push origin/main

## Verificación post-deploy (7 días tuning window)

- [ ] Log `⏸️ [V3-Reversal] {sym}: funding ... bloqueando` aparece en Railway
- [ ] Conteo bloqueos por símbolo por día
- [ ] Conteo V3 alerts totales por día (comparar pre vs post)
- [ ] WR V3 (post-bloqueo) vs WR V3 baseline pre-gate

## Tuning post-7d

- [ ] Si bloqueo < 10% V3 alerts → bajar threshold a 20%
- [ ] Si bloqueo > 50% V3 alerts → subir a 50% o quitar gate
- [ ] Si V3 WR mejora >5pp → mantener gate, evaluar V4

## Backlog Spec 006.5

- [ ] Wire funding context en voz Apocalipsis (Sentinel Compact prompt)
- [ ] Funding rate trend (5d slope) — no solo current value
- [ ] Multi-exchange funding (Bybit + dYdX) si available

## Próximos specs roadmap (NotebookLM 4)

- [ ] **Spec 007** — Liquidity Sweeps (max/min cruzados con Macro Gate) — 1 día, $0
- [ ] **Spec 008** — Whale Netflows on-chain Etherscan API — 2 días, $0
- [ ] **Spec 009** — HMM Regime Classifier (Salmos semáforo maestro) — 2-3 días, $0
