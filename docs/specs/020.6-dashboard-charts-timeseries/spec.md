# Spec 020.6 — Dashboard Chart.js Time-Series (Equity Curve + Boost Segments)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P2 — visibilidad histórica complementa Spec 020.5 cards
> **Origen:** Spec 020.5 backlog ("Charts time-series via Chart.js CDN")

## Contexto

Spec 015 (Live Metrics Dashboard) muestra WR + tablas point-in-time. Spec 020.5 agregó intel cards de estado actual (HMM/CVD/Whale/Social). Falta **historia visual**: Fernando no ve trayectoria del WR a lo largo del tiempo ni comparativa visual de los buckets boost del A/B test (Spec 022).

Spec 020.6 agrega 2 charts time-series en dashboard_live.html usando Chart.js vía CDN (cero build step, vanilla JS).

## Goals

1. Nueva sección "📊 Histórico Performance" en dashboard_live.html, después de Intel cards (Spec 020.5) y antes del footer.
2. **Equity Curve chart** — WR diario últimos 30 días:
   - X-axis: fecha DD/MM
   - Y-axis: WR%
   - Color line dinámico: verde si tendencia alcista (mean last 5 > mean first 5), rojo si bajista
   - Tooltip: "DD/MM · N trades · YY% WR"
3. **Boost Segments Bar chart** — comparativa WR por boost bucket (reusa `get_intel_ab_stats()` Spec 022):
   - 3 barras: boost_0 / boost_1+ / boost_3+
   - Y-axis: WR%
   - Color por bar: rojo <30%, amarillo 30-50%, verde >50%
   - Hover: "N trades · WR% X"
4. Auto-refresh charts cada 5min (slower que Spec 020.5 intel — historical data no cambia rápido).
5. Backend helper `compute_wr_over_time(days=30)` en `dashboard_metrics.py` + endpoint `/api/metrics/wr_timeseries`.

## Non-goals

- Charts multi-line (régimen overlap, boost+regime cross-time) — Spec 020.7
- WebSocket push real-time — futuro
- Drag-to-zoom / pan en charts — Chart.js zoom plugin no incluido
- Exportar PNG/CSV — Spec 020.8
- Charts en mobile <320px optimizado — Chart.js responsive default es OK
- Auth/Basic Auth (Spec 015.5)

## Dependencias

- `templates/dashboard_live.html` ✅ Spec 015 + 020.5
- `dashboard_metrics.py` ✅ Spec 015 (helpers SQL pattern)
- `tracker.get_intel_ab_stats()` ✅ Spec 022 (boost_segments data)
- `trades.db` schema: `trades` (open_time, status), `intel_outcomes` (boost_applied, outcome)
- Chart.js v4.4.0 CDN: `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js`

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Chart.js CDN failure → no charts render | Vanilla JS try/catch + status message "—" en sección |
| 30 días de trades = muchas rows → SQL slow | `WHERE open_time >= date('now','-30 days')` + GROUP BY DATE + LIMIT 60 |
| Días sin trades = gaps en línea | SQL devuelve solo días con trades. Chart.js conecta puntos linealmente (acceptable para WR trend visual) |
| Boost segments vacío si Spec 022 sin data | Bar chart muestra 0 + status "sin data A/B" — no crash |
| Race condition refresh con Spec 020.5 30s | Charts usan setInterval 5min independiente. Cada chart con su lifecycle. |
| Bundle size CDN ~70KB Chart.js v4 | Aceptable — Fernando solo abre dashboard en wifi, no mobile data |
| Mantener filosofía Spec 015 (no frameworks) | Chart.js es **library** (no framework, no JSX/build). Solo CDN + vanilla JS. |

## Criterio de aceptación

1. Abrir `/dashboard/live` → sección "📊 Histórico Performance" visible
2. Equity Curve chart renderiza con datos últimos 30 días
3. Color línea verde si WR mejorando, rojo si empeorando
4. Tooltip hover muestra fecha + N trades + WR%
5. Boost Segments bar chart muestra 3 barras con colores por WR threshold
6. Endpoint `GET /api/metrics/wr_timeseries` retorna JSON `{daily: [...], generated_at}`
7. Smoke test `python3 -c "import dashboard_metrics; print(dashboard_metrics.compute_wr_over_time(30))"` no crash
8. Auto-refresh charts cada 5min sin reload página
9. Si Chart.js CDN fail → sección muestra "—" no crash page
10. Secciones Spec 015 + 020.5 intactas (no romper auto-refresh existente)
