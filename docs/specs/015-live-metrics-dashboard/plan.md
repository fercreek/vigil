# Plan 015 — Live Metrics Dashboard

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Estrategia

Capa servidor-render mínima sobre Flask existente. Nuevo módulo `dashboard_metrics.py` con SQL aislado, nuevo template `dashboard_live.html`, 4 routes nuevas en `app.py` (sin tocar las existentes).

## Decisiones técnicas

### 1. Server-side render vs SPA

**Decisión:** Jinja2 server-side render.

Razón:
- Bot ya usa Jinja2 — coste cero, sin nuevo build pipeline
- 60s refresh es aceptable (Fernando ve el dashboard, no opera contra él en milisegundos)
- Sin React/Vue → sin npm, sin bundler, sin frontend toolchain
- Mobile-friendly por defecto sin viewport JS hacks
- Endpoints JSON siguen disponibles si en futuro queremos SPA

Trade-off aceptado: reload completo cada 60s vs partial update. Para 91 trades + 39 episodes, payload es <50KB.

### 2. Color thresholds WR badges

```
WR < 30%   → RED    (señal de problema, requiere acción)
30 ≤ WR < 50% → YELLOW (mediocre, observar)
WR ≥ 50%   → GREEN  (aceptable, dejar correr)
```

Razón: alinea con benchmarks NotebookLM 3 (SWING target 60%+, COMMODITY 53-61%). Sub-30% = bot perdiendo dinero netamente — debe alertar visualmente. Estos thresholds aplican a global, por símbolo y por estrategia.

### 3. SQL aislado en `dashboard_metrics.py`

Razón:
- Flask routes deben ser delgadas (orquestación, no SQL)
- Funciones testeables sin spin-up de Flask
- Reutilizable desde `daily_report.py` o agentes futuros (Cuadrilla Zenith podría consumir `compute_wr_by_symbol()` directo)
- Patrón consistente con `tracker.py` y `metrics.py`

### 4. Conexión read-only + timeout 2s

```python
sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True, timeout=2.0)
```

Razón:
- `mode=ro` previene cualquier accidente de mutación desde el dashboard
- `timeout=2.0` evita que un lock del bot main cause hang del dashboard
- Bot main usa WAL → reads concurrentes a writes están permitidas

### 5. Status mapping para WIN/LOSS

```python
WIN_STATUSES  = ('FULL_WON', 'WON', 'PARTIAL_CLOSED')
LOSS_STATUSES = ('LOST',)
```

`PARTIAL_CLOSED` cuenta como win porque ya hubo realización de ganancia en TP1 (consistente con `tracker.get_win_rate`).

Otros statuses (`None`, `OPEN`, custom) cuentan como "open" — total - wins - losses.

### 6. LIMIT en todas las queries

- `by_symbol`: LIMIT 50 (cubre cripto + watchlist completa NYSE+stocks PTS)
- `by_strategy`: LIMIT 20 (V1-TECH, V2-AI, SWING, COMMODITY, MANUAL, V3-Reversal, BITLOBO, STOCK... <20)
- `recent_trades`: LIMIT n, n max 200 (input validado)
- `signal_episodes by_source`: LIMIT 20

Razón: anticipar >10k rows futuros sin re-arquitectura. Latencia objetivo <100ms.

### 7. Auto-refresh con visibility check

```javascript
setTimeout(() => {
    if (document.visibilityState === 'visible') {
        window.location.reload();
    } else {
        scheduleReload(); // re-arm si tab oculta
    }
}, 60000);
```

Razón: Fernando deja el tab abierto en background. Sin el check, Railway free tier come bandwidth innecesario. Con el check, sólo refresca cuando el tab está visible.

### 8. NO Chart.js / Plotly esta versión

Razón:
- 91 trades / 39 episodes → tablas + badges son suficientes
- CDN externo = punto de falla si Railway tiene egress filtering
- Spec 015.6 candidato cuando volumen justifique gráficas
- Pure HTML + CSS rinde más rápido en mobile

### 9. Template extiende paleta dark de `index.html`

Mismo `--bg`, `--surface`, `--green/red/yellow` que existing template. Razón: consistencia visual con dashboard principal del bot, Fernando navega entre ambos.

## Verificación

- [x] `py_compile dashboard_metrics.py app.py`
- [x] `python3 dashboard_metrics.py` produce JSON válido
- [x] `python3 -c "from dashboard_metrics import compute_global_wr; print(compute_global_wr())"`
- [ ] Curl local `http://localhost:5001/dashboard/live` (post-deploy)
- [ ] Mobile render DevTools 375px (post-deploy)

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(dashboard): spec-015 live metrics dashboard` — `dashboard_metrics.py`, `templates/dashboard_live.html`, routes en `app.py` |

## Backlog Spec 015.x

- **Spec 015.5** — Auth básico (HTTP Basic + env `DASHBOARD_USER/PASS`) si Railway URL se vuelve discoverable
- **Spec 015.6** — Equity curve chart (acumulado P&L vs tiempo) con Chart.js cuando trades > 200
- **Spec 015.7** — Filtros UI (date range, symbol multi-select, strategy filter)
- **Spec 015.8** — Endpoint `/api/metrics/regime` cuando HMM Spec 009 esté hooked en config (mostrar régimen activo: VERDE_BULL / AMARILLA / NARANJA_BEAR)
- **Spec 015.9** — Endpoint `/api/metrics/budget_burn` integrando `ai_budget` para ver $ gastado en Gemini/Claude vs presupuesto
