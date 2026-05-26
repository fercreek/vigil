# Plan 020.6 — Dashboard Chart.js Time-Series

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Chart.js v4.4.0 vía CDN jsdelivr (no npm, no build)

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
```

Razones:
- Versión 4.x es current major (v4.4.0 estable, sin v5 breaking changes)
- UMD build = global `Chart` accesible en vanilla JS
- jsdelivr CDN = fast, immutable URL (no risk de version drift)
- Filosofía Spec 015: cero build step. Chart.js es **library** (no framework como React/Vue). Compatible con vanilla JS.
- Bundle ~70KB minified — aceptable para dashboard interno

Alternativas descartadas:
- ApexCharts: bundle más grande, API verbosa
- D3.js: low-level, requiere mucho boilerplate para charts simples
- Recharts: React-only, no fit con vanilla JS

### 2. Backend helper SQL approach (`compute_wr_over_time(days=30)`)

```sql
SELECT
    DATE(open_time) AS day,
    SUM(CASE WHEN status IN ('FULL_WON','WON','PARTIAL_CLOSED') THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN status='LOST' THEN 1 ELSE 0 END) AS losses,
    COUNT(*) AS total
FROM trades
WHERE open_time >= date('now', ?)
  AND open_time IS NOT NULL
GROUP BY day
ORDER BY day ASC
LIMIT 60
```

- `?` recibe `'-30 days'` parametrizado para evitar SQL injection
- ORDER BY ASC para que Chart.js plotee de izq→der naturalmente
- LIMIT 60 hard cap (anticipando >30 días futuros)
- WHERE `open_time IS NOT NULL` evita rows con timestamps incompletos
- Return list of dicts `[{date, wr, total, wins}, ...]` — Chart.js-friendly

### 3. Color line dinámico (trend-based)

```javascript
function trendColor(daily) {
    if (daily.length < 5) return '#48BB78'; // default green
    const n = daily.length;
    const first5 = daily.slice(0, Math.min(5, n));
    const last5 = daily.slice(Math.max(0, n - 5));
    const avgFirst = first5.reduce((a, d) => a + d.wr, 0) / first5.length;
    const avgLast = last5.reduce((a, d) => a + d.wr, 0) / last5.length;
    return avgLast >= avgFirst ? '#48BB78' : '#FC8181';
}
```

Decisión simple: comparación de medias de primeros 5 vs últimos 5 días. Robusto contra outliers (vs comparar solo primer y último día).

### 4. Bar color por WR threshold

Reutiliza `wrColor(wr)` del prompt:
```javascript
function wrColor(wr) {
    if (wr < 30) return '#FC8181';
    if (wr < 50) return '#F6E05E';
    return '#48BB78';
}
```

3 buckets boost_0/boost_1+/boost_3+ → 3 colores independientes basados en su propio WR.

### 5. Auto-refresh charts cada 5min (300000ms)

Vs Spec 020.5 intel cards 30s:
- Historical data (WR diario, A/B stats) no cambia segundo a segundo
- Reduce queries SQL a `trades` table (más pesada que intel module fetches)
- 5min es buen trade-off entre freshness y carga DB
- Page reload Spec 015 sigue siendo 60s (no afecta)

```javascript
setInterval(loadCharts, 5 * 60 * 1000);
```

### 6. Reusar `wrColor()` y crear `chartContext` global

Para evitar duplicar el helper de color del prompt, declarar `wrColor` arriba del IIFE de charts (separado del IIFE de intel Spec 020.5). Funciones globales no needed — cada IIFE self-contained.

### 7. Lifecycle de Chart.js (destroy + recreate en refresh)

```javascript
let equityChart = null;
async function loadEquityCurve() {
    const data = await fetchJson('/api/metrics/wr_timeseries');
    if (!data || !data.daily) { /* show — */ return; }
    if (equityChart) equityChart.destroy(); // critical: avoid memory leak
    equityChart = new Chart(ctx, { ... });
}
```

Chart.js v4 requiere `.destroy()` antes de recrear sobre mismo canvas. Sin esto → memory leak + canvas con datos viejos overlay.

### 8. Endpoint `/api/metrics/wr_timeseries` separado (no embed en `/api/metrics/wr`)

Razones:
- Separation of concerns: `/wr` es snapshot point-in-time
- Cache headers diferentes posibles en futuro (timeseries más cacheable)
- Endpoint dedicado más testeable individualmente
- Match con pattern Spec 020 (cada intel module su propio endpoint)

### 9. Try/catch graceful en chart render

Si Chart.js CDN falla o crash en parse JSON → mostrar mensaje en `chart-status` div:
```javascript
try {
    if (typeof Chart === 'undefined') {
        document.getElementById('chart-status').textContent = 'Chart.js CDN no disponible';
        return;
    }
    // render
} catch (e) {
    console.error('[chart error]', e);
}
```

### 10. Coexistencia con Spec 015 + 020.5 scripts

Tres IIFEs independientes en `<script>`:
1. Page reload 60s (Spec 015 existente — intacto)
2. Intel cards 30s refresh (Spec 020.5 existente — intacto)
3. Charts 5min refresh (Spec 020.6 nuevo)

Cada uno con su propio scope + setInterval. Sin shared state. Sin race conditions.

## Verificación

- ✅ `compute_wr_over_time(30)` en `dashboard_metrics.py`
- ✅ Endpoint `/api/metrics/wr_timeseries` en `app.py`
- ✅ Section "📊 Histórico Performance" en `templates/dashboard_live.html`
- ✅ Chart.js CDN script tag en `<head>` o pre-script
- ✅ IIFE de charts independiente con setInterval 5min
- ✅ Smoke test `python3 -c "import dashboard_metrics; ..."` OK
- ✅ `python3 -m py_compile` OK ambos archivos
- Producción pendiente: verificar charts render en `/dashboard/live` post-deploy

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(dashboard): spec-020.6 chart.js time-series — equity curve + boost segments` |

## Backlog Spec 020.7

- Multi-line chart: WR overlapped por regime (STRONG_TREND vs RANGE vs VOLATILE_SQUEEZE) en el mismo timeline
- Charts: distribución de boost_applied (histogram, no solo buckets)
- Botón "export PNG" para charts (Chart.js built-in `chart.toBase64Image()`)
- Endpoint `/api/metrics/regime_history` para overlay régimen en equity curve
- Cache de `wr_timeseries` (60s TTL) en memoria para reducir queries DB
- Mobile-optimized chart layouts (<320px)
