# Tasks 004 — NotebookLM Findings Integration

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26 — pending commits

## Esta sesión (2026-05-26)

- [x] `MAX_PER_CLUSTER_BY_CLUSTER` dict en `config.py` (post line ~192)
- [x] `QUANTUM_SUPPRESSED_UNTIL = "2026-06-01"` en `config.py`
- [x] `CRYPTO_PROXY_BTC_GATE = 74000.0` en `config.py`
- [x] `MACRO_BONDS_WATCH = ["TLT", "TBT"]` en `config.py`
- [x] Import + auto-expire en `stock_analyzer.py:stock_watchdog()`
- [x] `python3 -m py_compile config.py stock_analyzer.py` → OK
- [x] Smoke test: today 2026-05-26 vs UNTIL 2026-06-01 → not expired → IONQ/RGTI siguen suprimidas ✓
- [x] Smoke test: forced UNTIL 2026-05-25 → expired True → quantum list cleared ✓
- [ ] Commit `feat(stock): spec-004 NotebookLM findings`
- [ ] Commit `docs: research/notebook-lm/* corpus + prompts + results`

## Verificación post-deploy

- [ ] Logs hoy 26-May: NO "QUANTUM auto-expired" (UNTIL=2026-06-01 futuro)
- [ ] Logs hoy 26-May: SÍ "IONQ SUPRIMIDA" + "RGTI SUPRIMIDA" (skip activo)
- [ ] Logs 1-Jun: SÍ "QUANTUM auto-expired" + IONQ/RGTI vuelven a alerts normales (con WEEK_PRIORITY tags si aplica)
- [ ] No regresión en NVDA/OKLO earnings suppression (Spec 002 + 003 intactas)

## Backlog P1 (Spec 005 candidato)

- [ ] Filtro `EXPLOSIVE_CORRECTION` — state machine régimen + boost dinámico explosivas
- [ ] Filtro `BARRIDA_OPPORTUNITY` — detector spikes intradía AI-Infra/Nuclear con VIX<22+SP500>7000
- [ ] Enforcement real `MAX_PER_CLUSTER_BY_CLUSTER` — count posiciones open en `tracker.py`
- [ ] Fetch BTC current en `stock_watchdog` para enforcement de `CRYPTO_PROXY_BTC_GATE`
- [ ] `MACRO_BONDS_WATCH` — agregar alertas si TLT/TBT spike >X% (define threshold)
- [ ] Auto-rotación semanal `WEEK_PRIORITY_*` (parsear nuevo reporte PTS via skill `cortex-macro-intel`)

## Backlog P2

- [ ] Notebook 2: Catalyst Calendar 26-30 May (FOMC + earnings + macro)
- [ ] Notebook 3: Bot Performance Audit (trades.db + signal_episodes)
- [ ] Auto-trigger NotebookLM refresh cada lunes con nuevo corpus
- [ ] Dashboard live: stale check de `WEEK_REVIEW_DATE` visual en HTML
