# Tasks 020.6 — Dashboard Chart.js Time-Series

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] Helper `compute_wr_over_time(days=30)` en `dashboard_metrics.py`
  * SQL GROUP BY DATE(open_time), filtrado últimos 30 días
  * Return list `[{date, wr, total, wins}, ...]` ordenado ASC
  * Try/except → list vacío en error
- [x] Endpoint `/api/metrics/wr_timeseries` en `app.py`
  * Llama `compute_wr_over_time(30)`
  * Retorna JSON `{daily: [...], generated_at}`
- [x] Sección "📊 Histórico Performance" en `templates/dashboard_live.html`
  * Después de Spec 020.5 intel cards, antes de footer
  * 2 canvas: `equity-curve-chart` + `boost-segments-chart`
  * Status indicator `chart-status`
- [x] Chart.js v4.4.0 CDN script tag agregado
- [x] IIFE charts independiente del IIFE Spec 020.5
  * `wrColor(wr)` helper
  * `trendColor(daily)` para línea equity curve
  * `loadEquityCurve()` async + fetchJson
  * `loadBoostSegments()` async + fetchJson `/api/metrics/intel_ab`
  * `destroy()` antes de recrear chart (evita memory leak)
  * `setInterval(loadCharts, 5 * 60 * 1000)` 5min refresh
- [x] Smoke test `python3 -m py_compile dashboard_metrics.py app.py` OK
- [x] Smoke test `compute_wr_over_time(30)` retorna lista válida
- [x] Footer actualizado con link `/api/metrics/wr_timeseries`
- [ ] Commit `feat(dashboard): spec-020.6 chart.js time-series — equity curve + boost segments` (main thread)
- [ ] Push origin/main (main thread)

## Verificación post-deploy

- [ ] Abrir `https://[railway]/dashboard/live` en browser
- [ ] Sección "📊 Histórico Performance" visible
- [ ] Equity curve chart renderiza línea con datos 30 días
- [ ] Color línea verde (alcista) o rojo (bajista) según trend
- [ ] Tooltip hover muestra "DD/MM · N trades · YY% WR"
- [ ] Boost segments bar chart muestra 3 barras coloreadas
- [ ] Hover barras muestra "N trades · WR% X"
- [ ] Auto-refresh charts cada 5min sin reload página
- [ ] Spec 015 + 020.5 sections intactas

## Backlog Spec 020.7

- [ ] Multi-line chart: WR overlapped por regime (STRONG_TREND/RANGE/SQUEEZE)
- [ ] Histogram distribución `boost_applied` raw values
- [ ] Botón export PNG (`chart.toBase64Image()`)
- [ ] Endpoint `/api/metrics/regime_history` para overlay régimen
- [ ] Cache 60s in-memory para `wr_timeseries`
- [ ] Mobile-optimized charts <320px
