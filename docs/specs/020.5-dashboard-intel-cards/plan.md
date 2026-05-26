# Plan 020.5 — Dashboard Intel Cards

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Vanilla JS fetch async (no frameworks)

Mantiene filosofía Spec 015. Razones:
- No build step (no webpack, no transpiler)
- No bundle bloat (Bootstrap/jQuery/React/Vue + CSS frameworks)
- Carga rápida en mobile
- Cero CDN dependency (Railway egress)

### 2. Promise.all paralelo

```javascript
async function loadAll() {
    await Promise.all([loadRegimes(), loadCVD(), loadWhale(), loadSocial()]);
}
```

4 endpoints en paralelo. Latencia total = max(4) en lugar de sum(4). Si endpoint individual falla, los otros siguen.

### 3. Color coding intuitive

```javascript
function regimeColor(r) {
    if (r === 'STRONG_TREND') return '#48BB78';   // green
    if (r === 'RANGE') return '#F6E05E';           // yellow
    if (r === 'VOLATILE_SQUEEZE') return '#FC8181'; // red
}

function signalColor(s) {
    if (s === 'BULLISH' || s === 'FEAR') return '#48BB78';
    if (s === 'BEARISH' || s === 'EUPHORIA') return '#FC8181';
}
```

Tailwind-inspired hex. Consistente con sentimiento (bullish = green even si signal es FEAR — porque FEAR retail = bottom = bullish for V3 LONG).

### 4. Grid responsive con `auto-fill`

```css
grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
```

Mobile <320px: 1 columna. Desktop wide: 5+ columnas. Browser nativo, sin media queries.

### 5. Cards independientes inline-styled

En lugar de class CSS shared, inline-styled. Razón:
- Fácil de modificar individual sin tocar CSS principal
- Self-contained html string en template literal
- Match con estilo card existente (rgba background, border-radius 6px)

### 6. Status indicator "updated HH:MM:SS"

```javascript
el.textContent = 'updated ' + new Date().toLocaleTimeString();
```

Fernando ve cuándo fue el último fetch. Útil debug si data parece stale.

### 7. setInterval 30s para intel-only (página reload 60s)

Intel updates 2x más frecuente que page reload. Razón:
- WR/trades change slow (60s reload OK)
- Intel (régimen, CVD, social) más volátil
- Update via fetch evita perder scroll position

### 8. Trailing /api/metrics/intel_ab en footer

Agrego link al endpoint Spec 022 (A/B test). Fernando puede hacer curl si quiere ver stats raw.

## Verificación

- ✅ Edit aplicado a templates/dashboard_live.html
- ✅ 4 IDs nuevos: regime-cards, cvd-cards, whale-card, social-cards
- ✅ IIFE async + Promise.all + setInterval 30s
- ✅ Color helpers + endpoints fetch correctos
- Producción pendiente: navegar a /dashboard/live después de deploy

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(dashboard): spec-020.5 frontend intel cards — HMM + CVD + Whale + Social` |

## Backlog Spec 020.6

- Charts time-series via Chart.js CDN (régimen history, CVD over time)
- Endpoint `/api/metrics/regime_transitions` (Spec 002.6) + visualization
- Botones manual refresh
- HTTP Basic auth (Spec 015.5)
- Telegram /dashboard link helper
- WebSocket push real-time (futuro)
