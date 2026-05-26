# Plan 020 — Dashboard Intel Endpoints

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Import lazy en cada endpoint

```python
@app.route('/api/metrics/regime')
def api_metrics_regime():
    try:
        import regime_hmm
        ...
    except ImportError:
        return jsonify({'error': 'regime_hmm module not available'}), 503
```

Razón:
- Si Railway tiene `hmmlearn` missing → endpoint regime falla con 503 pero los OTROS endpoints siguen funcionando
- Cero impact en boot time del bot (modules pesados solo se importan al hit del endpoint)
- Acoplamiento mínimo entre app.py y modules intel

### 2. Flask `<path:symbol>` converter

`/api/metrics/cvd/BTC/USDT` — el "/" en BTC/USDT necesita path converter (default `<string>` no permite slash).

```python
@app.route('/api/metrics/cvd/<path:symbol>')
def api_metrics_cvd(symbol: str):
```

### 3. Query params para flexibilidad

- `?symbols=BTC/USDT,ETH/USDT` — CSV — comma-separated
- `?lookback_hours=24` — int default
- Validación mínima — si llega "foo" → falla en el módulo, exception → 500 con mensaje

### 4. NO incluyo dashboard HTML changes en este spec

Razón: modificar `dashboard_live.html` requeriría refactor del template existente + nuevo JS para fetch + render dinámico. Scope creep.

Spec 020.5 candidato: Frontend tweak para mostrar regime cards + CVD chart.

### 5. Cada endpoint retorna `generated_at` timestamp

Permite al frontend mostrar staleness del dato sin necesitar otro endpoint de health.

### 6. Status codes:
- 200 OK con datos
- 200 OK con dict vacío (cache miss, símbolo no encontrado — el módulo decide)
- 503 si module ImportError (degradación graceful)
- 500 si runtime error

## Verificación

- ✅ py_compile app.py
- ✅ 4 endpoints definidos via AST
- Producción pendiente: test manual con curl en Railway

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(dashboard): spec-020 intel endpoints — regime, CVD, onchain, social` |

## Backlog Spec 020.5

- Frontend tweak: regime cards en `dashboard_live.html`
- CVD chart over time (necesita time-series storage, Spec 012.6 dependency)
- HTTP Basic auth en `/api/metrics/*` (Spec 015.5 candidato)
- Endpoint `/api/metrics/grounded_search/usage` (Spec 014.6)
- Endpoint `/api/metrics/regime/history` (HMM persistence Spec 009.5)
- Caching response headers (`Cache-Control: max-age=60`)
