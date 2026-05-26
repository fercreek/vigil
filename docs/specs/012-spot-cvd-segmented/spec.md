# Spec 012 — Spot CVD Segmentado (Cumulative Volume Delta)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — Mes 3 Sem 9 roadmap NotebookLM 4 (último del roadmap)
> **Origen:** `docs/research/notebook-lm-4/RESULTS.md` Prompt 1 #2 + Prompt 3 #4 + Prompt 6 Spec 013

## Contexto

NotebookLM 4 identificó CVD Segmentado como TOP 2 estrategia faltante (después de Funding Rate filter, Spec 006). El "edge real institucional" según el análisis NO está en SMC dibujado en gráficas, sino en ver el flujo real de órdenes — si las ballenas (>$100k) acumulan mientras retail (<$1k) vende panic.

Procesa la API `binance_spot.fetch_trades(symbol, limit=1000)` que retorna las últimas N trades con `{amount, price, side, timestamp}`. Clasifica por tamaño de orden (cost = amount × price) en 3 buckets y suma buy - sell por bucket.

## Goals

1. Módulo standalone `cvd_segmented.py` con:
   - `compute_cvd_segmented(symbol, lookback_trades=1000)` → dict completo
   - `format_cvd_summary(cvd)` → string conciso para inyectar en prompts AI
   - `_classify_bucket(cost_usd)` → 'retail' / 'mid' / 'whale'
   - `_classify_divergence(retail_cvd, mid_cvd, whale_cvd)` → 'BEARISH' / 'BULLISH' / 'NEUTRAL'
2. Cache 60s (trades volátiles, cache corto)
3. Sin tocar otros archivos en este spec (hooks → Spec 012.5)

## Buckets

| Bucket | Rango USD | Línea (NotebookLM convention) |
|--------|-----------|-------------------------------|
| retail | < $1,000 | amarilla |
| mid | $1,000 - $100,000 | naranja |
| whale | >= $100,000 | marrón |

## Divergence signal

| Condición | Signal | Interpretación |
|-----------|--------|----------------|
| whale_cvd < -$50k AND retail_cvd > +$50k | BEARISH | Ballenas venden, retail compra → top inminente |
| whale_cvd > +$50k AND retail_cvd < -$50k | BULLISH | Ballenas acumulan, retail vende → bottom inminente |
| Otro | NEUTRAL | Sin divergencia accionable |

## Non-goals

- Wire en Cuadrilla Zenith voz Genesis o Salmos — Spec 012.5 candidato
- Time-series CVD (gráfica multi-bar) — solo snapshot último 1000 trades
- Múltiples exchanges (Bybit, Coinbase) — solo Binance Spot
- Persistencia histórica del CVD — cache in-memory

## Dependencias

- `ccxt` ✅ usado en exchange_singleton
- `exchange_singleton.binance_spot` ✅ ya configurado (`fetch_trades`)
- `logger_core.logger` ✅ existe

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| `fetch_trades` rate limit Binance (~10 calls/sec) | Cache 60s. 5 símbolos × 1 call/min = bajo rate. |
| Trades volátiles → CVD oscila mucho | Threshold $50k para divergence evita ruido + cache 60s smooth |
| Side puede ser None en algunos exchanges | Skip trades sin side válido en loop |
| Bucket thresholds ($1k retail, $100k whale) están hardcoded | Documented in module top — Spec 012.5 puede mover a config si validado |
| Resultado depende de cuánto historia hay | Min 10 trades requirement; <10 → return empty dict |

## Criterio de aceptación

1. `python3 -m py_compile cvd_segmented.py` → OK
2. AST funciones: `_classify_bucket`, `_classify_divergence`, `_cache_get`, `_cache_set`, `compute_cvd_segmented`, `format_cvd_summary`
3. Dispatcher tests:
   - bucket: $500 → retail, $5000 → mid, $150k → whale ✓
   - divergence BEARISH: retail +60k & whale -60k ✓
   - divergence BULLISH: retail -60k & whale +60k ✓
   - divergence NEUTRAL: ambos signo same ✓
4. format_cvd_summary devuelve string compacto para AI prompt
5. Empty dict graceful si exchange_singleton no disponible
6. Producción pendiente: Spec 012.5 hace wire + valida con trades reales
