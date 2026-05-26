# Tasks 015 — Live Metrics Dashboard

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] `dashboard_metrics.py` nuevo módulo con funciones:
  - [x] `compute_global_wr()` → dict
  - [x] `compute_wr_by_symbol()` → dict {symbol: {...}}
  - [x] `compute_wr_by_strategy()` → dict {strategy: {...}}
  - [x] `get_recent_trades(n=20)` → list[dict]
  - [x] `get_signal_episodes_summary()` → dict
  - [x] `get_dashboard_snapshot()` → dict agregado para template
- [x] `templates/dashboard_live.html` creado
  - [x] Dark theme con paleta consistente vs `index.html`
  - [x] Mobile responsive (grid colapsa a 1 columna <720px)
  - [x] Header con generated_at + total trades
  - [x] WR badge color-coded (red/yellow/green @ 30%/50%)
  - [x] Tabla por símbolo con WR pill colorizada
  - [x] Tabla por estrategia con WR pill colorizada
  - [x] Recent activity tabla con status badges
  - [x] Signal episodes summary con orphans count
  - [x] Auto-refresh 60s con visibility check
- [x] Routes nuevas en `app.py` (sin tocar las existentes):
  - [x] `GET /dashboard/live` HTML
  - [x] `GET /api/metrics/wr` JSON
  - [x] `GET /api/metrics/recent_trades` JSON con `?n=` param
  - [x] `GET /api/metrics/signal_episodes_summary` JSON
- [x] `import dashboard_metrics` en `app.py`
- [x] py_compile verification
- [x] Smoke test `python3 -c "from dashboard_metrics import compute_global_wr; print(compute_global_wr())"`
- [ ] Commit `feat(dashboard): spec-015 live metrics dashboard`
- [ ] Push origin/main
- [ ] Deploy Railway (auto on push)

## Verificación post-deploy

- [ ] `curl https://scalp-bot.railway.app/dashboard/live` → 200 HTML
- [ ] `curl https://scalp-bot.railway.app/api/metrics/wr` → 200 JSON
- [ ] Abrir en móvil → render sin overflow horizontal
- [ ] Auto-refresh observado en DevTools Network tab (cada 60s exact)
- [ ] Tab oculta → no requests durante hide (visibility check funcional)
- [ ] Latencia p50 `/api/metrics/wr` < 100ms

## Tuning post-7d

- [ ] Si dashboard se usa diario → confirmar valor antes de invertir en 015.5+
- [ ] Si Fernando pide gráficas → priorizar Spec 015.6 (Chart.js equity curve)
- [ ] Si Railway log muestra spam GET /dashboard/live → ajustar refresh a 120s o agregar cache layer

## Próximos specs roadmap

- [ ] **Spec 015.5** — HTTP Basic auth (DASHBOARD_USER/PASS env)
- [ ] **Spec 015.6** — Equity curve Chart.js
- [ ] **Spec 015.7** — Filtros UI (date range, symbol filter)
- [ ] **Spec 015.8** — `/api/metrics/regime` endpoint (HMM Spec 009 hook)
- [ ] **Spec 015.9** — `/api/metrics/budget_burn` (ai_budget integration)

## Backlog técnico

- [ ] Si trades.db crece >10k rows → agregar índice en `(open_time DESC)` para `get_recent_trades`
- [ ] Si DB lock se vuelve frecuente → considerar `PRAGMA journal_mode=WAL` explícito en main
- [ ] Considerar exportar `/api/metrics/snapshot` agregado (todo en 1 call) para clientes externos
